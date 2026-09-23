#!/usr/bin/env bash
# Re-run W2 -> W3 -> W4 after the 2026-09-22 code-review fixes (seed-mixed group partition,
# exact decayed-LFU eviction order, static warm-up exclusion, phase-boundary recovery).
# Gates (quick runs) precede every sweep; any failure stops the chain. Status: results/overnight/STATUS.
set -euo pipefail
cd "$(dirname "$0")/.."
OV=results/overnight; mkdir -p "$OV/logs"
status() { echo "$(date '+%F %T') [rerun] $*" | tee -a "$OV/STATUS"; }
trap 'status "FAILED at line $LINENO"' ERR
status "START"
uv run pytest -q > "$OV/logs/rerun_pytest.log" 2>&1 && status "pytest OK"
uv run python experiments/w2_rq1.py --split grouped --seeds 0 1 --quick > "$OV/logs/rerun_w2_quick.log" 2>&1 && status "w2 quick gate OK"
rm -rf results/w2/grouped results/w2/forward results/w2/grouped_quick
uv run python experiments/w2_rq1.py --split grouped > "$OV/logs/rerun_w2_grouped.log" 2>&1 && status "w2 grouped OK"
uv run python experiments/w2_rq1.py --split forward > "$OV/logs/rerun_w2_forward.log" 2>&1 && status "w2 forward OK"
uv run python experiments/w2_report.py > "$OV/logs/rerun_w2_report.log" 2>&1 && cp results/w2/tables.md docs/results_w2.md && status "w2 report OK"
uv run python experiments/w3_locality.py --quick > "$OV/logs/rerun_w3_quick.log" 2>&1 && status "w3 quick gate OK (incl. full alignment check)"
rm -rf results/w3/parts results/w3/locality.parquet results/w3/drift_hourly.parquet
experiments/overnight.sh w3 4 && status "w3 OK"
uv run python experiments/w4_cache.py --quick > "$OV/logs/rerun_w4_quick.log" 2>&1 && status "w4 quick gate OK"
rm -rf results/w4/parts results/w4/summary.parquet results/w4/hourly.parquet
experiments/overnight.sh w4 4 && status "w4 OK"
uv run python experiments/w4_recovery.py > "$OV/logs/rerun_w4_recovery.log" 2>&1 && status "w4 recovery OK"
status "DONE"
