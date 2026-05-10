import os
import re
from pathlib import Path
from uuid import uuid4

from app.models.schemas import GraphData, KnowledgeEdge, KnowledgeNode
from app.services.textbook_store import TextbookStore

CATEGORY_KEYWORDS = {
    "解剖结构": ["骨", "肌", "血管", "神经", "器官", "组织", "膜", "腔", "解剖"],
    "生理功能": ["功能", "代谢", "分泌", "吸收", "调节", "反馈", "电位", "收缩"],
    "病理变化": ["炎症", "坏死", "凋亡", "增生", "萎缩", "水肿", "充血", "血栓"],
    "微生物": ["细菌", "病毒", "真菌", "寄生虫", "感染", "免疫", "抗体", "疫苗"],
    "核心概念": ["定义", "机制", "原理", "过程", "系统", "网络", "通路", "级联"],
}


def _best_category(text: str) -> str:
    text_lower = text.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return cat
    return "核心概念"


def _mock_extract_nodes(chapters: list[dict], textbook_id: str, textbook_title: str) -> list[KnowledgeNode]:
    nodes = []
    for ch in chapters:
        title = ch.get("title", "")
        content = (ch.get("content") or "").strip()
        page_start = ch.get("page_start", 0)

        if not content:
            continue

        # Try English capital-letter medical terms first
        term_pattern = re.compile(r"[A-Z][A-Za-z·]+(?:病|症|综合征|炎|癌|素|酶|体|原)")
        found_terms = list(dict.fromkeys(term_pattern.findall(content)))[:6]

        for term in found_terms:
            idx = content.find(term)
            start = max(0, idx - 100)
            end = min(len(content), idx + 150)
            window = content[start:end].strip()
            node_id = f"{textbook_id}_node_{len(nodes) + 1:03d}"
            nodes.append(KnowledgeNode(
                id=node_id,
                name=term,
                definition=window[:120] + ("..." if len(window) > 120 else ""),
                category=_best_category(content),
                textbook_id=textbook_id,
                textbook_title=textbook_title,
                chapter=title,
                page=page_start,
                source_text=window,
                frequency=1,
            ))

        # Fallback: extract Chinese 2-4 char meaningful words
        if len(found_terms) == 0:
            chinese_words = re.findall(r"[\u4e00-\u9fff]{2,4}", content)
            seen, words = set(), []
            for w in chinese_words:
                if w not in seen and len(words) < 4:
                    seen.add(w)
                    words.append(w)

            for word in words:
                node_id = f"{textbook_id}_node_{len(nodes) + 1:03d}"
                nodes.append(KnowledgeNode(
                    id=node_id,
                    name=word,
                    definition=f"来自{title}的关键概念",
                    category=_best_category(content),
                    textbook_id=textbook_id,
                    textbook_title=textbook_title,
                    chapter=title,
                    page=page_start,
                    source_text=f"{title}：{content[:80]}",
                    frequency=1,
                ))

    return nodes


def _build_mock_edges(nodes: list[KnowledgeNode]) -> list[KnowledgeEdge]:
    edges = []
    for i in range(len(nodes)):
        for j in range(i + 1, min(i + 3, len(nodes))):
            rel_type = ["prerequisite", "parallel", "contains", "applies_to"][(i + j) % 4]
            edges.append(KnowledgeEdge(
                id=f"edge_{len(edges) + 1:03d}",
                source=nodes[i].id,
                target=nodes[j].id,
                relation_type=rel_type,
                confidence=0.5 + (i % 3) * 0.15,
            ))
    return edges


class GraphStore:
    def __init__(self, textbook_store: TextbookStore) -> None:
        self._graphs: dict[str, GraphData] = {}
        self._textbook_store = textbook_store

    def build_graph(self, textbook_id: str) -> GraphData | None:
        textbook = self._textbook_store.get_textbook(textbook_id)
        if textbook is None:
            return None

        chapters = [
            {"title": ch.title, "content": ch.content, "page_start": ch.page_start}
            for ch in textbook.chapters
        ]

        nodes = _mock_extract_nodes(chapters, textbook_id, textbook.title)
        edges = _build_mock_edges(nodes)

        graph = GraphData(
            textbook_id=textbook_id,
            nodes=nodes,
            edges=edges,
            total_nodes=len(nodes),
            total_edges=len(edges),
        )
        self._graphs[textbook_id] = graph
        return graph

    def get_graph(self, textbook_id: str) -> GraphData | None:
        return self._graphs.get(textbook_id)