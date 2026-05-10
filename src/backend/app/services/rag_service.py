import hashlib
import json
import math
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime

from app.models.schemas import (
    Chapter,
    RagChunk,
    RagCitation,
    RagIndexStatus,
    RagQueryResponse,
    RagSourceChunk,
    TextbookDetail,
)


FALLBACK_ANSWER = "当前知识库中未找到相关信息"
VECTOR_SIZE = 384


@dataclass
class RagIndex:
    textbook_ids: list[str]
    chunks: list[RagChunk]
    embeddings: dict[str, list[float]]
    embedding_mode: str
    updated_at: datetime


@dataclass
class SearchResult:
    chunk: RagChunk
    score: float


def build_rag_index(textbooks: list[TextbookDetail], chunk_size: int = 700, overlap: int = 80) -> RagIndex:
    chunks: list[RagChunk] = []
    for textbook in textbooks:
        for chapter in textbook.chapters:
            chunks.extend(split_chapter(textbook, chapter, chunk_size, overlap))

    embeddings, mode = build_embeddings([chunk.text for chunk in chunks])
    return RagIndex(
        textbook_ids=[textbook.textbook_id for textbook in textbooks],
        chunks=chunks,
        embeddings={chunk.chunk_id: embedding for chunk, embedding in zip(chunks, embeddings, strict=False)},
        embedding_mode=mode,
        updated_at=datetime.utcnow(),
    )


def split_chapter(
    textbook: TextbookDetail,
    chapter: Chapter,
    chunk_size: int = 700,
    overlap: int = 80,
) -> list[RagChunk]:
    text = normalize_text(chapter.content)
    if not text:
        return []

    chunks: list[RagChunk] = []
    start = 0
    text_length = len(text)
    while start < text_length:
        if text_length - start <= chunk_size:
            end = text_length
        elif text_length - start <= 800:
            end = text_length
        else:
            end = choose_chunk_end(text, start, chunk_size)

        chunk_text = text[start:end].strip()
        if chunk_text:
            page_start, page_end = estimate_page_range(chapter, start, end, text_length)
            digest = hashlib.sha1(
                f"{textbook.textbook_id}:{chapter.chapter_id}:{start}:{end}".encode("utf-8")
            ).hexdigest()[:10]
            chunks.append(
                RagChunk(
                    chunk_id=f"rag_{digest}",
                    textbook_id=textbook.textbook_id,
                    textbook=textbook.title,
                    chapter=chapter.title,
                    page_start=page_start,
                    page_end=page_end,
                    text=chunk_text,
                    char_count=len(chunk_text),
                )
            )

        if end >= text_length:
            break
        start = max(start + 1, end - overlap)

    return chunks


def choose_chunk_end(text: str, start: int, chunk_size: int) -> int:
    min_end = min(len(text), start + 500)
    max_end = min(len(text), start + chunk_size)
    if max_end <= min_end:
        return max_end

    window = text[min_end:max_end]
    for index in range(len(window) - 1, -1, -1):
        if window[index] in "。！？；;.\n":
            return min_end + index + 1
    return max_end


def estimate_page_range(chapter: Chapter, start: int, end: int, text_length: int) -> tuple[int, int]:
    if text_length <= 0:
        return chapter.page_start, chapter.page_end

    page_count = max(1, chapter.page_end - chapter.page_start + 1)
    start_offset = min(page_count - 1, math.floor((start / text_length) * page_count))
    end_offset = min(page_count - 1, math.floor((max(end - 1, 0) / text_length) * page_count))
    return chapter.page_start + start_offset, chapter.page_start + max(start_offset, end_offset)


