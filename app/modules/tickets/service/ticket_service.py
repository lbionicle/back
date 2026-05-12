from uuid import UUID
from typing import Literal
from datetime import datetime, timezone

from sqlalchemy import func, or_, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.modules.ai.service.ai_assistant_service import (
    generate_bot_answer,
    generate_ticket_title,
)
from app.modules.tickets.model.models import (
    MessageSenderType,
    Ticket,
    TicketMessage,
    TicketStatus, TicketRating, TicketMessageKind,
)
from app.modules.tickets.service.ticket_ai_context import build_ai_chat_context
from app.modules.users.model.models import User, UserRole


RATING_REQUEST_MESSAGE_TEXT = (
    "Обращение закрыто. Пожалуйста, оцените качество обслуживания "
    "и при желании оставьте комментарий."
)

async def get_ticket_by_id(
    session: AsyncSession,
    ticket_id: UUID,
) -> Ticket | None:
    result = await session.execute(
        select(Ticket)
        .options(
            selectinload(Ticket.messages),
            selectinload(Ticket.rating),
            selectinload(Ticket.initiator),
            selectinload(Ticket.operator),
        )
        .where(Ticket.id == ticket_id)
    )

    return result.scalar_one_or_none()


async def get_ticket_messages(
    session: AsyncSession,
    ticket_id: UUID,
) -> list[TicketMessage]:
    result = await session.execute(
        select(TicketMessage)
        .where(TicketMessage.ticket_id == ticket_id)
        .order_by(TicketMessage.created_at.asc(), TicketMessage.id.asc())
    )

    return list(result.scalars().all())

def build_rating_submitted_message(
    rating: int,
    comment: str | None,
    is_update: bool,
) -> str:
    stars = "★" * rating + "☆" * (5 - rating)

    action_text = (
        "Пользователь обновил отзыв"
        if is_update
        else "Пользователь оставил отзыв"
    )

    if comment:
        return f"{action_text}: {stars} ({rating}/5).\nКомментарий: {comment}"

    return f"{action_text}: {stars} ({rating}/5)."

def has_actual_rating(ticket: Ticket) -> bool:
    if not ticket.rating:
        return False

    if not ticket.closed_at:
        return True

    return ticket.rating.updated_at >= ticket.closed_at

async def add_rating_request_message_if_needed(
    session: AsyncSession,
    ticket: Ticket,
) -> None:
    if ticket.status != TicketStatus.closed:
        return

    if not ticket.closed_at:
        return

    if has_actual_rating(ticket):
        return

    existing_message_result = await session.execute(
        select(TicketMessage.id)
        .where(TicketMessage.ticket_id == ticket.id)
        .where(TicketMessage.kind == TicketMessageKind.rating_request)
        .where(TicketMessage.created_at >= ticket.closed_at)
        .limit(1)
    )

    if existing_message_result.scalar_one_or_none():
        return

    message = TicketMessage(
        ticket_id=ticket.id,
        sender_id=None,
        sender_type=MessageSenderType.bot,
        kind=TicketMessageKind.rating_request,
        text=RATING_REQUEST_MESSAGE_TEXT,
    )

    session.add(message)


async def create_ticket(
    session: AsyncSession,
    initiator: User,
    message_text: str,
) -> Ticket:
    ticket = Ticket(
        title="Новый чат",
        initiator_id=initiator.id,
        status=TicketStatus.in_progress,
        is_operator_requested=False,
    )

    session.add(ticket)
    await session.flush()

    ticket_id = ticket.id

    user_message = TicketMessage(
        ticket_id=ticket_id,
        sender_id=initiator.id,
        sender_type=MessageSenderType.initiator,
        kind=TicketMessageKind.text,
        text=message_text,
    )

    session.add(user_message)
    await session.commit()

    messages = await get_ticket_messages(session, ticket_id)
    ai_context = build_ai_chat_context(messages)

    bot_answer = await generate_bot_answer(ai_context)
    generated_title = await generate_ticket_title(message_text)

    created_ticket = await get_ticket_by_id(session, ticket_id)

    if not created_ticket:
        raise RuntimeError("Не удалось получить созданный тикет")

    created_ticket.title = generated_title

    bot_message = TicketMessage(
        ticket_id=ticket_id,
        sender_id=None,
        sender_type=MessageSenderType.bot,
        kind=TicketMessageKind.text,
        text=bot_answer,
    )

    session.add(created_ticket)
    session.add(bot_message)
    await session.commit()

    updated_ticket = await get_ticket_by_id(session, ticket_id)

    if not updated_ticket:
        raise RuntimeError("Не удалось получить созданный тикет")

    return updated_ticket


