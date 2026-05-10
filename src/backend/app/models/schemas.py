from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


TextbookStatus = Literal["parsing", "parsed", "failed"]
GraphRelationType = Literal["prerequisite", "parallel", "contains", "applies_to"]
GraphBuildMode = Literal["auto", "llm", "mock"]


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


class KnowledgeOccurrence(BaseModel):
    chapter_id: str
    chapter: str
    page: int
    source_text: str


class KnowledgeNode(BaseModel):
    id: str
    name: str
    definition: str
    category: str
    textbook_id: str
    textbook_title: str
    chapter_id: str
    chapter: str
    page: int
    source_text: str
    frequency: int = 1
    occurrences: list[KnowledgeOccurrence] = Field(default_factory=list)


class KnowledgeEdge(BaseModel):
    id: str
    source: str
    target: str
    relation_type: GraphRelationType
    label: str
    weight: float = 1.0
    textbook_id: str
    textbook_title: str
    chapter: str
    page: int
    source_text: str


class GraphBuildRequest(BaseModel):
    textbook_ids: list[str] | None = None
    mode: GraphBuildMode = "auto"
    max_nodes_per_chapter: int = Field(default=8, ge=2, le=20)


class GraphStats(BaseModel):
    textbook_count: int
    node_count: int
    edge_count: int
    relation_types: list[GraphRelationType] = Field(default_factory=list)


class GraphResponse(BaseModel):
    graph_id: str
    textbook_ids: list[str]
    nodes: list[KnowledgeNode]
    edges: list[KnowledgeEdge]
    stats: GraphStats
    build_mode: GraphBuildMode
    generated_at: datetime = Field(default_factory=datetime.utcnow)


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
