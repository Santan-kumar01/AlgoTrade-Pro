import pytest

from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine

from src.core.database import (
    AsyncSessionLocal,
    close_db_connection,
    engine,
    get_db,
)
from src.models.base import Base


def test_database_engine_configuration():
    assert isinstance(engine, AsyncEngine)
    assert engine.url.drivername == "postgresql+asyncpg"
    assert engine.pool is not None


def test_async_session_factory_configuration():
    assert AsyncSessionLocal.class_ is AsyncSession
    assert AsyncSessionLocal.kw["expire_on_commit"] is False
    assert AsyncSessionLocal.kw["autoflush"] is False


def test_database_dependency_is_async_generator():
    dependency = get_db()
    assert hasattr(dependency, "__anext__")


def test_declarative_base_metadata():
    from src.models import Asset, User

    assert Base.metadata is not None
    assert set(Base.metadata.tables.keys()) == {"users", "assets"}
    assert User.__table__ in Base.metadata.tables.values()
    assert Asset.__table__ in Base.metadata.tables.values()


@pytest.mark.asyncio
async def test_database_session_lifecycle(monkeypatch):
    """Verify that the database dependency closes its session."""

    class FakeSession:
        closed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            self.closed = True

    fake_session = FakeSession()

    monkeypatch.setattr(
        "src.core.database.AsyncSessionLocal",
        lambda: fake_session,
    )

    dependency = get_db()

    yielded_session = await anext(dependency)
    assert yielded_session is fake_session
    assert fake_session.closed is False

    await dependency.aclose()

    assert fake_session.closed is True


@pytest.mark.asyncio
async def test_database_engine_disposal():
    await close_db_connection()