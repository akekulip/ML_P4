#!/usr/bin/env bash
# Unattended driver for the W3 / W4 sweeps. Independent of any Claude session.
#
# Each unit of work (split mode x seed) runs as its own process with a timeout, up to 3 attempts.
# A crash or OOM kill fails only that unit; units whose part file already exists are skipped, so
# re-running this script resumes where it stopped. Progress: results/overnight/STATUS; one log
# per unit in results/overnight/logs/.
#
# Usage: experiments/overnight.sh w3|w4 [parallel_jobs]
set -uo pipefail
cd "$(dirname "$0")/.."
STAGE=${1:?usage: overnight.sh w3|w4 [parallel_jobs]}
JOBS=${2:-4}
OV=results/overnight
mkdir -p "$OV/logs"
status() { echo "$(date '+%F %T') [$STAGE] $*" | tee -a "$OV/STATUS"; }

case "$STAGE" in
  w3) SCRIPT=experiments/w3_locality.py; PARTS=results/w3/parts; REPORT=experiments/w3_report.py ;;
  w4) SCRIPT=experiments/w4_cache.py;    PARTS=results/w4/parts; REPORT=experiments/w4_report.py ;;
  *) echo "unknown stage $STAGE"; exit 2 ;;
esac

run_unit() {  # $1=mode $2=seed; called by xargs
  local mode=$1 seed=$2 log="$OV/logs/${STAGE}_${1}_seed${2}.log"
  for attempt in 1 2 3; do
    if [ -f "$PARTS/${mode}_seed${seed}.parquet" ]; then return 0; fi
    echo "--- attempt $attempt $(date '+%T')" >> "$log"
    if timeout 3h uv run python "$SCRIPT" --job "$mode" "$seed" >> "$log" 2>&1; then
      echo "$(date '+%F %T') [$STAGE] unit $mode/$seed OK (attempt $attempt)" >> "$OV/STATUS"
      return 0
    fi
    echo "$(date '+%F %T') [$STAGE] unit $mode/$seed FAILED attempt $attempt (exit $?), see $log" >> "$OV/STATUS"
    sleep 30
  done
  return 1
}
export -f run_unit
export STAGE SCRIPT PARTS OV

status "START (parallel=$JOBS)"
printf '%s\n' grouped\ 0 grouped\ 1 grouped\ 2 grouped\ 3 grouped\ 4 forward\ 0 forward\ 1 forward\ 2 forward\ 3 forward\ 4 \
  | xargs -P "$JOBS" -L 1 bash -c 'run_unit "$0" "$1"'
if uv run python "$SCRIPT" --merge >> "$OV/logs/${STAGE}_merge.log" 2>&1; then
  status "MERGE OK"
else
  status "MERGE FAILED (some unit never completed), see $OV/logs/${STAGE}_merge.log"; exit 1
fi
if uv run python "$REPORT" >> "$OV/logs/${STAGE}_report.log" 2>&1; then
  status "REPORT OK"
  status "DONE"
else
  status "REPORT FAILED, see $OV/logs/${STAGE}_report.log"; exit 1
fi
