#!/bin/bash
# Run from the repository root. Existing user servers are never stopped here.
# Group 4: single frozen system, new Hyper holdout. Run once.
set -euo pipefail
export PYTHONPATH=api
export HF_HUB_OFFLINE=1
export DATABASE_URL
DATABASE_URL=$(sed 's|claim_check@/|claim_check@localhost/|' ../../work/postgres-test-url)
backend_pid=''
cleanup() {
  if [[ -n "$backend_pid" ]]; then
    kill "$backend_pid" 2>/dev/null || true
    wait "$backend_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM
start_backend() {
  api/.venv/bin/uvicorn application:app --app-dir evaluation/hyper/final --host 127.0.0.1 --port 8102 > "evaluation/hyper/final/results/api.log" 2>&1 &
  backend_pid=$!
  for _ in $(seq 1 60); do
    if ! kill -0 "$backend_pid" 2>/dev/null; then
      echo 'Evaluation API failed to start.' >&2
      exit 1
    fi
    if curl -fsS http://127.0.0.1:8102/api/v1/health >/dev/null 2>&1; then return; fi
    sleep 1
  done
  echo 'Evaluation API did not become ready.' >&2
  exit 1
}
if [[ ! -f evaluation/hyper/final/results/final-pairs.json ]]; then
  api/.venv/bin/python evaluation/hyper/final/run_pairs.py \
    --model MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli \
    --policy production --split test --unlock-test --nli-only \
    --minimum-evidence 0.20 --dominance-ratio 2.0 \
    --output evaluation/hyper/final/results/final-pairs.json \
    > evaluation/hyper/final/results/final-pairs.log 2>&1
fi
start_backend
for mode in controlled modal urls live; do
  node evaluation/hyper/final/product.mjs "$mode" > "evaluation/hyper/final/results/product-$mode.log" 2>&1
done
cleanup
api/.venv/bin/python evaluation/hyper/final/summarize.py
