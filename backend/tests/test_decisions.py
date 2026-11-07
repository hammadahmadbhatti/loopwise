"""Decision engine: opportunities, explainable priority, AI brief, decision log."""


def _theme(acc, name):
    """Find a theme by (part of) its auto-generated name."""
    first = name.split(" & ")[0]
    return next(t for t in acc.get("/themes").json()["items"] if first in t["name"])


def test_opportunity_from_theme_has_evidence_and_score(loaded):
    theme = _theme(loaded, "Dashboard & Performance")
    r = loaded.post(f"/themes/{theme['id']}/opportunity")
    assert r.status_code == 201
    oid = r.json()["id"]
    assert loaded.post(f"/themes/{theme['id']}/opportunity").json() == {"id": oid, "existing": True}
    opp = loaded.get(f"/opportunities/{oid}").json()
    m = opp["metrics"]
    assert m["mentions"] == theme["count"] and m["customers"] >= 5 and m["mrr"] > 0
    assert len(m["countries"]) >= 4 and m["negative_share"] > 0.8
    assert 0 <= opp["priority_score"] <= 100
    assert {b["component"] for b in opp["breakdown"]} >= {"demand", "revenue", "pain", "momentum", "reach"}
    assert opp["rank"] == 1 and len(opp["evidence"]) == theme["count"]


def test_priority_reflects_evidence(loaded):
    big = _theme(loaded, "Dashboard & Performance")
    small = min(loaded.get("/themes").json()["items"], key=lambda t: (t["count"], -(t["avg_sentiment"] or 0)))
    o_big = loaded.post(f"/themes/{big['id']}/opportunity").json()["id"]
    o_small = loaded.post(f"/themes/{small['id']}/opportunity").json()["id"]
    ranked = [o["id"] for o in loaded.get("/opportunities").json()["items"]]
    assert ranked.index(o_big) < ranked.index(o_small)


def test_weights_change_ranking(loaded):
    perf = loaded.post(f"/themes/{_theme(loaded, 'Dashboard & Performance')['id']}/opportunity").json()["id"]
    praise_like = next(t for t in loaded.get("/themes").json()["items"] if (t["avg_sentiment"] or 0) > 0.5)
    happy = loaded.post(f"/themes/{praise_like['id']}/opportunity").json()["id"]
    loaded.patch("", json={"settings": {"priority_weights": {"pain": 1.0, "demand": 0, "revenue": 0, "momentum": 0, "reach": 0, "rice": 0}}})
    scores = {o["id"]: o["priority_score"] for o in loaded.get("/opportunities").json()["items"]}
    assert scores[perf] > scores[happy]


def test_rice_fields_feed_the_score(loaded):
    oid = loaded.post(f"/themes/{_theme(loaded, 'Dashboard & Performance')['id']}/opportunity").json()["id"]
    r = loaded.patch(f"/opportunities/{oid}", json={"reach": 400, "impact": 2, "confidence": 0.8, "effort": 4})
    assert r.json()["metrics"]["rice_score"] == 160.0
    assert any(b["component"] == "rice" for b in r.json()["breakdown"])
    assert loaded.patch(f"/opportunities/{oid}", json={"impact": 7}).status_code == 422


def test_manual_opportunity_with_linked_feedback(loaded):
    ids = [f["id"] for f in loaded.get("/feedback", params={"q": "Slack"}).json()["items"]]
    oid = loaded.post("/opportunities", json={"title": "Slack alerts", "feedback_ids": ids}).json()["id"]
    opp = loaded.get(f"/opportunities/{oid}").json()
    assert opp["metrics"]["mentions"] == len(ids) and all(e["linked"] for e in opp["evidence"])
    assert loaded.delete(f"/opportunities/{oid}/feedback/{ids[0]}").status_code == 204
    assert loaded.get(f"/opportunities/{oid}").json()["metrics"]["mentions"] == len(ids) - 1


def test_ai_brief_offline_cites_only_real_feedback(loaded):
    oid = loaded.post(f"/themes/{_theme(loaded, 'Dashboard & Performance')['id']}/opportunity").json()["id"]
    r = loaded.post(f"/opportunities/{oid}/brief")
    assert r.status_code == 200
    brief = r.json()["brief"]
    evidence_ids = {e["id"] for e in loaded.get(f"/opportunities/{oid}").json()["evidence"]}
    assert brief["evidence"] and {e["feedback_id"] for e in brief["evidence"]} <= evidence_ids
    assert brief["recommendation"] in ("build_now", "build_later", "investigate", "decline")
    assert "customers" in brief["summary"] and r.json()["brief_by"].startswith("heuristic")


def test_brief_requires_evidence(account):
    oid = account.post("/opportunities", json={"title": "Empty idea"}).json()["id"]
    assert account.post(f"/opportunities/{oid}/brief").status_code == 422


def test_decision_log_snapshots_evidence(loaded):
    oid = loaded.post(f"/themes/{_theme(loaded, 'Dashboard & Performance')['id']}/opportunity").json()["id"]
    loaded.post(f"/opportunities/{oid}/brief")
    d = loaded.post(f"/opportunities/{oid}/decisions", json={"outcome": "build", "rationale": "Top revenue risk this quarter"})
    assert d.status_code == 201
    snap = d.json()["evidence_snapshot"]
    assert snap["customers"] >= 5 and snap["ai_recommendation"] in ("build_now", "build_later", "investigate", "decline")
    assert loaded.get(f"/opportunities/{oid}").json()["status"] == "planned"
    log = loaded.get("/decisions").json()
    assert "Dashboard" in log[0]["opportunity_title"] and log[0]["decided_by"] == "Owner"
