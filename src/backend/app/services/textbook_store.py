from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.models.schemas import TextbookDetail, TextbookSummary
from app.services.textbook_parser import parse_textbook


SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}


class TextbookStore:
    def __init__(self, upload_dir: str = "data/uploads") -> None:
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._textbooks: dict[str, TextbookDetail] = {}

    def list_textbooks(self) -> list[TextbookSummary]:
        return sorted(
            [TextbookSummary(**item.model_dump(exclude={"chapters"})) for item in self._textbooks.values()],
            key=lambda item: item.uploaded_at,
            reverse=True,
        )

    def get_textbook(self, textbook_id: str) -> TextbookDetail | None:
        return self._textbooks.get(textbook_id)

    async def add_upload(self, file: UploadFile) -> TextbookSummary:
        textbook_id = f"book_{uuid4().hex[:8]}"
        original_name = Path(file.filename or "untitled").name
        extension = Path(original_name).suffix.lower()
        content = await file.read()
        size_bytes = len(content)

        detail = TextbookDetail(
            textbook_id=textbook_id,
            filename=original_name,
            title=Path(original_name).stem or original_name,
            format=(extension.lstrip(".") or "unknown").upper(),
            size_bytes=size_bytes,
            size_label=format_size(size_bytes),
            status="parsing",
            message="解析中",
            total_pages=0,
            total_chars=0,
            chapter_count=0,
            chapters=[],
        )
        self._textbooks[textbook_id] = detail

        if extension not in SUPPORTED_EXTENSIONS:
            detail.status = "failed"
            detail.message = "暂只支持 PDF、Markdown、TXT"
            return TextbookSummary(**detail.model_dump(exclude={"chapters"}))

        target = self.upload_dir / f"{textbook_id}{extension or '.bin'}"
        target.write_bytes(content)

        try:
            parsed = parse_textbook(target, original_name)
        except Exception as exc:  # noqa: BLE001 - surface parser failures to the UI as status data.
            detail.status = "failed"
            detail.message = f"解析失败：{exc}"
            return TextbookSummary(**detail.model_dump(exclude={"chapters"}))

        detail.title = parsed.title
        detail.status = "parsed"
        detail.message = "解析完成"
        detail.total_pages = parsed.total_pages
        detail.total_chars = parsed.total_chars
        detail.chapter_count = len(parsed.chapters)
        detail.chapters = parsed.chapters
        return TextbookSummary(**detail.model_dump(exclude={"chapters"}))


def format_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
