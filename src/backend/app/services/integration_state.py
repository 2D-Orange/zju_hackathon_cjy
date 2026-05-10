import json
import os
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException

from app.models.schemas import (
    IntegrationDecision,
    IntegrationDecisionPatch,
    IntegrationResponse,
    IntegrationStats,
)
from app.services.integration_service import make_empty_response


_latest_response: IntegrationResponse | None = None


def set_integration_response(response: IntegrationResponse) -> IntegrationResponse:
    global _latest_response
    _latest_response = response
    save_integration_response(response)
    return response


def get_integration_response() -> IntegrationResponse | None:
    global _latest_response
    if _latest_response is not None:
        return _latest_response

    response = load_integration_response()
    if response is not None:
        _latest_response = response
    return _latest_response


def list_integration_response() -> IntegrationResponse:
    return get_integration_response() or make_empty_response([])


def find_decision(decision_id: str | None = None, message: str = "") -> IntegrationDecision | None:
    response = get_integration_response()
    if response is None or not response.decisions:
        return None

    if decision_id:
        for decision in response.decisions:
            if decision.decision_id == decision_id:
                return decision

    for decision in response.decisions:
        if decision.decision_id and decision.decision_id in message:
            return decision

    normalized = normalize_text(message)
    for decision in response.decisions:
        if decision.result_node.name and normalize_text(decision.result_node.name) in normalized:
            return decision

    return response.decisions[0]


def update_decision(
    decision_id: str,
    patch: IntegrationDecisionPatch,
    manual_reason: str | None = None,
) -> IntegrationDecision:
    response = get_integration_response()
    if response is None:
        raise HTTPException(status_code=404, detail="尚未生成整合决策")

    for decision in response.decisions:
        if decision.decision_id != decision_id:
            continue
        if not decision.editable:
            raise HTTPException(status_code=400, detail="该决策不可编辑")
        if patch.action is not None:
            decision.action = patch.action
        if patch.reason is not None:
            decision.reason = patch.reason
        elif manual_reason is not None:
            decision.reason = manual_reason
        if patch.confidence is not None:
            decision.confidence = round(patch.confidence, 2)
        decision.manually_edited = True
        decision.updated_at = datetime.utcnow()
        response.stats = recompute_stats_after_patch(response)
        save_integration_response(response)
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


def save_integration_response(response: IntegrationResponse) -> None:
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_integration_response() -> IntegrationResponse | None:
    path = store_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return IntegrationResponse.model_validate(data)


def store_path() -> Path:
    return Path(os.getenv("INTEGRATION_STORE_PATH", "data/processed/integration_decisions.json"))


def normalize_text(value: str) -> str:
    return "".join(value.lower().split())
