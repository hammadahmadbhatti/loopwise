"""Dashboard aggregates, emerging-issue detection and Ask-your-feedback."""

from datetime import datetime, timedelta, timezone


def test_overview_kpis(loaded):
    o = loaded.get("/insights/overview", params={"days": 90}).json()
    k = o["kpis"]
    assert k["feedback"] == 76 and k["languages"] >= 8 and k["countries"] >= 15
    assert k["churn_signals"] >= 3 and k["pending_analysis"] == 0
    assert sum(d["negative"] + d["positive"] + d["neutral"] for d in o["series"]) == 76
    assert o["top_themes"] and o["at_risk"][0]["mrr"] >= o["at_risk"][-1]["mrr"]


def test_emerging_issue_detected(account):
    now = datetime.now(timezone.utc)
    texts = ["The search is broken and returns nothing", "Search returns no results at all",
             "Search results are empty since the update", "Search is broken again, no results"]
    for i, t in enumerate(texts):
        account.post("/feedback", json={"text": t, "created_at": (now - timedelta(days=i % 3)).isoformat()})
    account.post("/feedback", json={"text": "Search used to work fine", "created_at": (now - timedelta(days=40)).isoformat()})
    account.drain()
    o = account.get("/insights/overview").json()
    assert o["emerging"], o["top_themes"]
    assert o["emerging"][0]["this_week"] >= 3


def test_ask_answers_with_citations(loaded):
    r = loaded.post("/insights/ask", json={"question": "What do customers say about billing and double charges?"}).json()
    assert r["retrieved"] > 0 and r["citations"]
    cited = loaded.get(f"/feedback/{r['citations'][0]['id']}").json()
    assert cited["theme"] is not None
    assert "Billing" in r["answer"] or "billing" in r["answer"].lower() or "charge" in r["answer"].lower()


def test_ask_on_empty_workspace(account):
    r = account.post("/insights/ask", json={"question": "Why are users unhappy?"}).json()
    assert r["citations"] == [] and r["retrieved"] == 0


def test_ai_status_and_test_endpoint(account):
    s = account.get("/ai").json()
    assert s["active"]["name"] == "heuristic" and {p["name"] for p in s["providers"]} == {"anthropic", "openai", "ollama", "heuristic"}
    r = account.post("/ai/test", json={"text": "Ich liebe diese App"}).json()
    assert r["result"]["language"] == "de" and r["result"]["sentiment_label"] == "positive"


def test_ask_understands_churn_intent(loaded):
    r = loaded.post("/insights/ask", json={"question": "Which problems make customers want to cancel?"}).json()
    assert r["retrieved"] >= 4
    ids = [c["id"] for c in r["citations"]]
    assert all(loaded.get(f"/feedback/{i}").json()["churn_risk"] for i in ids)


def test_ask_applies_language_and_plan_filters(loaded):
    r = loaded.post("/insights/ask", json={"question": "What are German-speaking customers complaining about?"}).json()
    assert r["retrieved"] >= 3 and all(c["language"] == "de" for c in r["citations"])
    r = loaded.post("/insights/ask", json={"question": "What do Enterprise customers ask for most?"}).json()
    assert r["retrieved"] >= 3
    for c in r["citations"]:
        assert loaded.get(f"/feedback/{c['id']}").json()["customer"]["plan"] == "Enterprise"
