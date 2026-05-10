from dataclasses import dataclass
from typing import Literal

AiRole = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class AiChatMessage:
    role: AiRole
    content: str