from fastapi import APIRouter, Depends, Response, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.modules.auth.model.schemas import AuthResponse, SignInRequest, SignUpRequest
from app.modules.auth.service.auth_service import authenticate_user, register_initiator
from app.modules.users.model.schemas import UserRead
from app.shared.dependencies import get_current_user

router = APIRouter()

def set_auth_cookie(response: Response, access_token: str) -> None:
    response.set_cookie(
        key="accessToken",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


@router.post(
    "/sign-up",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
async def sign_up(
    data: SignUpRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    try:
        auth_data = await register_initiator(session, data)
        set_auth_cookie(response, auth_data.access_token)
        return auth_data
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.post("/sign-in", response_model=AuthResponse)
async def sign_in(
    data: SignInRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    auth_data = await authenticate_user(session, data)

    if not auth_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверная почта или пароль",
        )

    set_auth_cookie(response, auth_data.access_token)

    return auth_data

@router.post("/sign-out", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out(response: Response):
    response.delete_cookie(
        key="accessToken",
        path="/",
        httponly=True,
        samesite="lax",
    )

@router.get("/me", response_model=UserRead)
async def get_me(current_user=Depends(get_current_user)):
    return current_user