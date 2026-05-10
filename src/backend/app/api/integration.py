from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.api.graph import resolve_textbooks
from app.models.schemas import (
    IntegrationDecision,
    IntegrationDecisionPatch,
    IntegrationResponse,
    IntegrationRunRequest,
    IntegrationStats,
)
from app.services.graph_service import build_knowledge_graph
from app.services.integration_service import make_empty_response, run_integration


router = APIRouter(prefix="/api/integration", tags=["integration"])

_latest_response: IntegrationResponse | None = None


@router.post("/run", response_model=IntegrationResponse)
async def run_integration_workflow(request: IntegrationRunRequest) -> IntegrationResponse:
    global _latest_response
    textbooks = resolve_textbooks(request.textbook_ids)
    if len(textbooks) < 2:
        raise HTTPException(status_code=400, detail="跨教材整合至少需要两本已解析教材")

    graph = build_knowledge_graph(textbooks)
    _latest_response = run_integration(
        graph,
        similarity_threshold=request.similarity_threshold,
        max_decisions=request.max_decisions,
    )
    return _latest_response


@router.get("/decisions", response_model=IntegrationResponse)
async def list_integration_decisions() -> IntegrationResponse:
    if _latest_response is None:
        return make_empty_response([])
    return _latest_response


@router.patch("/decisions/{decision_id}", response_model=IntegrationDecision)
async def patch_integration_decision(
    decision_id: str,
    patch: IntegrationDecisionPatch,
) -> IntegrationDecision:
    global _latest_response
    if _latest_response is None:
        raise HTTPException(status_code=404, detail="尚未生成整合决策")

    for decision in _latest_response.decisions:
        if decision.decision_id != decision_id:
            continue
        if not decision.editable:
            raise HTTPException(status_code=400, detail="该决策不可编辑")
        if patch.action is not None:
            decision.action = patch.action
        if patch.reason is not None:
            decision.reason = patch.reason
        if patch.confidence is not None:
            decision.confidence = round(patch.confidence, 2)
        decision.manually_edited = True
        decision.updated_at = datetime.utcnow()
        _latest_response.stats = recompute_stats_after_patch(_latest_response)
        return decision

    raise HTTPException(status_code=404, detail="整合决策不存在")


def recompute_stats_after_patch(response: IntegrationResponse) -> IntegrationStats:
    stats = response.stats
    return IntegrationStats(
        textbook_count=stats.textbook_count,
        decision_count=len(response.decisions),
        merge_count=sum(1 for decision in response.decisions if decision.action == "merge"),
        keep_count=sum(1 for decision in response.decisions if decision.action == "keep"),
        remove_count=sum(1 for decision in response.decisions if decision.action == "remove"),
        original_chars=stats.original_chars,
        compressed_chars=stats.compressed_chars,
        compression_ratio=stats.compression_ratio,
    )
