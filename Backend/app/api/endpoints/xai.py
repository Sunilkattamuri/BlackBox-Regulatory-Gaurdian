from fastapi import APIRouter
from pydantic import BaseModel
from ...services.xai_service import xai_service

router = APIRouter()

class XAIRequest(BaseModel):
    text: str
    question: str

@router.post("/explain")
def get_explanation(request: XAIRequest):
    # Pass None for model/tokenizer since we are mocking it for the prototype UI
    explanation = xai_service.generate_explanation(None, None, request.text, request.question)
    return explanation
