"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Building2,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  FileSearch,
  Filter,
  Gauge,
  GitCompareArrows,
  Landmark,
  Layers3,
  Search,
  ShieldAlert,
  SlidersHorizontal,
  X,
} from "lucide-react";

import { api } from "@/lib/api";
import { cn, compactCurrency, currency, dateTime, number, pct, shortDate, titleCase } from "@/lib/format";
import { useApi, useDebouncedValue } from "@/lib/hooks";
import type {
  ApplicantDetailResponse,
  ApplicationsResponse,
  ApplicationSummary,
  FacilityAudit,
  FactorBreakdown,
} from "@/lib/types";
import {
  Badge,
  Card,
  DecisionBadge,
  EmptyState,
  ErrorPanel,
  InfoRow,
  LoadingPanel,
  PageHeader,
  ReconciliationBadge,
  SectionHeading,
  SeverityBadge,
  Skeleton,
} from "@/components/ui";
import { BureauUtilizationChart } from "@/components/charts";

const PAGE_SIZE = 15;

type SortField =
  | "decision_date"
  | "application_date"
  | "variance"
  | "exposure"
  | "score"
  | "applicant"
  | "requested_amount";

const SORT_OPTIONS: Array<{ value: SortField; label: string }> = [
  { value: "decision_date", label: "Latest decision" },
  { value: "variance", label: "Debt variance" },
  { value: "exposure", label: "Gross exposure" },
  { value: "score", label: "Eligibility score" },
  { value: "requested_amount", label: "Requested amount" },
  { value: "applicant", label: "Applicant name" },
];

function ScoreScale({ score }: { score: number }) {
  const position = Math.max(0, Math.min(100, ((score - 300) / 600) * 100));
  const approve = ((750 - 300) / 600) * 100;
  const refer = ((680 - 300) / 600) * 100;
  const color = score >= 750 ? "bg-brand-500" : score >= 680 ? "bg-amber-500" : "bg-rose-500";
  return (
    <div className="mt-3">
      <div className="relative h-2.5 overflow-hidden rounded-full bg-slate-100">
        <div className="absolute inset-y-0 left-0 w-full bg-gradient-to-r from-rose-100 via-amber-100 to-emerald-100" />
        <div className={cn("absolute inset-y-0 left-0 rounded-full", color)} style={{ width: `${position}%` }} />
        <span className="absolute inset-y-0 w-px bg-white/80" style={{ left: `${approve}%` }} title="Approve threshold: 750" />
        <span className="absolute inset-y-0 w-px bg-white/80" style={{ left: `${refer}%` }} title="Refer threshold: 680" />
      </div>
      <div className="mt-1.5 flex justify-between text-[10px] text-slate-400">
        <span>300</span>
        <span>680 refer</span>
        <span>750 approve</span>
        <span>900</span>
      </div>
    </div>
  );
}

function FactorRow({ factor, max }: { factor: FactorBreakdown; max: number }) {
  const magnitude = Math.max(2, (Math.abs(factor.contribution) / max) * 100);
  return (
    <li className="rounded-xl border border-slate-100 bg-slate-50/50 p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <p className="text-[12px] font-medium text-slate-800">{factor.factor_name}</p>
            <SeverityBadge severity={factor.severity} />
          </div>
          <p className="mt-0.5 text-[10.5px] text-slate-500">
            Observed {factor.comparison_operator === ">=" ? "≥" : "≤"}{" "}
            {factor.observed.toLocaleString("en-US", { maximumFractionDigits: 1 })} vs benchmark{" "}
            {factor.benchmark.toLocaleString("en-US", { maximumFractionDigits: 1 })} ·{" "}
            {factor.regulation_ref}
          </p>
        </div>
        <span className="shrink-0 text-[12px] font-semibold tabular-nums text-rose-600">
          {factor.contribution.toFixed(1)}
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white ring-1 ring-inset ring-slate-100">
        <div
          className="h-full rounded-full bg-gradient-to-r from-rose-400 to-rose-500"
          style={{ width: `${magnitude}%` }}
        />
      </div>
      <p className="mt-2 text-[11px] leading-5 text-slate-600">{factor.plain_language}</p>
    </li>
  );
}

