# Loopwise

**AI-powered global customer feedback and decision-making platform.**

Loopwise collects customer feedback from every channel and every language, uses AI to turn it into
themes and evidence-ranked opportunities, helps a product team decide what to build (and records why),
then closes the loop by telling each customer, in their own language, when the thing they asked for ships.

```
 Collect                Understand                    Decide                         Close the loop
 ───────                ──────────                    ──────                         ──────────────
 Website widget   ┐     language detection            opportunities ranked by        changelog draft
 Public portal    │     translation                   customers · revenue · pain     localized emails
 CSV import       ├──▶  sentiment · category    ──▶   momentum · reach · RICE  ──▶   (outbox or SMTP)
 Server API       │     urgency · churn risk          AI decision brief              public roadmap
 Inbound email    ┘     themes (semantic clusters)    decision log with evidence     + votes
```

## Features

| Area | What it does |
|---|---|
| **Collection** | Embeddable widget (shadow-DOM, no cookies, honeypot + rate limit), public portal with roadmap voting and changelog, CSV import with automatic column mapping (1–5 or 0–10 ratings, MRR or ARR), `X-API-Key` server API, inbound-email webhook. |
| **AI analysis** | Every message gets language, translation into the workspace's working language, one-line summary, sentiment (−1..1), category, urgency, churn signal and keywords. Runs in a background worker so intake is instant. |
| **Themes** | Embeddings of the *translated* text, average-linkage agglomerative clustering, stable theme identities across re-runs, AI-written theme names, duplicate detection, emerging-issue alerts (week-over-week spikes). |
| **Decision engine** | Opportunities (from a theme or hand-linked feedback) with an explainable 0–100 priority score: demand, revenue at stake, pain, momentum, global reach and optional RICE, with weights per workspace. AI decision brief: problem, affected segments, cited evidence, options with pros/cons, risks, recommendation, confidence and suggested RICE inputs. Decision log snapshots the evidence at the moment of each decision. |
| **Ask your feedback** | Natural-language questions answered from retrieved feedback with `[#id]` citations. Retrieval understands intent (churn, complaints, praise) and filters by plan, language, country and time window named in the question. |
| **Close the loop** | Marking an opportunity *shipped* drafts a changelog entry and one personal email per affected customer (feedback authors + portal voters), localized per customer language. Review, edit, then send via SMTP or to an `.eml` outbox. |
| **Multi-tenant** | Workspaces with owner/admin/member roles; every query is scoped by workspace and cross-tenant ids return 404. |
| **AI providers** | Claude, OpenAI, Ollama (free, local) or the built-in offline engine, selectable per workspace, with automatic fallback to the offline engine on any provider failure. |

## Tech stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, scikit-learn, NumPy, langdetect.
  SQLite for local development, PostgreSQL in production (the full test suite passes on both).
- **AI:** `anthropic` SDK (Claude, structured outputs, per-task effort, server-side refusal fallbacks), `openai` SDK
  (strict JSON-schema outputs, embeddings), Ollama REST API, and a dependency-free offline engine.
- **Frontend:** Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, Recharts, lucide icons.
- **Deploy:** Dockerfiles for both apps, `docker-compose.yml` with Postgres and Caddy (automatic HTTPS).

## Quick start (local)

```bash
# 1. Backend API on :8000
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env          # optional locally: add ANTHROPIC_API_KEY / OPENAI_API_KEY
.venv/bin/python -m uvicorn app.main:app --port 8000
```

```bash
# 2. Web app on :3000 (proxies /api to the backend)
cd frontend
npm install
BACKEND_URL=http://localhost:8000 npm run dev
```

Open http://localhost:3000, create a workspace, then import
[`backend/tests/fixtures/sample_feedback.csv`](backend/tests/fixtures/sample_feedback.csv) (76 messages in 8 languages
from 45 customer accounts) under **Settings → Import**. Analysis runs in the background; themes appear within seconds.

With no API keys at all, everything works on the offline engine. Add a key (or run Ollama) and switch providers under
**Settings → AI provider**, then click **Re-analyze all feedback**.

## Choosing an AI provider

