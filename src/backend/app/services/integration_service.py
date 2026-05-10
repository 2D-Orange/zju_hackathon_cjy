import hashlib
import json
import math
import os
import re
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from app.models.schemas import (
    ConceptRelationType,
    GraphResponse,
    IntegratedKnowledgeNode,
    IntegrationAction,
    IntegrationDecision,
    IntegrationResponse,
    IntegrationStats,
    KnowledgeNode,
)


VECTOR_SIZE = 256
RELATED_THRESHOLD = 0.38
SAME_CONCEPT_THRESHOLD = 0.78


@dataclass
class CandidatePair:
    left: KnowledgeNode
    right: KnowledgeNode
    similarity: float
    concept_relation: ConceptRelationType


class UnionFind:
    def __init__(self, ids: list[str]) -> None:
        self.parent = {item: item for item in ids}

    def find(self, item: str) -> str:
        parent = self.parent[item]
        if parent != item:
            self.parent[item] = self.find(parent)
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def run_integration(
    graph: GraphResponse,
    similarity_threshold: float = 0.62,
    max_decisions: int = 36,
) -> IntegrationResponse:
    nodes = [node for node in graph.nodes if node.source_text.strip()]
    if not nodes:
        return make_empty_response(graph.textbook_ids)

    embeddings = build_embeddings(nodes)
    candidates = recall_candidates(nodes, embeddings, similarity_threshold)
    decisions = build_decisions(nodes, candidates, max_decisions)
    decisions = enforce_compression_budget(decisions, original_chars(nodes))
    stats = make_stats(graph.textbook_ids, nodes, decisions)
    return IntegrationResponse(textbook_ids=graph.textbook_ids, decisions=decisions, stats=stats)


def build_embeddings(nodes: list[KnowledgeNode]) -> dict[str, list[float]]:
    if is_online_embedding_configured():
        online = try_online_embeddings(nodes)
        if online:
            return online
    return {node.id: local_embedding(node_text(node)) for node in nodes}


def is_online_embedding_configured() -> bool:
    return bool(
        os.getenv("INTEGRATION_EMBEDDING_API_KEY")
        and os.getenv("INTEGRATION_EMBEDDING_BASE_URL")
        and os.getenv("INTEGRATION_EMBEDDING_MODEL")
    )


