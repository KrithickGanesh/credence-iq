"""Transparent, deterministic eligibility scoring shared by the API and seed job.

The scoring model is intentionally simple: every contribution is a function of a
single, auditable underwriting factor.  The same weights are persisted in
Exasol's ``RISK_FACTOR_WEIGHTS`` table and the analytical view is generated from
them, so the API, the database view, and the synthetic data generator cannot
silently drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

MIN_SCORE = 300.0
MAX_SCORE = 900.0

FACTOR_DEFINITIONS: list[dict[str, Any]] = [
    {
        "factor_code": "SCORE_BASE",
        "factor_name": "Model baseline",
        "category": "MODEL",
        "weight": 790.0,
        "benchmark_threshold": 0.0,
        "comparison_operator": "NONE",
        "severity": "INFO",
        "regulation_ref": "Model documentation",
        "adverse_action_reason": "Baseline score before applicant-specific factors.",
        "plain_language_template": "The score starts from a neutral model baseline.",
        "display_order": 0,
        "is_scored": 0,
    },
    {
        "factor_code": "DECISION_APPROVE_THRESHOLD",
        "factor_name": "Approval threshold",
        "category": "MODEL",
        "weight": 750.0,
        "benchmark_threshold": 0.0,
        "comparison_operator": "NONE",
        "severity": "INFO",
        "regulation_ref": "Model documentation",
        "adverse_action_reason": "Scores at or above this threshold are approved.",
        "plain_language_template": "Applications at or above this score are approved.",
        "display_order": 1,
        "is_scored": 0,
    },
    {
        "factor_code": "DECISION_REFER_THRESHOLD",
        "factor_name": "Manual review threshold",
        "category": "MODEL",
        "weight": 680.0,
        "benchmark_threshold": 0.0,
        "comparison_operator": "NONE",
        "severity": "INFO",
        "regulation_ref": "Model documentation",
        "adverse_action_reason": "Scores between this and the approval threshold are referred.",
        "plain_language_template": "Scores between this and the approval threshold receive manual review.",
        "display_order": 2,
        "is_scored": 0,
    },
    {
        "factor_code": "BUREAU_SCORE",
        "factor_name": "Credit bureau score (CIBIL-style)",
        "category": "CREDIT_HISTORY",
        "weight": 0.30,
        "benchmark_threshold": 680.0,
        "comparison_operator": "GTE",
        "severity": "HIGH",
        "regulation_ref": (
            "RBI (Credit Information Reporting) Directions, 2025; "
            "Credit Information Companies (Regulation) Act, 2005"
        ),
        "adverse_action_reason": "Credit bureau score materially below the portfolio benchmark.",
        "plain_language_template": (
            "Your CIBIL-style credit bureau score of {observed} is below our benchmark of "
            "{benchmark}. A lower score can reflect late payments, high balances, "
            "or limited credit history."
        ),
        "display_order": 10,
        "is_scored": 1,
    },
    {
        "factor_code": "DTI_RATIO",
        "factor_name": "Debt-to-income ratio",
        "category": "CAPACITY",
        "weight": -50.0,
        "benchmark_threshold": 0.40,
        "comparison_operator": "LTE",
        "severity": "HIGH",
        "regulation_ref": "RBI Fair Practices Code for Lenders; ability-to-repay policy",
        "adverse_action_reason": (
            "Proposed debt service would consume more than the policy guideline "
            "for monthly income."
        ),
        "plain_language_template": (
            "Your existing monthly debt payments, plus the proposed payment, would "
            "equal {observed_pct} of your monthly income. Our guideline is "
            "{benchmark_pct} or less."
        ),
        "display_order": 20,
        "is_scored": 1,
    },
    {
        "factor_code": "DELINQUENCY_12M",
        "factor_name": "Delinquencies in 12 months",
        "category": "PAYMENT_HISTORY",
        "weight": -35.0,
        "benchmark_threshold": 0.0,
        "comparison_operator": "LTE",
        "severity": "HIGH",
        "regulation_ref": "RBI Fair Practices Code for Lenders",
        "adverse_action_reason": "One or more delinquent accounts reported in the past 12 months.",
        "plain_language_template": (
            "Our review found {observed} delinquent account(s) reported in the last "
            "12 months. The guideline is {benchmark}."
        ),
        "display_order": 30,
        "is_scored": 1,
    },
    {
        "factor_code": "HARD_INQUIRY_6M",
        "factor_name": "Hard credit inquiries",
        "category": "CREDIT_SEEKING",
        "weight": -10.0,
        "benchmark_threshold": 2.0,
        "comparison_operator": "LTE",
        "severity": "MEDIUM",
        "regulation_ref": "RBI (Credit Information Reporting) Directions, 2025",
        "adverse_action_reason": "Frequent recent applications for new credit.",
        "plain_language_template": (
            "You have {observed} hard credit inquiries in the last 6 months. Our "
            "guideline is {benchmark} or fewer."
        ),
        "display_order": 40,
        "is_scored": 1,
    },
    {
        "factor_code": "UTILIZATION",
        "factor_name": "Revolving utilization",
        "category": "CAPACITY",
        "weight": -30.0,
        "benchmark_threshold": 0.30,
        "comparison_operator": "LTE",
        "severity": "MEDIUM",
        "regulation_ref": "RBI Fair Practices Code for Lenders",
        "adverse_action_reason": "Revolving credit balances are high relative to available limits.",
        "plain_language_template": (
            "You are using {observed_pct} of your available revolving credit. Our "
            "guideline is {benchmark_pct} or less."
        ),
        "display_order": 50,
        "is_scored": 1,
    },
    {
        "factor_code": "EXPOSURE_MISMATCH",
        "factor_name": "Cross-system exposure mismatch",
        "category": "DATA_QUALITY",
        "weight": -40.0,
        "benchmark_threshold": 0.02,
        "comparison_operator": "LTE",
        "severity": "HIGH",
        "regulation_ref": (
            "RBI (Credit Information Reporting) Directions, 2025; "
            "Digital Personal Data Protection Act, 2023"
        ),
        "adverse_action_reason": (
            "Internal core, card, and micro-credit systems report conflicting balances "
            "for the same facility."
        ),
        "plain_language_template": (
            "Our records show a {observed_pct} difference between systems for the same "
            "account. We are required to resolve this before relying on the balance. "
            "The acceptable variance is {benchmark_pct} or less."
        ),
        "display_order": 60,
        "is_scored": 1,
    },
    {
        "factor_code": "DAYS_PAST_DUE",
        "factor_name": "Maximum days past due",
        "category": "PAYMENT_HISTORY",
        "weight": -0.60,
        "benchmark_threshold": 0.0,
        "comparison_operator": "LTE",
        "severity": "HIGH",
        "regulation_ref": "RBI Fair Practices Code for Lenders",
        "adverse_action_reason": "An account is currently past due.",
        "plain_language_template": (
            "At least one account is {observed} days past due. Our guideline is "
            "{benchmark} days."
        ),
        "display_order": 70,
        "is_scored": 1,
    },
    {
        "factor_code": "COLLECTIONS",
        "factor_name": "Collections accounts",
        "category": "PAYMENT_HISTORY",
        "weight": -25.0,
        "benchmark_threshold": 0.0,
        "comparison_operator": "LTE",
        "severity": "MEDIUM",
        "regulation_ref": "RBI Fair Practices Code for Lenders",
        "adverse_action_reason": "One or more accounts are in collections.",
        "plain_language_template": (
            "Our review found {observed} account(s) in collections. Our guideline is "
            "{benchmark}."
        ),
        "display_order": 80,
        "is_scored": 1,
    },
    {
        "factor_code": "BANKRUPTCY",
        "factor_name": "Bankruptcy history",
        "category": "PAYMENT_HISTORY",
        "weight": -100.0,
        "benchmark_threshold": 0.0,
        "comparison_operator": "LTE",
        "severity": "HIGH",
        "regulation_ref": "RBI Fair Practices Code for Lenders",
        "adverse_action_reason": "A bankruptcy is reported in the applicant's credit history.",
        "plain_language_template": (
            "A bankruptcy is reported in your credit history. Our guideline is "
            "{benchmark} bankruptcies."
        ),
        "display_order": 90,
        "is_scored": 1,
    },
]


def default_weights() -> dict[str, dict[str, Any]]:
    """Return the factor definitions keyed by factor code."""

    return {item["factor_code"]: dict(item) for item in FACTOR_DEFINITIONS}


def coerce_weights(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Normalise rows loaded from Exasol (strings/Decimals) into floats."""

    weights: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = dict(row)
        item["weight"] = float(item["weight"])
        item["benchmark_threshold"] = float(item.get("benchmark_threshold") or 0.0)
        item["display_order"] = int(item.get("display_order") or 0)
        item["is_scored"] = int(item.get("is_scored") or 0)
        weights[str(item["factor_code"]).upper()] = item
    return weights


