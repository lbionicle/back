from zipfile import ZipFile

from app.modules.analytics.model.schemas import (
    AnalyticsPeriod,
    ServiceManagerAnalyticsRead,
)
from app.modules.analytics.service.analytics_report_service import (
    build_analytics_report_workbook,
)
from app.modules.tickets.model.models import TicketStatus


def test_build_analytics_report_workbook_creates_valid_xlsx():
    analytics = ServiceManagerAnalyticsRead.model_validate(
        {
            "summary": {
                "total_tickets_count": 10,
                "average_resolution_minutes": 180,
                "average_quality_rating": 4.5,
                "closed_tickets_count": 7,
            },
            "created_tickets_series": [
                {"date": "2026-05-10", "count": 2},
                {"date": "2026-05-11", "count": 4},
                {"date": "2026-05-12", "count": 4},
            ],
            "status_distribution": [
                {"status": TicketStatus.pending, "count": 1},
                {"status": TicketStatus.in_progress, "count": 2},
                {"status": TicketStatus.closed, "count": 7},
            ],
            "resolution_time_series": [
                {"date": "2026-05-10", "average_resolution_minutes": 120},
                {"date": "2026-05-11", "average_resolution_minutes": 180},
                {"date": "2026-05-12", "average_resolution_minutes": 240},
            ],
            "rating_distribution": [
                {"rating": 1, "count": 0},
                {"rating": 2, "count": 1},
                {"rating": 3, "count": 1},
                {"rating": 4, "count": 2},
                {"rating": 5, "count": 3},
            ],
        },
    )

    report = build_analytics_report_workbook(
        analytics=analytics,
        period=AnalyticsPeriod.week,
    )

    assert report.getbuffer().nbytes > 0

    with ZipFile(report) as archive:
        file_names = archive.namelist()

        assert "xl/workbook.xml" in file_names
        assert any(name.startswith("xl/charts/chart") for name in file_names)
        assert any(name.startswith("xl/worksheets/sheet") for name in file_names)