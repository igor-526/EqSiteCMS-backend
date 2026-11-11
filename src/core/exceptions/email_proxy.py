class EmailServiceResponseError(Exception):
    """The peer response cannot establish a valid operation result."""

    def __init__(self) -> None:
        super().__init__("Email service returned an invalid response")


class EmailConfirmationQueueError(Exception):
    """Create succeeded, but confirmation queue acceptance is unknown."""

    def __init__(self) -> None:
        super().__init__(
            "Email сохранён, но отправку подтверждения не удалось подтвердить. "
            "Повторите запрос или используйте повторную отправку."
        )
