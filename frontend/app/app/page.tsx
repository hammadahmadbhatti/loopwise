"use client";

import { AlertTriangle, ArrowRight, Flame, Globe2, Inbox, Upload } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { BarList, SENTIMENT_COLORS, Sparkline, VolumeChart } from "@/components/charts";
import { Badge, Card, CardHeader, Delta, EmptyState, LanguageBadge, PageHeader, Select, Skeleton, Stat, UrgencyBadge } from "@/components/ui";
import { ws } from "@/lib/api";
import { CATEGORY_LABEL, languageName, money, num, relTime } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Overview } from "@/lib/types";

export default function OverviewPage() {
  const [days, setDays] = useState(30);
  const { data, loading } = useApi<Overview>(ws(`/insights/overview?days=${days}`), { pollMs: 15000 });

  const k = data?.kpis;
  const volumeDelta = k && k.feedback_prev ? ((k.feedback - k.feedback_prev) / k.feedback_prev) * 100 : null;
  const sentDelta = k && k.avg_sentiment != null && k.avg_sentiment_prev != null ? k.avg_sentiment - k.avg_sentiment_prev : null;

  return (
    <>
      <PageHeader
        title="Overview"
        subtitle="What customers around the world are telling you, analyzed and grouped automatically."
        actions={
          <Select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Period">
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={365}>Last 12 months</option>
          </Select>
        }
      />

      {loading && !data ? (
        <div className="grid gap-4 md:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-24" />)}</div>
      ) : !data || (data.kpis.feedback === 0 && data.kpis.feedback_prev === 0) ? (
        <Card>
          <EmptyState icon={<Inbox className="h-5 w-5" />} title="No feedback yet"
            action={<div className="flex gap-2"><Link href="/app/settings#import"><span className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand-600 px-3.5 text-sm font-medium text-white"><Upload className="h-4 w-4" /> Import a CSV</span></Link><Link href="/app/settings#widget"><span className="inline-flex h-9 items-center rounded-lg border border-slate-200 px-3.5 text-sm font-medium text-slate-700">Install the widget</span></Link></div>}>
            Connect a channel or import existing survey, review or support data. Loopwise analyzes every message in any language as it arrives.
          </EmptyState>
        </Card>
      ) : (
        <div className="space-y-6">
          {k!.pending_analysis > 0 && (
            <div className="flex items-center gap-2 rounded-lg border border-brand-100 bg-brand-50 px-3 py-2 text-sm text-brand-700">
              <span className="h-2 w-2 animate-pulse rounded-full bg-brand-500" /> Analyzing {k!.pending_analysis} new piece{k!.pending_analysis === 1 ? "" : "s"} of feedback…
            </div>
          )}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Stat label="Feedback received" value={num(k!.feedback)} delta={<Delta value={volumeDelta} suffix="%" />} />
            <Stat label="Average sentiment" value={k!.avg_sentiment == null ? "–" : (k!.avg_sentiment > 0 ? "+" : "") + k!.avg_sentiment.toFixed(2)} delta={<Delta value={sentDelta} />} hint="-1 (very negative) to +1 (very positive)" />
            <Stat label="Negative share" value={`${k!.negative_pct}%`} />
            <Stat label="Churn signals" value={num(k!.churn_signals)} />
            <Stat label="Languages" value={num(k!.languages)} />
            <Stat label="Countries" value={num(k!.countries)} />
            <Stat label="Customers heard" value={num(k!.customers)} />
            <Stat label="Avg. rating" value={k!.avg_rating == null ? "–" : `${k!.avg_rating.toFixed(1)} / 5`} />
          </div>

          {data.emerging.length > 0 && (
            <Card className="border-rose-200 bg-rose-50/40">
              <div className="flex flex-wrap items-center gap-3 px-5 py-3.5">
                <Flame className="h-4 w-4 text-rose-500" />
                <span className="text-sm font-semibold text-rose-900">Emerging issues</span>
                {data.emerging.map((e) => (
                  <Link key={e.id} href={`/app/feedback?theme=${e.id}`} className="inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-white px-2.5 py-1 text-sm text-rose-800 hover:border-rose-300">
                    {e.name} <span className="text-xs text-rose-500">{e.this_week} this week vs ~{e.baseline}/wk</span>
                  </Link>
                ))}
              </div>
            </Card>
          )}

          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader title="Feedback volume by sentiment" subtitle={`Daily, last ${days} days`} action={
                <div className="flex gap-3 text-[11px] text-slate-500">
                  {(["positive", "neutral", "negative"] as const).map((s) => (
                    <span key={s} className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: SENTIMENT_COLORS[s] }} />{s}</span>
                  ))}
                </div>
              } />
              <div className="p-4"><VolumeChart data={data.series} /></div>
            </Card>
            <Card>
              <CardHeader title="What it's about" subtitle="Category of each message" />
              <div className="p-5">
                <BarList items={data.categories.map(([c, n]) => ({ label: CATEGORY_LABEL[c] ?? c, value: n }))} />
              </div>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader title="Top themes" subtitle="Grouped automatically across languages" action={<Link href="/app/themes" className="inline-flex items-center gap-1 text-xs font-medium text-brand-600">All themes <ArrowRight className="h-3 w-3" /></Link>} />
              <ul className="divide-y divide-slate-100">
                {data.top_themes.length === 0 && <li className="px-5 py-6 text-sm text-slate-500">Themes appear once a few similar messages arrive.</li>}
                {data.top_themes.map((t) => (
                  <li key={t.id}>
                    <Link href={`/app/feedback?theme=${t.id}`} className="flex items-center gap-4 px-5 py-3 hover:bg-slate-50">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 truncate text-sm font-medium text-slate-900">
                          {t.name} {t.emerging && <Badge tone="red">Emerging</Badge>}
                        </div>
                        <div className="text-xs text-slate-500">{t.count} mentions · sentiment {t.avg_sentiment == null ? "–" : t.avg_sentiment.toFixed(2)}</div>
                      </div>
                      <Sparkline values={t.weekly} highlight={t.emerging} />
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
            <Card>
              <CardHeader title="Where it comes from" subtitle="Countries by volume, colored by sentiment" action={<Globe2 className="h-4 w-4 text-slate-400" />} />
              <div className="p-5">
                <BarList items={data.countries.slice(0, 8).map((c) => ({
                  label: c.country, value: c.count,
                  tone: c.avg_sentiment == null ? "#94a3b8" : c.avg_sentiment < -0.2 ? SENTIMENT_COLORS.negative : c.avg_sentiment > 0.2 ? SENTIMENT_COLORS.positive : SENTIMENT_COLORS.neutral,
                }))} />
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {data.languages.map(([l, n]) => <Badge key={l} tone="blue" title={languageName(l)}>{l.toUpperCase()} · {n}</Badge>)}
                </div>
              </div>
            </Card>
          </div>

          <Card>
            <CardHeader title="Customers at risk" subtitle="Churn signals and critical issues, highest revenue first" action={<AlertTriangle className="h-4 w-4 text-amber-500" />} />
            {data.at_risk.length === 0 ? (
              <div className="px-5 py-6 text-sm text-slate-500">No churn signals in this period.</div>
            ) : (
              <ul className="divide-y divide-slate-100">
                {data.at_risk.map((r) => (
                  <li key={r.id}>
                    <Link href={`/app/feedback?open=${r.id}`} className="flex flex-wrap items-center gap-3 px-5 py-3 hover:bg-slate-50">
                      <div className="w-44 shrink-0">
                        <div className="truncate text-sm font-medium">{r.company || r.customer || "Anonymous"}</div>
                        <div className="text-xs text-slate-500">{money(r.mrr)}/mo</div>
                      </div>
                      <div className="min-w-0 flex-1 truncate text-sm text-slate-700">{r.summary}</div>
                      <div className="flex items-center gap-1.5">
                        <LanguageBadge code={r.language} />
                        {r.churn_risk && <Badge tone="red">Churn risk</Badge>}
                        <UrgencyBadge value={r.urgency} />
                        <span className="text-xs text-slate-400">{relTime(r.created_at)}</span>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
