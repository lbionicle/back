import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tickets.model.models import (
    MessageSenderType,
    Ticket,
    TicketMessage,
    TicketMessageKind,
    TicketStatus,
)
from app.modules.tickets.service import ticket_service
from app.modules.tickets.service.ticket_service import (
    assign_ticket_to_operator,
    close_ticket,
    create_ticket,
    rate_ticket_by_initiator,
    request_operator,
)
from app.modules.users.model.models import UserRole


@pytest.mark.asyncio
async def test_create_ticket_creates_user_and_bot_messages(
    db_session: AsyncSession,
    user_factory,
    monkeypatch,
):
    initiator = await user_factory(
        email="initiator@test.by",
        role=UserRole.initiator,
    )

    async def fake_generate_bot_answer(_messages):
        return "Тестовый ответ ИИ"

    async def fake_generate_ticket_title(_message):
        return "Тестовый тикет"

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

    ticket = await create_ticket(
        session=db_session,
        initiator=initiator,
        message_text="У меня проблема с доступом",
    )

    assert ticket.title == "Тестовый тикет"
    assert ticket.status == TicketStatus.in_progress
    assert ticket.initiator_id == initiator.id
    assert len(ticket.messages) == 2

    assert ticket.messages[0].sender_type == MessageSenderType.initiator
    assert ticket.messages[0].kind == TicketMessageKind.text
    assert ticket.messages[0].text == "У меня проблема с доступом"

    assert ticket.messages[1].sender_type == MessageSenderType.bot
    assert ticket.messages[1].kind == TicketMessageKind.text
    assert ticket.messages[1].text == "Тестовый ответ ИИ"


@pytest.mark.asyncio
async def test_request_operator_moves_ticket_to_pending(
    db_session: AsyncSession,
    user_factory,
):
    initiator = await user_factory(
        email="initiator@test.by",
        role=UserRole.initiator,
    )

    ticket = Ticket(
        title="Проблема с системой",
        initiator_id=initiator.id,
        status=TicketStatus.in_progress,
        is_operator_requested=False,
    )

    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)

    updated_ticket = await request_operator(
        session=db_session,
        ticket=ticket,
    )

    assert updated_ticket.status == TicketStatus.pending
    assert updated_ticket.is_operator_requested is True

    bot_messages = [
        message
        for message in updated_ticket.messages
        if message.sender_type == MessageSenderType.bot
    ]

    assert len(bot_messages) == 1
    assert "Соединяю вас с оператором" in bot_messages[0].text


@pytest.mark.asyncio
async def test_assign_ticket_to_operator_validates_operator_role(
    db_session: AsyncSession,
    user_factory,
):
    initiator = await user_factory(
        email="initiator@test.by",
        role=UserRole.initiator,
    )
    not_operator = await user_factory(
        email="not-operator@test.by",
        role=UserRole.initiator,
    )

    ticket = Ticket(
        title="Тикет",
        initiator_id=initiator.id,
        status=TicketStatus.pending,
        is_operator_requested=True,
    )

    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)

    with pytest.raises(ValueError, match="Назначить можно только пользователя"):
        await assign_ticket_to_operator(
            session=db_session,
            ticket=ticket,
            operator=not_operator,
        )


@pytest.mark.asyncio
async def test_close_ticket_adds_rating_request_message(
    db_session: AsyncSession,
    user_factory,
):
    initiator = await user_factory(
        email="initiator@test.by",
        role=UserRole.initiator,
    )
    operator = await user_factory(
        email="operator@test.by",
        role=UserRole.operator,
    )

    ticket = Ticket(
        title="Тикет",
        initiator_id=initiator.id,
        operator_id=operator.id,
        status=TicketStatus.in_progress,
        is_operator_requested=True,
    )

    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)

    closed_ticket = await close_ticket(
        session=db_session,
        ticket=ticket,
    )

    assert closed_ticket.status == TicketStatus.closed
    assert closed_ticket.closed_at is not None

    rating_request_messages = [
        message
        for message in closed_ticket.messages
        if message.kind == TicketMessageKind.rating_request
    ]

    assert len(rating_request_messages) == 1
    assert "оцените качество обслуживания" in rating_request_messages[0].text


@pytest.mark.asyncio
async def test_rate_ticket_by_initiator_creates_rating_and_chat_message(
    db_session: AsyncSession,
    user_factory,
):
    initiator = await user_factory(
        email="initiator@test.by",
        role=UserRole.initiator,
    )

    ticket = Ticket(
        title="Закрытый тикет",
        initiator_id=initiator.id,
        status=TicketStatus.closed,
    )

    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)

    updated_ticket = await rate_ticket_by_initiator(
        session=db_session,
        ticket=ticket,
        initiator=initiator,
        rating=5,
        comment="Всё отлично",
    )

    assert updated_ticket.rating is not None
    assert updated_ticket.rating.rating == 5
    assert updated_ticket.rating.comment == "Всё отлично"

    rating_messages = [
        message
        for message in updated_ticket.messages
        if message.kind == TicketMessageKind.rating_submitted
    ]

    assert len(rating_messages) == 1
    assert "Пользователь оставил отзыв" in rating_messages[0].text
    assert "★★★★★" in rating_messages[0].text