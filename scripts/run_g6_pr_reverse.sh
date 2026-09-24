#!/usr/bin/env bash
# Second PeerRush worker: the co-primary f = 25% D4 jobs in reverse clock order (memory-gated, skips finished outputs).
cd "$(dirname "$0")/.."
waitmem() { while [ "$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo)" -lt "$1" ]; do sleep 30; done; }
for g in $(seq 29 -1 0); do
  n=results/g5/pr_25_d4_at$g.npz
  [ -f "$n" ] && continue
  pgrep -f "g5_peerrush.py --job 25:d4@$g\$" > /dev/null && break      # the forward worker has reached this job
  waitmem 12
  uv run python scripts/g5_peerrush.py --job "25:d4@$g" > "results/g5/logs/pr_25_d4_at$g.log" 2>&1 || echo "FAILED 25:d4@$g" >> results/g5/g6_failed.txt
done
