import re
from dataclasses import dataclass
from pathlib import Path

from app.models.schemas import Chapter


CHAPTER_PATTERN = re.compile(
    r"^\s*(第\s*[一二三四五六七八九十百千万零〇两\d]+\s*[章节篇])(?:\s|[、:：.-]|$).{0,60}$"
)
SPECIAL_TITLE_PATTERN = re.compile(r"^\s*(绪论|导论|总论|概述|前言)\s*$")
PAGE_MARK_PATTERN = re.compile(
    r"^\s*(?:[-—_]*\s*)?(?:\d+|第\s*\d+\s*页(?:\s*/\s*共\s*\d+\s*页)?)(?:\s*[-—_]*)?\s*$"
)


@dataclass
class ParsedTextbook:
    title: str
    total_pages: int
    total_chars: int
    chapters: list[Chapter]


def parse_textbook(path: Path, filename: str) -> ParsedTextbook:
    extension = path.suffix.lower()
    if extension == ".pdf":
        return parse_pdf(path, filename)
    if extension in {".md", ".markdown"}:
        return parse_markdown(path, filename)
    if extension == ".txt":
        return parse_txt(path, filename)
    raise ValueError("暂只支持 PDF、Markdown、TXT")


def parse_pdf(path: Path, filename: str) -> ParsedTextbook:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("缺少 PyMuPDF 依赖，请先安装 requirements.txt") from exc

    chapters: list[Chapter] = []
    current_title: str | None = None
    current_page_start = 1
    current_page_end = 1
    current_parts: list[str] = []
    total_chars = 0
    title = Path(filename).stem or filename

    with fitz.open(path) as document:
        total_pages = document.page_count
        for page_index in range(total_pages):
            page_number = page_index + 1
            page = document.load_page(page_index)
            page_text = clean_page_text(page.get_text("text"), page_number)
            if not page_text:
                continue

            page_title = detect_chapter_title(page_text)
            if page_title:
                if current_parts:
                    chapters.append(
                        make_chapter(
                            len(chapters) + 1,
                            current_title or "正文",
                            current_page_start,
                            current_page_end,
                            current_parts,
                        )
                    )
                current_title = page_title
                current_page_start = page_number
                current_parts = [page_text]
            else:
                if not current_parts:
                    current_title = "正文"
                    current_page_start = page_number
                current_parts.append(page_text)

            current_page_end = page_number
            total_chars += len(page_text)

    if current_parts:
        chapters.append(
            make_chapter(
                len(chapters) + 1,
                current_title or "正文",
                current_page_start,
                current_page_end,
                current_parts,
            )
        )

    if not chapters:
        chapters = [
            Chapter(
                chapter_id="ch_001",
                title="正文",
                page_start=1,
                page_end=max(total_pages, 1),
                content="",
                char_count=0,
            )
        ]
    elif len(chapters) == 1 and chapters[0].title == "正文" and total_pages > 5:
        chapters = split_plain_pages(path, filename)

    total_chars = sum(chapter.char_count for chapter in chapters)

    return ParsedTextbook(title=title, total_pages=total_pages, total_chars=total_chars, chapters=chapters)


def parse_markdown(path: Path, filename: str) -> ParsedTextbook:
    content = read_text_file(path)
    title = Path(filename).stem or filename
    lines = [normalize_line(line) for line in content.splitlines()]
    chapters: list[Chapter] = []
    current_title = "正文"
    current_parts: list[str] = []

    for line in lines:
        if not line:
            continue
        heading = parse_markdown_heading(line) or detect_line_chapter_title(line)
        if heading:
            if current_parts:
                chapters.append(make_chapter(len(chapters) + 1, current_title, 1, 1, current_parts))
            current_title = heading
            current_parts = [line]
        else:
            current_parts.append(line)

    if current_parts:
        chapters.append(make_chapter(len(chapters) + 1, current_title, 1, 1, current_parts))

    if not chapters:
        chapters = [make_chapter(1, "正文", 1, 1, [content.strip()])]

    return ParsedTextbook(
        title=title,
        total_pages=0,
        total_chars=sum(chapter.char_count for chapter in chapters),
        chapters=chapters,
    )


