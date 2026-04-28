#!/usr/bin/env bash
# docker/entrypoint.sh — start command dispatcher
set -euo pipefail

mkdir -p /app/data/journal /app/data/csv_imports /app/data/graphify

case "${1:-run}" in
  run)
    exec asklivermore-bot run --tick-seconds "${TICK_SECONDS:-60}"
    ;;
  once)
    exec asklivermore-bot once
    ;;
  replay)
    shift
    exec asklivermore-bot replay "$@"
    ;;
  shell)
    exec /bin/bash
    ;;
  *)
    exec "$@"
    ;;
esac
