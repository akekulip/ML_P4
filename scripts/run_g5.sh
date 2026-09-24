#!/usr/bin/env bash
# Pre-registered PeerRush fill-attack jobs (F:ARM@CLOCK), memory-bounded, skipping finished outputs.
#   scripts/run_g5.sh --dry-run   lists the jobs and checks pairing without running anything.
# Every defended job at fill f and clock g has an undefended partner (f:und@g) and a no-attack partner (0:ARM@g).
# Stage A (f = 0 and 10%, about 4 GB per run) uses 2 workers; stage B (f = 25%, about 8.6 GB per run) uses 1.
cd "$(dirname "$0")/.."
DEF="d1 d3c8 d3c16"
C10=$(seq 0 3 27); C25="0 6 12 18 24"

stage_a() {
  for g in $(seq 0 29); do echo "0:und@$g"; done
  for g in $C10; do for a in $DEF; do echo "0:$a@$g"; done; done
  for g in $(seq 0 29); do echo "10:und@$g"; done
  for g in $C10; do for a in $DEF; do echo "10:$a@$g"; done; done
}
stage_b() {
  for g in $(printf "%s\n" $(seq 0 9) $C25 | sort -n | uniq); do echo "25:und@$g"; done
  for g in $C25; do for a in $DEF; do echo "25:$a@$g"; done; done
}

check_pairs() {
  local all; all=$( { stage_a; stage_b; } )
  local bad=0 j f a g
  for j in $(echo "$all" | grep -vE '^[0-9]+:und@'); do
    f=${j%%:*}; a=${j#*:}; a=${a%@*}; g=${j#*@}
    echo "$all" | grep -qx "$f:und@$g" || { echo "missing undefended partner for $j"; bad=1; }
    echo "$all" | grep -qx "0:$a@$g"   || { echo "missing no-attack partner for $j"; bad=1; }
  done
  return $bad
}

if [ "$1" = "--dry-run" ]; then
  check_pairs && echo "pairing ok"; echo "stage A: $(stage_a | wc -l) jobs; stage B: $(stage_b | wc -l) jobs"; exit $?
fi
check_pairs || exit 1

mkdir -p results/g5/logs
run() { j=$1; n=results/g5/pr_$(echo "$j" | sed 's/:/_/;s/@/_at/').npz
        [ -f "$n" ] || uv run python scripts/g5_peerrush.py --job "$j" > "results/g5/logs/$(basename "$n" .npz).log" 2>&1; }
export -f run
stage_a | xargs -P 2 -I{} bash -c 'run {}'
echo "stage A done $(date)" >> results/g5/STATUS
stage_b | xargs -P 1 -I{} bash -c 'run {}'
echo "stage B done $(date)" >> results/g5/STATUS
