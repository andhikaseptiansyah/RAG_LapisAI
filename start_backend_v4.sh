#!/usr/bin/env sh
set -eu
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_ROOT/backend"
export PYTHONPATH=.
echo "Starting LapisAI backend build rag-multilingual-v6-20260723"
exec python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
