import asyncio
from datetime import datetime, timedelta, timezone

from pwdlib import PasswordHash
from sqlalchemy import delete, or_, select

from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.modules.tickets.model.models import (
    MessageSenderType,
    Ticket,
    TicketMessage,
    TicketMessageKind,
    TicketRating,
    TicketStatus,
)
from app.modules.users.model.models import User, UserRole

DEMO_DOMAIN = "demo.intelliticket.by"
DEMO_PASSWORD = "qwerty123"

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def build_rating_message(rating: int, comment: str | None) -> str:
    stars = "★" * rating + "☆" * (5 - rating)

    if comment:
        return (
            f"Пользователь оставил отзыв: {stars} ({rating}/5).\n"
            f"Комментарий: {comment}"
        )

    return f"Пользователь оставил отзыв: {stars} ({rating}/5)."


async def clear_demo_data() -> None:
    async with AsyncSessionLocal() as session:
        demo_user_ids_result = await session.execute(
            select(User.id).where(User.email.like(f"%@{DEMO_DOMAIN}")),
        )

        demo_user_ids = list(demo_user_ids_result.scalars().all())

        if not demo_user_ids:
            return

        demo_ticket_ids_result = await session.execute(
            select(Ticket.id).where(
                or_(
                    Ticket.initiator_id.in_(demo_user_ids),
                    Ticket.operator_id.in_(demo_user_ids),
                ),
            ),
        )

        demo_ticket_ids = list(demo_ticket_ids_result.scalars().all())

        if demo_ticket_ids:
            await session.execute(
                delete(TicketRating).where(
                    TicketRating.ticket_id.in_(demo_ticket_ids),
                ),
            )

            await session.execute(
                delete(TicketMessage).where(
                    TicketMessage.ticket_id.in_(demo_ticket_ids),
                ),
            )

            await session.execute(
                delete(Ticket).where(Ticket.id.in_(demo_ticket_ids)),
            )

        await session.execute(
            delete(User).where(User.id.in_(demo_user_ids)),
        )

        await session.commit()


def get_status_for_ticket(days_ago: int, index: int) -> TicketStatus:
    if days_ago <= 1:
        if index % 3 == 0:
            return TicketStatus.pending

        return TicketStatus.in_progress

    if days_ago <= 14:
        if index % 8 == 0:
            return TicketStatus.pending

        if index % 4 == 0:
            return TicketStatus.in_progress

        return TicketStatus.closed

    if index % 17 == 0:
        return TicketStatus.pending

    if index % 11 == 0:
        return TicketStatus.in_progress

    return TicketStatus.closed


def get_tickets_count_for_day(days_ago: int) -> int:
    if days_ago % 11 == 1:
        return 0

    count = 1

    if days_ago % 2 == 0:
        count += 1

    if days_ago % 5 == 0:
        count += 1

    if days_ago % 13 == 0:
        count += 2

    if days_ago % 29 == 0:
        count += 2

    return count


def get_resolution_minutes(index: int, days_ago: int) -> int:
    if index % 12 == 0:
        return 20 + index % 25

    if index % 9 == 0:
        return 360 + index % 240

    if days_ago % 10 == 0:
        return 180 + index % 180

    return 45 + index % 150


