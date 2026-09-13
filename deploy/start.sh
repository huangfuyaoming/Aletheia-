#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# This container exports OMP_NUM_THREADS=0, which libgomp rejects ("Invalid value").
# Pin a sane value so torch/OpenMP start cleanly; only set if unusable.
if [ "${OMP_NUM_THREADS:-0}" -lt 1 ] 2>/dev/null; then
  export OMP_NUM_THREADS=8
fi
# app settings load .env. Never use --preload, --reload, or multiple workers.
exec gunicorn --workers 1 --worker-class gthread --threads 4 \
  --bind 0.0.0.0:6006 --timeout 300 --graceful-timeout 300 \
  --access-logfile - --error-logfile - 'app:create_app()'
