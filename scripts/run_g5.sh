#!/usr/bin/env bash
# Runs the pre-registered PeerRush fill-attack jobs in two memory-bounded stages (skips finished outputs).
cd "$(dirname "$0")/.."
jobs_a=$( { for g in $(seq 0 29); do echo "0:und@$g"; echo "10:und@$g"; done
            for g in $(seq 0 3 27); do for a in d1 d3c8 d3c16; do echo "10:$a@$g"; done; done; } )
jobs_b=$( { for g in $(seq 0 9); do echo "25:und@$g"; done
            for g in 0 6 12 18 24; do for a in d1 d3c8 d3c16; do echo "25:$a@$g"; done; done; } )
run() { j=$1; n=results/g5/pr_$(echo "$j" | sed 's/:/_/;s/@/_at/').npz
        [ -f "$n" ] || uv run python scripts/g5_peerrush.py --job "$j" > "results/g5/logs/$(basename "$n" .npz).log" 2>&1; }
export -f run
echo "$jobs_a" | xargs -P 4 -I{} bash -c 'run {}'
echo "stage A done $(date)" >> results/g5/STATUS
echo "$jobs_b" | xargs -P 2 -I{} bash -c 'run {}'
echo "stage B done $(date)" >> results/g5/STATUS
