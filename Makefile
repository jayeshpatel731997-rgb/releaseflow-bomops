.PHONY: install dev seed reset test lint typecheck build
install:
	python -m pip install -e "backend[dev]"
	cd frontend && npm install
dev:
	docker compose up --build
seed:
	cd backend && python -c "from app.db.session import SessionLocal; from app.db.seed import seed_database; db=SessionLocal(); print(seed_database(db)); db.close()"
reset: seed
test:
	cd backend && pytest
	cd frontend && npm test
lint:
	cd backend && ruff check . && ruff format --check .
	cd frontend && npm run lint
typecheck:
	cd backend && mypy app
	cd frontend && npm run typecheck
build:
	cd frontend && npm run build