async def get_initiator_tickets(
    session: AsyncSession,
    initiator: User,
) -> list[Ticket]:
    result = await session.execute(
        select(Ticket)
        .where(Ticket.initiator_id == initiator.id)
        .order_by(Ticket.updated_at.desc())
    )

    return list(result.scalars().all())


async def request_operator(
    session: AsyncSession,
    ticket: Ticket,
) -> Ticket:
    ticket.is_operator_requested = True
    ticket.status = TicketStatus.pending

    bot_message = TicketMessage(
        ticket_id=ticket.id,
        sender_id=None,
        sender_type=MessageSenderType.bot,
        kind=TicketMessageKind.text,
        text="Соединяю вас с оператором службы поддержки.",
    )

    session.add(ticket)
    session.add(bot_message)

    await session.commit()

    updated_ticket = await get_ticket_by_id(session, ticket.id)

    if not updated_ticket:
        raise RuntimeError("Не удалось получить обновлённый тикет")

    return updated_ticket


async def create_initiator_message(
    session: AsyncSession,
    ticket: Ticket,
    initiator: User,
    text: str,
) -> Ticket:
    ticket_id = ticket.id
    should_generate_bot_answer = not ticket.is_operator_requested

    message = TicketMessage(
        ticket_id=ticket_id,
        sender_id=initiator.id,
        sender_type=MessageSenderType.initiator,
        kind=TicketMessageKind.text,
        text=text,
    )

    ticket.updated_at = datetime.now(timezone.utc)

    session.add(ticket)
    session.add(message)
    await session.commit()

    if should_generate_bot_answer:
        messages = await get_ticket_messages(session, ticket_id)
        ai_context = build_ai_chat_context(messages)

        bot_answer = await generate_bot_answer(ai_context)

        bot_message = TicketMessage(
            ticket_id=ticket_id,
            sender_id=None,
            sender_type=MessageSenderType.bot,
            text=bot_answer,
        )

        updated_ticket = await get_ticket_by_id(session, ticket_id)

        if not updated_ticket:
            raise RuntimeError("Не удалось получить обновлённый тикет")

        updated_ticket.updated_at = datetime.now(timezone.utc)

        session.add(updated_ticket)
        session.add(bot_message)
        await session.commit()

    updated_ticket = await get_ticket_by_id(session, ticket_id)

    if not updated_ticket:
        raise RuntimeError("Не удалось получить обновлённый тикет")

    return updated_ticket


async def create_operator_message(
    session: AsyncSession,
    ticket: Ticket,
    operator: User,
    text: str,
) -> Ticket:
    message = TicketMessage(
        ticket_id=ticket.id,
        sender_id=operator.id,
        sender_type=MessageSenderType.operator,
        kind=TicketMessageKind.text,
        text=text,
    )

    ticket.updated_at = datetime.now(timezone.utc)

    session.add(ticket)
    session.add(message)
    await session.commit()

    updated_ticket = await get_ticket_by_id(session, ticket.id)

    if not updated_ticket:
        raise RuntimeError("Не удалось получить обновлённый тикет")

    return updated_ticket


async def get_available_operator_tickets(
    session: AsyncSession,
) -> list[Ticket]:
    result = await session.execute(
        select(Ticket)
        .where(Ticket.is_operator_requested.is_(True))
        .where(Ticket.status == TicketStatus.pending)
        .order_by(Ticket.created_at.asc())
    )

    return list(result.scalars().all())


