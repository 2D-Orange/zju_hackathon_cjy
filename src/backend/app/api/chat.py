from fastapi import APIRouter

from app.models.schemas import TeacherFeedbackRequest, TeacherFeedbackResponse
from app.services.chat_service import handle_teacher_feedback


router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=TeacherFeedbackResponse)
async def teacher_feedback(request: TeacherFeedbackRequest) -> TeacherFeedbackResponse:
    return handle_teacher_feedback(request)
