from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ... import models, schemas
from ...database import get_db
from ...services.contract_service import contract_service
import shutil
import os

router = APIRouter()

UPLOAD_DIR = "uploaded_contracts"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", response_model=schemas.ContractResponse)
async def upload_contract(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Save to DB
    db_contract = models.Contract(filename=file.filename, status="processing")
    db.add(db_contract)
    db.commit()
    db.refresh(db_contract)

    # Process via inference service
    try:
        results = contract_service.analyze_contract(file_path)
        db_contract.extracted_data = results
        db_contract.status = "completed"
        db_contract.raw_text = results.get("raw_text", "")
        db.commit()
        db.refresh(db_contract)
    except Exception as e:
        db_contract.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))

    return db_contract

@router.get("/", response_model=List[schemas.ContractResponse])
def get_contracts(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    contracts = db.query(models.Contract).offset(skip).limit(limit).all()
    return contracts
