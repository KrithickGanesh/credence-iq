SHELL := /bin/bash

ifeq ($(OS),Windows_NT)
PYTHON := .venv/Scripts/python
else
PYTHON := .venv/bin/python
endif

.PHONY: help install seed dry-run api web test bench up up-fallback down logs status start clean

help:
	@echo "CredenceIQ targets"
	@echo "  make install     Create .venv and install backend dependencies"
	@echo "  make status      Show Exasol Personal status (exakit status)"
	@echo "  make start       Start Exasol Personal (exakit start)"
	@echo "  make seed        Generate 30,000 customers / ~292k rows in Exasol"
	@echo "  make dry-run     Generate 2,000 customers without touching Exasol"
	@echo "  make api         Run FastAPI on http://localhost:8000"
	@echo "  make web         Run the Next.js dashboard on http://localhost:3000"
	@echo "  make test        Run deterministic scoring tests"
	@echo "  make bench       Benchmark per-customer N+1 vs one set-based pass"
	@echo "  make up          Containerise the app tier against host Exasol Personal"
	@echo "  make up-fallback Start the optional exasol/docker-db stack instead"
	@echo "  make down        Stop the Docker stack"

install:
	python -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r backend/requirements.txt

status:
	exakit status

start:
	exakit start

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

up-fallback:
	docker compose -f docker-compose.docker-db.yml up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

clean:
	rm -rf frontend/.next backend/.pytest_cache .pytest_cache seed.log benchmark.json