def query_rag(index: RagIndex | None, question: str, top_k: int = 5, min_score: float = 0.12) -> RagQueryResponse:
    if index is None or not index.chunks:
        return RagQueryResponse(answer=FALLBACK_ANSWER)

    results = search_index(index, question, top_k)
    if not results or results[0].score < min_score:
        return RagQueryResponse(
            answer=FALLBACK_ANSWER,
            source_chunks=[make_source_chunk(result) for result in results],
        )

    supported = [result for result in results if result.score >= min_score]
    answer = try_llm_answer(question, supported) or make_extractive_answer(question, supported)
    if answer == FALLBACK_ANSWER:
        return RagQueryResponse(
            answer=FALLBACK_ANSWER,
            source_chunks=[make_source_chunk(result) for result in results],
        )

    return RagQueryResponse(
        answer=answer,
        citations=[make_citation(result) for result in supported],
        source_chunks=[make_source_chunk(result) for result in results],
    )


def search_index(index: RagIndex, question: str, top_k: int = 5) -> list[SearchResult]:
    query_vector = embed_query(question, index.embedding_mode)
    if not query_vector:
        return []

    results = [
        SearchResult(chunk=chunk, score=round(cosine_similarity(query_vector, index.embeddings[chunk.chunk_id]), 4))
        for chunk in index.chunks
        if chunk.chunk_id in index.embeddings
    ]
    return sorted(results, key=lambda item: (-item.score, item.chunk.textbook, item.chunk.chapter))[:top_k]


def build_embeddings(texts: list[str]) -> tuple[list[list[float]], str]:
    if not texts:
        return [], "local"
    if is_online_embedding_configured():
        online = try_online_embeddings(texts)
        if len(online) == len(texts):
            return online, "online"
    return [local_embedding(text) for text in texts], "local"


def embed_query(question: str, embedding_mode: str) -> list[float]:
    if embedding_mode == "online" and is_online_embedding_configured():
        online = try_online_embeddings([question])
        if online:
            return online[0]
    return local_embedding(question)


def is_online_embedding_configured() -> bool:
    return bool(get_env("RAG_EMBEDDING_BASE_URL", "EMBEDDING_BASE_URL", "LLM_BASE_URL") and get_embedding_model())


def try_online_embeddings(texts: list[str]) -> list[list[float]]:
    base_url = get_env("RAG_EMBEDDING_BASE_URL", "EMBEDDING_BASE_URL", "LLM_BASE_URL").rstrip("/")
    model = get_embedding_model()
    api_key = get_env("RAG_EMBEDDING_API_KEY", "EMBEDDING_API_KEY", "LLM_API_KEY")
    payload = {"model": model, "input": [text[:1200] for text in texts]}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        f"{base_url}/embeddings",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return []

    vectors: list[list[float]] = []
    for item in data.get("data", []):
        vector = item.get("embedding")
        if not isinstance(vector, list) or not vector:
            return []
        vectors.append([float(value) for value in vector])
    return vectors


def get_embedding_model() -> str:
    return get_env("RAG_EMBEDDING_MODEL", "EMBEDDING_MODEL")


def local_embedding(text: str) -> list[float]:
    vector = [0.0] * VECTOR_SIZE
    tokens = extract_tokens(text)
    for token in tokens:
        digest = hashlib.sha1(token.encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % VECTOR_SIZE
        vector[index] += 1.0
    length = math.sqrt(sum(value * value for value in vector))
    return [value / length for value in vector] if length else vector


def extract_tokens(text: str) -> list[str]:
    normalized = normalize_key(text)
    tokens: list[str] = []
    tokens.extend(re.findall(r"[a-z0-9]{2,}", normalized))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]+", normalized))
    for size in (2, 3):
        tokens.extend(chinese[index : index + size] for index in range(max(0, len(chinese) - size + 1)))
    if chinese:
        tokens.extend(chinese[index] for index in range(len(chinese)))
    return tokens


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0
    length = min(len(left), len(right))
    return max(0.0, min(1.0, sum(left[index] * right[index] for index in range(length))))


def try_llm_answer(question: str, results: list[SearchResult]) -> str | None:
    if not is_llm_configured():
        return None

    base_url = get_env("RAG_LLM_BASE_URL", "LLM_BASE_URL").rstrip("/")
    model = get_env("RAG_LLM_MODEL", "LLM_MODEL")
    api_key = get_env("RAG_LLM_API_KEY", "LLM_API_KEY")
    prompt = build_rag_prompt(question, results)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是教材 RAG 问答模块。只能依据用户提供的 chunk 回答；"
                    f"若依据不足，必须只返回“{FALLBACK_ANSWER}”。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    answer = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    if not answer:
        return None
    if answer == FALLBACK_ANSWER:
        return answer
    return answer if "[" in answer and "]" in answer else None


