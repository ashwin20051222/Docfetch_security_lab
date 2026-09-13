from __future__ import annotations

from typing import Any


class ApiError(Exception):
    """Structured API error matching the documented error contract."""

    status_code: int = 400
    code: str = "GENERAL_ERROR"
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, code: str | None = None):
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code
        super().__init__(self.message)

    def to_payload(self, request_id: str | None = None) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "request_id": request_id,
            }
        }


class InvalidURLError(ApiError):
    status_code = 422
    code = "INVALID_URL"


class SSRFDeniedError(ApiError):
    status_code = 422
    code = "SSRF_BLOCKED"


class FetchFailedError(ApiError):
    status_code = 502
    code = "FETCH_FAILED"


class DocumentNotFoundError(ApiError):
    status_code = 404
    code = "DOCUMENT_NOT_FOUND"


class ConflictError(ApiError):
    status_code = 409
    code = "CONFLICT"


class InvalidDocumentError(ApiError):
    status_code = 422
    code = "INVALID_DOCUMENT"


class FileTooLargeError(ApiError):
    status_code = 413
    code = "FILE_TOO_LARGE"


class TargetNotAuthorizedError(ApiError):
    status_code = 403
    code = "TARGET_NOT_AUTHORIZED"


class RateLimitedError(ApiError):
    status_code = 429
    code = "RATE_LIMITED"


class AuthRequiredError(ApiError):
    status_code = 401
    code = "AUTH_REQUIRED"


class AuthNotConfiguredError(ApiError):
    status_code = 403
    code = "AUTH_NOT_CONFIGURED"
    message = "Authentication is not configured."