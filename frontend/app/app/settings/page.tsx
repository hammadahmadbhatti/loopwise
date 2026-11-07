"use client";

import { CheckCircle2, Copy, ExternalLink, KeyRound, RefreshCw, Upload, XCircle } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useRef, useState } from "react";
import { Badge, Button, Card, CardHeader, ErrorNote, Input, Label, PageHeader, Select, Skeleton, Textarea, cn } from "@/components/ui";
import { api, ws } from "@/lib/api";
import { COMPONENT_LABEL, languageName, providerLabel } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { AIStatus, Workspace } from "@/lib/types";

function CopyBox({ value, multiline }: { value: string; multiline?: boolean }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="relative">
      <pre className={cn("scroll-thin overflow-x-auto rounded-lg bg-slate-900 p-3 pr-12 font-mono text-xs text-slate-100", !multiline && "whitespace-nowrap")}>{value}</pre>
      <button
        onClick={async () => { await navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
        className="absolute right-2 top-2 rounded-md bg-slate-700 p-1.5 text-slate-200 hover:bg-slate-600" aria-label="Copy"
      >
        {copied ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}

function Settings() {
  const params = useSearchParams();
  const { data: w, reload, setData } = useApi<Workspace>(ws(""));
  const { data: ai, reload: reloadAi } = useApi<AIStatus>(ws("/ai"));
  const [err, setErr] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  async function saveSettings(patch: Record<string, unknown>, label: string, name?: string) {
    setErr(null);
    try {
      const updated = await api<Workspace>(ws(""), { method: "PATCH", body: { ...(name ? { name } : {}), settings: patch } });
      setData(updated);
      setSaved(label);
      setTimeout(() => setSaved(null), 2000);
      if ("ai_provider" in patch) void reloadAi(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    }
  }

  if (!w || !ai) return <div className="space-y-4"><Skeleton className="h-40" /><Skeleton className="h-64" /></div>;
  const isAdmin = w.role === "owner" || w.role === "admin";
  const origin = typeof window !== "undefined" ? window.location.origin : "";

  return (
    <>
      <PageHeader title="Settings" subtitle={`${w.name} · you are ${w.role}`} />
      {params.get("welcome") && (
        <div className="mb-6 rounded-xl border border-brand-100 bg-brand-50 px-5 py-4 text-sm text-brand-900">
          <div className="font-semibold">Welcome to Loopwise 👋</div>
          <p className="mt-1">Start by importing existing feedback (survey exports, app reviews, support tickets) as CSV, or install the website widget. Feedback is analyzed in the background as it arrives.</p>
        </div>
      )}
      <ErrorNote error={err} />
      <div className="mt-4 grid gap-6 lg:grid-cols-2">
        <AISection ai={ai} w={w} isAdmin={isAdmin} onSave={(p) => saveSettings({ ai_provider: p }, "ai")} saved={saved === "ai"} />
        <ImportSection />
        <WidgetSection w={w} origin={origin} isAdmin={isAdmin} onRotated={() => reload(true)} onSave={(p) => saveSettings(p, "portal")} saved={saved === "portal"} />
        <WeightsSection w={w} isAdmin={isAdmin} onSave={(weights) => saveSettings({ priority_weights: weights }, "weights")} saved={saved === "weights"} />
        <WorkspaceSection w={w} isAdmin={isAdmin} onSave={(name, lang) => saveSettings({ working_language: lang }, "workspace", name)} saved={saved === "workspace"} />
        <TeamSection isAdmin={isAdmin} />
      </div>
    </>
  );
}

function SavedTick({ show }: { show: boolean }) {
  return show ? <span className="inline-flex items-center gap-1 text-xs text-emerald-600"><CheckCircle2 className="h-3.5 w-3.5" /> Saved</span> : null;
}

function AISection({ ai, w, isAdmin, onSave, saved }: { ai: AIStatus; w: Workspace; isAdmin: boolean; onSave: (p: string) => void; saved: boolean }) {
  const [text, setText] = useState("Das neue Dashboard ist super, aber der CSV-Export fehlt uns wirklich.");
  const [result, setResult] = useState<{ result: Record<string, unknown>; produced_by: string; error: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [queued, setQueued] = useState<number | null>(null);
  return (
    <Card className="lg:col-span-2" id="ai">
      <CardHeader title="AI provider" subtitle="Choose which AI analyzes feedback, names themes and writes briefs. If a provider fails, the offline engine takes over automatically." action={<SavedTick show={saved} />} />
      <div className="grid gap-6 p-5 lg:grid-cols-2">
        <div className="space-y-3">
          <ul className="space-y-2">
            {ai.providers.map((p) => (
              <li key={p.name} className={cn("flex items-start gap-3 rounded-lg border px-3 py-2.5", ai.active.name === p.name ? "border-brand-200 bg-brand-50/50" : "border-slate-200")}>
                {p.available ? <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-500" /> : <XCircle className="mt-0.5 h-4 w-4 text-slate-300" />}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 text-sm font-medium">{p.title}{ai.active.name === p.name && <Badge tone="brand">Active</Badge>}</div>
                  <div className="text-xs text-slate-500">{p.detail}</div>
                </div>
              </li>
            ))}
          </ul>
          <Label>Use for this workspace</Label>
          <Select className="w-full" aria-label="AI provider for this workspace" disabled={!isAdmin} value={w.settings.ai_provider} onChange={(e) => onSave(e.target.value)}>
            <option value="default">Server default ({ai.server_default})</option>
            <option value="auto">Auto: best available</option>
            <option value="anthropic">Claude (Anthropic)</option>
            <option value="openai">OpenAI</option>
            <option value="ollama">Ollama (free, runs locally)</option>
            <option value="heuristic">Offline engine only</option>
          </Select>
          <p className="text-xs text-slate-500">Now using <span className="font-medium">{providerLabel(`${ai.active.name}:${ai.active.model}`)}</span> ({ai.active.note}). Embeddings: {ai.embeddings.name} · {ai.embeddings.model}. API keys are set on the server (<code>ANTHROPIC_API_KEY</code>, <code>OPENAI_API_KEY</code>, <code>OLLAMA_BASE_URL</code>).</p>
          <div className="flex items-center gap-2">
            <Button size="sm" loading={busy === "re"} onClick={async () => { setBusy("re"); const r = await api<{ queued: number }>(ws("/feedback/reanalyze-all"), { method: "POST" }); setQueued(r.queued); setBusy(null); }}>
              <RefreshCw className="h-3.5 w-3.5" /> Re-analyze all feedback
            </Button>
            {queued !== null && <span className="text-xs text-slate-500">{queued} items queued</span>}
          </div>
        </div>
        <div className="space-y-2">
          <Label>Try it</Label>
          <Textarea rows={3} aria-label="Text to analyze" value={text} onChange={(e) => setText(e.target.value)} />
          <Button size="sm" variant="primary" loading={busy === "test"} onClick={async () => { setBusy("test"); try { setResult(await api(ws("/ai/test"), { body: { text } })); } finally { setBusy(null); } }}>Analyze</Button>
          {result && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs">
              <div className="mb-2 font-medium text-slate-700">{providerLabel(result.produced_by)}{result.error && <span className="ml-2 text-amber-600">({result.error})</span>}</div>
              <dl className="grid grid-cols-[110px_1fr] gap-x-2 gap-y-1 text-slate-600">
                {Object.entries(result.result).map(([k, v]) => (
                  <div key={k} className="contents"><dt className="text-slate-400">{k}</dt><dd className="break-words">{Array.isArray(v) ? v.join(", ") : String(v) || "–"}</dd></div>
                ))}
              </dl>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

function ImportSection() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ imported: number; skipped: number; errors: string[]; columns: Record<string, string> } | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function upload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    const form = new FormData();
    form.append("file", file);
    try {
      setResult(await api(ws("/feedback/import"), { form }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card id="import">
      <CardHeader title="Import feedback (CSV)" subtitle="Survey exports, app-store reviews, support tickets, NPS verbatims." />
      <div className="space-y-3 p-5">
        <p className="text-sm text-slate-600">Only a text column is required (<code>text</code>, <code>feedback</code>, <code>comment</code>, <code>review</code>…). Optional: <code>email</code>, <code>name</code>, <code>company</code>, <code>country</code>, <code>plan</code>, <code>mrr</code> or <code>arr</code>, <code>rating</code> (1–5 or 0–10), <code>created_at</code>, <code>source</code>. <a className="font-medium text-brand-600 hover:underline" href="/loopwise-import-template.csv" download>Download a template</a>.</p>
        <input ref={fileRef} type="file" aria-label="CSV file" accept=".csv,text/csv" className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-700 hover:file:bg-slate-200" />
        <Button variant="primary" loading={busy} onClick={upload}><Upload className="h-4 w-4" /> Import</Button>
        <ErrorNote error={error} />
        {result && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            Imported {result.imported} (skipped {result.skipped}). Columns used: {Object.entries(result.columns).map(([k, v]) => `${k}←${v}`).join(", ")}. Analysis is running in the background.
            {result.errors.length > 0 && <ul className="mt-1 list-disc pl-4 text-xs">{result.errors.map((e) => <li key={e}>{e}</li>)}</ul>}
          </div>
        )}
      </div>
    </Card>
  );
}

function WidgetSection({ w, origin, isAdmin, onRotated, onSave, saved }: { w: Workspace; origin: string; isAdmin: boolean; onRotated: () => void; onSave: (p: Record<string, unknown>) => void; saved: boolean }) {
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const snippet = `<script src="${origin}/widget.js" data-key="${w.public_key}" data-api="${origin}" data-color="${w.settings.brand_color}" async></script>`;
  const curl = `curl -X POST ${origin}/api/v1/feedback \\\n  -H "X-API-Key: ${apiKey ?? "<your API key>"}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"text":"Checkout keeps failing","email":"jane@example.com","company":"Acme","plan":"Pro","mrr":299,"country":"Germany"}'`;
  return (
    <Card id="widget" className="lg:col-span-2">
      <CardHeader title="Collect feedback" subtitle="Website widget, public portal and API. All channels feed the same analysis pipeline." action={<SavedTick show={saved} />} />
      <div className="grid gap-6 p-5 lg:grid-cols-3">
        <div className="space-y-2">
          <h4 className="text-sm font-semibold">Website widget</h4>
          <p className="text-xs text-slate-500">Paste before <code>&lt;/body&gt;</code> on your site or app. Adds a small feedback button.</p>
          <CopyBox value={snippet} multiline />
        </div>
        <div className="space-y-2">
          <h4 className="text-sm font-semibold">Public portal</h4>
          <p className="text-xs text-slate-500">Customers submit ideas, vote on your public roadmap and read the changelog.</p>
          <a href={`/p/${w.slug}`} target="_blank" className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:underline">{origin}/p/{w.slug} <ExternalLink className="h-3.5 w-3.5" /></a>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" disabled={!isAdmin} checked={w.settings.portal_enabled} onChange={(e) => onSave({ portal_enabled: e.target.checked })} className="accent-brand-600" /> Portal enabled
          </label>
          <div className="flex items-center gap-2">
            <Label>Brand color</Label>
            <input type="color" disabled={!isAdmin} value={w.settings.brand_color} onChange={(e) => onSave({ brand_color: e.target.value })} className="h-7 w-10 cursor-pointer rounded border border-slate-200" aria-label="Brand color" />
          </div>
        </div>
        <div className="space-y-2">
          <h4 className="text-sm font-semibold">Server API</h4>
          <p className="text-xs text-slate-500">Send feedback from your CRM, help desk or backend. Inbound email webhooks go to <code>/api/v1/inbound-email</code>.</p>
          {apiKey && <div className="rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">Copy this key now, it won&apos;t be shown again.</div>}
          <CopyBox value={curl} multiline />
          <Button size="sm" disabled={!isAdmin} loading={busy} onClick={async () => { setBusy(true); try { setApiKey((await api<{ api_key: string }>(ws("/api-key"), { method: "POST" })).api_key); onRotated(); } finally { setBusy(false); } }}>
            <KeyRound className="h-3.5 w-3.5" /> {w.api_key_prefix ? "Rotate API key" : "Create API key"}
          </Button>
          {w.api_key_prefix && !apiKey && <p className="text-xs text-slate-400">Current key starts with {w.api_key_prefix}…</p>}
        </div>
      </div>
    </Card>
  );
}

function WeightsSection({ w, isAdmin, onSave, saved }: { w: Workspace; isAdmin: boolean; onSave: (weights: Record<string, number>) => void; saved: boolean }) {
  const [weights, setWeights] = useState(w.settings.priority_weights);
  const total = Object.values(weights).reduce((a, b) => a + b, 0) || 1;
  return (
    <Card id="weights">
      <CardHeader title="Prioritization weights" subtitle="How much each factor counts in the priority score. Only the ratio matters." action={<SavedTick show={saved} />} />
      <div className="space-y-3 p-5">
        {Object.keys(COMPONENT_LABEL).map((k) => (
          <div key={k} className="grid grid-cols-[130px_1fr_44px] items-center gap-3">
            <span className="text-sm text-slate-700">{COMPONENT_LABEL[k]}</span>
            <input type="range" min={0} max={1} step={0.05} disabled={!isAdmin} value={weights[k] ?? 0}
              onChange={(e) => setWeights({ ...weights, [k]: Number(e.target.value) })} className="accent-brand-600" aria-label={COMPONENT_LABEL[k]} />
            <span className="text-right text-xs tabular-nums text-slate-500">{Math.round(((weights[k] ?? 0) / total) * 100)}%</span>
          </div>
        ))}
        <Button size="sm" variant="primary" disabled={!isAdmin} onClick={() => onSave(weights)}>Save weights</Button>
      </div>
    </Card>
  );
}

function WorkspaceSection({ w, isAdmin, onSave, saved }: { w: Workspace; isAdmin: boolean; onSave: (name: string, lang: string) => void; saved: boolean }) {
  const [name, setName] = useState(w.name);
  const [lang, setLang] = useState(w.settings.working_language);
  return (
    <Card>
      <CardHeader title="Workspace" action={<SavedTick show={saved} />} />
      <div className="space-y-3 p-5">
        <label className="block"><Label>Name</Label><Input disabled={!isAdmin} value={name} onChange={(e) => setName(e.target.value)} /></label>
        <div>
          <Label hint="(feedback is translated into this)">Working language</Label>
          <Select className="w-full" aria-label="Working language" disabled={!isAdmin} value={lang} onChange={(e) => setLang(e.target.value)}>
            {["en", "de", "es", "fr", "pt", "it", "nl", "ja"].map((l) => <option key={l} value={l}>{languageName(l)}</option>)}
          </Select>
        </div>
        <Button size="sm" variant="primary" disabled={!isAdmin} onClick={() => onSave(name, lang)}>Save</Button>
      </div>
    </Card>
  );
}

function TeamSection({ isAdmin }: { isAdmin: boolean }) {
  const { data, reload } = useApi<{ id: number; email: string; name: string; role: string }[]>(ws("/members"));
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [error, setError] = useState<string | null>(null);
  return (
    <Card>
      <CardHeader title="Team" subtitle="Teammates need an account first; then add them here." />
      <div className="space-y-3 p-5">
        <ul className="divide-y divide-slate-100 text-sm">
          {data?.map((m) => <li key={m.id} className="flex items-center justify-between py-2"><span>{m.name || m.email} <span className="text-xs text-slate-400">{m.email}</span></span><Badge>{m.role}</Badge></li>)}
        </ul>
        {isAdmin && (
          <div className="flex gap-2">
            <Input aria-label="Teammate email" placeholder="teammate@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            <Select value={role} onChange={(e) => setRole(e.target.value)} aria-label="Role"><option value="member">Member</option><option value="admin">Admin</option></Select>
            <Button onClick={async () => { setError(null); try { await api(ws("/members"), { body: { email, role } }); setEmail(""); void reload(true); } catch (e) { setError(e instanceof Error ? e.message : "Failed"); } }}>Add</Button>
          </div>
        )}
        <ErrorNote error={error} />
      </div>
    </Card>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-64" />}>
      <Settings />
    </Suspense>
  );
}
