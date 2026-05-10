import os

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.schemas import TextbookDetail, TextbookSummary, UploadResponse
from app.services.textbook_store import TextbookStore

router = APIRouter(prefix="/api/textbooks", tags=["textbooks"])
store = TextbookStore(upload_dir=os.getenv("UPLOAD_DIR", "data/uploads"))


@router.post("/upload", response_model=UploadResponse)
async def upload_textbooks(files: list[UploadFile] = File(...)) -> UploadResponse:
    textbooks = [await store.add_upload(file) for file in files]
    return UploadResponse(textbooks=textbooks)


@router.get("", response_model=list[TextbookSummary])
async def list_textbooks() -> list[TextbookSummary]:
    return store.list_textbooks()


@router.get("/{textbook_id}", response_model=TextbookDetail)
async def get_textbook(textbook_id: str) -> TextbookDetail:
    textbook = store.get_textbook(textbook_id)
    if textbook is None:
        raise HTTPException(status_code=404, detail="教材不存在")
    return textbook
