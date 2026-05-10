import json
import os
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.models.schemas import (
    ChatMessage,
    IntegrationAction,
    IntegrationDecision,
    IntegrationDecisionPatch,
    TeacherFeedbackRequest,
    TeacherFeedbackResponse,
)
from app.services.integration_state import find_decision, get_integration_response, update_decision


SessionStore = dict[str, list[ChatMessage]]

_sessions: SessionStore | None = None


def handle_teacher_feedback(request: TeacherFeedbackRequest) -> TeacherFeedbackResponse:
    session_id = request.session_id or f"session_{uuid4().hex[:10]}"
    sessions = get_sessions()
    history = sessions.get(session_id) or request.history.copy()

    teacher_message = ChatMessage(
        message_id=f"msg_{uuid4().hex[:10]}",
        role="teacher",
        content=request.message.strip(),
        decision_id=request.decision_id,
    )
    history.append(teacher_message)

    response = get_integration_response()
    if response is None or not response.decisions:
        answer = "请先在“跨教材整合”中运行整合，生成可追溯决策后再进行反馈。"
        assistant_message = make_assistant_message(answer, request.decision_id)
        history.append(assistant_message)
        save_session(session_id, history)
        return TeacherFeedbackResponse(session_id=session_id, intent="clarify", answer=answer, history=history)

    decision = find_decision(request.decision_id, request.message)
    if decision is None:
        answer = "当前没有找到可解释或可修改的整合决策，请先选择一条决策再反馈。"
        assistant_message = make_assistant_message(answer, request.decision_id)
        history.append(assistant_message)
        save_session(session_id, history)
        return TeacherFeedbackResponse(session_id=session_id, intent="clarify", answer=answer, history=history)

    action = parse_requested_action(request.message)
    if action is not None:
        updated_decision = apply_teacher_action(decision, action, request.message)
        answer = build_update_answer(updated_decision)
        assistant_message = make_assistant_message(answer, updated_decision.decision_id)
        history.append(assistant_message)
        save_session(session_id, history)
        return TeacherFeedbackResponse(
            session_id=session_id,
            intent="modify",
            answer=answer,
            history=history,
            updated_decision=updated_decision,
        )

    answer = build_explanation(decision)
    assistant_message = make_assistant_message(answer, decision.decision_id)
    history.append(assistant_message)
    save_session(session_id, history)
    return TeacherFeedbackResponse(
        session_id=session_id,
        intent="explain",
        answer=answer,
        history=history,
    )


def parse_requested_action(message: str) -> IntegrationAction | None:
    normalized = normalize_message(message)
    has_edit_verb = any(keyword in normalized for keyword in ["改为", "修改", "调整", "设为", "改成", "标记为"])
    asks_reason = any(keyword in normalized for keyword in ["为什么", "为何", "原因", "依据", "解释"])
    if asks_reason and not any(keyword in normalized for keyword in ["改为", "修改", "调整", "设为", "改成", "标记为", "拆分", "取消", "不要"]):
        return None
    if any(keyword in normalized for keyword in ["拆分", "取消合并", "不要合并", "改为保留", "改成保留", "设为保留"]):
        return "keep"
    if any(keyword in normalized for keyword in ["改为移除", "改成移除", "设为移除", "删除", "移除", "去掉"]):
        return "remove"
    if any(keyword in normalized for keyword in ["改为合并", "改成合并", "设为合并"]):
        return "merge"
    if not asks_reason and normalized.startswith("保留"):
        return "keep"
    if not asks_reason and normalized.startswith("合并"):
        return "merge"
    if has_edit_verb and "保留" in normalized:
        return "keep"
    if has_edit_verb and "合并" in normalized:
        return "merge"
    return None


def apply_teacher_action(
    decision: IntegrationDecision,
    action: IntegrationAction,
    teacher_message: str,
) -> IntegrationDecision:
    reason = build_manual_reason(decision, action, teacher_message)
    return update_decision(
        decision.decision_id,
        IntegrationDecisionPatch(action=action, reason=reason, confidence=min(decision.confidence, 0.86)),
    )


def build_explanation(decision: IntegrationDecision) -> str:
    node = decision.result_node
    source = source_label(decision)
    return "\n".join(
        [
            f"当前决策为“{action_label(decision.action)}”，置信度 {round(decision.confidence * 100)}%。",
            f"决策原因：{decision.reason}",
            f"结果节点：{node.name}。定义依据：{node.definition}",
            f"原文证据：{short_text(node.source_text)}",
            f"教材出处：{source}",
        ]
    )


def build_manual_reason(decision: IntegrationDecision, action: IntegrationAction, teacher_message: str) -> str:
    source = source_label(decision)
    return (
        f"教师反馈“{short_text(teacher_message, 80)}”将决策调整为“{action_label(action)}”。"
        f"调整仍保留原决策证据：{decision.reason}；"
        f"节点定义依据为“{short_text(decision.result_node.definition, 120)}”；"
        f"原文证据为“{short_text(decision.result_node.source_text, 140)}”；"
        f"出处：{source}。"
    )


def build_update_answer(decision: IntegrationDecision) -> str:
    return "\n".join(
        [
            f"已将决策 {decision.decision_id} 调整为“{action_label(decision.action)}”。",
            f"更新后的理由：{decision.reason}",
            f"可追溯出处：{source_label(decision)}",
        ]
    )


def source_label(decision: IntegrationDecision) -> str:
    node = decision.result_node
    textbooks = " / ".join(node.textbook_titles) or "未知教材"
    chapters = " / ".join(node.chapters[:3]) or "未知章节"
    pages = "、".join(f"第 {page} 页" for page in node.pages[:5]) or "页码未知"
    return f"[{textbooks}, {chapters}, {pages}]"


def make_assistant_message(content: str, decision_id: str | None) -> ChatMessage:
    return ChatMessage(
        message_id=f"msg_{uuid4().hex[:10]}",
        role="assistant",
        content=content,
        decision_id=decision_id,
        created_at=datetime.utcnow(),
    )


def get_sessions() -> SessionStore:
    global _sessions
    if _sessions is None:
        _sessions = load_sessions()
    return _sessions


def save_session(session_id: str, history: list[ChatMessage]) -> None:
    sessions = get_sessions()
    sessions[session_id] = history
    save_sessions(sessions)


def load_sessions() -> SessionStore:
    path = chat_store_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        session_id: [ChatMessage.model_validate(message) for message in messages]
        for session_id, messages in raw.items()
        if isinstance(messages, list)
    }


def save_sessions(sessions: SessionStore) -> None:
    path = chat_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        session_id: [message.model_dump(mode="json") for message in messages]
        for session_id, messages in sessions.items()
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def chat_store_path() -> Path:
    return Path(os.getenv("CHAT_STORE_PATH", "data/processed/chat_sessions.json"))


def normalize_message(message: str) -> str:
    return re.sub(r"\s+", "", message.lower())


def short_text(value: str, max_length: int = 160) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    return text if len(text) <= max_length else f"{text[:max_length]}..."


def action_label(action: IntegrationAction) -> str:
    if action == "merge":
        return "合并"
    if action == "remove":
        return "移除"
    return "保留"
