"""Widget, public portal, voting, API-key ingest and abuse protection."""


def test_widget_submission_is_analyzed(client, account):
    pk = account.get("").json()["public_key"]
    r = client.post(f"/api/public/widget/{pk}/feedback", json={"text": "Das Hochladen von Dateien stürzt ständig ab!", "email": "kunde@firma.example.com", "rating": 1, "page_url": "https://app.example/upload"}, headers={"Origin": "https://customer-site.example"})
    assert r.status_code == 201 and r.headers["access-control-allow-origin"] == "*"
    account.drain()
    fb = account.get("/feedback").json()["items"][0]
    assert fb["source"] == "widget" and fb["language"] == "de" and fb["category"] == "bug"
    assert fb["customer"]["email"] == "kunde@firma.example.com" and fb["page_url"].endswith("/upload")


def test_widget_preflight_allows_any_origin(client, account):
    pk = account.get("").json()["public_key"]
    r = client.options(f"/api/public/widget/{pk}/feedback", headers={"Origin": "https://x.example", "Access-Control-Request-Method": "POST"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "*"


def test_honeypot_and_unknown_key(client, account):
    pk = account.get("").json()["public_key"]
    assert client.post(f"/api/public/widget/{pk}/feedback", json={"text": "buy cheap stuff", "website": "spam.example"}).json() == {"ok": True}
    assert account.get("/feedback").json()["total"] == 0
    assert client.post("/api/public/widget/pk_nope/feedback", json={"text": "hello there"}).status_code == 404


def test_rate_limit(client, account, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "public_rate_limit", 3)
    pk = account.get("").json()["public_key"]
    codes = [client.post(f"/api/public/widget/{pk}/feedback", json={"text": f"message number {i}"}).status_code for i in range(5)]
    assert codes == [201, 201, 201, 429, 429]


def test_portal_feedback_votes_and_privacy(client, account):
    slug = account.get("").json()["slug"]
    public_opp = account.post("/opportunities", json={"title": "Dark mode", "is_public": True}).json()["id"]
    private_opp = account.post("/opportunities", json={"title": "Secret pricing change"}).json()["id"]
    portal = client.get(f"/api/public/portal/{slug}").json()
    assert [o["id"] for o in portal["roadmap"]] == [public_opp]
    v1 = client.post(f"/api/public/portal/{slug}/opportunities/{public_opp}/vote", json={"email": "fan@example.com"}).json()
    v2 = client.post(f"/api/public/portal/{slug}/opportunities/{public_opp}/vote", json={"email": "FAN@example.com"}).json()
    assert v1 == {"votes": 1, "already_voted": False} and v2 == {"votes": 1, "already_voted": True}
    assert client.post(f"/api/public/portal/{slug}/opportunities/{private_opp}/vote", json={"email": "x@example.com"}).status_code == 404
    assert client.post(f"/api/public/portal/{slug}/feedback", json={"text": "Please add dark mode"}).status_code == 201
    opp = account.get(f"/opportunities/{public_opp}").json()
    assert opp["metrics"]["votes"] == 1 and opp["metrics"]["customers"] == 1
    account.patch("", json={"settings": {"portal_enabled": False}})
    assert client.get(f"/api/public/portal/{slug}").status_code == 404


def test_api_key_ingest_and_inbound_email(client, account):
    assert client.post("/api/v1/feedback", json={"text": "x"}).status_code == 401
    key = account.post("/api-key").json()["api_key"]
    assert account.get("").json()["api_key_prefix"] == key[:10]
    r = client.post("/api/v1/feedback", headers={"X-API-Key": key}, json={"text": "Invoices are wrong again", "email": "cfo@bigco.example.com", "company": "BigCo", "plan": "Enterprise", "mrr": 3000, "country": "Germany"})
    assert r.status_code == 201
    r = client.post("/api/v1/inbound-email", headers={"X-API-Key": key}, json={"from": "ops@bigco.example.com", "subject": "Export broken", "text": "The CSV export fails since Monday."})
    assert r.status_code == 201
    customers = account.get("/customers").json()["items"]
    assert customers[0]["company"] == "BigCo" and customers[0]["mrr"] == 3000
    assert {f["source"] for f in account.get("/feedback").json()["items"]} == {"api", "email"}
    old = key
    account.post("/api-key")
    assert client.post("/api/v1/feedback", headers={"X-API-Key": old}, json={"text": "x"}).status_code == 401
