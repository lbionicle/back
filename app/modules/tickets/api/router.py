from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.tickets.model.models import TicketStatus
from app.modules.tickets.model.schemas import (
    CreateTicketRequest,
    SendTicketMessageRequest,
    TicketAssignRequest,
    TicketDetailsRead,
    TicketListResponse,
    TicketPriorityUpdateRequest,
    TicketRead,
    TicketStatsRead,
    TicketTableRead,
    TicketUserRead, TicketStatusUpdateRequest, TicketRatingRequest,
)
from app.modules.tickets.service.ticket_service import (
    assign_ticket_by_manager,
    assign_ticket_to_operator,
    close_ticket,
    create_initiator_message,
    create_operator_message,
    create_ticket,
    delete_ticket,
    get_assigned_operator_tickets,
    get_available_operator_tickets,
    get_initiator_tickets,
    get_manager_tickets_list,
    get_manager_tickets_stats,
    get_operator_tickets_list,
    get_operator_tickets_stats,
    get_ticket_by_id,
    request_operator,
    update_ticket_priority,
    update_ticket_status, rate_ticket_by_initiator
)
from app.modules.users.model.models import User, UserRole
from app.modules.users.service.user_service import get_user_by_id
from app.shared.dependencies import get_current_user, require_roles

router = APIRouter()

def build_ticket_table_read(
    ticket,
    initiator,
    operator,
) -> TicketTableRead:
    return TicketTableRead(
        id=ticket.id,
        title=ticket.title,
        status=ticket.status,
        is_priority=ticket.is_priority,
        is_operator_requested=ticket.is_operator_requested,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        closed_at=ticket.closed_at,
        initiator=TicketUserRead(
            id=initiator.id,
            full_name=initiator.full_name,
            email=initiator.email,
            role=initiator.role,
            avatar_url=initiator.avatar_url,
        ),
        operator=TicketUserRead(
            id=operator.id,
            full_name=operator.full_name,
            email=operator.email,
            role=operator.role,
            avatar_url=operator.avatar_url,
        )
        if operator
        else None,
    )

