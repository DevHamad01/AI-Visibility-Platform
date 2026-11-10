.PHONY: up down logs test migrate fmt check

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

test:
	docker compose run --rm api pytest -v

check:
	docker compose run --rm api ruff check app tests
	docker compose run --rm --no-deps --entrypoint sh frontend -c "nginx -t"
	cd frontend && npm run lint && npm run build && npm test -- --watch=false

migrate:
	docker compose run --rm api alembic upgrade head

fmt:
	docker compose run --rm api sh -c "ruff format app tests && ruff check --fix app tests"
