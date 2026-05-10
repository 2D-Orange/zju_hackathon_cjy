from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


TextbookStatus = Literal["parsing", "parsed", "failed"]


class Chapter(BaseModel):
    chapter_id: str
    title: str
    page_start: int
    page_end: int
    content: str
    char_count: int


class TextbookSummary(BaseModel):
    textbook_id: str
    filename: str
    title: str
    format: str
    size_bytes: int
    size_label: str
    status: TextbookStatus
    message: str
    total_pages: int = 0
    total_chars: int = 0
    chapter_count: int = 0
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class TextbookDetail(TextbookSummary):
    chapters: list[Chapter] = Field(default_factory=list)


class UploadResponse(BaseModel):
    textbooks: list[TextbookSummary]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    detail: str | list[dict]
