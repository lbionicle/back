import os
from collections.abc import AsyncGenerator, Callable

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5439/intelliticket_test",
)
os.environ.setdefault(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5439/intelliticket_test",
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-intelliticket-tests")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
os.environ.setdefault("SERVICE_MANAGER_EMAIL", "admin@test.by")
os.environ.setdefault("SERVICE_MANAGER_PASSWORD", "admin12345")
os.environ.setdefault("SERVICE_MANAGER_FULL_NAME", "Тестовый менеджер")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("OLLAMA_MODEL", "test-model")
os.environ.setdefault("TICKET_AUTO_CLOSE_HOURS", "24")
os.environ.setdefault("TICKET_AUTO_CLOSE_INTERVAL_MINUTES", "30")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.modules.tickets.model import models as ticket_models
from app.modules.users.model import models as user_models
from app.modules.users.model.models import User, UserRole
from app.modules.users.service.user_service import create_user

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5439/intelliticket_test",
)


@pytest_asyncio.fixture()
async def test_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )

    async with engine.begin() as connection:
        await connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await connection.execute(text("CREATE SCHEMA public"))
        await connection.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
        await connection.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture()
async def session_factory(test_engine):
    return async_sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
    )


@pytest_asyncio.fixture()
async def db_session(
    session_factory,
) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session

        if session.in_transaction():
            await session.rollback()


@pytest.fixture(autouse=True)
def override_get_session(session_factory):
    async def get_test_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session

    yield

    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield client


@pytest_asyncio.fixture()
async def user_factory(
    db_session: AsyncSession,
) -> Callable[..., User]:
    async def factory(
        *,
        full_name: str = "Тестовый пользователь",
        email: str = "user@test.by",
        password: str = "password123",
        role: UserRole = UserRole.initiator,
        is_blocked: bool = False,
    ) -> User:
        user = await create_user(
            session=db_session,
            full_name=full_name,
            email=email,
            password=password,
            role=role,
        )

        if is_blocked:
            user.is_blocked = True
            db_session.add(user)
            await db_session.commit()
            await db_session.refresh(user)

        return user

    return factory


def build_auth_headers(user: User) -> dict[str, str]:
    access_token = create_access_token(
        subject=str(user.id),
        role=user.role.value,
    )

    return {
        "Authorization": f"Bearer {access_token}",
    }