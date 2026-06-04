.PHONY: install run test lint

install:
	pip install -r requirements.txt
	playwright install chromium

run:
	streamlit run ui/app.py

test:
	pytest tests/ -v --tb=short

lint:
	ruff check .
