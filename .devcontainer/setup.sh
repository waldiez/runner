#!/usr/bin/env bash

# On startup actions:
# - upgrade pip
# - install requirements
# - if .git is a directory, we are ok
# - if .git is a file, check if it is a submodule
#   - if it is a submodule and the original git dir is found, we are ok
#   - if it the root git dir is not found, backup the .git file and reinitialize the repository
#     (we cannot commit if we cannot resolve the parent git dir)
# - install pre-commit hooks

HERE="$(dirname "$(readlink -f "$0")")"
ROOT_DIR="$(dirname "$HERE")"

# podman/docker
sudo chown -R "$(id -u):$(id -g)" "$HOME/.local"  # in case this is a volume

cd "$ROOT_DIR" || exit 1

pip install --upgrade pip
pip install -r requirements/all.txt

if [ -z "$SSH_AUTH_SOCK" ]; then
   # Check for a currently running instance of the agent
   # shellcheck disable=SC2009,SC2126
   RUNNING_AGENT="$(ps -ax | grep 'ssh-agent -s' | grep -v grep | wc -l | tr -d '[:space:]')"
   if [ "$RUNNING_AGENT" = "0" ]; then
        # Launch a new instance of the agent
        ssh-agent -s &> "${HOME}/.ssh/ssh-agent"
   fi
   eval "$(cat "${HOME}/.ssh/ssh-agent")" > /dev/null || true
   ssh-add 2> /dev/null
fi

if [ -d ".git" ]; then
    pre-commit install
    exit 0
fi

if [ ! -f ".git" ]; then
    git init --initial-branch=main
    pre-commit install
    exit 0
fi

GITFILE=$(cat .git)
if [ -d "$GITFILE" ]; then
    pre-commit install
    exit 0
fi

echo "Backing up .git file to .git.bak"
mv .git .git.bak
git init --initial-branch=main
echo "Warning: .git file was a submodule, reinitialized the repository."
echo "Please check the .git.bak file for the submodule path."
pre-commit install
echo "Make sure you 'python3 .devcontainer/teardown.py'"
echo "to restore the original .git file if needed"
echo "when you are done with the devcontainer."

# check if we can connect to the database and to the redis server
python3 scripts/pre_start.py
