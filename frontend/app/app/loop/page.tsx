"use client";

import { Eye, EyeOff, Mail, Megaphone, Pencil, Plus, Send, Trash2 } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorNote, Input, Label, LanguageBadge, Modal, PageHeader, Skeleton, Tabs, Textarea } from "@/components/ui";
import { api, ws } from "@/lib/api";
import { languageName, providerLabel, relTime, shortDate } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { ChangelogEntry, Notification } from "@/lib/types";

export default function LoopPage() {
  const [tab, setTab] = useState<"outbox" | "changelog">("outbox");
  return (
    <>
      <PageHeader title="Close the loop" subtitle="When you ship what customers asked for, tell them in their own language. Drafts are created automatically when an opportunity is marked shipped." />
      <div className="mb-4"><Tabs value={tab} onChange={setTab} items={[{ value: "outbox", label: "Customer emails" }, { value: "changelog", label: "Changelog" }]} /></div>
      {tab === "outbox" ? <Outbox /> : <Changelog />}
    </>
  );
}

function Outbox() {
  const { data, loading, error, reload } = useApi<{ items: Notification[]; delivery: { mode: string; detail: string } }>(ws("/notifications"));
  const [preview, setPreview] = useState<Notification | null>(null);
  const [editing, setEditing] = useState<Notification | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const groups = useMemo(() => {
    const g = new Map<string, { title: string; oppId: number | null; items: Notification[] }>();
    for (const n of data?.items ?? []) {
      const key = String(n.opportunity_id ?? "none");
      if (!g.has(key)) g.set(key, { title: n.opportunity_title ?? "Other", oppId: n.opportunity_id, items: [] });
      g.get(key)!.items.push(n);
    }
    return [...g.values()];
  }, [data]);

  async function send(oppId: number | null, ids?: number[]) {
    setBusy(`send-${oppId}-${ids?.join(",") ?? "all"}`);
    setErr(null);
    try {
      const r = await api<{ sent: number; failed: number; mode: string }>(ws("/notifications/send"), { body: ids ? { notification_ids: ids } : { opportunity_id: oppId } });
      setMsg(`${r.sent} sent${r.failed ? `, ${r.failed} failed` : ""}${r.mode === "outbox" ? " (written to the outbox folder; set EMAIL_MODE=smtp to deliver)" : ""}.`);
      await reload(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(null);
    }
  }

  if (loading && !data) return <Skeleton className="h-64" />;
  return (
    <div className="space-y-4">
      <ErrorNote error={err || error} />
      {msg && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</div>}
      {data && <p className="flex items-center gap-1.5 text-xs text-slate-500"><Mail className="h-3.5 w-3.5" /> Delivery: {data.delivery.detail}</p>}
      {groups.length === 0 ? (
        <Card><EmptyState icon={<Megaphone className="h-5 w-5" />} title="No customer emails yet" action={<Link href="/app/opportunities" className="text-sm font-medium text-brand-600">Go to opportunities →</Link>}>Mark an opportunity as shipped and Loopwise drafts a personal note to every customer who asked for it.</EmptyState></Card>
      ) : groups.map((g) => {
        const drafts = g.items.filter((n) => n.status !== "sent");
        const langs = [...new Set(g.items.map((n) => n.language))];
        return (
          <Card key={g.title}>
            <CardHeader
              title={g.oppId ? <Link href={`/app/opportunities/${g.oppId}`} className="hover:underline">{g.title}</Link> : g.title}
              subtitle={`${g.items.length} recipients · ${langs.map(languageName).join(", ")} · ${g.items.length - drafts.length} sent`}
              action={drafts.length > 0 && <Button size="sm" variant="primary" loading={busy === `send-${g.oppId}-all`} onClick={() => send(g.oppId)}><Send className="h-3.5 w-3.5" /> Send {drafts.length}</Button>}
            />
            <ul className="divide-y divide-slate-100">
              {g.items.map((n) => (
                <li key={n.id} className="flex flex-wrap items-center gap-3 px-5 py-2.5">
                  <LanguageBadge code={n.language} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-slate-800">{n.subject}</div>
                    <div className="truncate text-xs text-slate-500">{n.email} · {providerLabel(n.localized_by)}</div>
                  </div>
                  {n.status === "sent" ? <Badge tone="green">Sent {relTime(n.sent_at)}</Badge> : n.status === "failed" ? <Badge tone="red" title={n.error}>Failed</Badge> : <Badge tone="amber">Draft</Badge>}
                  <Button size="sm" variant="ghost" onClick={() => setPreview(n)} aria-label="Preview"><Eye className="h-3.5 w-3.5" /></Button>
                  {n.status !== "sent" && <Button size="sm" variant="ghost" onClick={() => setEditing(n)} aria-label="Edit"><Pencil className="h-3.5 w-3.5" /></Button>}
                </li>
              ))}
            </ul>
          </Card>
        );
      })}
      <Modal open={!!preview} onClose={() => setPreview(null)} title="Email preview">
        {preview && (
          <div className="space-y-2 text-sm">
            <div className="text-xs text-slate-500">To: {preview.email} · {languageName(preview.language)}</div>
            <div className="font-medium">{preview.subject}</div>
            <pre className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 font-sans text-sm text-slate-700">{preview.body}</pre>
          </div>
        )}
      </Modal>
      <EditNotification n={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void reload(true); }} />
    </div>
  );
}

