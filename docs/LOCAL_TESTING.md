# Local testing

## Automated

```bash
cd backend && .venv/bin/python -m pytest          # 75 tests on SQLite
cd frontend && npx tsc --noEmit && npx eslint . && npx next build
```

To run the backend suite on PostgreSQL, point `TEST_DATABASE_URL` at an empty database (tables are created and dropped
per test):

```bash
TEST_DATABASE_URL=postgresql+psycopg://user@localhost:5432/loopwise_test .venv/bin/python -m pytest
```

Offline clustering quality can be re-measured with the sample generator's ground truth (`scripts/make_sample_csv.py`
defines which theme each sample message belongs to).

## Local test account

If you ran the manual browser pass, its throwaway login is stored in `docs/LOCAL_TESTING.local.md`. Git ignores that
file (`*.local.md`), so credentials never reach the repository. To start fresh, delete `backend/loopwise.db` and
register a new workspace at `/register`.

## Manual end-to-end checklist

This is the browser pass done before handover, with both servers running (API on 8000/8010, web on 3000/3020):

1. **Sign up** at `/register` → lands on Settings with the welcome note. The provider list shows which AIs are
   available and which one is active.
2. **Try it:** analyze the German sample text. Language `de`, category `feature_request`.
3. **Import** `backend/tests/fixtures/sample_feedback.csv` → "Imported 76", columns auto-mapped. Within seconds all 76
   are analyzed and 12 themes exist.
4. **Overview:** KPIs, sentiment volume chart, categories, top themes with sparklines, an *emerging issue* banner for
   the dashboard-performance spike, customers at risk sorted by MRR.
5. **Themes:** every theme spans several languages; revenue, negative share and churn signals per theme. Rename and
   merge work; renamed names survive *Re-run discovery*.
6. **Make opportunity** from a theme → detail page with the priority breakdown. **Generate brief** → recommendation,
   evidence quotes (clickable), options, risks, suggested RICE (*Apply to RICE*).
7. **Record decision** (build + rationale) → status becomes Planned, entry appears in the Decision log with an
   evidence snapshot.
8. **Mark shipped** → confirmation → banner: changelog entry plus N emails in M languages.
9. **Changelog & outbox:** drafts grouped per opportunity with language badges. Preview, edit, **Send** → `.eml`
   files in `backend/outbox/workspace-<id>/` with `Content-Language` set. Publish the changelog entry.
10. **Portal** `/p/<slug>` (signed out is fine): public roadmap columns, vote (email, deduplicated), submit feedback in
    any language, published changelog.
11. **Widget:** on any other origin (for example the API's `/docs` page), inject
    `<script src="http://localhost:3000/widget.js" data-key="pk_..." data-api="http://localhost:3000"></script>`,
    open it, rate, send → the message arrives with `source=widget`, the page URL and the rating.
12. **Feedback inbox:** filters, search, detail drawer (similar feedback across languages, theme reassignment, link
    to opportunity, re-analyze).
13. **Ask AI:** "Which problems make customers want to cancel?" → only churn-signal feedback cited. "What are
    German-speaking customers complaining about?" → only German feedback.
14. **Mobile (375 px):** no horizontal page scroll; navigation collapses to a select; wide tables scroll inside their card.
