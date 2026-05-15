from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.tickets.model.models import (
    Ticket,
    TicketMessageKind,
    TicketStatus,
)
from app.modules.tickets.service.ticket_auto_close_service import (
    close_stale_in_progress_tickets,
)
from app.modules.tickets.service.ticket_service import get_ticket_by_id
from app.modules.users.model.models import UserRole


@pytest.mark.asyncio
async def test_close_stale_in_progress_tickets_closes_only_old_in_progress_tickets(
    db_session: AsyncSession,
    user_factory,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ticket_auto_close_hours", 24)

    initiator = await user_factory(
        email="initiator@test.by",
        role=UserRole.initiator,
    )

    old_ticket = Ticket(
        title="Старый тикет",
        initiator_id=initiator.id,
        status=TicketStatus.in_progress,
        updated_at=datetime.now(timezone.utc) - timedelta(hours=25),
    )

    fresh_ticket = Ticket(
        title="Свежий тикет",
        initiator_id=initiator.id,
        status=TicketStatus.in_progress,
        updated_at=datetime.now(timezone.utc),
    )

    pending_ticket = Ticket(
        title="Ожидающий тикет",
        initiator_id=initiator.id,
        status=TicketStatus.pending,
        updated_at=datetime.now(timezone.utc) - timedelta(hours=48),
    )

    db_session.add_all([old_ticket, fresh_ticket, pending_ticket])
    await db_session.commit()

    closed_count = await close_stale_in_progress_tickets(db_session)

    assert closed_count == 1

    updated_old_ticket = await get_ticket_by_id(db_session, old_ticket.id)
    updated_fresh_ticket = await get_ticket_by_id(db_session, fresh_ticket.id)
    updated_pending_ticket = await get_ticket_by_id(db_session, pending_ticket.id)

    assert updated_old_ticket.status == TicketStatus.closed
    assert updated_old_ticket.closed_at is not None

    assert updated_fresh_ticket.status == TicketStatus.in_progress
    assert updated_pending_ticket.status == TicketStatus.pending

    rating_request_messages = [
        message
        for message in updated_old_ticket.messages
        if message.kind == TicketMessageKind.rating_request
    ]

    assert len(rating_request_messages) == 1