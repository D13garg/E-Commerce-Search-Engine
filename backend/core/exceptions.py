"""
core/exceptions.py — Custom exceptions for the layered architecture.
"""

class AppException(Exception):
    """Base application exception."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ProductNotFound(AppException):
    """Exception raised when a product is not found."""
    def __init__(self, slug: str, store: str = None):
        if store:
            message = f"Product '{slug}' not found in store '{store}'"
        else:
            message = f"Product '{slug}' not found"
        super().__init__(message, status_code=404)


class MatchNotFound(AppException):
    """Exception raised when cross-store matches are not found."""
    def __init__(self, message: str):
        super().__init__(message, status_code=404)


class PriceHistoryNotFound(AppException):
    """Exception raised when price history is not found."""
    def __init__(self, message: str):
        super().__init__(message, status_code=404)