function EditNotification({ n, onClose, onSaved }: { n: Notification | null; onClose: () => void; onSaved: () => void }) {
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [last, setLast] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (n && n.id !== last) {
    setLast(n.id);
    setSubject(n.subject);
    setBody(n.body);
  }
  async function save() {
    setBusy(true);
    try {
      await api(ws(`/notifications/${n!.id}`), { method: "PATCH", body: { subject, body } });
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal open={!!n} onClose={onClose} title="Edit email" footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" loading={busy} onClick={save}>Save</Button></>}>
      <div className="space-y-3">
        <ErrorNote error={error} />
        <label className="block"><Label>Subject</Label><Input value={subject} onChange={(e) => setSubject(e.target.value)} /></label>
        <label className="block"><Label>Body</Label><Textarea rows={10} value={body} onChange={(e) => setBody(e.target.value)} /></label>
      </div>
    </Modal>
  );
}

function Changelog() {
  const { data, loading, error, reload } = useApi<ChangelogEntry[]>(ws("/changelog"));
  const [editing, setEditing] = useState<ChangelogEntry | "new" | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  async function toggle(e: ChangelogEntry) {
    setBusy(e.id);
    await api(ws(`/changelog/${e.id}`), { method: "PATCH", body: { published: !e.published } });
    await reload(true);
    setBusy(null);
  }
  async function remove(e: ChangelogEntry) {
    if (!confirm(`Delete "${e.title}"?`)) return;
    await api(ws(`/changelog/${e.id}`), { method: "DELETE" });
    await reload(true);
  }

  if (loading && !data) return <Skeleton className="h-64" />;
  return (
    <div className="space-y-4">
      <ErrorNote error={error} />
      <div className="flex justify-end"><Button variant="primary" onClick={() => setEditing("new")}><Plus className="h-4 w-4" /> New entry</Button></div>
      {!data?.length ? (
        <Card><EmptyState icon={<Megaphone className="h-5 w-5" />} title="No changelog entries">Entries are drafted automatically when you ship an opportunity. Published entries appear on your public portal.</EmptyState></Card>
      ) : data.map((e) => (
        <Card key={e.id} className="p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold">{e.title}</h3>
                {e.published ? <Badge tone="green">Published {shortDate(e.published_at)}</Badge> : <Badge tone="amber">Draft</Badge>}
              </div>
              <p className="mt-0.5 text-xs text-slate-400">{e.written_by && `Drafted by ${providerLabel(e.written_by)} · `}{relTime(e.created_at)}</p>
            </div>
            <div className="flex gap-1">
              <Button size="sm" loading={busy === e.id} onClick={() => toggle(e)}>{e.published ? <><EyeOff className="h-3.5 w-3.5" /> Unpublish</> : <><Eye className="h-3.5 w-3.5" /> Publish</>}</Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(e)} aria-label="Edit"><Pencil className="h-3.5 w-3.5" /></Button>
              <Button size="sm" variant="ghost" onClick={() => remove(e)} aria-label="Delete"><Trash2 className="h-3.5 w-3.5" /></Button>
            </div>
          </div>
          <p className="mt-3 whitespace-pre-wrap text-sm text-slate-700">{e.body}</p>
        </Card>
      ))}
      <EditEntry entry={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void reload(true); }} />
    </div>
  );
}

function EditEntry({ entry, onClose, onSaved }: { entry: ChangelogEntry | "new" | null; onClose: () => void; onSaved: () => void }) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [last, setLast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = entry === "new" ? "new" : entry ? String(entry.id) : null;
  if (key !== last) {
    setLast(key);
    setTitle(entry && entry !== "new" ? entry.title : "");
    setBody(entry && entry !== "new" ? entry.body : "");
  }
  async function save() {
    setBusy(true);
    try {
      if (entry === "new") await api(ws("/changelog"), { body: { title, body } });
      else await api(ws(`/changelog/${entry!.id}`), { method: "PATCH", body: { title, body } });
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal open={!!entry} onClose={onClose} title={entry === "new" ? "New changelog entry" : "Edit entry"} footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" loading={busy} disabled={title.trim().length < 2} onClick={save}>Save</Button></>}>
      <div className="space-y-3">
        <ErrorNote error={error} />
        <label className="block"><Label>Title</Label><Input value={title} onChange={(e) => setTitle(e.target.value)} /></label>
        <label className="block"><Label>Body</Label><Textarea rows={8} value={body} onChange={(e) => setBody(e.target.value)} /></label>
      </div>
    </Modal>
  );
}
