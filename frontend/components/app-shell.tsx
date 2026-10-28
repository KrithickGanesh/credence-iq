"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Activity,
  Database,
  FileText,
  LayoutDashboard,
  ShieldAlert,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

import { api } from "@/lib/api";
import { cn } from "@/lib/format";
import type { HealthResponse } from "@/lib/types";

interface NavItem {
  href: string;
  label: string;
  description: string;
  icon: LucideIcon;
}

const NAV: NavItem[] = [
  {
    href: "/",
    label: "Risk & Exposure",
    description: "Portfolio overview",
    icon: LayoutDashboard,
  },
  {
    href: "/audit",
    label: "Discrepancy Audit",
    description: "Cross-ledger recon",
    icon: ShieldAlert,
  },
  {
    href: "/studio",
    label: "Adverse Action Studio",
    description: "Letters & scenarios",
    icon: FileText,
  },
];

function useHealth() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    const load = () => {
      api
        .health()
        .then((value) => {
          if (!active) return;
          setHealth(value);
          setFailed(false);
        })
        .catch(() => {
          if (active) setFailed(true);
        });
    };
    load();
    const timer = setInterval(load, 30_000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  return { health, failed };
}

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      className={cn(
        "group flex items-start gap-3 rounded-xl px-3 py-2.5 transition",
        active
          ? "bg-white/10 text-white ring-1 ring-inset ring-white/10"
          : "text-slate-400 hover:bg-white/[0.06] hover:text-slate-100",
      )}
    >
      <span
        className={cn(
          "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition",
          active
            ? "bg-brand-500/20 text-brand-300"
            : "bg-white/[0.04] text-slate-400 group-hover:text-slate-200",
        )}
      >
        <Icon size={16} strokeWidth={1.9} />
      </span>
      <span className="min-w-0">
        <span className="block truncate text-[13px] font-medium leading-5">{item.label}</span>
        <span
          className={cn(
            "block truncate text-[11px] leading-4",
            active ? "text-slate-400" : "text-slate-500",
          )}
        >
          {item.description}
        </span>
      </span>
    </Link>
  );
}

function HealthPill({ health, failed }: { health: HealthResponse | null; failed: boolean }) {
  const online = Boolean(health && health.database === "up" && !failed);
  return (
    <div
      className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5"
      title={
        online
          ? `Exasol ${health?.exasol_version ?? ""} · ${health?.ping_ms ?? 0} ms ping`
          : "Exasol connection unavailable"
      }
    >
      <span className="relative flex h-2 w-2">
        {online && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
        )}
        <span
          className={cn(
            "relative inline-flex h-2 w-2 rounded-full",
            online ? "bg-emerald-400" : failed ? "bg-rose-400" : "bg-amber-400",
          )}
        />
      </span>
      <span className="text-[11px] font-medium text-slate-300">
        {online ? "Exasol live" : failed ? "API offline" : "Connecting…"}
      </span>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { health, failed } = useHealth();

  return (
    <div className="flex min-h-screen">
      <aside className="no-print fixed inset-y-0 left-0 z-30 hidden w-[268px] flex-col bg-navy-950 px-4 pb-5 pt-6 lg:flex">
        <Link href="/" className="mb-8 flex items-center gap-3 px-2">
          <span className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-700 shadow-lg shadow-brand-900/40">
            <Activity size={20} className="text-white" strokeWidth={2.2} />
          </span>
          <span>
            <span className="block text-[15px] font-semibold tracking-tight text-white">
              Credence<span className="text-brand-400">IQ</span>
            </span>
            <span className="block text-[10px] uppercase tracking-[0.18em] text-slate-500">
              Risk Intelligence
            </span>
          </span>
        </Link>

        <nav className="space-y-1.5">
          <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">
            Workspace
          </p>
          {NAV.map((item) => (
            <NavLink
              key={item.href}
              item={item}
              active={item.href === "/" ? pathname === "/" : pathname.startsWith(item.href)}
            />
          ))}
        </nav>

        <div className="mt-8 rounded-xl border border-white/[0.07] bg-white/[0.03] p-3.5">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
            <Sparkles size={13} className="text-brand-400" />
            Agentic disclosure
          </div>
          <p className="mt-2 text-[11.5px] leading-5 text-slate-500">
            Deterministic compliance letters by default, with optional OpenAI, Anthropic, or local
            LLM drafting.
          </p>
        </div>

        <div className="mt-auto space-y-3 pt-6">
          <HealthPill health={health} failed={failed} />
          <div className="flex items-center gap-2 px-1 text-[10.5px] text-slate-600">
            <Database size={12} />
            <span className="truncate">
              {health?.schema ?? "CREDENCEIQ"} · v{health?.api_version ?? "1.0.0"}
            </span>
          </div>
          <p className="px-1 text-[10px] leading-4 text-slate-700">
            Synthetic demonstration data. Not for production credit decisions.
          </p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col lg:pl-[268px]">
        <header className="no-print sticky top-0 z-20 border-b border-slate-200/70 bg-canvas/85 backdrop-blur-xl lg:hidden">
          <div className="flex items-center justify-between gap-3 px-4 py-3">
            <Link href="/" className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-400 to-brand-700">
                <Activity size={16} className="text-white" />
              </span>
              <span className="text-sm font-semibold tracking-tight">
                Credence<span className="text-brand-600">IQ</span>
              </span>
            </Link>
            <HealthPill health={health} failed={failed} />
          </div>
          <nav className="scrollbar-none flex gap-1 overflow-x-auto px-3 pb-2">
            {NAV.map((item) => {
              const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-medium transition",
                    active
                      ? "bg-navy-900 text-white"
                      : "text-slate-600 hover:bg-white hover:text-ink",
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </header>

        <main className="min-w-0 flex-1 px-4 pb-14 pt-6 sm:px-6 lg:px-8 lg:pt-8">
          <div className="mx-auto w-full max-w-[1440px]">{children}</div>
        </main>

        <footer className="no-print border-t border-slate-200/70 px-6 py-5 text-[11px] text-slate-400 lg:px-8">
          <div className="mx-auto flex w-full max-w-[1440px] flex-wrap items-center justify-between gap-2">
            <span>CredenceIQ · Exasol-Powered Risk Intelligence</span>
            <span>
              API{" "}
              <code className="rounded bg-slate-200/60 px-1.5 py-0.5 font-mono text-[10px] text-slate-600">
                {api.baseUrl}
              </code>
            </span>
          </div>
        </footer>
      </div>
    </div>
  );
}
