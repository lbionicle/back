import httpx

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "hf.co/NidAll/supergemma4-e4b-abliterated-Q4_K_M-GGUF:Q4_K_M"

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


async def generate_bot_answer(user_message: str) -> str:
    prompt = (
        "Ты ИИ-ассистент службы поддержки в тикет-сервисе IntelliTicket. "
        "Отвечай кратко, понятно и по делу. "
        "Если данных недостаточно, попроси пользователя уточнить проблему.\n\n"
        f"Сообщение пользователя: {user_message}"
    )



    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                },
            )

        response.raise_for_status()

        data = response.json()
        answer = data.get("response")

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
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
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