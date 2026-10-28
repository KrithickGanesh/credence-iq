SHELL := /bin/bash

ifeq ($(OS),Windows_NT)
PYTHON := .venv/Scripts/python
else
PYTHON := .venv/bin/python
endif

.PHONY: help install seed dry-run api web test bench up down logs clean

help:
	@echo "CredenceIQ targets"
	@echo "  make install   Create .venv and install backend dependencies"
	@echo "  make seed      Generate 30,000 customers / 300k+ rows in Exasol"
	@echo "  make dry-run   Generate 2,000 customers without touching Exasol"
	@echo "  make api       Run FastAPI on http://localhost:8000"
	@echo "  make web       Run the Next.js dashboard on http://localhost:3000"
	@echo "  make test      Run deterministic scoring tests"
	@echo "  make bench     Benchmark legacy N+1 vs one Exasol pass"
	@echo "  make up        Start the full stack with Docker Compose"
	@echo "  make down      Stop the Docker stack"

install:
	python -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r backend/requirements.txt

seed:
	$(PYTHON) seed_data.py --if-empty --customers 30000

dry-run:
	$(PYTHON) seed_data.py --dry-run --customers 2000

api:
	cd backend && ../$(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

web:
	cd frontend && npm run dev

test:
	$(PYTHON) -m pytest backend/tests -q

bench:
	$(PYTHON) scripts/benchmark.py --sample 100 --runs 3

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

clean:
	rm -rf frontend/.next backend/.pytest_cache .pytest_cache seed.log benchmark.json