function FacilityCard({ facility }: { facility: FacilityAudit }) {
  const conflicted = facility.status === "CONFLICT";
  return (
    <details
      className={cn(
        "group rounded-xl border bg-white",
        conflicted ? "border-rose-200" : "border-slate-200",
      )}
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2.5 [&::-webkit-details-marker]:hidden">
        <div className="flex min-w-0 items-center gap-2">
          <span
            className={cn(
              "flex h-6 w-6 shrink-0 items-center justify-center rounded-md",
              conflicted ? "bg-rose-50 text-rose-600" : "bg-emerald-50 text-emerald-600",
            )}
          >
            {conflicted ? <GitCompareArrows size={12} /> : <CheckCircle2 size={12} />}
          </span>
          <div className="min-w-0">
            <p className="truncate font-mono text-[10.5px] font-medium text-slate-700">
              {facility.facility_ref}
            </p>
            <p className="text-[10px] text-slate-500">
              {titleCase(facility.product_type)} · {facility.systems_reporting} systems ·{" "}
              {facility.days_past_due} DPD
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-[11.5px] font-semibold tabular-nums text-slate-800">
            {currency(facility.max_balance)}
          </p>
          <p
            className={cn(
              "text-[10px] font-medium",
              conflicted ? "text-rose-600" : "text-emerald-600",
            )}
          >
            {conflicted ? `+${currency(facility.balance_spread)} spread` : "matched"}
          </p>
        </div>
      </summary>
      <div className="border-t border-slate-100 px-3 py-2">
        <table className="w-full text-left">
          <thead>
            <tr className="text-[9.5px] uppercase tracking-[0.08em] text-slate-400">
              <th className="py-1 font-medium">System</th>
              <th className="py-1 text-right font-medium">Balance</th>
              <th className="py-1 text-right font-medium">Limit</th>
              <th className="py-1 text-right font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {facility.reports.map((report) => (
              <tr key={report.exposure_id} className="border-t border-slate-50">
                <td className="py-1.5 text-[10.5px] text-slate-600">{report.system_label}</td>
                <td className="py-1.5 text-right text-[10.5px] tabular-nums text-slate-700">
                  {currency(report.outstanding_balance)}
                </td>
                <td className="py-1.5 text-right text-[10.5px] tabular-nums text-slate-500">
                  {currency(report.sanctioned_limit)}
                </td>
                <td className="py-1.5 text-right text-[10px] text-slate-500">
                  {titleCase(report.account_status)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-1 text-[9.5px] text-slate-400">
          Last reported {shortDate(facility.reports[0]?.last_reported_date)}
        </p>
      </div>
    </details>
  );
}

function DetailPanel({
  customerId,
  onClose,
}: {
  customerId: number;
  onClose: () => void;
}) {
  const { data, error, loading, refetch } = useApi<ApplicantDetailResponse>(
    `applicant-${customerId}`,
    () => api.reconciliation(customerId),
    customerId > 0,
  );

  const topFactors = useMemo(() => {
    if (!data) return { negatives: [] as FactorBreakdown[], max: 1 };
    const negatives = data.eligibility.factors
      .filter((factor) => factor.is_negative)
      .sort((a, b) => a.contribution - b.contribution);
    const max = Math.max(1, ...negatives.map((factor) => Math.abs(factor.contribution)));
    return { negatives, max };
  }, [data]);

  return (
    <div className="flex h-full flex-col">
      <div className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-navy-900 text-white">
            <FileSearch size={14} />
          </span>
          <div>
            <p className="text-[12px] font-semibold text-ink">Applicant 360</p>
            <p className="text-[10px] text-slate-500">
              {data ? `Customer #${data.applicant.customer_id} · ${data.query_ms.toFixed(0)} ms` : "Live Exasol query"}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
          aria-label="Close applicant detail"
        >
          <X size={16} />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {loading && !data ? (
          <div className="space-y-4">
            <Skeleton className="h-20 w-full" />
            <LoadingPanel label="Joining bureau, behavioural, and ledger records…" rows={5} />
          </div>
        ) : error || !data ? (
          <ErrorPanel title="Applicant could not be loaded" message={error ?? "Unknown error"} onRetry={refetch} />
        ) : (
          <div className="space-y-4">
            {/* Identity */}
            <div>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold tracking-tight text-ink">
                    {data.applicant.first_name} {data.applicant.last_name}
                  </h2>
                  <p className="text-[11.5px] text-slate-500">
                    {data.applicant.email} · {data.applicant.phone}
                  </p>
                  <p className="text-[11px] text-slate-400">
                    {data.applicant.city}, {data.applicant.state} {data.applicant.postal_code}
                  </p>
                </div>
                <Badge tone="neutral">{titleCase(data.applicant.segment)}</Badge>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <Badge tone="info">KYC {titleCase(data.applicant.kyc_status)}</Badge>
                <Badge tone="neutral">{titleCase(data.applicant.employment_status)}</Badge>
                <Badge tone="neutral">Customer since {shortDate(data.applicant.customer_since)}</Badge>
              </div>
            </div>

            {/* Decision + score */}
            <div className="rounded-xl border border-slate-200 bg-gradient-to-b from-slate-50/80 to-white p-3.5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="eyebrow">Eligibility score</p>
                  <div className="mt-1 flex items-end gap-2">
                    <span className="text-3xl font-semibold leading-none tracking-tight text-ink tabular-nums">
                      {data.eligibility.score.toFixed(0)}
                    </span>
                    <span className="mb-0.5 text-[11px] text-slate-400">/ 900 · grade {data.eligibility.grade}</span>
                  </div>
                </div>
                <DecisionBadge decision={data.eligibility.decision} />
              </div>
              <ScoreScale score={data.eligibility.score} />
              <div className="mt-3 flex items-center justify-between gap-2 rounded-lg bg-white px-2.5 py-2 ring-1 ring-inset ring-slate-100">
                <span className="text-[10.5px] text-slate-500">
                  {data.eligibility.decision === "APPROVED"
                    ? "Meets the approval threshold"
                    : `${Math.max(0, data.eligibility.score_gap_to_approval).toFixed(0)} pts below approval (${data.eligibility.approve_threshold.toFixed(0)})`}
                </span>
                <Link
                  href={`/studio?customer=${data.applicant.customer_id}`}
                  className="inline-flex shrink-0 items-center gap-1 text-[10.5px] font-semibold text-brand-700 hover:text-brand-800"
                >
                  Simulate <ArrowUpRight size={11} />
                </Link>
              </div>
            </div>

            {/* Application */}
            <div className="rounded-xl border border-slate-200 p-3.5">
              <div className="flex items-center justify-between">
                <p className="eyebrow">Latest application</p>
                <span className="font-mono text-[10px] text-slate-400">
                  #{data.application.application_id}
                </span>
              </div>
              <dl className="mt-2 divide-y divide-slate-50">
                <InfoRow label="Requested" value={currency(data.application.requested_amount)} />
                <InfoRow label="Product" value={titleCase(data.application.product_type)} />
                <InfoRow label="Tenure" value={`${data.application.tenure_months} months`} />
                <InfoRow label="Purpose" value={titleCase(data.application.purpose)} />
                <InfoRow label="DTI ratio" value={pct(data.application.dti_ratio)} />
                <InfoRow label="Proposed EMI" value={currency(data.application.proposed_emi)} />
                <InfoRow
                  label="Decision date"
                  value={shortDate(data.application.decision_date)}
                />
                <InfoRow label="Channel" value={`${titleCase(data.application.channel)} · ${data.application.branch_code}`} />
              </dl>
              {data.application.denial_factors && (
                <p className="mt-2 rounded-lg bg-rose-50 px-2.5 py-2 text-[10.5px] leading-5 text-rose-700">
                  <span className="font-semibold">Decline rationale: </span>
                  {data.application.denial_factors.split(",").map(titleCase).join(" · ")}
                </p>
              )}
            </div>

            {/* Factor breakdown */}
            <div>
              <SectionHeading
                icon={SlidersHorizontal}
                title="Why this score"
                description={`${topFactors.negatives.length} adverse factors applied to the model baseline.`}
              />
              {topFactors.negatives.length === 0 ? (
                <div className="mt-2 rounded-xl border border-emerald-200 bg-emerald-50/60 p-3 text-[11.5px] text-emerald-800">
                  No adverse factors detected. This profile clears every benchmark.
                </div>
              ) : (
                <ul className="mt-2.5 space-y-2">
                  {topFactors.negatives.slice(0, 6).map((factor) => (
                    <FactorRow key={factor.factor_code} factor={factor} max={topFactors.max} />
                  ))}
                </ul>
              )}
            </div>

            {/* Reconciliation */}
            <div className="rounded-xl border border-slate-200 p-3.5">
              <div className="flex items-center justify-between gap-2">
                <SectionHeading icon={Layers3} title="Exposure reconciliation" />
                <ReconciliationBadge status={data.reconciliation.status} compact />
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <div className="rounded-lg bg-slate-50 p-2.5">
                  <p className="text-[9.5px] uppercase tracking-[0.08em] text-slate-500">Reported</p>
                  <p className="mt-0.5 text-sm font-semibold tabular-nums text-slate-800">
                    {compactCurrency(data.reconciliation.reported_total)}
                  </p>
                </div>
                <div className="rounded-lg bg-brand-50 p-2.5">
                  <p className="text-[9.5px] uppercase tracking-[0.08em] text-brand-700">Reconciled</p>
                  <p className="mt-0.5 text-sm font-semibold tabular-nums text-brand-800">
                    {compactCurrency(data.reconciliation.reconciled_total)}
                  </p>
                </div>
              </div>
              <div className="mt-2 flex items-center justify-between gap-2 rounded-lg bg-rose-50 px-2.5 py-2">
                <span className="text-[10.5px] text-rose-700">
                  {data.reconciliation.variance > 0 ? "Double-counted" : "No overstatement"} ·{" "}
                  {data.reconciliation.systems_reporting} systems ·{" "}
                  {data.reconciliation.exposure_accounts} accounts
                </span>
                <span className="text-[11.5px] font-semibold tabular-nums text-rose-700">
                  {currency(data.reconciliation.variance)}
                </span>
              </div>

              <div className="mt-3 space-y-2">
                {data.reconciliation.systems.map((system) => (
                  <div key={system.system} className="flex items-center gap-2">
                    <span className="w-[86px] truncate text-[10.5px] text-slate-600">{system.label}</span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full bg-slate-500"
                        style={{ width: `${Math.min(100, system.share * 100)}%` }}
                      />
                    </div>
                    <span className="w-[74px] text-right text-[10.5px] tabular-nums text-slate-600">
                      {compactCurrency(system.exposure)}
                    </span>
                  </div>
                ))}
              </div>

              <div className="mt-3">
                <BureauUtilizationChart
                  utilization={data.reconciliation.portfolio_utilization_ratio}
                  percentile={data.reconciliation.utilization_percentile}
                />
              </div>

              <div className="mt-3">
                <div className="flex items-center justify-between">
                  <p className="eyebrow">Facility audit</p>
                  <span className="text-[10px] text-slate-400">
                    {data.reconciliation.conflicted_facilities} conflicts
                  </span>
                </div>
                <div className="mt-2 space-y-1.5">
                  {data.reconciliation.facilities.map((facility) => (
                    <FacilityCard key={facility.facility_ref} facility={facility} />
                  ))}
                </div>
              </div>
            </div>

            {/* Bureau */}
            <div className="rounded-xl border border-slate-200 p-3.5">
              <SectionHeading icon={Landmark} title="Bureau records" />
              <div className="mt-2 space-y-2">
                {data.bureau_records.map((record) => (
                  <div
                    key={`${record.bureau_name}-${record.report_date}`}
                    className="rounded-lg border border-slate-100 bg-slate-50/50 p-2.5"
                  >
                    <div className="flex items-center justify-between">
                      <p className="text-[11px] font-medium text-slate-700">{record.bureau_name}</p>
                      <span className="text-[10px] text-slate-400">{shortDate(record.report_date)}</span>
                    </div>
                    <div className="mt-1.5 grid grid-cols-4 gap-x-2 gap-y-1 text-[10px] text-slate-500">
                      <span>
                        Score <b className="tabular-nums text-slate-800">{record.bureau_score}</b>
                      </span>
                      <span>
                        Delinq <b className="tabular-nums text-slate-800">{record.delinquencies_12m}</b>
                      </span>
                      <span>
                        Inquiries <b className="tabular-nums text-slate-800">{record.hard_inquiries_6m}</b>
                      </span>
                      <span>
                        Util <b className="tabular-nums text-slate-800">{pct(record.utilization_ratio, 0)}</b>
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <Link
              href={`/studio?customer=${data.applicant.customer_id}`}
              className="btn-primary w-full"
            >
              Open scenario studio
              <ArrowRight size={14} />
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

function AuditWorkspace() {
  const params = useSearchParams();
  const initialCustomer = Number(params.get("customer") ?? "") || null;
  const initialDiscrepancy = params.get("discrepancy") === "1";

  const [search, setSearch] = useState("");
  const [decision, setDecision] = useState("");
  const [discrepancyOnly, setDiscrepancyOnly] = useState(initialDiscrepancy);
  const [sort, setSort] = useState<SortField>("variance");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number | null>(initialCustomer);

  const debouncedSearch = useDebouncedValue(search, 350);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, decision, discrepancyOnly, sort]);

  useEffect(() => {
    const url = new URL(window.location.href);
    if (selected) url.searchParams.set("customer", String(selected));
    else url.searchParams.delete("customer");
    window.history.replaceState(null, "", url.toString());
  }, [selected]);

  const listKey = JSON.stringify({ page, debouncedSearch, decision, discrepancyOnly, sort });
  const { data, error, loading, refetch } = useApi<ApplicationsResponse>(
    `applications-${listKey}`,
    () =>
      api.applications({
        page,
        page_size: PAGE_SIZE,
        search: debouncedSearch || undefined,
        eligibility_decision: decision || undefined,
        discrepancy_only: discrepancyOnly || undefined,
        sort,
        direction: sort === "applicant" ? "asc" : "desc",
      }),
  );

  const activeFilters = Boolean(debouncedSearch || decision || discrepancyOnly);
  const totalPages = data?.total_pages ?? 1;

  return (
    <>
      <PageHeader
        eyebrow="Discrepancy & exposure audit"
        title="Reconcile every applicant"
        description="Search the full book, isolate cross-ledger conflicts, and inspect the exact factor contributions behind every decision."
        actions={
          <>
            <button type="button" className="btn-ghost" onClick={refetch} disabled={loading}>
              <GitCompareArrows size={14} className={cn(loading && "animate-pulse")} />
              Re-run reconciliation
            </button>
            <Link href="/" className="btn-dark">
              <ArrowLeft size={14} />
              Overview
            </Link>
          </>
        }
        meta={
          <>
            <span className="inline-flex items-center gap-1.5 text-[11px] text-slate-500">
              <ShieldAlert size={12} className="text-amber-600" />
              {data ? `${number(data.total)} customers match the current filters` : "Querying book…"}
            </span>
            {data && (
              <span className="text-[11px] text-slate-400">
                {data.query_ms.toFixed(0)} ms · as of {dateTime(data.generated_at)}
              </span>
            )}
          </>
        }
      />

      {/* Filters */}
      <div className="panel mb-4 p-3.5">
        <div className="flex flex-col gap-2.5 lg:flex-row lg:items-center">
          <div className="relative min-w-0 flex-1">
            <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by name, email, or city…"
              className="field !pl-9"
              aria-label="Search applicants"
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-1.5 text-[11px] text-slate-500">
              <Filter size={12} />
              <select
                value={decision}
                onChange={(event) => setDecision(event.target.value)}
                className="field !w-auto !py-1.5 !text-[12px]"
                aria-label="Filter by eligibility decision"
              >
                <option value="">All decisions</option>
                <option value="APPROVED">Approved</option>
                <option value="REFERRED">Referred</option>
                <option value="DECLINED">Declined</option>
              </select>
            </label>
            <label className="flex items-center gap-1.5 text-[11px] text-slate-500">
              <SlidersHorizontal size={12} />
              <select
                value={sort}
                onChange={(event) => setSort(event.target.value as SortField)}
                className="field !w-auto !py-1.5 !text-[12px]"
                aria-label="Sort applications"
              >
                {SORT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => setDiscrepancyOnly((value) => !value)}
              aria-pressed={discrepancyOnly}
              className={cn(
                "inline-flex items-center gap-2 rounded-xl border px-3 py-1.5 text-[12px] font-medium transition",
                discrepancyOnly
                  ? "border-amber-300 bg-amber-50 text-amber-800"
                  : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50",
              )}
            >
              <span
                className={cn(
                  "relative h-3.5 w-6 rounded-full transition",
                  discrepancyOnly ? "bg-amber-500" : "bg-slate-300",
                )}
              >
                <span
                  className={cn(
                    "absolute top-0.5 h-2.5 w-2.5 rounded-full bg-white transition-all",
                    discrepancyOnly ? "left-3" : "left-0.5",
                  )}
                />
              </span>
              Conflicts only
            </button>
            {activeFilters && (
              <button
                type="button"
                className="btn-ghost !px-2.5 !py-1.5 text-[11px]"
                onClick={() => {
                  setSearch("");
                  setDecision("");
                  setDiscrepancyOnly(false);
                }}
              >
                <X size={12} /> Clear
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_440px]">
        {/* Master list */}
        <Card className="overflow-hidden">
          {error ? (
            <div className="p-4">
              <ErrorPanel message={error} onRetry={refetch} />
            </div>
          ) : loading && !data ? (
            <div className="space-y-3 p-5">
              {Array.from({ length: 8 }).map((_, index) => (
                <Skeleton key={index} className="h-9 w-full" />
              ))}
            </div>
          ) : !data || data.items.length === 0 ? (
            <EmptyState
              title="No applicants match these filters"
              description="Try broadening the search, clearing the decision filter, or disabling conflicts-only mode."
              action={
                activeFilters ? (
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={() => {
                      setSearch("");
                      setDecision("");
                      setDiscrepancyOnly(false);
                    }}
                  >
                    Reset filters
                  </button>
                ) : undefined
              }
            />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] border-collapse text-left">
                  <thead>
                    <tr className="table-head">
                      <th className="px-4 py-2.5 font-semibold">Applicant</th>
                      <th className="px-2.5 py-2.5 font-semibold">Eligibility</th>
                      <th className="px-2.5 py-2.5 text-right font-semibold">Requested</th>
                      <th className="px-2.5 py-2.5 text-right font-semibold">Score</th>
                      <th className="px-2.5 py-2.5 text-right font-semibold">Variance</th>
                      <th className="px-2.5 py-2.5 font-semibold">Recon</th>
                      <th className="px-3 py-2.5" />
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((row) => (
                      <AuditRow
                        key={row.customer_id}
                        row={row}
                        active={row.customer_id === selected}
                        onSelect={() => setSelected(row.customer_id)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-4 py-3">
                <p className="text-[10.5px] text-slate-500">
                  Page {data.page} of {data.total_pages} · {number(data.total)} customers · {data.query_ms.toFixed(0)} ms
                </p>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    className="btn-ghost !px-2 !py-1.5"
                    onClick={() => setPage((value) => Math.max(1, value - 1))}
                    disabled={page <= 1 || loading}
                    aria-label="Previous page"
                  >
                    <ChevronLeft size={14} />
                  </button>
                  <span className="px-2 text-[11px] tabular-nums text-slate-500">
                    {page} / {totalPages}
                  </span>
                  <button
                    type="button"
                    className="btn-ghost !px-2 !py-1.5"
                    onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
                    disabled={page >= totalPages || loading}
                    aria-label="Next page"
                  >
                    <ChevronRight size={14} />
                  </button>
                </div>
              </div>
            </>
          )}
        </Card>

        {/* Desktop detail pane */}
        <aside className="sticky top-6 hidden max-h-[calc(100vh-3rem)] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-card xl:block">
          {selected ? (
            <DetailPanel customerId={selected} onClose={() => setSelected(null)} />
          ) : (
            <div className="flex h-[420px] flex-col items-center justify-center px-8 text-center">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
                <FileSearch size={20} />
              </span>
              <p className="mt-3 text-sm font-medium text-slate-700">Select an applicant</p>
              <p className="mt-1 max-w-[260px] text-[12px] leading-5 text-slate-500">
                Inspect facility-level ledger conflicts, factor-level score contributions, and the
                full reconciliation trail.
              </p>
              <div className="mt-4 flex items-center gap-1.5 text-[10.5px] text-slate-400">
                <Gauge size={12} /> {data ? `${number(data.total)} candidates in view` : "Loading book…"}
              </div>
            </div>
          )}
        </aside>
      </div>

      {/* Mobile drawer */}
      {selected && (
        <div className="fixed inset-0 z-40 xl:hidden">
          <button
            type="button"
            aria-label="Close detail overlay"
            className="absolute inset-0 bg-navy-950/40 backdrop-blur-sm"
            onClick={() => setSelected(null)}
          />
          <div className="absolute inset-y-0 right-0 w-full max-w-md overflow-hidden bg-white shadow-2xl">
            <DetailPanel customerId={selected} onClose={() => setSelected(null)} />
          </div>
        </div>
      )}
    </>
  );
}

function AuditRow({
  row,
  active,
  onSelect,
}: {
  row: ApplicationSummary;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <tr
      className={cn(
        "cursor-pointer border-t border-slate-100 transition-colors",
        active ? "bg-brand-50/70" : "hover:bg-slate-50/70",
      )}
      onClick={onSelect}
    >
      <td className="px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-[10px] font-semibold",
              active ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-500",
            )}
          >
            {row.first_name.charAt(0)}
            {row.last_name.charAt(0)}
          </span>
          <div className="min-w-0">
            <p className="truncate text-[12px] font-medium text-slate-800">
              {row.first_name} {row.last_name}
            </p>
            <p className="truncate text-[10px] text-slate-500">
              {row.latest_product_type.replaceAll("_", " ").toLowerCase()} · {row.city}
            </p>
          </div>
        </div>
      </td>
      <td className="px-2.5 py-2.5">
        <DecisionBadge decision={row.eligibility_decision} />
      </td>
      <td className="px-2.5 py-2.5 text-right text-[11.5px] tabular-nums text-slate-600">
        {compactCurrency(row.latest_requested_amount)}
      </td>
      <td className="px-2.5 py-2.5 text-right">
        <span className="text-[12px] font-semibold tabular-nums text-slate-800">
          {row.eligibility_score.toFixed(0)}
        </span>
        <span className="block text-[9.5px] text-slate-400">grade {row.recomputed_grade}</span>
      </td>
      <td className="px-2.5 py-2.5 text-right">
        <span
          className={cn(
            "text-[11.5px] font-semibold tabular-nums",
            row.debt_variance > 0 ? "text-rose-600" : "text-slate-400",
          )}
        >
          {row.debt_variance > 0 ? `+${compactCurrency(row.debt_variance)}` : "—"}
        </span>
        <span className="block text-[9.5px] text-slate-400">{pct(row.variance_ratio)}</span>
      </td>
      <td className="px-2.5 py-2.5">
        <ReconciliationBadge status={row.reconciliation_status} compact />
      </td>
      <td className="px-3 py-2.5 text-right">
        <ArrowUpRight size={13} className={cn("inline", active ? "text-brand-600" : "text-slate-300")} />
      </td>
    </tr>
  );
}

export default function AuditPage() {
  return (
    <Suspense
      fallback={
        <div className="panel p-6">
          <Skeleton className="h-5 w-52" />
          <Skeleton className="mt-3 h-3 w-80" />
        </div>
      }
    >
      <AuditWorkspace />
    </Suspense>
  );
}
