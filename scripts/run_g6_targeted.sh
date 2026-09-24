#!/usr/bin/env bash
# Targeted pilot grid (exploratory): 4 arms x 2 victim sets x clocks 0-9, primary day; memory-gated, skips finished outputs.
cd "$(dirname "$0")/.."
waitmem() { while [ "$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo)" -lt "$1" ]; do sleep 30; done; }
export -f waitmem
run() { j=$1; n=results/g2/g6t_$(echo "$j" | sed 's/:/_/g;s/@/_at/').npz
        [ -f "$n" ] || { waitmem 6; uv run python scripts/g6_targeted.py --job "$j" > /dev/null 2>&1 || echo "FAILED targeted $j" >> results/g2/g6_failed.txt; }; }
export -f run
for g in $(seq 0 9); do for v in vul top; do for a in und1 d4k1 d4k2 d5k2; do echo "p:$v:$a@$g"; done; done; done | xargs -P "${TG_WORKERS:-2}" -I{} bash -c 'run {}'
echo "g6 targeted done $(date)" >> results/g5/STATUS
