import type { Decision, ReconciliationStatus } from "./types";

export function cn(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(" ");
}

export function currency(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value);
}

/**
 * Indian-scale abbreviation for dense cards: ₹1,635Cr, ₹6.3L.
 *
 * Intl's `notation: "compact"` renders 1,635 crore as "₹1.6KCr", which reads
 * ambiguously, so the lakh/crore units are applied explicitly.
 */
export function compactCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const abs = Math.abs(value);
  const format = (scaled: number) =>
    new Intl.NumberFormat("en-IN", {
      maximumFractionDigits: Math.abs(scaled) < 100 ? 1 : 0,
    }).format(scaled);
  if (abs >= 1_00_00_000) return `₹${format(value / 1_00_00_000)}Cr`;
  if (abs >= 1_00_000) return `₹${format(value / 1_00_000)}L`;
  if (abs >= 1_000) return `₹${format(value / 1_000)}K`;
  return currency(value);
}

export function number(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-IN").format(value);
}

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function shortDate(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("en-IN", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function monthLabel(value: string): string {
  const [year, month] = value.split("-");
  const parsed = new Date(Number(year), Number(month) - 1, 1);
  return parsed.toLocaleDateString("en-IN", { month: "short" });
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("en-IN", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function initials(first: string, last: string): string {
  return `${first.charAt(0)}${last.charAt(0)}`.toUpperCase();
}

export function titleCase(value: string): string {
  return value
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function decisionTone(decision: Decision): "success" | "danger" | "warning" {
  if (decision === "APPROVED") return "success";
  if (decision === "DECLINED") return "danger";
  return "warning";
}

export function statusTone(
  status: ReconciliationStatus,
): "success" | "danger" | "warning" {
  if (status === "RECONCILED") return "success";
  if (status === "MISMATCH") return "danger";
  return "warning";
}

export function scoreColor(score: number): string {
  if (score >= 750) return "#0f9f7a";
  if (score >= 680) return "#d97706";
  return "#dc2626";
}

export function scoreBg(score: number): string {
  if (score >= 750) return "bg-emerald-50 text-emerald-700 ring-emerald-200";
  if (score >= 680) return "bg-amber-50 text-amber-700 ring-amber-200";
  return "bg-rose-50 text-rose-700 ring-rose-200";
}

export function clamp(value: number, low: number, high: number): number {
  return Math.max(low, Math.min(high, value));
}
