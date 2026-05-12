from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.db.session import get_session
from app.modules.analytics.model.schemas import (
    AnalyticsPeriod,
    ServiceManagerAnalyticsRead,
)
from app.modules.analytics.service.analytics_report_service import (
    build_analytics_report_workbook,
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


@router.get("/service-manager/report")
async def export_service_manager_analytics_report(
    period: AnalyticsPeriod = Query(default=AnalyticsPeriod.week),
    _service_manager: User = Depends(require_roles(UserRole.service_manager)),
    session: AsyncSession = Depends(get_session),
):
    raw_analytics = await get_service_manager_analytics(
        session=session,
        period=period,
    )

    analytics = ServiceManagerAnalyticsRead.model_validate(raw_analytics)

    report = build_analytics_report_workbook(
        analytics=analytics,
        period=period,
    )

    current_date = datetime.now().date().isoformat()
    filename = f"intelliticket-analytics-{period.value}-{current_date}.xlsx"

    return StreamingResponse(
        report,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )