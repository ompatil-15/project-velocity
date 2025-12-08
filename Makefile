.PHONY: server

server:
	source venv/bin/activate && uvicorn app.main:app --reload

db:
	sqlite3 db/checkpoints.sqlite