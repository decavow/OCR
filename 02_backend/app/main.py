# FastAPI app entry, lifespan events, routers mount

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.lifespan import startup, shutdown
from app.core.middleware import setup_middleware


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
    allow_origins=["*"],  # TODO: Configure for production
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
    # TODO: Check DB, NATS, MinIO connections
    return {"status": "healthy"}
