"use client";

import { GitMerge, Layers, Pencil, RefreshCw, Target } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Sparkline } from "@/components/charts";
import { Badge, Button, Card, EmptyState, ErrorNote, Input, Label, Modal, PageHeader, Select, Skeleton, StatusBadge } from "@/components/ui";
import { api, ws } from "@/lib/api";
import { CATEGORY_LABEL, languageName, money, providerLabel } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Theme } from "@/lib/types";

export default function ThemesPage() {
  const router = useRouter();
  const { data, loading, reload, error } = useApi<{ items: Theme[]; has_unthemed: boolean }>(ws("/themes"), { pollMs: 20000 });
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [editing, setEditing] = useState<Theme | null>(null);
  const [merging, setMerging] = useState<Theme | null>(null);
  const [sort, setSort] = useState<"count" | "mrr" | "sentiment" | "trend">("count");

  async function run(label: string, fn: () => Promise<unknown>) {
    setBusy(label);
    setErr(null);
    try {
      await fn();
      await reload(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(null);
    }
  }

  async function toOpportunity(t: Theme) {
    setBusy(`opp-${t.id}`);
    try {
      const r = await api<{ id: number }>(ws(`/themes/${t.id}/opportunity`), { method: "POST" });
      router.push(`/app/opportunities/${r.id}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
      setBusy(null);
    }
  }

  const items = [...(data?.items ?? [])].sort((a, b) => {
    if (sort === "mrr") return b.mrr - a.mrr;
    if (sort === "sentiment") return (a.avg_sentiment ?? 0) - (b.avg_sentiment ?? 0);
    if (sort === "trend") return b.weekly[7] - a.weekly[7] || b.count - a.count;
    return b.count - a.count;
  });

  return (
    <>
      <PageHeader
        title="Themes"
        subtitle="Feedback that talks about the same thing, grouped by meaning across every language. Themes update as new feedback arrives."
        actions={<>
          <Select value={sort} onChange={(e) => setSort(e.target.value as typeof sort)} aria-label="Sort themes">
            <option value="count">Most mentioned</option><option value="mrr">Most revenue</option><option value="sentiment">Most negative</option><option value="trend">Trending this week</option>
          </Select>
          <Button loading={busy === "discover"} onClick={() => run("discover", () => api(ws("/themes/discover"), { method: "POST" }))}>
            <RefreshCw className="h-4 w-4" /> Re-run discovery
          </Button>
        </>}
      />
      <ErrorNote error={err || error} />
      {loading && !data ? (
        <div className="grid gap-4 md:grid-cols-2">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-40" />)}</div>
      ) : items.length === 0 ? (
        <Card><EmptyState icon={<Layers className="h-5 w-5" />} title="No themes yet">Themes form automatically once at least two pieces of feedback talk about the same thing.</EmptyState></Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {items.map((t) => (
            <Card key={t.id} className="flex flex-col p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="truncate text-[15px] font-semibold text-slate-900">{t.name}</h3>
                    {t.emerging && <Badge tone="red">Emerging</Badge>}
                  </div>
                  <p className="mt-0.5 line-clamp-2 text-sm text-slate-500">{t.description}</p>
                </div>
                <Sparkline values={t.weekly} highlight={t.emerging} />
              </div>
              <div className="mt-4 grid grid-cols-4 gap-3 text-center">
                <Metric label="Mentions" value={t.count} />
                <Metric label="Customers" value={t.customers} />
                <Metric label="MRR" value={money(t.mrr)} />
                <Metric label="Negative" value={`${t.negative_pct}%`} tone={t.negative_pct > 50 ? "text-rose-600" : undefined} />
              </div>
              <div className="mt-4 flex flex-wrap gap-1.5">
                {t.languages.map((l) => <Badge key={l} tone="blue" title={languageName(l)}>{l.toUpperCase()}</Badge>)}
                {t.categories.slice(0, 2).map(([c]) => <Badge key={c}>{CATEGORY_LABEL[c] ?? c}</Badge>)}
                {t.churn_risk > 0 && <Badge tone="red">{t.churn_risk} churn signal{t.churn_risk > 1 ? "s" : ""}</Badge>}
                {t.countries.length > 0 && <Badge>{t.countries.length} countr{t.countries.length > 1 ? "ies" : "y"}</Badge>}
              </div>
              {t.keywords.length > 0 && <p className="mt-2 truncate text-xs text-slate-400">Keywords: {t.keywords.join(", ")}</p>}
              <div className="mt-auto flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3" style={{ marginTop: 16 }}>
                <Link href={`/app/feedback?theme=${t.id}`} className="text-xs font-medium text-brand-600 hover:underline">View {t.count} feedback</Link>
                <span className="flex-1" />
                {t.opportunities.length > 0 ? (
                  <Link href={`/app/opportunities/${t.opportunities[0].id}`} className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-700 hover:underline">
                    <Target className="h-3.5 w-3.5" /> {t.opportunities[0].title} <StatusBadge status={t.opportunities[0].status} />
                  </Link>
                ) : (
                  <Button size="sm" variant="primary" loading={busy === `opp-${t.id}`} onClick={() => toOpportunity(t)}><Target className="h-3.5 w-3.5" /> Make opportunity</Button>
                )}
                <Button size="sm" variant="ghost" onClick={() => setEditing(t)} aria-label="Rename"><Pencil className="h-3.5 w-3.5" /></Button>
                <Button size="sm" variant="ghost" onClick={() => setMerging(t)} aria-label="Merge"><GitMerge className="h-3.5 w-3.5" /></Button>
              </div>
              {t.labeled_by && <p className="mt-2 text-[11px] text-slate-400">Named by {providerLabel(t.labeled_by)}{t.name_locked ? " · renamed manually" : ""}</p>}
            </Card>
          ))}
        </div>
      )}

      <RenameModal theme={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void reload(true); }} />
      <MergeModal theme={merging} themes={data?.items ?? []} onClose={() => setMerging(null)} onSaved={() => { setMerging(null); void reload(true); }} />
    </>
  );
}

function Metric({ label, value, tone }: { label: string; value: React.ReactNode; tone?: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-2 py-2">
      <div className={`text-sm font-semibold tabular-nums ${tone ?? "text-slate-900"}`}>{value}</div>
      <div className="text-[11px] text-slate-500">{label}</div>
    </div>
  );
}

function RenameModal({ theme, onClose, onSaved }: { theme: Theme | null; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastId, setLastId] = useState<number | null>(null);
  if (theme && theme.id !== lastId) {
    setLastId(theme.id);
    setName(theme.name);
    setDescription(theme.description);
  }
  async function save() {
    setBusy(true);
    try {
      await api(ws(`/themes/${theme!.id}`), { method: "PATCH", body: { name, description } });
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal open={!!theme} onClose={onClose} title="Rename theme" footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" loading={busy} onClick={save}>Save</Button></>}>
      <div className="space-y-3">
        <ErrorNote error={error} />
        <label className="block"><Label>Name</Label><Input value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label className="block"><Label>Description</Label><Input value={description} onChange={(e) => setDescription(e.target.value)} /></label>
        <p className="text-xs text-slate-400">Renamed themes keep their name when discovery re-runs.</p>
      </div>
    </Modal>
  );
}

function MergeModal({ theme, themes, onClose, onSaved }: { theme: Theme | null; themes: Theme[]; onClose: () => void; onSaved: () => void }) {
  const [into, setInto] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function save() {
    setBusy(true);
    try {
      await api(ws(`/themes/${theme!.id}/merge`), { body: { into_id: Number(into) } });
      setInto("");
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal open={!!theme} onClose={onClose} title={`Merge "${theme?.name ?? ""}"`} footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!into} loading={busy} onClick={save}>Merge</Button></>}>
      <div className="space-y-3">
        <ErrorNote error={error} />
        <Label>Move all its feedback into</Label>
        <Select className="w-full" aria-label="Target theme" value={into} onChange={(e) => setInto(e.target.value)}>
          <option value="">Choose a theme…</option>
          {themes.filter((t) => t.id !== theme?.id).map((t) => <option key={t.id} value={t.id}>{t.name} ({t.count})</option>)}
        </Select>
      </div>
    </Modal>
  );
}
