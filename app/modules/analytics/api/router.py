from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.analytics.model.schemas import (
    AnalyticsPeriod,
    ServiceManagerAnalyticsRead,
)
from app.modules.analytics.service.analytics_service import (
    get_service_manager_analytics,
)
from app.modules.users.model.models import User, UserRole
from app.shared.dependencies import require_roles

router = APIRouter()


@router.get("/service-manager", response_model=ServiceManagerAnalyticsRead)
async def get_service_manager_analytics_endpoint(
    period: AnalyticsPeriod = Query(default=AnalyticsPeriod.week),
    session: AsyncSession = Depends(get_session),
    _service_manager: User = Depends(require_roles(UserRole.service_manager)),
):
    return await get_service_manager_analytics(
        session=session,
        period=period,
    )