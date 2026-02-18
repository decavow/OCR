# OCR Platform - Makefile

.PHONY: up down build logs clean dev health
.PHONY: worker-paddle worker-paddle-vl worker-tesseract workers workers-down workers-build
.PHONY: create-admin promote demote

# === Core (Infrastructure + Backend) ===

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

worker-paddle:
	$(MAKE) -C 03_worker up-paddle

worker-paddle-vl:
	$(MAKE) -C 03_worker up-paddle-vl

worker-tesseract:
	$(MAKE) -C 03_worker up-tesseract

workers: worker-paddle worker-paddle-vl worker-tesseract

workers-down:
	$(MAKE) -C 03_worker down-paddle
	$(MAKE) -C 03_worker down-paddle-vl
	$(MAKE) -C 03_worker down-tesseract

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
