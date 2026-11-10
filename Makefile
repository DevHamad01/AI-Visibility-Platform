.PHONY: up down logs test migrate fmt

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

test:
	docker compose run --rm api pytest -v

migrate:
	docker compose run --rm api alembic upgrade head

fmt:
	docker compose run --rm api sh -c "ruff format app tests && ruff check --fix app tests"
