"""Custom exception hierarchy for Intelligent Email Service."""


class EmailServiceError(Exception):
    """Base exception for all errors raised by Intelligent Email Service."""


class EmailProviderError(EmailServiceError):
    """Base exception for email provider communication failures."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class ProviderAuthenticationError(EmailProviderError):
    """Raised when authentication credentials (OAuth token/API key) are invalid or expired (401/403)."""


class ProviderRateLimitError(EmailProviderError):
    """Raised when the email provider returns an HTTP 429 rate limit/throttling error."""

    def __init__(
        self,
        message: str,
        retry_after: int | None = None,
        status_code: int | None = 429,
        response_body: str | None = None,
    ):
        super().__init__(message, status_code=status_code, response_body=response_body)
        self.retry_after = retry_after


class ProviderNotFoundError(EmailProviderError):
    """Raised when a requested resource (user, mailbox, or message) is not found (404)."""


class EmailRetrievalError(EmailServiceError):
    """Raised when filtering, retrieving, or processing client emails fails."""
