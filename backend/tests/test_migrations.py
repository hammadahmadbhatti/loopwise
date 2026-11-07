"""The Alembic migration must produce exactly the schema the models describe."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.db import make_engine, run_migrations
from app.models import Base


def test_migrations_match_models(tmp_path):
    url = f"sqlite:///{tmp_path}/migrated.db"
    run_migrations(url)
    run_migrations(url)  # idempotent
    engine = make_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []
