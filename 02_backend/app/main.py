# FastAPI app entry, lifespan events, routers mount

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.config import settings
from app.core.lifespan import startup, shutdown, storage_service, queue_service
from app.core.middleware import setup_middleware
from app.infrastructure.database.connection import SessionLocal
from app.modules.health.service import HealthService


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await startup()
    yield
    # Shutdown
    await shutdown()


app = FastAPI(
    title="OCR Platform API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup custom middleware
setup_middleware(app)

# Mount API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Real health check: DB, NATS, MinIO."""
    from app.core.lifespan import storage_service, queue_service
    db = SessionLocal()
    try:
        service = HealthService(db, storage_service, queue_service)
        result = await service.check_all()
        status_code = 200 if result["status"] != "unhealthy" else 503
        return JSONResponse(content=result, status_code=status_code)
    finally:
        db.close()