| Provider | Setup | Translation | Cost | Notes |
|---|---|---|---|---|
| Claude | `ANTHROPIC_API_KEY` | ✓ | per token | Default model `claude-opus-5-5`; low effort for classification, high effort for decision briefs. |
| OpenAI | `OPENAI_API_KEY` | ✓ | per token | `gpt-5-mini` + `text-embedding-3-small` (semantic embeddings). |
| Ollama | install Ollama, `ollama pull qwen2.5:7b` (+ `nomic-embed-text`) | ✓ | free | Feedback never leaves your machine. |
| Offline engine | nothing | ✗ | free | Lexicons for EN/DE/ES/FR/PT/IT/NL plus a cross-lingual concept dictionary. |

`AI_PROVIDER=auto` picks Claude → OpenAI → Ollama → offline, whichever is available first. Details in
[docs/AI_PROVIDERS.md](docs/AI_PROVIDERS.md).

## Tests

```bash
cd backend
.venv/bin/python -m pytest                     # 75 tests, SQLite, ~1 minute
TEST_DATABASE_URL=postgresql+psycopg://user@localhost:5432/loopwise_test .venv/bin/python -m pytest   # same suite on Postgres
```

```bash
cd frontend
npx tsc --noEmit && npx eslint . && npx next build
```

The suite covers auth and tenant isolation, roles, the offline engine on multilingual inputs, provider request
contracts (Claude, OpenAI and Ollama with fake clients, so no network or cost), automatic fallback, CSV import,
duplicate detection, theme discovery and stability, priority scoring and weights, RICE, AI briefs that may only cite
real feedback, the decision log, shipping → localized notifications → outbox `.eml` files, the public portal, voting,
the widget (CORS preflight, honeypot, rate limit), API-key ingest, dashboard aggregates, emerging-issue detection,
Ask-your-feedback retrieval, and that Alembic migrations match the models.

## Project layout

```
loopwise/
├── backend/
│   ├── app/
│   │   ├── ai/            provider interface, Claude / OpenAI / Ollama / offline engine, embeddings, prompts
│   │   ├── routers/       auth, workspaces, feedback, customers, themes, opportunities, insights, loop, public
│   │   ├── services/      intake, analysis worker, themes (clustering), scoring, insights, close-the-loop, CSV import
│   │   ├── models.py      SQLAlchemy models
│   │   └── main.py        FastAPI app, CORS, startup migrations + worker
│   ├── alembic/           migrations
│   ├── scripts/           sample-data generator
│   └── tests/             pytest suite + multilingual fixture
├── frontend/
│   ├── app/               landing, auth, dashboard (/app/*), public portal (/p/[slug])
│   ├── components/        UI kit, charts, app shell, feedback drawer
│   ├── lib/               API client, auth context, hooks, types, formatting
│   └── public/widget.js   embeddable website widget
├── deploy/Caddyfile
├── docker-compose.yml
└── docs/                  architecture, AI providers, API, local testing
```

## Honest limitations

- The **offline engine cannot translate**. It still groups feedback across languages through its concept dictionary
  (on the sample set its themes match the ground truth exactly; on held-out phrasings, adjusted Rand index 0.74), but
  quotes stay in the original language. Use Claude, OpenAI or Ollama for translation.
- Claude, OpenAI and Ollama are covered by **contract tests with fake clients**. They were not called live during
  development (no keys were configured), so prompt quality on real models is untested.
- The analysis worker is an **in-process thread**, and the public rate limiter is **in-memory**. Both are right for
  one API instance; running several replicas needs a shared queue and Redis.
- In production (`ENVIRONMENT=production`, set by `docker-compose.yml`) the API **refuses to start** unless
  `SECRET_KEY` is set to 32+ random characters, and Compose requires `POSTGRES_PASSWORD`. No usable secret ships in the repo.
- The Docker/Caddy deployment files follow the setup used for earlier projects but were **not run here** (Docker isn't
  installed on the development machine).

## Documentation

- [Architecture](docs/ARCHITECTURE.md): data model, pipeline, clustering, scoring, security
- [AI providers](docs/AI_PROVIDERS.md): setup, models, prompts, fallback, cost control
- [API](docs/API.md): endpoint reference (interactive OpenAPI docs at `/docs` on the API)
- [Local testing](docs/LOCAL_TESTING.md): manual end-to-end checklist

---

Developed by [Hammad Ahmad](https://www.linkedin.com/in/hammad187/).
