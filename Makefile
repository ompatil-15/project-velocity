.PHONY: server

server:
	source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000

db:
	sqlite3 db/checkpoints.sqlite