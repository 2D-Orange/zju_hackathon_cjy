from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.models.schemas import TextbookSummary


SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}


class TextbookStore:
    def __init__(self, upload_dir: str = "data/uploads") -> None:
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._textbooks: dict[str, TextbookSummary] = {}

    def list_textbooks(self) -> list[TextbookSummary]:
        return sorted(
            self._textbooks.values(),
            key=lambda item: item.uploaded_at,
            reverse=True,
        )

    async def add_upload(self, file: UploadFile) -> TextbookSummary:
        textbook_id = f"book_{uuid4().hex[:8]}"
        original_name = Path(file.filename or "untitled").name
        extension = Path(original_name).suffix.lower()
        content = await file.read()
        size_bytes = len(content)

        status = "mock_parsed" if extension in SUPPORTED_EXTENSIONS else "failed"
        message = (
            "已上传，mock 解析完成"
            if status == "mock_parsed"
            else "暂只支持 PDF、Markdown、TXT"
        )

        if status != "failed":
            target = self.upload_dir / f"{textbook_id}{extension or '.bin'}"
            target.write_bytes(content)

        summary = TextbookSummary(
            textbook_id=textbook_id,
            filename=original_name,
            title=Path(original_name).stem or original_name,
            format=(extension.lstrip(".") or "unknown").upper(),
            size_bytes=size_bytes,
            size_label=format_size(size_bytes),
            status=status,
            message=message,
            total_pages=1 if extension == ".pdf" else 0,
            total_chars=0,
            chapter_count=0,
        )
        self._textbooks[textbook_id] = summary
        return summary


def format_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