def _weight(weights: Mapping[str, Mapping[str, Any]], code: str) -> float:
    return float(weights[code]["weight"])


def _threshold(weights: Mapping[str, Mapping[str, Any]], code: str) -> float:
    return float(weights[code]["benchmark_threshold"])


def approval_threshold(weights: Mapping[str, Mapping[str, Any]]) -> float:
    return _weight(weights, "DECISION_APPROVE_THRESHOLD")


def refer_threshold(weights: Mapping[str, Mapping[str, Any]]) -> float:
    return _weight(weights, "DECISION_REFER_THRESHOLD")


def decision_for(score: float, weights: Mapping[str, Mapping[str, Any]]) -> str:
    if score >= approval_threshold(weights):
        return "APPROVED"
    if score >= refer_threshold(weights):
        return "REFERRED"
    return "DECLINED"


def grade_for(score: float, weights: Mapping[str, Mapping[str, Any]] | None = None) -> str:
    if weights:
        approve = approval_threshold(weights)
        refer = refer_threshold(weights)
        if score >= approve + 80:
            return "A"
        if score >= approve:
            return "B"
        if score >= approve - 40:
            return "C"
        if score >= refer:
            return "D"
        return "E"
    if score >= 830:
        return "A"
    if score >= 750:
        return "B"
    if score >= 710:
        return "C"
    if score >= 680:
        return "D"
    return "E"


