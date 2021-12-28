set dotenv-load := false


_default:
  @just --list --unsorted


run-dev:
	uvicorn trek.main:app --reload


run:
	uvicorn trek.main:app


test:
	coverage run -m ward
	-coverage html
	coverage report


migrate:
	python -m trek --mode=migrate


install-deps:
	pip-compile requirements.in
	pip-compile requirements-dev.in
	pip-sync requirements*.txt


_assert-no-unstaged-changes:
	git update-index --refresh
	git diff-index --quiet HEAD --

_assert-docker-machine-active:
	# If no docker-machine active, run:
	# docker-machine env docker-droplet; and eval (docker-machine env docker-droplet)
	docker-machine active | grep -q 'docker-droplet'

_deploy:
	docker-compose build
	docker-compose up -d

_git-push:
	git push --no-verify

push: _assert-no-unstaged-changes _assert-docker-machine-active test _deploy _git-push
