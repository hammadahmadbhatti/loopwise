"use client";

import { ChevronUp, MessageSquarePlus, Rocket } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Button, ErrorNote, Input, Label, Modal, Spinner, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { shortDate } from "@/lib/format";

interface Portal {
  name: string;
  title: string;
  brand_color: string;
  roadmap: { id: number; title: string; description: string; status: string; votes: number; shipped_at: string | null }[];
  changelog: { id: number; title: string; body: string; published_at: string | null }[];
}

const COLUMNS = [
  { status: "under_review", label: "Under consideration" },
  { status: "planned", label: "Planned" },
  { status: "in_progress", label: "In progress" },
  { status: "shipped", label: "Shipped" },
];

export default function PortalPage() {
  const { slug } = useParams<{ slug: string }>();
  const [portal, setPortal] = useState<Portal | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [voting, setVoting] = useState<number | null>(null);
  const [email, setEmail] = useState("");
  const [text, setText] = useState("");
  const [fbEmail, setFbEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [voted, setVoted] = useState<Set<number>>(new Set());

  const load = useCallback(async () => {
    try {
      setPortal(await api<Portal>(`/api/public/portal/${slug}`, { auth: false }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Portal not found");
    }
  }, [slug]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial fetch
    void load();
    try {
      setEmail(window.localStorage.getItem("loopwise.portal.email") ?? "");
    } catch { /* storage unavailable */ }
  }, [load]);

  async function submitFeedback(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api(`/api/public/portal/${slug}/feedback`, { body: { text, email: fbEmail || null }, auth: false });
      setSent(true);
      setText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send");
    } finally {
      setBusy(false);
    }
  }

  async function vote(id: number) {
    setBusy(true);
    try {
      await api(`/api/public/portal/${slug}/opportunities/${id}/vote`, { body: { email }, auth: false });
      try { window.localStorage.setItem("loopwise.portal.email", email); } catch { /* ignore */ }
      setVoted(new Set([...voted, id]));
      setVoting(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not vote");
    } finally {
      setBusy(false);
    }
  }

  if (!portal) {
    return <div className="flex min-h-screen items-center justify-center">{error ? <p className="text-sm text-slate-500">{error}</p> : <Spinner className="h-6 w-6" />}</div>;
  }
  const color = portal.brand_color;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-10">
          <div className="text-sm font-medium" style={{ color }}>{portal.name}</div>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">{portal.title}</h1>
          <p className="mt-2 max-w-2xl text-slate-600">Tell us what would make the product better, vote on ideas, and see what we&apos;ve shipped. Write in any language.</p>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl gap-8 px-4 py-8 lg:grid-cols-[1fr_340px]">
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Roadmap</h2>
          {portal.roadmap.length === 0 ? <p className="text-sm text-slate-500">Nothing on the public roadmap yet.</p> : (
            <div className="grid gap-4 md:grid-cols-2">
              {COLUMNS.map((col) => {
                const items = portal.roadmap.filter((r) => r.status === col.status);
                if (!items.length) return null;
                return (
                  <div key={col.status}>
                    <div className="mb-2 text-xs font-semibold text-slate-500">{col.label}</div>
                    <ul className="space-y-2">
                      {items.map((r) => (
                        <li key={r.id} className="flex gap-3 rounded-xl border border-slate-200 bg-white p-3">
                          <button
                            onClick={() => (email ? vote(r.id) : setVoting(r.id))}
                            disabled={voted.has(r.id) || r.status === "shipped"}
                            className="flex h-12 w-11 shrink-0 flex-col items-center justify-center rounded-lg border text-xs font-semibold transition disabled:opacity-60"
                            style={{ borderColor: voted.has(r.id) ? color : "#e2e8f0", color: voted.has(r.id) ? color : "#475569" }}
                            aria-label={`Vote for ${r.title}`}
                          >
                            <ChevronUp className="h-4 w-4" />{r.votes}
                          </button>
                          <div className="min-w-0">
                            <div className="text-sm font-medium">{r.title}</div>
                            {r.description && <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">{r.description}</p>}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          )}

          <h2 className="mb-3 mt-10 text-sm font-semibold uppercase tracking-wide text-slate-500">Changelog</h2>
          {portal.changelog.length === 0 ? <p className="text-sm text-slate-500">No updates published yet.</p> : (
            <ol className="space-y-4">
              {portal.changelog.map((c) => (
                <li key={c.id} className="rounded-xl border border-slate-200 bg-white p-4">
                  <div className="flex items-center gap-2 text-xs text-slate-500"><Rocket className="h-3.5 w-3.5" style={{ color }} />{shortDate(c.published_at)}</div>
                  <h3 className="mt-1 font-semibold">{c.title}</h3>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">{c.body}</p>
                </li>
              ))}
            </ol>
          )}
        </section>

        <aside>
          <form onSubmit={submitFeedback} className="sticky top-6 space-y-3 rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-center gap-2 font-semibold"><MessageSquarePlus className="h-4 w-4" style={{ color }} /> Share feedback</div>
            {sent ? (
              <div className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">Thank you! Our team reads every message.
                <button type="button" className="mt-1 block text-xs underline" onClick={() => setSent(false)}>Send another</button>
              </div>
            ) : <>
              <ErrorNote error={error} />
              <Textarea required minLength={3} rows={5} placeholder="What should we improve? Any language is fine." value={text} onChange={(e) => setText(e.target.value)} />
              <label className="block"><Label hint="(optional, so we can tell you when it ships)">Email</Label><Input type="email" value={fbEmail} onChange={(e) => setFbEmail(e.target.value)} /></label>
              <Button type="submit" loading={busy} className="w-full text-white" style={{ background: color }}>Send feedback</Button>
            </>}
          </form>
        </aside>
      </main>
      <footer className="pb-8 text-center text-xs text-slate-400">Powered by Loopwise</footer>

      <Modal open={voting !== null} onClose={() => setVoting(null)} title="Vote for this idea"
        footer={<><Button onClick={() => setVoting(null)}>Cancel</Button><Button variant="primary" loading={busy} disabled={!email.includes("@")} onClick={() => vote(voting!)}>Vote</Button></>}>
        <Label hint="(we'll email you when it ships)">Your email</Label>
        <Input type="email" aria-label="Your email" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />
      </Modal>
    </div>
  );
}
