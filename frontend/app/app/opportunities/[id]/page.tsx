"use client";

import { ArrowLeft, Check, Globe2, Megaphone, Sparkles, ThumbsDown, ThumbsUp, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { FeedbackDrawer } from "@/components/FeedbackDrawer";
import { Badge, Button, Card, CardHeader, CategoryBadge, ErrorNote, Input, Label, LanguageBadge, Modal, ProgressBar, Select, SentimentBadge, Skeleton, Textarea, cn } from "@/components/ui";
import { api, ws } from "@/lib/api";
import { COMPONENT_LABEL, RECOMMENDATION_LABEL, languageName, money, providerLabel, relTime, shortDate, STATUS_LABEL } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { OpportunityDetail } from "@/lib/types";

export default function OpportunityPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: o, loading, error, reload, setData } = useApi<OpportunityDetail>(ws(`/opportunities/${id}`));
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [openFeedback, setOpenFeedback] = useState<number | null>(null);
  const [confirmShip, setConfirmShip] = useState(false);
  const [loopNote, setLoopNote] = useState<string | null>(null);

  async function patch(body: Record<string, unknown>, label = "save") {
    setBusy(label);
    setErr(null);
    try {
      const updated = await api<OpportunityDetail>(ws(`/opportunities/${id}`), { method: "PATCH", body });
      setData(updated);
      if (updated.close_the_loop) {
        const c = updated.close_the_loop;
        setLoopNote(`Drafted a changelog entry and ${c.notifications_created} customer email${c.notifications_created === 1 ? "" : "s"} in ${c.languages.map(languageName).join(", ")}. Review and send them in Changelog & outbox.`);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(null);
    }
  }

  async function generateBrief() {
    setBusy("brief");
    setErr(null);
    try {
      const r = await api<{ error: string }>(ws(`/opportunities/${id}/brief`), { method: "POST" });
      if (r.error) setErr(`The AI provider failed, so the offline engine wrote this brief instead (${r.error}).`);
      await reload(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(null);
    }
  }

  if (loading && !o) return <div className="space-y-4"><Skeleton className="h-24" /><Skeleton className="h-64" /></div>;
  if (!o) return <ErrorNote error={error ?? "Not found"} />;
  const m = o.metrics;
  const brief = o.brief;

  return (
    <>
      <Link href="/app/opportunities" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"><ArrowLeft className="h-4 w-4" /> Opportunities</Link>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight">{o.title}</h1>
          {o.description && <p className="mt-1 max-w-3xl text-sm text-slate-600">{o.description}</p>}
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            {o.theme && <Link href={`/app/feedback?theme=${o.theme.id}`}><Badge tone="violet">Theme: {o.theme.name}</Badge></Link>}
            {o.rank && <span>Ranked #{o.rank} of {o.open_count} open</span>}
            {o.shipped_at && <span>Shipped {shortDate(o.shipped_at)}</span>}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1.5 text-sm text-slate-600">
            <input type="checkbox" checked={o.is_public} onChange={(e) => patch({ is_public: e.target.checked }, "public")} className="accent-brand-600" />
            <Globe2 className="h-4 w-4" /> On public roadmap
          </label>
          <Select value={o.status} onChange={(e) => e.target.value === "shipped" ? setConfirmShip(true) : patch({ status: e.target.value }, "status")} aria-label="Status">
            {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
          <Button variant="ghost" aria-label="Delete" onClick={async () => { if (confirm("Delete this opportunity? Its feedback stays.")) { await api(ws(`/opportunities/${id}`), { method: "DELETE" }); router.push("/app/opportunities"); } }}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="space-y-4">
        <ErrorNote error={err} />
        {loopNote && (
          <div className="flex items-center justify-between gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            <span className="flex items-center gap-2"><Megaphone className="h-4 w-4" />{loopNote}</span>
            <Link href="/app/loop" className="shrink-0 font-medium underline">Open outbox</Link>
          </div>
        )}
      </div>

      <div className="mt-4 grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader title="AI decision brief" subtitle={o.brief_at ? `Written by ${providerLabel(o.brief_by)} · ${relTime(o.brief_at)}` : "Summarizes the evidence and recommends what to do"}
              action={<Button size="sm" variant={brief ? "secondary" : "primary"} loading={busy === "brief"} onClick={generateBrief}><Sparkles className="h-3.5 w-3.5" /> {brief ? "Regenerate" : "Generate brief"}</Button>} />
            {!brief ? (
              <p className="px-5 py-6 text-sm text-slate-500">Generate a brief to get an evidence-based recommendation, risks and options, citing real customer quotes.</p>
            ) : (
              <div className="space-y-5 p-5">
                <div className="flex flex-wrap items-center gap-3">
                  <Badge tone={brief.recommendation === "build_now" ? "green" : brief.recommendation === "decline" ? "slate" : brief.recommendation === "investigate" ? "amber" : "brand"} className="px-2 py-1 text-xs">
                    Recommendation: {RECOMMENDATION_LABEL[brief.recommendation]}
                  </Badge>
                  <span className="text-xs text-slate-500">Confidence {Math.round(brief.confidence * 100)}%</span>
                </div>
                <p className="text-[15px] leading-relaxed text-slate-800">{brief.summary}</p>
                <div className="grid gap-4 md:grid-cols-2">
                  <div><h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Problem</h4><p className="mt-1 text-sm text-slate-700">{brief.problem}</p></div>
                  <div><h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Who&apos;s affected</h4><ul className="mt-1 list-disc space-y-0.5 pl-4 text-sm text-slate-700">{brief.affected_segments.map((s, i) => <li key={i}>{s}</li>)}</ul></div>
                </div>
                {brief.evidence.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Evidence</h4>
                    <ul className="mt-2 space-y-2">
                      {brief.evidence.map((e) => (
                        <li key={e.feedback_id}>
                          <button onClick={() => setOpenFeedback(e.feedback_id)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-left hover:border-brand-200 hover:bg-brand-50/30">
                            <p className="text-sm italic text-slate-700">&ldquo;{e.quote}&rdquo;</p>
                            <p className="mt-1 text-xs text-slate-500">#{e.feedback_id} · {e.why_it_matters}</p>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="grid gap-3 md:grid-cols-3">
                  {brief.options.map((op, i) => (
                    <div key={i} className="rounded-lg border border-slate-200 p-3">
                      <div className="text-sm font-medium">{op.title}</div>
                      <ul className="mt-2 space-y-1 text-xs text-slate-600">
                        {op.pros.map((p, j) => <li key={j} className="flex gap-1.5"><ThumbsUp className="mt-0.5 h-3 w-3 shrink-0 text-emerald-500" />{p}</li>)}
                        {op.cons.map((c, j) => <li key={j} className="flex gap-1.5"><ThumbsDown className="mt-0.5 h-3 w-3 shrink-0 text-rose-400" />{c}</li>)}
                      </ul>
                    </div>
                  ))}
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <div><h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Risks</h4><ul className="mt-1 list-disc space-y-0.5 pl-4 text-sm text-slate-700">{brief.risks.map((r, i) => <li key={i}>{r}</li>)}</ul></div>
                  <div><h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Rationale</h4><p className="mt-1 text-sm text-slate-700">{brief.rationale}</p></div>
                </div>
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
                  <span>Suggested RICE inputs: impact {brief.suggested_impact}, confidence {Math.round(brief.suggested_confidence * 100)}%</span>
                  <Button size="sm" loading={busy === "apply"} onClick={() => patch({ impact: brief.suggested_impact, confidence: brief.suggested_confidence }, "apply")}><Check className="h-3.5 w-3.5" /> Apply to RICE</Button>
                </div>
              </div>
            )}
          </Card>

          <Card>
            <CardHeader title={`Evidence (${m.mentions} mentions${m.duplicates ? `, ${m.duplicates} duplicates` : ""})`} subtitle="Feedback from the linked theme plus anything linked manually" />
            <ul className="divide-y divide-slate-100">
              {o.evidence.map((f) => (
                <li key={f.id}>
                  <button onClick={() => setOpenFeedback(f.id)} className="flex w-full items-start gap-3 px-5 py-3 text-left hover:bg-slate-50">
                    <div className="min-w-0 flex-1">
                      <p className="line-clamp-2 text-sm text-slate-800">{f.translated_text || f.text}</p>
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        <LanguageBadge code={f.language} /><SentimentBadge value={f.sentiment} /><CategoryBadge value={f.category} />
                        {f.churn_risk && <Badge tone="red">Churn risk</Badge>}
                        {f.linked && <Badge tone="brand">Linked</Badge>}
                      </div>
                    </div>
                    <div className="w-36 shrink-0 text-right text-xs text-slate-500">
                      <div className="truncate font-medium text-slate-700">{f.customer?.company || f.customer?.name || "Anonymous"}</div>
                      <div>{f.customer?.mrr ? `${money(f.customer.mrr)}/mo` : ""}</div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="p-5">
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-medium text-slate-500">Priority score</span>
              <span className="text-3xl font-semibold tabular-nums">{Math.round(o.priority_score)}<span className="text-base text-slate-400">/100</span></span>
            </div>
            <ul className="mt-4 space-y-3">
              {o.breakdown.map((b) => (
                <li key={b.component}>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-600">{COMPONENT_LABEL[b.component]} <span className="text-slate-400">× {Math.round(b.weight * 100)}%</span></span>
                    <span className="tabular-nums text-slate-500">+{b.contribution}</span>
                  </div>
                  <div className="mt-1"><ProgressBar value={b.value * 100} tone={b.component === "pain" ? "red" : b.component === "revenue" ? "green" : b.component === "momentum" ? "amber" : "brand"} /></div>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-[11px] text-slate-400">Each factor is scaled against your other open opportunities. Weights live in Settings.</p>
          </Card>

          <Card className="p-5">
            <h3 className="text-sm font-semibold">Evidence at a glance</h3>
            <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
              <Fact label="Customers" value={m.customers} />
              <Fact label="Revenue affected" value={`${money(m.mrr)}/mo`} />
              <Fact label="Portal votes" value={m.votes} />
              <Fact label="Churn signals" value={m.churn_risk} tone={m.churn_risk ? "text-rose-600" : undefined} />
              <Fact label="Avg. sentiment" value={m.avg_sentiment?.toFixed(2) ?? "–"} />
              <Fact label="Negative share" value={`${Math.round(m.negative_share * 100)}%`} />
              <Fact label="Last 30 days" value={`${m.recent_30} (${m.growth_pct == null ? "–" : `${m.growth_pct > 0 ? "+" : ""}${Math.round(m.growth_pct)}%`})`} />
              <Fact label="RICE score" value={m.rice_score ?? "–"} />
            </dl>
            {m.countries.length > 0 && <p className="mt-3 text-xs text-slate-500"><span className="font-medium text-slate-600">Countries:</span> {m.countries.join(", ")}</p>}
            {m.languages.length > 0 && <p className="mt-1 text-xs text-slate-500"><span className="font-medium text-slate-600">Languages:</span> {m.languages.map(languageName).join(", ")}</p>}
            {Object.keys(m.plans).length > 0 && <p className="mt-1 text-xs text-slate-500"><span className="font-medium text-slate-600">Plans:</span> {Object.entries(m.plans).map(([p, n]) => `${p} ${n}`).join(", ")}</p>}
          </Card>

          <RiceCard o={o} busy={busy === "rice"} onSave={(v) => patch(v, "rice")} />
          <DecisionCard o={o} onRecorded={() => reload(true)} />
          {(o.notifications.draft + o.notifications.sent + o.notifications.failed) > 0 && (
            <Card className="p-5">
              <h3 className="text-sm font-semibold">Closing the loop</h3>
              <p className="mt-1 text-sm text-slate-600">{o.notifications.sent} sent · {o.notifications.draft} drafts · {o.notifications.failed} failed</p>
              <Link href="/app/loop" className="mt-2 inline-block text-sm font-medium text-brand-600">Review in outbox →</Link>
            </Card>
          )}
        </div>
      </div>

      <FeedbackDrawer id={openFeedback} onClose={() => setOpenFeedback(null)} onChanged={() => reload(true)} />
      <Modal open={confirmShip} onClose={() => setConfirmShip(false)} title="Mark as shipped?"
        footer={<><Button onClick={() => setConfirmShip(false)}>Cancel</Button><Button variant="primary" loading={busy === "status"} onClick={async () => { await patch({ status: "shipped" }, "status"); setConfirmShip(false); }}>Mark shipped</Button></>}>
        <p className="text-sm text-slate-600">Loopwise will draft a changelog entry and a personal email, in their own language, to every customer who asked for this ({m.known_customers} known customers). Nothing is sent until you review it in the outbox.</p>
      </Modal>
    </>
  );
}

function Fact({ label, value, tone }: { label: string; value: React.ReactNode; tone?: string }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className={cn("font-semibold tabular-nums", tone ?? "text-slate-900")}>{value}</dd>
    </div>
  );
}

function RiceCard({ o, busy, onSave }: { o: OpportunityDetail; busy: boolean; onSave: (v: Record<string, number | null>) => void }) {
  const [v, setV] = useState({ reach: o.reach?.toString() ?? "", impact: o.impact?.toString() ?? "", confidence: o.confidence != null ? String(Math.round(o.confidence * 100)) : "", effort: o.effort?.toString() ?? "" });
  const [key, setKey] = useState(`${o.reach}-${o.impact}-${o.confidence}-${o.effort}`);
  const fresh = `${o.reach}-${o.impact}-${o.confidence}-${o.effort}`;
  if (fresh !== key) {
    setKey(fresh);
    setV({ reach: o.reach?.toString() ?? "", impact: o.impact?.toString() ?? "", confidence: o.confidence != null ? String(Math.round(o.confidence * 100)) : "", effort: o.effort?.toString() ?? "" });
  }
  const n = (s: string) => (s.trim() === "" ? null : Number(s));
  return (
    <Card className="p-5">
      <h3 className="text-sm font-semibold">RICE</h3>
      <p className="mt-0.5 text-xs text-slate-500">Optional. Adds a classic RICE factor to the priority score.</p>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <label className="block"><Label hint="users/quarter">Reach</Label><Input type="number" min={0} value={v.reach} onChange={(e) => setV({ ...v, reach: e.target.value })} placeholder={String(o.metrics.customers)} /></label>
        <div>
          <Label>Impact</Label>
          <Select className="w-full" aria-label="Impact" value={v.impact} onChange={(e) => setV({ ...v, impact: e.target.value })}>
            <option value="">–</option><option value="0.25">0.25 minimal</option><option value="0.5">0.5 low</option><option value="1">1 medium</option><option value="2">2 high</option><option value="3">3 massive</option>
          </Select>
        </div>
        <label className="block"><Label hint="%">Confidence</Label><Input type="number" min={0} max={100} value={v.confidence} onChange={(e) => setV({ ...v, confidence: e.target.value })} /></label>
        <label className="block"><Label hint="person-weeks">Effort</Label><Input type="number" min={0.1} step={0.5} value={v.effort} onChange={(e) => setV({ ...v, effort: e.target.value })} /></label>
      </div>
      <Button className="mt-3 w-full" size="sm" loading={busy}
        onClick={() => onSave({ reach: n(v.reach), impact: n(v.impact), confidence: n(v.confidence) == null ? null : n(v.confidence)! / 100, effort: n(v.effort) })}>
        Save RICE
      </Button>
    </Card>
  );
}

function DecisionCard({ o, onRecorded }: { o: OpportunityDetail; onRecorded: () => void }) {
  const [outcome, setOutcome] = useState("build");
  const [rationale, setRationale] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function record() {
    setBusy(true);
    setError(null);
    try {
      await api(ws(`/opportunities/${o.id}/decisions`), { body: { outcome, rationale } });
      setRationale("");
      onRecorded();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card className="p-5">
      <h3 className="text-sm font-semibold">Decision</h3>
      <p className="mt-0.5 text-xs text-slate-500">Recorded with a snapshot of the evidence, so you can revisit why you decided.</p>
      <div className="mt-3 space-y-2">
        <ErrorNote error={error} />
        <Select className="w-full" value={outcome} onChange={(e) => setOutcome(e.target.value)} aria-label="Outcome">
          <option value="build">Build it (moves to Planned)</option>
          <option value="investigate">Investigate further</option>
          <option value="defer">Defer</option>
          <option value="decline">Decline</option>
        </Select>
        <Textarea rows={3} placeholder="Why? e.g. Top revenue risk; 3 enterprise accounts threatening to churn." value={rationale} onChange={(e) => setRationale(e.target.value)} />
        <Button variant="primary" size="sm" className="w-full" disabled={rationale.trim().length < 3} loading={busy} onClick={record}>Record decision</Button>
      </div>
      {o.decisions.length > 0 && (
        <ul className="mt-4 space-y-3 border-t border-slate-100 pt-3">
          {o.decisions.map((d) => (
            <li key={d.id} className="text-sm">
              <div className="flex items-center justify-between">
                <Badge tone={d.outcome === "build" ? "green" : d.outcome === "decline" ? "slate" : "amber"}>{d.outcome}</Badge>
                <span className="text-xs text-slate-400">{d.decided_by} · {relTime(d.created_at)}</span>
              </div>
              <p className="mt-1 text-slate-700">{d.rationale}</p>
              <p className="mt-0.5 text-[11px] text-slate-400">Score then: {String(d.evidence_snapshot.priority_score ?? "–")} · {String(d.evidence_snapshot.customers ?? "–")} customers{d.evidence_snapshot.ai_recommendation ? ` · AI said ${RECOMMENDATION_LABEL[String(d.evidence_snapshot.ai_recommendation)]}` : ""}</p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
