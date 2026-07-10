"""auth/exceptions.py — HTTP exceptions for the auth module."""

from fastapi import HTTPException, status


class AppException(HTTPException):
    pass


class UnauthorizedException(AppException):
    def __init__(self, detail: str = "Not authenticated."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class BadRequestException(AppException):
    def __init__(self, detail: str = "Bad request."):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class ConflictException(AppException):
    def __init__(self, detail: str = "Resource already exists."):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class TooManyRequestsException(AppException):
    def __init__(self, detail: str = "Too many requests. Please try again later."):
        super().__init__(status_code=429, detail=detail)