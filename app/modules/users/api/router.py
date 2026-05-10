import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.users.model.models import UserRole, User
from app.modules.users.model.schemas import (
    ManagerUserUpdateRequest,
    OperatorCreateRequest,
    UserListResponse,
    UserRead,
    UserStatsRead,
    UserUpdateRequest,
    OperatorAvailability,
    OperatorListResponse,
    OperatorRead,
    OperatorStatsRead
)
from app.modules.users.service.user_service import (
    block_user,
    create_operator,
    delete_user,
    get_user_by_id,
    get_users_list,
    get_users_stats,
    save_user,
    unblock_user,
    update_current_user,
    update_user_by_manager,
    get_operators_list,
    get_operators_stats,
)
from app.shared.dependencies import require_roles, get_current_user

router = APIRouter()

AVATARS_DIR = Path("media/avatars")

ALLOWED_AVATAR_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
}

MAX_AVATAR_SIZE = 2 * 1024 * 1024


@router.post(
    "/operators",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_operator_endpoint(
    data: OperatorCreateRequest,
    session: AsyncSession = Depends(get_session),
    _service_manager=Depends(require_roles(UserRole.service_manager)),
):
    try:
        return await create_operator(session, data)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get("/operators/stats", response_model=OperatorStatsRead)
async def get_operators_stats_endpoint(
    session: AsyncSession = Depends(get_session),
    _service_manager: User = Depends(require_roles(UserRole.service_manager)),
):
    stats = await get_operators_stats(session)

    return OperatorStatsRead(
        busyOperatorsCount=stats["busy_operators_count"],
        freeOperatorsCount=stats["free_operators_count"],
    )


@router.get("/operators", response_model=OperatorListResponse)
async def get_operators_endpoint(
    search: str | None = Query(default=None),
    is_blocked: bool | None = Query(default=None, alias="isBlocked"),
    availability: OperatorAvailability | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    sort_by: str | None = Query(default=None, alias="sortBy"),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
    session: AsyncSession = Depends(get_session),
    _service_manager: User = Depends(require_roles(UserRole.service_manager)),
):
    operators, total = await get_operators_list(
        session=session,
        search=search,
        is_blocked=is_blocked,
        availability=availability.value if availability else None,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return OperatorListResponse(
        items=[
            build_operator_read(
                user=operator,
                active_tickets_count=active_tickets_count,
                solved_tickets_count=solved_tickets_count,
            )
            for operator, active_tickets_count, solved_tickets_count in operators
        ],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("/me/avatar", response_model=UserRead)
async def upload_my_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await save_avatar_file(file, current_user)

    return await save_user(session, current_user)



@router.patch("/me", response_model=UserRead)
async def update_me(
    data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await update_current_user(
            session=session,
            user=current_user,
            data=data,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

@router.get("/stats", response_model=UserStatsRead)
async def get_users_stats_endpoint(
    session: AsyncSession = Depends(get_session),
    _service_manager: User = Depends(require_roles(UserRole.service_manager)),
):
    stats = await get_users_stats(session)

    return UserStatsRead(
        operatorsCount=stats["operators_count"],
        initiatorsCount=stats["initiators_count"],
    )


@router.get("", response_model=UserListResponse)
async def get_users_endpoint(
    search: str | None = Query(default=None),
    role: UserRole | None = Query(default=None),
    is_blocked: bool | None = Query(default=None, alias="isBlocked"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    sort_by: str | None = Query(default=None, alias="sortBy"),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
    session: AsyncSession = Depends(get_session),
    _service_manager: User = Depends(require_roles(UserRole.service_manager)),
):
    users, total = await get_users_list(
        session=session,
        search=search,
        role=role,
        is_blocked=is_blocked,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return UserListResponse(
        items=users,
        total=total,
        page=page,
        limit=limit,
    )

@router.patch("/{user_id}", response_model=UserRead)
async def update_user_endpoint(
    user_id: uuid.UUID,
    data: ManagerUserUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(UserRole.service_manager)),
):
    user = await get_user_by_id(session, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя изменять собственный профиль через панель управления",
        )

    try:
        return await update_user_by_manager(
            session=session,
            user=user,
            data=data,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.patch("/{user_id}/block", response_model=UserRead)
async def block_user_endpoint(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(UserRole.service_manager)),
):
    user = await get_user_by_id(session, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя заблокировать собственный профиль",
        )

    try:
        return await block_user(session, user)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.patch("/{user_id}/unblock", response_model=UserRead)
async def unblock_user_endpoint(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(UserRole.service_manager)),
):
    user = await get_user_by_id(session, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя разблокировать собственный профиль через панель управления",
        )

    try:
        return await unblock_user(session, user)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

@router.post("/{user_id}/avatar", response_model=UserRead)
async def upload_user_avatar_by_manager(
    user_id: uuid.UUID,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(UserRole.service_manager)),
):
    user = await get_user_by_id(session, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для изменения собственного аватара используйте профиль",
        )

    if user.role == UserRole.service_manager:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя изменять аватар менеджера сервисного обслуживания",
        )

    await save_avatar_file(file, user)

    return await save_user(session, user)

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_endpoint(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(UserRole.service_manager)),
):
    user = await get_user_by_id(session, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя удалить собственный профиль",
        )

    try:
        await delete_user(session, user)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


def get_avatar_file_path(avatar_url: str | None) -> Path | None:
    if not avatar_url:
        return None

    prefix = "/media/avatars/"

    if not avatar_url.startswith(prefix):
        return None

    file_name = avatar_url.removeprefix(prefix)

    return AVATARS_DIR / file_name


async def save_avatar_file(file: UploadFile, user: User) -> None:
    if file.content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Можно загрузить только PNG или JPG",
        )

    content = await file.read()

    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Размер аватара не должен превышать 2 МБ",
        )

    AVATARS_DIR.mkdir(parents=True, exist_ok=True)

    old_avatar_path = get_avatar_file_path(user.avatar_url)

    extension = ALLOWED_AVATAR_TYPES[file.content_type]
    file_name = f"{user.id}-{uuid.uuid4().hex}{extension}"
    file_path = AVATARS_DIR / file_name

    file_path.write_bytes(content)

    if old_avatar_path and old_avatar_path.exists():
        old_avatar_path.unlink()

    user.avatar_url = f"/media/avatars/{file_name}"

def build_operator_read(
    user: User,
    active_tickets_count: int,
    solved_tickets_count: int,
) -> OperatorRead:
    availability = (
        OperatorAvailability.busy
        if active_tickets_count > 0
        else OperatorAvailability.free
    )

    return OperatorRead(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        avatar_url=user.avatar_url,
        is_blocked=user.is_blocked,
        created_at=user.created_at,
        availability=availability,
        active_tickets_count=active_tickets_count,
        solved_tickets_count=solved_tickets_count,
    )