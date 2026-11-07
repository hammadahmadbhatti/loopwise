import { ArrowRight, BrainCircuit, Globe2, Inbox, Layers, Megaphone, ShieldCheck, Target } from "lucide-react";
import Link from "next/link";
import { Logo } from "@/components/AppShell";

const PILLARS = [
  { icon: Inbox, title: "Collect from everywhere", text: "Website widget, public feedback portal, CSV imports of surveys and reviews, a server API and inbound email. One inbox." },
  { icon: Globe2, title: "Understand every language", text: "Each message is language-detected, translated, scored for sentiment, categorized and checked for urgency and churn risk." },
  { icon: Layers, title: "Find the themes", text: "Semantic clustering groups what customers mean, not the words they use, so German, Spanish and English reports of one bug become one theme." },
  { icon: Target, title: "Decide with evidence", text: "Opportunities are ranked by customers affected, revenue at stake, pain and momentum. AI decision briefs cite real quotes." },
  { icon: Megaphone, title: "Close the loop", text: "Ship it and Loopwise drafts a changelog entry plus a personal email to every customer who asked, in their own language." },
  { icon: ShieldCheck, title: "Your choice of AI", text: "Claude, OpenAI, or a free local model through Ollama, with a built-in offline engine as automatic fallback." },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-white">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5">
        <Logo />
        <nav className="flex items-center gap-2 text-sm">
          <Link href="/login" className="rounded-lg px-3 py-2 font-medium text-slate-600 hover:bg-slate-100">Sign in</Link>
          <Link href="/register" className="rounded-lg bg-slate-900 px-3.5 py-2 font-medium text-white hover:bg-slate-800">Get started</Link>
        </nav>
      </header>

      <section className="mx-auto max-w-6xl px-4 pb-20 pt-16 text-center md:pt-24">
        <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-brand-100 bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700">
          <BrainCircuit className="h-3.5 w-3.5" /> AI-powered customer feedback and decision-making
        </div>
        <h1 className="mx-auto mt-6 max-w-3xl text-4xl font-semibold tracking-tight text-slate-900 md:text-6xl">
          Hear every customer, in every language. Build what matters.
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-600">
          Loopwise turns scattered feedback from around the world into ranked, evidence-backed product decisions, then tells customers when you&apos;ve shipped what they asked for.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/register" className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-brand-700">
            Create a free workspace <ArrowRight className="h-4 w-4" />
          </Link>
          <Link href="/login" className="rounded-xl border border-slate-200 px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50">Sign in</Link>
        </div>

        <div className="mx-auto mt-16 grid max-w-4xl grid-cols-2 gap-px overflow-hidden rounded-2xl border border-slate-200 bg-slate-200 text-left md:grid-cols-4">
          {[
            ["Collect", "widget · portal · CSV · API · email"],
            ["Understand", "translate · sentiment · themes"],
            ["Decide", "priority score · AI brief · log"],
            ["Close the loop", "changelog · localized emails"],
          ].map(([t, s], i) => (
            <div key={t} className="bg-white p-5">
              <div className="text-xs font-semibold text-brand-600">0{i + 1}</div>
              <div className="mt-1 font-semibold text-slate-900">{t}</div>
              <div className="mt-1 text-xs text-slate-500">{s}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="border-t border-slate-100 bg-slate-50 py-20">
        <div className="mx-auto grid max-w-6xl gap-6 px-4 md:grid-cols-3">
          {PILLARS.map(({ icon: Icon, title, text }) => (
            <div key={title} className="rounded-2xl border border-slate-200 bg-white p-6">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><Icon className="h-5 w-5" /></div>
              <h3 className="mt-4 font-semibold text-slate-900">{title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{text}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-slate-100 py-8 text-center text-xs text-slate-400">
        Loopwise · Developed by{" "}
        <a href="https://www.linkedin.com/in/hammad187/" target="_blank" rel="noreferrer" className="font-medium text-slate-500 hover:text-slate-700">Hammad Ahmad</a>
      </footer>
    </div>
  );
}