@router.post(
    "",
    response_model=TicketDetailsRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_my_ticket(
    data: CreateTicketRequest,
    current_user: User = Depends(require_roles(UserRole.initiator)),
    session: AsyncSession = Depends(get_session),
):
    return await create_ticket(
        session=session,
        initiator=current_user,
        message_text=data.message,
    )


@router.get("/my", response_model=list[TicketRead])
async def get_my_tickets(
    current_user: User = Depends(require_roles(UserRole.initiator)),
    session: AsyncSession = Depends(get_session),
):
    return await get_initiator_tickets(session, current_user)


@router.get("/manager/stats", response_model=TicketStatsRead)
async def get_manager_tickets_stats_endpoint(
    session: AsyncSession = Depends(get_session),
    _service_manager: User = Depends(require_roles(UserRole.service_manager)),
):
    stats = await get_manager_tickets_stats(session)

    return TicketStatsRead(
        totalTicketsCount=stats["total_tickets_count"],
        priorityTicketsCount=stats["priority_tickets_count"],
        pendingTicketsCount=stats["pending_tickets_count"],
        inProgressTicketsCount=stats["in_progress_tickets_count"],
        closedTicketsCount=stats["closed_tickets_count"],
    )


@router.get("/manager", response_model=TicketListResponse)
async def get_manager_tickets_endpoint(
    search: str | None = None,
    status_filter: TicketStatus | None = Query(default=None, alias="status"),
    is_priority: bool | None = Query(default=None, alias="isPriority"),
    operator_id: UUID | None = Query(default=None, alias="operatorId"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    sort_by: str | None = Query(default=None, alias="sortBy"),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
    session: AsyncSession = Depends(get_session),
    _service_manager: User = Depends(require_roles(UserRole.service_manager)),
):
    tickets, total = await get_manager_tickets_list(
        session=session,
        search=search,
        status=status_filter,
        is_priority=is_priority,
        operator_id=operator_id,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return TicketListResponse(
        items=[
            build_ticket_table_read(ticket, initiator, operator)
            for ticket, initiator, operator in tickets
        ],
        total=total,
        page=page,
        limit=limit,
    )

@router.get("/{ticket_id}", response_model=TicketDetailsRead)
async def get_ticket_details(
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    ticket = await get_ticket_by_id(session, ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тикет не найден",
        )

    is_initiator_owner = (
        current_user.role == UserRole.initiator
        and ticket.initiator_id == current_user.id
    )
    is_assigned_operator = (
        current_user.role == UserRole.operator
        and ticket.operator_id == current_user.id
    )
    is_available_for_operator = (
        current_user.role == UserRole.operator
        and ticket.is_operator_requested
        and ticket.status == TicketStatus.pending
    )
    is_service_manager = current_user.role == UserRole.service_manager

    if not (
        is_initiator_owner
        or is_assigned_operator
        or is_available_for_operator
        or is_service_manager
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для просмотра тикета",
        )

    return ticket

@router.put("/{ticket_id}/rating", response_model=TicketDetailsRead)
async def rate_ticket_endpoint(
    ticket_id: UUID,
    data: TicketRatingRequest,
    current_user: User = Depends(require_roles(UserRole.initiator)),
    session: AsyncSession = Depends(get_session),
):
    ticket = await get_ticket_by_id(session, ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тикет не найден",
        )

    if ticket.initiator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нельзя оценить чужой тикет",
        )

    try:
        return await rate_ticket_by_initiator(
            session=session,
            ticket=ticket,
            initiator=current_user,
            rating=data.rating,
            comment=data.comment,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

@router.patch("/{ticket_id}/priority", response_model=TicketRead)
async def update_ticket_priority_endpoint(
    ticket_id: UUID,
    data: TicketPriorityUpdateRequest,
    current_user: User = Depends(require_roles(UserRole.service_manager)),
    session: AsyncSession = Depends(get_session),
):
    ticket = await get_ticket_by_id(session, ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тикет не найден",
        )

    return await update_ticket_priority(
        session=session,
        ticket=ticket,
        is_priority=data.is_priority,
    )

@router.patch("/{ticket_id}/status", response_model=TicketRead)
async def update_ticket_status_endpoint(
    ticket_id: UUID,
    data: TicketStatusUpdateRequest,
    current_user: User = Depends(
        require_roles(UserRole.operator, UserRole.service_manager),
    ),
    session: AsyncSession = Depends(get_session),
):
    ticket = await get_ticket_by_id(session, ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тикет не найден",
        )

    if (
        current_user.role == UserRole.operator
        and ticket.operator_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Оператор может менять статус только назначенного ему тикета",
        )

    try:
        return await update_ticket_status(
            session=session,
            ticket=ticket,
            next_status=data.status,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

@router.patch("/{ticket_id}/assign", response_model=TicketRead)
async def assign_ticket_by_manager_endpoint(
    ticket_id: UUID,
    data: TicketAssignRequest,
    current_user: User = Depends(require_roles(UserRole.service_manager)),
    session: AsyncSession = Depends(get_session),
):
    ticket = await get_ticket_by_id(session, ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тикет не найден",
        )

    operator = await get_user_by_id(session, data.operator_id)

    if not operator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Оператор не найден",
        )

    try:
        return await assign_ticket_by_manager(
            session=session,
            ticket=ticket,
            operator=operator,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

@router.post("/{ticket_id}/request-operator", response_model=TicketDetailsRead)
async def request_operator_for_ticket(
    ticket_id: UUID,
    current_user: User = Depends(require_roles(UserRole.initiator)),
    session: AsyncSession = Depends(get_session),
):
    ticket = await get_ticket_by_id(session, ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тикет не найден",
        )

    if ticket.initiator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нельзя запросить оператора для чужого тикета",
        )

    if ticket.status == TicketStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя запросить оператора для закрытого тикета",
        )

    if ticket.is_operator_requested:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Оператор уже запрошен",
        )

    return await request_operator(session, ticket)


@router.post("/{ticket_id}/messages", response_model=TicketDetailsRead)
async def send_ticket_message(
    ticket_id: UUID,
    data: SendTicketMessageRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    ticket = await get_ticket_by_id(session, ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тикет не найден",
        )

    if ticket.status == TicketStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя отправить сообщение в закрытый тикет",
        )

    if current_user.role == UserRole.initiator:
        if ticket.initiator_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нельзя писать в чужой тикет",
            )

        if ticket.is_operator_requested and ticket.status == TicketStatus.pending:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ожидайте подключения оператора",
            )

        return await create_initiator_message(
            session=session,
            ticket=ticket,
            initiator=current_user,
            text=data.text,
        )

    if current_user.role == UserRole.operator:
        if ticket.operator_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Оператор может писать только в назначенный ему тикет",
            )

        return await create_operator_message(
            session=session,
            ticket=ticket,
            operator=current_user,
            text=data.text,
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Недостаточно прав для отправки сообщения",
    )


