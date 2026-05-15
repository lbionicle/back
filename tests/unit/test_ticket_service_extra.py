from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tickets.model.models import (
    Ticket,
    TicketMessageKind,
    TicketStatus,
)
from app.modules.tickets.service.ticket_service import (
    assign_ticket_by_manager,
    get_manager_tickets_list,
    get_manager_tickets_stats,
    get_operator_tickets_list,
    get_operator_tickets_stats,
    rate_ticket_by_initiator,
    update_ticket_priority,
    update_ticket_status,
)
from app.modules.users.model.models import UserRole


@pytest.mark.asyncio
async def test_get_manager_tickets_stats_counts_tickets(
    db_session: AsyncSession,
    user_factory,
):
    initiator = await user_factory(
        email="initiator@test.by",
        role=UserRole.initiator,
    )

    tickets = [
        Ticket(
            title="Ожидает",
            initiator_id=initiator.id,
            status=TicketStatus.pending,
            is_priority=True,
        ),
        Ticket(
            title="В процессе",
            initiator_id=initiator.id,
            status=TicketStatus.in_progress,
        ),
        Ticket(
            title="Закрыт",
            initiator_id=initiator.id,
            status=TicketStatus.closed,
        ),
    ]

    db_session.add_all(tickets)
    await db_session.commit()

    stats = await get_manager_tickets_stats(db_session)

    assert stats["total_tickets_count"] == 3
    assert stats["priority_tickets_count"] == 1
    assert stats["pending_tickets_count"] == 1
    assert stats["in_progress_tickets_count"] == 1
    assert stats["closed_tickets_count"] == 1


@pytest.mark.asyncio
async def test_get_operator_tickets_stats_counts_available_and_assigned(
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

    available_ticket = Ticket(
        title="Доступный тикет",
        initiator_id=initiator.id,
        status=TicketStatus.pending,
        is_operator_requested=True,
        is_priority=True,
    )
    assigned_ticket = Ticket(
        title="Назначенный тикет",
        initiator_id=initiator.id,
        operator_id=operator.id,
        status=TicketStatus.in_progress,
        is_operator_requested=True,
    )
    closed_ticket = Ticket(
        title="Закрытый тикет",
        initiator_id=initiator.id,
        operator_id=operator.id,
        status=TicketStatus.closed,
        is_operator_requested=True,
    )

    db_session.add_all([available_ticket, assigned_ticket, closed_ticket])
    await db_session.commit()

    stats = await get_operator_tickets_stats(db_session, operator)

    assert stats["total_tickets_count"] == 2
    assert stats["priority_tickets_count"] == 1
    assert stats["pending_tickets_count"] == 1
    assert stats["in_progress_tickets_count"] == 1
    assert stats["closed_tickets_count"] == 1


@pytest.mark.asyncio
async def test_update_ticket_priority_changes_priority(
    db_session: AsyncSession,
    user_factory,
):
    initiator = await user_factory(
        email="initiator@test.by",
        role=UserRole.initiator,
    )

    ticket = Ticket(
        title="Тикет",
        initiator_id=initiator.id,
        status=TicketStatus.in_progress,
        is_priority=False,
    )

    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)

    updated_ticket = await update_ticket_priority(
        session=db_session,
        ticket=ticket,
        is_priority=True,
    )

    assert updated_ticket.is_priority is True


@pytest.mark.asyncio
async def test_assign_ticket_by_manager_assigns_operator(
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
        status=TicketStatus.pending,
        is_operator_requested=True,
    )

    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)

    updated_ticket = await assign_ticket_by_manager(
        session=db_session,
        ticket=ticket,
        operator=operator,
    )

    assert updated_ticket.operator_id == operator.id
    assert updated_ticket.status == TicketStatus.in_progress
    assert updated_ticket.is_operator_requested is True


@pytest.mark.asyncio
async def test_assign_ticket_by_manager_rejects_blocked_operator(
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
        is_blocked=True,
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

    with pytest.raises(ValueError, match="заблокированного оператора"):
        await assign_ticket_by_manager(
            session=db_session,
            ticket=ticket,
            operator=operator,
        )


@pytest.mark.asyncio
async def test_update_ticket_status_to_pending_clears_operator(
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
        closed_at=datetime.now(timezone.utc),
    )

    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)

    updated_ticket = await update_ticket_status(
        session=db_session,
        ticket=ticket,
        next_status=TicketStatus.pending,
    )

    assert updated_ticket.status == TicketStatus.pending
    assert updated_ticket.operator_id is None
    assert updated_ticket.is_operator_requested is True
    assert updated_ticket.closed_at is None


