import json
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

HTTP_SUCCESS_CODE = 200
DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_NVIDIA_MODEL = "meta/llama-3.1-70b-instruct"


def clean_json_content(raw_content: str) -> str:
    """Strips markdown code blocks and returns clean JSON string."""
    cleaned = raw_content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def build_email_thread_prompts(
    topic: str, advisor_name: str, client_name: str, thread_count: int
) -> tuple[str, str]:
    """Builds system and user prompts for email thread generation."""
    system_prompt = (
        "You are a synthetic email thread generator. Your task is to output a chronological conversation "
        "between a financial advisor and a client. You must format the output strictly as a JSON array "
        "of objects representing the chronological messages. Each object must contain:\n"
        "- 'sender': either 'advisor' or 'client'\n"
        "- 'body': the clean text body of the email (without any trailing quoted history or headers, just the new message content)\n"
        "- 'subject': the subject line of the email (starting with 'Re:' for replies)"
    )

    user_prompt = (
        f"Generate a thread of exactly {thread_count} realistic back-and-forth emails discussing the topic: '{topic}'.\n"
        f"Financial Advisor: '{advisor_name}'\n"
        f"Client: '{client_name}'\n\n"
        "Format the output strictly as a JSON array. Example structure:\n"
        "[\n"
        f'  {{"sender": "client", "subject": "{topic.title()}", "body": "Hello..."}},\n'
        f'  {{"sender": "advisor", "subject": "Re: {topic.title()}", "body": "Hi..."}}\n'
        "]"
    )
    return system_prompt, user_prompt


def parse_email_thread_response(
    raw_content: str, provider_name: str = "LLM"
) -> list[dict[str, Any]]:
    """Cleans raw response string and parses it into a list of message dictionaries."""
    clean_content = clean_json_content(raw_content)
    data = json.loads(clean_content)

    if isinstance(data, dict):
        for val in data.values():
            if isinstance(val, list):
                return val
    if isinstance(data, list):
        return data

    raise ValueError(
        f"{provider_name} response JSON did not resolve to a list of messages."
    )


class BaseLLMClient:
    """Base client for OpenAI-compatible LLM services."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        provider_name: str = "LLM",
    ):
        if not api_key:
            raise ValueError(f"{provider_name} API key must be provided.")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.provider_name = provider_name

    def _clean_json_content(self, raw_content: str) -> str:
        """Strips markdown code blocks and returns clean JSON string."""
        return clean_json_content(raw_content)

    def _build_headers(self) -> dict[str, str]:
        """Constructs default HTTP headers for requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Constructs request payload for chat completion."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if response_format:
            payload["response_format"] = response_format
        return payload

    async def _send_request(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout: float = 45.0,
    ) -> dict[str, Any]:
        """Executes the HTTP POST request to the chat completion endpoint."""
        url = f"{self.base_url}/chat/completions"
        logger.info(
            "Requesting email thread from %s (model: %s)...",
            self.provider_name,
            self.model,
        )

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code != HTTP_SUCCESS_CODE:
                raise httpx.HTTPStatusError(
                    f"{self.provider_name} returned HTTP {response.status_code}. Status: {response.text}",
                    request=response.request,
                    response=response,
                )

            result = response.json()
            if "choices" not in result or not result["choices"]:
                raise ValueError(
                    f"{self.provider_name} response does not contain 'choices': {result}"
                )

            return result

    def _extract_content(self, response_data: dict[str, Any]) -> str:
        """Extracts text content from the LLM response choices."""
        return response_data["choices"][0]["message"]["content"]

    async def generate_email_thread(
        self, topic: str, advisor_name: str, client_name: str, thread_count: int
    ) -> list[dict[str, Any]]:
        """Calls the LLM API to generate raw email messages for a thread."""
        system_prompt, user_prompt = build_email_thread_prompts(
            topic, advisor_name, client_name, thread_count
        )
        headers = self._build_headers()
        payload = self._build_payload(system_prompt, user_prompt)
        response_data = await self._send_request(payload, headers)
        raw_content = self._extract_content(response_data)
        return parse_email_thread_response(raw_content, self.provider_name)


class NvidiaClient(BaseLLMClient):
    """Client for NVIDIA NIM / AI Cloud LLM generation."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_NVIDIA_MODEL,
        base_url: str = DEFAULT_NVIDIA_BASE_URL,
    ):
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url,
            provider_name="NVIDIA",
        )

    def _build_headers(self) -> dict[str, str]:
        headers = super()._build_headers()
        headers["Accept"] = "application/json"
        return headers


