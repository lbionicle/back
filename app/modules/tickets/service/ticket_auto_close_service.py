import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.modules.tickets.model.models import (
    MessageSenderType,
    Ticket,
    TicketMessage,
    TicketMessageKind,
    TicketStatus,
)


async def close_stale_in_progress_tickets(
    session: AsyncSession,
) -> int:
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(hours=settings.ticket_auto_close_hours)

    result = await session.execute(
        select(Ticket)
        .where(Ticket.status == TicketStatus.in_progress)
        .where(Ticket.updated_at <= stale_before)
    )

    tickets = list(result.scalars().all())

    if not tickets:
        return 0

    for ticket in tickets:
        ticket.status = TicketStatus.closed
        ticket.closed_at = now
        ticket.updated_at = now

        bot_message = TicketMessage(
            ticket_id=ticket.id,
            sender_id=None,
            sender_type=MessageSenderType.bot,
            kind=TicketMessageKind.rating_request,
            text=(
                "Тикет был автоматически закрыт, так как в течение суток "
                "по нему не было новых сообщений. "
                "Пожалуйста, оцените качество обслуживания."
            ),
        )

        session.add(ticket)
        session.add(bot_message)

    await session.commit()

    return len(tickets)


async def run_ticket_auto_close_worker() -> None:
    interval_seconds = settings.ticket_auto_close_interval_minutes * 60

    while True:
        try:
            async with AsyncSessionLocal() as session:
                await close_stale_in_progress_tickets(session)
        except Exception as error:
            print(f"Ошибка автоматического закрытия тикетов: {error}")

        await asyncio.sleep(interval_seconds)