def is_llm_configured() -> bool:
    return bool(get_env("RAG_LLM_BASE_URL", "LLM_BASE_URL") and get_env("RAG_LLM_MODEL", "LLM_MODEL"))


def build_rag_prompt(question: str, results: list[SearchResult]) -> str:
    contexts = []
    for index, result in enumerate(results, start=1):
        chunk = result.chunk
        contexts.append(
            "\n".join(
                [
                    f"[C{index}]",
                    f"教材：{chunk.textbook}",
                    f"章节：{chunk.chapter}",
                    f"页码：第 {chunk.page_start}-{chunk.page_end} 页",
                    f"原文：{chunk.text}",
                ]
            )
        )
    return "\n\n".join(
        [
            "请只基于下列教材 chunk 回答问题，不得使用模型自身医学知识补全。",
            "每个关键结论后必须附引用，格式为：[教材, 章节, 第 X 页]。",
            f"如果 chunk 中没有足够依据，请只返回：{FALLBACK_ANSWER}",
            f"问题：{question}",
            "检索 chunk：",
            "\n\n".join(contexts),
        ]
    )


def make_extractive_answer(question: str, results: list[SearchResult]) -> str:
    claims: list[str] = []
    for result in results:
        sentence = select_supported_sentence(question, result.chunk.text)
        if sentence:
            claims.append(f"{sentence} {citation_text(result.chunk)}")
        if len(claims) >= 3:
            break
    return "\n".join(claims) if claims else FALLBACK_ANSWER


def select_supported_sentence(question: str, text: str) -> str:
    question_tokens = set(extract_tokens(question))
    sentences = split_sentences(text)
    scored: list[tuple[int, str]] = []
    for sentence in sentences:
        sentence_tokens = set(extract_tokens(sentence))
        overlap = len(question_tokens & sentence_tokens)
        if question.strip() and question.strip() in sentence:
            overlap += 6
        scored.append((overlap, sentence))

    scored.sort(key=lambda item: (-item[0], len(item[1])))
    for score, sentence in scored:
        if score > 0:
            return truncate_sentence(sentence, 180)
    return ""


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？；;.!?])\s*", text)
    sentences = [part.strip() for part in parts if part.strip()]
    if sentences:
        return sentences
    return [text[:180].strip()] if text.strip() else []


def make_citation(result: SearchResult) -> RagCitation:
    chunk = result.chunk
    return RagCitation(
        textbook=chunk.textbook,
        chapter=chunk.chapter,
        page=chunk.page_start,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        relevance_score=round(result.score, 4),
    )


def make_source_chunk(result: SearchResult) -> RagSourceChunk:
    chunk = result.chunk
    return RagSourceChunk(
        chunk_id=chunk.chunk_id,
        textbook_id=chunk.textbook_id,
        textbook=chunk.textbook,
        chapter=chunk.chapter,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        text=chunk.text,
        relevance_score=round(result.score, 4),
    )


def make_status(index: RagIndex | None) -> RagIndexStatus:
    if index is None:
        return RagIndexStatus(indexed=False)
    return RagIndexStatus(
        indexed=True,
        textbook_ids=index.textbook_ids,
        chunk_count=len(index.chunks),
        embedding_mode=index.embedding_mode,  # type: ignore[arg-type]
        updated_at=index.updated_at,
    )


def citation_text(chunk: RagChunk) -> str:
    return f"[{chunk.textbook}, {chunk.chapter}, 第 {chunk.page_start} 页]"


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def normalize_key(value: str) -> str:
    return re.sub(r"[\s（）()《》“”\"'、，,。:：；;./\\-]", "", value).lower()


def truncate_sentence(sentence: str, max_length: int) -> str:
    clean = normalize_text(sentence)
    return clean if len(clean) <= max_length else f"{clean[:max_length]}..."


def get_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return ""
