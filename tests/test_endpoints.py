from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intelligent_email_service.email_connectors import MockGraphProvider


@pytest.mark.asyncio
async def test_mock_graph_provider_endpoint():
    """Test for Mockoon"""
    provider = MockGraphProvider(base_url="http://localhost:3000")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "value": [
            {
                "id": "msg-001",
                "subject": "Portfolio Rebalance Q2",
                "conversationId": "conv-abc-123",
                "receivedDateTime": "2026-05-02T14:00:00Z",
                "from": {
                    "emailAddress": {
                        "name": "Jane Client",
                        "address": "jane.household@example-clients.com",
                    }
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "name": "Advisor One",
                            "address": "advisor1@contoso.com",
                        }
                    }
                ],
                "hasAttachments": False,
                "body": {
                    "contentType": "html",
                    "content": "<p>Sounds good, thanks for confirming.</p>",
                },
            }
        ]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        emails = await provider.get_emails(user_id="tst_ad-001")
        assert len(emails) == 1
        assert emails[0]["id"] == "msg-001"
        assert emails[0]["subject"] == "Portfolio Rebalance Q2"
        mock_get.assert_called_once_with(
            "http://localhost:3000/v1.0/users/tst_ad-001/messages"
        )


@pytest.mark.asyncio
async def test_mock_graph_users_endpoint():
    provider = MockGraphProvider(base_url="http://localhost:3000")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "value": [
            {
                "id": "tst_ad-001",
                "displayName": "Advisor One",
                "mail": "advisor1@contoso.com",
            },
            {
                "id": "tst_ad-002",
                "displayName": "Advisor Two",
                "mail": "advisor2@contoso.com",
            },
        ]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        advisors = await provider.get_advisors_list()
        assert advisors[0]["id"] == "tst_ad-001"
        assert advisors[1]["id"] == "tst_ad-002"
        mock_get.assert_called_once_with("http://localhost:3000/v1.0/users/")


@pytest.mark.asyncio
async def test_mock_graph_advisor_info_endpoint():
    provider = MockGraphProvider(base_url="http://localhost:3000")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "value": [
            {
                "id": "tst_ad-001",
                "displayName": "Advisor One",
                "mail": "advisor1@contoso.com",
            }
        ]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        advisor_info = await provider.get_advisor_info(user_id="tst_ad-001")
        assert len(advisor_info) == 1
        mock_get.assert_called_once_with("http://localhost:3000/v1.0/users/tst_ad-001")
