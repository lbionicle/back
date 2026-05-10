import httpx

from app.core.config import settings
from app.modules.ai.model.models import AiChatMessage


def get_ollama_url(path: str) -> str:
    return f"{settings.ollama_base_url.rstrip('/')}{path}"


def get_last_user_message(messages: list[AiChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return message.content

    return ""


def build_fallback_answer(user_message: str) -> str:
    return (
        "Я принял ваше обращение и попробую помочь. "
        "Пожалуйста, уточните детали проблемы: что именно произошло, "
        "когда появилась ошибка и какие действия вы уже выполняли."
    )


def build_fallback_title(user_message: str) -> str:
    words = user_message.strip().split()

    if not words:
        return "Новый чат"

    title = " ".join(words[:5])

    return title[:60]


async def generate_bot_answer(messages: list[AiChatMessage]) -> str:
    user_message = get_last_user_message(messages)

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                get_ollama_url("/api/chat"),
                json={
                    "model": settings.ollama_model,
                    "messages": [
                        {
                            "role": message.role,
                            "content": message.content,
                        }
                        for message in messages
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                    },
                },
            )

        response.raise_for_status()

        data = response.json()
        answer = data.get("message", {}).get("content")

        if not answer:
            return build_fallback_answer(user_message)

        return answer.strip()
    except Exception:
        return build_fallback_answer(user_message)


async def generate_ticket_title(user_message: str) -> str:
    prompt = (
        "Придумай короткий заголовок тикета на русском языке. "
        "Максимум 5 слов. Без кавычек и точки в конце.\n\n"
        f"Сообщение пользователя: {user_message}"
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                get_ollama_url("/api/generate"),
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                },
            )

        response.raise_for_status()

        data = response.json()
        title = data.get("response")

        if not title:
            return build_fallback_title(user_message)

        return title.strip().replace('"', "")[:80]
    except Exception:
        return build_fallback_title(user_message)