@pytest.mark.asyncio
async def test_update_ticket_status_to_in_progress_requires_operator(
    db_session: AsyncSession,
    user_factory,
):
    initiator = await user_factory(
        email="initiator@test.by",
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

    with pytest.raises(ValueError, match="без назначенного оператора"):
        await update_ticket_status(
            session=db_session,
            ticket=ticket,
            next_status=TicketStatus.in_progress,
        )


@pytest.mark.asyncio
async def test_update_ticket_status_to_closed_adds_rating_request(
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

    updated_ticket = await update_ticket_status(
        session=db_session,
        ticket=ticket,
        next_status=TicketStatus.closed,
    )

    assert updated_ticket.status == TicketStatus.closed
    assert updated_ticket.closed_at is not None

    assert any(
        message.kind == TicketMessageKind.rating_request
        for message in updated_ticket.messages
    )


@pytest.mark.asyncio
async def test_rate_ticket_rejects_not_closed_ticket(
    db_session: AsyncSession,
    user_factory,
):
    initiator = await user_factory(
        email="initiator@test.by",
        role=UserRole.initiator,
    )

    ticket = Ticket(
        title="Тикет",
        initiator_id=initiator.id,
        status=TicketStatus.in_progress,
    )

    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)

    with pytest.raises(ValueError, match="Оценить можно только закрытый тикет"):
        await rate_ticket_by_initiator(
            session=db_session,
            ticket=ticket,
            initiator=initiator,
            rating=5,
            comment=None,
        )


@pytest.mark.asyncio
async def test_rate_ticket_rejects_foreign_ticket(
    db_session: AsyncSession,
    user_factory,
):
    owner = await user_factory(
        email="owner@test.by",
        role=UserRole.initiator,
    )
    another_user = await user_factory(
        email="another@test.by",
        role=UserRole.initiator,
    )

    ticket = Ticket(
        title="Чужой тикет",
        initiator_id=owner.id,
        status=TicketStatus.closed,
    )

    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)

    with pytest.raises(ValueError, match="Нельзя оценить чужой тикет"):
        await rate_ticket_by_initiator(
            session=db_session,
            ticket=ticket,
            initiator=another_user,
            rating=5,
            comment=None,
        )


@pytest.mark.asyncio
async def test_get_manager_tickets_list_filters_by_search_and_status(
    db_session: AsyncSession,
    user_factory,
):
    initiator = await user_factory(
        full_name="Анна Пользователь",
        email="anna@test.by",
        role=UserRole.initiator,
    )
    operator = await user_factory(
        full_name="Олег Оператор",
        email="operator@test.by",
        role=UserRole.operator,
    )

    first_ticket = Ticket(
        title="Проблема с авторизацией",
        initiator_id=initiator.id,
        operator_id=operator.id,
        status=TicketStatus.in_progress,
        is_operator_requested=True,
        is_priority=True,
    )
    second_ticket = Ticket(
        title="Ошибка оплаты",
        initiator_id=initiator.id,
        status=TicketStatus.closed,
    )

    db_session.add_all([first_ticket, second_ticket])
    await db_session.commit()

    tickets, total = await get_manager_tickets_list(
        session=db_session,
        search="авторизацией",
        status=TicketStatus.in_progress,
        is_priority=True,
        page=1,
        limit=10,
    )

    assert total == 1
    assert len(tickets) == 1

    ticket, found_initiator, found_operator = tickets[0]

    assert ticket.id == first_ticket.id
    assert found_initiator.id == initiator.id
    assert found_operator.id == operator.id


@pytest.mark.asyncio
async def test_get_operator_tickets_list_returns_assigned_and_available(
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

    assigned_ticket = Ticket(
        title="Назначенный тикет",
        initiator_id=initiator.id,
        operator_id=operator.id,
        status=TicketStatus.in_progress,
        is_operator_requested=True,
    )
    available_ticket = Ticket(
        title="Доступный тикет",
        initiator_id=initiator.id,
        status=TicketStatus.pending,
        is_operator_requested=True,
    )

    db_session.add_all([assigned_ticket, available_ticket])
    await db_session.commit()

    tickets, total = await get_operator_tickets_list(
        session=db_session,
        operator=operator,
        page=1,
        limit=10,
    )

    ticket_ids = {ticket.id for ticket, _initiator, _operator in tickets}

    assert total == 2
    assert assigned_ticket.id in ticket_ids
    assert available_ticket.id in ticket_ids