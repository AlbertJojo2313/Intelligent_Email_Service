"""FastAPI application for intelligent email service"""

from dataclasses import asdict
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from intelligent_email_service.config import EmailQueryFilter, PipelineConfig
from intelligent_email_service.exceptions import EmailProviderError
from intelligent_email_service.pipeline import process_client_emails

app = FastAPI(
    title="Intelligent Email Service",
    description="Basic Endpoint for email thread compression on Azure.",
    version="0.1.0",
)


class CompressRequest(BaseModel):
    advisor_id: str = Field(
        ...,
        description="Financial advisor ID / User ID in Microsoft Graph",
        examples=["tst_ad-001"],
    )
    client_id: str = Field(
        ...,
        description="Target client email address",
        examples=["client@household.com"],
    )
    start_date: datetime | None = Field(
        default=None,
        description="Optional start date filter (ISO 8601)",
    )
    end_date: datetime | None = Field(
        default=None,
        description="Optional end date filter (ISO 8601)",
    )


@app.get("/")
def root() -> dict[str, str]:
    """Root endpoint for status check"""
    return {
        "message": "Intelligent Email service is running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Health Check endpoint for service"""
    config = PipelineConfig()
    return {
        "status": "healthy",
        "env": config.app_env,
    }


@app.post("/compress")
async def compress_emails(payload: CompressRequest) -> list[dict[str, Any]]:
    """Retrieves, Reconstructs, and compresses client email threads"""
    query = EmailQueryFilter(
        advisor_id=payload.advisor_id,
        client_id=payload.client_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    config = PipelineConfig()

    try:
        threads = await process_client_emails(query=query, config=config)
        return [asdict(t) for t in threads]
    except EmailProviderError as err:
        raise HTTPException(
            status_code=502,
            detail=f"Email Provider Error: {err}",
        ) from err
    except Exception as err:
        raise HTTPException(
            status_code=500, detail=f"Internal Processing Error: {err}"
        ) from err
