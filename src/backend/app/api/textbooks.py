import os

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.store import get_store
from app.models.schemas import TextbookDetail, TextbookSummary, UploadResponse

router = APIRouter(prefix="/api/textbooks", tags=["textbooks"])


@router.post("/upload", response_model=UploadResponse)
async def upload_textbooks(files: list[UploadFile] = File(...)) -> UploadResponse:
    textbooks = [await get_store().add_upload(file) for file in files]
    return UploadResponse(textbooks=textbooks)


@router.get("", response_model=list[TextbookSummary])
async def list_textbooks() -> list[TextbookSummary]:
    return get_store().list_textbooks()


@router.get("/{textbook_id}", response_model=TextbookDetail)
async def get_textbook(textbook_id: str) -> TextbookDetail:
    textbook = get_store().get_textbook(textbook_id)
    if textbook is None:
        raise HTTPException(status_code=404, detail="教材不存在")
    return textbook
