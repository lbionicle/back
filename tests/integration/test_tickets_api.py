import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tickets.model.models import Ticket, TicketStatus
from app.modules.tickets.service import ticket_service
from app.modules.users.model.models import UserRole
from tests.conftest import build_auth_headers


@pytest.mark.asyncio
async def test_create_ticket_api_creates_ticket_with_bot_answer(
    async_client,
    monkeypatch,
):
    async def fake_generate_bot_answer(_messages):
        return "Тестовый ответ ИИ"

    async def fake_generate_ticket_title(_message):
        return "Тестовый заголовок"

    monkeypatch.setattr(
        ticket_service,
        "generate_bot_answer",
        fake_generate_bot_answer,
    )
    monkeypatch.setattr(
        ticket_service,
        "generate_ticket_title",
        fake_generate_ticket_title,
    )

    sign_up_response = await async_client.post(
        "/api/auth/sign-up",
        json={
            "fullName": "Инициатор",
            "email": "initiator@test.by",
            "password": "password123",
            "confirmPassword": "password123",
        },
    )

    assert sign_up_response.status_code == 201, sign_up_response.json()

    response = await async_client.post(
        "/api/tickets",
        json={
            "message": "Не получается войти в систему",
        },
    )

    assert response.status_code == 201, response.json()

    body = response.json()

    assert body["title"] == "Тестовый заголовок"
    assert body["status"] == "in_progress"
    assert body["isOperatorRequested"] is False

    assert len(body["messages"]) == 2
    assert body["messages"][0]["senderType"] == "initiator"
    assert body["messages"][0]["kind"] == "text"
    assert body["messages"][0]["text"] == "Не получается войти в систему"

    assert body["messages"][1]["senderType"] == "bot"
    assert body["messages"][1]["kind"] == "text"
    assert body["messages"][1]["text"] == "Тестовый ответ ИИ"


@pytest.mark.asyncio
async def test_request_operator_api_moves_ticket_to_pending(
    async_client,
    monkeypatch,
):
    async def fake_generate_bot_answer(_messages):
        return "Ответ ИИ"

    async def fake_generate_ticket_title(_message):
        return "Тикет"

    monkeypatch.setattr(
        ticket_service,
        "generate_bot_answer",
        fake_generate_bot_answer,
    )
    monkeypatch.setattr(
        ticket_service,
        "generate_ticket_title",
        fake_generate_ticket_title,
    )

    sign_up_response = await async_client.post(
        "/api/auth/sign-up",
        json={
            "fullName": "Инициатор",
            "email": "initiator@test.by",
            "password": "password123",
            "confirmPassword": "password123",
        },
    )

    assert sign_up_response.status_code == 201, sign_up_response.json()

    create_response = await async_client.post(
        "/api/tickets",
        json={
            "message": "Нужна помощь",
        },
    )

    assert create_response.status_code == 201, create_response.json()

    ticket_id = create_response.json()["id"]

    response = await async_client.post(
        f"/api/tickets/{ticket_id}/request-operator",
    )

    assert response.status_code == 200, response.json()

    body = response.json()

    assert body["status"] == "pending"
    assert body["isOperatorRequested"] is True

    assert any(
        message["senderType"] == "bot"
        and "Соединяю вас с оператором" in message["text"]
        for message in body["messages"]
    )


@pytest.mark.asyncio
async def test_operator_can_close_assigned_ticket(
    async_client,
    db_session: AsyncSession,
    user_factory,
):
    initiator = await user_factory(
        full_name="Инициатор",
        email="initiator@test.by",
        role=UserRole.initiator,
    )
    operator = await user_factory(
        full_name="Оператор",
        email="operator@test.by",
        role=UserRole.operator,
    )

    ticket = Ticket(
        title="Назначенный тикет",
        initiator_id=initiator.id,
        operator_id=operator.id,
        status=TicketStatus.in_progress,
        is_operator_requested=True,
    )

    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)

    response = await async_client.post(
        f"/api/operator/tickets/{ticket.id}/close",
        headers=build_auth_headers(operator),
    )

    assert response.status_code == 200, response.json()

    body = response.json()

    assert body["status"] == "closed"
    assert body["closedAt"] is not None

    assert any(
        message["kind"] == "rating_request"
        for message in body["messages"]
    )