"use client";

import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { compactCurrency, currency, number, pct, titleCase } from "@/lib/format";
import type {
  DecisionSlice,
  DenialDriver,
  ExposureSystem,
  VelocityPoint,
} from "@/lib/types";

const GRID = "#eef2f6";
const AXIS = "#94a3b8";

const SYSTEM_COLORS: Record<string, string> = {
  CORE: "#4f46e5",
  CARDS: "#0ea5e9",
  MICRO: "#f59e0b",
};

const DECISION_COLORS: Record<string, string> = {
  APPROVED: "#0f9f7a",
  DECLINED: "#dc2626",
  REFERRED: "#d97706",
};

const tooltipStyle = {
  borderRadius: 12,
  border: "1px solid #e2e8f0",
  boxShadow: "0 12px 30px rgba(15, 23, 42, 0.10)",
  fontSize: 12,
  padding: "8px 12px",
};

export function ExposureBySystemChart({ data }: { data: ExposureSystem[] }) {
  const rows = data.map((entry) => ({
    ...entry,
    name: entry.label || titleCase(entry.system),
    short: compactCurrency(entry.exposure),
  }));
  return (
    <div className="h-[228px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 12, bottom: 0, left: 4 }} barCategoryGap={18}>
          <CartesianGrid stroke={GRID} horizontal={false} />
          <XAxis
            type="number"
            tickFormatter={(value: number) => compactCurrency(value)}
            axisLine={false}
            tickLine={false}
            tick={{ fill: AXIS, fontSize: 11 }}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={78}
            axisLine={false}
            tickLine={false}
            tick={{ fill: "#475569", fontSize: 11.5, fontWeight: 500 }}
          />
          <Tooltip
            cursor={{ fill: "rgba(15, 23, 42, 0.03)" }}
            contentStyle={tooltipStyle}
            formatter={(value, _name, item) => {
              const payload = item.payload as { accounts?: number; share?: number };
              return [
                `${currency(Number(value))}  ·  ${number(payload.accounts)} accounts  ·  ${pct(payload.share ?? 0)} of exposure`,
                "Outstanding",
              ];
            }}
          />
          <Bar dataKey="exposure" radius={[0, 6, 6, 0]} maxBarSize={30}>
            {rows.map((row) => (
              <Cell key={row.system} fill={SYSTEM_COLORS[row.system] ?? "#64748b"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function DecisionMixChart({ data }: { data: DecisionSlice[] }) {
  const total = data.reduce((sum, entry) => sum + entry.count, 0);
  const rows = data.map((entry) => ({
    ...entry,
    name: titleCase(entry.decision),
  }));
  return (
    <div className="flex h-[228px] items-center gap-2">
      <div className="relative h-full min-w-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={rows}
              dataKey="count"
              nameKey="name"
              innerRadius="62%"
              outerRadius="86%"
              paddingAngle={2}
              stroke="#ffffff"
              strokeWidth={2}
            >
              {rows.map((row) => (
                <Cell key={row.decision} fill={DECISION_COLORS[row.decision] ?? "#64748b"} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={tooltipStyle}
              formatter={(value, name, item) => {
                const payload = item.payload as { share?: number };
                return [`${number(Number(value))} applications · ${pct(payload.share ?? 0)}`, name];
              }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Decisions</span>
          <span className="text-xl font-semibold tabular-nums text-ink">{number(total)}</span>
        </div>
      </div>
      <ul className="w-[112px] shrink-0 space-y-3">
        {rows.map((row) => (
          <li key={row.decision} className="flex items-start gap-2">
            <span
              className="mt-1 h-2 w-2 shrink-0 rounded-full"
              style={{ background: DECISION_COLORS[row.decision] ?? "#64748b" }}
            />
            <div className="min-w-0">
              <p className="text-[11px] font-medium text-slate-700">{row.name}</p>
              <p className="text-[11px] tabular-nums text-slate-500">
                {number(row.count)} · {pct(row.share)}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function RejectionVelocityChart({ data }: { data: VelocityPoint[] }) {
  const rows = data.map((entry) => ({ ...entry, label: entry.month }));
  return (
    <div className="h-[228px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
          <defs>
            <linearGradient id="velocityFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0f9f7a" stopOpacity={0.22} />
              <stop offset="100%" stopColor="#0f9f7a" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis
            dataKey="month"
            axisLine={false}
            tickLine={false}
            tick={{ fill: AXIS, fontSize: 10.5 }}
            tickFormatter={(value: string) => {
              const [year, month] = value.split("-");
              const date = new Date(Number(year), Number(month) - 1, 1);
              return date.toLocaleDateString("en-US", { month: "short" });
            }}
          />
          <YAxis
            yAxisId="left"
            axisLine={false}
            tickLine={false}
            tick={{ fill: AXIS, fontSize: 10.5 }}
            tickFormatter={(value: number) => (value >= 1000 ? `${(value / 1000).toFixed(1)}k` : String(value))}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            axisLine={false}
            tickLine={false}
            tick={{ fill: AXIS, fontSize: 10.5 }}
            tickFormatter={(value: number) => `${Math.round(value * 100)}%`}
            domain={[0, "auto"]}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(value, name) => {
              if (name === "Decline rate") return [pct(Number(value)), name];
              return [number(Number(value)), name];
            }}
            labelFormatter={(label) => {
              const [year, month] = String(label).split("-");
              const date = new Date(Number(year), Number(month) - 1, 1);
              return date.toLocaleDateString("en-US", { month: "long", year: "numeric" });
            }}
          />
          <Area
            yAxisId="left"
            type="monotone"
            dataKey="applications"
            name="Applications"
            stroke="#0f9f7a"
            strokeWidth={2}
            fill="url(#velocityFill)"
            dot={false}
            activeDot={{ r: 3.5 }}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="decline_rate"
            name="Decline rate"
            stroke="#dc2626"
            strokeWidth={1.6}
            strokeDasharray="4 3"
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function DenialDriversChart({ data }: { data: DenialDriver[] }) {
  const rows = data.slice(0, 6).map((entry) => ({
    ...entry,
    name: entry.factor_name,
    short: titleCase(entry.factor_code),
  }));
  return (
    <div className="h-[228px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 0 }} barCategoryGap={14}>
          <CartesianGrid stroke={GRID} horizontal={false} />
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="name"
            width={148}
            axisLine={false}
            tickLine={false}
            tick={{ fill: "#475569", fontSize: 10.5 }}
          />
          <Tooltip
            cursor={{ fill: "rgba(15, 23, 42, 0.03)" }}
            contentStyle={tooltipStyle}
            formatter={(value, _name, item) => {
              const payload = item.payload as { avg_contribution?: number; regulation_ref?: string };
              return [
                `${number(Number(value))} declines · avg −${Math.abs(payload.avg_contribution ?? 0).toFixed(0)} pts · ${payload.regulation_ref ?? ""}`,
                "Adverse driver",
              ];
            }}
          />
          <Bar dataKey="count" radius={[0, 5, 5, 0]} fill="#dc2626" fillOpacity={0.82} maxBarSize={18} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function BureauUtilizationChart({
  utilization,
  percentile,
}: {
  utilization: number;
  percentile: number;
}) {
  const value = Math.max(0, Math.min(1.2, utilization));
  return (
    <div>
      <div className="flex items-end justify-between">
        <span className="text-[11px] text-slate-500">Portfolio utilization</span>
        <span className="text-sm font-semibold tabular-nums text-ink">{pct(utilization)}</span>
      </div>
      <div className="relative mt-2 h-2.5 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-gradient-to-r from-brand-400 to-brand-600"
          style={{ width: `${Math.min(100, (value / 1.2) * 100)}%` }}
        />
        <span className="absolute inset-y-0 left-[41.7%] w-px bg-slate-400/50" title="50% utilization" />
      </div>
      <p className="mt-1.5 text-[10.5px] text-slate-500">
        {percentile.toFixed(0)}th percentile across the portfolio
      </p>
    </div>
  );
}