@dataclass
class ScoreContribution:
    factor_code: str
    factor_name: str
    category: str
    observed: float
    benchmark: float
    contribution: float
    severity: str
    regulation_ref: str
    reason: str
    plain_language: str
    comparison_operator: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "factor_code": self.factor_code,
            "factor_name": self.factor_name,
            "category": self.category,
            "observed": round(self.observed, 4),
            "benchmark": round(self.benchmark, 4),
            "contribution": round(self.contribution, 2),
            "severity": self.severity,
            "regulation_ref": self.regulation_ref,
            "reason": self.reason,
            "plain_language": self.plain_language,
            "comparison_operator": self.comparison_operator,
        }


@dataclass
class ScoreResult:
    score: float
    decision: str
    grade: str
    contributions: list[ScoreContribution] = field(default_factory=list)

    @property
    def negative_factors(self) -> list[ScoreContribution]:
        return sorted(
            [c for c in self.contributions if c.contribution < -0.5],
            key=lambda c: c.contribution,
        )

    @property
    def positive_factors(self) -> list[ScoreContribution]:
        return sorted(
            [c for c in self.contributions if c.contribution > 0.5],
            key=lambda c: c.contribution,
            reverse=True,
        )


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _render_template(template: str, observed: float, benchmark: float, code: str) -> str:
    pct_codes = {"DTI_RATIO", "UTILIZATION", "EXPOSURE_MISMATCH"}
    if code in pct_codes:
        return template.format(
            observed=round(observed, 4),
            benchmark=round(benchmark, 4),
            observed_pct=_fmt_pct(observed),
            benchmark_pct=_fmt_pct(benchmark),
        )
    return template.format(
        observed=f"{observed:g}",
        benchmark=f"{benchmark:g}",
        observed_pct=_fmt_pct(observed),
        benchmark_pct=_fmt_pct(benchmark),
    )


