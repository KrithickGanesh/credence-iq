export type Decision = "APPROVED" | "DECLINED" | "REFERRED";
export type ReconciliationStatus = "RECONCILED" | "MINOR_VARIANCE" | "MISMATCH";

export interface ApplicationSummary {
  customer_id: number;
  first_name: string;
  last_name: string;
  email: string;
  city: string;
  state: string;
  segment: string;
  annual_income: number;
  latest_application_id: number;
  latest_application_date: string;
  latest_decision_date: string;
  latest_decision: Decision;
  latest_requested_amount: number;
  latest_product_type: string;
  latest_tenure_months: number;
  latest_purpose: string;
  latest_dti_ratio: number;
  latest_income: number;
  latest_proposed_emi: number;
  latest_risk_grade: string;
  latest_model_score: number;
  latest_denial_factors: string;
  latest_channel: string;
  latest_branch_code: string;
  bureau_score: number;
  delinquencies_12m: number;
  hard_inquiries_6m: number;
  collections_count: number;
  bankruptcies: number;
  credit_history_months: number;
  bureau_utilization_ratio: number;
  core_exposure: number;
  card_exposure: number;
  micro_exposure: number;
  gross_exposure: number;
  reconciled_exposure: number;
  debt_variance: number;
  variance_ratio: number;
  total_sanctioned: number;
  max_dpd: number;
  systems_reporting: number;
  exposure_accounts: number;
  conflicted_facilities: number;
  reported_balance_spread: number;
  portfolio_utilization_ratio: number;
  utilization_percentile: number;
  exposure_percentile: number;
  reconciliation_status: ReconciliationStatus;
  has_discrepancy: number;
  eligibility_score: number;
  eligibility_decision: Decision;
  score_gap_to_approval: number;
  recomputed_grade: string;
}

