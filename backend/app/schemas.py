"""Pydantic response and request contracts for the CredenceIQ API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Decision = Literal["APPROVED", "DECLINED", "REFERRED"]
ReconciliationStatus = Literal["RECONCILED", "MINOR_VARIANCE", "MISMATCH"]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
class ApplicationSummary(ApiModel):
    customer_id: int
    first_name: str
    last_name: str
    email: str
    city: str
    state: str
    segment: str
    annual_income: float
    latest_application_id: int
    latest_application_date: date
    latest_decision_date: date
    latest_decision: Decision
    latest_requested_amount: float
    latest_product_type: str
    latest_tenure_months: int
    latest_purpose: str
    latest_dti_ratio: float
    latest_income: float
    latest_proposed_emi: float
    latest_risk_grade: str
    latest_model_score: float
    latest_denial_factors: str
    latest_channel: str
    latest_branch_code: str
    bureau_score: int
    delinquencies_12m: int
    hard_inquiries_6m: int
    collections_count: int
    bankruptcies: int
    credit_history_months: int
    bureau_utilization_ratio: float
    core_exposure: float
    card_exposure: float
    micro_exposure: float
    gross_exposure: float
    reconciled_exposure: float
    debt_variance: float
    variance_ratio: float
    total_sanctioned: float
    max_dpd: int
    systems_reporting: int
    exposure_accounts: int
    conflicted_facilities: int
    reported_balance_spread: float
    portfolio_utilization_ratio: float
    utilization_percentile: float
    exposure_percentile: float
    reconciliation_status: ReconciliationStatus
    has_discrepancy: int
    eligibility_score: float
    eligibility_decision: Decision
    score_gap_to_approval: float
    recomputed_grade: str


class ApplicationsResponse(ApiModel):
    items: list[ApplicationSummary]
    page: int
    page_size: int
    total: int
    total_pages: int
    query_ms: float
    generated_at: datetime


# ---------------------------------------------------------------------------
# Applicant reconciliation
# ---------------------------------------------------------------------------
class ApplicantProfile(ApiModel):
    customer_id: int
    first_name: str
    last_name: str
    email: str
    phone: str
    city: str
    state: str
    postal_code: str
    segment: str
    annual_income: float
    employment_status: str
    kyc_status: str
    customer_since: date


class ApplicationDetail(ApiModel):
    application_id: int
    application_date: date
    decision_date: date
    decision: Decision
    requested_amount: float
    product_type: str
    tenure_months: int
    purpose: str
    dti_ratio: float
    income_at_application: float
    proposed_emi: float
    risk_grade: str
    model_score: float
    denial_factors: str
    channel: str
    branch_code: str


class FactorBreakdown(ApiModel):
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
    is_negative: bool


class EligibilityDetail(ApiModel):
    score: float
    decision: Decision
    grade: str
    score_gap_to_approval: float
    approve_threshold: float
    refer_threshold: float
    factors: list[FactorBreakdown]


class SystemExposure(ApiModel):
    system: str
    label: str
    exposure: float
    accounts: int
    share: float
    max_dpd: int


class ExposureReport(ApiModel):
    exposure_id: str
    source_system: str
    system_label: str
    outstanding_balance: float
    sanctioned_limit: float
    days_past_due: int
    account_status: str
    last_reported_date: date


class FacilityAudit(ApiModel):
    facility_ref: str
    product_type: str
    systems_reporting: int
    min_balance: float
    max_balance: float
    balance_spread: float
    days_past_due: int
    status: str
    reports: list[ExposureReport]


class ReconciliationSummary(ApiModel):
    status: ReconciliationStatus
    reported_total: float
    reconciled_total: float
    variance: float
    variance_ratio: float
    conflicted_facilities: int
    systems_reporting: int
    exposure_accounts: int
    reported_balance_spread: float
    portfolio_utilization_ratio: float
    utilization_percentile: float
    exposure_percentile: float
    systems: list[SystemExposure]
    facilities: list[FacilityAudit]


class BureauRecord(ApiModel):
    bureau_name: str
    report_date: date
    bureau_score: int
    delinquencies_12m: int
    delinquencies_24m: int
    hard_inquiries_6m: int
    collections_count: int
    bankruptcies: int
    credit_history_months: int
    utilization_ratio: float
    total_accounts: int


class ApplicantDetailResponse(ApiModel):
    applicant: ApplicantProfile
    application: ApplicationDetail
    eligibility: EligibilityDetail
    reconciliation: ReconciliationSummary
    bureau_records: list[BureauRecord]
    query_ms: float
    generated_at: datetime


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
class SimulationRequest(ApiModel):
    revolving_paydown: float = Field(default=0.0, ge=0.0, le=1_000_000)
    resolve_exposure_mismatch: bool = False
    income_increase_annual: float = Field(default=0.0, ge=0.0, le=1_000_000)
    additional_hard_inquiries: int = Field(default=0, ge=0, le=20)


class SimulationProjection(ApiModel):
    score: float
    decision: Decision
    grade: str
    score_gap_to_approval: float
    dti_ratio: float
    utilization_ratio: float
    variance_ratio: float
    gross_exposure: float
    card_exposure: float
    hard_inquiries_6m: int


class ActionImpact(ApiModel):
    code: str
    label: str
    description: str
    score_impact: float
    projected_score: float
    applied: bool


class PathToApproval(ApiModel):
    target_score: float
    gap: float
    reachable: bool
    additional_paydown: float | None
    message: str


class SimulationResponse(ApiModel):
    customer_id: int
    applicant_name: str
    application_id: int
    current: SimulationProjection
    simulated: SimulationProjection
    score_delta: float
    decision_changed: bool
    actions: list[ActionImpact]
    path_to_approval: PathToApproval
    assumptions: list[str]
    query_ms: float
    generated_at: datetime


# ---------------------------------------------------------------------------
# Adverse action
# ---------------------------------------------------------------------------
class AdverseActionRequest(ApiModel):
    tone: Literal["formal", "plain"] = "formal"
    include_state_disclosure: bool = True


class FactorDisclosure(ApiModel):
    factor_code: str
    factor_name: str
    finding: str
    regulation: str
    impact: str


class ComplianceLetter(ApiModel):
    title: str
    recipient: str
    body: str
    factor_disclosures: list[FactorDisclosure]
    appeal_rights: list[str]
    contact: str
    issued_date: date


class CustomerExplanation(ApiModel):
    headline: str
    summary: str
    what_this_means: list[str]
    next_steps: list[str]


class AdverseActionResponse(ApiModel):
    report_id: str
    generated_at: datetime
    provider: str
    model: str
    generation_mode: Literal["llm", "template"]
    persisted: bool
    applicant_name: str
    decision: Decision
    score: float
    compliance_letter: ComplianceLetter
    customer_explanation: CustomerExplanation
    disclaimer: str
    query_ms: float
    llm_ms: float


class GeneratedDisclosure(ApiModel):
    compliance_letter: ComplianceLetter
    customer_explanation: CustomerExplanation


# ---------------------------------------------------------------------------
# Portfolio overview
# ---------------------------------------------------------------------------
class PortfolioTotals(ApiModel):
    total_applications: int
    approved: int
    declined: int
    referred: int
    decline_rate: float
    approval_rate: float
    customers: int
    mismatches: int
    minor_variances: int
    reconciled: int
    mismatch_rate: float
    reported_exposure: float
    reconciled_exposure: float
    double_counted_exposure: float
    average_dti: float
    average_bureau_score: float
    average_eligibility_score: float


class ExposureSystem(ApiModel):
    system: str
    label: str
    exposure: float
    accounts: int
    share: float


class DecisionSlice(ApiModel):
    decision: Decision
    count: int
    share: float


class VelocityPoint(ApiModel):
    month: str
    applications: int
    declines: int
    decline_rate: float


class DenialDriver(ApiModel):
    factor_code: str
    factor_name: str
    count: int
    avg_contribution: float
    regulation_ref: str


class ReconciliationSlice(ApiModel):
    status: ReconciliationStatus
    count: int
    share: float


class OverviewResponse(ApiModel):
    portfolio: PortfolioTotals
    exposure_by_system: list[ExposureSystem]
    decision_mix: list[DecisionSlice]
    rejection_velocity: list[VelocityPoint]
    denial_drivers: list[DenialDriver]
    reconciliation_mix: list[ReconciliationSlice]
    top_discrepancies: list[ApplicationSummary]
    query_ms: float
    generated_at: datetime


# ---------------------------------------------------------------------------
# Health / metadata
# ---------------------------------------------------------------------------
class HealthResponse(ApiModel):
    status: Literal["ok", "degraded"]
    database: Literal["up", "down"]
    schema: str
    api_version: str
    exasol_version: str | None = None
    pool: dict[str, Any]
    ping_ms: float
    generated_at: datetime


class FactorWeight(ApiModel):
    factor_code: str
    factor_name: str
    category: str
    weight: float
    benchmark_threshold: float
    comparison_operator: str
    severity: str
    regulation_ref: str
    adverse_action_reason: str
    plain_language_template: str
    display_order: int
    is_scored: int


class FactorsResponse(ApiModel):
    factors: list[FactorWeight]
    approve_threshold: float
    refer_threshold: float
    query_ms: float
