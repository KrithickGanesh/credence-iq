"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDownRight,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BadgeCheck,
  Check,
  ChevronDown,
  ClipboardCheck,
  Copy,
  Database,
  Download,
  FileText,
  Gauge,
  Info,
  Landmark,
  Loader2,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  UserRound,
  Wand2,
  Wallet,
} from "lucide-react";

import { api } from "@/lib/api";
import { cn, currency, dateTime, decisionTone, number, pct, scoreBg, shortDate, titleCase } from "@/lib/format";
import { useApi, useDebouncedValue } from "@/lib/hooks";
import type {
  AdverseActionResponse,
  ApplicationsResponse,
  ApplicationSummary,
  Decision,
  SimulationRequest,
  SimulationResponse,
} from "@/lib/types";
import {
  Badge,
  Card,
  DecisionBadge,
  EmptyState,
  ErrorPanel,
  InfoRow,
  PageHeader,
  SectionHeading,
  Skeleton,
} from "@/components/ui";

const DEFAULTS: SimulationRequest = {
  revolving_paydown: 0,
  resolve_exposure_mismatch: false,
  income_increase_annual: 0,
  additional_hard_inquiries: 0,
};

const DECISION_BANNER: Record<Decision, { tone: string; label: string }> = {
  APPROVED: {
    tone: "border-emerald-200 bg-emerald-50/70 text-emerald-900",
    label: "Approved — no adverse-action notice is required for this file.",
  },
  REFERRED: {
    tone: "border-amber-200 bg-amber-50/70 text-amber-900",
    label: "Referred — a notice is available and can be regenerated as the scenario changes.",
  },
  DECLINED: {
    tone: "border-rose-200 bg-rose-50/70 text-rose-900",
    label: "Declined — this file requires a compliant adverse-action notice.",
  },
};

