from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class EmailProvider(ABC):
    @abstractmethod
    async def get_emails(
        self,
        user_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def get_emails_by_conversation_id(
        self, user_id: str, conversation_id: str
    ) -> list[dict[str, Any]]:
        pass
