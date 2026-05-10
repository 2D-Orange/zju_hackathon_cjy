import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.models.schemas import (
    Chapter,
    GraphBuildMode,
    GraphResponse,
    GraphRelationType,
    GraphStats,
    KnowledgeEdge,
    KnowledgeNode,
    KnowledgeOccurrence,
    TextbookDetail,
)


SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[。！？；;])\s*|\n+")
SOURCE_TRIGGER_PATTERN = re.compile(r"(是指|称为|称|又称|定义为|包括|分为|可分为|由.+?组成|构成)")
APPLIES_TRIGGER_PATTERN = re.compile(r"(用于|应用于|适用于|作用于|参与|调节|影响|导致|引起|发生于|表现为)")
KEYWORD_PATTERN = re.compile(
    r"[A-Za-z0-9α-ωΑ-Ω一-龥（）()·]{1,18}?"
    r"(?:系统|组织|细胞|病毒|细菌|真菌|器官|功能|病变|炎症|感染|反应|结构|疾病|综合征|"
    r"代谢|循环|神经|免疫|机制|过程|分类|作用|治疗|诊断|症状|体征|损伤因子|因子|蛋白|受体|"
    r"激素|酶|病原体|抗体|血管|淋巴|"
    r"癌|瘤|血症|缺陷|损伤|坏死|水肿|休克|发热|缺氧)"
)

RELATION_LABELS: dict[GraphRelationType, str] = {
    "prerequisite": "先修",
    "parallel": "并列",
    "contains": "包含",
    "applies_to": "应用于",
}

TERM_STOPWORDS = {
    "本章",
    "本节",
    "教材",
    "内容",
    "概述",
    "主要",
    "一般",
    "正常",
    "异常",
    "临床",
    "基础",
    "学习",
    "掌握",
    "了解",
    "熟悉",
    "作用",
    "过程",
    "功能",
    "结构",
}


@dataclass
class ConceptCandidate:
    name: str
    definition: str
    category: str
    textbook_id: str
    textbook_title: str
    chapter_id: str
    chapter: str
    page: int
    source_text: str
    position: int


def build_knowledge_graph(
    textbooks: list[TextbookDetail],
    mode: GraphBuildMode = "auto",
    max_nodes_per_chapter: int = 8,
) -> GraphResponse:
    """Build a traceable graph from parsed chapter text only."""
    graph_id = make_graph_id([textbook.textbook_id for textbook in textbooks])
    requested_mode = resolve_requested_mode(mode)
    used_mode: GraphBuildMode = "mock"
    nodes_by_key: dict[tuple[str, str], KnowledgeNode] = {}
    chapter_node_ids: dict[tuple[str, str], list[str]] = {}
    node_positions: dict[tuple[str, str], int] = {}
    evidence_sentences: dict[tuple[str, str], list[str]] = {}

    for textbook in textbooks:
        for chapter in textbook.chapters:
            if not chapter.content.strip():
                continue

            candidates: list[ConceptCandidate] = []
            if requested_mode == "llm":
                candidates = extract_with_llm(textbook, chapter, max_nodes_per_chapter)
                if candidates:
                    used_mode = "llm"

            if not candidates:
                candidates = extract_with_mock(textbook, chapter, max_nodes_per_chapter)

            for candidate in candidates:
                key = (candidate.textbook_id, normalize_key(candidate.name))
                if not key[1]:
                    continue

                occurrence = KnowledgeOccurrence(
                    chapter_id=candidate.chapter_id,
                    chapter=candidate.chapter,
                    page=candidate.page,
                    source_text=candidate.source_text,
                )
                if key not in nodes_by_key:
                    node = KnowledgeNode(
                        id=make_node_id(candidate.textbook_id, candidate.name),
                        name=candidate.name,
                        definition=candidate.definition,
                        category=candidate.category,
                        textbook_id=candidate.textbook_id,
                        textbook_title=candidate.textbook_title,
                        chapter_id=candidate.chapter_id,
                        chapter=candidate.chapter,
                        page=candidate.page,
                        source_text=candidate.source_text,
                        frequency=1,
                        occurrences=[occurrence],
                    )
                    nodes_by_key[key] = node
                else:
                    node = nodes_by_key[key]
                    node.frequency += 1
                    if len(node.occurrences) < 8 and occurrence.source_text not in {
                        item.source_text for item in node.occurrences
                    }:
                        node.occurrences.append(occurrence)

                chapter_key = (candidate.textbook_id, candidate.chapter_id)
                chapter_node_ids.setdefault(chapter_key, [])
                if nodes_by_key[key].id not in chapter_node_ids[chapter_key]:
                    chapter_node_ids[chapter_key].append(nodes_by_key[key].id)
                position_key = (candidate.chapter_id, nodes_by_key[key].id)
                node_positions[position_key] = min(
                    node_positions.get(position_key, candidate.position),
                    candidate.position,
                )
                evidence_sentences.setdefault((candidate.chapter_id, nodes_by_key[key].id), [])
                if candidate.source_text not in evidence_sentences[(candidate.chapter_id, nodes_by_key[key].id)]:
                    evidence_sentences[(candidate.chapter_id, nodes_by_key[key].id)].append(candidate.source_text)

    nodes = sorted(nodes_by_key.values(), key=lambda item: (item.textbook_title, item.chapter_id, item.name))
    edges = build_edges(nodes, chapter_node_ids, node_positions, evidence_sentences)
    relation_types = sorted({edge.relation_type for edge in edges})

    return GraphResponse(
        graph_id=graph_id,
        textbook_ids=[textbook.textbook_id for textbook in textbooks],
        nodes=nodes,
        edges=edges,
        stats=GraphStats(
            textbook_count=len(textbooks),
            node_count=len(nodes),
            edge_count=len(edges),
            relation_types=relation_types,
        ),
        build_mode=used_mode,
    )