function useSimulation(customerId: number | null, scenario: SimulationRequest) {
  const [data, setData] = useState<SimulationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!customerId) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    const timer = setTimeout(() => {
      api
        .simulate(customerId, scenario)
        .then((result) => {
          if (!cancelled) setData(result);
        })
        .catch((reason: unknown) => {
          if (!cancelled) setError(reason instanceof Error ? reason.message : "Simulation failed");
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [customerId, scenario]);

  return { data, error, loading };
}

function ApplicantPicker({
  selected,
  onSelect,
}: {
  selected: number | null;
  onSelect: (customerId: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"ALL" | "REFERRED" | "DECLINED">("ALL");
  const debounced = useDebouncedValue(query, 300);

  const { data, loading } = useApi<ApplicationsResponse>(
    `studio-picker-${debounced}-${filter}`,
    () =>
      api.applications({
        page_size: 8,
        search: debounced || undefined,
        decision: filter === "ALL" ? undefined : filter,
        sort: "score",
        direction: "desc",
        discrepancy_only: filter === "ALL" ? undefined : false,
      }),
    open,
  );

  return (
    <div
      className="relative"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false);
      }}
    >
      <div className="flex items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            placeholder="Find an applicant by name, email, or city…"
            className="field !pl-9 !pr-9"
            aria-label="Find an applicant"
          />
          <ChevronDown
            size={14}
            className={cn(
              "pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 transition",
              open && "rotate-180",
            )}
          />
        </div>
        {selected && (
          <Link
            href={`/audit?customer=${selected}`}
            className="btn-ghost hidden shrink-0 sm:inline-flex"
            title="Open this applicant in the audit workspace"
          >
            <ClipboardCheck size={14} />
            Audit
          </Link>
        )}
      </div>

      {open && (
        <div className="absolute left-0 right-0 top-[calc(100%+6px)] z-40 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lift">
          <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-3 py-2">
            <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
              {loading ? "Searching book…" : `${data?.total ?? 0} files`}
            </span>
            <div className="flex gap-1">
              {(["ALL", "REFERRED", "DECLINED"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setFilter(value)}
                  className={cn(
                    "rounded-md px-2 py-1 text-[10px] font-medium transition",
                    filter === value
                      ? "bg-navy-900 text-white"
                      : "text-slate-500 hover:bg-slate-100",
                  )}
                >
                  {value === "ALL" ? "All" : titleCase(value)}
                </button>
              ))}
            </div>
          </div>
          <div className="max-h-[320px] overflow-y-auto">
            {data?.items.length ? (
              data.items.map((row) => (
                <button
                  key={row.customer_id}
                  type="button"
                  onClick={() => {
                    onSelect(row.customer_id);
                    setOpen(false);
                    setQuery("");
                  }}
                  className={cn(
                    "flex w-full items-center gap-3 border-b border-slate-50 px-3 py-2.5 text-left transition last:border-0",
                    row.customer_id === selected ? "bg-brand-50" : "hover:bg-slate-50",
                  )}
                >
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-[10px] font-semibold text-slate-500">
                    {row.first_name.charAt(0)}
                    {row.last_name.charAt(0)}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[12px] font-medium text-slate-800">
                      {row.first_name} {row.last_name}
                      <span className="ml-1 font-normal text-slate-400">#{row.customer_id}</span>
                    </span>
                    <span className="block truncate text-[10px] text-slate-500">
                      {row.city}, {row.state} · {currency(row.latest_requested_amount)} · score{" "}
                      {row.eligibility_score.toFixed(0)}
                    </span>
                  </span>
                  <DecisionBadge decision={row.latest_decision} />
                </button>
              ))
            ) : (
              <p className="px-3 py-6 text-center text-[11.5px] text-slate-500">
                {loading ? "Querying Exasol…" : "No applicants match this search."}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ScenarioSlider({
  label,
  description,
  value,
  max,
  step,
  display,
  onChange,
  accent = "brand",
  unit = "currency",
  disabled = false,
}: {
  label: string;
  description: string;
  value: number;
  max: number;
  step: number;
  display: string;
  onChange: (value: number) => void;
  accent?: "brand" | "sky" | "rose";
  unit?: "currency" | "inquiries";
  disabled?: boolean;
}) {
  const fill = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className={cn("rounded-xl border border-slate-100 bg-white p-3", disabled && "opacity-60")}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[12px] font-medium text-slate-800">{label}</p>
          <p className="mt-0.5 text-[10.5px] leading-4 text-slate-500">{description}</p>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-md px-2 py-1 text-[11px] font-semibold tabular-nums",
            accent === "brand"
              ? "bg-brand-50 text-brand-700"
              : accent === "sky"
                ? "bg-sky-50 text-sky-700"
                : "bg-rose-50 text-rose-700",
          )}
        >
          {display}
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={max}
        step={step}
        value={Math.min(value, max)}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
        className="mt-3"
        style={{ "--fill": `${fill}%` } as React.CSSProperties}
        aria-label={label}
      />
      <div className="mt-1 flex justify-between text-[9.5px] text-slate-400">
        <span>{currency(0)}</span>
        <span>{unit === "inquiries" ? `${number(max)} inquiries` : currency(max)}</span>
      </div>
    </div>
  );
}

function ScoreTransition({ sim }: { sim: SimulationResponse }) {
  const improved = sim.score_delta > 0;
  const flat = sim.score_delta === 0;
  return (
    <div className="rounded-xl border border-slate-200 bg-gradient-to-br from-white to-slate-50 p-3.5">
      <div className="flex items-center justify-between">
        <p className="eyebrow">Projected score</p>
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] font-semibold",
            flat
              ? "bg-slate-100 text-slate-600"
              : improved
                ? "bg-emerald-50 text-emerald-700"
                : "bg-rose-50 text-rose-700",
          )}
        >
          {flat ? "No change" : improved ? <TrendingUp size={11} /> : <ArrowDownRight size={11} />}
          {!flat && (sim.score_delta > 0 ? "+" : "")}
          {!flat && sim.score_delta.toFixed(1)}
        </span>
      </div>
      <div className="mt-2 flex items-end gap-2">
        <span className="text-sm font-medium tabular-nums text-slate-400 line-through decoration-slate-300">
          {sim.current.score.toFixed(0)}
        </span>
        <ArrowRight size={14} className="mb-1 text-slate-400" />
        <span className="text-3xl font-semibold leading-none tracking-tight text-ink tabular-nums">
          {sim.simulated.score.toFixed(0)}
        </span>
        <span className="mb-0.5 text-[10.5px] text-slate-400">/ 900 · grade {sim.simulated.grade}</span>
      </div>
      <div className="mt-2.5 flex items-center justify-between gap-2">
        <DecisionBadge decision={sim.current.decision} />
        <ArrowRight size={13} className="text-slate-300" />
        <DecisionBadge decision={sim.simulated.decision} />
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 border-t border-slate-100 pt-2.5">
        <div>
          <p className="text-[9.5px] uppercase tracking-[0.08em] text-slate-400">Utilization</p>
          <p className="text-[11.5px] font-semibold tabular-nums text-slate-700">
            {pct(sim.simulated.utilization_ratio)}
          </p>
        </div>
        <div>
          <p className="text-[9.5px] uppercase tracking-[0.08em] text-slate-400">DTI</p>
          <p className="text-[11.5px] font-semibold tabular-nums text-slate-700">
            {pct(sim.simulated.dti_ratio)}
          </p>
        </div>
        <div>
          <p className="text-[9.5px] uppercase tracking-[0.08em] text-slate-400">Variance</p>
          <p className="text-[11.5px] font-semibold tabular-nums text-slate-700">
            {pct(sim.simulated.variance_ratio)}
          </p>
        </div>
      </div>
    </div>
  );
}

