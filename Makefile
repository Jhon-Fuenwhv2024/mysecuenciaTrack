.PHONY: test sample api web docker

sample:
	cd backend && . .venv/bin/activate && PYTHONPATH=$$PWD python ../scripts/generate_sample.py

test:
	cd backend && . .venv/bin/activate && cd .. && SEPARATION_BACKEND=mock PYTHONPATH=backend pytest -q

api:
	SEPARATION_BACKEND=$${SEPARATION_BACKEND:-mock} PYTHONPATH=backend \
	  backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8765 --app-dir backend

web:
	cd frontend && npm run dev -- --host 0.0.0.0 --port 3847

docker:
	docker compose up --build
