import os

from fastapi import APIRouter, HTTPException

from app.core.store import get_store
from app.models.schemas import GraphData
from app.services.graph_service import GraphStore

router = APIRouter(prefix="/api/graph", tags=["graph"])
graph_store = GraphStore(get_store())


@router.post("/build")
async def build_graph(textbook_id: str) -> GraphData:
    graph = graph_store.build_graph(textbook_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="教材不存在")
    return graph


@router.get("/{textbook_id}")
async def get_graph(textbook_id: str) -> GraphData:
    graph = graph_store.get_graph(textbook_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="图谱未构建或不存在")
    return graph