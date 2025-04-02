#!/usr/bin/env sh

set -e  # Fail on error

# Perform pre-start checks, initial data setup and start the application

# (in container)
# app root: /home/user/app
# scripts root (where this file is): /home/user/scripts
HERE="$(dirname "$(readlink -f "$0")")"
ROOT_DIR="$(dirname "$HERE")"


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
    pre_start_checks
    initial_data_setup
    echo "Starting uvicorn server..."
    # no args, it will load the configuration from the environment
    python3 -m app
}

start_worker() {
    pre_start_checks
    initial_data_setup
    echo "Starting worker..."
    # --no-configure-logging
    #   Use this parameter if your application configures custom logging. (default: True)
    # --log-level {INFO,WARNING,DEBUG,ERROR,FATAL}
    #       worker log level (default: INFO)
    LOG_LEVEL="$(get_log_level)"
    taskiq worker app.worker:broker --workers 1 --max-tasks-per-child 3 --log-level "$LOG_LEVEL"
}

start_scheduler() {
    pre_start_checks
    initial_data_setup
    # --no-configure-logging
    #   Use this parameter if your application configures custom logging. (default: True)
    # --log-level {INFO,WARNING,DEBUG,ERROR,FATAL}
    #       worker log level (default: INFO)
    LOG_LEVEL="$(get_log_level)"
    taskiq scheduler app.worker:scheduler --log-level "$LOG_LEVEL"
}

start_broker() {
    pre_start_checks
    initial_data_setup
    # both worker and scheduler
    echo "Starting Broker (worker and scheduler)..."

    # Trap SIGTERM and SIGINT to propagate to both worker and scheduler
    trap 'kill -- -$$' TERM INT

    taskiq worker app.worker:broker --workers 1 --log-level "$LOG_LEVEL" &
    WORKER_PID=$!

    taskiq scheduler app.worker:scheduler --log-level "$LOG_LEVEL" &
    SCHEDULER_PID=$!

    # Wait for both processes
    wait "$WORKER_PID" "$SCHEDULER_PID"
}

main() {
    case "${1:-uvicorn}" in
        uvicorn)
            start_uvicorn
            ;;
        worker)
            start_worker
            ;;
        scheduler)
            start_scheduler
            ;;
        broker)
            start_broker
            ;;
        *)
            echo "Invalid command: ${1}"
            exit 1
            ;;
    esac
}

main "$@"
