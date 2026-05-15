import pytest


@pytest.mark.asyncio
async def test_sign_up_creates_initiator_and_sets_cookie(async_client):
    response = await async_client.post(
        "/api/auth/sign-up",
        json={
            "fullName": "Иван Иванов",
            "email": "ivan@test.by",
            "password": "password123",
            "confirmPassword": "password123",
        },
    )

    assert response.status_code == 201, response.json()

    body = response.json()

    assert body["user"]["email"] == "ivan@test.by"
    assert body["user"]["role"] == "initiator"
    assert body["accessToken"]
    assert body["tokenType"] == "bearer"

    assert "accessToken" in response.cookies


@pytest.mark.asyncio
async def test_sign_in_returns_401_for_wrong_credentials(async_client):
    response = await async_client.post(
        "/api/auth/sign-in",
        json={
            "email": "unknown@test.by",
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Неверная почта или пароль"


@pytest.mark.asyncio
async def test_me_returns_current_user_after_sign_up(async_client):
    sign_up_response = await async_client.post(
        "/api/auth/sign-up",
        json={
            "fullName": "Пётр Петров",
            "email": "petr@test.by",
            "password": "password123",
            "confirmPassword": "password123",
        },
    )

    assert sign_up_response.status_code == 201, sign_up_response.json()

    response = await async_client.get("/api/auth/me")

    assert response.status_code == 200, response.json()

    body = response.json()

    assert body["email"] == "petr@test.by"
    assert body["role"] == "initiator"
    assert body["fullName"] == "Пётр Петров"