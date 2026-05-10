from fastapi import APIRouter

from app.modules.analytics.api.router import router as analytics_router
from app.modules.auth.api.router import router as auth_router
from app.modules.tickets.api.router import (
    operator_router as operator_tickets_router,
)
from app.modules.tickets.api.router import router as tickets_router
from app.modules.users.api.router import router as users_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(tickets_router, prefix="/tickets", tags=["Tickets"])
api_router.include_router(
    operator_tickets_router,
    prefix="/operator/tickets",
    tags=["Operator tickets"],
)
api_router.include_router(
    analytics_router,
    prefix="/analytics",
    tags=["Analytics"],
)