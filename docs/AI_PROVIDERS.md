# AI providers

Every provider implements the same interface (`backend/app/ai/base.py`) and returns the same Pydantic objects, so the
rest of the app never knows which model ran:

| Task | Output | Used for |
|---|---|---|
| `analyze_feedback` | language, translation, summary, sentiment, category, urgency, churn risk, keywords | every incoming message |
| `label_theme` | name, description | each newly discovered theme |
| `decision_brief` | summary, problem, segments, cited evidence, options, risks, recommendation, confidence, suggested RICE | opportunity page |
| `answer_question` | answer with `[#id]` citations, follow-up questions | Ask your feedback |
| `release_note` / `localize` | subject and body | close-the-loop emails |

## Selection and fallback

- Server default: `AI_PROVIDER=auto|anthropic|openai|ollama|heuristic`. `auto` uses the first available of
  Claude → OpenAI → Ollama → offline engine.
- Per workspace: **Settings → AI provider** overrides the server default.
- If the chosen provider is unavailable (no key, Ollama not running), the workspace transparently uses the offline engine.
- If a call fails at runtime (network, rate limit, refusal, invalid JSON), that single task re-runs on the offline
  engine. The result is labelled, for example `heuristic:offline-v1 (fallback from anthropic)`, and the provider's
  error is stored on the feedback (`analysis_error`) and shown in the UI.
- After switching providers, **Re-analyze all feedback** re-queues everything. Embeddings are recomputed automatically
  when the embedder changes.

## Claude (Anthropic)

```bash
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-opus-5-5        # default
```

Implementation (`app/ai/anthropic_provider.py`), using the official `anthropic` Python SDK:

- **Structured outputs:** `output_config.format` with a strict JSON schema generated from the Pydantic model (refs
  inlined, every property required, `additionalProperties: false`). Responses are then validated by Pydantic.
- **Effort per task:** `low` for classification, theme naming, release notes and translation; `medium` for Ask;
  `high` for decision briefs. Adaptive thinking is the model default; no thinking parameter is sent.
- **Refusal fallback:** requests go through `client.beta.messages.create` with `betas=["server-side-fallback-2026-07-01"]`
  and `fallbacks="default"`, so a safety-classifier refusal is retried server-side on Anthropic's recommended model.
  If the whole chain still refuses (`stop_reason == "refusal"`) the task falls back to the offline engine.
- **Prompt caching:** the static system prompts carry `cache_control`; all per-request data is in the user message, so
  the prefix stays byte-stable once prompts exceed the minimum cacheable length.
- **Errors:** authentication, rate-limit, API-status and connection errors are mapped to `ProviderError` (most specific
  first); the SDK already retries 429/5xx twice.

Cost control: the per-message call is the high-volume one and runs at `low` effort. For large historical imports,
the Message Batches API (50% cheaper) would be the next step; it isn't wired in yet.

## OpenAI

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Chat Completions with `response_format = {"type": "json_schema", "strict": true}` using the same generated schemas.
Refusals (`message.refusal`) and length cut-offs raise `ProviderError`. With a key present, OpenAI embeddings are also
used for themes, duplicates and retrieval (`EMBEDDINGS_PROVIDER=auto`).

## Ollama (free, local)

```bash
# install from https://ollama.com, then:
ollama pull qwen2.5:7b          # multilingual, follows JSON schemas well
ollama pull nomic-embed-text    # optional: local semantic embeddings
OLLAMA_BASE_URL=http://localhost:11434
```

Uses `POST /api/chat` with `format` set to the JSON schema and temperature 0, and `POST /api/embed` for embeddings.
Availability checks `/api/tags` (cached for 30 seconds) and tells you exactly which `ollama pull` is missing.
Feedback never leaves your machine, which helps with GDPR-sensitive data.

## Offline engine (built in)

No key, no download, no network. `app/ai/heuristic.py`, `app/ai/concepts.py`, `app/ai/textutil.py`:

- **Language:** `langdetect` with a fixed seed (deterministic).
- **Sentiment:** hand-built lexicons for EN/DE/ES/FR/PT/IT/NL with negation ("not bad"), intensifiers ("super slow"),
  wishes ("would love…", "serait génial" are requests, not praise), and blending with a star rating when there is one.
- **Category, urgency, churn:** multilingual phrase and prefix rules (for example "charged twice", "cobraron dos veces",
  "doppelt abgebucht" → pricing, critical).
- **Cross-lingual concepts:** a small dictionary maps product vocabulary in eight languages to shared concepts
  (`slow`: slow, langsam, lento, lent, 遅…), used as embedding features and for theme names.
- **Briefs, answers, release notes:** templates filled with the real metrics and real quotes. Release notes have native
  templates in seven languages.
- **Cannot translate:** translation stays empty and the UI says so.

## Adding a provider

Subclass `LLMProvider` (`app/ai/llm.py`) and implement two methods:

```python
class MyProvider(LLMProvider):
    name = "myprovider"

    def available(self) -> tuple[bool, str]: ...
    def _structured(self, task: str, system: str, user: str, schema: type[T]) -> T: ...
```

Then register it in `app/ai/registry.py` (`_FACTORIES`, `PROVIDER_ORDER`, `PROVIDER_TITLES`). All task methods,
prompts, citation validation and fallback behaviour come for free.
