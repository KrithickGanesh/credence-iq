"""Database-backed analytics repository.

Every function in this module executes live SQL against Exasol.  No demo
workflow is served from static JSON.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal

from .config import settings
from .db import ExasolPool
from .schemas import SimulationRequest
from .scoring import (
    approval_threshold,
    coerce_weights,
    default_weights,
    refer_threshold,
    score_metrics,
)

logger = logging.getLogger("credenceiq.repository")

SYSTEM_LABELS = {
    "CORE_BANKING": "Core Banking",
    "CARD_ENGINE": "Card Engine",
    "MICROCREDIT": "Micro-credit",
}
SYSTEMS = ("CORE_BANKING", "CARD_ENGINE", "MICROCREDIT")

_WEIGHTS_LOCK = threading.Lock()
_WEIGHTS_CACHE: dict[str, dict[str, Any]] | None = None
_WEIGHTS_CACHED_AT = 0.0
_WEIGHTS_TTL_SECONDS = 300.0


def _iso(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _normalise_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: _iso(value) for key, value in row.items()}


def _normalise_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: _iso(value) for key, value in row.items()} for row in rows]


def format_inr(value: float) -> str:
    """Format an INR amount using Indian lakh/crore digit grouping."""

    digits = f"{abs(float(value)):,.0f}".replace(",", "")
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups + [tail])
    return f"{'-' if value < 0 else ''}₹{digits}"


def _f(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key)
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _i(row: dict[str, Any], key: str, default: int = 0) -> int:
    value = row.get(key)
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Factor weights
# ---------------------------------------------------------------------------
def get_weights(pool: ExasolPool, force: bool = False) -> dict[str, dict[str, Any]]:
    global _WEIGHTS_CACHE, _WEIGHTS_CACHED_AT
    now = time.time()
    if not force and _WEIGHTS_CACHE is not None and now - _WEIGHTS_CACHED_AT < _WEIGHTS_TTL_SECONDS:
        return _WEIGHTS_CACHE
    with _WEIGHTS_LOCK:
        if not force and _WEIGHTS_CACHE is not None and time.time() - _WEIGHTS_CACHED_AT < _WEIGHTS_TTL_SECONDS:
            return _WEIGHTS_CACHE
        result = pool.query(
            f"""
            SELECT factor_code, factor_name, category, weight, benchmark_threshold,
                   comparison_operator, severity, regulation_ref, adverse_action_reason,
                   plain_language_template, display_order, is_scored
            FROM {settings.exasol_schema}.RISK_FACTOR_WEIGHTS
            ORDER BY display_order
            """
        )
        weights = coerce_weights(result.rows)
        _WEIGHTS_CACHE = weights
        _WEIGHTS_CACHED_AT = time.time()
        return weights


def clear_weight_cache() -> None:
    global _WEIGHTS_CACHE, _WEIGHTS_CACHED_AT
    _WEIGHTS_CACHE = None
    _WEIGHTS_CACHED_AT = 0.0


# ---------------------------------------------------------------------------
# Application search
# ---------------------------------------------------------------------------
_SORT_COLUMNS = {
    "decision_date": "latest_decision_date",
    "application_date": "latest_application_date",
    "variance": "variance_ratio",
    "exposure": "gross_exposure",
    "score": "eligibility_score",
    "applicant": "last_name",
    "requested_amount": "latest_requested_amount",
}


def list_applications(
    pool: ExasolPool,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    decision: str | None = None,
    eligibility_decision: str | None = None,
    discrepancy_only: bool = False,
    sort: str = "decision_date",
    direction: Literal["asc", "desc"] = "desc",
) -> dict[str, Any]:
    filters: list[str] = ["1 = 1"]
    params: dict[str, Any] = {}
    if search and search.strip():
        params["pattern"] = f"%{search.strip()}%"
        filters.append(
            """
            (
                UPPER(first_name || ' ' || last_name) LIKE UPPER({pattern})
                OR UPPER(email) LIKE UPPER({pattern})
                OR CAST(customer_id AS VARCHAR(30)) LIKE {pattern}
                OR CAST(latest_application_id AS VARCHAR(30)) LIKE {pattern}
            )
            """
        )
    if decision:
        filters.append("latest_decision = {decision}")
        params["decision"] = decision.upper()
    if eligibility_decision:
        filters.append("eligibility_decision = {eligibility_decision}")
        params["eligibility_decision"] = eligibility_decision.upper()
    if discrepancy_only:
        filters.append("reconciliation_status <> 'RECONCILED'")

    where = " AND ".join(filters)
    sort_column = _SORT_COLUMNS.get(sort, "latest_decision_date")
    order_direction = "DESC" if direction.lower() == "desc" else "ASC"
    limit = max(1, min(page_size, 100))
    offset = max(0, (page - 1) * limit)

    count_result = pool.query(
        f"SELECT COUNT(*) AS total FROM {settings.exasol_schema}.V_RECONCILED_CREDIT_360 WHERE {where}",
        params,
    )
    total = _i(count_result.rows[0], "total") if count_result.rows else 0

    data_result = pool.query(
        f"""
        SELECT *
        FROM {settings.exasol_schema}.V_RECONCILED_CREDIT_360
        WHERE {where}
        ORDER BY {sort_column} {order_direction}, customer_id ASC
        LIMIT {limit} OFFSET {offset}
        """,
        params,
    )
    items = _normalise_rows(data_result.rows)
    for item in items:
        item["latest_denial_factors"] = item.get("latest_denial_factors") or ""
    total_pages = max(1, (total + limit - 1) // limit) if total else 0
    return {
        "items": items,
        "page": page,
        "page_size": limit,
        "total": total,
        "total_pages": total_pages,
        "query_ms": round(count_result.elapsed_ms + data_result.elapsed_ms, 2),
        "generated_at": datetime.now(timezone.utc),
    }


# ---------------------------------------------------------------------------
# Applicant 360 / reconciliation
# ---------------------------------------------------------------------------
def get_applicant_row(pool: ExasolPool, customer_id: int) -> tuple[dict[str, Any] | None, float]:
    result = pool.query(
        f"""
        SELECT * FROM {settings.exasol_schema}.V_RECONCILED_CREDIT_360
        WHERE customer_id = {customer_id}
        """
    )
    return _normalise_row(result.rows[0] if result.rows else None), result.elapsed_ms


def _metric_map(row: dict[str, Any]) -> dict[str, float]:
    return {
        "bureau_score": _f(row, "bureau_score", 680),
        "dti_ratio": _f(row, "latest_dti_ratio"),
        "delinquencies_12m": _f(row, "delinquencies_12m"),
        "hard_inquiries_6m": _f(row, "hard_inquiries_6m"),
        "utilization_ratio": _f(row, "portfolio_utilization_ratio"),
        "variance_ratio": _f(row, "variance_ratio"),
        "max_dpd": _f(row, "max_dpd"),
        "collections_count": _f(row, "collections_count"),
        "bankruptcies": _f(row, "bankruptcies"),
    }


def get_applicant_detail(
    pool: ExasolPool, customer_id: int
) -> tuple[dict[str, Any] | None, float]:
    started = time.perf_counter()
    row, row_ms = get_applicant_row(pool, customer_id)
    if row is None:
        return None, row_ms

    weights = get_weights(pool)
    exposure_result = pool.query(
        f"""
        SELECT exposure_id, source_system, facility_ref, account_ref, product_type,
               outstanding_balance, sanctioned_limit, days_past_due, account_status,
               last_reported_date
        FROM {settings.exasol_schema}.SYSTEM_EXPOSURES
        WHERE customer_id = {customer_id}
        ORDER BY facility_ref, source_system, outstanding_balance DESC
        """
    )
    bureau_result = pool.query(
        f"""
        SELECT bureau_name, report_date, bureau_score, delinquencies_12m,
               delinquencies_24m, hard_inquiries_6m, collections_count, bankruptcies,
               credit_history_months, utilization_ratio, total_accounts
        FROM {settings.exasol_schema}.CREDIT_BUREAU_RECORDS
        WHERE customer_id = {customer_id}
        ORDER BY report_date DESC
        """
    )

    facility_map: dict[str, dict[str, Any]] = {}
    system_counts: dict[str, int] = {system: 0 for system in SYSTEMS}
    system_exposure: dict[str, float] = {system: 0.0 for system in SYSTEMS}
    system_dpd: dict[str, int] = {system: 0 for system in SYSTEMS}

    for exposure in exposure_result.rows:
        exposure = _normalise_row(exposure) or {}
        source = str(exposure["source_system"])
        system_counts[source] = system_counts.get(source, 0) + 1
        system_exposure[source] = system_exposure.get(source, 0.0) + _f(exposure, "outstanding_balance")
        system_dpd[source] = max(system_dpd.get(source, 0), _i(exposure, "days_past_due"))
        facility = facility_map.setdefault(
            str(exposure["facility_ref"]),
            {
                "facility_ref": str(exposure["facility_ref"]),
                "product_type": str(exposure["product_type"]),
                "min_balance": _f(exposure, "outstanding_balance"),
                "max_balance": _f(exposure, "outstanding_balance"),
                "days_past_due": 0,
                "reports": [],
                "systems": set(),
            },
        )
        balance = _f(exposure, "outstanding_balance")
        facility["min_balance"] = min(facility["min_balance"], balance)
        facility["max_balance"] = max(facility["max_balance"], balance)
        facility["days_past_due"] = max(facility["days_past_due"], _i(exposure, "days_past_due"))
        facility["systems"].add(source)
        facility["reports"].append(
            {
                "exposure_id": str(exposure["exposure_id"]),
                "source_system": source,
                "system_label": SYSTEM_LABELS.get(source, source),
                "outstanding_balance": balance,
                "sanctioned_limit": _f(exposure, "sanctioned_limit"),
                "days_past_due": _i(exposure, "days_past_due"),
                "account_status": str(exposure["account_status"]),
                "last_reported_date": exposure["last_reported_date"],
            }
        )

    facilities: list[dict[str, Any]] = []
    for facility in facility_map.values():
        spread = facility["max_balance"] - facility["min_balance"]
        facilities.append(
            {
                "facility_ref": facility["facility_ref"],
                "product_type": facility["product_type"],
                "systems_reporting": len(facility["systems"]),
                "min_balance": round(facility["min_balance"], 2),
                "max_balance": round(facility["max_balance"], 2),
                "balance_spread": round(spread, 2),
                "days_past_due": facility["days_past_due"],
                "status": "CONFLICT" if len(facility["systems"]) > 1 else "MATCHED",
                "reports": sorted(facility["reports"], key=lambda item: item["source_system"]),
            }
        )
    facilities.sort(key=lambda item: (-item["balance_spread"], item["facility_ref"]))

    reported_total = _f(row, "gross_exposure")
    systems = [
        {
            "system": system,
            "label": SYSTEM_LABELS[system],
            "exposure": round(system_exposure.get(system, 0.0), 2),
            "accounts": system_counts.get(system, 0),
            "share": round(system_exposure.get(system, 0.0) / reported_total, 4)
            if reported_total > 0
            else 0.0,
            "max_dpd": system_dpd.get(system, 0),
        }
        for system in SYSTEMS
    ]

    score_result = score_metrics(_metric_map(row), weights)
    factors = []
    for contribution in score_result.contributions:
        item = contribution.as_dict()
        item["is_negative"] = contribution.contribution < 0
        factors.append(item)

    total_ms = round((time.perf_counter() - started) * 1000, 2)

    return (
        {
            "applicant": {
                "customer_id": _i(row, "customer_id"),
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "email": row["email"],
                "phone": row["phone"],
                "city": row["city"],
                "state": row["state"],
                "postal_code": row["postal_code"],
                "segment": row["segment"],
                "annual_income": _f(row, "annual_income"),
                "employment_status": row["employment_status"],
                "kyc_status": row["kyc_status"],
                "customer_since": row["customer_since"],
            },
            "application": {
                "application_id": _i(row, "latest_application_id"),
                "application_date": row["latest_application_date"],
                "decision_date": row["latest_decision_date"],
                "decision": row["latest_decision"],
                "requested_amount": _f(row, "latest_requested_amount"),
                "product_type": row["latest_product_type"],
                "tenure_months": _i(row, "latest_tenure_months"),
                "purpose": row["latest_purpose"],
                "dti_ratio": _f(row, "latest_dti_ratio"),
                "income_at_application": _f(row, "latest_income"),
                "proposed_emi": _f(row, "latest_proposed_emi"),
                "risk_grade": row["latest_risk_grade"],
                "model_score": _f(row, "latest_model_score"),
                "denial_factors": row["latest_denial_factors"] or "",
                "channel": row["latest_channel"],
                "branch_code": row["latest_branch_code"],
            },
            "eligibility": {
                "score": _f(row, "eligibility_score"),
                "decision": row["eligibility_decision"],
                "grade": row["recomputed_grade"],
                "score_gap_to_approval": _f(row, "score_gap_to_approval"),
                "approve_threshold": approval_threshold(weights),
                "refer_threshold": refer_threshold(weights),
                "factors": factors,
            },
            "reconciliation": {
                "status": row["reconciliation_status"],
                "reported_total": _f(row, "gross_exposure"),
                "reconciled_total": _f(row, "reconciled_exposure"),
                "variance": _f(row, "debt_variance"),
                "variance_ratio": _f(row, "variance_ratio"),
                "conflicted_facilities": _i(row, "conflicted_facilities"),
                "systems_reporting": _i(row, "systems_reporting"),
                "exposure_accounts": _i(row, "exposure_accounts"),
                "reported_balance_spread": _f(row, "reported_balance_spread"),
                "portfolio_utilization_ratio": _f(row, "portfolio_utilization_ratio"),
                "utilization_percentile": _f(row, "utilization_percentile"),
                "exposure_percentile": _f(row, "exposure_percentile"),
                "systems": systems,
                "facilities": facilities,
            },
            "bureau_records": _normalise_rows(bureau_result.rows),
            "query_ms": total_ms,
            "generated_at": datetime.now(timezone.utc),
        },
        total_ms,
    )


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
def simulate(pool: ExasolPool, customer_id: int, request: SimulationRequest) -> dict[str, Any] | None:
    started = time.perf_counter()
    result = pool.query(
        f"""
        SELECT
            customer_id, first_name, last_name, latest_application_id, latest_decision,
            latest_product_type, latest_requested_amount, latest_income, latest_dti_ratio,
            bureau_score, delinquencies_12m, hard_inquiries_6m,
            portfolio_utilization_ratio, variance_ratio, max_dpd, collections_count,
            bankruptcies, card_exposure, gross_exposure, reconciled_exposure,
            total_sanctioned, debt_variance,
            GREATEST(0.0, card_exposure - {{paydown}}) AS sim_card_exposure,
            GREATEST(0.0, gross_exposure - LEAST({{paydown}}, card_exposure)) AS sim_gross_exposure,
            CASE WHEN {{resolve}} = 1 THEN 0.0 ELSE variance_ratio END AS sim_variance_ratio,
            CASE WHEN {{income_boost}} > 0
                 THEN latest_dti_ratio * latest_income / (latest_income + {{income_boost}})
                 ELSE latest_dti_ratio END AS sim_dti_ratio,
            hard_inquiries_6m + {{new_inquiries}} AS sim_hard_inquiries_6m,
            CASE WHEN total_sanctioned > 0
                 THEN GREATEST(0.0, gross_exposure - LEAST({{paydown}}, card_exposure)) / total_sanctioned
                 ELSE 0.0 END AS sim_utilization_ratio
        FROM {settings.exasol_schema}.V_RECONCILED_CREDIT_360
        WHERE customer_id = {customer_id}
        """,
        {
            "paydown": float(request.revolving_paydown),
            "resolve": 1 if request.resolve_exposure_mismatch else 0,
            "income_boost": float(request.income_increase_annual),
            "new_inquiries": int(request.additional_hard_inquiries),
        },
    )
    if not result.rows:
        return None
    row = _normalise_row(result.rows[0]) or {}
    weights = get_weights(pool)

    card_exposure = _f(row, "card_exposure")
    gross_exposure = _f(row, "gross_exposure")
    total_sanctioned = _f(row, "total_sanctioned")
    current_dti = _f(row, "latest_dti_ratio")
    latest_income = _f(row, "latest_income")
    variance_ratio = _f(row, "variance_ratio")
    current_utilization = _f(row, "portfolio_utilization_ratio")
    current_inquiries = _i(row, "hard_inquiries_6m")
    base_metrics = _metric_map(row)

    def project(
        paydown: float = 0.0,
        resolve: bool = False,
        income_boost: float = 0.0,
        new_inquiries: int = 0,
    ) -> dict[str, Any]:
        paydown = max(0.0, min(float(paydown), card_exposure))
        gross_after = max(0.0, gross_exposure - min(paydown, card_exposure))
        utilization_after = gross_after / total_sanctioned if total_sanctioned > 0 else 0.0
        dti_after = (
            current_dti * latest_income / (latest_income + income_boost)
            if income_boost > 0 and latest_income > 0
            else current_dti
        )
        metrics = dict(base_metrics)
        metrics["dti_ratio"] = dti_after
        metrics["utilization_ratio"] = utilization_after
        metrics["variance_ratio"] = 0.0 if resolve else variance_ratio
        metrics["hard_inquiries_6m"] = current_inquiries + new_inquiries
        score = score_metrics(metrics, weights)
        return {
            "score": score.score,
            "decision": score.decision,
            "grade": score.grade,
            "score_gap_to_approval": round(max(0.0, approval_threshold(weights) - score.score), 1),
            "dti_ratio": round(dti_after, 4),
            "utilization_ratio": round(utilization_after, 4),
            "variance_ratio": round(0.0 if resolve else variance_ratio, 4),
            "gross_exposure": round(gross_after, 2),
            "card_exposure": round(max(0.0, card_exposure - paydown), 2),
            "hard_inquiries_6m": current_inquiries + new_inquiries,
        }

    current = project()
    simulated = project(
        paydown=request.revolving_paydown,
        resolve=request.resolve_exposure_mismatch,
        income_boost=request.income_increase_annual,
        new_inquiries=request.additional_hard_inquiries,
    )

    paydown_only = project(paydown=request.revolving_paydown)
    mismatch_only = project(resolve=request.resolve_exposure_mismatch)
    income_only = project(income_boost=request.income_increase_annual)
    inquiries_only = project(new_inquiries=request.additional_hard_inquiries)

    actions = [
        {
            "code": "REVOLVING_PAYDOWN",
            "label": "Pay down revolving balances",
            "description": (
                f"Apply {format_inr(request.revolving_paydown)} to the card engine and recompute "
                "gross exposure and utilization."
            ),
            "score_impact": round(paydown_only["score"] - current["score"], 1),
            "projected_score": paydown_only["score"],
            "applied": request.revolving_paydown > 0,
        },
        {
            "code": "RESOLVE_MISMATCH",
            "label": "Resolve cross-system mismatch",
            "description": (
                "Align duplicate facility balances across core, card, and micro-credit ledgers."
            ),
            "score_impact": round(mismatch_only["score"] - current["score"], 1),
            "projected_score": mismatch_only["score"],
            "applied": request.resolve_exposure_mismatch,
        },
        {
            "code": "VERIFIED_INCOME",
            "label": "Document additional income",
            "description": (
                f"Verify {format_inr(request.income_increase_annual)} of additional annual income, "
                "which reduces the debt-to-income ratio."
            ),
            "score_impact": round(income_only["score"] - current["score"], 1),
            "projected_score": income_only["score"],
            "applied": request.income_increase_annual > 0,
        },
        {
            "code": "NEW_INQUIRIES",
            "label": "New credit applications",
            "description": "Additional hard inquiries increase credit-seeking risk.",
            "score_impact": round(inquiries_only["score"] - current["score"], 1),
            "projected_score": inquiries_only["score"],
            "applied": request.additional_hard_inquiries > 0,
        },
    ]

    target = approval_threshold(weights)
    gap = round(max(0.0, target - simulated["score"]), 1)
    reachable = simulated["score"] >= target
    additional_paydown: float | None = 0.0 if reachable else None
    message = "The current scenario already crosses the approval threshold."
    if not reachable and card_exposure > 0:
        def score_at(paydown: float) -> float:
            return project(
                paydown=paydown,
                resolve=request.resolve_exposure_mismatch,
                income_boost=request.income_increase_annual,
                new_inquiries=request.additional_hard_inquiries,
            )["score"]

        if score_at(card_exposure) >= target:
            low, high = request.revolving_paydown, card_exposure
            for _ in range(45):
                mid = (low + high) / 2
                if score_at(mid) >= target:
                    high = mid
                else:
                    low = mid
            additional = max(0.0, round(high - request.revolving_paydown, 2))
            additional_paydown = additional
            reachable = True
            message = (
                f"An additional {format_inr(additional)} revolving paydown beyond the current scenario "
                f"would move the file above {target:.0f}."
            )
        else:
            message = (
                f"The score remains below {target:.0f} even after paying off all revolving "
                "balances. Reducing the requested amount or documenting additional income is "
                "required for approval."
            )

    total_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "customer_id": _i(row, "customer_id"),
        "applicant_name": f"{row['first_name']} {row['last_name']}",
        "application_id": _i(row, "latest_application_id"),
        "current": current,
        "simulated": simulated,
        "score_delta": round(simulated["score"] - current["score"], 1),
        "decision_changed": simulated["decision"] != current["decision"],
        "actions": actions,
        "path_to_approval": {
            "target_score": target,
            "gap": gap,
            "reachable": reachable,
            "additional_paydown": additional_paydown,
            "message": message,
        },
        "assumptions": [
            "Ledger balances update immediately and are reflected in the next credit-information cycle.",
            "Additional income must be documented and independently verified.",
            "Sanctioned limits and all non-adjusted factors remain unchanged.",
            "This is a pre-decision estimate, not a credit offer or approval commitment.",
        ],
        "query_ms": total_ms,
        "generated_at": datetime.now(timezone.utc),
    }


# ---------------------------------------------------------------------------
# Adverse action persistence
# ---------------------------------------------------------------------------
def persist_report(
    pool: ExasolPool,
    *,
    report_id: str,
    customer_id: int,
    application_id: int,
    generated_at: datetime,
    provider: str,
    model: str,
    generation_mode: str,
    payload: dict[str, Any],
) -> bool:
    try:
        pool.execute(
            f"""
            INSERT INTO {settings.exasol_schema}.ADVERSE_ACTION_REPORTS
                (report_id, customer_id, application_id, generated_at, provider, model,
                 generation_mode, letter_json)
            VALUES
                ({{report_id}}, {{customer_id}}, {{application_id}}, {{generated_at}},
                 {{provider}}, {{model}}, {{generation_mode}}, {{letter_json}})
            """,
            {
                "report_id": report_id,
                "customer_id": customer_id,
                "application_id": application_id,
                "generated_at": generated_at.replace(tzinfo=None),
                "provider": provider[:40],
                "model": model[:120],
                "generation_mode": generation_mode,
                "letter_json": json.dumps(payload, default=str)[:1_999_000],
            },
        )
        return True
    except Exception as exc:  # persistence must not destroy a generated letter
        logger.warning("could not persist adverse action report: %s", exc)
        return False


def new_report_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Portfolio overview
# ---------------------------------------------------------------------------
def _month_range(count: int = 12) -> list[str]:
    today = date.today().replace(day=1)
    months: list[str] = []
    for offset in range(count - 1, -1, -1):
        year = today.year
        month = today.month - offset
        while month <= 0:
            month += 12
            year -= 1
        months.append(f"{year:04d}-{month:02d}")
    return months


def portfolio_udf_check(pool: ExasolPool) -> dict[str, Any]:
    """Score the whole book with the Exasol Python UDF and compare to the view."""

    schema = settings.exasol_schema
    result = pool.query(
        f"""
        SELECT
            COUNT(*) AS customers_scored,
            SUM(CASE WHEN ABS(u.score - v.eligibility_score) <= 0.05 THEN 1 ELSE 0 END)
                AS matching_scores,
            ROUND(AVG(ABS(u.score - v.eligibility_score)), 6) AS mean_abs_difference,
            ROUND(MAX(ABS(u.score - v.eligibility_score)), 2) AS max_abs_difference,
            SUM(CASE WHEN u.decision = v.eligibility_decision THEN 1 ELSE 0 END)
                AS decision_matches,
            SUM(CASE WHEN u.decision = 'APPROVED' THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN u.decision = 'REFERRED' THEN 1 ELSE 0 END) AS referred,
            SUM(CASE WHEN u.decision = 'DECLINED' THEN 1 ELSE 0 END) AS declined
        FROM (
            SELECT {schema}.SCORE_PORTFOLIO(
                v.customer_id,
                v.bureau_score,
                v.latest_dti_ratio,
                v.delinquencies_12m,
                v.hard_inquiries_6m,
                v.portfolio_utilization_ratio,
                v.variance_ratio,
                v.max_dpd,
                v.collections_count,
                v.bankruptcies
            )
            FROM {schema}.V_RECONCILED_CREDIT_360 v
        ) u
        JOIN {schema}.V_RECONCILED_CREDIT_360 v ON v.customer_id = u.customer_id_out
        """
    )
    row = result.rows[0] if result.rows else {}
    scored = _i(row, "customers_scored")
    matches = _i(row, "matching_scores")
    return {
        "script": f"{schema}.SCORE_PORTFOLIO",
        "engine": "Exasol PYTHON3 SET UDF",
        "customers_scored": scored,
        "matching_scores": matches,
        "agreement_rate": round(matches / scored, 4) if scored else 0.0,
        "mean_abs_difference": _f(row, "mean_abs_difference"),
        "max_abs_difference": _f(row, "max_abs_difference"),
        "decision_matches": _i(row, "decision_matches"),
        "decision_mix": {
            "APPROVED": _i(row, "approved"),
            "REFERRED": _i(row, "referred"),
            "DECLINED": _i(row, "declined"),
        },
        "elapsed_ms": round(result.elapsed_ms, 2),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def get_overview(pool: ExasolPool) -> dict[str, Any]:
    schema = settings.exasol_schema
    total_ms = 0.0

    apps = pool.query(
        f"""
        SELECT
            COUNT(*) AS total_applications,
            SUM(CASE WHEN decision = 'APPROVED' THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN decision = 'DECLINED' THEN 1 ELSE 0 END) AS declined,
            SUM(CASE WHEN decision = 'REFERRED' THEN 1 ELSE 0 END) AS referred,
            ROUND(AVG(dti_ratio), 4) AS average_dti
        FROM {schema}.LOAN_APPLICATIONS
        """
    )
    total_ms += apps.elapsed_ms
    app_row = apps.rows[0] if apps.rows else {}

    book = pool.query(
        f"""
        SELECT
            COUNT(*) AS customers,
            SUM(CASE WHEN reconciliation_status = 'MISMATCH' THEN 1 ELSE 0 END) AS mismatches,
            SUM(CASE WHEN reconciliation_status = 'MINOR_VARIANCE' THEN 1 ELSE 0 END) AS minor_variances,
            SUM(CASE WHEN reconciliation_status = 'RECONCILED' THEN 1 ELSE 0 END) AS reconciled,
            SUM(gross_exposure) AS reported_exposure,
            SUM(reconciled_exposure) AS reconciled_exposure,
            SUM(debt_variance) AS double_counted_exposure,
            ROUND(AVG(bureau_score), 1) AS average_bureau_score,
            ROUND(AVG(eligibility_score), 1) AS average_eligibility_score
        FROM {schema}.V_RECONCILED_CREDIT_360
        """
    )
    total_ms += book.elapsed_ms
    book_row = book.rows[0] if book.rows else {}

    systems_result = pool.query(
        f"""
        SELECT source_system,
               SUM(outstanding_balance) AS exposure,
               COUNT(*) AS accounts
        FROM {schema}.SYSTEM_EXPOSURES
        GROUP BY source_system
        """
    )
    total_ms += systems_result.elapsed_ms
    system_totals = {str(row["source_system"]): row for row in systems_result.rows}
    reported_total = sum(_f(row, "exposure") for row in systems_result.rows)

    velocity_result = pool.query(
        f"""
        SELECT TO_CHAR(decision_date, 'YYYY-MM') AS month_key,
               COUNT(*) AS applications,
               SUM(CASE WHEN decision = 'DECLINED' THEN 1 ELSE 0 END) AS declines
        FROM {schema}.LOAN_APPLICATIONS
        WHERE decision_date >= ADD_MONTHS(CURRENT_DATE, -11)
        GROUP BY TO_CHAR(decision_date, 'YYYY-MM')
        ORDER BY 1
        """
    )
    total_ms += velocity_result.elapsed_ms
    velocity_map = {str(row["month_key"]): row for row in velocity_result.rows}
    velocity = []
    for month in _month_range(12):
        row = velocity_map.get(month, {})
        applications_count = _i(row, "applications")
        declines = _i(row, "declines")
        velocity.append(
            {
                "month": month,
                "applications": applications_count,
                "declines": declines,
                "decline_rate": round(declines / applications_count, 4) if applications_count else 0.0,
            }
        )

    drivers_result = pool.query(
        f"""
        SELECT f.factor_code, w.factor_name,
               COUNT(*) AS denial_count,
               ROUND(AVG(f.contribution), 2) AS avg_contribution,
               MAX(w.regulation_ref) AS regulation_ref
        FROM {schema}.APPLICATION_RISK_FACTORS f
        JOIN {schema}.LOAN_APPLICATIONS a ON a.application_id = f.application_id
        JOIN {schema}.RISK_FACTOR_WEIGHTS w ON w.factor_code = f.factor_code
        WHERE a.decision = 'DECLINED'
        GROUP BY f.factor_code, w.factor_name
        ORDER BY denial_count DESC
        LIMIT 8
        """
    )
    total_ms += drivers_result.elapsed_ms

    mix_result = pool.query(
        f"""
        SELECT reconciliation_status AS status, COUNT(*) AS count_
        FROM {schema}.V_RECONCILED_CREDIT_360
        GROUP BY reconciliation_status
        ORDER BY reconciliation_status
        """
    )
    total_ms += mix_result.elapsed_ms
    mix_map = {str(row["status"]): _i(row, "count_") for row in mix_result.rows}
    customer_count = _i(book_row, "customers")

    discrepancies = pool.query(
        f"""
        SELECT * FROM {schema}.V_RECONCILED_CREDIT_360
        WHERE reconciliation_status = 'MISMATCH'
        ORDER BY debt_variance DESC
        LIMIT 8
        """
    )
    total_ms += discrepancies.elapsed_ms

    total_applications = _i(app_row, "total_applications")
    approved = _i(app_row, "approved")
    declined = _i(app_row, "declined")
    referred = _i(app_row, "referred")
    mismatches = _i(book_row, "mismatches")
    reported_exposure = _f(book_row, "reported_exposure")
    reconciled_exposure = _f(book_row, "reconciled_exposure")

    return {
        "portfolio": {
            "total_applications": total_applications,
            "approved": approved,
            "declined": declined,
            "referred": referred,
            "decline_rate": round(declined / total_applications, 4) if total_applications else 0.0,
            "approval_rate": round(approved / total_applications, 4) if total_applications else 0.0,
            "customers": customer_count,
            "mismatches": mismatches,
            "minor_variances": _i(book_row, "minor_variances"),
            "reconciled": _i(book_row, "reconciled"),
            "mismatch_rate": round(mismatches / customer_count, 4) if customer_count else 0.0,
            "reported_exposure": reported_exposure,
            "reconciled_exposure": reconciled_exposure,
            "double_counted_exposure": round(reported_exposure - reconciled_exposure, 2),
            "average_dti": _f(app_row, "average_dti"),
            "average_bureau_score": _f(book_row, "average_bureau_score"),
            "average_eligibility_score": _f(book_row, "average_eligibility_score"),
        },
        "exposure_by_system": [
            {
                "system": system,
                "label": SYSTEM_LABELS[system],
                "exposure": _f(system_totals.get(system, {}), "exposure"),
                "accounts": _i(system_totals.get(system, {}), "accounts"),
                "share": round(_f(system_totals.get(system, {}), "exposure") / reported_total, 4)
                if reported_total
                else 0.0,
            }
            for system in SYSTEMS
        ],
        "decision_mix": [
            {
                "decision": decision,
                "count": count,
                "share": round(count / total_applications, 4) if total_applications else 0.0,
            }
            for decision, count in (
                ("APPROVED", approved),
                ("REFERRED", referred),
                ("DECLINED", declined),
            )
        ],
        "rejection_velocity": velocity,
        "denial_drivers": [
            {
                "factor_code": str(row["factor_code"]),
                "factor_name": str(row["factor_name"]),
                "count": _i(row, "denial_count"),
                "avg_contribution": _f(row, "avg_contribution"),
                "regulation_ref": str(row["regulation_ref"]),
            }
            for row in drivers_result.rows
        ],
        "reconciliation_mix": [
            {
                "status": status,
                "count": mix_map.get(status, 0),
                "share": round(mix_map.get(status, 0) / customer_count, 4)
                if customer_count
                else 0.0,
            }
            for status in ("RECONCILED", "MINOR_VARIANCE", "MISMATCH")
        ],
        "top_discrepancies": _normalise_rows(discrepancies.rows),
        "query_ms": round(total_ms, 2),
        "generated_at": datetime.now(timezone.utc),
    }


def list_factors(pool: ExasolPool) -> dict[str, Any]:
    weights = get_weights(pool, force=True)
    factors = [
        {
            "factor_code": item["factor_code"],
            "factor_name": item["factor_name"],
            "category": item["category"],
            "weight": float(item["weight"]),
            "benchmark_threshold": float(item["benchmark_threshold"]),
            "comparison_operator": item["comparison_operator"],
            "severity": item["severity"],
            "regulation_ref": item["regulation_ref"],
            "adverse_action_reason": item["adverse_action_reason"],
            "plain_language_template": item["plain_language_template"],
            "display_order": int(item["display_order"]),
            "is_scored": int(item["is_scored"]),
        }
        for item in sorted(weights.values(), key=lambda row: int(row["display_order"]))
    ]
    return {
        "factors": factors,
        "approve_threshold": approval_threshold(weights),
        "refer_threshold": refer_threshold(weights),
        "query_ms": 0.0,
    }
