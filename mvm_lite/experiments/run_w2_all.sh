#!/usr/bin/env bash
# Full W2 chain: grouped (primary IID), forward (primary replay), random (leakage demonstration).
set -euo pipefail
cd "$(dirname "$0")/.."
uv run python experiments/w2_rq1.py --split grouped --seeds 0 1 2 3 4
uv run python experiments/w2_rq1.py --split forward --seeds 0 1 2 3 4
uv run python experiments/w2_rq1.py --split random --seeds 0 1 2
echo "ALL W2 RUNS DONE"
