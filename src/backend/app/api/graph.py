from fastapi import APIRouter, HTTPException

from app.api.textbooks import store
from app.models.schemas import GraphBuildRequest, GraphResponse, TextbookDetail
from app.services.graph_service import build_knowledge_graph


router = APIRouter(prefix="/api/graph", tags=["graph"])

_graph_cache: dict[str, GraphResponse] = {}


@router.post("/build", response_model=GraphResponse)
async def build_graph(request: GraphBuildRequest) -> GraphResponse:
    textbooks = resolve_textbooks(request.textbook_ids)
    graph = build_knowledge_graph(
        textbooks,
        mode=request.mode,
        max_nodes_per_chapter=request.max_nodes_per_chapter,
    )
    _graph_cache[cache_key(graph.textbook_ids)] = graph
    for textbook_id in graph.textbook_ids:
        _graph_cache[cache_key([textbook_id])] = (
            graph
            if len(graph.textbook_ids) == 1
            else build_knowledge_graph([item for item in textbooks if item.textbook_id == textbook_id])
        )
    return graph


@router.get("/{textbook_id}", response_model=GraphResponse)
async def get_graph(textbook_id: str) -> GraphResponse:
    key = cache_key([textbook_id])
    if key in _graph_cache:
        return _graph_cache[key]
    textbooks = resolve_textbooks([textbook_id])
    graph = build_knowledge_graph(textbooks)
    _graph_cache[key] = graph
    return graph


def resolve_textbooks(textbook_ids: list[str] | None) -> list[TextbookDetail]:
    if textbook_ids:
        requested_ids = textbook_ids
    else:
        requested_ids = [item.textbook_id for item in store.list_textbooks() if item.status == "parsed"]

    if not requested_ids:
        raise HTTPException(status_code=400, detail="请先上传并解析至少一本教材")

    textbooks: list[TextbookDetail] = []
    missing: list[str] = []
    not_ready: list[str] = []
    for textbook_id in requested_ids:
        textbook = store.get_textbook(textbook_id)
        if textbook is None:
            missing.append(textbook_id)
            continue
        if textbook.status != "parsed":
            not_ready.append(textbook_id)
            continue
        textbooks.append(textbook)

    if missing:
        raise HTTPException(status_code=404, detail=f"教材不存在：{', '.join(missing)}")
    if not_ready:
        raise HTTPException(status_code=400, detail=f"教材尚未解析完成：{', '.join(not_ready)}")
    return textbooks


def cache_key(textbook_ids: list[str]) -> str:
    return "|".join(sorted(textbook_ids))
