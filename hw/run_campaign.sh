#!/usr/bin/env bash
# W8 hardware campaign. Each run: cold cache, one slice, one rate, one K; 3 repetitions.
#   K=8: MVM (switch holds 8 leaves, misses go to Hulk's CPU); K=0: CPU only (every query to Hulk).
# Results: results/w8/runs/<label>/ ; progress: results/w8/campaign.log
set -uo pipefail
cd "$(dirname "$0")/.."
LOG=results/w8/campaign.log; mkdir -p results/w8
run() { local label=$1; shift
  if [ -f "results/w8/runs/$label/records.bin" ]; then echo "skip $label" >> "$LOG"; return; fi
  echo "$(date '+%T') start $label" >> "$LOG"
  if timeout 600 hw/run_experiment.sh "$label" "$@" >> "$LOG" 2>&1; then echo "$(date '+%T') done $label" >> "$LOG"
  else echo "$(date '+%T') FAILED $label" >> "$LOG"; fi
}
for rep in 1 2 3; do
  for slice in full_0425_to_0426 benign_0427_to_0428; do
    run "a_${slice}_k8_r1000_rep$rep" "$slice" 1000 0 8
    run "a_${slice}_k0_r1000_rep$rep" "$slice" 1000 0 0
  done
  for rate in 5000 20000 50000 100000; do
    run "b_full_k8_r${rate}_rep$rep" full_0425_to_0426 "$rate" 0 8
    run "b_full_k0_r${rate}_rep$rep" full_0425_to_0426 "$rate" 0 0
  done
done
echo "$(date '+%T') CAMPAIGN DONE" >> "$LOG"
