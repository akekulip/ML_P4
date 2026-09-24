#!/usr/bin/env bash
# Exploratory baseline (not pre-registered in G6; baseline 5 of the paper plan): a table of twice the size, same number of holders
# (5% of 131,072 slots = 10% of 65,536), MAWI primary day, clocks 0 to 9.
cd "$(dirname "$0")/.."
waitmem() { while [ "$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo)" -lt "$1" ]; do sleep 30; done; }
export -f waitmem
run() { s=${1%% *}; j=${1#* }; waitmem 6; uv run python scripts/$s --job "$j" > /dev/null 2>&1 || echo "FAILED $1" >> results/g2/g6_failed.txt; }
export -f run
for g in $(seq 0 9); do echo "g2_mawi.py p:oracle:crc@$g~131072"; echo "g2b_mawi.py p:oracle:b0l:5@$g~131072"; done | xargs -P 2 -d '\n' -I{} bash -c 'run "{}"'
echo "g6 double done $(date)" >> results/g5/STATUS
