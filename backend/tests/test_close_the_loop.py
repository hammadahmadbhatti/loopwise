"""Shipping an opportunity drafts a changelog entry and localized customer notifications."""

import email
from pathlib import Path

from app.config import get_settings


def _ship_export(acc):
    theme = next(t for t in acc.get("/themes").json()["items"] if "Export" in t["name"])
    oid = acc.post(f"/themes/{theme['id']}/opportunity").json()["id"]
    acc.patch(f"/opportunities/{oid}", json={"description": "Export any report to CSV or Excel.", "is_public": True})
    r = acc.patch(f"/opportunities/{oid}", json={"status": "shipped"})
    assert r.status_code == 200
    return oid, r.json()


def test_ship_creates_localized_drafts(loaded):
    oid, out = _ship_export(loaded)
    loop = out["close_the_loop"]
    assert loop["notifications_created"] >= 6
    assert {"en", "de", "es"} <= set(loop["languages"])
    notes = loaded.get("/notifications", params={"opportunity_id": oid}).json()["items"]
    de = next(n for n in notes if n["language"] == "de")
    en = next(n for n in notes if n["language"] == "en")
    assert de["subject"].startswith("Jetzt verfügbar") and de["body"].startswith("Hallo ")
    assert en["subject"].startswith("Now live") and "{{name}}" not in en["body"]
    assert all(n["status"] == "draft" for n in notes)
    entry = loaded.get("/changelog").json()[0]
    assert entry["opportunity_id"] == oid and entry["published"] is False
    assert entry["body"].startswith("Export any report to CSV or Excel.")
    assert "Shipped thanks to feedback from" in entry["body"] and "email" not in entry["body"].lower()


def test_reship_is_idempotent(loaded):
    oid, out = _ship_export(loaded)
    loaded.patch(f"/opportunities/{oid}", json={"status": "in_progress"})
    again = loaded.patch(f"/opportunities/{oid}", json={"status": "shipped"}).json()["close_the_loop"]
    assert again["notifications_created"] == 0
    assert len(loaded.get("/changelog").json()) == 1


def test_send_writes_outbox_emails(loaded):
    oid, _ = _ship_export(loaded)
    notes = loaded.get("/notifications", params={"opportunity_id": oid}).json()["items"]
    first = notes[0]
    loaded.patch(f"/notifications/{first['id']}", json={"subject": "Edited subject"})
    result = loaded.post("/notifications/send", json={"opportunity_id": oid}).json()
    assert result == {"sent": len(notes), "failed": 0, "mode": "outbox"}
    eml = Path(get_settings().outbox_dir) / f"workspace-{loaded.wid}" / f"notification-{first['id']}.eml"
    msg = email.message_from_bytes(eml.read_bytes())
    assert msg["Subject"] == "Edited subject" and msg["To"] == first["email"]
    assert msg["Content-Language"] == first["language"]
    assert loaded.patch(f"/notifications/{first['id']}", json={"subject": "late edit"}).status_code == 409
    assert all(n["status"] == "sent" for n in loaded.get("/notifications", params={"opportunity_id": oid}).json()["items"])


def test_published_changelog_and_roadmap_appear_on_portal(loaded, client):
    oid, _ = _ship_export(loaded)
    entry = loaded.get("/changelog").json()[0]
    slug = loaded.get("").json()["slug"]
    assert client.get(f"/api/public/portal/{slug}").json()["changelog"] == []
    loaded.patch(f"/changelog/{entry['id']}", json={"published": True})
    portal = client.get(f"/api/public/portal/{slug}").json()
    assert portal["changelog"][0]["title"] == entry["title"]
    assert portal["roadmap"][0]["id"] == oid and portal["roadmap"][0]["status"] == "shipped"
