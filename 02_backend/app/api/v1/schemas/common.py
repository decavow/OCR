# ErrorResponse, PaginatedResponse

from pydantic import BaseModel
from typing import TypeVar, Generic, List

T = TypeVar("T")


class ErrorResponse(BaseModel):
    detail: str
    code: str = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
