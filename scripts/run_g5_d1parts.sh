#!/usr/bin/env bash
# Post-hoc diagnostic: D1 split into its three changes, f = 0 and 10%, clocks 0, 3, 6, 9 (one worker).
cd "$(dirname "$0")/.."
for g in 0 3 6 9; do for f in 0 10; do for a in d1w d1t d1i; do
  n=results/g5/pr_${f}_${a}_at${g}.npz
  [ -f "$n" ] || uv run python scripts/g5_peerrush.py --job "$f:$a@$g" > "results/g5/logs/pr_${f}_${a}_at${g}.log" 2>&1
done; done; done
echo "d1 parts done $(date)" >> results/g5/STATUS
