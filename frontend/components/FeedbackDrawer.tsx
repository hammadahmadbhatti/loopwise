"use client";

import { Archive, CheckCircle2, Languages, Link2, RefreshCw, Star } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ws } from "@/lib/api";
import { languageName, money, providerLabel, relTime } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { FeedbackDetail, Opportunity, Theme } from "@/lib/types";
import { Badge, Button, CategoryBadge, Drawer, ErrorNote, LanguageBadge, Select, SentimentBadge, Spinner, StatusBadge, UrgencyBadge } from "./ui";

export function FeedbackDrawer({ id, onClose, onChanged }: { id: number | null; onClose: () => void; onChanged?: () => void }) {
  const { data: fb, loading, reload, error } = useApi<FeedbackDetail>(id ? ws(`/feedback/${id}`) : null);
  const { data: themes } = useApi<{ items: Theme[] }>(id ? ws("/themes") : null);
  const { data: opps } = useApi<{ items: Opportunity[] }>(id ? ws("/opportunities") : null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [linkTo, setLinkTo] = useState("");

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset local UI state when switching items
    setErr(null);
    setLinkTo("");
  }, [id]);

  async function act(label: string, fn: () => Promise<unknown>) {
    setBusy(label);
    setErr(null);
    try {
      await fn();
      await reload(true);
      onChanged?.();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Drawer open={id !== null} onClose={onClose} title={fb ? `Feedback #${fb.id}` : "Feedback"}>
      {loading && !fb ? (
        <div className="flex justify-center p-10"><Spinner /></div>
      ) : error ? (
        <div className="p-5"><ErrorNote error={error} /></div>
      ) : fb ? (
        <div className="space-y-6 p-5">
          <ErrorNote error={err} />
          <section>
            <div className="mb-2 flex flex-wrap items-center gap-1.5">
              <LanguageBadge code={fb.language} />
              <SentimentBadge value={fb.sentiment} />
              <CategoryBadge value={fb.category} />
              <UrgencyBadge value={fb.urgency} />
              {fb.churn_risk && <Badge tone="red">Churn risk</Badge>}
              {fb.duplicate_of_id && <Badge tone="amber">Duplicate of #{fb.duplicate_of_id}</Badge>}
              {fb.rating && <Badge tone="amber"><Star className="h-3 w-3" /> {fb.rating}/5</Badge>}
            </div>
            <blockquote className="whitespace-pre-wrap rounded-lg border-l-4 border-brand-200 bg-slate-50 px-4 py-3 text-[15px] leading-relaxed text-slate-800">{fb.text}</blockquote>
            {fb.translated_text ? (
              <div className="mt-3 rounded-lg border border-sky-100 bg-sky-50/60 px-4 py-3">
                <div className="mb-1 flex items-center gap-1.5 text-xs font-medium text-sky-700"><Languages className="h-3.5 w-3.5" /> Translated from {languageName(fb.language)}</div>
                <p className="text-sm text-slate-700">{fb.translated_text}</p>
              </div>
            ) : fb.language && fb.language !== "en" && fb.analyzed_by.startsWith("heuristic") ? (
              <p className="mt-2 text-xs text-slate-500">The offline engine doesn&apos;t translate. Switch to Claude, OpenAI or a local Ollama model in Settings, then re-analyze.</p>
            ) : null}
            {fb.summary && <p className="mt-3 text-sm text-slate-600"><span className="font-medium text-slate-700">Summary:</span> {fb.summary}</p>}
            {fb.keywords.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">{fb.keywords.map((k) => <Badge key={k}>{k}</Badge>)}</div>
            )}
            <p className="mt-3 text-xs text-slate-400">
              {fb.source} · {relTime(fb.created_at)}{fb.analyzed_by && ` · analyzed by ${providerLabel(fb.analyzed_by)}`}
              {fb.page_url && <> · <a className="underline" href={fb.page_url} target="_blank" rel="noreferrer">page</a></>}
            </p>
            {fb.analysis_error && <p className="mt-1 text-xs text-amber-600">Provider note: {fb.analysis_error}</p>}
          </section>

          {fb.customer && (
            <section className="rounded-lg border border-slate-200 p-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Customer</div>
              <div className="mt-1 text-sm font-medium">{fb.customer.name || fb.customer.email}</div>
              <div className="text-sm text-slate-500">
                {[fb.customer.company, fb.customer.plan && `${fb.customer.plan} plan`, fb.customer.mrr ? `${money(fb.customer.mrr)}/mo` : null, fb.customer.country].filter(Boolean).join(" · ")}
              </div>
              {fb.customer.email && <div className="mt-0.5 text-xs text-slate-400">{fb.customer.email}</div>}
            </section>
          )}

          <section className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Theme</div>
            <div className="flex items-center gap-2">
              <Select
                className="flex-1"
                value={fb.theme?.id ?? ""}
                onChange={(e) => act("theme", () => api(ws(`/feedback/${fb.id}`), { method: "PATCH", body: e.target.value ? { theme_id: Number(e.target.value) } : { clear_theme: true } }))}
                aria-label="Theme"
              >
                <option value="">No theme</option>
                {themes?.items.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </Select>
              {busy === "theme" && <Spinner />}
            </div>
            {fb.theme_locked && <p className="text-xs text-slate-400">Set manually; automatic theme discovery won&apos;t move it.</p>}
          </section>

          <section className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Opportunities</div>
            {fb.opportunities.length === 0 && <p className="text-sm text-slate-500">Not linked to an opportunity yet.</p>}
            {fb.opportunities.map((o) => (
              <Link key={o.id} href={`/app/opportunities/${o.id}`} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50">
                {o.title} <StatusBadge status={o.status} />
              </Link>
            ))}
            <div className="flex items-center gap-2">
              <Select className="flex-1" value={linkTo} onChange={(e) => setLinkTo(e.target.value)} aria-label="Link to opportunity">
                <option value="">Link to an opportunity…</option>
                {opps?.items.filter((o) => !fb.opportunities.some((x) => x.id === o.id)).map((o) => <option key={o.id} value={o.id}>{o.title}</option>)}
              </Select>
              <Button size="sm" disabled={!linkTo} loading={busy === "link"} onClick={() => act("link", () => api(ws(`/opportunities/${linkTo}/feedback`), { body: { feedback_ids: [fb.id] } }))}>
                <Link2 className="h-3.5 w-3.5" /> Link
              </Button>
            </div>
          </section>

          {fb.similar.length > 0 && (
            <section className="space-y-2">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Similar feedback</div>
              <ul className="space-y-1.5">
                {fb.similar.map((s) => (
                  <li key={s.id} className="flex items-start gap-2 text-sm text-slate-600">
                    <LanguageBadge code={s.language} />
                    <span className="flex-1">{s.summary}</span>
                    <span className="text-xs tabular-nums text-slate-400">{Math.round(s.similarity * 100)}%</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="flex flex-wrap gap-2 border-t border-slate-100 pt-4">
            {fb.status !== "reviewed" && (
              <Button size="sm" loading={busy === "reviewed"} onClick={() => act("reviewed", () => api(ws(`/feedback/${fb.id}`), { method: "PATCH", body: { status: "reviewed" } }))}>
                <CheckCircle2 className="h-3.5 w-3.5" /> Mark reviewed
              </Button>
            )}
            {fb.status !== "archived" ? (
              <Button size="sm" variant="ghost" loading={busy === "archive"} onClick={() => act("archive", () => api(ws(`/feedback/${fb.id}`), { method: "PATCH", body: { status: "archived" } }))}>
                <Archive className="h-3.5 w-3.5" /> Archive
              </Button>
            ) : (
              <Button size="sm" variant="ghost" onClick={() => act("unarchive", () => api(ws(`/feedback/${fb.id}`), { method: "PATCH", body: { status: "new" } }))}>Restore</Button>
            )}
            <Button size="sm" variant="ghost" loading={busy === "reanalyze"} onClick={() => act("reanalyze", () => api(ws(`/feedback/${fb.id}/reanalyze`), { method: "POST" }))}>
              <RefreshCw className="h-3.5 w-3.5" /> Re-analyze
            </Button>
          </section>
        </div>
      ) : null}
    </Drawer>
  );
}