async def get_assigned_operator_tickets(
    session: AsyncSession,
    operator: User,
) -> list[Ticket]:
    result = await session.execute(
        select(Ticket)
        .where(Ticket.operator_id == operator.id)
        .where(Ticket.status == TicketStatus.in_progress)
        .order_by(Ticket.updated_at.desc())
    )

    return list(result.scalars().all())


async def assign_ticket_to_operator(
    session: AsyncSession,
    ticket: Ticket,
    operator: User,
) -> Ticket:
    if operator.role != UserRole.operator:
        raise ValueError("Назначить можно только пользователя с ролью оператора")

    if operator.is_blocked:
        raise ValueError("Нельзя назначить заблокированного оператора")

    if ticket.status == TicketStatus.closed:
        raise ValueError("Нельзя назначить оператора на закрытый тикет")

    ticket.operator_id = operator.id
    ticket.status = TicketStatus.in_progress
    ticket.is_operator_requested = True

    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)

    return ticket

async def close_ticket(
    session: AsyncSession,
    ticket: Ticket,
) -> Ticket:
    ticket.status = TicketStatus.closed

    if ticket.closed_at is None:
        ticket.closed_at = datetime.now(timezone.utc)

    ticket.updated_at = datetime.now(timezone.utc)

    session.add(ticket)

    await add_rating_request_message_if_needed(session, ticket)

    await session.commit()

    updated_ticket = await get_ticket_by_id(session, ticket.id)

    if not updated_ticket:
        raise RuntimeError("Не удалось получить обновлённый тикет")

    return updated_ticket

async def delete_ticket(
    session: AsyncSession,
    ticket: Ticket,
) -> None:
    await session.delete(ticket)
    await session.commit()

async def get_manager_tickets_stats(session: AsyncSession) -> dict[str, int]:
    total_result = await session.execute(select(func.count(Ticket.id)))

    priority_result = await session.execute(
        select(func.count(Ticket.id)).where(Ticket.is_priority.is_(True))
    )

    pending_result = await session.execute(
        select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.pending)
    )

    in_progress_result = await session.execute(
        select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.in_progress)
    )

    closed_result = await session.execute(
        select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.closed)
    )

    return {
        "total_tickets_count": total_result.scalar_one(),
        "priority_tickets_count": priority_result.scalar_one(),
        "pending_tickets_count": pending_result.scalar_one(),
        "in_progress_tickets_count": in_progress_result.scalar_one(),
        "closed_tickets_count": closed_result.scalar_one(),
    }


async def get_operator_tickets_stats(
    session: AsyncSession,
    operator: User,
) -> dict[str, int]:
    available_result = await session.execute(
        select(func.count(Ticket.id))
        .where(Ticket.is_operator_requested.is_(True))
        .where(Ticket.status == TicketStatus.pending)
    )

    in_progress_result = await session.execute(
        select(func.count(Ticket.id))
        .where(Ticket.operator_id == operator.id)
        .where(Ticket.status == TicketStatus.in_progress)
    )

    priority_result = await session.execute(
        select(func.count(Ticket.id))
        .where(
            or_(
                Ticket.operator_id == operator.id,
                and_(
                    Ticket.is_operator_requested.is_(True),
                    Ticket.status == TicketStatus.pending,
                ),
            ),
        )
        .where(Ticket.is_priority.is_(True))
    )

    closed_result = await session.execute(
        select(func.count(Ticket.id))
        .where(Ticket.operator_id == operator.id)
        .where(Ticket.status == TicketStatus.closed)
    )

    available_count = available_result.scalar_one()
    in_progress_count = in_progress_result.scalar_one()
    priority_count = priority_result.scalar_one()
    closed_count = closed_result.scalar_one()

    return {
        "total_tickets_count": available_count + in_progress_count,
        "priority_tickets_count": priority_count,
        "pending_tickets_count": available_count,
        "in_progress_tickets_count": in_progress_count,
        "closed_tickets_count": closed_count,
    }