async def create_demo_data() -> None:
    now = datetime.now(timezone.utc)
    password_hash = hash_password(DEMO_PASSWORD)

    managers = [
        User(
            full_name="Демо Менеджер",
            email=f"manager@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.service_manager,
            avatar_url=None,
            is_blocked=False,
        ),
    ]

    operators = [
        User(
            full_name="Ольга Соколова",
            email=f"operator.olga@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.operator,
            avatar_url=None,
            is_blocked=False,
        ),
        User(
            full_name="Никита Рутер",
            email=f"operator.ruter@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.operator,
            avatar_url=None,
            is_blocked=False,
        ),
        User(
            full_name="Екатерина Морозова",
            email=f"operator.kate@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.operator,
            avatar_url=None,
            is_blocked=False,
        ),
        User(
            full_name="Алексей Волков",
            email=f"operator.alex@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.operator,
            avatar_url=None,
            is_blocked=False,
        ),
        User(
            full_name="Ирина Лебедева",
            email=f"operator.irina@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.operator,
            avatar_url=None,
            is_blocked=False,
        ),
        User(
            full_name="Сергей Орлов",
            email=f"operator.sergey@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.operator,
            avatar_url=None,
            is_blocked=False,
        ),
        User(
            full_name="Заблокированный Оператор",
            email=f"operator.blocked@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.operator,
            avatar_url=None,
            is_blocked=True,
        ),
    ]

    initiators = [
        User(
            full_name="Михаил Иванов",
            email=f"mikhail.ivanov@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.initiator,
            avatar_url=None,
            is_blocked=False,
        ),
        User(
            full_name="Анна Петрова",
            email=f"anna.petrova@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.initiator,
            avatar_url=None,
            is_blocked=False,
        ),
        User(
            full_name="Дмитрий Козлов",
            email=f"dmitry.kozlov@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.initiator,
            avatar_url=None,
            is_blocked=False,
        ),
        User(
            full_name="Мария Смирнова",
            email=f"maria.smirnova@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.initiator,
            avatar_url=None,
            is_blocked=False,
        ),
        User(
            full_name="Павел Новиков",
            email=f"pavel.novikov@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.initiator,
            avatar_url=None,
            is_blocked=False,
        ),
        User(
            full_name="Елена Васильева",
            email=f"elena.vasilieva@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.initiator,
            avatar_url=None,
            is_blocked=False,
        ),
        User(
            full_name="Кирилл Захаров",
            email=f"kirill.zakharov@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.initiator,
            avatar_url=None,
            is_blocked=False,
        ),
        User(
            full_name="Виктория Белова",
            email=f"victoria.belova@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.initiator,
            avatar_url=None,
            is_blocked=False,
        ),
        User(
            full_name="Артём Фёдоров",
            email=f"artem.fedorov@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.initiator,
            avatar_url=None,
            is_blocked=False,
        ),
        User(
            full_name="Наталья Соловьёва",
            email=f"natalia.solovieva@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.initiator,
            avatar_url=None,
            is_blocked=False,
        ),
        User(
            full_name="Роман Павлов",
            email=f"roman.pavlov@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.initiator,
            avatar_url=None,
            is_blocked=False,
        ),
        User(
            full_name="Юлия Андреева",
            email=f"julia.andreeva@{DEMO_DOMAIN}",
            password_hash=password_hash,
            role=UserRole.initiator,
            avatar_url=None,
            is_blocked=False,
        ),
    ]

    ticket_titles = [
        "Ошибка при входе в систему",
        "Не приходит письмо подтверждения",
        "Проблема с загрузкой аватара",
        "Не отображаются мои тикеты",
        "Нужно изменить данные профиля",
        "Некорректно работает поиск",
        "Не открывается страница аналитики",
        "Не сохраняется сообщение в чате",
        "Проблема с назначением оператора",
        "Ошибка при закрытии тикета",
        "Не обновляется статус обращения",
        "Нужно уточнить права доступа",
        "Не отображается исполнитель тикета",
        "Ошибка при отправке сообщения",
        "Непонятный ответ ИИ-ассистента",
        "Не отображается история переписки",
        "Не работает экспорт отчёта",
        "Не загружается список пользователей",
        "Ошибка при смене пароля",
        "Не получается удалить тикет",
        "Некорректно отображается статус",
        "Не работает фильтр по приоритету",
        "Долго открывается страница тикета",
        "Не виден комментарий к отзыву",
        "Сбивается пагинация после удаления",
        "Ошибка при назначении исполнителя",
        "Не отображается средняя оценка",
        "Проблема с CORS при открытии сайта",
        "Не сохраняется оценка обслуживания",
        "Некорректное время решения тикета",
    ]

    user_first_messages = [
        "Здравствуйте. Не получается выполнить действие в системе. Подскажите, пожалуйста, что можно сделать?",
        "Добрый день. Возникла ошибка, раньше всё работало корректно.",
        "Здравствуйте. После обновления страницы проблема повторяется.",
        "Добрый день. Не могу понять, почему данные не сохраняются.",
        "Здравствуйте. Нужна помощь с обращением, потому что самостоятельно решить не получилось.",
        "Добрый день. Появилась непонятная ошибка, прикладываю описание ситуации.",
    ]

    operator_answers = [
        "Здравствуйте. Я посмотрел ваше обращение. Сейчас проверю данные и помогу решить проблему.",
        "Добрый день. Уточните, пожалуйста, после какого действия появляется ошибка.",
        "Здравствуйте. Вижу ваше обращение, сейчас проверю состояние тикета.",
        "Добрый день. Вероятно, проблема связана с некорректными данными. Сейчас разберёмся.",
        "Здравствуйте. Я взял обращение в работу и проверю его по журналу действий.",
        "Добрый день. Спасибо за описание, сейчас предложу решение.",
    ]

    closing_messages = [
        "Проблема исправлена. Проверьте, пожалуйста, что теперь всё работает корректно.",
        "Данные обновлены. Обращение можно закрывать.",
        "Причина ошибки устранена. Если проблема повторится, создайте новое обращение.",
        "Настройки исправлены, доступ восстановлен.",
        "Мы проверили ситуацию и внесли необходимые изменения.",
    ]

    rating_comments = [
        "Оператор помог быстро, проблема решена.",
        "Ответ был понятным, спасибо.",
        "Хотелось бы немного быстрее, но в целом хорошо.",
        "Проблему решили полностью.",
        "Поддержка сработала отлично.",
        "Оператор подробно объяснил, что нужно сделать.",
        "Проблема решена, но пришлось уточнять детали.",
        "Ответ хороший, но хотелось бы больше подробностей.",
        "Быстро подключились и помогли.",
        "Всё понятно, обращение обработали качественно.",
    ]

    rating_values_cycle = [
        5,
        5,
        4,
        5,
        3,
        4,
        5,
        2,
        4,
        5,
        1,
        4,
        5,
        3,
        5,
    ]

    async with AsyncSessionLocal() as session:
        all_users = managers + operators + initiators
        session.add_all(all_users)
        await session.commit()

        for user in all_users:
            await session.refresh(user)

        active_operators = [operator for operator in operators if not operator.is_blocked]

        total_index = 0

        for days_ago in range(0, 240):
            tickets_count = get_tickets_count_for_day(days_ago)

            if tickets_count == 0:
                continue

            for local_index in range(tickets_count):
                total_index += 1

                created_at = now - timedelta(
                    days=days_ago,
                    hours=(total_index * 3) % 12,
                    minutes=(total_index * 7) % 55,
                )

                status = get_status_for_ticket(days_ago, total_index)

                initiator = initiators[total_index % len(initiators)]
                operator = active_operators[total_index % len(active_operators)]

                is_closed = status == TicketStatus.closed
                is_assigned = status in {
                    TicketStatus.in_progress,
                    TicketStatus.closed,
                }

                resolution_minutes = get_resolution_minutes(total_index, days_ago)

                closed_at = (
                    created_at + timedelta(minutes=resolution_minutes)
                    if is_closed
                    else None
                )

                if closed_at and closed_at >= now:
                    status = TicketStatus.in_progress
                    is_closed = False
                    is_assigned = True
                    closed_at = None

                updated_at = closed_at or created_at + timedelta(
                    minutes=10 + total_index % 120,
                )

                ticket = Ticket(
                    title=ticket_titles[total_index % len(ticket_titles)],
                    initiator_id=initiator.id,
                    operator_id=operator.id if is_assigned else None,
                    status=status,
                    is_operator_requested=True,
                    is_priority=total_index % 9 in {0, 1},
                    created_at=created_at,
                    updated_at=updated_at,
                    closed_at=closed_at,
                )

                session.add(ticket)
                await session.flush()

                messages: list[TicketMessage] = [
                    TicketMessage(
                        ticket_id=ticket.id,
                        sender_id=initiator.id,
                        sender_type=MessageSenderType.initiator,
                        kind=TicketMessageKind.text,
                        text=user_first_messages[
                            total_index % len(user_first_messages)
                        ],
                        created_at=created_at + timedelta(minutes=1),
                    ),
                    TicketMessage(
                        ticket_id=ticket.id,
                        sender_id=None,
                        sender_type=MessageSenderType.bot,
                        kind=TicketMessageKind.text,
                        text=(
                            "Я принял ваше обращение. Опишите проблему подробнее. "
                            "Если потребуется помощь специалиста, можно запросить оператора."
                        ),
                        created_at=created_at + timedelta(minutes=2),
                    ),
                    TicketMessage(
                        ticket_id=ticket.id,
                        sender_id=None,
                        sender_type=MessageSenderType.bot,
                        kind=TicketMessageKind.text,
                        text="Соединяю вас с оператором службы поддержки.",
                        created_at=created_at + timedelta(minutes=4),
                    ),
                ]

                if status == TicketStatus.pending:
                    messages.append(
                        TicketMessage(
                            ticket_id=ticket.id,
                            sender_id=initiator.id,
                            sender_type=MessageSenderType.initiator,
                            kind=TicketMessageKind.text,
                            text="Ожидаю подключения оператора.",
                            created_at=created_at + timedelta(minutes=7),
                        ),
                    )

                if is_assigned:
                    messages.extend(
                        [
                            TicketMessage(
                                ticket_id=ticket.id,
                                sender_id=operator.id,
                                sender_type=MessageSenderType.operator,
                                kind=TicketMessageKind.text,
                                text=operator_answers[
                                    total_index % len(operator_answers)
                                ],
                                created_at=created_at + timedelta(minutes=8),
                            ),
                            TicketMessage(
                                ticket_id=ticket.id,
                                sender_id=initiator.id,
                                sender_type=MessageSenderType.initiator,
                                kind=TicketMessageKind.text,
                                text="Спасибо, ожидаю ответа.",
                                created_at=created_at + timedelta(minutes=12),
                            ),
                        ],
                    )

                if is_closed and closed_at:
                    messages.extend(
                        [
                            TicketMessage(
                                ticket_id=ticket.id,
                                sender_id=operator.id,
                                sender_type=MessageSenderType.operator,
                                kind=TicketMessageKind.text,
                                text=closing_messages[
                                    total_index % len(closing_messages)
                                ],
                                created_at=closed_at - timedelta(minutes=12),
                            ),
                            TicketMessage(
                                ticket_id=ticket.id,
                                sender_id=initiator.id,
                                sender_type=MessageSenderType.initiator,
                                kind=TicketMessageKind.text,
                                text="Да, теперь всё работает. Спасибо.",
                                created_at=closed_at - timedelta(minutes=7),
                            ),
                            TicketMessage(
                                ticket_id=ticket.id,
                                sender_id=None,
                                sender_type=MessageSenderType.bot,
                                kind=TicketMessageKind.rating_request,
                                text=(
                                    "Обращение закрыто. Пожалуйста, оцените качество обслуживания "
                                    "и при желании оставьте комментарий."
                                ),
                                created_at=closed_at + timedelta(minutes=1),
                            ),
                        ],
                    )

                    should_have_rating = total_index % 6 != 0

                    if should_have_rating:
                        rating_value = rating_values_cycle[
                            total_index % len(rating_values_cycle)
                        ]
                        comment = rating_comments[
                            total_index % len(rating_comments)
                        ]
                        rating_created_at = closed_at + timedelta(minutes=5)

                        rating = TicketRating(
                            ticket_id=ticket.id,
                            initiator_id=initiator.id,
                            rating=rating_value,
                            comment=comment,
                            created_at=rating_created_at,
                            updated_at=rating_created_at,
                        )

                        messages.append(
                            TicketMessage(
                                ticket_id=ticket.id,
                                sender_id=None,
                                sender_type=MessageSenderType.bot,
                                kind=TicketMessageKind.rating_submitted,
                                text=build_rating_message(rating_value, comment),
                                created_at=rating_created_at,
                            ),
                        )

                        session.add(rating)

                session.add_all(messages)

        await session.commit()

        print("Демо-данные успешно добавлены.")
        print()
        print("Пользователи:")
        print(f"Менеджер: manager@{DEMO_DOMAIN}")

        for operator in operators:
            blocked_label = " заблокирован" if operator.is_blocked else ""
            print(f"Оператор: {operator.email}{blocked_label}")

        for initiator in initiators:
            print(f"Инициатор: {initiator.email}")

        print()
        print(f"Пароль для всех: {DEMO_PASSWORD}")
        print(f"Всего создано тикетов: {total_index}")


async def main() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    await clear_demo_data()
    await create_demo_data()


if __name__ == "__main__":
    asyncio.run(main())