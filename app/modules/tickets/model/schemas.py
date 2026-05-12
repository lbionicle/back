from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tickets.model.models import (
    MessageSenderType,
    TicketMessageKind,
    TicketStatus,
)
from app.modules.users.model.models import UserRole


class CreateTicketRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


class SendTicketMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class TicketMessageRead(BaseModel):
    id: UUID
    sender_id: UUID | None = Field(default=None, serialization_alias="senderId")
    sender_type: MessageSenderType = Field(serialization_alias="senderType")
    kind: TicketMessageKind
    text: str
    created_at: datetime = Field(serialization_alias="createdAt")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class TicketRead(BaseModel):
    id: UUID
    title: str
    initiator_id: UUID = Field(serialization_alias="initiatorId")
    operator_id: UUID | None = Field(default=None, serialization_alias="operatorId")
    status: TicketStatus
    is_operator_requested: bool = Field(serialization_alias="isOperatorRequested")
    is_priority: bool = Field(serialization_alias="isPriority")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")
    closed_at: datetime | None = Field(default=None, serialization_alias="closedAt")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class TicketRatingRead(BaseModel):
    id: UUID
    ticket_id: UUID = Field(serialization_alias="ticketId")
    initiator_id: UUID = Field(serialization_alias="initiatorId")
    rating: int
    comment: str | None = None
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class TicketRatingRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class TicketUserRead(BaseModel):
    id: UUID
    full_name: str = Field(serialization_alias="fullName")
    email: str
    role: UserRole
    avatar_url: str | None = Field(default=None, serialization_alias="avatarUrl")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class TicketDetailsRead(TicketRead):
    messages: list[TicketMessageRead]
    rating: TicketRatingRead | None = None
    initiator: TicketUserRead
    operator: TicketUserRead | None = None


class TicketTableRead(BaseModel):
    id: UUID
    title: str
    status: TicketStatus
    is_priority: bool = Field(serialization_alias="isPriority")
    is_operator_requested: bool = Field(serialization_alias="isOperatorRequested")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")
    closed_at: datetime | None = Field(default=None, serialization_alias="closedAt")
    initiator: TicketUserRead
    operator: TicketUserRead | None = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class TicketListResponse(BaseModel):
    items: list[TicketTableRead]
    total: int
    page: int
    limit: int


class TicketStatsRead(BaseModel):
    total_tickets_count: int = Field(alias="totalTicketsCount")
    priority_tickets_count: int = Field(alias="priorityTicketsCount")
    pending_tickets_count: int = Field(alias="pendingTicketsCount")
    in_progress_tickets_count: int = Field(alias="inProgressTicketsCount")
    closed_tickets_count: int = Field(alias="closedTicketsCount")

    model_config = ConfigDict(
        populate_by_name=True,
    )


class TicketAssignRequest(BaseModel):
    operator_id: UUID = Field(alias="operatorId")

    model_config = ConfigDict(
        populate_by_name=True,
    )


class TicketPriorityUpdateRequest(BaseModel):
    is_priority: bool = Field(alias="isPriority")

    model_config = ConfigDict(
        populate_by_name=True,
    )


class TicketStatusUpdateRequest(BaseModel):
    status: TicketStatus

    model_config = ConfigDict(
        populate_by_name=True,
    )