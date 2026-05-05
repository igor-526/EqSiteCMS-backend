read readme to get know about the project and make sure you follow all rules of development.

make sure you regularly run, especially at the end of the task:
unit tests `PYTHONPATH=src uv run pytest -s -vv tests/unit`
lint `uv run mypy src`
formatting `uv run isort src && uv run black src`

you will not be able to run integration tests so just write logic accurate
