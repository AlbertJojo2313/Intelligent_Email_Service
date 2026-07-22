import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure tools directory is on path for synthetic_generator imports
tools_dir = str(Path(__file__).parent.parent / "tools")
if tools_dir not in sys.path:
    sys.path.insert(0, tools_dir)

from synthetic_generator.llm_client import (  # type: ignore[import-not-found, reportMissingImports]
    DEFAULT_NVIDIA_BASE_URL,
    DEFAULT_NVIDIA_MODEL,
    NvidiaClient,
)


def test_missing_api_key_validation():
    with pytest.raises(ValueError, match="NVIDIA API key must be provided."):
        NvidiaClient(api_key="")


def test_nvidia_client_defaults():
    client = NvidiaClient(api_key="nvapi-test123")
    assert client.model == DEFAULT_NVIDIA_MODEL
    assert str(client.client.base_url).rstrip("/") == DEFAULT_NVIDIA_BASE_URL


def test_build_system_prompt():
    prompt = NvidiaClient._build_system_prompt()
    assert "synthetic email conversation" in prompt.lower()
    assert "json array" in prompt.lower()


def test_build_user_prompt():
    prompt = NvidiaClient._build_user_prompt(
        topic="Portfolio Review",
        advisor_name="John Advisor",
        client_name="Sarah Client",
        thread_count=3,
    )
    assert "Portfolio Review" in prompt
    assert "John Advisor" in prompt
    assert "Sarah Client" in prompt
    assert "3" in prompt


def test_parse_response_valid_json_array():
    raw_json = '[{"sender": "client", "subject": "Hi", "body": "Hello"}]'
    result = NvidiaClient._parse_response(raw_json)
    assert len(result) == 1
    assert result[0]["sender"] == "client"


def test_parse_response_markdown_fences():
    raw_markdown = "```json\n[{\"sender\": \"client\", \"subject\": \"Hi\", \"body\": \"Hello\"}]\n```"
    result = NvidiaClient._parse_response(raw_markdown)
    assert len(result) == 1
    assert result[0]["body"] == "Hello"


def test_parse_response_invalid_json():
    with pytest.raises(ValueError, match="NVIDIA returned invalid JSON"):
        NvidiaClient._parse_response("invalid json string")


def test_parse_response_not_a_list():
    with pytest.raises(ValueError, match="NVIDIA response must be a JSON array"):
        NvidiaClient._parse_response('{"key": "value"}')


@pytest.mark.asyncio
async def test_nvidia_client_generate_email_thread():
    client = NvidiaClient(api_key="nvapi-test123")

    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(
            message=MagicMock(
                content='[{"sender": "client", "subject": "Test", "body": "Body"}]'
            )
        )
    ]

    with patch.object(
        client.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_create.return_value = mock_completion

        messages = await client.generate_email_thread(
            topic="Test Topic",
            advisor_name="Adv",
            client_name="Cli",
            thread_count=2,
        )

        assert len(messages) == 1
        assert messages[0]["subject"] == "Test"
        assert mock_create.called
