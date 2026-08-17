from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from intelligent_email_service.app import app
from intelligent_email_service.exceptions import EmailProviderError
from intelligent_email_service.preprocessing.compressor import CompressedThread


@pytest.mark.asyncio
async def test_root_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Intelligent Email service is running"
        assert "docs" in data
        assert "health" in data


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "env" in data


@pytest.mark.asyncio
async def test_compress_endpoint_success():
    mock_threads = [
        CompressedThread(
            subject="Financial Planning Q3",
            conversation_id="conv-123",
            format="modified",
            total_messages=2,
            compressed_body="Summary of conversation...",
            attachments_summary=[],
            estimated_tokens=30,
            used_llmlingua=False,
        )
    ]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        with patch(
            "intelligent_email_service.app.process_client_emails",
            new_callable=AsyncMock,
        ) as mock_process:
            mock_process.return_value = mock_threads
            response = await client.post(
                "/compress",
                json={
                    "advisor_id": "advisor@firm.com",
                    "client_id": "client@household.com",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["subject"] == "Financial Planning Q3"
            assert data[0]["total_messages"] == 2


@pytest.mark.asyncio
async def test_compress_endpoint_provider_error():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        with patch(
            "intelligent_email_service.app.process_client_emails",
            new_callable=AsyncMock,
        ) as mock_process:
            mock_process.side_effect = EmailProviderError("Upstream service timeout")
            response = await client.post(
                "/compress",
                json={
                    "advisor_id": "advisor@firm.com",
                    "client_id": "client@household.com",
                },
            )
            assert response.status_code == 502
            assert "Email Provider Error" in response.json()["detail"]


@pytest.mark.asyncio
async def test_compress_endpoint_empty_results():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        with patch(
            "intelligent_email_service.app.process_client_emails",
            new_callable=AsyncMock,
        ) as mock_process:
            mock_process.return_value = []
            response = await client.post(
                "/compress",
                json={
                    "advisor_id": "advisor@firm.com",
                    "client_id": "no_emails@household.com",
                },
            )
            assert response.status_code == 200
            assert response.json() == []


@pytest.mark.asyncio
async def test_compress_endpoint_missing_required_fields():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/compress", json={"advisor_id": "advisor@firm.com"})
        assert response.status_code == 422  # Pydantic validation error for missing client_id


@pytest.mark.asyncio
async def test_compress_endpoint_with_date_filters():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        with patch(
            "intelligent_email_service.app.process_client_emails",
            new_callable=AsyncMock,
        ) as mock_process:
            mock_process.return_value = []
            response = await client.post(
                "/compress",
                json={
                    "advisor_id": "advisor@firm.com",
                    "client_id": "client@household.com",
                    "start_date": "2026-01-01T00:00:00Z",
                    "end_date": "2026-08-16T23:59:59Z",
                },
            )
            assert response.status_code == 200
            assert mock_process.called
            call_query = mock_process.call_args.kwargs.get("query")
            assert call_query.start_date is not None
            assert call_query.end_date is not None
