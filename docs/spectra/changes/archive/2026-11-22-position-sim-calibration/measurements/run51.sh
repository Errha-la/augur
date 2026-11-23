#!/usr/bin/env bash
# Re-analyze benchmark and evaluation races for lightgbm and baseline, then run the bench.
set -u
# Paths are relative to the repository root (the script was first run from the
# position-sim-calibration worktree, with the venv and data of the main checkout).
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
PY="$ROOT/backend/.venv/bin/python"
DATA="$ROOT/data"
OUT="$ROOT/bench"
cd "$ROOT/backend"
export PYTHONPATH=src
RACES="2024-01-bahrain-grand-prix 2024-24-abu-dhabi-grand-prix 2024-12-british-grand-prix 2024-13-hungarian-grand-prix 2024-14-belgian-grand-prix 2024-15-dutch-grand-prix 2024-16-italian-grand-prix 2024-17-azerbaijan-grand-prix 2024-18-singapore-grand-prix 2024-19-united-states-grand-prix 2024-20-mexico-city-grand-prix 2024-21-s-o-paulo-grand-prix 2024-22-las-vegas-grand-prix 2024-23-qatar-grand-prix"
start=$(date +%s)
for model in lightgbm baseline; do
  for race in $RACES; do
    "$PY" -W ignore -m augur.analyze --race "$race" --model "$model" --data-dir "$DATA" 2>&1 | sed "s/^/[$model] /"
  done
done
echo "analysis done in $(( $(date +%s) - start )) s"
for model in lightgbm baseline; do
  "$PY" -W ignore -m augur.bench --model "$model" --data-dir "$DATA" --out-dir "$OUT"
  "$PY" -W ignore -m augur.bench --model "$model" --eval --data-dir "$DATA" --out-dir "$OUT"
done
echo "all done in $(( $(date +%s) - start )) s"
