# OCR Platform - Makefile

.PHONY: up down build logs clean dev health
.PHONY: worker-paddle worker-tesseract workers workers-down
.PHONY: create-admin promote demote

# === Core (Infrastructure + Backend) ===

up:
	docker-compose up -d

down:
	docker-compose down

build:
	docker-compose build

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	rm -rf data/

dev:
	docker-compose up --build

backend:
	docker-compose up -d backend

health:
	curl -f http://localhost:8000/health

# === Workers ===

worker-paddle:
	docker-compose -f worker/deploy/paddle-text/docker-compose.yml up -d

worker-tesseract:
	docker-compose -f worker/deploy/tesseract-cpu/docker-compose.yml up -d

workers: worker-paddle worker-tesseract

workers-down:
	docker-compose -f worker/deploy/paddle-text/docker-compose.yml down
	docker-compose -f worker/deploy/tesseract-cpu/docker-compose.yml down

# === Admin ===
# Usage:
#   make create-admin EMAIL=admin@example.com PASS=secret123
#   make promote EMAIL=user@example.com
#   make demote EMAIL=user@example.com

create-admin:
	docker-compose exec backend python -m app.cli create-admin $(EMAIL) $(PASS)

promote:
	docker-compose exec backend python -m app.cli promote $(EMAIL)

demote:
	docker-compose exec backend python -m app.cli demote $(EMAIL)

# === All ===

all: up workers

all-down: workers-down down
