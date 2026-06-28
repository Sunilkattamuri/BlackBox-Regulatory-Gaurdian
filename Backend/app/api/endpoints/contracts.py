from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from ... import models, schemas
from ...database import SessionLocal, get_db
from ...services.contract_service import contract_service
from ...services.vector_store_service import vector_store_service
import shutil
import os

router = APIRouter()

UPLOAD_DIR = "uploaded_contracts"
os.makedirs(UPLOAD_DIR, exist_ok=True)

from datetime import datetime

def process_contract_background(contract_id: int, file_path: str):
    db = SessionLocal()
    try:
        db_contract = db.query(models.Contract).filter(models.Contract.id == contract_id).first()
        if not db_contract:
            return

        results = contract_service.analyze_contract(file_path)
        db_contract.extracted_data = results
        db_contract.status = "completed"
        db_contract.completed_at = datetime.utcnow()
        db_contract.raw_text = results.get("raw_text", "")
        db.commit()
        
        # Integrate with Pinecone Vector DB for RAG
        full_text = results.get("full_text", "")
        if full_text:
            vector_store_service.upsert_contract(
                contract_id=db_contract.id,
                filename=db_contract.filename,
                text=full_text
            )
            
    except Exception as e:
        print(f"Error processing contract {contract_id}: {e}")
        db_contract = db.query(models.Contract).filter(models.Contract.id == contract_id).first()
        if db_contract:
            db_contract.status = "failed"
            db_contract.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()

@router.post("/upload", response_model=schemas.ContractResponse)
async def upload_contract(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
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

    # Offload processing to background task
    background_tasks.add_task(process_contract_background, db_contract.id, file_path)

    return db_contract

@router.get("/", response_model=List[schemas.ContractResponse])
def get_contracts(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    contracts = db.query(models.Contract).order_by(models.Contract.id.desc()).offset(skip).limit(limit).all()
    return contracts

@router.delete("/{contract_id}")
def delete_contract(contract_id: int, db: Session = Depends(get_db)):
    contract = db.query(models.Contract).filter(models.Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Try to delete the physical file
    file_path = os.path.join(UPLOAD_DIR, contract.filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file: {e}")
            
    # Remove from Vector DB
    vector_store_service.delete_contract(contract_id)
            
    db.delete(contract)
    db.commit()
    return {"message": "Contract deleted successfully"}
