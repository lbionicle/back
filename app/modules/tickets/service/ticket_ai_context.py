from app.modules.ai.model.models import AiChatMessage
from app.modules.tickets.model.models import MessageSenderType, TicketMessage

AI_CONTEXT_MESSAGES_LIMIT = 12

SYSTEM_MESSAGE = """
Ты ИИ-ассистент службы поддержки в тикет-сервисе IntelliTicket.
Твоя задача – помогать пользователю разобраться с его обращением.

Отвечай на русском языке, понятно, спокойно и по делу.
Учитывай предыдущие сообщения текущего тикета.
Если данных недостаточно, задай уточняющий вопрос.
Не придумывай факты, которых пользователь не сообщал.
Если проблема требует участия специалиста, предложи пользователю запросить оператора.
Не отвечай слишком длинно, если вопрос простой.
""".strip()


def build_ai_chat_context(messages: list[TicketMessage]) -> list[AiChatMessage]:
    context: list[AiChatMessage] = [
        AiChatMessage(
            role="system",
            content=SYSTEM_MESSAGE,
        ),
    ]

    useful_messages = [
        message
        for message in sorted(messages, key=lambda item: item.created_at)
        if message.text.strip()
        and message.sender_type
        in {
            MessageSenderType.initiator,
            MessageSenderType.bot,
        }
    ]

    useful_messages = useful_messages[-AI_CONTEXT_MESSAGES_LIMIT:]

    for message in useful_messages:
        if message.sender_type == MessageSenderType.initiator:
            context.append(
                AiChatMessage(
                    role="user",
                    content=message.text,
                ),
            )

        if message.sender_type == MessageSenderType.bot:
            context.append(
                AiChatMessage(
                    role="assistant",
                    content=message.text,
                ),
            )

    return context