def parse_txt(path: Path, filename: str) -> ParsedTextbook:
    content = read_text_file(path)
    title = Path(filename).stem or filename
    lines = [normalize_line(line) for line in content.splitlines()]
    chapters: list[Chapter] = []
    current_title = "正文"
    current_parts: list[str] = []

    for line in lines:
        if not line:
            continue
        heading = detect_line_chapter_title(line)
        if heading:
            if current_parts:
                chapters.append(make_chapter(len(chapters) + 1, current_title, 1, 1, current_parts))
            current_title = heading
            current_parts = [line]
        else:
            current_parts.append(line)

    if current_parts:
        chapters.append(make_chapter(len(chapters) + 1, current_title, 1, 1, current_parts))

    if not chapters:
        chapters = [make_chapter(1, "正文", 1, 1, [content.strip()])]

    return ParsedTextbook(
        title=title,
        total_pages=0,
        total_chars=sum(chapter.char_count for chapter in chapters),
        chapters=chapters,
    )


def split_plain_pages(path: Path, filename: str, pages_per_block: int = 5) -> list[Chapter]:
    import fitz

    chapters: list[Chapter] = []
    current_parts: list[str] = []
    page_start = 1

    with fitz.open(path) as document:
        for page_index in range(document.page_count):
            page_number = page_index + 1
            page_text = clean_page_text(document.load_page(page_index).get_text("text"), page_number)
            if page_text:
                current_parts.append(page_text)
            if page_number % pages_per_block == 0 and current_parts:
                chapters.append(
                    make_chapter(
                        len(chapters) + 1,
                        f"第 {page_start}-{page_number} 页正文",
                        page_start,
                        page_number,
                        current_parts,
                    )
                )
                page_start = page_number + 1
                current_parts = []

        if current_parts:
            chapters.append(
                make_chapter(
                    len(chapters) + 1,
                    f"第 {page_start}-{document.page_count} 页正文",
                    page_start,
                    document.page_count,
                    current_parts,
                )
            )

    if not chapters:
        chapters.append(make_chapter(1, Path(filename).stem or "正文", 1, 1, [""]))
    return chapters


def clean_page_text(raw_text: str, page_number: int) -> str:
    lines = []
    for raw_line in raw_text.splitlines():
        line = normalize_line(raw_line)
        if not line:
            continue
        if PAGE_MARK_PATTERN.match(line):
            continue
        if line in {str(page_number), f"- {page_number} -", f"— {page_number} —"}:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def detect_chapter_title(page_text: str) -> str | None:
    for line in page_text.splitlines()[:8]:
        title = detect_line_chapter_title(line)
        if title:
            return title
    return None


def detect_line_chapter_title(line: str) -> str | None:
    normalized = normalize_line(line)
    if not normalized or len(normalized) > 80:
        return None
    if SPECIAL_TITLE_PATTERN.match(normalized):
        return normalized
    if CHAPTER_PATTERN.match(normalized):
        return normalized
    return None


def parse_markdown_heading(line: str) -> str | None:
    match = re.match(r"^(#{1,6})\s+(.+)$", line)
    if not match:
        return None
    title = normalize_line(match.group(2))
    return title[:80] if title else None


def make_chapter(
    index: int,
    title: str,
    page_start: int,
    page_end: int,
    parts: list[str],
) -> Chapter:
    content = "\n".join(part.strip() for part in parts if part.strip()).strip()
    return Chapter(
        chapter_id=f"ch_{index:03d}",
        title=title.strip() or "正文",
        page_start=page_start,
        page_end=max(page_start, page_end),
        content=content,
        char_count=len(content),
    )


def normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.replace("\u3000", " ")).strip()


def read_text_file(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")
