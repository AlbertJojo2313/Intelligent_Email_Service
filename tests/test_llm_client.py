import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

# Ensure tools directory is on path for synthetic_generator imports
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from synthetic_generator.llm_client import (
    BaseLLMClient,
    NvidiaClient,
    build_email_thread_prompts,
    clean_json_content,
    parse_email_thread_response,
)


def test_clean_json_content():
    raw_markdown = "```json\n[{\"sender\": \"client\", \"body\": \"Hello\"}]\n```"
    cleaned = clean_json_content(raw_markdown)
    assert cleaned == '[{"sender": "client", "body": "Hello"}]'

    raw_plain = '[{"sender": "advisor", "body": "Hi"}]'
    assert clean_json_content(raw_plain) == raw_plain


def test_build_email_thread_prompts():
    sys_prompt, user_prompt = build_email_thread_prompts(
        topic="Portfolio Review",
        advisor_name="John Advisor",
        client_name="Sarah Client",
        thread_count=3,
    )
    assert "synthetic email thread generator" in sys_prompt
    assert "Portfolio Review" in user_prompt
    assert "John Advisor" in user_prompt
    assert "Sarah Client" in user_prompt
    assert "3" in user_prompt


def test_parse_email_thread_response_list():
    raw_json = '[{"sender": "client", "subject": "Hi", "body": "Hello"}]'
    result = parse_email_thread_response(raw_json, "TestProvider")
    assert len(result) == 1
    assert result[0]["sender"] == "client"


def test_parse_email_thread_response_dict_wrapper():
    raw_json = '{"messages": [{"sender": "advisor", "subject": "Re: Hi", "body": "Hello"}]}'
    result = parse_email_thread_response(raw_json, "TestProvider")
    assert len(result) == 1
    assert result[0]["sender"] == "advisor"


def test_parse_email_thread_response_invalid():
    with pytest.raises(ValueError, match="TestProvider response JSON did not resolve"):
        parse_email_thread_response('"invalid_string"', "TestProvider")


def test_missing_api_key_validation():
    with pytest.raises(ValueError, match="NVIDIA API key must be provided."):
        NvidiaClient(api_key="")


def test_nvidia_client_defaults_and_headers():
    client = NvidiaClient(api_key="nvapi-test123")
    assert client.api_key == "nvapi-test123"
    assert client.model == "meta/llama-3.1-70b-instruct"
    assert client.base_url == "https://integrate.api.nvidia.com/v1"

    headers = client._build_headers()
    assert headers["Authorization"] == "Bearer nvapi-test123"
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"


@pytest.mark.asyncio
async def test_nvidia_client_generate_email_thread():
    client = NvidiaClient(api_key="nvapi-test123")

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "choices": [
            {
                "message": {
                    "content": '```json\n[{"sender": "client", "subject": "Test", "body": "Body"}]\n```'
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        messages = await client.generate_email_thread(
            topic="Test Topic",
            advisor_name="Adv",
            client_name="Cli",
            thread_count=2,
        )
        assert len(messages) == 1
        assert messages[0]["subject"] == "Test"
        assert mock_post.called