def score_metrics(
    metrics: Mapping[str, Any],
    weights: Mapping[str, Mapping[str, Any]] | None = None,
) -> ScoreResult:
    """Recompute the eligibility score and every factor contribution.

    ``metrics`` keys:
      bureau_score, dti_ratio, delinquencies_12m, hard_inquiries_6m,
      utilization_ratio, variance_ratio, max_dpd, collections_count, bankruptcies
    """

    w = weights or default_weights()

    bureau_score = float(metrics.get("bureau_score") or 680.0)
    dti = max(0.0, float(metrics.get("dti_ratio") or 0.0))
    delinquencies = max(0.0, float(metrics.get("delinquencies_12m") or 0.0))
    inquiries = max(0.0, float(metrics.get("hard_inquiries_6m") or 0.0))
    utilization = max(0.0, float(metrics.get("utilization_ratio") or 0.0))
    variance = max(0.0, float(metrics.get("variance_ratio") or 0.0))
    dpd = max(0.0, float(metrics.get("max_dpd") or 0.0))
    collections = max(0.0, float(metrics.get("collections_count") or 0.0))
    bankruptcies = max(0.0, float(metrics.get("bankruptcies") or 0.0))

    score = _weight(w, "SCORE_BASE")
    contributions: list[ScoreContribution] = []

    def add(code: str, observed: float, contribution: float) -> None:
        item = w[code]
        benchmark = _threshold(w, code)
        contributions.append(
            ScoreContribution(
                factor_code=code,
                factor_name=item["factor_name"],
                category=item["category"],
                observed=observed,
                benchmark=benchmark,
                contribution=contribution,
                severity=item["severity"],
                regulation_ref=item["regulation_ref"],
                reason=item["adverse_action_reason"],
                plain_language=_render_template(
                    item["plain_language_template"], observed, benchmark, code
                ),
                comparison_operator=item["comparison_operator"],
            )
        )

    add(
        "BUREAU_SCORE",
        bureau_score,
        (bureau_score - _threshold(w, "BUREAU_SCORE")) * _weight(w, "BUREAU_SCORE"),
    )
    dti_threshold = _threshold(w, "DTI_RATIO")
    dti_contribution = (
        _weight(w, "DTI_RATIO") * (1.0 + 2.5 * (dti - dti_threshold))
        if dti > dti_threshold
        else 0.0
    )
    add("DTI_RATIO", dti, dti_contribution)

    add(
        "DELINQUENCY_12M",
        delinquencies,
        _weight(w, "DELINQUENCY_12M") * delinquencies,
    )

    inquiry_threshold = _threshold(w, "HARD_INQUIRY_6M")
    add(
        "HARD_INQUIRY_6M",
        inquiries,
        _weight(w, "HARD_INQUIRY_6M") * max(0.0, inquiries - inquiry_threshold),
    )

    util_threshold = _threshold(w, "UTILIZATION")
    util_contribution = (
        _weight(w, "UTILIZATION")
        * min(3.0, max(0.0, utilization - util_threshold) / 0.25)
        if utilization > util_threshold
        else 0.0
    )
    add("UTILIZATION", utilization, util_contribution)

    variance_threshold = _threshold(w, "EXPOSURE_MISMATCH")
    variance_contribution = (
        _weight(w, "EXPOSURE_MISMATCH")
        * min(2.0, max(0.0, variance - variance_threshold) / 0.09)
        if variance > variance_threshold
        else 0.0
    )
    add("EXPOSURE_MISMATCH", variance, variance_contribution)

    add(
        "DAYS_PAST_DUE",
        dpd,
        _weight(w, "DAYS_PAST_DUE") * max(0.0, dpd),
    )
    add("COLLECTIONS", collections, _weight(w, "COLLECTIONS") * collections)
    add("BANKRUPTCY", bankruptcies, _weight(w, "BANKRUPTCY") * bankruptcies)

    score += sum(c.contribution for c in contributions)
    score = round(min(MAX_SCORE, max(MIN_SCORE, score)), 1)

    contributions.sort(key=lambda c: c.contribution)
    return ScoreResult(
        score=score,
        decision=decision_for(score, w),
        grade=grade_for(score, w),
        contributions=contributions,
    )


