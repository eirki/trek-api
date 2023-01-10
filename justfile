set dotenv-load := false

venv_path := justfile_directory() + "/.venv"
venv_script := venv_path + "/bin/activate"

default:
    @just --list

setup-venv:
    #!/usr/bin/env bash
    python3.9 -m venv .venv
    attr -s com.dropbox.ignored -V 1 .venv
    source {{venv_script}}
    just install-deps

install-deps-dev:
    #!/usr/bin/env bash
    source {{venv_script}}
    pip install pip-tools==6.2.0
    pip-compile --verbose
    pip-compile --verbose requirements-dev.in
    pip-sync requirements*.txt

install-deps:
    #!/usr/bin/env bash
    source {{venv_script}}
    pip install -r requirements.txt

run-tests:
    #!/usr/bin/env bash
    source {{venv_script}}
    coverage run -m ward
    # -coverage html
    coverage report

serve-dev:
    #!/usr/bin/env bash
    source {{venv_script}}
    uvicorn trek.main:app --reload

serve:
    #!/usr/bin/env bash
    source {{venv_script}}
    uvicorn trek.main:app --host 0.0.0.0 --port 5007

migrate:
    #!/usr/bin/env bash
    source {{venv_script}}
    python -m trek --mode=migrate


_assert-no-unstaged-changes:
    git update-index --refresh
    git diff-index --quiet HEAD --

_assert-docker-machine-active:
    # If no docker-machine active, run:
    # docker-machine env docker-droplet; and eval (docker-machine env docker-droplet)
    docker-machine active | grep -q 'docker-droplet'
    docker context use droplet-ctx

_deploy:
    docker-compose build
    docker-compose up -d

_git-push:
    git push --no-verify

push:
    #!/usr/bin/env fish
    just _assert-no-unstaged-changes
    just run-tests
    eval (docker-machine env docker-droplet)
    just _deploy
    just _git-push
