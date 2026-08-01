#!/usr/bin/env bash
#
# The one command. Fixtures in, ranked matches out, no services required.
#
# Everything runs against a SQLite file at .data/xfun.db. There is no database
# server, no container, and no credentials, because the point of this repository
# is that someone can clone it and see the structure work.
#
set -euo pipefail

cd "$(dirname "$0")/.."

BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'

echo "${BOLD}xFUN — walking skeleton${RESET}"
echo "${DIM}Placeholder models on fixture data. These scores predict nothing."
echo "See docs/STUBS.md.${RESET}"
echo

# uv if available, otherwise plain python3 -- the pipeline adds the workspace
# packages to sys.path itself, so a fresh clone works either way.
if command -v uv >/dev/null 2>&1; then
  RUN=(uv run python)
else
  RUN=(python3)
  echo "${DIM}uv not found; using system python3.${RESET}"
  echo "${DIM}Install uv for the full workspace: https://docs.astral.sh/uv/${RESET}"
  echo
fi

echo "${BOLD}pipeline${RESET}"
"${RUN[@]}" scripts/pipeline.py

echo
echo "${BOLD}api${RESET}  http://localhost:8000/v1/matches?from=2026-08-01&to=2026-08-31"
echo "${DIM}      docs at http://localhost:8000/docs${RESET}"
echo "${DIM}      web:  pnpm install && pnpm client:generate && pnpm web:dev${RESET}"
echo

if ! "${RUN[@]}" -c "import fastapi, uvicorn" 2>/dev/null; then
  echo "FastAPI is not installed, so the API will not start."
  echo "Run: uv sync"
  exit 0
fi

exec "${RUN[@]}" -m uvicorn xfun_api:app --host 127.0.0.1 --port 8000
