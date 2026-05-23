class ShelfyGAIError(Exception):
    """Base exception for application-level errors."""


class WindowNotFoundError(ShelfyGAIError):
    """Raised when a window handle can no longer be found."""


class WindowOperationError(ShelfyGAIError):
    """Raised when a platform window operation fails."""


class GroupOperationError(ShelfyGAIError):
    """Raised when a window group operation is invalid."""
