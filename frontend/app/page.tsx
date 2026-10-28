"use client";

import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  Building2,
  CircleAlert,
  Cpu,
  DatabaseZap,
  Gauge,
  Layers3,
  Percent,
  RefreshCw,
  ShieldAlert,
  Users,
  Wallet,
} from "lucide-react";

import { api } from "@/lib/api";
import { cn, compactCurrency, currency, dateTime, number, pct } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { OverviewResponse, UdfScoringResponse } from "@/lib/types";
import { DecisionMixChart, DenialDriversChart, ExposureBySystemChart, RejectionVelocityChart, SYSTEM_COLORS } from "@/components/charts";
import {
  Badge,
  Card,
  DecisionBadge,
  ErrorPanel,
  LoadingPanel,
  PageHeader,
  ReconciliationBadge,
  SectionHeading,
  Skeleton,
  StatCard,
} from "@/components/ui";

const RECON_TONE = {
  RECONCILED: "bg-emerald-500",
  MINOR_VARIANCE: "bg-amber-500",
  MISMATCH: "bg-rose-500",
} as const;

export default function OverviewPage() {
  const { data, error, loading, refetch } = useApi<OverviewResponse>("overview", api.overview);
  const { data: udf, refetch: refetchUdf } = useApi<UdfScoringResponse>(
    "udf-scoring",
    api.udfScoring,
  );

  if (loading && !data) {
    return (
      <>
        <PageHeader
          eyebrow="Portfolio intelligence"
          title="Risk & Exposure Overview"
          description="A live, reconciled view of credit risk, cross-ledger exposure, and decision outcomes across the portfolio."
        />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {Array.from({ length: 5 }).map((_, index) => (
            <div key={index} className="panel p-5">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="mt-4 h-7 w-28" />
              <Skeleton className="mt-3 h-3 w-32" />
            </div>
          ))}
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-12">
          <div className="lg:col-span-7">
            <LoadingPanel label="Aggregating three exposure ledgers in Exasol…" rows={4} />
          </div>
          <div className="lg:col-span-5">
            <LoadingPanel label="Resolving decision mix…" rows={4} />
          </div>
        </div>
      </>
    );
  }

  if (error && !data) {
    return (
      <>
        <PageHeader
          eyebrow="Portfolio intelligence"
          title="Risk & Exposure Overview"
          description="A live, reconciled view of credit risk, cross-ledger exposure, and decision outcomes across the portfolio."
        />
        <ErrorPanel
          title="The portfolio view could not be loaded"
          message={error}
          onRetry={refetch}
        />
        <div className="panel mt-4 p-5">
          <p className="eyebrow">Bring the stack online</p>
          <ol className="mt-3 grid gap-2 text-[12.5px] leading-6 text-slate-600 sm:grid-cols-3">
            <li className="rounded-lg bg-slate-50 px-3 py-2">
              <span className="font-mono text-[11px] text-brand-700">exakit start</span>
              <span className="mt-1 block text-[11px] text-slate-500">Start Exasol Personal.</span>
            </li>
            <li className="rounded-lg bg-slate-50 px-3 py-2">
              <span className="font-mono text-[11px] text-brand-700">python seed_data.py --if-empty</span>
              <span className="mt-1 block text-[11px] text-slate-500">Generate the synthetic book.</span>
            </li>
            <li className="rounded-lg bg-slate-50 px-3 py-2">
              <span className="font-mono text-[11px] text-brand-700">uvicorn app.main:app</span>
              <span className="mt-1 block text-[11px] text-slate-500">Serve live analytical APIs.</span>
            </li>
          </ol>
        </div>
      </>
    );
  }

  if (!data) return null;

  const portfolio = data.portfolio;
  const doubleCountShare =
    portfolio.reported_exposure > 0
      ? portfolio.double_counted_exposure / portfolio.reported_exposure
      : 0;
  const reconTotal =
    portfolio.reconciled + portfolio.minor_variances + portfolio.mismatches || 1;

  return (
    <div className="animate-fade-up">
      <PageHeader
        eyebrow="Portfolio intelligence"
        title="Risk & Exposure Overview"
        description="A live, reconciled view of credit risk, cross-ledger exposure, and decision outcomes. Every number is computed by Exasol at request time."
        actions={
          <>
            <button
              type="button"
              className="btn-ghost"
              onClick={() => {
                refetch();
                refetchUdf();
              }}
              disabled={loading}
            >
              <RefreshCw size={14} className={cn(loading && "animate-spin")} />
              Refresh
            </button>
            <Link href="/audit" className="btn-dark">
              Open audit workspace
              <ArrowRight size={14} />
            </Link>
          </>
        }
        meta={
          <>
            <span className="inline-flex items-center gap-1.5 text-[11px] text-slate-500">
              <DatabaseZap size={12} className="text-brand-600" />
              Live Exasol query · {data.query_ms.toFixed(0)} ms
            </span>
            <span className="text-[11px] text-slate-400">As of {dateTime(data.generated_at)}</span>
            <Badge tone="brand" dot>
              {number(portfolio.customers)} customers
            </Badge>
          </>
        }
      />

      {/* Headline insight ------------------------------------------------- */}
      <section className="relative mb-4 overflow-hidden rounded-xl border border-slate-200 bg-white p-5 shadow-card sm:p-6">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-y-0 left-0 w-1 bg-gradient-to-b from-brand-500 to-brand-700"
        />
        <div className="grid gap-6 pl-4 lg:grid-cols-[1.55fr_1fr] lg:items-center lg:pl-5">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-brand-600/15 bg-brand-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-brand-800">
              <ShieldAlert size={12} />
              Cross-ledger reconciliation
            </div>
            <h2 className="mt-3 text-balance text-xl font-semibold leading-snug tracking-tight text-ink sm:text-[22px]">
              Reported exposure overstates the book by{" "}
              <span className="text-brand-700">{compactCurrency(portfolio.double_counted_exposure)}</span>.
            </h2>
            <p className="mt-2 max-w-xl text-[12.5px] leading-6 text-slate-500">
              Core banking, card management, and micro-lending each report the same facilities
              independently. Exasol reconciles facility-level balances across all three, then
              re-scores every applicant on the deduplicated exposure — not the inflated ledger sum.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Link href="/audit?discrepancy=1" className="btn-primary">
                Inspect {number(portfolio.mismatches)} mismatches
                <ArrowUpRight size={14} />
              </Link>
              <Link href="/studio" className="btn-ghost">
                Draft adverse-action notices
              </Link>
            </div>
          </div>
          <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-slate-200 bg-slate-200">
            <div className="bg-white p-4">
              <dt className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Reported</dt>
              <dd className="mt-1 text-lg font-semibold tabular-nums text-ink">
                {compactCurrency(portfolio.reported_exposure)}
              </dd>
            </div>
            <div className="bg-white p-4">
              <dt className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Reconciled</dt>
              <dd className="mt-1 text-lg font-semibold tabular-nums text-brand-700">
                {compactCurrency(portfolio.reconciled_exposure)}
              </dd>
            </div>
            <div className="bg-white p-4">
              <dt className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Overstatement</dt>
              <dd className="mt-1 text-lg font-semibold tabular-nums text-amber-600">
                {pct(doubleCountShare)}
              </dd>
            </div>
            <div className="bg-white p-4">
              <dt className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Decline rate</dt>
              <dd className="mt-1 text-lg font-semibold tabular-nums text-ink">{pct(portfolio.decline_rate)}</dd>
            </div>
          </dl>
        </div>
      </section>

      {/* KPI strip -------------------------------------------------------- */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard
          label="Applications"
          value={number(portfolio.total_applications)}
          helper={`${number(portfolio.approved)} approved · ${number(portfolio.referred)} referred`}
          icon={Layers3}
          tone="info"
        />
        <StatCard
          label="Approval rate"
          value={pct(portfolio.approval_rate)}
          helper={`Avg score ${portfolio.average_eligibility_score.toFixed(0)} / 900`}
          icon={Gauge}
          tone="success"
          trend={{ value: `${number(portfolio.approved)} approvals`, direction: "up" }}
        />
        <StatCard
          label="Decline rate"
          value={pct(portfolio.decline_rate)}
          helper={`${number(portfolio.declined)} declined applications`}
          icon={Percent}
          tone="danger"
        />
        <StatCard
          label="Exposure mismatch"
          value={pct(portfolio.mismatch_rate)}
          helper={`${number(portfolio.mismatches)} of ${number(portfolio.customers)} customers`}
          icon={ShieldAlert}
          tone="warning"
        />
        <StatCard
          label="Double-counted"
          value={compactCurrency(portfolio.double_counted_exposure)}
          helper={`${pct(doubleCountShare)} of reported exposure`}
          icon={Wallet}
          tone="brand"
        />
      </div>

      {/* Exasol-native scoring ------------------------------------------- */}
      <Card className="panel-pad mt-4">
        <div className="grid gap-4 lg:grid-cols-[1.45fr_1fr] lg:items-center">
          <div>
            <SectionHeading
              icon={Cpu}
              title="In-database scoring with an Exasol Python UDF"
              description="The same risk model runs as a Python SET UDF inside Exasol, scoring the entire applicant book in one pass without moving factor rows to the API tier."
              action={<Badge tone="brand">{udf?.engine ?? "Exasol UDF"}</Badge>}
            />
            <p className="mt-2.5 max-w-2xl text-[12px] leading-6 text-slate-500">
              {udf ? (
                <>
                  <span className="font-mono text-[11px] text-slate-600">{udf.script}</span> scored{" "}
                  {number(udf.customers_scored)} applicants in{" "}
                  <span className="font-semibold text-ink">{udf.elapsed_ms.toFixed(0)} ms</span>. Results
                  agree with the analytical view on {pct(udf.agreement_rate, 2)} of scores and{" "}
                  {pct(udf.decision_matches / Math.max(1, udf.customers_scored), 2)} of decisions;
                  the largest rounding difference is {udf.max_abs_difference.toFixed(1)} points.
                </>
              ) : (
                "Run the seed job to install SCORE_PORTFOLIO and compare its output with the analytical view."
              )}
            </p>
          </div>
          <dl className="grid grid-cols-3 gap-px overflow-hidden rounded-xl border border-slate-200 bg-slate-200">
            <div className="bg-slate-50 p-3.5">
              <dt className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Scored</dt>
              <dd className="mt-1 text-lg font-semibold tabular-nums text-ink">
                {udf ? number(udf.customers_scored) : "—"}
              </dd>
            </div>
            <div className="bg-slate-50 p-3.5">
              <dt className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Agreement</dt>
              <dd className="mt-1 text-lg font-semibold tabular-nums text-brand-700">
                {udf ? pct(udf.agreement_rate, 2) : "—"}
              </dd>
            </div>
            <div className="bg-slate-50 p-3.5">
              <dt className="text-[10px] uppercase tracking-[0.12em] text-slate-500">UDF time</dt>
              <dd className="mt-1 text-lg font-semibold tabular-nums text-ink">
                {udf ? `${udf.elapsed_ms.toFixed(0)} ms` : "—"}
              </dd>
            </div>
          </dl>
        </div>
      </Card>

      {/* Charts ----------------------------------------------------------- */}
      <div className="mt-4 grid gap-4 lg:grid-cols-12">
        <Card className="panel-pad lg:col-span-7">
          <SectionHeading
            icon={Building2}
            title="Exposure by source system"
            description="Gross outstanding balance reported by each ledger before reconciliation."
            action={<Badge tone="neutral">3 ledgers</Badge>}
          />
          <div className="mt-3">
            <ExposureBySystemChart data={data.exposure_by_system} />
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-slate-100 pt-3.5">
            {data.exposure_by_system.map((system) => (
              <div key={system.system} className="flex items-center gap-2">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{
                    background: SYSTEM_COLORS[system.system] ?? "#64748b",
                  }}
                />
                <span className="text-[11px] text-slate-600">
                  {system.label} · {compactCurrency(system.exposure)}
                </span>
              </div>
            ))}
          </div>
        </Card>

        <Card className="panel-pad lg:col-span-5">
          <SectionHeading
            icon={Gauge}
            title="Decision mix"
            description="Latest decision per customer across the active book."
          />
          <div className="mt-3">
            <DecisionMixChart data={data.decision_mix} />
          </div>
          <div className="mt-2 grid grid-cols-3 gap-2 border-t border-slate-100 pt-3.5">
            {data.reconciliation_mix.map((slice) => (
              <div key={slice.status} className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <span
                    className={cn("h-1.5 w-1.5 rounded-full", RECON_TONE[slice.status])}
                  />
                  <span className="truncate text-[10px] uppercase tracking-[0.08em] text-slate-500">
                    {slice.status === "MINOR_VARIANCE" ? "Minor" : slice.status.toLowerCase()}
                  </span>
                </div>
                <p className="mt-1 text-sm font-semibold tabular-nums text-ink">
                  {pct(slice.share, 0)}
                </p>
                <p className="text-[10px] text-slate-400">{number(slice.count)} customers</p>
              </div>
            ))}
          </div>
        </Card>

        <Card className="panel-pad lg:col-span-7">
          <SectionHeading
            icon={Layers3}
            title="Application velocity & decline rate"
            description="Monthly application volume against the realized decline rate."
            action={<Badge tone="neutral">Trailing 12 months</Badge>}
          />
          <div className="mt-3">
            <RejectionVelocityChart data={data.rejection_velocity} />
          </div>
        </Card>

        <Card className="panel-pad lg:col-span-5">
          <SectionHeading
            icon={CircleAlert}
            title="Adverse-action drivers"
            description="Most frequent factors behind declined decisions."
            action={
              <Link href="/studio" className="text-[11px] font-medium text-brand-700 hover:text-brand-800">
                Studio →
              </Link>
            }
          />
          <div className="mt-3">
            <DenialDriversChart data={data.denial_drivers} />
          </div>
        </Card>
      </div>

      {/* Discrepancy table ------------------------------------------------ */}
      <Card className="mt-4 overflow-hidden">
        <div className="flex flex-wrap items-end justify-between gap-3 p-5 pb-4">
          <SectionHeading
            icon={ShieldAlert}
            title="Largest unreconciled exposures"
            description="Facilities whose balances disagree across source systems, ranked by variance."
          />
          <Link href="/audit" className="btn-ghost !py-1.5 text-[12px]">
            View all applications
            <ArrowRight size={13} />
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] border-collapse text-left">
            <thead>
              <tr className="table-head">
                <th className="px-5 py-2.5 font-semibold">Applicant</th>
                <th className="px-3 py-2.5 font-semibold">Decision</th>
                <th className="px-3 py-2.5 text-right font-semibold">Reported</th>
                <th className="px-3 py-2.5 text-right font-semibold">Reconciled</th>
                <th className="px-3 py-2.5 text-right font-semibold">Variance</th>
                <th className="px-3 py-2.5 font-semibold">Status</th>
                <th className="px-5 py-2.5 text-right font-semibold">Audit</th>
              </tr>
            </thead>
            <tbody>
              {data.top_discrepancies.map((row) => (
                <tr key={row.customer_id} className="table-row">
                  <td className="px-5 py-3">
                    <p className="text-[12.5px] font-medium text-ink">
                      {row.first_name} {row.last_name}
                    </p>
                    <p className="text-[10.5px] text-slate-500">
                      {row.city}, {row.state} · {row.segment.toLowerCase()}
                    </p>
                  </td>
                  <td className="px-3 py-3">
                    <DecisionBadge decision={row.latest_decision} />
                  </td>
                  <td className="px-3 py-3 text-right text-[12px] tabular-nums text-slate-600">
                    {currency(row.gross_exposure)}
                  </td>
                  <td className="px-3 py-3 text-right text-[12px] tabular-nums text-slate-600">
                    {currency(row.reconciled_exposure)}
                  </td>
                  <td className="px-3 py-3 text-right">
                    <span className="text-[12px] font-semibold tabular-nums text-rose-600">
                      +{currency(row.debt_variance)}
                    </span>
                    <span className="block text-[10px] text-slate-400">
                      {pct(row.variance_ratio)}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    <ReconciliationBadge status={row.reconciliation_status} compact />
                  </td>
                  <td className="px-5 py-3 text-right">
                    <Link
                      href={`/audit?customer=${row.customer_id}`}
                      className="inline-flex items-center gap-1 text-[11.5px] font-medium text-brand-700 hover:text-brand-800"
                    >
                      Inspect <ArrowUpRight size={12} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 px-5 py-3 text-[10.5px] text-slate-400">
          <span className="inline-flex items-center gap-1.5">
            <Users size={11} />
            {number(portfolio.mismatches)} mismatched and {number(portfolio.minor_variances)} minor-variance
            customers detected in this snapshot
          </span>
          <span>{number(reconTotal)} customers audited</span>
        </div>
      </Card>
    </div>
  );
}
