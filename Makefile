.PHONY: db-upgrade db-downgrade db-current db-migrate db-revision test lint

# Run all Alembic migrations to head
db-upgrade:
	cd backend && python -m alembic upgrade head

# Downgrade the last migration
db-downgrade:
	cd backend && python -m alembic downgrade -1

# Show current migration version
db-current:
	cd backend && python -m alembic current

# Auto-generate a new migration (usage: make db-migrate m="description")
db-migrate:
	cd backend && python -m alembic revision --autogenerate -m "$(m)"

# Create an empty revision (usage: make db-revision m="description")
db-revision:
	cd backend && python -m alembic revision -m "$(m)"

# Run tests
test:
	cd backend && python -m pytest tests/ -v

# Lint
lint:
	cd backend && python -m ruff check .
