"use client";

import { ChevronLeft, ChevronRight, Download, Inbox, Plus, Search } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { FeedbackDrawer } from "@/components/FeedbackDrawer";
import { Badge, Button, Card, CategoryBadge, EmptyState, ErrorNote, Input, Label, LanguageBadge, Modal, PageHeader, Select, SentimentBadge, Skeleton, Textarea, UrgencyBadge, cn } from "@/components/ui";
import { api, qs, ws } from "@/lib/api";
import { CATEGORY_LABEL, languageName, relTime } from "@/lib/format";
import { useApi, useDebounced } from "@/lib/hooks";
import type { Feedback, Theme } from "@/lib/types";

interface Page { items: Feedback[]; total: number; page: number; page_size: number; facets: { languages: string[]; countries: string[] } }

function FeedbackInbox() {
  const params = useSearchParams();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [filters, setFilters] = useState({
    sentiment: "", category: "", urgency: "", language: "", source: "", churn_risk: "",
    theme_id: params.get("theme") ?? "", customer_id: params.get("customer") ?? "", sort: "newest", status: "",
  });
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<number | null>(params.get("open") ? Number(params.get("open")) : null);
  const [adding, setAdding] = useState(false);
  const debouncedQ = useDebounced(q);

  const path = useMemo(() => ws(`/feedback${qs({ ...filters, q: debouncedQ, page, page_size: 25 })}`), [filters, debouncedQ, page]);
  const { data, loading, reload, error } = useApi<Page>(path, { pollMs: 10000 });
  const { data: themes } = useApi<{ items: Theme[] }>(ws("/themes"));

  const set = (k: keyof typeof filters) => (e: React.ChangeEvent<HTMLSelectElement>) => {
    setFilters({ ...filters, [k]: e.target.value });
    setPage(1);
  };
  const activeTheme = themes?.items.find((t) => String(t.id) === filters.theme_id);
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  async function exportCsv() {
    const res = await api<Response>(ws("/feedback/export.csv"), { raw: true });
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = "feedback.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <PageHeader
        title="Feedback"
        subtitle="Every message from every channel, translated, scored and tagged by AI."
        actions={<>
          <Button onClick={exportCsv}><Download className="h-4 w-4" /> Export CSV</Button>
          <Button variant="primary" onClick={() => setAdding(true)}><Plus className="h-4 w-4" /> Add feedback</Button>
        </>}
      />

      <Card className="mb-4 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
            <Input className="pl-8" placeholder="Search text and translations…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
          </div>
          <Select value={filters.sentiment} onChange={set("sentiment")} aria-label="Sentiment">
            <option value="">Any sentiment</option><option value="negative">Negative</option><option value="neutral">Neutral</option><option value="positive">Positive</option>
          </Select>
          <Select value={filters.category} onChange={set("category")} aria-label="Category">
            <option value="">Any category</option>
            {Object.entries(CATEGORY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
          <Select value={filters.urgency} onChange={set("urgency")} aria-label="Urgency">
            <option value="">Any urgency</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
          </Select>
          <Select value={filters.language} onChange={set("language")} aria-label="Language">
            <option value="">Any language</option>
            {data?.facets.languages.map((l) => <option key={l} value={l}>{languageName(l)}</option>)}
          </Select>
          <Select value={filters.theme_id} onChange={set("theme_id")} aria-label="Theme">
            <option value="">Any theme</option>
            {themes?.items.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </Select>
          <Select value={filters.churn_risk} onChange={set("churn_risk")} aria-label="Churn risk">
            <option value="">Churn risk: any</option><option value="true">Churn risk only</option>
          </Select>
          <Select value={filters.sort} onChange={set("sort")} aria-label="Sort">
            <option value="newest">Newest</option><option value="oldest">Oldest</option><option value="most_negative">Most negative</option><option value="highest_mrr">Highest MRR</option>
          </Select>
        </div>
        {filters.customer_id && (
          <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
            Showing one customer&apos;s feedback
            <button className="underline" onClick={() => { setFilters({ ...filters, customer_id: "" }); router.replace("/app/feedback"); }}>clear</button>
          </div>
        )}
        {activeTheme && (
          <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
            Showing theme <Badge tone="brand">{activeTheme.name}</Badge>
            <button className="underline" onClick={() => { setFilters({ ...filters, theme_id: "" }); router.replace("/app/feedback"); }}>clear</button>
          </div>
        )}
      </Card>

      <ErrorNote error={error} />
      <Card>
        {loading && !data ? (
          <div className="space-y-2 p-4">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-14" />)}</div>
        ) : data && data.items.length === 0 ? (
          <EmptyState icon={<Inbox className="h-5 w-5" />} title="Nothing matches">Try clearing filters, or import feedback in Settings.</EmptyState>
        ) : (
          <ul className="divide-y divide-slate-100">
            {data?.items.map((f) => (
              <li key={f.id}>
                <button onClick={() => setOpenId(f.id)} className={cn("flex w-full items-start gap-4 px-5 py-3.5 text-left hover:bg-slate-50", openId === f.id && "bg-brand-50/50")}>
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-2 text-sm text-slate-800">{f.translated_text || f.text}</p>
                    {f.translated_text && <p className="mt-0.5 line-clamp-1 text-xs italic text-slate-400">{f.text}</p>}
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      {f.analysis_status !== "done" ? <Badge tone="brand">{f.analysis_status === "failed" ? "Analysis failed" : "Analyzing…"}</Badge> : <>
                        <LanguageBadge code={f.language} />
                        <SentimentBadge value={f.sentiment} />
                        <CategoryBadge value={f.category} />
                        <UrgencyBadge value={f.urgency} />
                        {f.churn_risk && <Badge tone="red">Churn risk</Badge>}
                        {f.theme && <Badge tone="violet">{f.theme.name}</Badge>}
                        {f.duplicate_of_id && <Badge tone="amber">Duplicate</Badge>}
                      </>}
                    </div>
                  </div>
                  <div className="hidden w-40 shrink-0 text-right sm:block">
                    <div className="truncate text-xs font-medium text-slate-700">{f.customer?.company || f.customer?.name || "Anonymous"}</div>
                    <div className="text-xs text-slate-400">{[f.customer?.plan, f.country].filter(Boolean).join(" · ")}</div>
                    <div className="mt-1 text-[11px] text-slate-400">{f.source} · {relTime(f.created_at)}</div>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
        {data && data.total > data.page_size && (
          <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3 text-sm text-slate-500">
            <span>{data.total} results</span>
            <div className="flex items-center gap-2">
              <Button size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></Button>
              <span className="tabular-nums">{page} / {pages}</span>
              <Button size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)} aria-label="Next page"><ChevronRight className="h-4 w-4" /></Button>
            </div>
          </div>
        )}
      </Card>

      <FeedbackDrawer id={openId} onClose={() => setOpenId(null)} onChanged={() => reload(true)} />
      <AddFeedbackModal open={adding} onClose={() => setAdding(false)} onAdded={() => { setAdding(false); void reload(); }} />
    </>
  );
}

function AddFeedbackModal({ open, onClose, onAdded }: { open: boolean; onClose: () => void; onAdded: () => void }) {
  const [form, setForm] = useState({ text: "", email: "", name: "", company: "", plan: "", mrr: "", country: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setForm({ ...form, [k]: e.target.value });

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const customer = form.email ? { email: form.email, name: form.name || null, company: form.company || null, plan: form.plan || null, mrr: form.mrr ? Number(form.mrr) : null, country: form.country || null } : null;
      await api(ws("/feedback"), { body: { text: form.text, country: form.country || null, customer } });
      setForm({ text: "", email: "", name: "", company: "", plan: "", mrr: "", country: "" });
      onAdded();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Add feedback" footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" loading={busy} disabled={!form.text.trim()} onClick={save}>Save & analyze</Button></>}>
      <div className="space-y-3">
        <ErrorNote error={error} />
        <label className="block"><Label hint="any language">Feedback</Label><Textarea rows={4} value={form.text} onChange={set("text")} placeholder="Paste a customer quote, call note or review…" /></label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block"><Label>Customer email</Label><Input value={form.email} onChange={set("email")} type="email" /></label>
          <label className="block"><Label>Name</Label><Input value={form.name} onChange={set("name")} /></label>
          <label className="block"><Label>Company</Label><Input value={form.company} onChange={set("company")} /></label>
          <label className="block"><Label>Country</Label><Input value={form.country} onChange={set("country")} /></label>
          <label className="block"><Label>Plan</Label><Input value={form.plan} onChange={set("plan")} /></label>
          <label className="block"><Label>MRR (USD)</Label><Input value={form.mrr} onChange={set("mrr")} type="number" min={0} /></label>
        </div>
        <p className="text-xs text-slate-400">Customer details are optional, but they power revenue-weighted prioritization and let you notify the customer when you ship.</p>
      </div>
    </Modal>
  );
}

export default function FeedbackPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96" />}>
      <FeedbackInbox />
    </Suspense>
  );
}
