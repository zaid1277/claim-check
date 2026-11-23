#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
api/.venv/bin/ruff check api evaluation
api/.venv/bin/ruff format --check api evaluation
api/.venv/bin/python -m pytest api/tests -q
cd web
npm run lint
npm run format:check
npm run typecheck
npm test
npm run test:extension
npm run build
if [[ "${1:-}" == "--browser" ]]; then
  npm run test:e2e -- --config=playwright.release.config.ts
fi