async def get_manager_tickets_list(
    session: AsyncSession,
    *,
    search: str | None = None,
    status: TicketStatus | None = None,
    is_priority: bool | None = None,
    operator_id: UUID | None = None,
    page: int = 1,
    limit: int = 10,
    sort_by: str | None = None,
    sort_order: Literal["asc", "desc"] = "desc",
) -> tuple[list[tuple[Ticket, User, User | None]], int]:
    Initiator = aliased(User)
    Operator = aliased(User)

    filters = []

    if search:
        normalized_search = f"%{search.lower()}%"

        filters.append(
            or_(
                func.lower(Ticket.title).like(normalized_search),
                func.lower(Initiator.full_name).like(normalized_search),
                func.lower(Initiator.email).like(normalized_search),
                func.lower(Operator.full_name).like(normalized_search),
                func.lower(Operator.email).like(normalized_search),
            )
        )

    if status is not None:
        filters.append(Ticket.status == status)

    if is_priority is not None:
        filters.append(Ticket.is_priority.is_(is_priority))

    if operator_id is not None:
        filters.append(Ticket.operator_id == operator_id)

    base_query = (
        select(Ticket)
        .join(Initiator, Ticket.initiator_id == Initiator.id)
        .outerjoin(Operator, Ticket.operator_id == Operator.id)
        .where(*filters)
    )

    total_result = await session.execute(
        select(func.count(Ticket.id))
        .select_from(Ticket)
        .join(Initiator, Ticket.initiator_id == Initiator.id)
        .outerjoin(Operator, Ticket.operator_id == Operator.id)
        .where(*filters)
    )

    total = total_result.scalar_one()

    sort_columns = {
        "title": Ticket.title,
        "status": Ticket.status,
        "createdAt": Ticket.created_at,
        "updatedAt": Ticket.updated_at,
        "isPriority": Ticket.is_priority,
        "initiator": Initiator.full_name,
        "operator": Operator.full_name,
    }

    sort_column = sort_columns.get(sort_by or "createdAt", Ticket.created_at)

    order_expression = (
        sort_column.asc()
        if sort_order == "asc"
        else sort_column.desc()
    )

    offset = (page - 1) * limit

    result = await session.execute(
        select(Ticket, Initiator, Operator)
        .join(Initiator, Ticket.initiator_id == Initiator.id)
        .outerjoin(Operator, Ticket.operator_id == Operator.id)
        .where(*filters)
        .order_by(order_expression, Ticket.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    return [
        (ticket, initiator, operator)
        for ticket, initiator, operator in result.all()
    ], total

async def get_operator_tickets_list(
    session: AsyncSession,
    *,
    operator: User,
    search: str | None = None,
    status: TicketStatus | None = None,
    is_priority: bool | None = None,
    page: int = 1,
    limit: int = 10,
    sort_by: str | None = None,
    sort_order: Literal["asc", "desc"] = "desc",
) -> tuple[list[tuple[Ticket, User, User | None]], int]:
    Initiator = aliased(User)
    Operator = aliased(User)

    filters = [
        or_(
            Ticket.operator_id == operator.id,
            and_(
                Ticket.is_operator_requested.is_(True),
                Ticket.status == TicketStatus.pending,
            ),
        ),
    ]

    if search:
        normalized_search = f"%{search.lower()}%"

        filters.append(
            or_(
                func.lower(Ticket.title).like(normalized_search),
                func.lower(Initiator.full_name).like(normalized_search),
                func.lower(Initiator.email).like(normalized_search),
            )
        )

    if status is not None:
        filters.append(Ticket.status == status)

    if is_priority is not None:
        filters.append(Ticket.is_priority.is_(is_priority))

    total_result = await session.execute(
        select(func.count(Ticket.id))
        .select_from(Ticket)
        .join(Initiator, Ticket.initiator_id == Initiator.id)
        .outerjoin(Operator, Ticket.operator_id == Operator.id)
        .where(*filters)
    )

    total = total_result.scalar_one()

    sort_columns = {
        "title": Ticket.title,
        "status": Ticket.status,
        "createdAt": Ticket.created_at,
        "updatedAt": Ticket.updated_at,
        "isPriority": Ticket.is_priority,
        "initiator": Initiator.full_name,
        "operator": Operator.full_name,
    }

    sort_column = sort_columns.get(sort_by or "createdAt", Ticket.created_at)

    order_expression = (
        sort_column.asc()
        if sort_order == "asc"
        else sort_column.desc()
    )

    offset = (page - 1) * limit

    result = await session.execute(
        select(Ticket, Initiator, Operator)
        .join(Initiator, Ticket.initiator_id == Initiator.id)
        .outerjoin(Operator, Ticket.operator_id == Operator.id)
        .where(*filters)
        .order_by(order_expression, Ticket.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    return [
        (ticket, initiator, assigned_operator)
        for ticket, initiator, assigned_operator in result.all()
    ], total

async def update_ticket_priority(
    session: AsyncSession,
    ticket: Ticket,
    is_priority: bool,
) -> Ticket:
    ticket.is_priority = is_priority

    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)

    return ticket


async def assign_ticket_by_manager(
    session: AsyncSession,
    ticket: Ticket,
    operator: User,
) -> Ticket:
    if operator.role != UserRole.operator:
        raise ValueError("Назначить можно только пользователя с ролью оператора")

    if operator.is_blocked:
        raise ValueError("Нельзя назначить заблокированного оператора")

    if ticket.status == TicketStatus.closed:
        raise ValueError("Нельзя назначить оператора на закрытый тикет")

    ticket.operator_id = operator.id
    ticket.status = TicketStatus.in_progress
    ticket.is_operator_requested = True

    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)

    return ticket

async def update_ticket_status(
    session: AsyncSession,
    ticket: Ticket,
    next_status: TicketStatus,
) -> Ticket:
    if next_status == TicketStatus.pending:
        ticket.status = TicketStatus.pending
        ticket.operator_id = None
        ticket.is_operator_requested = True
        ticket.closed_at = None

    elif next_status == TicketStatus.in_progress:
        if ticket.operator_id is None:
            raise ValueError(
                "Нельзя перевести тикет в работу без назначенного оператора",
            )

        ticket.status = TicketStatus.in_progress
        ticket.is_operator_requested = True
        ticket.closed_at = None

    elif next_status == TicketStatus.closed:
        ticket.status = TicketStatus.closed

        if ticket.closed_at is None:
            ticket.closed_at = datetime.now(timezone.utc)

    else:
        raise ValueError("Некорректный статус тикета")

    ticket.updated_at = datetime.now(timezone.utc)

    session.add(ticket)

    if next_status == TicketStatus.closed:
        await add_rating_request_message_if_needed(session, ticket)

    await session.commit()

    updated_ticket = await get_ticket_by_id(session, ticket.id)

    if not updated_ticket:
        raise RuntimeError("Не удалось получить обновлённый тикет")

    return updated_ticket

async def rate_ticket_by_initiator(
    session: AsyncSession,
    *,
    ticket: Ticket,
    initiator: User,
    rating: int,
    comment: str | None,
) -> Ticket:
    if ticket.initiator_id != initiator.id:
        raise ValueError("Нельзя оценить чужой тикет")

    if ticket.status != TicketStatus.closed:
        raise ValueError("Оценить можно только закрытый тикет")

    normalized_comment = comment.strip() if comment and comment.strip() else None
    is_update = ticket.rating is not None

    if ticket.rating:
        ticket.rating.rating = rating
        ticket.rating.comment = normalized_comment
        session.add(ticket.rating)
    else:
        ticket_rating = TicketRating(
            ticket_id=ticket.id,
            initiator_id=initiator.id,
            rating=rating,
            comment=normalized_comment,
        )

        session.add(ticket_rating)

    feedback_message = TicketMessage(
        ticket_id=ticket.id,
        sender_id=None,
        sender_type=MessageSenderType.bot,
        kind=TicketMessageKind.rating_submitted,
        text=build_rating_submitted_message(
            rating=rating,
            comment=normalized_comment,
            is_update=is_update,
        ),
    )

    ticket.updated_at = datetime.now(timezone.utc)

    session.add(ticket)
    session.add(feedback_message)

    await session.commit()

    updated_ticket = await get_ticket_by_id(session, ticket.id)

    if not updated_ticket:
        raise RuntimeError("Не удалось получить обновлённый тикет")

    return updated_ticket
