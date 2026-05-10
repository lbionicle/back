import uuid
from typing import Literal

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.modules.tickets.model.models import Ticket, TicketStatus
from app.modules.users.model.models import User, UserRole
from app.modules.users.model.schemas import OperatorCreateRequest, UserUpdateRequest, ManagerUserUpdateRequest


async def get_user_by_email(
    session: AsyncSession,
    email: str,
) -> User | None:
    result = await session.execute(
        select(User).where(User.email == email.lower()),
    )

    return result.scalar_one_or_none()


async def get_user_by_id(
    session: AsyncSession,
    user_id: str | uuid.UUID,
) -> User | None:
    result = await session.execute(
        select(User).where(User.id == user_id),
    )

    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    *,
    full_name: str,
    email: str,
    password: str,
    role: UserRole,
) -> User:
    user = User(
        full_name=full_name,
        email=email.lower(),
        password_hash=hash_password(password),
        role=role,
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


async def create_operator(
    session: AsyncSession,
    data: OperatorCreateRequest,
) -> User:
    existing_user = await get_user_by_email(session, data.email)

    if existing_user:
        raise ValueError("Пользователь с такой почтой уже существует")

    return await create_user(
        session=session,
        full_name=data.full_name,
        email=data.email,
        password=data.password,
        role=UserRole.operator,
    )


async def update_current_user(
    session: AsyncSession,
    user: User,
    data: UserUpdateRequest,
) -> User:
    if data.email and data.email != user.email:
        existing_user = await get_user_by_email(session, data.email)

        if existing_user:
            raise ValueError("Пользователь с такой почтой уже существует")

        user.email = data.email

    if data.full_name is not None:
        user.full_name = data.full_name

    if data.password:
        user.password_hash = hash_password(data.password)

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user

async def ensure_service_manager_exists(session: AsyncSession) -> None:
    existing_user = await get_user_by_email(session, settings.service_manager_email)

    if existing_user:
        return

    await create_user(
        session=session,
        full_name=settings.service_manager_full_name,
        email=settings.service_manager_email,
        password=settings.service_manager_password,
        role=UserRole.service_manager,
    )


async def save_user(session: AsyncSession, user: User) -> User:
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user

async def get_users_stats(session: AsyncSession) -> dict[str, int]:
    operators_count_result = await session.execute(
        select(func.count(User.id)).where(User.role == UserRole.operator),
    )

    initiators_count_result = await session.execute(
        select(func.count(User.id)).where(User.role == UserRole.initiator),
    )

    return {
        "operators_count": operators_count_result.scalar_one(),
        "initiators_count": initiators_count_result.scalar_one(),
    }


async def get_users_list(
    session: AsyncSession,
    *,
    search: str | None = None,
    role: UserRole | None = None,
    is_blocked: bool | None = None,
    page: int = 1,
    limit: int = 10,
    sort_by: str | None = None,
    sort_order: str = "desc",
) -> tuple[list[User], int]:
    filters = [
        User.role != UserRole.service_manager,
    ]

    if search:
        normalized_search = f"%{search.lower()}%"

        filters.append(
            or_(
                func.lower(User.full_name).like(normalized_search),
                func.lower(User.email).like(normalized_search),
            ),
        )

    if role:
        filters.append(User.role == role)

    if is_blocked is not None:
        filters.append(User.is_blocked.is_(is_blocked))

    total_result = await session.execute(
        select(func.count(User.id)).where(*filters),
    )

    total = total_result.scalar_one()

    offset = (page - 1) * limit

    sort_columns = {
        "fullName": User.full_name,
        "email": User.email,
        "role": User.role,
        "isBlocked": User.is_blocked,
        "createdAt": User.created_at,
    }

    sort_column = sort_columns.get(sort_by or "createdAt", User.created_at)

    order_expression = (
        sort_column.asc()
        if sort_order == "asc"
        else sort_column.desc()
    )

    users_result = await session.execute(
        select(User)
        .where(*filters)
        .order_by(order_expression)
        .offset(offset)
        .limit(limit),
    )

    return list(users_result.scalars().all()), total


async def update_user_by_manager(
    session: AsyncSession,
    *,
    user: User,
    data: ManagerUserUpdateRequest,
) -> User:
    if user.role == UserRole.service_manager:
        raise ValueError("Нельзя изменять профиль менеджера сервисного обслуживания")

    if data.email and data.email.lower() != user.email:
        existing_user = await get_user_by_email(session, data.email)

        if existing_user:
            raise ValueError("Пользователь с такой почтой уже существует")

        user.email = data.email.lower()

    if data.full_name is not None:
        user.full_name = data.full_name

    if data.role is not None:
        if data.role == UserRole.service_manager:
            raise ValueError("Нельзя назначить роль менеджера сервисного обслуживания")

        user.role = data.role

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


async def block_user(
    session: AsyncSession,
    user: User,
) -> User:
    if user.role == UserRole.service_manager:
        raise ValueError("Нельзя заблокировать менеджера сервисного обслуживания")

    user.is_blocked = True

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


async def unblock_user(
    session: AsyncSession,
    user: User,
) -> User:
    if user.role == UserRole.service_manager:
        raise ValueError("Нельзя разблокировать менеджера сервисного обслуживания")

    user.is_blocked = False

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


async def delete_user(
    session: AsyncSession,
    user: User,
) -> None:
    if user.role == UserRole.service_manager:
        raise ValueError("Нельзя удалить менеджера сервисного обслуживания")

    await session.delete(user)
    await session.commit()

def get_operator_ticket_counts_subqueries():
    active_tickets_subquery = (
        select(
            Ticket.operator_id.label("operator_id"),
            func.count(Ticket.id).label("active_tickets_count"),
        )
        .where(Ticket.operator_id.is_not(None))
        .where(Ticket.status == TicketStatus.in_progress)
        .group_by(Ticket.operator_id)
        .subquery()
    )

    solved_tickets_subquery = (
        select(
            Ticket.operator_id.label("operator_id"),
            func.count(Ticket.id).label("solved_tickets_count"),
        )
        .where(Ticket.operator_id.is_not(None))
        .where(Ticket.status == TicketStatus.closed)
        .group_by(Ticket.operator_id)
        .subquery()
    )

    return active_tickets_subquery, solved_tickets_subquery


async def get_operators_stats(session: AsyncSession) -> dict[str, int]:
    active_tickets_subquery, _ = get_operator_ticket_counts_subqueries()

    active_tickets_count = func.coalesce(
        active_tickets_subquery.c.active_tickets_count,
        0,
    )

    result = await session.execute(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (active_tickets_count > 0, 1),
                        else_=0,
                    ),
                ),
                0,
            ).label("busy_operators_count"),
            func.coalesce(
                func.sum(
                    case(
                        (active_tickets_count == 0, 1),
                        else_=0,
                    ),
                ),
                0,
            ).label("free_operators_count"),
        )
        .select_from(User)
        .outerjoin(
            active_tickets_subquery,
            User.id == active_tickets_subquery.c.operator_id,
        )
        .where(User.role == UserRole.operator)
    )

    row = result.one()

    return {
        "busy_operators_count": row.busy_operators_count,
        "free_operators_count": row.free_operators_count,
    }

