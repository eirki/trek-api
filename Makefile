dev:
	uvicorn trek.main:app --reload

run:
	uvicorn trek.main:app

test:
	ward

migrate:
	python -m trek --mode=migrate

deps:
	pip-compile requirements.in
	pip-compile requirements-dev.in
	pip-sync requirements*.txt
