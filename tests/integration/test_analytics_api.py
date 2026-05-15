import pytest

from app.modules.users.model.models import UserRole
from tests.conftest import build_auth_headers


@pytest.mark.asyncio
async def test_service_manager_can_get_analytics(async_client, user_factory):
    service_manager = await user_factory(
        full_name="Менеджер",
        email="manager@test.by",
        role=UserRole.service_manager,
    )

    response = await async_client.get(
        "/api/analytics/service-manager?period=week",
        headers=build_auth_headers(service_manager),
    )

    assert response.status_code == 200

    body = response.json()

    assert "summary" in body
    assert "createdTicketsSeries" in body
    assert "statusDistribution" in body
    assert "resolutionTimeSeries" in body
    assert "ratingDistribution" in body


@pytest.mark.asyncio
async def test_service_manager_can_download_analytics_report(
    async_client,
    user_factory,
):
    service_manager = await user_factory(
        full_name="Менеджер",
        email="manager@test.by",
        role=UserRole.service_manager,
    )

    response = await async_client.get(
        "/api/analytics/service-manager/report?period=week",
        headers=build_auth_headers(service_manager),
    )

    assert response.status_code == 200

    assert response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    assert response.content.startswith(b"PK")
    assert len(response.content) > 1000


@pytest.mark.asyncio
async def test_initiator_cannot_get_service_manager_analytics(
    async_client,
    user_factory,
):
    initiator = await user_factory(
        email="initiator@test.by",
        role=UserRole.initiator,
    )

    response = await async_client.get(
        "/api/analytics/service-manager?period=week",
        headers=build_auth_headers(initiator),
    )

    assert response.status_code == 403