function LetterBody({ report }: { report: AdverseActionResponse }) {
  const letter = report.compliance_letter;
  return (
    <article className="letter-paper rounded-xl border border-slate-200 bg-white px-5 py-5 font-serif sm:px-7 sm:py-6">
      <header className="flex items-start justify-between gap-3 border-b border-slate-200 pb-4">
        <div>
          <div className="flex items-center gap-2 font-sans">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-navy-900 text-[11px] font-bold text-white">
              CQ
            </span>
            <span className="text-[12px] font-semibold tracking-tight text-navy-900">
              CredenceIQ Finance
            </span>
          </div>
          <p className="mt-1 font-sans text-[9.5px] uppercase tracking-[0.14em] text-slate-400">
            Consumer Credit Division
          </p>
        </div>
        <div className="text-right font-sans">
          <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-400">
            Confidential
          </p>
          <p className="text-[10px] text-slate-500">{shortDate(letter.issued_date)}</p>
        </div>
      </header>

      <div className="mt-3 flex items-center gap-1.5 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1.5 font-sans text-[9.5px] font-medium text-amber-800">
        <span className="rounded bg-amber-200/70 px-1.5 py-0.5 text-[8.5px] font-bold uppercase tracking-wide">
          Draft
        </span>
        Synthetic demo letter. Not legal advice; a compliance officer must review before issue.
      </div>

      <div className="mt-4 space-y-1 font-sans text-[10.5px] leading-5 text-slate-600">
        <p className="text-[9.5px] uppercase tracking-[0.12em] text-slate-400">Recipient</p>
        <p className="font-medium text-slate-800">{letter.recipient}</p>
      </div>

      <h2 className="mt-4 text-[15px] font-semibold tracking-tight text-navy-900">
        {letter.title}
      </h2>

      <div className="mt-2.5 space-y-2.5 text-[11.5px] leading-[1.75] text-slate-700">
        {letter.body.split("\n\n").map((paragraph, index) => (
          <p key={index}>{paragraph}</p>
        ))}
      </div>

      {letter.factor_disclosures.length > 0 && (
        <div className="mt-4">
          <p className="font-sans text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-400">
            Principal reasons for this decision
          </p>
          <ol className="mt-2 space-y-2">
            {letter.factor_disclosures.map((disclosure, index) => (
              <li key={disclosure.factor_code} className="flex gap-2.5">
                <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-navy-900 font-sans text-[9px] font-semibold text-white">
                  {index + 1}
                </span>
                <div>
                  <p className="font-sans text-[11px] font-semibold text-slate-800">
                    {disclosure.factor_name}{" "}
                    <span className="font-mono text-[9px] font-normal text-slate-400">
                      {disclosure.factor_code}
                    </span>
                  </p>
                  <p className="text-[10.5px] leading-5 text-slate-600">{disclosure.finding}</p>
                  <p className="font-sans text-[9.5px] text-slate-400">
                    {disclosure.regulation} · Impact: {disclosure.impact}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}

      <div className="mt-4 border-t border-slate-200 pt-3">
        <p className="font-sans text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-400">
          Your right to appeal
        </p>
        <ul className="mt-1.5 space-y-1 font-sans text-[10.5px] leading-5 text-slate-600">
          {letter.appeal_rights.map((right) => (
            <li key={right} className="flex gap-1.5">
              <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-slate-400" />
              {right}
            </li>
          ))}
        </ul>
        <p className="mt-3 font-sans text-[10.5px] leading-5 text-slate-600">
          Questions about this notice: <span className="font-medium text-slate-800">{letter.contact}</span>
        </p>
      </div>

      <footer className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 pt-2.5 font-sans text-[9px] text-slate-400">
        <span>Report {report.report_id}</span>
        <span>Generated by CredenceIQ · {report.generation_mode === "llm" ? "AI-assisted" : "deterministic template"}</span>
      </footer>
    </article>
  );
}

function ExplanationPane({ report }: { report: AdverseActionResponse }) {
  const explanation = report.customer_explanation;
  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-brand-200 bg-brand-50/60 p-3.5">
        <div className="flex items-center gap-1.5 text-[9.5px] font-semibold uppercase tracking-[0.13em] text-brand-700">
          <BadgeCheck size={12} />
          Plain-English summary
        </div>
        <h3 className="mt-1.5 text-[14px] font-semibold leading-snug tracking-tight text-brand-950">
          {explanation.headline}
        </h3>
        <p className="mt-1.5 text-[11.5px] leading-5 text-brand-900/80">{explanation.summary}</p>
      </div>

      <div>
        <p className="eyebrow">What this means for you</p>
        <ul className="mt-2 space-y-1.5">
          {explanation.what_this_means.map((line, index) => (
            <li
              key={index}
              className="flex gap-2 rounded-lg border border-slate-100 bg-white p-2.5 text-[11px] leading-5 text-slate-600"
            >
              <Info size={13} className="mt-0.5 shrink-0 text-slate-400" />
              {line}
            </li>
          ))}
        </ul>
      </div>

      <div>
        <p className="eyebrow">Next steps</p>
        <ol className="mt-2 space-y-1.5">
          {explanation.next_steps.map((step, index) => (
            <li key={index} className="flex gap-2.5 text-[11px] leading-5 text-slate-600">
              <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-brand-100 text-[9px] font-semibold text-brand-800">
                {index + 1}
              </span>
              {step}
            </li>
          ))}
        </ol>
      </div>

      <div className="rounded-lg bg-slate-50 p-3">
        <p className="text-[9.5px] leading-4 text-slate-500">{report.disclaimer}</p>
      </div>
    </div>
  );
}

function StudioWorkspace() {
  const params = useSearchParams();
  const initial = Number(params.get("customer") ?? "") || null;
  const [customerId, setCustomerId] = useState<number | null>(initial);
  const [scenario, setScenario] = useState<SimulationRequest>(DEFAULTS);
  const [tone, setTone] = useState<"formal" | "plain">("formal");
  const [letter, setLetter] = useState<AdverseActionResponse | null>(null);
  const [letterError, setLetterError] = useState<string | null>(null);
  const [letterLoading, setLetterLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [pane, setPane] = useState<"letter" | "explanation">("letter");
  const generatedFor = useRef<number | null>(null);

  const suggestions = useApi<ApplicationsResponse>(
    "studio-suggestion",
    () =>
      api.applications({
        page_size: 6,
        eligibility_decision: "DECLINED",
        sort: "score",
        direction: "desc",
      }),
    customerId === null,
  );

  useEffect(() => {
    if (!customerId && suggestions.data?.items.length) {
      setCustomerId(suggestions.data.items[0].customer_id);
    }
  }, [customerId, suggestions.data]);

  useEffect(() => {
    setScenario(DEFAULTS);
    setLetter(null);
    setLetterError(null);
    generatedFor.current = null;
  }, [customerId]);

  const { data: sim, error: simError, loading: simLoading } = useSimulation(customerId, scenario);

  const generate = useCallback(
    async (nextTone: "formal" | "plain") => {
      if (!customerId) return;
      setLetterLoading(true);
      setLetterError(null);
      try {
        const result = await api.adverseAction(customerId, { tone: nextTone });
        setLetter(result);
      } catch (reason) {
        setLetter(null);
        setLetterError(reason instanceof Error ? reason.message : "Disclosure generation failed");
      } finally {
        setLetterLoading(false);
      }
    },
    [customerId],
  );

  useEffect(() => {
    if (!customerId || !sim) return;
    if (sim.current.decision === "APPROVED") return;
    if (generatedFor.current === customerId) return;
    generatedFor.current = customerId;
    void generate(tone);
  }, [customerId, sim, generate, tone]);

  const cardMax = Math.max(
    5000,
    Math.min(100000, Math.ceil((sim?.current.card_exposure ?? 30000) / 1000) * 1000),
  );

  const letterText = useMemo(() => {
    if (!letter) return "";
    const value = letter.compliance_letter;
    return [
      value.title,
      `${value.issued_date} · ${value.recipient}`,
      value.body,
      "",
      "PRINCIPAL REASONS",
      ...value.factor_disclosures.map(
        (disclosure, index) =>
          `${index + 1}. ${disclosure.factor_name} (${disclosure.factor_code}) — ${disclosure.finding} [${disclosure.regulation}]`,
      ),
      "",
      "YOUR RIGHT TO APPEAL",
      ...value.appeal_rights.map((right) => `• ${right}`),
      "",
      `Contact: ${value.contact}`,
      `Report: ${letter.report_id}`,
    ].join("\n");
  }, [letter]);

  const copyLetter = async () => {
    if (!letterText) return;
    try {
      await navigator.clipboard.writeText(letterText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };

  const downloadLetter = () => {
    if (!letter) return;
    const blob = new Blob([letterText], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `adverse-action-${letter.report_id}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const approved = sim?.current.decision === "APPROVED";
  const banner = sim ? DECISION_BANNER[sim.current.decision] : null;

  return (
    <>
      <PageHeader
        eyebrow="Adverse action & scenario studio"
        title="Turn declines into defensible decisions"
        description="Re-score a file live in Exasol, explore the path back to approval, and generate regulator-ready disclosures in plain English."
        actions={
          <>
            <Link href="/audit" className="btn-ghost">
              <ArrowLeft size={14} />
              Audit workspace
            </Link>
            <button
              type="button"
              className="btn-primary"
              onClick={() => generate(tone)}
              disabled={!customerId || letterLoading || approved}
            >
              {letterLoading ? <Loader2 size={14} className="animate-spin" /> : <Wand2 size={14} />}
              {letter ? "Regenerate notice" : "Generate notice"}
            </button>
          </>
        }
        meta={
          sim && (
            <>
              <span className="inline-flex items-center gap-1.5 text-[11px] text-slate-500">
                <Database size={12} className="text-brand-600" />
                Live re-scoring · {sim.query_ms.toFixed(0)} ms
              </span>
              <span className="text-[11px] text-slate-400">
                App {number(sim.application_id)} · re-scored {dateTime(sim.generated_at)}
              </span>
            </>
          )
        }
      />

      {/* Applicant selector */}
      <Card className="mb-4 p-3.5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-navy-900 text-white">
              <UserRound size={15} />
            </span>
            <div className="shrink-0">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                Working file
              </p>
              <p className="text-[12px] font-medium text-slate-800">
                {sim ? sim.applicant_name : customerId ? `Customer #${customerId}` : "Select an applicant"}
              </p>
            </div>
          </div>
          <div className="min-w-0 flex-1">
            <ApplicantPicker
              selected={customerId}
              onSelect={(value) => setCustomerId(value)}
            />
          </div>
          {sim && (
            <div className="flex shrink-0 flex-wrap items-center gap-2">
              <DecisionBadge decision={sim.current.decision} />
              <span className={cn("chip ring-inset", scoreBg(sim.current.score))}>
                Score {sim.current.score.toFixed(0)}
              </span>
              <span className="chip bg-slate-50 text-slate-600 ring-slate-200">
                {currency(sim.current.gross_exposure)} exposure
              </span>
            </div>
          )}
        </div>
        {suggestions.data?.items.length && !customerId ? (
          <div className="mt-2.5 flex flex-wrap items-center gap-1.5 border-t border-slate-100 pt-2.5">
            <span className="text-[10px] text-slate-400">Borderline declines:</span>
            {suggestions.data.items.slice(0, 4).map((row) => (
              <button
                key={row.customer_id}
                type="button"
                onClick={() => setCustomerId(row.customer_id)}
                className="rounded-full border border-slate-200 px-2.5 py-1 text-[10px] text-slate-600 transition hover:border-brand-300 hover:bg-brand-50"
              >
                {row.first_name} {row.last_name.charAt(0)}. · {row.eligibility_score.toFixed(0)}
              </button>
            ))}
          </div>
        ) : null}
      </Card>

      {banner && (
        <div className={cn("mb-4 flex items-start gap-2 rounded-xl border px-3.5 py-2.5 text-[11.5px] leading-5", banner.tone)}>
          <Info size={14} className="mt-0.5 shrink-0" />
          <span>{banner.label}</span>
        </div>
      )}

      {!customerId ? (
        <Card>
          <EmptyState
            title="Choose a file to begin"
            description="Search the book above, or open one of the borderline declined files to explore the path back to approval."
            action={
              suggestions.data?.items[0] ? (
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => setCustomerId(suggestions.data!.items[0].customer_id)}
                >
                  Open {suggestions.data.items[0].first_name}{" "}
                  {suggestions.data.items[0].last_name}
                  <ArrowRight size={14} />
                </button>
              ) : undefined
            }
          />
        </Card>
      ) : simError && !sim ? (
        <ErrorPanel
          title="This file could not be re-scored"
          message={simError}
        />
      ) : !sim ? (
        <div className="grid gap-4 lg:grid-cols-12">
          <Card className="panel-pad lg:col-span-5">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="mt-4 h-24 w-full" />
            <Skeleton className="mt-3 h-16 w-full" />
            <Skeleton className="mt-3 h-16 w-full" />
          </Card>
          <Card className="panel-pad lg:col-span-7">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="mt-4 h-[360px] w-full" />
          </Card>
        </div>
      ) : (
        <div className="grid items-start gap-4 lg:grid-cols-12">
          {/* Scenario lab */}
          <div className="space-y-4 lg:col-span-5">
            <Card className="panel-pad">
              <SectionHeading
                icon={Gauge}
                title="Scenario laboratory"
                description="Every slider re-runs the scoring model against live Exasol balances."
                action={
                  simLoading ? (
                    <span className="inline-flex items-center gap-1 text-[10px] text-brand-700">
                      <Loader2 size={11} className="animate-spin" /> re-scoring
                    </span>
                  ) : (
                    <Badge tone="success" dot>
                      synced
                    </Badge>
                  )
                }
              />
              <div className="mt-3">
                <ScoreTransition sim={sim} />
              </div>

              <div className="mt-3 space-y-2.5">
                <ScenarioSlider
                  label="Revolving paydown"
                  description="Apply cash to the card ledger to cut utilization and gross exposure."
                  value={scenario.revolving_paydown}
                  max={cardMax}
                  step={500}
                  display={currency(scenario.revolving_paydown)}
                  onChange={(value) =>
                    setScenario((current) => ({ ...current, revolving_paydown: value }))
                  }
                />
                <ScenarioSlider
                  label="Additional verified income"
                  description="Document annual income to reduce the debt-to-income ratio."
                  value={scenario.income_increase_annual}
                  max={2_500_000}
                  step={50_000}
                  display={currency(scenario.income_increase_annual)}
                  accent="sky"
                  onChange={(value) =>
                    setScenario((current) => ({ ...current, income_increase_annual: value }))
                  }
                />
                <ScenarioSlider
                  label="New hard inquiries"
                  description="Stress-test how new credit-seeking behaviour erodes the score."
                  value={scenario.additional_hard_inquiries}
                  max={6}
                  step={1}
                  display={`${number(scenario.additional_hard_inquiries)} inquiries`}
                  accent="rose"
                  unit="inquiries"
                  onChange={(value) =>
                    setScenario((current) => ({ ...current, additional_hard_inquiries: value }))
                  }
                />

                <button
                  type="button"
                  onClick={() =>
                    setScenario((current) => ({
                      ...current,
                      resolve_exposure_mismatch: !current.resolve_exposure_mismatch,
                    }))
                  }
                  aria-pressed={scenario.resolve_exposure_mismatch}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 rounded-xl border p-3 text-left transition",
                    scenario.resolve_exposure_mismatch
                      ? "border-brand-300 bg-brand-50/70"
                      : "border-slate-100 bg-white hover:border-slate-200",
                  )}
                >
                  <span>
                    <span className="block text-[12px] font-medium text-slate-800">
                      Resolve cross-ledger mismatch
                    </span>
                    <span className="mt-0.5 block text-[10.5px] leading-4 text-slate-500">
                      Deduplicate conflicting facility balances before scoring.
                    </span>
                  </span>
                  <span
                    className={cn(
                      "relative h-5 w-9 shrink-0 rounded-full transition",
                      scenario.resolve_exposure_mismatch ? "bg-brand-600" : "bg-slate-300",
                    )}
                  >
                    <span
                      className={cn(
                        "absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all",
                        scenario.resolve_exposure_mismatch ? "left-[18px]" : "left-0.5",
                      )}
                    />
                  </span>
                </button>
              </div>

              <div className="mt-3 flex items-center justify-between gap-2">
                <button
                  type="button"
                  className="btn-ghost !py-1.5 text-[11px]"
                  onClick={() => setScenario(DEFAULTS)}
                >
                  <RefreshCw size={12} /> Reset scenario
                </button>
                <span className="text-[10px] text-slate-400">
                  {simLoading ? "Querying Exasol…" : `${sim.query_ms.toFixed(0)} ms`}
                </span>
              </div>
            </Card>

            <Card className="panel-pad">
              <SectionHeading
                icon={Target}
                title="Path to approval"
                description={`Approval threshold ${sim.path_to_approval.target_score.toFixed(0)} · current gap ${sim.path_to_approval.gap.toFixed(0)} pts`}
                action={
                  sim.path_to_approval.reachable ? (
                    <Badge tone="success" dot>
                      reachable
                    </Badge>
                  ) : (
                    <Badge tone="danger" dot>
                      out of reach
                    </Badge>
                  )
                }
              />
              <p className="mt-2.5 rounded-lg bg-slate-50 p-2.5 text-[11.5px] leading-5 text-slate-600">
                {sim.path_to_approval.message}
              </p>
              {sim.path_to_approval.additional_paydown !== null &&
                sim.path_to_approval.additional_paydown > 0 && (
                  <button
                    type="button"
                    className="btn-primary mt-2.5 w-full !py-2 text-[11.5px]"
                    onClick={() =>
                      setScenario((current) => ({
                        ...current,
                        revolving_paydown: Math.min(
                          cardMax,
                          current.revolving_paydown + (sim.path_to_approval.additional_paydown ?? 0),
                        ),
                      }))
                    }
                  >
                    <Wallet size={13} />
                    Apply additional {currency(sim.path_to_approval.additional_paydown)}
                  </button>
                )}

              <div className="mt-3 space-y-1.5">
                {sim.actions.map((action) => (
                  <div
                    key={action.code}
                    className={cn(
                      "flex items-start gap-2 rounded-lg border px-2.5 py-2",
                      action.applied ? "border-brand-200 bg-brand-50/50" : "border-slate-100 bg-white",
                    )}
                  >
                    <span
                      className={cn(
                        "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md",
                        action.applied
                          ? "bg-brand-100 text-brand-700"
                          : "bg-slate-100 text-slate-400",
                      )}
                    >
                      {action.applied ? <Check size={11} /> : <Info size={11} />}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[11px] font-medium text-slate-700">{action.label}</p>
                      <p className="text-[10px] leading-4 text-slate-500">{action.description}</p>
                    </div>
                    <span
                      className={cn(
                        "shrink-0 text-[11px] font-semibold tabular-nums",
                        action.score_impact > 0
                          ? "text-emerald-600"
                          : action.score_impact < 0
                            ? "text-rose-600"
                            : "text-slate-400",
                      )}
                    >
                      {action.score_impact > 0 ? "+" : ""}
                      {action.score_impact.toFixed(1)}
                    </span>
                  </div>
                ))}
              </div>

              <details className="group mt-3">
                <summary className="flex cursor-pointer list-none items-center justify-between text-[10px] font-medium text-slate-500 [&::-webkit-details-marker]:hidden">
                  Model assumptions
                  <ChevronDown size={12} className="transition group-open:rotate-180" />
                </summary>
                <ul className="mt-1.5 space-y-1">
                  {sim.assumptions.map((assumption) => (
                    <li key={assumption} className="flex gap-1.5 text-[10px] leading-4 text-slate-500">
                      <span className="mt-[6px] h-1 w-1 shrink-0 rounded-full bg-slate-300" />
                      {assumption}
                    </li>
                  ))}
                </ul>
              </details>
            </Card>
          </div>

          {/* Letters */}
          <Card className="overflow-hidden lg:col-span-7">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-navy-900 text-white">
                  <FileText size={14} />
                </span>
                <div>
                  <p className="text-[12px] font-semibold text-ink">Disclosure workbench</p>
                  <p className="text-[10px] text-slate-500">
                    {letter
                      ? `${letter.provider} · ${letter.model} · ${letter.llm_ms.toFixed(0)} ms`
                      : "Compliance letter and plain-English companion"}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                {letter && (
                  <Badge tone={letter.generation_mode === "llm" ? "brand" : "success"}>
                    {letter.generation_mode === "llm" ? (
                      <>
                        <Sparkles size={10} /> LLM drafted
                      </>
                    ) : (
                      <>
                        <ShieldCheck size={10} /> deterministic
                      </>
                    )}
                  </Badge>
                )}
                <select
                  value={tone}
                  onChange={(event) => {
                    const value = event.target.value as "formal" | "plain";
                    setTone(value);
                    if (letter) void generate(value);
                  }}
                  className="field !w-auto !py-1.5 !text-[11px]"
                  aria-label="Letter tone"
                >
                  <option value="formal">Formal tone</option>
                  <option value="plain">Plain tone</option>
                </select>
                <button
                  type="button"
                  className="btn-ghost !px-2 !py-1.5"
                  onClick={copyLetter}
                  disabled={!letter}
                  title="Copy letter"
                >
                  {copied ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
                </button>
                <button
                  type="button"
                  className="btn-ghost !px-2 !py-1.5"
                  onClick={downloadLetter}
                  disabled={!letter}
                  title="Download letter"
                >
                  <Download size={13} />
                </button>
                <button
                  type="button"
                  className="btn-dark !px-2.5 !py-1.5 !text-[11px]"
                  onClick={() => generate(tone)}
                  disabled={letterLoading || approved}
                >
                  {letterLoading ? (
                    <Loader2 size={12} className="animate-spin" />
                  ) : (
                    <Wand2 size={12} />
                  )}
                  Generate
                </button>
              </div>
            </div>

            <div className="flex gap-1 border-b border-slate-100 px-4 pt-2 xl:hidden">
              {(["letter", "explanation"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setPane(value)}
                  className={cn(
                    "rounded-t-lg px-3 py-1.5 text-[11px] font-medium capitalize transition",
                    pane === value
                      ? "bg-slate-100 text-slate-800"
                      : "text-slate-500 hover:text-slate-700",
                  )}
                >
                  {value === "letter" ? "Compliance letter" : "Plain English"}
                </button>
              ))}
            </div>

            <div className="p-3.5 sm:p-4">
              {approved ? (
                <EmptyState
                  title="No adverse action required"
                  description="This file is currently approved, so CredenceIQ will not generate an adverse-action notice. Move a slider to explore a decline scenario, or choose a referred or declined file."
                  action={
                    <Link href="/audit" className="btn-ghost">
                      Browse declined files
                      <ArrowUpRight size={13} />
                    </Link>
                  }
                />
              ) : letterLoading && !letter ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 rounded-lg bg-brand-50 px-3 py-2 text-[11px] text-brand-800">
                    <Loader2 size={13} className="animate-spin" />
                    Drafting the notice and cross-checking factor disclosures…
                  </div>
                  <Skeleton className="h-4 w-44" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-11/12" />
                  <Skeleton className="h-3 w-4/5" />
                  <Skeleton className="h-[280px] w-full" />
                </div>
              ) : letterError ? (
                <ErrorPanel
                  title="The notice could not be generated"
                  message={letterError}
                  onRetry={() => generate(tone)}
                />
              ) : letter ? (
                <>
                  <div className={cn("grid gap-3 xl:grid-cols-[1.12fr_1fr]", pane === "letter" ? "" : "")}>
                    <div className={cn(pane === "explanation" && "hidden xl:block")}>
                      <LetterBody report={letter} />
                    </div>
                    <div className={cn(pane === "letter" && "hidden xl:block")}>
                      <div className="mb-2 flex items-center justify-between">
                        <span className="eyebrow">Customer-facing explanation</span>
                        <span className="inline-flex items-center gap-1 text-[9.5px] text-slate-400">
                          <Database size={10} /> {letter.persisted ? "persisted" : "not persisted"}
                        </span>
                      </div>
                      <ExplanationPane report={letter} />
                      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
                        <Badge tone="neutral">Report {letter.report_id}</Badge>
                        <Badge tone="neutral">Score {letter.score.toFixed(0)}</Badge>
                        <Badge tone={decisionTone(letter.decision)}>{titleCase(letter.decision)}</Badge>
                      </div>
                      <p className="mt-2 text-[9.5px] leading-4 text-slate-400">
                        Generated {dateTime(letter.generated_at)} · query {letter.query_ms.toFixed(0)} ms ·
                        disclosure {letter.llm_ms.toFixed(0)} ms
                      </p>
                    </div>
                  </div>
                </>
              ) : (
                <EmptyState
                  title="No disclosure drafted yet"
                  description="Generate a compliance notice to see the formal letter alongside a plain-English explanation of the same decision."
                  action={
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={() => generate(tone)}
                      disabled={!customerId || approved}
                    >
                      <Wand2 size={14} /> Generate notice
                    </button>
                  }
                />
              )}
            </div>

            {letter && (
              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 bg-slate-50/60 px-4 py-2.5">
                <span className="text-[10px] text-slate-500">
                  Decision drivers disclosed in the letter:{" "}
                  <b className="text-slate-700">{letter.compliance_letter.factor_disclosures.length}</b>
                </span>
                <span className="inline-flex items-center gap-1 text-[10px] text-slate-400">
                  <Landmark size={11} /> RBI / DPDP aligned draft
                </span>
              </div>
            )}
          </Card>
        </div>
      )}
    </>
  );
}

export default function StudioPage() {
  return (
    <Suspense
      fallback={
        <div className="panel p-6">
          <Skeleton className="h-5 w-56" />
          <Skeleton className="mt-3 h-3 w-80" />
        </div>
      }
    >
      <StudioWorkspace />
    </Suspense>
  );
}
