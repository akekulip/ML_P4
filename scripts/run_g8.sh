#!/usr/bin/env bash
# G8 semantic-change matrix (docs/preregistration.md, G8 entry): fold hash on, delta = 0, MAWI and PeerRush;
# then the delta sweep on MAWI f=10%. Memory-gated, skips finished outputs.
cd "$(dirname "$0")/.."
waitmem() { while [ "$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo)" -lt "$1" ]; do sleep 30; done; }
export -f waitmem
mawi() { j=$1; n=results/g2/g8_$(echo "$j" | sed 's/:/_/g;s/@/_at/').npz
         [ -f "$n" ] || { waitmem 6; uv run python scripts/g8_mawi.py --job "$j" > /dev/null 2>&1 || echo "FAILED mawi $j" >> results/g2/g8_failed.txt; }; }
pr() { j=$1; n=results/g5/g8_$(echo "$j" | sed 's/:/_/g;s/@/_at/').npz
       [ -f "$n" ] || { waitmem 12; uv run python scripts/g8_peerrush.py --job "$j" > /dev/null 2>&1 || echo "FAILED pr $j" >> results/g5/g8_failed.txt; }; }
export -f mawi pr

# agreement gate: MAWI primary day f=0,10%, 10 draws, und + d4c, fold hash, delta=0
for g in $(seq 0 9); do for arm in und d4c; do mawi "p:fold:0:$arm:0@$g"; mawi "p:fold:0:$arm:10@$g"; done; done
# PeerRush 8192 slots, f=0,25%, 10 draws, und + d4 (idle policy not modelled; run und only as the comparator; d4c stands in for the two-way arm)
for g in $(seq 0 9); do pr "fold:0:und:0@$g"; pr "fold:0:und:25@$g"; pr "fold:0:d4c:0@$g"; pr "fold:0:d4c:25@$g"; done
echo "g8 agreement done $(date)" >> results/g5/STATUS

# delta sweep (descriptive): MAWI f=10%, 3 draws per delta, und + d4c, sorted hash (isolate the delay effect)
for d in 1 10 100 1000; do for g in 0 3 6; do for arm in und d4c; do mawi "p:sorted:$d:$arm:10@$g"; done; done; done
echo "g8 delta done $(date)" >> results/g5/STATUS
