.PHONY: install run debug clean lint lint-strict test context check

install:
	uv sync

run:
	uv run python -m src $(ARGS)

debug:
	uv run python -m pdb -m src $(ARGS)

clean:
	rm -rf __pycache__ src/__pycache__ tests/__pycache__ .pytest_cache .mypy_cache

lint:
	uv run flake8 src tests scripts
	uv run mypy src tests scripts --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict:
	uv run flake8 src tests scripts
	uv run mypy src tests scripts --strict

test:
	uv run pytest

context:
	uv run python scripts/validate-context.py

check: context lint test
