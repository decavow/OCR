# POST /upload (multipart files + config)

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import datetime

from app.api.deps import get_db, get_current_user, get_storage, get_queue
from app.modules.upload.service import UploadService
from app.modules.upload.exceptions import UploadError

router = APIRouter()


class FileResponse(BaseModel):
    id: str
    original_name: str
    mime_type: str
    size_bytes: int

    class Config:
        from_attributes = True


class JobResponse(BaseModel):
    id: str
    file_id: str
    status: str
    method: str
    tier: int

    class Config:
        from_attributes = True


class UploadResponse(BaseModel):
    request_id: str
    status: str
    total_files: int
    output_format: str
    method: str
    tier: int
    created_at: datetime
    files: List[FileResponse]


@router.post("", response_model=UploadResponse)
async def upload_files(
    files: List[UploadFile] = File(...),
    output_format: str = "txt",
    retention_hours: int = 168,
    method: str = "ocr_text_raw",
    tier: int = 0,
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
    queue=Depends(get_queue),
    current_user=Depends(get_current_user),
):
    """Upload files for OCR processing.

    - Validates files (type, size)
    - Stores files in MinIO uploads bucket
    - Creates Request, File, and Job records
    - Publishes jobs to NATS queue for processing
    """
    try:
        upload_service = UploadService(db, storage, queue)
        request = await upload_service.process_upload(
            user_id=current_user.id,
            files=files,
            output_format=output_format,
            retention_hours=retention_hours,
            method=method,
            tier=tier,
        )

        # Build response
        file_responses = [
            FileResponse.model_validate(f) for f in request.files
        ]

        return UploadResponse(
            request_id=request.id,
            status=request.status,
            total_files=request.total_files,
            output_format=request.output_format,
            method=request.method,
            tier=request.tier,
            created_at=request.created_at,
            files=file_responses,
        )

    except UploadError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
