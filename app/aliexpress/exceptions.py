class AliExpressAPIError(Exception):
    def __init__(self, message: str, *, code: str | int | None = None) -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class AliExpressRateLimitError(AliExpressAPIError):
    pass


class AliExpressCredentialsError(AliExpressAPIError):
    pass


class AliExpressImageSearchNotSupportedError(AliExpressAPIError):
    pass