def resolve_requested_mode(mode: GraphBuildMode) -> GraphBuildMode:
    if mode == "auto":
        configured = os.getenv("GRAPH_EXTRACTOR_MODE", "mock").lower()
        if configured == "llm" and is_llm_configured():
            return "llm"
        return "mock"
    if mode == "llm" and is_llm_configured():
        return "llm"
    return "mock"


def is_llm_configured() -> bool:
    return bool(os.getenv("GRAPH_LLM_API_KEY") and os.getenv("GRAPH_LLM_BASE_URL") and os.getenv("GRAPH_LLM_MODEL"))


def extract_with_llm(
    textbook: TextbookDetail,
    chapter: Chapter,
    max_nodes_per_chapter: int,
) -> list[ConceptCandidate]:
    base_url = os.getenv("GRAPH_LLM_BASE_URL", "").rstrip("/")
    api_key = os.getenv("GRAPH_LLM_API_KEY", "")
    model = os.getenv("GRAPH_LLM_MODEL", "")
    if not base_url or not api_key or not model:
        return []

    prompt = (
        "你是医学教材知识图谱抽取器。只允许从给定章节原文抽取知识点。"
        "返回 JSON 数组，每项包含 name、definition、category、source_text。"
        "source_text 必须是原文中的连续片段；definition 必须是原文摘录或基于 source_text 的短摘录，不能引入外部医学常识。"
        f"最多返回 {max_nodes_per_chapter} 个知识点。\n\n"
        f"教材：{textbook.title}\n章节：{chapter.title}\n原文：\n{chapter.content[:6000]}"
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
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
        return []

    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return []

    if isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict):
        items = parsed.get("nodes", [])
    else:
        items = []
    if not isinstance(items, list):
        return []

    candidates: list[ConceptCandidate] = []
    for index, item in enumerate(items[:max_nodes_per_chapter]):
        if not isinstance(item, dict):
            continue
        source_text = normalize_source_text(str(item.get("source_text", "")))
        name = clean_term(str(item.get("name", "")))
        if not source_text or source_text not in chapter.content or not name:
            continue
        candidates.append(
            ConceptCandidate(
                name=name,
                definition=truncate_text(str(item.get("definition") or source_text), 180),
                category=truncate_text(str(item.get("category") or classify_term(name, source_text)), 24),
                textbook_id=textbook.textbook_id,
                textbook_title=textbook.title,
                chapter_id=chapter.chapter_id,
                chapter=chapter.title,
                page=chapter.page_start,
                source_text=truncate_text(source_text, 220),
                position=index,
            )
        )
    return candidates


def extract_with_mock(
    textbook: TextbookDetail,
    chapter: Chapter,
    max_nodes_per_chapter: int,
) -> list[ConceptCandidate]:
    sentences = split_sentences(chapter.content)
    if not sentences:
        return []

    ranked: dict[str, ConceptCandidate] = {}
    scores: dict[str, int] = {}
    chapter_topic = clean_chapter_title(chapter.title)
    topic_source = sentences[0][1]
    if chapter_topic:
        key = normalize_key(chapter_topic)
        ranked[key] = make_candidate(
            chapter_topic,
            "章节主题",
            topic_source,
            textbook,
            chapter,
            position=0,
        )
        scores[key] = 7

    for position, sentence in sentences:
        if len(ranked) > max_nodes_per_chapter * 4:
            break
        terms = extract_terms(sentence)
        for term in terms:
            key = normalize_key(term)
            if not key:
                continue
            category = classify_term(term, sentence)
            score = 4 if SOURCE_TRIGGER_PATTERN.search(sentence) else 2
            score += min(sentence.count(term), 2)
            if key not in ranked:
                ranked[key] = make_candidate(term, category, sentence, textbook, chapter, position)
                scores[key] = score
            else:
                scores[key] += score

    ordered = sorted(
        ranked.values(),
        key=lambda item: (-scores.get(normalize_key(item.name), 0), item.position, len(item.name)),
    )
    return ordered[:max_nodes_per_chapter]


