import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from .fallback_generator import FallbackGenerator
from .llm_client import NvidiaClient
from .models import ClientProfile

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdvisorProfile:
    name: str
    email: str


@dataclass(frozen=True)
class EmailGenerationConfig:
    base_date_range_days: int = 30
    message_gap_hours_min: int = 1
    message_gap_hours_max: int = 6
    fallback_templates: dict[str, list[str]] = field(default_factory=dict)


class SyntheticEmailGenerator:
    def __init__(
        self,
        advisor: AdvisorProfile,
        config: EmailGenerationConfig,
        nvidia_client: Optional[NvidiaClient] = None,
    ):
        self.advisor = advisor
        self.config = config
        self.nvidia_client = nvidia_client
        self.fallback_generator = FallbackGenerator(config.fallback_templates)

    def _format_as_quoted_body(
        self, email_body: str, previous_messages: list[dict[str, Any]]
    ) -> str:
        """
        Appends previous messages in standard email reply quote format
        """
        quoted_text = email_body
        for msg in reversed(previous_messages):
            sent_str = msg["receivedDateTime"]
            sender = msg["from"]["emailAddress"]["name"]
            email = msg["from"]["emailAddress"]["address"]
            body_content = msg["body"]["content"]

            quoted_text += f"\n\nOn {sent_str}, {sender} <{email}> wrote:\n"
            quoted_text += "\n".join(f"> {line}" for line in body_content.splitlines())
        return quoted_text

    async def _fetch_raw_thread_messages(
        self, topic: str, client: ClientProfile, thread_length: int
    ) -> list[dict[str, Any]]:
        """
        Attempts to generate thread content via NVIDIA API, falling back to local template generator if it fails.
        """
        if self.nvidia_client:
            try:
                return await self.nvidia_client.generate_email_thread(
                    topic=topic,
                    advisor_name=self.advisor.name,
                    client_name=client.name,
                    thread_count=thread_length,
                )
            except Exception as e:
                logger.warning(
                    "NVIDIA API generation failed: %s. Falling back to template-based generation.",
                    e,
                )

        return self.fallback_generator.generate(
            topic=topic,
            advisor_name=self.advisor.name,
            client_name=client.name,
            thread_count=thread_length,
        )

    async def generate_thread(
        self,
        topic: str,
        client: ClientProfile,
        thread_length: int,
        include_quoted_history: bool,
    ) -> list[dict[str, Any]]:
        """
        Generates thread emails for a specific client and topic, then formats them with
        unique Microsoft Graph API-like IDs, timestamps, and quotes if unmodified.
        """
        conversation_id = str(uuid.uuid4())
        bodies = await self._fetch_raw_thread_messages(topic, client, thread_length)

        messages = []
        # Start at a random date in the configured range (UTC time)
        base_time = datetime.now(UTC) - timedelta(
            days=random.randint(1, self.config.base_date_range_days)
        )

        for i, item in enumerate(bodies):
            msg_id = f"AAMkAG{uuid.uuid4().hex[:12]}"
            sender_role = item.get("sender")
            if sender_role not in ["advisor", "client"]:
                sender_role = "client" if i % 2 == 0 else "advisor"

            if sender_role == "advisor":
                from_name, from_email = self.advisor.name, self.advisor.email
                to_name, to_email = client.name, client.email
            else:
                from_name, from_email = client.name, client.email
                to_name, to_email = self.advisor.name, self.advisor.email

            # Ensure chronological ordering: each message is generated at a later time than the previous one
            msg_time = base_time + timedelta(
                hours=i * 2
                + random.randint(
                    self.config.message_gap_hours_min, self.config.message_gap_hours_max
                )
            )
            received_time = msg_time.isoformat().replace("+00:00", "Z")

            raw_body = item.get("body", "")
            body_content = raw_body

            # If this is an unmodified thread, the last email has the quoted history of previous emails
            if include_quoted_history and i == len(bodies) - 1 and len(messages) > 0:
                body_content = self._format_as_quoted_body(raw_body, messages)

            message_obj = {
                "id": msg_id,
                "createdDateTime": received_time,
                "lastModifiedDateTime": received_time,
                "categories": [],
                "receivedDateTime": received_time,
                "sentDateTime": received_time,
                "hasAttachments": False,
                "conversation_id": conversation_id,
                "message_id": msg_id,
                "subject": item.get("subject", topic.replace("_", " ").title()),
                "body": {"content_type": "html", "content": body_content},
                "sender": {"emailAddress": {"name": from_name, "address": from_email}},
                "from": {"emailAddress": {"name": from_name, "address": from_email}},
                "toRecipients": [
                    {"emailAddress": {"name": to_name, "address": to_email}}
                ],
            }
            messages.append(message_obj)
        return messages
