.PHONY: install run run-frontend test check

install:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

run:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-frontend:
	cd frontend && python3 -m http.server 5500

test:
	cd backend && . .venv/bin/activate && PYTHONPATH=. pytest -q

check:
	cd backend && . .venv/bin/activate && PYTHONPATH=. pytest -q
	node --check frontend/app.js
