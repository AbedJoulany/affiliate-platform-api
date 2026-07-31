class ServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(ServiceError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, status_code=404)


class ConflictError(ServiceError):
    def __init__(self, message: str = "Resource already exists") -> None:
        super().__init__(message, status_code=409)


class UnauthorizedError(ServiceError):
    def __init__(self, message: str = "Could not validate credentials") -> None:
        super().__init__(message, status_code=401)


class ForbiddenError(ServiceError):
    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message, status_code=403)


class ValidationError(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=422)


class AIProviderError(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)


class TelegramPublishError(ServiceError):
    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        telegram_error_code: int | str | None = None,
        retry_after: float | int | None = None,
    ) -> None:
        super().__init__(message, status_code=502)
        self.http_status = http_status
        self.telegram_error_code = telegram_error_code
        self.retry_after = retry_after


class AliExpressAPIError(ServiceError):
    def __init__(self, message: str, *, code: str | int | None = None) -> None:
        super().__init__(message, status_code=502)
        self.code = code
