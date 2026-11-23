class ProviderError(Exception):
    """An external operation failed; its internal details stay out of responses."""

    def __init__(self, message: str, category: str | None = None):
        # `category` is an optional, additive machine-readable tag (e.g.
        # "bot-protection", "download-limit-exceeded") for evaluation/
        # diagnostic tooling to classify URL-ingestion failures (remediation
        # pass 5, part 10) without changing the user-facing message or any
        # existing behavior -- it is never included in the HTTP response.
        super().__init__(message)
        self.category = category
