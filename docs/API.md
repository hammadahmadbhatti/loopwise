# API reference

Interactive OpenAPI documentation is served by the backend at **`/docs`** (Swagger UI) and **`/openapi.json`**.
This page is generated from the route table (`app.routes`).

Authentication: `Authorization: Bearer <access_token>` from `/api/auth/login` or `/api/auth/register`, unless noted.
Workspace routes are under `/api/workspaces/{wid}` and return 404 for workspaces you're not a member of.

## Auth

Public (register, login); `/me` needs a token.

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/auth/login` | Login |
| `GET` | `/api/auth/me` | Me |
| `POST` | `/api/auth/register` | Register |

## Workspaces

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/workspaces` | Create |
| `GET` | `/api/workspaces/{wid}` | Get workspace |
| `PATCH` | `/api/workspaces/{wid}` | Update workspace |
| `GET` | `/api/workspaces/{wid}/ai` | Ai status |
| `POST` | `/api/workspaces/{wid}/ai/test` | Ai test |
| `POST` | `/api/workspaces/{wid}/api-key` | Rotate api key |
| `GET` | `/api/workspaces/{wid}/members` | List members |
| `POST` | `/api/workspaces/{wid}/members` | Add member |

## Feedback

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/workspaces/{wid}/feedback` | List feedback |
| `POST` | `/api/workspaces/{wid}/feedback` | Add feedback |
| `GET` | `/api/workspaces/{wid}/feedback/export.csv` | Export csv |
| `POST` | `/api/workspaces/{wid}/feedback/import` | Import feedback |
| `POST` | `/api/workspaces/{wid}/feedback/reanalyze-all` | Re-run analysis for everything, e.g. after switching from the offline engine to Claude. |
| `DELETE` | `/api/workspaces/{wid}/feedback/{fid}` | Delete feedback |
| `GET` | `/api/workspaces/{wid}/feedback/{fid}` | Get feedback |
| `PATCH` | `/api/workspaces/{wid}/feedback/{fid}` | Update feedback |
| `POST` | `/api/workspaces/{wid}/feedback/{fid}/reanalyze` | Reanalyze |

## Customers

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/workspaces/{wid}/customers` | List customers |
| `PATCH` | `/api/workspaces/{wid}/customers/{cid}` | Update customer |

## Themes

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/workspaces/{wid}/themes` | List themes |
| `POST` | `/api/workspaces/{wid}/themes/discover` | Rediscover |
| `GET` | `/api/workspaces/{wid}/themes/{tid}` | Get theme |
| `PATCH` | `/api/workspaces/{wid}/themes/{tid}` | Rename theme |
| `POST` | `/api/workspaces/{wid}/themes/{tid}/merge` | Merge theme |
| `POST` | `/api/workspaces/{wid}/themes/{tid}/opportunity` | Opportunity from theme |

## Decisions

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/workspaces/{wid}/decisions` | Decision log |
| `GET` | `/api/workspaces/{wid}/opportunities` | List opportunities |
| `POST` | `/api/workspaces/{wid}/opportunities` | Add opportunity |
| `DELETE` | `/api/workspaces/{wid}/opportunities/{oid}` | Delete opportunity |
| `GET` | `/api/workspaces/{wid}/opportunities/{oid}` | Get opportunity |
| `PATCH` | `/api/workspaces/{wid}/opportunities/{oid}` | Update opportunity |
| `POST` | `/api/workspaces/{wid}/opportunities/{oid}/brief` | Generate brief |
| `POST` | `/api/workspaces/{wid}/opportunities/{oid}/decisions` | Record decision |
| `POST` | `/api/workspaces/{wid}/opportunities/{oid}/feedback` | Link feedback |
| `DELETE` | `/api/workspaces/{wid}/opportunities/{oid}/feedback/{fid}` | Unlink feedback |

## Insights

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/workspaces/{wid}/insights/ask` | Ask |
| `GET` | `/api/workspaces/{wid}/insights/overview` | Overview |

## Close the loop

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/workspaces/{wid}/changelog` | List changelog |
| `POST` | `/api/workspaces/{wid}/changelog` | Add changelog |
| `DELETE` | `/api/workspaces/{wid}/changelog/{eid}` | Delete changelog |
| `PATCH` | `/api/workspaces/{wid}/changelog/{eid}` | Update changelog |
| `GET` | `/api/workspaces/{wid}/notifications` | List notifications |
| `POST` | `/api/workspaces/{wid}/notifications/send` | Send notifications |
| `PATCH` | `/api/workspaces/{wid}/notifications/{nid}` | Edit notification |

## Public

No authentication. CORS `*`, rate-limited per IP.

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/public/portal/{slug}` | Portal |
| `POST` | `/api/public/portal/{slug}/feedback` | Portal feedback |
| `POST` | `/api/public/portal/{slug}/opportunities/{oid}/vote` | Vote |
| `POST` | `/api/public/widget/{public_key}/feedback` | Widget feedback |
| `POST` | `/api/v1/feedback` | Server-to-server ingestion (CRM, support desk, app backend). Authenticate with the X-API-Key header. |
| `POST` | `/api/v1/inbound-email` | Point an inbound-email webhook (SendGrid Inbound Parse, Postmark, Mailgun routes) here. |

## Meta

No authentication.

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/health` | Health |

## Examples

```bash
# server-to-server ingest
curl -X POST http://localhost:8000/api/v1/feedback \
  -H "X-API-Key: lw_..." -H "Content-Type: application/json" \
  -d '{"text":"Checkout keeps failing","email":"jane@example.com","company":"Acme","plan":"Pro","mrr":299,"country":"Germany"}'

# inbound email webhook (map your provider's fields to from/subject/text)
curl -X POST http://localhost:8000/api/v1/inbound-email \
  -H "X-API-Key: lw_..." -H "Content-Type: application/json" \
  -d '{"from":"ops@example.com","subject":"Export broken","text":"The CSV export fails since Monday."}'
```
