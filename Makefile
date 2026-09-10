
MAP ?= maps/easy/02_simple_fork.txt
 
install:
	uv sync
 
run:
	uv run python3 main.py $(MAP)
 
debug:
	uv run python3 -m pdb main.py $(MAP)
 
clean:
	rm -rf __pycache__ .mypy_cache .pytest_cache
 
lint:
	uv run flake8 . --extend-exclude=.venv
	uv run mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs
 
lint-strict:
	uv run flake8 . --extend-exclude=.venv
	uv run mypy . --strict
 
.PHONY: install run debug clean lint lint-strict
 