operator_router = APIRouter()


@operator_router.get("", response_model=list[TicketRead])
async def get_operator_available_tickets(
    current_user: User = Depends(require_roles(UserRole.operator)),
    session: AsyncSession = Depends(get_session),
):
    return await get_available_operator_tickets(session)


@operator_router.get("/my", response_model=list[TicketRead])
async def get_my_operator_tickets(
    current_user: User = Depends(require_roles(UserRole.operator)),
    session: AsyncSession = Depends(get_session),
):
    return await get_assigned_operator_tickets(session, current_user)


@operator_router.get("/stats", response_model=TicketStatsRead)
async def get_operator_tickets_stats_endpoint(
    current_user: User = Depends(require_roles(UserRole.operator)),
    session: AsyncSession = Depends(get_session),
):
    stats = await get_operator_tickets_stats(session, current_user)

    return TicketStatsRead(
        totalTicketsCount=stats["total_tickets_count"],
        priorityTicketsCount=stats["priority_tickets_count"],
        pendingTicketsCount=stats["pending_tickets_count"],
        inProgressTicketsCount=stats["in_progress_tickets_count"],
        closedTicketsCount=stats["closed_tickets_count"],
    )


@operator_router.get("/list", response_model=TicketListResponse)
async def get_operator_tickets_list_endpoint(
    search: str | None = None,
    status_filter: TicketStatus | None = Query(default=None, alias="status"),
    is_priority: bool | None = Query(default=None, alias="isPriority"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    sort_by: str | None = Query(default=None, alias="sortBy"),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
    current_user: User = Depends(require_roles(UserRole.operator)),
    session: AsyncSession = Depends(get_session),
):
    tickets, total = await get_operator_tickets_list(
        session=session,
        operator=current_user,
        search=search,
        status=status_filter,
        is_priority=is_priority,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return TicketListResponse(
        items=[
            build_ticket_table_read(ticket, initiator, operator)
            for ticket, initiator, operator in tickets
        ],
        total=total,
        page=page,
        limit=limit,
    )

@operator_router.post("/{ticket_id}/assign-me", response_model=TicketRead)
async def assign_me_to_ticket(
    ticket_id: UUID,
    current_user: User = Depends(require_roles(UserRole.operator)),
    session: AsyncSession = Depends(get_session),
):
    ticket = await get_ticket_by_id(session, ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тикет не найден",
        )

    if not ticket.is_operator_requested:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Инициатор ещё не запрашивал оператора",
        )

    if ticket.status != TicketStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Тикет уже находится в работе или закрыт",
        )

    try:
        return await assign_ticket_to_operator(session, ticket, current_user)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

@operator_router.post("/{ticket_id}/close", response_model=TicketRead)
async def close_operator_ticket(
    ticket_id: UUID,
    current_user: User = Depends(require_roles(UserRole.operator)),
    session: AsyncSession = Depends(get_session),
):
    ticket = await get_ticket_by_id(session, ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тикет не найден",
        )

    if ticket.operator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Оператор может закрыть только свой тикет",
        )

    if ticket.status == TicketStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Тикет уже закрыт",
        )

    return await close_ticket(session, ticket)

@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket_by_id(
    ticket_id: UUID,
    current_user: User = Depends(
        require_roles(
            UserRole.initiator,
            UserRole.operator,
            UserRole.service_manager,
        ),
    ),
    session: AsyncSession = Depends(get_session),
):
    ticket = await get_ticket_by_id(session, ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тикет не найден",
        )

    if (
        current_user.role == UserRole.initiator
        and ticket.initiator_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нельзя удалить чужой тикет",
        )

    if (
        current_user.role == UserRole.operator
        and ticket.operator_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Оператор может удалить только назначенный ему тикет",
        )

    await delete_ticket(session, ticket)