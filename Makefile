# OCR Platform - Makefile

.PHONY: up down build logs clean dev health
.PHONY: worker-paddle worker-tesseract workers workers-down

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

# === All ===

all: up workers

all-down: workers-down down
