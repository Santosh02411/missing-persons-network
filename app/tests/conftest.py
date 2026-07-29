import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.redis_client import redis_client
from app.core.security import create_access_token, hash_password
from app.db.base import Base  # imports all models so metadata is complete
from app.db.session import get_db
from app.main import app
from app.models.user import User, UserRole

TEST_DATABASE_URL = settings.TEST_DATABASE_URL or settings.DATABASE_URL

engine = create_engine(TEST_DATABASE_URL, future=True)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def _test_schema():
    """Runs once per test session: ensures PostGIS is enabled and creates all
    tables directly from the models (not via Alembic — faster, and keeps the
    test suite independent of migration history). Drops everything afterward."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    """Wraps each test in an outer transaction + a SAVEPOINT. Application
    code (via the service layer) calls session.commit() freely -- committing
    only releases the SAVEPOINT, which the event listener immediately
    restarts. The outer transaction is rolled back at the end of the test, so
    nothing a test does ever persists into the next one.

    This is the standard SQLAlchemy pattern for testing code that manages its
    own commits (see SQLAlchemy docs: "Joining a Session into an External
    Transaction"). Without it, either every service function would need a
    test-only no-commit mode, or tests would leak data into each other.
    """
    connection = engine.connect()
    outer_transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, transaction):
        if transaction.nested and not transaction._parent.nested:
            sess.begin_nested()

    yield session

    session.close()
    outer_transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    """FastAPI TestClient wired to the transactional test session instead of
    the real app engine, via dependency_overrides."""

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _clean_redis():
    """Rate-limit counters, refresh-token jtis, and case-list cache entries
    are real Redis state, not part of the DB transaction rollback above --
    clean them before and after every test so tests can't leak into each
    other (e.g. a rate-limit test tripping the limit for a later test)."""
    prefixes = ("ratelimit:", "refresh_jti:", "cache:")

    def _flush():
        for prefix in prefixes:
            for key in redis_client.scan_iter(f"{prefix}*"):
                redis_client.delete(key)

    _flush()
    yield
    _flush()


@pytest.fixture()
def make_user(db_session):
    """Factory fixture: make_user(role=UserRole.AUTHORITY, is_verified=True)."""

    def _make_user(
        role: UserRole = UserRole.REPORTER,
        is_verified: bool | None = None,
        **overrides,
    ) -> User:
        if is_verified is None:
            is_verified = role == UserRole.REPORTER
        user = User(
            email=overrides.get("email", f"{uuid.uuid4()}@example.com"),
            hashed_password=hash_password(overrides.get("password", "testpassword123")),
            full_name=overrides.get("full_name", "Test User"),
            role=role,
            is_verified=is_verified,
            org_name=overrides.get("org_name"),
            is_active=overrides.get("is_active", True),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _make_user


@pytest.fixture()
def auth_headers():
    """auth_headers(user) -> {"Authorization": "Bearer <token>"}"""

    def _headers(user: User) -> dict:
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    return _headers
