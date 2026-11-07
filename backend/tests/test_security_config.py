"""Production must never run with a public or guessable token-signing key."""

import pytest

from app.config import DEV_SECRET, Settings


@pytest.mark.parametrize("secret", ["", DEV_SECRET, "change-me-to-a-long-random-string", "short-but-custom"])
def test_production_refuses_weak_secret(secret):
    s = Settings(environment="production", secret_key=secret, _env_file=None)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        s.assert_production_safe()


def test_production_accepts_strong_secret():
    Settings(environment="production", secret_key="x" * 48, _env_file=None).assert_production_safe()


def test_development_allows_default_with_warning_flag():
    s = Settings(environment="development", secret_key="", _env_file=None)
    assert s.secret_key == DEV_SECRET and s.secret_is_weak
    s.assert_production_safe()  # no error outside production


def test_forged_token_with_public_default_is_rejected(client):
    """A token signed with the repo's public dev secret must not work when the server uses a real secret."""
    import jwt

    from tests.conftest import Account

    acc = Account(client, "victim@example.com", "Victim Co")
    forged = jwt.encode({"sub": "1"}, DEV_SECRET, algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    assert client.get("/api/auth/me", headers=acc.headers).status_code == 200
