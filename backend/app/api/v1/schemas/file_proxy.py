# FileProxyDownloadReq, FileProxyUploadReq

from pydantic import BaseModel


class FileProxyDownloadReq(BaseModel):
    job_id: str
    file_id: str


class FileProxyUploadReq(BaseModel):
    job_id: str
    file_id: str
    content: str  # Base64 encoded content
    content_type: str = "text/plain"
