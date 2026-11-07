"use client";

import { Info, Plus, Target } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Badge, Button, Card, EmptyState, ErrorNote, Input, Label, Modal, PageHeader, Select, Skeleton, StatusBadge, Tabs, Textarea, cn } from "@/components/ui";
import { api, ws } from "@/lib/api";
import { COMPONENT_LABEL, money } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Opportunity } from "@/lib/types";
import { COMPONENT_COLORS, ScoreBar } from "@/components/ScoreBar";

export default function OpportunitiesPage() {
  const router = useRouter();
  const [tab, setTab] = useState<"open" | "shipped" | "declined" | "all">("open");
  const { data, loading, error, reload } = useApi<{ items: Opportunity[]; weights: Record<string, number> }>(ws("/opportunities"));
  const [creating, setCreating] = useState(false);

  const items = (data?.items ?? []).filter((o) =>
    tab === "all" ? true : tab === "open" ? ["under_review", "planned", "in_progress"].includes(o.status) : o.status === tab);

  return (
    <>
      <PageHeader
        title="Opportunities"
        subtitle="Problems worth solving, ranked by evidence: how many customers, how much revenue, how much pain, and whether it's growing."
        actions={<Button variant="primary" onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> New opportunity</Button>}
      />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <Tabs value={tab} onChange={setTab} items={[{ value: "open", label: "Open" }, { value: "shipped", label: "Shipped" }, { value: "declined", label: "Declined" }, { value: "all", label: "All" }]} />
        <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
          {Object.entries(COMPONENT_COLORS).map(([k, c]) => (
            <span key={k} className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: c }} />{COMPONENT_LABEL[k]} {data && `(${Math.round((data.weights[k] ?? 0) * 100)}%)`}</span>
          ))}
          <Link href="/app/settings#weights" className="inline-flex items-center gap-1 text-brand-600"><Info className="h-3 w-3" /> weights</Link>
        </div>
      </div>
      <ErrorNote error={error} />
      <Card>
        {loading && !data ? (
          <div className="space-y-2 p-4">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
        ) : items.length === 0 ? (
          <EmptyState icon={<Target className="h-5 w-5" />} title={tab === "open" ? "No open opportunities" : "Nothing here yet"}
            action={<Link href="/app/themes" className="text-sm font-medium text-brand-600">Turn a theme into an opportunity →</Link>}>
            Opportunities collect the evidence behind one problem so you can decide what to build next.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs font-medium text-slate-500">
                  <th className="w-10 px-5 py-2.5">#</th>
                  <th className="px-2 py-2.5">Opportunity</th>
                  <th className="w-44 px-2 py-2.5">Priority</th>
                  <th className="px-2 py-2.5 text-right">Customers</th>
                  <th className="px-2 py-2.5 text-right">MRR</th>
                  <th className="px-2 py-2.5 text-right">Sentiment</th>
                  <th className="px-2 py-2.5 text-right">30-day trend</th>
                  <th className="px-5 py-2.5 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((o, i) => (
                  <tr key={o.id} onClick={() => router.push(`/app/opportunities/${o.id}`)} className="cursor-pointer hover:bg-slate-50">
                    <td className="px-5 py-3 text-xs tabular-nums text-slate-400">{i + 1}</td>
                    <td className="px-2 py-3">
                      <div className="font-medium text-slate-900">{o.title}</div>
                      <div className="mt-0.5 flex flex-wrap gap-1.5 text-xs text-slate-500">
                        {o.metrics.mentions} mentions · {o.metrics.countries.length} countries
                        {o.metrics.churn_risk > 0 && <Badge tone="red">{o.metrics.churn_risk} churn</Badge>}
                        {o.has_brief && <Badge tone="violet">AI brief</Badge>}
                        {o.is_public && <Badge tone="blue">Public</Badge>}
                      </div>
                    </td>
                    <td className="px-2 py-3">
                      <div className="flex items-center gap-2">
                        <span className="w-8 text-right font-semibold tabular-nums text-slate-900">{Math.round(o.priority_score)}</span>
                        <ScoreBar breakdown={o.breakdown} score={o.priority_score} />
                      </div>
                    </td>
                    <td className="px-2 py-3 text-right tabular-nums">{o.metrics.customers}{o.metrics.votes > 0 && <span className="text-xs text-slate-400"> +{o.metrics.votes} votes</span>}</td>
                    <td className="px-2 py-3 text-right tabular-nums">{money(o.metrics.mrr)}</td>
                    <td className={cn("px-2 py-3 text-right tabular-nums", (o.metrics.avg_sentiment ?? 0) < -0.2 ? "text-rose-600" : "text-slate-600")}>{o.metrics.avg_sentiment?.toFixed(2) ?? "–"}</td>
                    <td className="px-2 py-3 text-right tabular-nums text-slate-600">{o.metrics.growth_pct == null ? "–" : `${o.metrics.growth_pct > 0 ? "+" : ""}${Math.round(o.metrics.growth_pct)}%`}</td>
                    <td className="px-5 py-3 text-right"><StatusBadge status={o.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <CreateModal open={creating} onClose={() => setCreating(false)} onCreated={(id) => { void reload(); router.push(`/app/opportunities/${id}`); }} />
    </>
  );
}

function CreateModal({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: (id: number) => void }) {
  const { data: themes } = useApi<{ items: { id: number; name: string; count: number }[] }>(open ? ws("/themes") : null);
  const [form, setForm] = useState({ title: "", description: "", theme_id: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function save() {
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ id: number }>(ws("/opportunities"), { body: { title: form.title, description: form.description, theme_id: form.theme_id ? Number(form.theme_id) : null } });
      setForm({ title: "", description: "", theme_id: "" });
      onCreated(r.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal open={open} onClose={onClose} title="New opportunity" footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={form.title.trim().length < 2} loading={busy} onClick={save}>Create</Button></>}>
      <div className="space-y-3">
        <ErrorNote error={error} />
        <label className="block"><Label>Title</Label><Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Export reports to CSV" /></label>
        <label className="block"><Label>Problem description</Label><Textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
        <div>
          <Label hint="(all its feedback becomes evidence)">Theme</Label>
          <Select className="w-full" aria-label="Theme" value={form.theme_id} onChange={(e) => setForm({ ...form, theme_id: e.target.value })}>
            <option value="">None, I&apos;ll link feedback manually</option>
            {themes?.items.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.count})</option>)}
          </Select>
        </div>
      </div>
    </Modal>
  );
}
