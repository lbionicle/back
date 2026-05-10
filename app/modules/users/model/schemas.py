import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.users.model.models import UserRole


class UserRead(BaseModel):
    id: UUID
    full_name: str = Field(alias="fullName")
    email: EmailStr
    role: UserRole
    avatar_url: str | None = Field(default=None, serialization_alias="avatarUrl")
    is_blocked: bool = Field(alias="isBlocked")
    created_at: datetime = Field(alias="createdAt")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

class UserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, alias="fullName", min_length=2, max_length=255)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)

    model_config = ConfigDict(populate_by_name=True)

class OperatorCreateRequest(BaseModel):
    full_name: str = Field(alias="fullName", min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)

    model_config = ConfigDict(populate_by_name=True)

class UserListResponse(BaseModel):
    items: list[UserRead]
    total: int
    page: int
    limit: int


class UserStatsRead(BaseModel):
    operators_count: int = Field(alias="operatorsCount")
    initiators_count: int = Field(alias="initiatorsCount")

    model_config = ConfigDict(populate_by_name=True)

class OperatorAvailability(str, enum.Enum):
    free = "free"
    busy = "busy"


class OperatorRead(UserRead):
    availability: OperatorAvailability
    active_tickets_count: int = Field(alias="activeTicketsCount")
    solved_tickets_count: int = Field(alias="solvedTicketsCount")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class OperatorListResponse(BaseModel):
    items: list[OperatorRead]
    total: int
    page: int
    limit: int


class OperatorStatsRead(BaseModel):
    busy_operators_count: int = Field(alias="busyOperatorsCount")
    free_operators_count: int = Field(alias="freeOperatorsCount")

    model_config = ConfigDict(populate_by_name=True)

class ManagerUserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, alias="fullName", min_length=2, max_length=255)
    email: EmailStr | None = None
    role: UserRole | None = None

    model_config = ConfigDict(populate_by_name=True)