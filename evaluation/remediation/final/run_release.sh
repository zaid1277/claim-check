#!/bin/bash
# Run from the repository root. Existing user servers are never stopped here.
# Remediation pass 5, part 17: single frozen (remediated) system, new
# confirmation holdout. Run once.
set -euo pipefail
export PYTHONPATH=api
export HF_HUB_OFFLINE=1
export DATABASE_URL
DATABASE_URL=$(sed 's|claim_check@/|claim_check@localhost/|' work/postgres-test-url)
backend_pid=''
web_pid=''
cleanup() {
  if [[ -n "$backend_pid" ]]; then
    kill "$backend_pid" 2>/dev/null || true
    wait "$backend_pid" 2>/dev/null || true
  fi
  if [[ -n "$web_pid" ]]; then
    kill "$web_pid" 2>/dev/null || true
    wait "$web_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM
start_backend() {
  api/.venv/bin/uvicorn application:app --app-dir evaluation/remediation/final --host 127.0.0.1 --port 8103 > "evaluation/remediation/final/results/api.log" 2>&1 &
  backend_pid=$!
  for _ in $(seq 1 60); do
    if ! kill -0 "$backend_pid" 2>/dev/null; then
      echo 'Evaluation API failed to start.' >&2
      exit 1
    fi
    if curl -fsS http://127.0.0.1:8103/api/v1/health >/dev/null 2>&1; then return; fi
    sleep 1
  done
  echo 'Evaluation API did not become ready.' >&2
  exit 1
}
start_web() {
  (cd web && API_BASE_URL=http://127.0.0.1:8103 node ../evaluation/final/serve-web.mjs) > "evaluation/remediation/final/results/web.log" 2>&1 &
  web_pid=$!
  for _ in $(seq 1 60); do
    if ! kill -0 "$web_pid" 2>/dev/null; then
      echo 'Evaluation web server failed to start.' >&2
      exit 1
    fi
    if curl -fsS http://127.0.0.1:3103 >/dev/null 2>&1; then return; fi
    sleep 1
  done
  echo 'Evaluation web server did not become ready.' >&2
  exit 1
}
if [[ ! -f evaluation/remediation/final/results/final-pairs.json ]]; then
  api/.venv/bin/python evaluation/remediation/final/run_pairs.py \
    --model MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli \
    --policy production --split test --unlock-test --nli-only \
    --minimum-evidence 0.20 --dominance-ratio 2.0 \
    --output evaluation/remediation/final/results/final-pairs.json \
    > evaluation/remediation/final/results/final-pairs.log 2>&1
fi
start_backend
start_web
for mode in controlled modal urls; do
  node evaluation/remediation/final/product.mjs "$mode" > "evaluation/remediation/final/results/product-$mode.log" 2>&1
done
cleanup
api/.venv/bin/python evaluation/remediation/final/summarize.py
