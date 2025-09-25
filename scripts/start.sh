#!/usr/bin/env sh

set -e  # Fail on error

# Perform pre-start checks, initial data setup and start the application

# (in container)
# app root: "/home/waldiez/app"
# scripts root (where this file is): /home/waldiez/scripts
HERE="$(dirname "$(readlink -f "$0")")"
ROOT_DIR="$(dirname "$HERE")"
DEV="false"

pre_start_checks() {
    if [ -f "${HERE}/pre_start.py" ]; then
        echo "Performing pre-start checks..."
        python3 "${HERE}/pre_start.py"
    fi
}

initial_data_setup() {
    if [ -f "${HERE}/initial_data.py" ]; then
        echo "Setting up initial data..."
        python3 "${HERE}/initial_data.py"
    fi
}

get_log_level() {
    DOT_ENV_FILE="${ROOT_DIR}/.env"
    if [ -f "$DOT_ENV_FILE" ]; then
        # shellcheck disable=SC1090
        . "$DOT_ENV_FILE"
    fi
    LOG_LEVEL="${LOG_LEVEL:-INFO}"
    LOG_LEVEL=$(echo "$LOG_LEVEL" | tr '[:lower:]' '[:upper:]')
    case "$LOG_LEVEL" in
        INFO|WARNING|DEBUG|ERROR|FATAL) ;;
        *) LOG_LEVEL="INFO" ;;
    esac
    echo "$LOG_LEVEL"
}

start_uvicorn() {
    if [ "$DEV" = "true" ] && [ -f "${ROOT_DIR}/.env" ]; then
        echo "Removing .env file..."
        # the keys should be in env variables (not in env)
        # the .env file will be automatically created by the app
        rm -f "${ROOT_DIR}/.env" || true
    fi
    pre_start_checks
    if [ "$DEV" = true ] && [ -f "${HERE}/drop.py" ]; then
        echo "Dropping database..."
        python3 "${HERE}/drop.py" --force
    fi
    initial_data_setup
    echo "Starting uvicorn server..."
    if [ "${DEV}" = "true" ]; then
        # make sure WALDIEZ_RUNNER_DEV is set to 1
        if [ -f "${ROOT_DIR}/.env" ]; then
            # shellcheck disable=SC1091
            . "${ROOT_DIR}/.env"
        fi
        sed -i "s/^WALDIEZ_RUNNER_DEV=.*/WALDIEZ_RUNNER_DEV=1/" "${ROOT_DIR}/.env"
        python3 -m waldiez_runner --dev
    else
        # no args, it will load the configuration from the environment
        python3 -m waldiez_runner
    fi
}

install_extras() {
  if [ -n "${WALDIEZ_RUNNER_EXTRA_PACKAGES:-}" ]; then
    echo "Installing extra packages: ${WALDIEZ_RUNNER_EXTRA_PACKAGES}"
    # Optional pip flags (indexes, trusted hosts, etc.)
    PIP_FLAGS=${EXTRA_PIP_FLAGS:-}
    # If we have /opt/base-locked.txt at build time, let's use it as a constraint
    CONS_FLAG=""
    if [ -f /opt/base-locked.txt ]; then
      CONS_FLAG="-c /opt/base-locked.txt"
      echo "Using constraints from /opt/base-locked.txt"
    fi
    # shellcheck disable=SC2086
    python -m pip install --no-cache-dir --upgrade-strategy only-if-needed ${PIP_FLAGS} ${CONS_FLAG} ${WALDIEZ_RUNNER_EXTRA_PACKAGES}
  else
    echo "No WALDIEZ_RUNNER_EXTRA_PACKAGES set. Skipping extras."
  fi
}

start_broker() {
    install_extras
    echo "Starting broker..."
    # --no-configure-logging
    #   Use this parameter if your application configures custom logging. (default: True)
    # --log-level {INFO,WARNING,DEBUG,ERROR,FATAL}
    #       worker log level (default: INFO)
    LOG_LEVEL="$(get_log_level)"
    taskiq worker waldiez_runner.worker:broker --workers 1 --log-level "$LOG_LEVEL"
}

start_scheduler() {
    # --no-configure-logging
    #   Use this parameter if your application configures custom logging. (default: True)
    # --log-level {INFO,WARNING,DEBUG,ERROR,FATAL}
    #       worker log level (default: INFO)
    LOG_LEVEL="$(get_log_level)"
    taskiq scheduler waldiez_runner.worker:scheduler --log-level "$LOG_LEVEL"
}

start_broker_and_scheduler() {
    pre_start_checks
    initial_data_setup
    # both broker and scheduler
    echo "Starting worker (broker and scheduler)..."

    # Trap SIGTERM and SIGINT to propagate to both worker and scheduler
    trap 'kill -- -$$' TERM INT

    taskiq worker waldiez_runner.worker:broker --workers 1 --log-level "$LOG_LEVEL" &
    WORKER_PID=$!

    taskiq scheduler waldiez_runner.worker:scheduler --log-level "$LOG_LEVEL" &
    SCHEDULER_PID=$!

    # Wait for both processes
    wait "$WORKER_PID" "$SCHEDULER_PID"
}

main() {
    case "${1:-uvicorn}" in
        uvicorn)
            start_uvicorn
            ;;
        scheduler)
            start_scheduler
            ;;
        broker)
            start_broker
            ;;
        worker)
            start_broker_and_scheduler
            ;;
        dev)
            DEV="true"
            start_uvicorn
            ;;
        *)
            echo "Invalid command: ${1}"
            exit 1
            ;;
    esac
}

main "$@"
