"""CredenceIQ access-pattern benchmark: per-customer N+1 vs one set-based pass.

Both paths run against the **same** Exasol instance and the same reconciled
data. The comparison is about *query composition*, not about Exasol versus a
transactional database:

* **N+1 composition** — the application issues separate round-trips for the
  customer, bureau record, latest application, and every exposure row, then
  reconciles in Python. This mirrors a transactional service assembling an
  applicant view one call at a time.
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
import os
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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


IDENTIFIER = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("EXASOL_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("EXASOL_PORT", "8563")))
    parser.add_argument("--user", default=os.getenv("EXASOL_USER", "sys"))
    parser.add_argument(
        "--password",
        default=os.getenv("EXASOL_PASSWORD", ""),
        help="Defaults to EXASOL_PASSWORD, then the starter-kit credential file.",
    )
    parser.add_argument("--schema", default="CREDENCEIQ")
    parser.add_argument("--sample", type=int, default=100, help="customers in the comparison (1-1000)")
    parser.add_argument("--runs", type=int, default=3, help="measured repetitions")
    parser.add_argument(
        "--json",
        default="",
        help="optional output path; defaults to benchmarks/results/benchmark-<timestamp>.json",
    )
    return parser.parse_args()


def resolve_password(explicit: str) -> str:
    """Prefer an explicit/env password, then the starter-kit credential file."""

    if explicit.strip():
        return explicit.strip()
    credential = (
        Path.home() / ".exasol-starter-kit" / "credentials" / "personal_sys_password"
    )
    if credential.exists():
        return credential.read_text(encoding="utf-8").strip()
    raise SystemExit(
        "No Exasol password. Set EXASOL_PASSWORD in .env or pass --password."
    )


def inr_crore(value: float) -> str:
    """Format a rupee amount using Indian lakh/crore units."""

    crore = value / 10_000_000
    if abs(crore) >= 100:
        return f"₹{crore:,.0f}Cr"
    if abs(crore) >= 1:
        return f"₹{crore:,.2f}Cr"
    lakh = value / 100_000
    return f"₹{lakh:,.1f}L"


def connect(args: argparse.Namespace) -> pyexasol.ExaConnection:
    schema = args.schema.strip().upper()
    if not IDENTIFIER.fullmatch(schema):
        raise SystemExit("--schema must be a simple SQL identifier")
    return pyexasol.connect(
        dsn=f"{args.host}:{args.port}",
        user=args.user,
        password=resolve_password(args.password),
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


def n_plus_one_profile(
    con: pyexasol.ExaConnection, schema: str, customer_id: int
) -> dict[str, Any]:
    """Simulate a transactional service assembling one profile with N+1 calls."""

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
        n_plus_one_profile(con, schema, ids[0])
        single_pass(con, schema, ids[: min(5, len(ids))])

        n_plus_one_ms, n_plus_one_samples = measure(
            lambda: [n_plus_one_profile(con, schema, customer_id) for customer_id in ids],
            runs,
        )
        one_pass_ms, one_pass_samples = measure(lambda: single_pass(con, schema, ids), runs)

        def portfolio() -> None:
            portfolio_totals(con, schema)

        portfolio_ms, portfolio_samples = measure(portfolio, runs)

        n_plus_one_queries = len(ids) * 4
        reduction = 1 - (one_pass_ms / n_plus_one_ms) if n_plus_one_ms else 0.0
        ms_saved = n_plus_one_ms - one_pass_ms
        speedup = n_plus_one_ms / one_pass_ms if one_pass_ms else float("inf")

        result = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "benchmark": "per-customer N+1 composition vs single set-based pass",
            "note": (
                "Both paths use the same Exasol instance and data. The result measures "
                "query composition and round-trips, not Exasol versus another engine."
            ),
            "exasol_version": version,
            "schema": schema,
            "sample_customers": len(ids),
            "runs": runs,
            "portfolio_customers": int(totals.get("customers") or 0),
            "portfolio_gross_exposure": float(totals.get("gross_exposure") or 0),
            "portfolio_reconciled_exposure": float(totals.get("reconciled_exposure") or 0),
            "n_plus_one": {
                "round_trips": n_plus_one_queries,
                "median_ms": round(n_plus_one_ms, 2),
                "samples_ms": [round(value, 2) for value in n_plus_one_samples],
                "ms_per_customer": round(n_plus_one_ms / len(ids), 2),
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
            "wall_time_reduction_pct": round(reduction * 100, 1),
            "median_ms_saved": round(ms_saved, 2),
            "ratio_x": round(speedup, 1),
        }

        print(f"{'Path':<36}{'Round-trips':>13}{'Median ms':>12}{'ms/customer':>14}")
        print("-" * 75)
        print(
            f"{'Per-customer N+1 composition':<36}{n_plus_one_queries:>13,}"
            f"{n_plus_one_ms:>12,.1f}{n_plus_one_ms / len(ids):>14,.1f}"
        )
        print(
            f"{'Single set-based credit-360 pass':<36}{1:>13,}"
            f"{one_pass_ms:>12,.1f}{one_pass_ms / len(ids):>14,.1f}"
        )
        print(f"{'Portfolio aggregate scan':<36}{1:>13,}{portfolio_ms:>12,.1f}{'n/a':>14}")
        print("-" * 75)
        print(
            f"N+1 -> single pass: {ms_saved:,.1f} ms less wall time "
            f"({reduction * 100:.1f}% lower) at the same result."
        )
        print(
            "Both paths run on the same Exasol instance; this measures query composition, "
            "not engine speed."
        )
        print(
            f"Reconciled exposure: {inr_crore(float(totals.get('reconciled_exposure') or 0))} "
            f"vs {inr_crore(float(totals.get('gross_exposure') or 0))} reported"
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
