from fastapi import APIRouter, HTTPException

from app.api.graph import resolve_textbooks
from app.models.schemas import (
    IntegrationDecision,
    IntegrationDecisionPatch,
    IntegrationResponse,
    IntegrationRunRequest,
)
from app.services.graph_service import build_knowledge_graph
from app.services.integration_service import run_integration
from app.services.integration_state import list_integration_response, set_integration_response, update_decision


router = APIRouter(prefix="/api/integration", tags=["integration"])


@router.post("/run", response_model=IntegrationResponse)
async def run_integration_workflow(request: IntegrationRunRequest) -> IntegrationResponse:
    textbooks = resolve_textbooks(request.textbook_ids)
    if len(textbooks) < 2:
        raise HTTPException(status_code=400, detail="跨教材整合至少需要两本已解析教材")

    graph = build_knowledge_graph(textbooks)
    return set_integration_response(
        run_integration(
            graph,
            similarity_threshold=request.similarity_threshold,
            max_decisions=request.max_decisions,
        )
    )


@router.get("/decisions", response_model=IntegrationResponse)
async def list_integration_decisions() -> IntegrationResponse:
    return list_integration_response()


@router.patch("/decisions/{decision_id}", response_model=IntegrationDecision)
async def patch_integration_decision(
    decision_id: str,
    patch: IntegrationDecisionPatch,
) -> IntegrationDecision:
    return update_decision(decision_id, patch)
