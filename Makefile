# OCR Platform - Makefile

.PHONY: up down build logs clean dev health
.PHONY: worker-paddle worker-paddle-vl worker-tesseract workers workers-down workers-build
.PHONY: create-admin promote demote

# === Core (Infrastructure + Backend) ===

infra-only:
	docker compose up -d minio nats

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

clean:
	docker compose down -v
	rm -rf data/

dev:
	docker compose up --build

backend:
	docker compose up -d backend

health:
	curl -f http://localhost:8000/health

# === Workers (base image + per-worker layer) ===
# See 03_worker/Makefile for detailed worker build targets
# docker build -f Dockerfile.base-gpu -t ocr-worker-base-gpu:latest .

worker-paddle:
	$(MAKE) -C 03_worker up-paddle

worker-paddle-vl:
	$(MAKE) -C 03_worker up-paddle-vl

worker-tesseract:
	$(MAKE) -C 03_worker up-tesseract

worker-marker:
	$(MAKE) -C 03_worker up-marker

workers: worker-paddle worker-paddle-vl worker-tesseract worker-marker

workers-down:
	$(MAKE) -C 03_worker down-paddle
	$(MAKE) -C 03_worker down-paddle-vl
	$(MAKE) -C 03_worker down-tesseract
	$(MAKE) -C 03_worker down-marker

workers-build:
	$(MAKE) -C 03_worker build-all

# === Admin ===
# admin@gmail.com/admin123

create-admin:
	docker compose exec backend python -m app.cli create-admin $(EMAIL) $(PASS)

promote:
	docker compose exec backend python -m app.cli promote $(EMAIL)

demote:
	docker compose exec backend python -m app.cli demote $(EMAIL)

# === All ===

all: up workers

all-down: workers-down down
# docker compose exec backend python -m app.cli create-admin admin@gmail.com admin123
# python -m app.cli create-admin admin@gmail.com admin123 