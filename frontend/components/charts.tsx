"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export const SENTIMENT_COLORS = { positive: "#10b981", neutral: "#94a3b8", negative: "#f43f5e", pending: "#cbd5e1" };

export function VolumeChart({ data }: { data: { date: string; positive: number; neutral: number; negative: number; pending: number }[] }) {
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid stroke="#f1f5f9" vertical={false} />
          <XAxis
            dataKey="date"
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: "#94a3b8" }}
            tickFormatter={(d: string) => new Date(d).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
            minTickGap={24}
          />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "#94a3b8" }} />
          <Tooltip
            contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 12 }}
            labelFormatter={(d) => new Date(String(d)).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })}
          />
          {(["negative", "neutral", "positive", "pending"] as const).map((k) => (
            <Area key={k} type="monotone" dataKey={k} stackId="1" stroke={SENTIMENT_COLORS[k]} fill={SENTIMENT_COLORS[k]} fillOpacity={0.35} strokeWidth={1.5} />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Tiny inline SVG sparkline (8 weekly buckets). */
export function Sparkline({ values, highlight }: { values: number[]; highlight?: boolean }) {
  const w = 80;
  const h = 22;
  const max = Math.max(1, ...values);
  const step = values.length > 1 ? w / (values.length - 1) : w;
  const points = values.map((v, i) => `${(i * step).toFixed(1)},${(h - 2 - (v / max) * (h - 4)).toFixed(1)}`).join(" ");
  const color = highlight ? "#f43f5e" : "#6366f1";
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden className="overflow-visible">
      <polyline points={points} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
      {values.length > 0 && (
        <circle cx={(values.length - 1) * step} cy={h - 2 - (values[values.length - 1] / max) * (h - 4)} r={2} fill={color} />
      )}
    </svg>
  );
}

export function BarList({ items, format }: { items: { label: React.ReactNode; value: number; tone?: string; sub?: React.ReactNode }[]; format?: (v: number) => string }) {
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <ul className="space-y-2">
      {items.map((it, i) => (
        <li key={i} className="text-sm">
          <div className="flex items-center justify-between gap-3">
            <span className="min-w-0 truncate text-slate-700">{it.label}</span>
            <span className="shrink-0 tabular-nums text-slate-500">{format ? format(it.value) : it.value}{it.sub}</span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
            <div className="h-full rounded-full" style={{ width: `${(it.value / max) * 100}%`, background: it.tone ?? "#6366f1" }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Sentiment as a diverging bar from -1..1 */
export function SentimentMeter({ value }: { value: number | null }) {
  if (value == null) return <span className="text-xs text-slate-400">–</span>;
  const pctWidth = Math.abs(value) * 50;
  const color = value < -0.2 ? SENTIMENT_COLORS.negative : value > 0.2 ? SENTIMENT_COLORS.positive : SENTIMENT_COLORS.neutral;
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-1.5 w-16 rounded-full bg-slate-100">
        <div className="absolute top-0 h-full w-px bg-slate-300" style={{ left: "50%" }} />
        <div
          className="absolute top-0 h-full rounded-full"
          style={{ background: color, width: `${pctWidth}%`, left: value < 0 ? `${50 - pctWidth}%` : "50%" }}
        />
      </div>
      <span className="text-xs tabular-nums text-slate-500">{value > 0 ? "+" : ""}{value.toFixed(2)}</span>
    </div>
  );
}
