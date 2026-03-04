.PHONY: install dev dev-backend dev-frontend test lint build clean docker-up docker-down

# ─── Install ────────────────────────────────────────────

install:
	cd backend && pip install -e ".[dev]"
	cd frontend && pnpm install

# ─── Development ────────────────────────────────────────

dev: dev-backend dev-frontend

dev-backend:
	cd backend && uvicorn src.main:app --reload --port 8000

dev-frontend:
	cd frontend && pnpm dev

# ─── Test ───────────────────────────────────────────────

test:
	cd backend && pytest -v

test-cov:
	cd backend && pytest --cov=src --cov-report=term-missing

# ─── Lint ───────────────────────────────────────────────

lint:
	cd backend && ruff check src/ tests/
	cd frontend && pnpm tsc --noEmit

lint-fix:
	cd backend && ruff check --fix src/ tests/

# ─── Build ──────────────────────────────────────────────

build:
	cd frontend && pnpm build

# ─── Docker ─────────────────────────────────────────────

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

# ─── Clean ──────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/dist frontend/dist
