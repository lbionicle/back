import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.modules.tickets.model.models import Ticket, TicketStatus
from app.modules.users.model.models import UserRole
from app.modules.users.model.schemas import (
    ManagerUserUpdateRequest,
    OperatorCreateRequest,
    UserUpdateRequest,
)
from app.modules.users.service.user_service import (
    block_user,
    create_operator,
    delete_user,
    ensure_service_manager_exists,
    get_operators_list,
    get_operators_stats,
    get_users_list,
    get_users_stats,
    get_user_by_email,
    unblock_user,
    update_current_user,
    update_user_by_manager,
)


@pytest.mark.asyncio
async def test_create_operator_creates_operator(db_session: AsyncSession):
    operator = await create_operator(
        db_session,
        OperatorCreateRequest(
            fullName="Оператор Тестовый",
            email="operator@test.by",
            password="password123",
        ),
    )

    assert operator.email == "operator@test.by"
    assert operator.role == UserRole.operator
    assert verify_password("password123", operator.password_hash)


@pytest.mark.asyncio
async def test_create_operator_rejects_duplicate_email(
    db_session: AsyncSession,
    user_factory,
):
    await user_factory(
        email="operator@test.by",
        role=UserRole.operator,
    )

    with pytest.raises(ValueError, match="Пользователь с такой почтой"):
        await create_operator(
            db_session,
            OperatorCreateRequest(
                fullName="Другой оператор",
                email="operator@test.by",
                password="password123",
            ),
        )


@pytest.mark.asyncio
async def test_update_current_user_updates_name_email_and_password(
    db_session: AsyncSession,
    user_factory,
):
    user = await user_factory(
        full_name="Старое имя",
        email="old@test.by",
        password="old-password",
        role=UserRole.initiator,
    )

    updated_user = await update_current_user(
        session=db_session,
        user=user,
        data=UserUpdateRequest(
            fullName="Новое имя",
            email="new@test.by",
            password="new-password",
        ),
    )

    assert updated_user.full_name == "Новое имя"
    assert updated_user.email == "new@test.by"
    assert verify_password("new-password", updated_user.password_hash)


@pytest.mark.asyncio
async def test_update_current_user_rejects_duplicate_email(
    db_session: AsyncSession,
    user_factory,
):
    user = await user_factory(
        email="first@test.by",
        role=UserRole.initiator,
    )
    await user_factory(
        email="second@test.by",
        role=UserRole.initiator,
    )

    with pytest.raises(ValueError, match="Пользователь с такой почтой"):
        await update_current_user(
            session=db_session,
            user=user,
            data=UserUpdateRequest(
                email="second@test.by",
            ),
        )


@pytest.mark.asyncio
async def test_ensure_service_manager_exists_creates_manager_once(
    db_session: AsyncSession,
):
    await ensure_service_manager_exists(db_session)
    await ensure_service_manager_exists(db_session)

    manager = await get_user_by_email(db_session, "admin@test.by")

    assert manager is not None
    assert manager.role == UserRole.service_manager


@pytest.mark.asyncio
async def test_get_users_stats_counts_operators_and_initiators(
    db_session: AsyncSession,
    user_factory,
):
    await user_factory(email="operator1@test.by", role=UserRole.operator)
    await user_factory(email="operator2@test.by", role=UserRole.operator)
    await user_factory(email="initiator@test.by", role=UserRole.initiator)
    await user_factory(email="manager@test.by", role=UserRole.service_manager)

    stats = await get_users_stats(db_session)

    assert stats["operators_count"] == 2
    assert stats["initiators_count"] == 1


@pytest.mark.asyncio
async def test_get_users_list_filters_and_excludes_service_manager(
    db_session: AsyncSession,
    user_factory,
):
    await user_factory(
        full_name="Анна Инициатор",
        email="anna@test.by",
        role=UserRole.initiator,
    )
    await user_factory(
        full_name="Олег Оператор",
        email="oleg@test.by",
        role=UserRole.operator,
        is_blocked=True,
    )
    await user_factory(
        full_name="Главный менеджер",
        email="manager@test.by",
        role=UserRole.service_manager,
    )

    users, total = await get_users_list(
        session=db_session,
        search="олег",
        is_blocked=True,
        page=1,
        limit=10,
    )

    assert total == 1
    assert len(users) == 1
    assert users[0].email == "oleg@test.by"


@pytest.mark.asyncio
async def test_update_user_by_manager_rejects_service_manager_changes(
    db_session: AsyncSession,
    user_factory,
):
    manager = await user_factory(
        email="manager@test.by",
        role=UserRole.service_manager,
    )

    with pytest.raises(ValueError, match="Нельзя изменять профиль менеджера"):
        await update_user_by_manager(
            session=db_session,
            user=manager,
            data=ManagerUserUpdateRequest(
                fullName="Новое имя",
            ),
        )


@pytest.mark.asyncio
async def test_update_user_by_manager_updates_user(
    db_session: AsyncSession,
    user_factory,
):
    user = await user_factory(
        full_name="Старое имя",
        email="old@test.by",
        role=UserRole.initiator,
    )

    updated_user = await update_user_by_manager(
        session=db_session,
        user=user,
        data=ManagerUserUpdateRequest(
            fullName="Новое имя",
            email="new@test.by",
            role=UserRole.operator,
        ),
    )

    assert updated_user.full_name == "Новое имя"
    assert updated_user.email == "new@test.by"
    assert updated_user.role == UserRole.operator


@pytest.mark.asyncio
async def test_block_unblock_and_delete_user(
    db_session: AsyncSession,
    user_factory,
):
    user = await user_factory(
        email="user@test.by",
        role=UserRole.initiator,
    )

    blocked_user = await block_user(db_session, user)

    assert blocked_user.is_blocked is True

    unblocked_user = await unblock_user(db_session, blocked_user)

    assert unblocked_user.is_blocked is False

    await delete_user(db_session, unblocked_user)

    deleted_user = await get_user_by_email(db_session, "user@test.by")

    assert deleted_user is None


@pytest.mark.asyncio
async def test_get_operators_stats_and_list(
    db_session: AsyncSession,
    user_factory,
):
    initiator = await user_factory(
        email="initiator@test.by",
        role=UserRole.initiator,
    )
    busy_operator = await user_factory(
        full_name="Занятый оператор",
        email="busy@test.by",
        role=UserRole.operator,
    )
    free_operator = await user_factory(
        full_name="Свободный оператор",
        email="free@test.by",
        role=UserRole.operator,
    )

    active_ticket = Ticket(
        title="Активный тикет",
        initiator_id=initiator.id,
        operator_id=busy_operator.id,
        status=TicketStatus.in_progress,
        is_operator_requested=True,
    )
    closed_ticket = Ticket(
        title="Закрытый тикет",
        initiator_id=initiator.id,
        operator_id=busy_operator.id,
        status=TicketStatus.closed,
        is_operator_requested=True,
    )

    db_session.add_all([active_ticket, closed_ticket])
    await db_session.commit()

    stats = await get_operators_stats(db_session)

    assert stats["busy_operators_count"] == 1
    assert stats["free_operators_count"] == 1

    operators, total = await get_operators_list(
        session=db_session,
        availability="busy",
        page=1,
        limit=10,
    )

    assert total == 1
    assert len(operators) == 1

    operator, active_count, solved_count = operators[0]

    assert operator.id == busy_operator.id
    assert active_count == 1
    assert solved_count == 1