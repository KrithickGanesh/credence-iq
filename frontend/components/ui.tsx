import type { LucideIcon } from "lucide-react";
import { AlertTriangle, ArrowDownRight, ArrowUpRight, Inbox, RotateCcw } from "lucide-react";

import { cn, decisionTone, statusTone, titleCase } from "@/lib/format";
import type { Decision, ReconciliationStatus } from "@/lib/types";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  meta,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  meta?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:mb-7 lg:flex-row lg:items-end lg:justify-between">
      <div className="min-w-0">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="mt-1.5 text-balance text-2xl font-semibold tracking-tight text-ink sm:text-[28px]">
          {title}
        </h1>
        {description && (
          <p className="mt-1.5 max-w-2xl text-[13px] leading-6 text-slate-500">{description}</p>
        )}
        {meta && <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">{meta}</div>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Card({
  className,
  children,
  as: Tag = "section",
}: {
  className?: string;
  children: React.ReactNode;
  as?: "section" | "div" | "article";
}) {
  return <Tag className={cn("panel", className)}>{children}</Tag>;
}

export function SectionHeading({
  title,
  description,
  action,
  icon: Icon,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: LucideIcon;
}) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="flex min-w-0 items-start gap-2.5">
        {Icon && (
          <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
            <Icon size={14} strokeWidth={2} />
          </span>
        )}
        <div className="min-w-0">
          <h2 className="text-[13.5px] font-semibold tracking-tight text-ink">{title}</h2>
          {description && (
            <p className="mt-0.5 text-[11.5px] leading-5 text-slate-500">{description}</p>
          )}
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

const TONES = {
  success: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  danger: "bg-rose-50 text-rose-700 ring-rose-200",
  warning: "bg-amber-50 text-amber-700 ring-amber-200",
  info: "bg-sky-50 text-sky-700 ring-sky-200",
  neutral: "bg-slate-50 text-slate-600 ring-slate-200",
  brand: "bg-brand-50 text-brand-700 ring-brand-200",
} as const;

export type Tone = keyof typeof TONES;

export function Badge({
  tone = "neutral",
  children,
  className,
  dot = false,
}: {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
  dot?: boolean;
}) {
  return (
    <span className={cn("chip", TONES[tone], className)}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />}
      {children}
    </span>
  );
}

export function DecisionBadge({ decision }: { decision: Decision }) {
  return (
    <Badge tone={decisionTone(decision)} dot>
      {titleCase(decision)}
    </Badge>
  );
}

export function ReconciliationBadge({
  status,
  compact = false,
}: {
  status: ReconciliationStatus;
  compact?: boolean;
}) {
  const label =
    status === "RECONCILED"
      ? "Reconciled"
      : status === "MINOR_VARIANCE"
        ? compact
          ? "Minor"
          : "Minor variance"
        : compact
          ? "Mismatch"
          : "Exposure mismatch";
  return (
    <Badge tone={statusTone(status)} dot>
      {label}
    </Badge>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const tone: Tone =
    severity === "critical" ? "danger" : severity === "high" ? "warning" : "neutral";
  return <Badge tone={tone}>{titleCase(severity)}</Badge>;
}

export function StatCard({
  label,
  value,
  helper,
  icon: Icon,
  tone = "neutral",
  trend,
}: {
  label: string;
  value: React.ReactNode;
  helper?: React.ReactNode;
  icon?: LucideIcon;
  tone?: Tone;
  trend?: { value: string; direction: "up" | "down"; positive?: boolean };
}) {
  return (
    <div className="panel group relative overflow-hidden p-4 transition hover:border-slate-300/80 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[10.5px] font-semibold uppercase tracking-[0.08em] text-slate-500">
          {label}
        </p>
        {Icon && (
          <span
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-lg ring-1 ring-inset",
              TONES[tone],
            )}
          >
            <Icon size={15} strokeWidth={2} />
          </span>
        )}
      </div>
      <p className="mt-2.5 text-[25px] font-semibold leading-none tracking-tight text-ink tabular-nums">
        {value}
      </p>
      {(helper || trend) && (
        <div className="mt-2.5 flex flex-wrap items-center gap-x-2 gap-y-1">
          {trend && (
            <span
              className={cn(
                "inline-flex items-center gap-0.5 text-[11px] font-semibold",
                trend.positive === false ? "text-rose-600" : "text-emerald-600",
              )}
            >
              {trend.direction === "up" ? (
                <ArrowUpRight size={12} />
              ) : (
                <ArrowDownRight size={12} />
              )}
              {trend.value}
            </span>
          )}
          {helper && <p className="text-[11px] leading-4 text-slate-500">{helper}</p>}
        </div>
      )}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-slate-200/70", className)} />;
}

export function LoadingPanel({
  label = "Running analytical query…",
  rows = 3,
}: {
  label?: string;
  rows?: number;
}) {
  return (
    <div className="panel panel-pad">
      <div className="flex items-center gap-2 text-[12px] text-slate-500">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand-400 opacity-70" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-brand-500" />
        </span>
        {label}
      </div>
      <div className="mt-4 space-y-3">
        {Array.from({ length: rows }).map((_, index) => (
          <Skeleton key={index} className={cn("h-4", index === rows - 1 ? "w-2/3" : "w-full")} />
        ))}
      </div>
    </div>
  );
}

export function ErrorPanel({
  title = "Unable to load this view",
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="panel border-rose-200/80 bg-rose-50/40 p-6">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-rose-100 text-rose-600">
          <AlertTriangle size={17} />
        </span>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-rose-900">{title}</h3>
          <p className="mt-1 text-[12.5px] leading-5 text-rose-700/90">{message}</p>
          {onRetry && (
            <button type="button" onClick={onRetry} className="btn-ghost mt-3 !border-rose-200 !text-rose-700 hover:!bg-rose-50">
              <RotateCcw size={13} />
              Retry
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-100 text-slate-400">
        <Inbox size={19} />
      </span>
      <p className="mt-3 text-sm font-medium text-slate-700">{title}</p>
      {description && <p className="mt-1 max-w-sm text-[12px] leading-5 text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function InfoRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5">
      <dt className="text-[11.5px] text-slate-500">{label}</dt>
      <dd className={cn("text-right text-[12px] font-medium text-slate-800", mono && "font-mono text-[11px]")}>
        {value}
      </dd>
    </div>
  );
}
