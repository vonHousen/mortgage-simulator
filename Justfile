default:
    @just --list

sync:
    uv sync --locked --all-groups

run:
    uv run streamlit run src/mortgage_simulator/app/streamlit_app.py

test:
    uv run pytest

test-cov:
    uv run pytest --cov --cov-report=term-missing

regression-excel:
    test -f data/mortgage-simulation-v2.xlsx || (echo "Missing Excel regression artifact: data/mortgage-simulation-v2.xlsx" >&2; exit 1)
    test -f data/regression/excel.json || (echo "Missing Excel regression manifest: data/regression/excel.json" >&2; exit 1)
    uv run pytest -m excel

regression-calendar:
    test -f data/calendar-day-mortgage-reference.csv || (echo "Missing calendar regression artifact: data/calendar-day-mortgage-reference.csv" >&2; exit 1)
    test -f data/regression/calendar.json || (echo "Missing calendar regression manifest: data/regression/calendar.json" >&2; exit 1)
    uv run pytest -m calendar

regression-insurance:
    test -f data/monthly-insurance-values.csv || (echo "Missing insurance regression artifact: data/monthly-insurance-values.csv" >&2; exit 1)
    test -f data/regression/insurance.json || (echo "Missing insurance regression manifest: data/regression/insurance.json" >&2; exit 1)
    uv run pytest -m insurance

e2e-regression-tests: regression-excel regression-calendar regression-insurance

lint:
    uv run ruff check .

format:
    uv run ruff format .

format-check:
    uv run ruff format --check .

typecheck:
    uv run mypy
    uv run ty check

lock-check:
    uv lock --check

ci: lock-check lint format-check typecheck test
