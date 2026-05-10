from fastapi import APIRouter

import app.api.graph as graph_module
import app.api.rag as rag_module
from app.api.textbooks import store
from app.models.schemas import ReportSummary
from app.services.chat_service import get_sessions
from app.services.integration_state import get_integration_response
from app.services.rag_service import make_status

router = APIRouter(prefix="/api/report", tags=["report"])


@router.get("/summary", response_model=ReportSummary)
async def report_summary() -> ReportSummary:
    textbooks = store.list_textbooks()
    parsed = [t for t in textbooks if t.status == "parsed"]
    total_chapters = 0
    total_chars = 0
    for t in parsed:
        detail = store.get_textbook(t.textbook_id)
        if detail:
            total_chapters += len(detail.chapters)
            total_chars += detail.total_chars

    graph_node_count = 0
    graph_edge_count = 0
    graph_textbook_count = 0
    if textbooks:
        parsed_ids = [t.textbook_id for t in parsed]
        combined_key = "|".join(sorted(parsed_ids))
        cached = graph_module._graph_cache.get(combined_key)
        if cached:
            graph_node_count = len(cached.nodes)
            graph_edge_count = len(cached.edges)
            graph_textbook_count = cached.stats.textbook_count if cached.stats else len(cached.textbook_ids)

    integration_response = get_integration_response()
    integration_decision_count = 0
    integration_merge_count = 0
    integration_keep_count = 0
    integration_remove_count = 0
    compression_ratio = 0.0
    original_chars = 0
    compressed_chars = 0
    if integration_response is not None:
        integration_decision_count = len(integration_response.decisions)
        if integration_response.stats:
            integration_merge_count = integration_response.stats.merge_count
            integration_keep_count = integration_response.stats.keep_count
            integration_remove_count = integration_response.stats.remove_count
            compression_ratio = integration_response.stats.compression_ratio
            original_chars = integration_response.stats.original_chars
            compressed_chars = integration_response.stats.compressed_chars

    rag_status = make_status(rag_module._latest_index)

    sessions = get_sessions()
    chat_session_count = len(sessions)

    return ReportSummary(
        textbook_count=len(textbooks),
        parsed_textbook_count=len(parsed),
        total_chapters=total_chapters,
        total_chars=total_chars,
        graph_node_count=graph_node_count,
        graph_edge_count=graph_edge_count,
        graph_textbook_count=graph_textbook_count,
        integration_decision_count=integration_decision_count,
        integration_merge_count=integration_merge_count,
        integration_keep_count=integration_keep_count,
        integration_remove_count=integration_remove_count,
        compression_ratio=compression_ratio,
        original_chars=original_chars,
        compressed_chars=compressed_chars,
        rag_indexed=rag_status.indexed,
        rag_chunk_count=rag_status.chunk_count,
        rag_embedding_mode=rag_status.embedding_mode or "",
        chat_session_count=chat_session_count,
    )
