from fastapi import APIRouter
from pydantic import BaseModel
from ...services.xai_service import xai_service
from ...services.contract_service import contract_service

router = APIRouter()

class XAIRequest(BaseModel):
    text: str
    question: str

@router.post("/explain")
def get_explanation(request: XAIRequest):
    # Pass the loaded QA pipeline to the explainer
    explanation = xai_service.generate_explanation(
        contract_service.qa_pipeline, 
        request.text, 
        request.question
    )
    return explanation
