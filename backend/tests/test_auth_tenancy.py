from tests.conftest import Account


def test_register_login_me(client):
    acc = Account(client, "ana@example.com", "Ana Co")
    r = client.post("/api/auth/login", json={"email": "ANA@example.com", "password": "correct-horse-1"})
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).json()
    assert me["email"] == "ana@example.com"
    assert me["workspaces"][0]["id"] == acc.wid and me["workspaces"][0]["role"] == "owner"


def test_wrong_password_and_duplicate_email(client):
    Account(client, "bo@example.com", "Bo Co")
    assert client.post("/api/auth/login", json={"email": "bo@example.com", "password": "nope-nope"}).status_code == 401
    r = client.post("/api/auth/register", json={"email": "bo@example.com", "password": "another-pass", "workspace_name": "X Co"})
    assert r.status_code == 409


def test_requires_token(client):
    acc = Account(client, "cy@example.com", "Cy Co")
    assert client.get(f"{acc.base}/feedback").status_code == 401
    assert client.get(f"{acc.base}/feedback", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_workspaces_are_isolated(client):
    a = Account(client, "a@example.com", "Tenant A")
    b = Account(client, "b@example.com", "Tenant B")
    fid = a.post("/feedback", json={"text": "Secret feedback for tenant A"}).json()["id"]
    # B cannot see A's workspace, list, or item, even by guessing ids
    assert client.get(f"{a.base}/feedback", headers=b.headers).status_code == 404
    assert client.get(f"{b.base}/feedback/{fid}", headers=b.headers).status_code == 404
    assert b.get("/feedback").json()["total"] == 0
    # and cannot link A's feedback into B's opportunity
    opp = b.post("/opportunities", json={"title": "B idea", "feedback_ids": [fid]}).json()
    assert opp["metrics"]["mentions"] == 0


def test_member_role_cannot_do_admin_things(client):
    owner = Account(client, "own@example.com", "Roles Co")
    member = Account(client, "mem@example.com", "Member Home")
    assert owner.post("/members", json={"email": "mem@example.com", "role": "member"}).status_code == 201
    as_member = {"Authorization": member.headers["Authorization"]}
    assert client.get(f"{owner.base}/feedback", headers=as_member).status_code == 200
    assert client.post(f"{owner.base}/api-key", headers=as_member).status_code == 403
    assert client.patch(f"{owner.base}", json={"name": "Hijacked"}, headers=as_member).status_code == 403


def test_settings_validation_and_update(account):
    r = account.patch("", json={"settings": {"priority_weights": {"revenue": 0.9}, "working_language": "de"}})
    assert r.status_code == 200
    s = r.json()["settings"]
    assert s["priority_weights"]["revenue"] == 0.9 and s["priority_weights"]["demand"] == 0.3
    assert s["working_language"] == "de"
    assert account.patch("", json={"settings": {"priority_weights": {"bogus": 0.1}}}).status_code == 422
    assert account.patch("", json={"settings": {"ai_provider": "skynet"}}).status_code == 422
