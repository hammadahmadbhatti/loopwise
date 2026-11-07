"use client";

import { MessageSquareQuote, Send, Sparkles } from "lucide-react";
import { useState } from "react";
import { FeedbackDrawer } from "@/components/FeedbackDrawer";
import { Badge, Button, Card, ErrorNote, Input, LanguageBadge, PageHeader, Spinner } from "@/components/ui";
import { api, ws } from "@/lib/api";
import { providerLabel } from "@/lib/format";
import type { AskResult } from "@/lib/types";

const SUGGESTIONS = [
  "Why are customers unhappy this month?",
  "What do enterprise customers ask for most?",
  "What are German-speaking customers complaining about?",
  "Which problems make customers want to cancel?",
  "What do people love about the product?",
];

interface Turn { question: string; result?: AskResult; error?: string }

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);

  async function ask(q: string) {
    const text = q.trim();
    if (text.length < 3 || busy) return;
    setQuestion("");
    setBusy(true);
    setTurns((t) => [{ question: text }, ...t]);
    try {
      const result = await api<AskResult>(ws("/insights/ask"), { body: { question: text } });
      setTurns((t) => [{ question: text, result }, ...t.slice(1)]);
    } catch (e) {
      setTurns((t) => [{ question: text, error: e instanceof Error ? e.message : "Failed" }, ...t.slice(1)]);
    } finally {
      setBusy(false);
    }
  }

  // Render [#123] citations as clickable chips
  function renderAnswer(text: string) {
    return text.split(/(\[#\d+\])/g).map((part, i) => {
      const m = part.match(/^\[#(\d+)\]$/);
      return m ? (
        <button key={i} onClick={() => setOpenId(Number(m[1]))} className="mx-0.5 rounded bg-brand-50 px-1 text-xs font-medium text-brand-700 hover:bg-brand-100">#{m[1]}</button>
      ) : <span key={i}>{part}</span>;
    });
  }

  return (
    <>
      <PageHeader title="Ask your feedback" subtitle="Ask a question in plain language. The answer is grounded in your customers' actual words, with citations you can open." />
      <Card className="p-3">
        <form onSubmit={(e) => { e.preventDefault(); void ask(question); }} className="flex gap-2">
          <div className="relative flex-1">
            <Sparkles className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-brand-500" />
            <Input className="pl-8" placeholder="e.g. What's driving negative sentiment in Brazil?" value={question} onChange={(e) => setQuestion(e.target.value)} />
          </div>
          <Button variant="primary" type="submit" loading={busy} disabled={question.trim().length < 3}><Send className="h-4 w-4" /> Ask</Button>
        </form>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((s) => (
            <button key={s} onClick={() => ask(s)} className="rounded-full border border-slate-200 px-2.5 py-1 text-xs text-slate-600 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-700">{s}</button>
          ))}
        </div>
      </Card>

      <div className="mt-6 space-y-4">
        {turns.map((t, i) => (
          <Card key={turns.length - i} className="p-5">
            <div className="flex items-start gap-2 text-sm font-medium text-slate-900"><MessageSquareQuote className="mt-0.5 h-4 w-4 text-slate-400" />{t.question}</div>
            {!t.result && !t.error && <div className="mt-4 flex items-center gap-2 text-sm text-slate-500"><Spinner /> Reading your feedback…</div>}
            <ErrorNote error={t.error ?? null} />
            {t.result && (
              <div className="mt-3">
                <div className="whitespace-pre-wrap text-[15px] leading-relaxed text-slate-800">{renderAnswer(t.result.answer)}</div>
                {t.result.citations.length > 0 && (
                  <div className="mt-4 space-y-2">
                    <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Sources</div>
                    {t.result.citations.map((c) => (
                      <button key={c.id} onClick={() => setOpenId(c.id)} className="flex w-full items-start gap-2 rounded-lg border border-slate-200 px-3 py-2 text-left text-sm hover:bg-slate-50">
                        <Badge tone="brand">#{c.id}</Badge><LanguageBadge code={c.language} />
                        <span className="flex-1 text-slate-700">{c.translated_text || c.text}</span>
                      </button>
                    ))}
                  </div>
                )}
                {t.result.follow_up_questions.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    {t.result.follow_up_questions.map((f) => <button key={f} onClick={() => ask(f)} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-200">{f}</button>)}
                  </div>
                )}
                <p className="mt-3 text-[11px] text-slate-400">Answered by {providerLabel(t.result.answered_by)} from {t.result.retrieved} relevant pieces of feedback.</p>
              </div>
            )}
          </Card>
        ))}
      </div>
      <FeedbackDrawer id={openId} onClose={() => setOpenId(null)} />
    </>
  );
}