async def get_operators_list(
    session: AsyncSession,
    *,
    search: str | None = None,
    is_blocked: bool | None = None,
    availability: Literal["free", "busy"] | None = None,
    page: int = 1,
    limit: int = 10,
    sort_by: str | None = None,
    sort_order: str = "desc",
) -> tuple[list[tuple[User, int, int]], int]:
    active_tickets_subquery, solved_tickets_subquery = (
        get_operator_ticket_counts_subqueries()
    )

    active_tickets_count = func.coalesce(
        active_tickets_subquery.c.active_tickets_count,
        0,
    )

    solved_tickets_count = func.coalesce(
        solved_tickets_subquery.c.solved_tickets_count,
        0,
    )

    filters = [
        User.role == UserRole.operator,
    ]

    if search:
        normalized_search = f"%{search.lower()}%"

        filters.append(
            or_(
                func.lower(User.full_name).like(normalized_search),
                func.lower(User.email).like(normalized_search),
            ),
        )

    if is_blocked is not None:
        filters.append(User.is_blocked.is_(is_blocked))

    if availability == "busy":
        filters.append(active_tickets_count > 0)

    if availability == "free":
        filters.append(active_tickets_count == 0)

    total_result = await session.execute(
        select(func.count(User.id))
        .select_from(User)
        .outerjoin(
            active_tickets_subquery,
            User.id == active_tickets_subquery.c.operator_id,
        )
        .where(*filters)
    )

    total = total_result.scalar_one()

    offset = (page - 1) * limit

    sort_columns = {
        "fullName": User.full_name,
        "email": User.email,
        "isBlocked": User.is_blocked,
        "createdAt": User.created_at,
        "availability": active_tickets_count,
        "activeTicketsCount": active_tickets_count,
        "solvedTicketsCount": solved_tickets_count,
    }

    sort_column = sort_columns.get(sort_by or "createdAt", User.created_at)

    order_expression = (
        sort_column.asc()
        if sort_order == "asc"
        else sort_column.desc()
    )

    result = await session.execute(
        select(
            User,
            active_tickets_count.label("active_tickets_count"),
            solved_tickets_count.label("solved_tickets_count"),
        )
        .select_from(User)
        .outerjoin(
            active_tickets_subquery,
            User.id == active_tickets_subquery.c.operator_id,
        )
        .outerjoin(
            solved_tickets_subquery,
            User.id == solved_tickets_subquery.c.operator_id,
        )
        .where(*filters)
        .order_by(order_expression, User.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    return [
        (
            row.User,
            row.active_tickets_count,
            row.solved_tickets_count,
        )
        for row in result.all()
    ], total