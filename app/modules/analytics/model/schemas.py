import enum
from pydantic import BaseModel, ConfigDict, Field

from app.modules.tickets.model.models import TicketStatus


class AnalyticsPeriod(str, enum.Enum):
    week = "week"
    month = "month"
    three_months = "3_months"
    six_months = "6_months"


class AnalyticsSummaryRead(BaseModel):
    total_tickets_count: int = Field(alias="totalTicketsCount")
    average_resolution_minutes: int | None = Field(alias="averageResolutionMinutes")
    average_quality_rating: float | None = Field(alias="averageQualityRating")
    closed_tickets_count: int = Field(alias="closedTicketsCount")

    model_config = ConfigDict(populate_by_name=True)


class CreatedTicketsPointRead(BaseModel):
    date: str
    count: int


class StatusDistributionPointRead(BaseModel):
    status: TicketStatus
    count: int


class ResolutionTimePointRead(BaseModel):
    date: str
    average_resolution_minutes: int | None = Field(alias="averageResolutionMinutes")

    model_config = ConfigDict(populate_by_name=True)


class RatingDistributionPointRead(BaseModel):
    rating: int
    count: int


class ServiceManagerAnalyticsRead(BaseModel):
    summary: AnalyticsSummaryRead
    created_tickets_series: list[CreatedTicketsPointRead] = Field(
        alias="createdTicketsSeries",
    )
    status_distribution: list[StatusDistributionPointRead] = Field(
        alias="statusDistribution",
    )
    resolution_time_series: list[ResolutionTimePointRead] = Field(
        alias="resolutionTimeSeries",
    )
    rating_distribution: list[RatingDistributionPointRead] = Field(
        alias="ratingDistribution",
    )

    model_config = ConfigDict(populate_by_name=True)