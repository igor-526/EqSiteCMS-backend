# Example usage: make makemigrations message="create_table"
makemigrations:
	docker exec eqsitecms-$(eq)-app sh -c "cd src && uv run alembic revision --autogenerate -m '$(msg)'"

migrate:
	docker exec eqsitecms-$(eq)-app sh -c "cd src && uv run alembic upgrade head"

shell:
	docker exec -it eqsitecms-$(eq)-app sh

# Opens postgresql command line interface
psql:
	docker exec -it eqsitecms-$(eq)-db psql -U eqsitecms

dumpall:
	docker exec -t eqsitecms-$(eq)-db pg_dumpall -c -U eqsitecms > dump_`date +%Y-%m-%d"_"%H_%M_%S`.sql

lint:
	uv run mypy src

format:
	uv run isort src && uv run black src

# Dangerous
drop_db:
	docker exec -t eqsitecms-$(eq)-db psql -U eqsitecms -d postgres -c "DROP DATABASE IF EXISTS eqsitecms;"

seed_dump:
	cat seed_mocks.sql | docker exec -i eqsitecms-$(eq)-db psql -U eqsitecms
