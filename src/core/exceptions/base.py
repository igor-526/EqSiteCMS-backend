class ClientError(Exception):
    """Error when user does something wrong."""

    pass


class NotFoundError(ClientError):
    """Raised when requested resource is not found."""

    pass


class ConsistencyError(Exception):
    """Never should be raised."""

    pass


class EntityNotFoundButShouldExistError(ConsistencyError):
    """Raised when requested resource is not found but should exist."""

    pass


class ConflictError(ConsistencyError):
    """Raised when resource conflicts with existing one."""

    pass
