#!/usr/bin/env bash
# Post-hoc diagnostic: D1 split into d1w / d1t / d1i on MAWI (oracle gate, B0-L fill 10%), at the clock starts of the existing D1 runs.
cd "$(dirname "$0")/.."
jobs() { for d in p r; do
  for g in $(ls results/g2 | grep "^b_${d}_oracle_b0l_10_at[0-9]*_p_d1.npz" | sed 's/.*_at\([0-9]*\)_p_d1.npz/\1/' | sort -n); do
    for a in d1w d1t d1i; do echo "g2_mawi.py $d:oracle:crc@$g+$a"; echo "g2b_mawi.py $d:oracle:b0l:10@$g+$a"; done
  done; done; }
run() { s=${1%% *}; j=${1#* }; uv run python scripts/$s --job "$j" > /dev/null 2>&1 || echo "FAILED $1" >> results/g2/d1parts_failed.txt; }
export -f run
jobs | xargs -P 4 -I{} bash -c 'run "{}"'
echo "mawi d1 parts done $(date)" >> results/g5/STATUS
