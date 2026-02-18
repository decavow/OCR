# OCR Worker - Build & Deploy
#
# Architecture: Base Image + Per-Worker Layer
#   Base images contain: Python runtime, shared deps, app code
#   Worker images add: engine-specific deps (paddleocr, tesseract, etc.)
#
# Usage:
#   make build-all          # Build all base + worker images
#   make build-paddle       # Build base-gpu + paddle worker
#   make build-paddle-vl    # Build base-gpu + paddle-vl worker
#   make build-tesseract    # Build base-cpu + tesseract worker
#   make up-paddle          # Build + start paddle worker
#   make up-paddle-vl       # Build + start paddle-vl worker
#   make up-tesseract       # Build + start tesseract worker
#
# Adding a new worker:
#   1. Create deploy/<name>/Dockerfile (FROM ocr-worker-base-gpu or base-cpu)
#   2. Create deploy/<name>/requirements.txt (engine-specific deps)
#   3. Create deploy/<name>/docker-compose.yml + .env.example
#   4. Add build-<name> and up-<name> targets below

.PHONY: build-base-gpu build-base-cpu build-paddle build-paddle-vl build-tesseract build-all
.PHONY: up-paddle up-paddle-vl up-tesseract down-paddle down-paddle-vl down-tesseract

# === Base Images ===

build-base-gpu:
	docker build -f Dockerfile.base-gpu -t ocr-worker-base-gpu:latest .

build-base-cpu:
	docker build -f Dockerfile.base-cpu -t ocr-worker-base-cpu:latest .

# === Worker Images ===

build-paddle: build-base-gpu
	docker build -f deploy/paddle-text/Dockerfile -t ocr-worker-paddle:latest .

build-tesseract: build-base-cpu
	docker build -f deploy/tesseract-cpu/Dockerfile -t ocr-worker-tesseract:latest .

build-paddle-vl: build-base-gpu
	docker build -f deploy/paddle-vl/Dockerfile -t ocr-worker-paddle-vl:latest .

build-all: build-paddle build-paddle-vl build-tesseract

# === Run Workers ===

up-paddle: build-base-gpu
	docker compose -f deploy/paddle-text/docker-compose.yml up -d --build

up-tesseract: build-base-cpu
	docker compose -f deploy/tesseract-cpu/docker-compose.yml up -d --build

up-paddle-vl: build-base-gpu
	docker compose -f deploy/paddle-vl/docker-compose.yml up -d --build

down-paddle:
	docker compose -f deploy/paddle-text/docker-compose.yml down

down-paddle-vl:
	docker compose -f deploy/paddle-vl/docker-compose.yml down

down-tesseract:
	docker compose -f deploy/tesseract-cpu/docker-compose.yml down

# === Logs ===

logs-paddle:
	docker compose -f deploy/paddle-text/docker-compose.yml logs -f

logs-paddle-vl:
	docker compose -f deploy/paddle-vl/docker-compose.yml logs -f

logs-tesseract:
	docker compose -f deploy/tesseract-cpu/docker-compose.yml logs -f
