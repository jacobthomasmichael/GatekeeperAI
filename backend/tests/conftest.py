import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.deps import get_db
from app.main import app
from app.models.user import User
from app.services.auth_service import hash_password

TEST_DB_URL = "postgresql+asyncpg://gatekeeper:gatekeeper_dev@localhost:5433/gatekeeperai_test"


def pytest_configure(config):
    import sqlalchemy as sa
    sync_url = TEST_DB_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    engine = sa.create_engine(sync_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    engine.dispose()


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


@pytest_asyncio.fixture
async def client(db):
    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(db):
    import uuid
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"admin_{suffix}@example.com",
        username=f"admin_{suffix}",
        hashed_password=hash_password("testpass123"),
        role="admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def ic_user(db):
    import uuid
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"ic_{suffix}@example.com",
        username=f"ic_{suffix}",
        hashed_password=hash_password("testpass123"),
        role="ic",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_token(client, admin_user):
    resp = await client.post("/api/v1/auth/login", json={
        "email": admin_user.email,
        "password": "testpass123",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def ic_token(client, ic_user):
    resp = await client.post("/api/v1/auth/login", json={
        "email": ic_user.email,
        "password": "testpass123",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]
