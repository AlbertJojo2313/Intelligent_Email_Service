import json
import logging
from typing import Any

from openai import APIStatusError, AsyncOpenAI, RateLimitError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

logger = logging.getLogger(__name__)

DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_NVIDIA_MODEL = "deepseek-ai/deepseek-v4-flash"


class NvidiaClient:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_NVIDIA_MODEL,
        base_url: str = DEFAULT_NVIDIA_BASE_URL,
    ):
        if not api_key:
            raise ValueError("NVIDIA API key must be provided.")

        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
        )

        self.model = model

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIStatusError, Exception)),
        wait=wait_random_exponential(min=2, max=60),
        stop=stop_after_attempt(8),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def generate_email_thread(
        self,
        topic: str,
        advisor_name: str,
        client_name: str,
        thread_count: int,
    ) -> list[dict[str, Any]]:
        completion = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": self._build_system_prompt(),
                },
                {
                    "role": "user",
                    "content": self._build_user_prompt(
                        topic=topic,
                        advisor_name=advisor_name,
                        client_name=client_name,
                        thread_count=thread_count,
                    ),
                },
            ],
            temperature=0.7,
            top_p=0.95,
            max_tokens=4096,
        )

        content = completion.choices[0].message.content

        if not content:
            raise ValueError("NVIDIA returned an empty response.")

        return self._parse_response(content)

    @staticmethod
    def _build_system_prompt() -> str:
        return """
You generate realistic synthetic email conversations
between a financial advisor and a client.

Return ONLY a valid JSON array.

Each array element must contain:
- "sender": either "advisor" or "client"
- "subject": the email subject
- "body": only the new content of the email

Do NOT include:
- quoted previous messages
- email headers
- timestamps
- Markdown code fences

The messages must form a chronological,
coherent back-and-forth conversation.

Replies should use "Re:" in the subject.
""".strip()

    @staticmethod
    def _build_user_prompt(
        topic: str,
        advisor_name: str,
        client_name: str,
        thread_count: int,
    ) -> str:
        return f"""
Generate exactly {thread_count} realistic emails
about the following topic:

Topic: {topic}

Financial Advisor: {advisor_name}
Client: {client_name}

Alternate naturally between the client and advisor.

Each email should respond naturally to the
previous email and maintain a coherent conversation.

Return only a JSON array.
""".strip()

    @staticmethod
    def _parse_response(
        content: str,
    ) -> list[dict[str, Any]]:
        content = content.strip()

        # Remove accidental Markdown code fences.
        if content.startswith("```"):
            lines = content.splitlines()

            if lines and lines[0].startswith("```"):
                lines.pop(0)

            if lines and lines[-1].startswith("```"):
                lines.pop()

            content = "\n".join(lines).strip()

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"NVIDIA returned invalid JSON:\n{content}") from e

        if not isinstance(data, list):
            raise ValueError("NVIDIA response must be a JSON array.")

        return data
