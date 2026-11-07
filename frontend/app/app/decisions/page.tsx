"use client";

import { Gavel } from "lucide-react";
import Link from "next/link";
import { Badge, Card, EmptyState, ErrorNote, PageHeader, Skeleton } from "@/components/ui";
import { ws } from "@/lib/api";
import { money, RECOMMENDATION_LABEL, shortDate } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Decision } from "@/lib/types";

export default function DecisionsPage() {
  const { data, loading, error } = useApi<Decision[]>(ws("/decisions"));
  return (
    <>
      <PageHeader title="Decision log" subtitle="Every product decision with its rationale and a snapshot of the evidence at the time, so the team can learn from past calls." />
      <ErrorNote error={error} />
      <Card>
        {loading && !data ? <div className="space-y-2 p-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
          : !data?.length ? <EmptyState icon={<Gavel className="h-5 w-5" />} title="No decisions recorded yet">Open an opportunity and record a decision: build, investigate, defer or decline.</EmptyState>
          : (
            <ol className="divide-y divide-slate-100">
              {data.map((d) => {
                const s = d.evidence_snapshot as Record<string, number | string | null | string[]>;
                return (
                  <li key={d.id} className="flex flex-wrap gap-4 px-5 py-4">
                    <div className="w-28 shrink-0 text-xs text-slate-500">{shortDate(d.created_at)}<div>{d.decided_by}</div></div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={d.outcome === "build" ? "green" : d.outcome === "decline" ? "slate" : "amber"}>{d.outcome}</Badge>
                        <Link href={`/app/opportunities/${d.opportunity_id}`} className="text-sm font-medium text-slate-900 hover:underline">{d.opportunity_title}</Link>
                      </div>
                      <p className="mt-1 text-sm text-slate-700">{d.rationale}</p>
                      <p className="mt-1 text-xs text-slate-400">
                        Evidence then: score {String(s.priority_score ?? "–")} · {String(s.customers ?? "–")} customers · {money(Number(s.mrr ?? 0))}/mo · {String(s.churn_risk ?? 0)} churn signals
                        {s.ai_recommendation ? ` · AI recommended: ${RECOMMENDATION_LABEL[String(s.ai_recommendation)]}` : ""}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
      </Card>
    </>
  );
}