def make_candidate(
    term: str,
    category: str,
    source_text: str,
    textbook: TextbookDetail,
    chapter: Chapter,
    position: int,
) -> ConceptCandidate:
    evidence = truncate_text(normalize_source_text(source_text), 220)
    return ConceptCandidate(
        name=term,
        definition=truncate_text(evidence, 180),
        category=category,
        textbook_id=textbook.textbook_id,
        textbook_title=textbook.title,
        chapter_id=chapter.chapter_id,
        chapter=chapter.title,
        page=chapter.page_start,
        source_text=evidence,
        position=position,
    )


def build_edges(
    nodes: list[KnowledgeNode],
    chapter_node_ids: dict[tuple[str, str], list[str]],
    node_positions: dict[tuple[str, str], int],
    evidence_sentences: dict[tuple[str, str], list[str]],
) -> list[KnowledgeEdge]:
    node_by_id = {node.id: node for node in nodes}
    edge_keys: set[tuple[str, str, GraphRelationType]] = set()
    edges: list[KnowledgeEdge] = []

    def add_edge(source_id: str, target_id: str, relation_type: GraphRelationType, source_text: str) -> None:
        if source_id == target_id:
            return
        key = (source_id, target_id, relation_type)
        if key in edge_keys:
            return
        source = node_by_id.get(source_id)
        target = node_by_id.get(target_id)
        if not source or not target:
            return
        edge_keys.add(key)
        edges.append(
            KnowledgeEdge(
                id=f"edge_{len(edges) + 1:04d}",
                source=source_id,
                target=target_id,
                relation_type=relation_type,
                label=RELATION_LABELS[relation_type],
                weight=1.0,
                textbook_id=source.textbook_id,
                textbook_title=source.textbook_title,
                chapter=source.chapter,
                page=source.page,
                source_text=truncate_text(source_text, 260),
            )
        )

    for (_textbook_id, chapter_id), node_ids in chapter_node_ids.items():
        sorted_ids = sorted(
            node_ids,
            key=lambda node_id: (
                0 if node_by_id[node_id].category == "章节主题" else 1,
                node_positions.get((chapter_id, node_id), 9999),
            ),
        )
        if len(sorted_ids) < 2:
            continue

        topic_ids = [node_id for node_id in sorted_ids if node_by_id[node_id].category == "章节主题"]
        term_ids = [node_id for node_id in sorted_ids if node_by_id[node_id].category != "章节主题"]
        if topic_ids:
            topic_id = topic_ids[0]
            for target_id in term_ids[:8]:
                add_edge(topic_id, target_id, "contains", node_by_id[target_id].source_text)

        ordered_terms = term_ids[:8]
        for source_id, target_id in zip(ordered_terms, ordered_terms[1:]):
            source_text = combine_evidence(
                evidence_sentences.get((chapter_id, source_id), []),
                evidence_sentences.get((chapter_id, target_id), []),
            )
            add_edge(source_id, target_id, "prerequisite", source_text)

        grouped: dict[str, list[str]] = {}
        for node_id in ordered_terms:
            grouped.setdefault(node_by_id[node_id].category, []).append(node_id)
        parallel_count = 0
        for ids in grouped.values():
            for source_id, target_id in zip(ids, ids[1:]):
                source_text = combine_evidence(
                    evidence_sentences.get((chapter_id, source_id), []),
                    evidence_sentences.get((chapter_id, target_id), []),
                )
                add_edge(source_id, target_id, "parallel", source_text)
                parallel_count += 1
                if parallel_count >= 4:
                    break
            if parallel_count >= 4:
                break
        if parallel_count == 0 and len(ordered_terms) >= 2:
            add_edge(
                ordered_terms[0],
                ordered_terms[1],
                "parallel",
                combine_evidence(
                    evidence_sentences.get((chapter_id, ordered_terms[0]), []),
                    evidence_sentences.get((chapter_id, ordered_terms[1]), []),
                ),
            )

        for source_id in ordered_terms:
            source_node = node_by_id[source_id]
            if not APPLIES_TRIGGER_PATTERN.search(source_node.source_text):
                continue
            for target_id in ordered_terms:
                if target_id != source_id and node_by_id[target_id].name in source_node.source_text:
                    add_edge(source_id, target_id, "applies_to", source_node.source_text)
                    break

    return edges


