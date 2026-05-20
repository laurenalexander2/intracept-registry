#!/usr/bin/env bash
# engine/run-task-1.sh — produce the Task 1 coverage report and commit it.
#
# Run from the repo root:
#   bash engine/run-task-1.sh
#
# Created because the agent's sandbox shell was unavailable; this is a
# one-shot helper that fulfils the "Output" + "Commit hygiene" sections of
# dispatch-notes/prompt-task-1-coverage.md.

set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"

echo "[task-1] running analyzer ..."
"$PYTHON" engine/coverage.py

echo "[task-1] checking output files ..."
for f in COVERAGE_REPORT.md coverage_data.json; do
    if [[ ! -f "$f" ]]; then
        echo "[task-1] ERROR: expected file $f was not produced"
        exit 1
    fi
done

echo "[task-1] staging and committing the two output files ..."
git add COVERAGE_REPORT.md coverage_data.json
git commit -m "task-1: coverage report from real session data"

echo "[task-1] done."
echo "  - COVERAGE_REPORT.md and coverage_data.json are committed."
echo "  - engine/coverage.py, engine/run-task-1.sh, progress-task-1.json,"
echo "    and dispatch-notes/task-1-*.md are still uncommitted; commit"
echo "    those separately with task-1-prefixed messages."
