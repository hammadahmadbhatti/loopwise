"use client";

import { Search, Users } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { SentimentMeter } from "@/components/charts";
import { Badge, Card, EmptyState, ErrorNote, Input, LanguageBadge, PageHeader, Select, Skeleton } from "@/components/ui";
import { qs, ws } from "@/lib/api";
import { money } from "@/lib/format";
import { useApi, useDebounced } from "@/lib/hooks";
import type { Customer } from "@/lib/types";

export default function CustomersPage() {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("mrr");
  const [atRisk, setAtRisk] = useState(false);
  const dq = useDebounced(q);
  const { data, loading, error } = useApi<{ total: number; items: Customer[] }>(ws(`/customers${qs({ q: dq, sort, at_risk: atRisk, page_size: 200 })}`));
  return (
    <>
      <PageHeader title="Customers" subtitle="Who's talking, what they pay, and how they feel. Revenue here drives the revenue-at-stake factor in prioritization." />
      <Card className="mb-4 flex flex-wrap items-center gap-2 p-3">
        <div className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
          <Input className="pl-8" placeholder="Search name, email or company" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <Select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort">
          <option value="mrr">Highest MRR</option><option value="feedback">Most feedback</option><option value="sentiment">Most negative</option><option value="recent">Most recent</option>
        </Select>
        <label className="flex items-center gap-1.5 text-sm text-slate-600"><input type="checkbox" checked={atRisk} onChange={(e) => setAtRisk(e.target.checked)} className="accent-brand-600" /> At risk only</label>
      </Card>
      <ErrorNote error={error} />
      <Card>
        {loading && !data ? <div className="space-y-2 p-4">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
          : !data?.items.length ? <EmptyState icon={<Users className="h-5 w-5" />} title="No customers yet">Customers are created automatically from feedback that includes an email.</EmptyState>
          : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-sm">
                <thead><tr className="border-b border-slate-100 text-left text-xs font-medium text-slate-500">
                  <th className="px-5 py-2.5">Customer</th><th className="px-2 py-2.5">Plan</th><th className="px-2 py-2.5 text-right">MRR</th>
                  <th className="px-2 py-2.5">Country</th><th className="px-2 py-2.5 text-right">Feedback</th><th className="px-2 py-2.5">Sentiment</th><th className="px-5 py-2.5"></th>
                </tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {data.items.map((c) => (
                    <tr key={c.id} className="hover:bg-slate-50">
                      <td className="px-5 py-2.5">
                        <div className="font-medium text-slate-900">{c.company || c.name || c.email}</div>
                        <div className="text-xs text-slate-500">{c.name}{c.email && ` · ${c.email}`}</div>
                      </td>
                      <td className="px-2 py-2.5">{c.plan && <Badge>{c.plan}</Badge>}</td>
                      <td className="px-2 py-2.5 text-right tabular-nums">{money(c.mrr)}</td>
                      <td className="px-2 py-2.5 text-slate-600"><span className="mr-1.5">{c.country}</span><LanguageBadge code={c.language} /></td>
                      <td className="px-2 py-2.5 text-right tabular-nums">
                        <Link className="text-brand-600 hover:underline" href={`/app/feedback?customer=${c.id}`}>{c.feedback_count}</Link>
                      </td>
                      <td className="px-2 py-2.5"><SentimentMeter value={c.avg_sentiment ?? null} /></td>
                      <td className="px-5 py-2.5 text-right">{(c.churn_signals ?? 0) > 0 && <Badge tone="red">Churn risk</Badge>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </Card>
    </>
  );
}
