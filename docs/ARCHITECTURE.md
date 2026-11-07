# Architecture

## Overview

```
                      ┌──────────────── Next.js 16 (port 3000) ─────────────────┐
 Browser  ──────────▶ │ landing · auth · dashboard (/app/*) · portal (/p/slug)   │
                      │ rewrites /api/* ──────────────────────────┐              │
                      └───────────────────────────────────────────┼──────────────┘
 widget.js on any site ── POST /api/public/widget/{key}/feedback ─┤
 CRM / help desk ──────── POST /api/v1/feedback (X-API-Key) ──────┤
                                                                  ▼
                      ┌──────────────── FastAPI (port 8000) ─────────────────────┐
                      │ routers ─▶ services ─▶ SQLAlchemy ─▶ SQLite / PostgreSQL  │
                      │                │                                          │
                      │                └─▶ AIService ─▶ Claude | OpenAI | Ollama  │
                      │                         └──(on failure)──▶ offline engine │
                      │ AnalysisWorker thread: pending feedback ─▶ analyze ─▶     │
                      │   embed ─▶ flag duplicates ─▶ refresh themes              │
                      └───────────────────────────────────────────────────────────┘
```

Intake never waits on AI: feedback is stored with `analysis_status = pending` and the API responds immediately.
The worker claims rows through the database (`pending → processing`), so a crash or restart never loses work
(`processing` rows are re-queued on startup) and failed items retry up to three times.

## Data model

| Table | Purpose |
|---|---|
| `users`, `workspaces`, `memberships` | Accounts, tenants and roles (owner, admin, member). Workspaces hold settings (AI provider, working language, priority weights, portal branding), a public widget key and a hashed server API key. |
| `customers` | Upserted from any channel by email or external id: name, company, country, plan, MRR, preferred language (learned from their feedback). |
| `feedback` | Original text and channel metadata plus AI analysis (language, translation, summary, sentiment, category, urgency, churn risk, keywords, `analyzed_by`), embedding, theme, duplicate link, triage status. |
| `themes` | Discovered clusters: name, description, keywords, `name_locked` (renamed by a human), `archived`. |
| `opportunities` | A problem worth solving: optional theme, manually linked feedback (`opportunity_feedback`), status, public flag, RICE inputs, cached AI brief. |
| `votes` | One per customer per opportunity, from the public portal. |
| `decisions` | Outcome, rationale, author and a JSON snapshot of the evidence and AI recommendation at decision time. |
| `changelog_entries`, `notifications` | Close-the-loop drafts and sent messages (channel, language, which provider localized it). |

Schema changes go through Alembic. `AUTO_MIGRATE=true` (default) upgrades on startup; a test asserts that the
migration and the models never drift, and it passes on SQLite and PostgreSQL.

## Analysis pipeline

1. **Analyze**: the workspace's provider returns a `FeedbackAnalysis` (Pydantic model, enforced through JSON-schema
   structured outputs on every LLM provider).
2. **Embed**: the *working-language* text (translation when there is one) is embedded. Because translation happens
   first, a German and a Spanish complaint about one bug land close together even with simple embeddings.
3. **Duplicates**: cosine similarity above the embedder's `dup_threshold` against recent items marks
   `duplicate_of_id`. Duplicates stay visible but don't inflate counts.
4. **Themes**: see below.

### Embedders

| Embedder | When | Vectors |
|---|---|---|
| OpenAI `text-embedding-3-small` | `OPENAI_API_KEY` set | dense, semantic |
| Ollama `nomic-embed-text` | Ollama running with that model | dense, semantic, local |
| Local | always available | hashed stemmed unigrams and bigrams plus cross-lingual concept features, TF-IDF weighted at query time |