def build_score_sql(
    weights: Mapping[str, Mapping[str, Any]] | None = None,
    columns: Mapping[str, str] | None = None,
) -> str:
    """Build the SQL expression used by the Exasol credit-360 view.

    Numeric weights are injected from the ``RISK_FACTOR_WEIGHTS`` table at view
    creation time.  The expression relies only on aggregate/scalar functions
    that Exasol evaluates in-memory.
    """

    w = weights or default_weights()
    c = {
        "bureau_score": "bureau_score",
        "dti_ratio": "latest_dti_ratio",
        "delinquencies_12m": "delinquencies_12m",
        "hard_inquiries_6m": "hard_inquiries_6m",
        "utilization_ratio": "portfolio_utilization_ratio",
        "variance_ratio": "variance_ratio",
        "max_dpd": "max_dpd",
        "collections_count": "collections_count",
        "bankruptcies": "bankruptcies",
    }
    if columns:
        c.update(columns)

    base = _weight(w, "SCORE_BASE")
    bureau_benchmark = _threshold(w, "BUREAU_SCORE")
    bureau_weight = _weight(w, "BUREAU_SCORE")
    dti_threshold = _threshold(w, "DTI_RATIO")
    dti_weight = _weight(w, "DTI_RATIO")
    delinq_weight = _weight(w, "DELINQUENCY_12M")
    inquiry_threshold = _threshold(w, "HARD_INQUIRY_6M")
    inquiry_weight = _weight(w, "HARD_INQUIRY_6M")
    util_threshold = _threshold(w, "UTILIZATION")
    util_weight = _weight(w, "UTILIZATION")
    var_threshold = _threshold(w, "EXPOSURE_MISMATCH")
    var_weight = _weight(w, "EXPOSURE_MISMATCH")
    dpd_weight = _weight(w, "DAYS_PAST_DUE")
    collections_weight = _weight(w, "COLLECTIONS")
    bankruptcy_weight = _weight(w, "BANKRUPTCY")

    return f"""ROUND(LEAST({MAX_SCORE:.1f}, GREATEST({MIN_SCORE:.1f},
            {base:.6f}
            + (COALESCE({c['bureau_score']}, {bureau_benchmark:.6f}) - {bureau_benchmark:.6f}) * {bureau_weight:.6f}
            + CASE WHEN {c['dti_ratio']} > {dti_threshold:.6f}
                   THEN {dti_weight:.6f} * (1.0 + 2.5 * ({c['dti_ratio']} - {dti_threshold:.6f}))
                   ELSE 0.0 END
            + {delinq_weight:.6f} * {c['delinquencies_12m']}
            + {inquiry_weight:.6f} * GREATEST(0.0, {c['hard_inquiries_6m']} - {inquiry_threshold:.6f})
            + CASE WHEN {c['utilization_ratio']} > {util_threshold:.6f}
                   THEN {util_weight:.6f} * LEAST(3.0, ({c['utilization_ratio']} - {util_threshold:.6f}) / 0.25)
                   ELSE 0.0 END
            + CASE WHEN {c['variance_ratio']} > {var_threshold:.6f}
                   THEN {var_weight:.6f} * LEAST(2.0, ({c['variance_ratio']} - {var_threshold:.6f}) / 0.09)
                   ELSE 0.0 END
            + {dpd_weight:.6f} * GREATEST(0.0, {c['max_dpd']})
            + {collections_weight:.6f} * {c['collections_count']}
            + {bankruptcy_weight:.6f} * {c['bankruptcies']}
        )), 1)"""


