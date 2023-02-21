set dotenv-load := false

venv_path := justfile_directory() + "/.venv"
venv_script := venv_path + "/bin/activate"
bin := venv_path + "/bin/"

default:
    @just --list

setup-venv:
    python3.9 -m venv .venv
    attr -s com.dropbox.ignored -V 1 .venv
    just install-deps

install-deps-dev:
    {{bin}}pip install pip-tools==6.2.0
    {{bin}}pip-compile --verbose
    {{bin}}pip-compile --verbose requirements-dev.in
    # rm -r justfile_directory() + "/.venv/lib/python3.9/site-packages/tests"
    # delete .venv/lib/python3.9/site-packages/tests
    {{bin}}pip-sync requirements*.txt

install-deps:
    {{bin}}pip install -r requirements.txt

run-tests:
    {{bin}}coverage run -m ward
    -{{bin}}coverage html
    {{bin}}coverage report

serve-dev:
    {{bin}}uvicorn trek.server:make_app --factory --reload

serve:
    {{bin}}uvicorn trek.server:make_app --factory --host 0.0.0.0 --port 5007

schedule:
    {{bin}}python -m trek --mode=scheduler


_assert-no-unstaged-changes:
    git update-index --refresh
    git diff-index --quiet HEAD --

_assert-docker-machine-active:
    # If no docker-machine active, run:
    # docker-machine env docker-droplet; and eval (docker-machine env docker-droplet)
    # docker-machine active | grep -q 'docker-droplet'
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
    docker context use droplet-ctx
    just _deploy
    just _git-push
