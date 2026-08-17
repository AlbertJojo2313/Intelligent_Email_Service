import asyncio
import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from .fallback_generator import FallbackGenerator
from .models import ClientProfile

if TYPE_CHECKING:
    from .llm_client import NvidiaClient

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
        nvidia_client: "NvidiaClient | None" = None,
        max_concurrency: int = 1,
        request_delay: float = 0.5,
    ):
        self.advisor = advisor
        self.config = config
        self.nvidia_client = nvidia_client
        self.fallback_generator = FallbackGenerator(self.config.fallback_templates)
        self._llm_semaphore = asyncio.Semaphore(max_concurrency)
        self.request_delay = request_delay

    def _format_as_quoted_body(
        self, email_body: str, previous_messages: list[dict[str, Any]]
    ) -> str:
        """
        Appends previous messages in standard email reply quote format with HTML tags.
        """
        paragraphs = "".join(
            f"<p>{line}</p>" for line in email_body.split("\n\n") if line.strip()
        )
        html_body = f"<div>{paragraphs or f'<p>{email_body}</p>'}</div>"

        for msg in reversed(previous_messages):
            sent_str = msg["receivedDateTime"]
            sender = msg["from"]["emailAddress"]["name"]
            email = msg["from"]["emailAddress"]["address"]
            prev_content = msg["body"]["content"]

            html_body += (
                f'<div id="divRplyFwdMsg" style="border-top:1px solid #e1e1e1; margin-top:15px; padding-top:10px;">'
                f"<b>From:</b> {sender} &lt;{email}&gt;<br>"
                f"<b>Sent:</b> {sent_str}<br>"
                f"<b>To:</b> {msg['toRecipients'][0]['emailAddress']['name']}<br>"
                f"<b>Subject:</b> {msg.get('subject', '')}<br><br>"
                f"<div>{prev_content}</div>"
                f"</div>"
            )
        return html_body

    async def _fetch_raw_thread_messages(
        self, topic: str, client: ClientProfile, thread_length: int
    ) -> list[dict[str, Any]]:
        """
        Attempts to generate thread content via NVIDIA API, falling back to local template generator if it fails.
        """
        if self.nvidia_client:
            try:
                async with self._llm_semaphore:
                    if self.request_delay > 0:
                        await asyncio.sleep(self.request_delay)
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
        thread_format: str,
    ) -> list[dict[str, Any]]:
        """
        Generates a synthetic email thread

        thread_format:
            - full_quoted: Every reply includes previous messages as quoted history.
            - modified: Each message contains only its own content.
        """
        if thread_format not in {"full_quoted", "modified"}:
            raise ValueError(
                f"Invalid thread_format: {thread_format!r}."
                "Expected 'full_quoted' or 'modified'."
            )

        conversation_id = str(uuid.uuid4())
        bodies = await self._fetch_raw_thread_messages(topic, client, thread_length)

        messages = []

        # Start at a random date in the configured range (UTC time)
        base_time = datetime.now(UTC) - timedelta(
            days=random.randint(1, self.config.base_date_range_days)
        )

        for i, raw_item in enumerate(bodies):
            item = {"body": raw_item} if isinstance(raw_item, str) else dict(raw_item)
            msg_id = f"AAMkAG{uuid.uuid4().hex[:12]}"
            sender_role = item.get("sender")
            if sender_role not in {"advisor", "client"}:
                sender_role = "client" if i % 2 == 0 else "advisor"

            if sender_role == "advisor":
                from_name, from_email = self.advisor.name, self.advisor.email
                to_name, to_email = client.name, client.email
            else:
                from_name, from_email = client.name, client.email
                to_name, to_email = self.advisor.name, self.advisor.email

            # Ensure chronological ordering: each message is generated at a later time than the previous one
            msg_time = base_time + timedelta(
                hours=(
                    i * 2
                    + random.randint(  # noqa: S311
                        self.config.message_gap_hours_min,
                        self.config.message_gap_hours_max,
                    )
                )
            )
            received_time = msg_time.isoformat().replace("+00:00", "Z")

            raw_body = item.get("body", "")
            paragraphs = "".join(
                f"<p>{line}</p>" for line in raw_body.split("\n\n") if line.strip()
            )
            body_content = f"<div>{paragraphs or f'<p>{raw_body}</p>'}</div>"

            # If this is an unmodified thread, the last email has the quoted history of previous emails
            if thread_format == "full_quoted" and messages:
                body_content = self._format_as_quoted_body(
                    email_body=raw_body, previous_messages=messages
                )

            message_obj = {
                "id": msg_id,
                "createdDateTime": received_time,
                "lastModifiedDateTime": received_time,
                "categories": [],
                "receivedDateTime": received_time,
                "sentDateTime": received_time,
                "hasAttachments": False,
                "attachments": [],
                "conversationId": conversation_id,
                "conversation_id": conversation_id,
                "message_id": msg_id,
                "subject": item.get("subject", topic.replace("_", " ").title()),
                "body": {
                    "contentType": "html",
                    "content_type": "html",
                    "content": body_content,
                },
                "sender": {"emailAddress": {"name": from_name, "address": from_email}},
                "from": {"emailAddress": {"name": from_name, "address": from_email}},
                "toRecipients": [
                    {"emailAddress": {"name": to_name, "address": to_email}}
                ],
            }
            messages.append(message_obj)
        return messages