def build_score_udf(
    weights: Mapping[str, Mapping[str, Any]] | None = None,
    schema: str = "CREDENCEIQ",
    script: str = "SCORE_PORTFOLIO",
) -> str:
    """Build an Exasol Python SET UDF that reproduces the scoring model in-database.

    The UDF is generated from the same ``RISK_FACTOR_WEIGHTS`` rows as the SQL
    view, so the model cannot drift between the two engines.  It scores an
    entire applicant set inside Exasol instead of shipping factor rows to the
    application tier.
    """

    w = weights or default_weights()

    base = _weight(w, "SCORE_BASE")
    bureau_benchmark = _threshold(w, "BUREAU_SCORE")
    bureau_weight = _weight(w, "BUREAU_SCORE")
    dti_threshold = _threshold(w, "DTI_RATIO")
    dti_weight = _weight(w, "DTI_RATIO")
    delinq_weight = _weight(w, "DELINQUENCY_12M")
    inquiry_threshold = _threshold(w, "HARD_INQUIRY_6M")
    inquiry_weight = _weight(w, "HARD_INQUIRY_6M")
    util_threshold = _threshold(w, "UTILIZATION")
    util_weight = _weight(w, "UTILIZATION")
    var_threshold = _threshold(w, "EXPOSURE_MISMATCH")
    var_weight = _weight(w, "EXPOSURE_MISMATCH")
    dpd_weight = _weight(w, "DAYS_PAST_DUE")
    collections_weight = _weight(w, "COLLECTIONS")
    bankruptcy_weight = _weight(w, "BANKRUPTCY")
    approve = approval_threshold(w)
    refer = refer_threshold(w)

    return f"""CREATE OR REPLACE PYTHON3 SET SCRIPT {schema}.{script}(
    CUSTOMER_ID DECIMAL(12,0),
    BUREAU_SCORE DOUBLE,
    DTI_RATIO DOUBLE,
    DELINQUENCIES_12M DOUBLE,
    HARD_INQUIRIES_6M DOUBLE,
    UTILIZATION_RATIO DOUBLE,
    VARIANCE_RATIO DOUBLE,
    MAX_DPD DOUBLE,
    COLLECTIONS_COUNT DOUBLE,
    BANKRUPTCIES DOUBLE
)
EMITS (
    CUSTOMER_ID_OUT DECIMAL(12,0),
    SCORE DOUBLE,
    DECISION VARCHAR(10),
    GRADE VARCHAR(2)
) AS
def run(ctx):
    while True:
        bureau = float(ctx.BUREAU_SCORE) if ctx.BUREAU_SCORE is not None else {bureau_benchmark:.6f}
        dti = max(0.0, float(ctx.DTI_RATIO) if ctx.DTI_RATIO is not None else 0.0)
        delinq = max(0.0, float(ctx.DELINQUENCIES_12M) if ctx.DELINQUENCIES_12M is not None else 0.0)
        inquiries = max(0.0, float(ctx.HARD_INQUIRIES_6M) if ctx.HARD_INQUIRIES_6M is not None else 0.0)
        utilization = max(0.0, float(ctx.UTILIZATION_RATIO) if ctx.UTILIZATION_RATIO is not None else 0.0)
        variance = max(0.0, float(ctx.VARIANCE_RATIO) if ctx.VARIANCE_RATIO is not None else 0.0)
        dpd = max(0.0, float(ctx.MAX_DPD) if ctx.MAX_DPD is not None else 0.0)
        collections = max(0.0, float(ctx.COLLECTIONS_COUNT) if ctx.COLLECTIONS_COUNT is not None else 0.0)
        bankruptcies = max(0.0, float(ctx.BANKRUPTCIES) if ctx.BANKRUPTCIES is not None else 0.0)

        score = {base:.6f}
        score += (bureau - {bureau_benchmark:.6f}) * {bureau_weight:.6f}
        if dti > {dti_threshold:.6f}:
            score += {dti_weight:.6f} * (1.0 + 2.5 * (dti - {dti_threshold:.6f}))
        score += {delinq_weight:.6f} * delinq
        score += {inquiry_weight:.6f} * max(0.0, inquiries - {inquiry_threshold:.6f})
        if utilization > {util_threshold:.6f}:
            score += {util_weight:.6f} * min(3.0, (utilization - {util_threshold:.6f}) / 0.25)
        if variance > {var_threshold:.6f}:
            score += {var_weight:.6f} * min(2.0, (variance - {var_threshold:.6f}) / 0.09)
        score += {dpd_weight:.6f} * dpd
        score += {collections_weight:.6f} * collections
        score += {bankruptcy_weight:.6f} * bankruptcies
        score = round(min({MAX_SCORE:.1f}, max({MIN_SCORE:.1f}, score)), 1)

        if score >= {approve:.1f}:
            decision = 'APPROVED'
        elif score >= {refer:.1f}:
            decision = 'REFERRED'
        else:
            decision = 'DECLINED'

        if score >= {approve + 80:.1f}:
            grade = 'A'
        elif score >= {approve:.1f}:
            grade = 'B'
        elif score >= {approve - 40:.1f}:
            grade = 'C'
        elif score >= {refer:.1f}:
            grade = 'D'
        else:
            grade = 'E'

        ctx.emit(ctx.CUSTOMER_ID, score, decision, grade)
        if not ctx.next():
            break
/"""
