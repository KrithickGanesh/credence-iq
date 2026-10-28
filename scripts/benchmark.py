"""CredenceIQ performance benchmark: legacy per-customer queries vs one Exasol pass.

The benchmark contrasts two access patterns over the *same* data:

* **Legacy N+1** — the application issues separate round-trips for the customer,
  bureau record, latest application, and every exposure row, then reconciles in
  Python. This mirrors a transactional service composing an applicant view.
* **Single set-based query** — one Exasol query against
  ``V_RECONCILED_CREDIT_360`` returns the same reconciled profile for every
  sampled customer.

Run after seeding:

    python scripts/benchmark.py --sample 100
    python scripts/benchmark.py --sample 250 --runs 5 --json benchmarks/results/run.json
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import pyexasol
except ImportError:  # pragma: no cover - friendly message on a bare interpreter
    sys.exit("pyexasol is required. Install it with: pip install -r backend/requirements.txt")


IDENTIFIER = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8563)
    parser.add_argument("--user", default="sys")
    parser.add_argument("--password", default="exasol")
    parser.add_argument("--schema", default="CREDENCEIQ")
    parser.add_argument("--sample", type=int, default=100, help="customers in the comparison (1-1000)")
    parser.add_argument("--runs", type=int, default=3, help="measured repetitions")
    parser.add_argument(
        "--json",
        default="",
        help="optional output path; defaults to benchmarks/results/benchmark-<timestamp>.json",
    )
    return parser.parse_args()


def connect(args: argparse.Namespace) -> pyexasol.ExaConnection:
    schema = args.schema.strip().upper()
    if not IDENTIFIER.fullmatch(schema):
        raise SystemExit("--schema must be a simple SQL identifier")
    return pyexasol.connect(
        dsn=f"{args.host}:{args.port}",
        user=args.user,
        password=args.password,
        compression=True,
        encryption=True,
        websocket_sslopt={"cert_reqs": ssl.CERT_NONE},
        fetch_dict=True,
        lower_ident=True,
        connection_timeout=20,
        socket_timeout=300,
    )


def fetch_ids(con: pyexasol.ExaConnection, schema: str, sample: int) -> list[int]:
    sql = (
        f"SELECT customer_id FROM {schema}.V_RECONCILED_CREDIT_360 "
        "ORDER BY customer_id LIMIT {limit}"
    )
    rows = con.execute(sql.format(limit=sample)).fetchall()
    return [int(row["customer_id"]) for row in rows]


def portfolio_totals(con: pyexasol.ExaConnection, schema: str) -> dict[str, Any]:
    sql = f"""
        SELECT
            COUNT(*) AS customers,
            SUM(gross_exposure) AS gross_exposure,
            SUM(reconciled_exposure) AS reconciled_exposure,
            SUM(debt_variance) AS variance,
            AVG(variance_ratio) AS avg_variance_ratio
        FROM {schema}.V_RECONCILED_CREDIT_360
    """
    return con.execute(sql).fetchone() or {}


def legacy_profile(con: pyexasol.ExaConnection, schema: str, customer_id: int) -> dict[str, Any]:
    """Simulate a transactional service composing one applicant profile."""

    customer = con.execute(
        f"SELECT customer_id, annual_income FROM {schema}.CUSTOMERS WHERE customer_id = {{cid}}",
        {"cid": customer_id},
    ).fetchone()
    bureau = con.execute(
        f"""
        SELECT bureau_score, utilization_ratio
        FROM {schema}.CREDIT_BUREAU_RECORDS
        WHERE customer_id = {{cid}}
        ORDER BY report_date DESC
        LIMIT 1
        """,
        {"cid": customer_id},
    ).fetchone()
    application = con.execute(
        f"""
        SELECT application_id, requested_amount, dti_ratio
        FROM {schema}.LOAN_APPLICATIONS
        WHERE customer_id = {{cid}}
        ORDER BY application_date DESC
        LIMIT 1
        """,
        {"cid": customer_id},
    ).fetchone()
    exposures = con.execute(
        f"""
        SELECT facility_ref, outstanding_balance, sanctioned_limit
        FROM {schema}.SYSTEM_EXPOSURES
        WHERE customer_id = {{cid}}
        """,
        {"cid": customer_id},
    ).fetchall()

    facilities: dict[str, float] = {}
    gross = 0.0
    for row in exposures:
        gross += float(row["outstanding_balance"] or 0)
        ref = str(row["facility_ref"])
        facilities[ref] = max(facilities.get(ref, 0.0), float(row["outstanding_balance"] or 0))
    reconciled = sum(facilities.values())
    return {
        "customer_id": customer_id,
        "bureau_score": (bureau or {}).get("bureau_score"),
        "requested_amount": (application or {}).get("requested_amount"),
        "annual_income": (customer or {}).get("annual_income"),
        "gross_exposure": round(gross, 2),
        "reconciled_exposure": round(reconciled, 2),
        "facilities": len(facilities),
    }


def single_pass(
    con: pyexasol.ExaConnection, schema: str, ids: list[int]
) -> tuple[list[dict[str, Any]], float]:
    placeholders = ", ".join(str(int(value)) for value in ids)
    started = time.perf_counter()
    rows = con.execute(
        f"""
        SELECT
            customer_id, bureau_score, latest_requested_amount,
            latest_income, gross_exposure, reconciled_exposure,
            debt_variance, variance_ratio, conflicted_facilities
        FROM {schema}.V_RECONCILED_CREDIT_360
        WHERE customer_id IN ({placeholders})
        ORDER BY customer_id
        """
    ).fetchall()
    elapsed_ms = (time.perf_counter() - started) * 1000
    return list(rows), elapsed_ms


def measure(fn, runs: int) -> tuple[float, list[float]]:
    samples: list[float] = []
    for _ in range(runs):
        started = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - started) * 1000)
    return statistics.median(samples), samples


def main() -> None:
    args = parse_args()
    sample = max(1, min(args.sample, 1000))
    runs = max(1, args.runs)
    con = connect(args)
    schema = args.schema.strip().upper()

    try:
        version = str(con.exasol_db_version)
        ids = fetch_ids(con, schema, sample)
        if not ids:
            raise SystemExit("No rows found. Run `python seed_data.py --reset` first.")

        totals = portfolio_totals(con, schema)
        print(f"CredenceIQ benchmark | Exasol {version} | schema {schema}")
        print(
            f"Sample {len(ids):,} customers of {int(totals.get('customers') or 0):,} "
            f"| {runs} measured run(s)\n"
        )

        # Warm both paths once.
        legacy_profile(con, schema, ids[0])
        single_pass(con, schema, ids[: min(5, len(ids))])

        legacy_ms, legacy_samples = measure(
            lambda: [legacy_profile(con, schema, customer_id) for customer_id in ids],
            runs,
        )
        one_pass_ms, one_pass_samples = measure(lambda: single_pass(con, schema, ids), runs)

        def portfolio() -> None:
            portfolio_totals(con, schema)

        portfolio_ms, portfolio_samples = measure(portfolio, runs)

        legacy_queries = len(ids) * 4
        speedup = legacy_ms / one_pass_ms if one_pass_ms else float("inf")
        reduction = 1 - (one_pass_ms / legacy_ms) if legacy_ms else 0.0

        result = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "exasol_version": version,
            "schema": schema,
            "sample_customers": len(ids),
            "runs": runs,
            "portfolio_customers": int(totals.get("customers") or 0),
            "portfolio_gross_exposure": float(totals.get("gross_exposure") or 0),
            "portfolio_reconciled_exposure": float(totals.get("reconciled_exposure") or 0),
            "legacy": {
                "round_trips": legacy_queries,
                "median_ms": round(legacy_ms, 2),
                "samples_ms": [round(value, 2) for value in legacy_samples],
                "ms_per_customer": round(legacy_ms / len(ids), 2),
            },
            "single_pass": {
                "round_trips": 1,
                "median_ms": round(one_pass_ms, 2),
                "samples_ms": [round(value, 2) for value in one_pass_samples],
                "ms_per_customer": round(one_pass_ms / len(ids), 2),
            },
            "portfolio_scan": {
                "median_ms": round(portfolio_ms, 2),
                "samples_ms": [round(value, 2) for value in portfolio_samples],
            },
            "speedup_x": round(speedup, 1),
            "latency_reduction_pct": round(reduction * 100, 1),
        }

        print(f"{'Path':<34}{'Round-trips':>13}{'Median ms':>12}{'ms/customer':>14}")
        print("-" * 73)
        print(
            f"{'Legacy per-customer composition':<34}{legacy_queries:>13,}"
            f"{legacy_ms:>12,.1f}{legacy_ms / len(ids):>14,.1f}"
        )
        print(
            f"{'Single Exasol credit-360 pass':<34}{1:>13,}"
            f"{one_pass_ms:>12,.1f}{one_pass_ms / len(ids):>14,.1f}"
        )
        print(f"{'Portfolio aggregate scan':<34}{1:>13,}{portfolio_ms:>12,.1f}{'n/a':>14}")
        print("-" * 73)
        print(f"Speedup: {speedup:,.1f}x fewer wall-clock ms ({reduction * 100:.1f}% lower latency)")
        print(
            f"Reconciled exposure: ${float(totals.get('reconciled_exposure') or 0):,.0f} "
            f"vs ${float(totals.get('gross_exposure') or 0):,.0f} reported"
        )

        output = Path(args.json) if args.json else (
            Path("benchmarks")
            / "results"
            / f"benchmark-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nWrote {output}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
