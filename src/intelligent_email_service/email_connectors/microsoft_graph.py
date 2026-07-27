from datetime import datetime
from typing import Any

from .base import EmailProvider


class MicrosoftGraphProvider(EmailProvider):
    def __init__(self, base_url: str = "https://graph.microsoft.com/v1.0"):
        self.base_url = base_url

    async def get_emails(
        self,
        user_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "Live Microsoft Graph API integration is currently an outline and not implemented."
        )

    async def get_emails_by_conversation_id(
        self, user_id: str, conversation_id: str
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "Live Microsoft Graph API integration is currently an outline and not implemented."
        )