The local embedder stores sparse hashed counts (stable across runs; CRC32, not Python's salted `hash`) and applies
TF-IDF over the current corpus when building a matrix. Each embedder carries its own clustering distance, duplicate
threshold and retrieval floor. Vectors record which embedder produced them and are re-computed when it changes.

### Theme discovery

- Average-linkage **agglomerative clustering** over a precomputed cosine-distance matrix with a distance threshold, so
  the number of themes is discovered rather than guessed (no `k`). Clusters of two or more become themes.
- **Stable identity:** each new cluster is matched to the existing theme with the highest member overlap (Jaccard ≥ 0.3)
  and reuses its id and name, so opportunities linked to a theme survive re-clustering. Themes that lose every member
  are archived unless an opportunity references them.
- **Human overrides win:** feedback moved by hand is `theme_locked` and never moved again; renamed themes keep their name.
- **Naming:** new themes are named by the AI provider from the items closest to the cluster centre plus TF-IDF keywords.
- The newest 3,000 items per workspace are clustered (an O(n²) distance matrix, about 72 MB at that size).
- **Offline quality:** the local embedder's threshold (0.88) was tuned on the 76-item sample (adjusted Rand index 1.00)
  and checked against 20 held-out phrasings it was not tuned on, including unrelated topics (ARI 0.74).

### Emerging issues

Per theme, weekly counts for the last eight weeks. A theme is *emerging* when this week has at least three mentions
and at least twice the average of the four weeks before it.

## Priority score

Each component is normalized to 0..1 *relative to the workspace's open opportunities*, then combined with the
workspace's weights. The API returns every component and its contribution, and the UI shows them, so a ranking is
never a black box.

| Component | Raw signal | Default weight |
|---|---|---|
| Demand | log(1 + unique customers + 0.5 × portal votes) | 30% |
| Revenue at stake | summed MRR of affected customers | 25% |
| Pain | 0.5 × negative sentiment + 0.3 × urgency + 0.2 × share of customers at churn risk | 20% |
| Momentum | 0.5 + 0.5 × tanh(30-day growth in mentions) | 10% |
| Global reach | number of countries | 5% |
| RICE | reach × impact × confidence ÷ effort, only when filled in (otherwise its weight is redistributed) | 10% |

`priority = 100 × Σ(weightᵢ × componentᵢ) / Σ(weightᵢ of the components present)`

## AI decision brief

The brief gets the numbers above plus up to 15 real quotes chosen for balance: the five most negative, the five
from the highest-paying customers, and the five most recent. The response is schema-validated, evidence citations not
in the input are dropped server-side, confidence is clamped to 0..1 and the suggested impact is snapped to the RICE
scale. The offline engine writes a template brief from the same numbers (it never invents figures).

## Close the loop

`status → shipped` drafts one changelog entry (opportunity description plus who asked for it) and one notification
per affected customer with an email: feedback authors in the evidence plus portal voters. The base note is written
once in the working language, then localized once per distinct customer language (not once per customer). The
`{{name}}` placeholder is filled per recipient. Re-shipping never creates duplicates. Nothing is sent until a team
member clicks Send. `EMAIL_MODE=outbox` writes RFC 822 `.eml` files; `EMAIL_MODE=smtp` sends through your server.

## Security

- Passwords: stdlib `scrypt` (N=2¹⁴, r=8, p=1, 16-byte salt). Tokens: HS256 JWT, 7-day expiry, `SECRET_KEY` from env.
- Tenancy: every workspace route resolves membership first. Unknown or foreign workspace ids return **404** (not 403)
  so ids can't be probed. Ids passed in bodies (feedback to link, themes to merge) are re-checked against the workspace.
- Roles: settings, API keys, members and sending emails require owner or admin.
- Server API keys are shown once and stored as SHA-256 hashes; rotating one invalidates the old key immediately.
- Public endpoints: CORS `*` (no cookies or credentials involved), a per-IP sliding-window rate limit, a honeypot
  field, and length limits on every input. The dashboard API only allows the configured origins.
- Prompt injection: feedback is wrapped in `<feedback>` tags and only ever used as data. The model can only answer in
  the fixed JSON schema, and citations are validated against the input.
- The widget renders inside a shadow root with no cookies and no third-party requests.
