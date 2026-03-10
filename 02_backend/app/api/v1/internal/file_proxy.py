# POST /internal/file-proxy/download, POST /internal/file-proxy/upload

import base64
import logging
from fastapi import APIRouter, Header, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.v1.schemas.file_proxy import FileProxyDownloadReq, FileProxyUploadReq
from app.api.deps import get_db, get_storage, get_request_id
from app.modules.file_proxy.service import FileProxyService
from app.modules.file_proxy.exceptions import FileProxyError

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/download")
async def download_for_worker(
    data: FileProxyDownloadReq,
    request: Request,
    x_access_key: str = Header(..., alias="X-Access-Key"),
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
):
    """Download file for worker processing.

    Workers call this endpoint to get the original file content.
    Access is verified via the X-Access-Key header.
    """
    rid = get_request_id(request)
    try:
        file_proxy = FileProxyService(db, storage)
        content, content_type, filename = await file_proxy.download_for_worker(
            access_key=x_access_key,
            job_id=data.job_id,
            file_id=data.file_id,
        )

        logger.debug(
            "File download for worker: job_id=%s file_id=%s filename=%s",
            data.job_id, data.file_id, filename,
            extra={"request_id": rid, "job_id": data.job_id},
        )

        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-File-Name": filename,
                "X-Content-Type": content_type,
            },
        )

    except FileProxyError as e:
        logger.warning(
            "File download access denied: job_id=%s file_id=%s error=%s",
            data.job_id, data.file_id, str(e),
            extra={"request_id": rid, "job_id": data.job_id},
        )
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(
            "File download failed: job_id=%s file_id=%s error=%s",
            data.job_id, data.file_id, str(e),
            exc_info=True,
            extra={"request_id": rid, "job_id": data.job_id},
        )
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.post("/upload")
async def upload_from_worker(
    data: FileProxyUploadReq,
    request: Request,
    x_access_key: str = Header(..., alias="X-Access-Key"),
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
):
    """Upload result from worker.

    Workers call this endpoint to upload processing results.
    Content is base64 encoded in the request body.
    """
    rid = get_request_id(request)
    try:
        # Decode base64 content
        try:
            content = base64.b64decode(data.content)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 content")

        file_proxy = FileProxyService(db, storage)
        result_key = await file_proxy.upload_from_worker(
            access_key=x_access_key,
            job_id=data.job_id,
            file_id=data.file_id,
            content=content,
            content_type=data.content_type,
        )

        logger.info(
            "File upload from worker: job_id=%s file_id=%s result_key=%s",
            data.job_id, data.file_id, result_key,
            extra={"request_id": rid, "job_id": data.job_id},
        )

        return {
            "success": True,
            "result_key": result_key,
        }

    except FileProxyError as e:
        logger.warning(
            "File upload access denied: job_id=%s file_id=%s error=%s",
            data.job_id, data.file_id, str(e),
            extra={"request_id": rid, "job_id": data.job_id},
        )
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "File upload failed: job_id=%s file_id=%s error=%s",
            data.job_id, data.file_id, str(e),
            exc_info=True,
            extra={"request_id": rid, "job_id": data.job_id},
        )
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
