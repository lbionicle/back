from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.model.schemas import AnalyticsPeriod
from app.modules.tickets.model.models import Ticket, TicketRating, TicketStatus


def get_period_start(period: AnalyticsPeriod) -> datetime:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == AnalyticsPeriod.week:
        return today_start - timedelta(days=6)

    if period == AnalyticsPeriod.month:
        return today_start - timedelta(days=29)

    if period == AnalyticsPeriod.three_months:
        return today_start - timedelta(days=89)

    if period == AnalyticsPeriod.six_months:
        return today_start - timedelta(days=179)

    return today_start - timedelta(days=6)


def build_empty_date_map(start_date: date, end_date: date) -> dict[str, int]:
    result: dict[str, int] = {}
    current_date = start_date

    while current_date <= end_date:
        result[current_date.isoformat()] = 0
        current_date += timedelta(days=1)

    return result


def build_empty_resolution_map(
    start_date: date,
    end_date: date,
) -> dict[str, int | None]:
    result: dict[str, int | None] = {}
    current_date = start_date

    while current_date <= end_date:
        result[current_date.isoformat()] = None
        current_date += timedelta(days=1)

    return result


def normalize_day(value) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()

    if isinstance(value, date):
        return value.isoformat()

    return str(value)


async def get_service_manager_analytics(
    session: AsyncSession,
    period: AnalyticsPeriod,
) -> dict:
    period_start = get_period_start(period)
    now = datetime.now(timezone.utc)

    start_date = period_start.date()
    end_date = now.date()

    resolution_minutes_expression = (
        func.extract("epoch", Ticket.closed_at - Ticket.created_at) / 60
    )

    total_tickets_result = await session.execute(
        select(func.count(Ticket.id)).where(Ticket.created_at >= period_start),
    )

    closed_tickets_result = await session.execute(
        select(func.count(Ticket.id))
        .where(Ticket.status == TicketStatus.closed)
        .where(Ticket.closed_at.is_not(None))
        .where(Ticket.closed_at >= period_start),
    )

    average_resolution_result = await session.execute(
        select(func.avg(resolution_minutes_expression))
        .where(Ticket.status == TicketStatus.closed)
        .where(Ticket.closed_at.is_not(None))
        .where(Ticket.closed_at >= period_start),
    )

    average_rating_result = await session.execute(
        select(func.avg(TicketRating.rating)).where(
            TicketRating.created_at >= period_start,
        ),
    )

    total_tickets_count = total_tickets_result.scalar_one()
    closed_tickets_count = closed_tickets_result.scalar_one()
    average_resolution = average_resolution_result.scalar_one()
    average_rating = average_rating_result.scalar_one()

    created_tickets_map = build_empty_date_map(start_date, end_date)

    created_day = func.date_trunc("day", Ticket.created_at).label("day")

    created_tickets_result = await session.execute(
        select(
            created_day,
            func.count(Ticket.id).label("count"),
        )
        .where(Ticket.created_at >= period_start)
        .group_by(created_day)
        .order_by(created_day),
    )

    for row in created_tickets_result.all():
        created_tickets_map[normalize_day(row.day)] = row.count

    status_counts = {
        TicketStatus.pending: 0,
        TicketStatus.in_progress: 0,
        TicketStatus.closed: 0,
    }

    status_distribution_result = await session.execute(
        select(
            Ticket.status,
            func.count(Ticket.id).label("count"),
        )
        .where(Ticket.created_at >= period_start)
        .group_by(Ticket.status),
    )

    for row in status_distribution_result.all():
        status_counts[row.status] = row.count

    resolution_time_map = build_empty_resolution_map(start_date, end_date)

    closed_day = func.date_trunc("day", Ticket.closed_at).label("day")

    resolution_time_result = await session.execute(
        select(
            closed_day,
            func.avg(resolution_minutes_expression).label("average_minutes"),
        )
        .where(Ticket.status == TicketStatus.closed)
        .where(Ticket.closed_at.is_not(None))
        .where(Ticket.closed_at >= period_start)
        .group_by(closed_day)
        .order_by(closed_day),
    )

    for row in resolution_time_result.all():
        average_minutes = row.average_minutes

        resolution_time_map[normalize_day(row.day)] = (
            round(float(average_minutes))
            if average_minutes is not None
            else None
        )

    rating_counts = {
        1: 0,
        2: 0,
        3: 0,
        4: 0,
        5: 0,
    }

    rating_distribution_result = await session.execute(
        select(
            TicketRating.rating,
            func.count(TicketRating.id).label("count"),
        )
        .where(TicketRating.created_at >= period_start)
        .group_by(TicketRating.rating)
        .order_by(TicketRating.rating),
    )

    for row in rating_distribution_result.all():
        rating_counts[row.rating] = row.count

    return {
        "summary": {
            "total_tickets_count": total_tickets_count,
            "average_resolution_minutes": (
                round(float(average_resolution))
                if average_resolution is not None
                else None
            ),
            "average_quality_rating": (
                round(float(average_rating), 1)
                if average_rating is not None
                else None
            ),
            "closed_tickets_count": closed_tickets_count,
        },
        "created_tickets_series": [
            {
                "date": point_date,
                "count": count,
            }
            for point_date, count in created_tickets_map.items()
        ],
        "status_distribution": [
            {
                "status": TicketStatus.pending,
                "count": status_counts[TicketStatus.pending],
            },
            {
                "status": TicketStatus.in_progress,
                "count": status_counts[TicketStatus.in_progress],
            },
            {
                "status": TicketStatus.closed,
                "count": status_counts[TicketStatus.closed],
            },
        ],
        "resolution_time_series": [
            {
                "date": point_date,
                "average_resolution_minutes": average_minutes,
            }
            for point_date, average_minutes in resolution_time_map.items()
        ],
        "rating_distribution": [
            {
                "rating": rating,
                "count": count,
            }
            for rating, count in rating_counts.items()
        ],
    }