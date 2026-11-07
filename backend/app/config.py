"""Runtime configuration, read from environment variables (or a .env file)."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-insecure-change-me"
# Values that are public (in this repo) and must never sign production tokens
KNOWN_PLACEHOLDER_SECRETS = {DEV_SECRET, "change-me-to-a-long-random-string", "changeme", "secret"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    environment: str = "development"  # "production" enforces a strong SECRET_KEY at startup
    database_url: str = "sqlite:///./loopwise.db"
    secret_key: str = DEV_SECRET
    access_token_minutes: int = 60 * 24 * 7
    cors_origins: str = "http://localhost:3000"
    public_app_url: str = "http://localhost:3000"

    # Run Alembic migrations automatically on startup
    auto_migrate: bool = True

    # Background analysis worker
    worker_enabled: bool = True
    worker_interval_seconds: float = 2.0
    worker_batch_size: int = 20

    # AI: "auto" picks the first available of anthropic -> openai -> ollama -> heuristic
    ai_provider: str = "auto"
    anthropic_api_key: str | None = None
    claude_model: str = "claude-opus-5-5"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_embed_model: str = "nomic-embed-text"
    # Embeddings: "auto" picks openai -> ollama -> local
    embeddings_provider: str = "auto"

    # Close-the-loop email delivery: "outbox" writes .eml files, "smtp" sends for real
    email_mode: str = "outbox"
    outbox_dir: str = "./outbox"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "Loopwise <no-reply@loopwise.local>"
    smtp_starttls: bool = True

    # Public endpoint abuse protection
    public_rate_limit: int = 30  # requests
    public_rate_window_seconds: int = 300

    @field_validator("secret_key")
    @classmethod
    def _empty_secret_means_unset(cls, v: str) -> str:
        return v.strip() or DEV_SECRET

    @property
    def secret_is_weak(self) -> bool:
        return self.secret_key in KNOWN_PLACEHOLDER_SECRETS or len(self.secret_key) < 32

    def assert_production_safe(self) -> None:
        """Refuse to run a production instance whose token-signing key is public or guessable."""
        if self.environment.lower() == "production" and self.secret_is_weak:
            raise RuntimeError(
                "SECRET_KEY is missing, a known placeholder, or shorter than 32 characters. Generate one with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
