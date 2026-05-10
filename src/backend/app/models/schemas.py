from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


TextbookStatus = Literal["parsing", "parsed", "failed"]
GraphRelationType = Literal["prerequisite", "parallel", "contains", "applies_to"]
GraphBuildMode = Literal["auto", "llm", "mock"]
IntegrationAction = Literal["merge", "keep", "remove"]
ConceptRelationType = Literal["same_concept", "broader_narrower", "related"]


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


class IntegratedKnowledgeNode(BaseModel):
    id: str
    name: str
    definition: str
    category: str
    source_nodes: list[str]
    textbook_titles: list[str]
    chapters: list[str]
    pages: list[int]
    source_text: str
    char_count: int


class IntegrationDecision(BaseModel):
    decision_id: str
    action: IntegrationAction
    concept_relation: ConceptRelationType
    reason: str
    confidence: float = Field(ge=0, le=1)
    affected_nodes: list[str]
    result_node: IntegratedKnowledgeNode
    original_chars: int
    compressed_chars: int
    editable: bool = True
    manually_edited: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class IntegrationRunRequest(BaseModel):
    textbook_ids: list[str] | None = None
    similarity_threshold: float = Field(default=0.62, ge=0, le=1)
    max_decisions: int = Field(default=36, ge=3, le=120)


class IntegrationStats(BaseModel):
    textbook_count: int
    decision_count: int
    merge_count: int
    keep_count: int
    remove_count: int
    original_chars: int
    compressed_chars: int
    compression_ratio: float


class IntegrationResponse(BaseModel):
    textbook_ids: list[str]
    decisions: list[IntegrationDecision]
    stats: IntegrationStats
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class IntegrationDecisionPatch(BaseModel):
    action: IntegrationAction | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=500)
    confidence: float | None = Field(default=None, ge=0, le=1)


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
