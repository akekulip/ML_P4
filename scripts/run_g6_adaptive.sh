#!/usr/bin/env bash
# G6 addendum 4: leak arm (8 cells x clocks 0-9) and rekey arm (T = 5, 10, 30, 60 s x clocks 0-9); memory-gated, skips finished outputs.
cd "$(dirname "$0")/.."
waitmem() { while [ "$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo)" -lt "$1" ]; do sleep 30; done; }
export -f waitmem
jobs() {
  for g in $(seq 0 9); do for c in ctl c1m1 c2m2 c2m1 c8m8 c8m4 c64m64 c64m32; do echo "leak p:vul:$c@$g"; done; done
  for g in $(seq 0 9); do for T in 5 10 30 60; do echo "rekey p:oracle:crc@$g+d5r$T"; done; done
}
run() { kind=${1%% *}; j=${1#* }
  if [ "$kind" = leak ]; then n=results/g2/g6l_$(echo "$j" | sed 's/:/_/g;s/@/_at/').npz; s=g6_leak.py
  else n=results/g2/a_$(echo "$j" | sed 's/:/_/g;s/@/_at/;s/+/_p_/').npz; s=g2_mawi.py; fi
  [ -f "$n" ] || { waitmem 6; uv run python scripts/$s --job "$j" > /dev/null 2>&1 || echo "FAILED $1" >> results/g2/g6_failed.txt; }; }
export -f run
jobs | xargs -P "${AD_WORKERS:-3}" -d '\n' -I{} bash -c 'run "{}"'
echo "g6 adaptive done $(date)" >> results/g5/STATUS
