#!/usr/bin/env bash
# G6 grid (docs/preregistration.md): MAWI jobs (4 workers) and PeerRush jobs (workers given by $PR_WORKERS, default 1) in priority order.
#   scripts/run_g6.sh mawi|pr      runs one stream; each job skips if its output exists.
cd "$(dirname "$0")/.."
kind=$1
# memory gate: wait for MemAvailable >= MIN_GB (PeerRush jobs peak at about 8.6 GB; MAWI at about 4 GB) so the kernel OOM-killer never fires
# (it would pick the largest process on the machine, which may belong to another session)
waitmem() { while [ "$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo)" -lt "$1" ]; do sleep 30; done; }
export -f waitmem
mkdir -p results/g5/logs results/g2/logs6
python3 scripts/g6_jobs.py "$kind" --check || exit 1
if [ "$kind" = mawi ] || [ "$kind" = mawi2 ] || [ "$kind" = mawi3 ]; then
  run() { s=${1%% *}; j=${1#* }
          n=$(python3 - "$s" "$j" <<'PY'
import sys; sys.path.insert(0, "scripts"); from g6_jobs import _name; print(_name("", f"{sys.argv[1]} {sys.argv[2]}"))
PY
)
          [ -f "results/g2/$n" ] || { waitmem ${MIN_GB:-6}; uv run python scripts/$s --job "$j" > "results/g2/logs6/$n.log" 2>&1 || echo "FAILED $1" >> results/g2/g6_failed.txt; }; }
  export -f run
  python3 scripts/g6_jobs.py "$kind" | xargs -P "${MAWI_WORKERS:-4}" -d '\n' -I{} bash -c 'run "{}"'
  echo "g6 $kind done $(date)" >> results/g5/STATUS
else
  run() { j=$1; n=results/g5/pr_$(echo "$j" | sed 's/:/_/;s/@/_at/').npz
          [ -f "$n" ] || { waitmem ${MIN_GB:-12}; uv run python scripts/g5_peerrush.py --job "$j" > "results/g5/logs/$(basename "$n" .npz).log" 2>&1 || echo "FAILED $j" >> results/g5/g6_failed.txt; }; }
  export -f run
  python3 scripts/g6_jobs.py pr | { if [ -n "$REVERSE" ]; then tac; else cat; fi; } | xargs -P "${PR_WORKERS:-1}" -I{} bash -c 'run {}'
  echo "g6 pr done $(date)" >> results/g5/STATUS
fi
