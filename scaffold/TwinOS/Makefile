.PHONY: install lint test contracts up down

install:
	pip install -e ".[dev]"

lint:
	ruff check .

contracts:              ## Interface Spec 계약 검증만 실행
	pytest tests/contracts -v

test:
	pytest tests plugins -v

up:                     ## 로컬 인프라 기동 (postgres/redis/minio)
	docker compose -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down
