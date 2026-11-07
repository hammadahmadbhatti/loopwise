"""Ingestion -> analysis -> themes, end to end on the multilingual sample."""

from collections import Counter

from sqlalchemy import select

from app.models import Feedback


def test_import_analyzes_everything_and_finds_themes(loaded):
    page = loaded.get("/feedback", params={"page_size": 100}).json()
    assert page["total"] == 76
    assert all(f["analysis_status"] == "done" for f in page["items"])
    langs = Counter(f["language"] for f in page["items"])
    assert {"en", "de", "es", "fr", "pt", "it", "nl", "ja"} <= set(langs)

    themes = loaded.get("/themes").json()["items"]
    names = {t["name"] for t in themes}
    assert len(themes) >= 10
    assert any("Dashboard" in n and "Performance" in n for n in names)
    biggest = max(themes, key=lambda t: t["count"])
    assert biggest["count"] >= 8 and len(biggest["languages"]) >= 3  # grouped across languages
    # each theme is internally consistent
    for t in themes:
        detail = loaded.get(f"/themes/{t['id']}").json()
        assert len(detail["feedback"]) == t["count"]


def test_csv_import_maps_customers_and_revenue(loaded):
    customers = loaded.get("/customers", params={"sort": "mrr"}).json()["items"]
    assert customers[0]["mrr"] == 2500 and customers[0]["company"] == "Acme Corp"
    assert any(c["churn_signals"] > 0 for c in loaded.get("/customers", params={"at_risk": True}).json()["items"])


def test_csv_without_text_column_is_rejected(account):
    r = account.post("/feedback/import", files={"file": ("x.csv", b"email,name\na@b.c,A\n", "text/csv")})
    assert r.status_code == 422 and "text column" in r.json()["detail"]


def test_semicolon_csv_and_nps_scale(account):
    raw = "comment;score;arr\nGreat app, love it;10;12000\nTerrible and slow;2;\n".encode()
    assert account.post("/feedback/import", files={"file": ("x.csv", raw, "text/csv")}).json()["imported"] == 2
    account.drain()
    items = account.get("/feedback").json()["items"]
    assert sorted(f["rating"] for f in items) == [1, 5]


def test_duplicates_are_flagged(account):
    for _ in range(2):
        account.post("/feedback", json={"text": "The CSV export button does nothing when I click it on the reports page."})
    account.drain()
    items = sorted(account.get("/feedback").json()["items"], key=lambda f: f["id"])
    assert items[0]["duplicate_of_id"] is None and items[1]["duplicate_of_id"] == items[0]["id"]


def test_filters_search_and_detail(loaded):
    neg = loaded.get("/feedback", params={"sentiment": "negative", "page_size": 100}).json()
    assert neg["total"] > 20 and all(f["sentiment_label"] == "negative" for f in neg["items"])
    de = loaded.get("/feedback", params={"language": "de"}).json()
    assert de["total"] >= 8
    hits = loaded.get("/feedback", params={"q": "Okta"}).json()
    assert hits["total"] == 1
    detail = loaded.get(f"/feedback/{hits['items'][0]['id']}").json()
    assert detail["theme"] is not None and len(detail["similar"]) >= 1


def test_manual_theme_assignment_survives_rediscovery(loaded):
    themes = loaded.get("/themes").json()["items"]
    fid = loaded.get("/feedback", params={"q": "Okta"}).json()["items"][0]["id"]
    target = next(t for t in themes if t["name"] != "Single sign-on")
    loaded.patch(f"/feedback/{fid}", json={"theme_id": target["id"]})
    loaded.post("/themes/discover")
    assert loaded.get(f"/feedback/{fid}").json()["theme"]["id"] == target["id"]


def test_rename_and_merge_themes(loaded):
    themes = loaded.get("/themes").json()["items"]
    a, b = themes[0], themes[1]
    assert loaded.patch(f"/themes/{a['id']}", json={"name": "Renamed by PM"}).json()["name_locked"] is True
    loaded.post("/themes/discover")
    assert any(t["name"] == "Renamed by PM" for t in loaded.get("/themes").json()["items"])
    r = loaded.post(f"/themes/{b['id']}/merge", json={"into_id": a["id"]}).json()
    assert r["moved_feedback"] == b["count"]


def test_reanalyze_requeues(loaded):
    assert loaded.post("/feedback/reanalyze-all").json()["queued"] == 76
    with loaded.client.session_factory() as db:
        assert db.scalar(select(Feedback).where(Feedback.analysis_status == "pending")) is not None
    loaded.drain()
    assert loaded.get("/feedback", params={"page_size": 1}).json()["items"][0]["analysis_status"] == "done"


def test_export_csv(loaded):
    r = loaded.get("/feedback/export.csv")
    assert r.status_code == 200 and r.text.count("\n") >= 77


def test_public_import_template_is_valid(account):
    from pathlib import Path
    template = Path(__file__).resolve().parents[2] / "frontend" / "public" / "loopwise-import-template.csv"
    with open(template, "rb") as fh:
        r = account.post("/feedback/import", files={"file": ("template.csv", fh, "text/csv")})
    assert r.json()["imported"] == 3 and set(r.json()["columns"]) >= {"text", "email", "mrr", "created_at"}
