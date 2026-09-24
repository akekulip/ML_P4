#!/usr/bin/env bash
# Third PeerRush worker: the no-attack D4 arm (needed for the excess and M1), memory-gated, skips finished outputs.
cd "$(dirname "$0")/.."
waitmem() { while [ "$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo)" -lt "$1" ]; do sleep 30; done; }
for g in $(seq 0 29); do
  n=results/g5/pr_0_d4_at$g.npz
  [ -f "$n" ] && continue
  waitmem 8
  uv run python scripts/g5_peerrush.py --job "0:d4@$g" > "results/g5/logs/pr_0_d4_at$g.log" 2>&1 || echo "FAILED 0:d4@$g" >> results/g5/g6_failed.txt
done
