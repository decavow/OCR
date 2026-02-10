# Aggregate all routers

from fastapi import APIRouter

from app.api.v1.endpoints import auth, upload, requests, jobs, files, health, services
from app.api.v1.endpoints.admin import service_types, service_instances
from app.api.v1.internal import file_proxy, heartbeat, job_status, register

api_router = APIRouter()

# Public endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(requests.router, prefix="/requests", tags=["requests"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(services.router, prefix="/services", tags=["services"])

# Admin endpoints (for managing service types and instances)
api_router.include_router(service_types.router, prefix="/admin/service-types", tags=["admin"])
api_router.include_router(service_instances.router, prefix="/admin/service-instances", tags=["admin"])

# Internal endpoints (Worker <-> Orchestration)
api_router.include_router(register.router, prefix="/internal", tags=["internal"])
api_router.include_router(file_proxy.router, prefix="/internal/file-proxy", tags=["internal"])
api_router.include_router(heartbeat.router, prefix="/internal", tags=["internal"])
api_router.include_router(job_status.router, prefix="/internal", tags=["internal"])
