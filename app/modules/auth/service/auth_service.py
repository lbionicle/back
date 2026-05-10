from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, verify_password
from app.modules.auth.model.schemas import AuthResponse, SignInRequest, SignUpRequest
from app.modules.users.model.models import UserRole
from app.modules.users.service.user_service import create_user, get_user_by_email


async def register_initiator(
    session: AsyncSession,
    data: SignUpRequest,
) -> AuthResponse:
    existing_user = await get_user_by_email(session, data.email)

    if existing_user:
        raise ValueError("Пользователь с такой почтой уже существует")

    user = await create_user(
        session=session,
        full_name=data.full_name,
        email=data.email,
        password=data.password,
        role=UserRole.initiator,
    )

    access_token = create_access_token(
        subject=str(user.id),
        role=user.role.value,
    )

    return AuthResponse(
        accessToken=access_token,
        user=user,
    )


async def authenticate_user(
    session: AsyncSession,
    data: SignInRequest,
) -> AuthResponse | None:
    user = await get_user_by_email(session, data.email)

    if not user:
        return None

    if user.is_blocked:
        return None

    if not verify_password(data.password, user.password_hash):
        return None

    access_token = create_access_token(
        subject=str(user.id),
        role=user.role.value,
    )

    return AuthResponse(
        accessToken=access_token,
        user=user,
    )