export interface ApplicationsResponse {
  items: ApplicationSummary[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  query_ms: number;
  generated_at: string;
}

export interface ApplicantProfile {
  customer_id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  city: string;
  state: string;
  postal_code: string;
  segment: string;
  annual_income: number;
  employment_status: string;
  kyc_status: string;
  customer_since: string;
}

export interface ApplicationDetail {
  application_id: number;
  application_date: string;
  decision_date: string;
  decision: Decision;
  requested_amount: number;
  product_type: string;
  tenure_months: number;
  purpose: string;
  dti_ratio: number;
  income_at_application: number;
  proposed_emi: number;
  risk_grade: string;
  model_score: number;
  denial_factors: string;
  channel: string;
  branch_code: string;
}

export interface FactorBreakdown {
  factor_code: string;
  factor_name: string;
  category: string;
  observed: number;
  benchmark: number;
  contribution: number;
  severity: string;
  regulation_ref: string;
  reason: string;
  plain_language: string;
  comparison_operator: string;
  is_negative: boolean;
}

export interface EligibilityDetail {
  score: number;
  decision: Decision;
  grade: string;
  score_gap_to_approval: number;
  approve_threshold: number;
  refer_threshold: number;
  factors: FactorBreakdown[];
}

export interface SystemExposure {
  system: string;
  label: string;
  exposure: number;
  accounts: number;
  share: number;
  max_dpd: number;
}

export interface ExposureReport {
  exposure_id: string;
  source_system: string;
  system_label: string;
  outstanding_balance: number;
  sanctioned_limit: number;
  days_past_due: number;
  account_status: string;
  last_reported_date: string;
}

export interface FacilityAudit {
  facility_ref: string;
  product_type: string;
  systems_reporting: number;
  min_balance: number;
  max_balance: number;
  balance_spread: number;
  days_past_due: number;
  status: "CONFLICT" | "MATCHED";
  reports: ExposureReport[];
}

export interface ReconciliationSummary {
  status: ReconciliationStatus;
  reported_total: number;
  reconciled_total: number;
  variance: number;
  variance_ratio: number;
  conflicted_facilities: number;
  systems_reporting: number;
  exposure_accounts: number;
  reported_balance_spread: number;
  portfolio_utilization_ratio: number;
  utilization_percentile: number;
  exposure_percentile: number;
  systems: SystemExposure[];
  facilities: FacilityAudit[];
}

export interface BureauRecord {
  bureau_name: string;
  report_date: string;
  bureau_score: number;
  delinquencies_12m: number;
  delinquencies_24m: number;
  hard_inquiries_6m: number;
  collections_count: number;
  bankruptcies: number;
  credit_history_months: number;
  utilization_ratio: number;
  total_accounts: number;
}

export interface ApplicantDetailResponse {
  applicant: ApplicantProfile;
  application: ApplicationDetail;
  eligibility: EligibilityDetail;
  reconciliation: ReconciliationSummary;
  bureau_records: BureauRecord[];
  query_ms: number;
  generated_at: string;
}

export interface SimulationRequest {
  revolving_paydown: number;
  resolve_exposure_mismatch: boolean;
  income_increase_annual: number;
  additional_hard_inquiries: number;
}

export interface SimulationProjection {
  score: number;
  decision: Decision;
  grade: string;
  score_gap_to_approval: number;
  dti_ratio: number;
  utilization_ratio: number;
  variance_ratio: number;
  gross_exposure: number;
  card_exposure: number;
  hard_inquiries_6m: number;
}

export interface ActionImpact {
  code: string;
  label: string;
  description: string;
  score_impact: number;
  projected_score: number;
  applied: boolean;
}

export interface PathToApproval {
  target_score: number;
  gap: number;
  reachable: boolean;
  additional_paydown: number | null;
  message: string;
}

export interface SimulationResponse {
  customer_id: number;
  applicant_name: string;
  application_id: number;
  current: SimulationProjection;
  simulated: SimulationProjection;
  score_delta: number;
  decision_changed: boolean;
  actions: ActionImpact[];
  path_to_approval: PathToApproval;
  assumptions: string[];
  query_ms: number;
  generated_at: string;
}

export interface FactorDisclosure {
  factor_code: string;
  factor_name: string;
  finding: string;
  regulation: string;
  impact: string;
}

export interface ComplianceLetter {
  title: string;
  recipient: string;
  body: string;
  factor_disclosures: FactorDisclosure[];
  appeal_rights: string[];
  contact: string;
  issued_date: string;
}

export interface CustomerExplanation {
  headline: string;
  summary: string;
  what_this_means: string[];
  next_steps: string[];
}

export interface AdverseActionResponse {
  report_id: string;
  generated_at: string;
  provider: string;
  model: string;
  generation_mode: "llm" | "template";
  persisted: boolean;
  applicant_name: string;
  decision: Decision;
  score: number;
  compliance_letter: ComplianceLetter;
  customer_explanation: CustomerExplanation;
  disclaimer: string;
  query_ms: number;
  llm_ms: number;
}

export interface PortfolioTotals {
  total_applications: number;
  approved: number;
  declined: number;
  referred: number;
  decline_rate: number;
  approval_rate: number;
  customers: number;
  mismatches: number;
  minor_variances: number;
  reconciled: number;
  mismatch_rate: number;
  reported_exposure: number;
  reconciled_exposure: number;
  double_counted_exposure: number;
  average_dti: number;
  average_bureau_score: number;
  average_eligibility_score: number;
}

export interface ExposureSystem {
  system: string;
  label: string;
  exposure: number;
  accounts: number;
  share: number;
}

export interface DecisionSlice {
  decision: Decision;
  count: number;
  share: number;
}

export interface VelocityPoint {
  month: string;
  applications: number;
  declines: number;
  decline_rate: number;
}

export interface DenialDriver {
  factor_code: string;
  factor_name: string;
  count: number;
  avg_contribution: number;
  regulation_ref: string;
}

export interface ReconciliationSlice {
  status: ReconciliationStatus;
  count: number;
  share: number;
}

export interface OverviewResponse {
  portfolio: PortfolioTotals;
  exposure_by_system: ExposureSystem[];
  decision_mix: DecisionSlice[];
  rejection_velocity: VelocityPoint[];
  denial_drivers: DenialDriver[];
  reconciliation_mix: ReconciliationSlice[];
  top_discrepancies: ApplicationSummary[];
  query_ms: number;
  generated_at: string;
}

export interface UdfScoringResponse {
  script: string;
  engine: string;
  customers_scored: number;
  matching_scores: number;
  agreement_rate: number;
  mean_abs_difference: number;
  max_abs_difference: number;
  decision_matches: number;
  decision_mix: Record<string, number>;
  elapsed_ms: number;
  generated_at: string;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  database: "up" | "down";
  schema: string;
  api_version: string;
  exasol_version: string | null;
  pool: {
    size: number;
    created: number;
    in_use: number;
    available: number;
    queries: number;
    avg_query_ms: number;
  };
  ping_ms: number;
  generated_at: string;
}
