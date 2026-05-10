from fastapi import APIRouter

from app.api.graph import resolve_textbooks
from app.models.schemas import RagIndexRequest, RagIndexStatus, RagQueryRequest, RagQueryResponse
from app.services.rag_service import RagIndex, build_rag_index, make_status, query_rag


router = APIRouter(prefix="/api/rag", tags=["rag"])

_latest_index: RagIndex | None = None


@router.post("/index", response_model=RagIndexStatus)
async def create_rag_index(request: RagIndexRequest) -> RagIndexStatus:
    global _latest_index
    textbooks = resolve_textbooks(request.textbook_ids)
    _latest_index = build_rag_index(textbooks, chunk_size=request.chunk_size, overlap=request.overlap)
    return make_status(_latest_index)


@router.get("/status", response_model=RagIndexStatus)
async def get_rag_status() -> RagIndexStatus:
    return make_status(_latest_index)


@router.post("/query", response_model=RagQueryResponse)
async def query_rag_index(request: RagQueryRequest) -> RagQueryResponse:
    return query_rag(
        _latest_index,
        question=request.question,
        top_k=request.top_k,
        min_score=request.min_score,
    )