def extract_terms(sentence: str) -> list[str]:
    terms: list[str] = []
    definition_match = re.search(
        r"([A-Za-z0-9α-ωΑ-Ω一-龥（）()·、，,的]{2,36}?)(?:是指|是|指|称为|称|又称|定义为)",
        sentence,
    )
    if definition_match:
        terms.append(definition_match.group(1))

    contains_match = re.search(r"([A-Za-z0-9α-ωΑ-Ω一-龥（）()·、，,的]{2,36}?)(?:包括|分为|可分为|分成|构成|组成)", sentence)
    if contains_match:
        terms.append(contains_match.group(1))

    for keyword in KEYWORD_PATTERN.findall(sentence):
        terms.append(keyword)

    for acronym in re.findall(r"\b[A-Z][A-Za-z0-9-]{2,}\b", sentence):
        terms.append(acronym)

    cleaned: list[str] = []
    seen: set[str] = set()
    for term in terms:
        normalized = clean_term(term)
        key = normalize_key(normalized)
        if key and key not in seen:
            seen.add(key)
            cleaned.append(normalized)
    return cleaned[:5]


def clean_term(term: str) -> str:
    normalized = normalize_source_text(term)
    normalized = re.split(r"[，,；;。:：、\s]", normalized)[-1]
    if len(normalized) > 8 or re.search(r"(是指|称为|包括|分为|具有|由于|以及|对|于|用于|应用于|参与|作用于|并|的)", normalized):
        parts = re.split(r"(?:是指|称为|又称|定义为|包括|分为|可分为|具有|由于|以及|对|于|用于|应用于|参与|作用于|并|的)", normalized)
        normalized = next((part for part in reversed(parts) if part), normalized)
    normalized = re.sub(
        r"^(?:此外|其中|因此|故|即|如|例如|所谓|这|此|其|该|上述|下列|主要|各种|所发生的|发生的|产生的|进行的|出现的|重要|基本)",
        "",
        normalized,
    )
    normalized = normalized.strip("（）()[]【】《》“”\"'：:，,。；;、")
    normalized = re.sub(r"^(第[一二三四五六七八九十百千万零〇两\d]+[章节篇])", "", normalized).strip()
    normalized = normalized.rstrip("的是和与及或、")
    if len(normalized) < 2 or len(normalized) > 24:
        return ""
    if normalized in TERM_STOPWORDS or normalized.isdigit():
        return ""
    return normalized


def clean_chapter_title(title: str) -> str:
    normalized = normalize_source_text(title)
    normalized = re.sub(r"^第\s*[一二三四五六七八九十百千万零〇两\d]+\s*[章节篇]\s*", "", normalized)
    normalized = normalized.strip(" ：:-")
    return normalized[:24] if len(normalized) >= 2 else ""


def classify_term(term: str, sentence: str) -> str:
    if SOURCE_TRIGGER_PATTERN.search(sentence):
        return "核心概念"
    if any(token in term for token in ("病", "炎", "感染", "癌", "瘤", "综合征", "休克", "水肿", "缺氧")):
        return "疾病病理"
    if any(token in term for token in ("细胞", "组织", "器官", "血管", "神经", "膜", "肌", "骨")):
        return "结构组织"
    if any(token in term for token in ("功能", "机制", "反应", "代谢", "循环", "免疫", "调节", "作用")):
        return "功能机制"
    if APPLIES_TRIGGER_PATTERN.search(sentence):
        return "临床应用"
    return "知识点"


def split_sentences(content: str) -> list[tuple[int, str]]:
    sentences: list[tuple[int, str]] = []
    cursor = 0
    for part in SENTENCE_SPLIT_PATTERN.split(content):
        sentence = normalize_source_text(part)
        if not sentence:
            cursor += len(part)
            continue
        if 6 <= len(sentence) <= 240:
            sentences.append((cursor, sentence))
        cursor += len(part)
    return sentences


def normalize_source_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def normalize_key(term: str) -> str:
    return re.sub(r"[\s（）()《》“”\"'、，,。:：；;-]", "", term).lower()


def truncate_text(text: str, max_length: int) -> str:
    normalized = normalize_source_text(text)
    return normalized if len(normalized) <= max_length else f"{normalized[: max_length - 1]}…"


def combine_evidence(left: list[str], right: list[str]) -> str:
    snippets = []
    for item in [*left[:1], *right[:1]]:
        if item and item not in snippets:
            snippets.append(item)
    return " / ".join(snippets)


def make_graph_id(textbook_ids: list[str]) -> str:
    joined = "_".join(sorted(textbook_ids)) or "empty"
    digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()[:10]
    return f"graph_{digest}"


def make_node_id(textbook_id: str, name: str) -> str:
    digest = hashlib.sha1(f"{textbook_id}:{name}".encode("utf-8")).hexdigest()[:10]
    return f"{textbook_id}_node_{digest}"