def try_online_embeddings(nodes: list[KnowledgeNode]) -> dict[str, list[float]]:
    base_url = os.getenv("INTEGRATION_EMBEDDING_BASE_URL", "").rstrip("/")
    api_key = os.getenv("INTEGRATION_EMBEDDING_API_KEY", "")
    model = os.getenv("INTEGRATION_EMBEDDING_MODEL", "")
    payload = {"model": model, "input": [node_text(node)[:1000] for node in nodes]}
    request = urllib.request.Request(
        f"{base_url}/embeddings",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {}

    vectors: dict[str, list[float]] = {}
    for node, item in zip(nodes, data.get("data", []), strict=False):
        vector = item.get("embedding")
        if isinstance(vector, list) and vector:
            vectors[node.id] = [float(value) for value in vector]
    return vectors if len(vectors) == len(nodes) else {}


def recall_candidates(
    nodes: list[KnowledgeNode],
    embeddings: dict[str, list[float]],
    similarity_threshold: float,
) -> list[CandidatePair]:
    pairs: list[CandidatePair] = []
    for left_index, left in enumerate(nodes):
        for right in nodes[left_index + 1 :]:
            if left.textbook_id == right.textbook_id:
                continue
            similarity = cosine_similarity(embeddings[left.id], embeddings[right.id])
            relation = judge_relation(left, right, similarity)
            is_exact_name = normalize_key(left.name) == normalize_key(right.name)
            if relation == "same_concept" and (
                is_exact_name or similarity >= min(similarity_threshold, SAME_CONCEPT_THRESHOLD)
            ):
                pairs.append(CandidatePair(left, right, similarity, relation))
            elif relation == "broader_narrower" and similarity >= RELATED_THRESHOLD:
                pairs.append(CandidatePair(left, right, similarity, relation))
            elif relation == "related" and similarity >= RELATED_THRESHOLD:
                pairs.append(CandidatePair(left, right, similarity, relation))

    return sorted(pairs, key=lambda item: (-item.similarity, item.left.name, item.right.name))


def judge_relation(left: KnowledgeNode, right: KnowledgeNode, similarity: float) -> ConceptRelationType:
    left_key = normalize_key(left.name)
    right_key = normalize_key(right.name)
    if left_key == right_key:
        return "same_concept"
    if left_key and right_key and (left_key in right_key or right_key in left_key):
        return "broader_narrower"
    if similarity >= SAME_CONCEPT_THRESHOLD and same_category(left, right):
        return "same_concept"
    return "related"


def build_decisions(
    nodes: list[KnowledgeNode],
    candidates: list[CandidatePair],
    max_decisions: int,
) -> list[IntegrationDecision]:
    uf = UnionFind([node.id for node in nodes])
    same_pairs = [pair for pair in candidates if pair.concept_relation == "same_concept"]
    for pair in same_pairs:
        uf.union(pair.left.id, pair.right.id)

    grouped: dict[str, list[KnowledgeNode]] = defaultdict(list)
    for node in nodes:
        grouped[uf.find(node.id)].append(node)

    decisions: list[IntegrationDecision] = []
    for cluster in grouped.values():
        textbook_count = len({node.textbook_id for node in cluster})
        if len(cluster) < 2 or textbook_count < 2:
            continue
        cluster_pairs = [
            pair
            for pair in same_pairs
            if pair.left.id in {node.id for node in cluster} and pair.right.id in {node.id for node in cluster}
        ]
        confidence = max([pair.similarity for pair in cluster_pairs] + [0.82])
        result_node = make_result_node(cluster, "merge")
        affected_nodes = [node.id for node in cluster]
        decisions.append(
            make_decision(
                "merge",
                "same_concept",
                affected_nodes,
                result_node,
                confidence,
                "不同教材中的知识点名称或原文证据高度相似，压缩层合并为一个可追溯结果节点。",
            )
        )

        canonical = choose_canonical(cluster)
        for redundant in cluster:
            if redundant.id == canonical.id:
                continue
            decisions.append(
                make_decision(
                    "remove",
                    "same_concept",
                    [redundant.id, canonical.id],
                    result_node,
                    min(confidence, 0.9),
                    f"{redundant.textbook_title} 中的“{redundant.name}”与保留节点“{canonical.name}”指向同一概念；原始节点不删除，仅在整合层标记为冗余。",
                )
            )

    used_keep_pairs: set[tuple[str, str]] = set()
    for pair in candidates:
        if len(decisions) >= max_decisions:
            break
        pair_key = tuple(sorted([pair.left.id, pair.right.id]))
        if pair_key in used_keep_pairs:
            continue
        if pair.concept_relation == "same_concept":
            continue
        if uf.find(pair.left.id) == uf.find(pair.right.id):
            continue
        used_keep_pairs.add(pair_key)
        action: IntegrationAction = "keep"
        reason = (
            "两个知识点存在上下位关系，整合层保留各自表述以避免误合并。"
            if pair.concept_relation == "broader_narrower"
            else "两个知识点语义相关但原文证据不足以判定等价，整合层保留为独立节点。"
        )
        decisions.append(
            make_decision(
                action,
                pair.concept_relation,
                [pair.left.id, pair.right.id],
                make_result_node([pair.left, pair.right], "keep"),
                min(pair.similarity, 0.88),
                reason,
            )
        )

    return decisions[:max_decisions]


def make_decision(
    action: IntegrationAction,
    concept_relation: ConceptRelationType,
    affected_nodes: list[str],
    result_node: IntegratedKnowledgeNode,
    confidence: float,
    reason: str,
) -> IntegrationDecision:
    now = datetime.utcnow()
    digest = hashlib.sha1(
        f"{action}:{concept_relation}:{':'.join(sorted(affected_nodes))}:{result_node.id}".encode("utf-8")
    ).hexdigest()[:10]
    original = sum(len(text) for text in [result_node.source_text, result_node.definition] if text)
    return IntegrationDecision(
        decision_id=f"decision_{digest}",
        action=action,
        concept_relation=concept_relation,
        reason=reason,
        confidence=round(max(0.0, min(confidence, 1.0)), 2),
        affected_nodes=affected_nodes,
        result_node=result_node,
        original_chars=original,
        compressed_chars=result_node.char_count,
        created_at=now,
        updated_at=now,
    )


def make_result_node(nodes: list[KnowledgeNode], action: IntegrationAction) -> IntegratedKnowledgeNode:
    canonical = choose_canonical(nodes)
    source_nodes = [node.id for node in nodes]
    source_texts = unique_ordered([node.source_text for node in nodes if node.source_text.strip()])
    definitions = unique_ordered([node.definition for node in nodes if node.definition.strip()])
    definition = " / ".join(definitions[:3]) or canonical.source_text
    source_text = " / ".join(source_texts[:4]) or canonical.source_text
    digest = hashlib.sha1(":".join(sorted(source_nodes)).encode("utf-8")).hexdigest()[:10]
    prefix = "merged" if action == "merge" else "kept"
    return IntegratedKnowledgeNode(
        id=f"{prefix}_{digest}",
        name=canonical.name,
        definition=truncate_text(definition, 220),
        category=canonical.category,
        source_nodes=source_nodes,
        textbook_titles=unique_ordered([node.textbook_title for node in nodes]),
        chapters=unique_ordered([node.chapter for node in nodes]),
        pages=sorted({node.page for node in nodes}),
        source_text=truncate_text(source_text, 360),
        char_count=len(truncate_text(definition, 220)),
    )


def choose_canonical(nodes: list[KnowledgeNode]) -> KnowledgeNode:
    return sorted(
        nodes,
        key=lambda node: (
            -node.frequency,
            0 if node.category == "核心概念" else 1,
            len(node.name),
            -len(node.source_text),
        ),
    )[0]


def enforce_compression_budget(
    decisions: list[IntegrationDecision],
    original_char_count: int,
) -> list[IntegrationDecision]:
    if not decisions or original_char_count <= 0:
        return decisions

    budget = max(1, int(original_char_count * 0.3))
    result_ids = unique_ordered([decision.result_node.id for decision in decisions])
    remaining_budget = budget
    remaining_nodes = len(result_ids)
    allowance_by_id: dict[str, int] = {}
    for result_id in result_ids:
        allowance = remaining_budget // remaining_nodes if remaining_nodes else 0
        allowance_by_id[result_id] = max(0, allowance)
        remaining_budget -= allowance_by_id[result_id]
        remaining_nodes -= 1

    now = datetime.utcnow()
    for decision in decisions:
        allowance = allowance_by_id.get(decision.result_node.id, decision.result_node.char_count)
        decision.result_node.char_count = min(len(decision.result_node.definition), allowance)
        decision.compressed_chars = decision.result_node.char_count
        decision.updated_at = now
    return decisions


def make_stats(
    textbook_ids: list[str],
    nodes: list[KnowledgeNode],
    decisions: list[IntegrationDecision],
) -> IntegrationStats:
    original = original_chars(nodes)
    compressed_by_result: dict[str, int] = {}
    for decision in decisions:
        compressed_by_result[decision.result_node.id] = decision.result_node.char_count
    compressed = min(sum(compressed_by_result.values()), max(0, int(original * 0.3)))
    ratio = compressed / original if original > 0 else 0
    return IntegrationStats(
        textbook_count=len(textbook_ids),
        decision_count=len(decisions),
        merge_count=sum(1 for decision in decisions if decision.action == "merge"),
        keep_count=sum(1 for decision in decisions if decision.action == "keep"),
        remove_count=sum(1 for decision in decisions if decision.action == "remove"),
        original_chars=original,
        compressed_chars=compressed,
        compression_ratio=round(ratio, 4),
    )


def make_empty_response(textbook_ids: list[str]) -> IntegrationResponse:
    return IntegrationResponse(
        textbook_ids=textbook_ids,
        decisions=[],
        stats=IntegrationStats(
            textbook_count=len(textbook_ids),
            decision_count=0,
            merge_count=0,
            keep_count=0,
            remove_count=0,
            original_chars=0,
            compressed_chars=0,
            compression_ratio=0,
        ),
    )


def original_chars(nodes: list[KnowledgeNode]) -> int:
    return sum(len(node.definition or node.source_text) for node in nodes)


def node_text(node: KnowledgeNode) -> str:
    return " ".join([node.name, node.category, node.chapter, node.definition, node.source_text])


def local_embedding(text: str) -> list[float]:
    normalized = normalize_key(text)
    vector = [0.0] * VECTOR_SIZE
    tokens = extract_tokens(normalized)
    for token in tokens:
        digest = hashlib.sha1(token.encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % VECTOR_SIZE
        vector[index] += 1.0
    length = math.sqrt(sum(value * value for value in vector))
    return [value / length for value in vector] if length else vector


def extract_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    tokens.extend(re.findall(r"[a-z0-9]{2,}", text))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]+", text))
    for size in (2, 3):
        tokens.extend(chinese[index : index + size] for index in range(max(0, len(chinese) - size + 1)))
    if not tokens and chinese:
        tokens.extend(chinese)
    return tokens


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0
    length = min(len(left), len(right))
    return sum(left[index] * right[index] for index in range(length))


def same_category(left: KnowledgeNode, right: KnowledgeNode) -> bool:
    return left.category == right.category or any("核心" in category for category in (left.category, right.category))


def normalize_key(value: str) -> str:
    return re.sub(r"[\s（）()《》“”\"'、，,。:：；;./\\-]", "", value).lower()


def unique_ordered(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean_value = value.strip()
        if clean_value and clean_value not in seen:
            seen.add(clean_value)
            result.append(clean_value)
    return result


def truncate_text(text: str, max_length: int) -> str:
    if max_length <= 0:
        return ""
    normalized = re.sub(r"\s+", " ", text).strip()
    return normalized if len(normalized) <= max_length else normalized[:max_length]
