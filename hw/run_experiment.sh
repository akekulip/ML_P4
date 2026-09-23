#!/usr/bin/env bash
# One MVM hardware run: controller on the switch, CPU backend on Hulk, query client on Vision.
# Usage: hw/run_experiment.sh LABEL SLICE RATE [N_QUERIES] [K] [POLL_MS]
#   SLICE = full_0425_to_0426 | benign_0427_to_0428 ; RATE = queries per second offered by Vision
# Results land in results/w8/runs/LABEL/ (client records, controller log, backend log, meta).
# Credentials come from ~/.lab_env ($SSHPASS); the host sudo password is sent on stdin only.
set -euo pipefail
LABEL=$1; SLICE=$2; RATE=$3; N=${4:-0}; K=${5:-8}; POLL=${6:-20}
cd "$(dirname "$0")/.."
set -a; source ~/.lab_env >/dev/null 2>&1; set +a; export SSHPASS
SW=decps@10.10.54.81; VI=decps@10.10.54.166; HU=decps@10.10.54.158
VISION_MAC=3c:fd:fe:cc:5d:c0; HULK_MAC=3c:fd:fe:e5:f9:91
OUT=results/w8/runs/$LABEL; mkdir -p "$OUT"
vsh() { sshpass -e ssh -o ConnectTimeout=10 "$VI" "$@"; }
hsh() { sshpass -e ssh -o ConnectTimeout=10 "$HU" "$@"; }
ssh_sw() { ssh -o BatchMode=yes -o ConnectTimeout=10 "$SW" "$@"; }

QF=queries_$SLICE.bin
if [ "$N" -gt 0 ]; then   # first N queries of the slice (44 bytes each)
  vsh "cd ~/ml_p4 && head -c $((N * 44)) queries_$SLICE.bin > q_$LABEL.bin"; QF=q_$LABEL.bin
fi

cleanup() {
  ssh_sw "cd ~/ml_p4 && [ -f ctl.pid ] && kill -TERM \$(cat ctl.pid) 2>/dev/null; sleep 2; rm -f ctl.pid" || true
  hsh "sudo -S -p '' bash -c 'cd ~decps/ml_p4 && [ -f backend.pid ] && kill \$(cat backend.pid) 2>/dev/null; rm -f backend.pid'" <<< "$SSHPASS" || true
}
trap cleanup EXIT

# 1. controller (clears leaf_tbl, cold cache)
ssh_sw "cd ~/ml_p4 && mkdir -p runs && (nohup python3 controller.py run --k $K --poll-ms $POLL --log runs/${LABEL}_ctl.csv > runs/${LABEL}_ctl.out 2>&1 & echo \$! > ctl.pid)"
for i in $(seq 1 30); do ssh_sw "grep -q 'serving digests' ~/ml_p4/runs/${LABEL}_ctl.out" && break; sleep 1; done
ssh_sw "grep -q 'serving digests' ~/ml_p4/runs/${LABEL}_ctl.out" || { echo "controller did not start"; ssh_sw "tail -5 ~/ml_p4/runs/${LABEL}_ctl.out"; exit 1; }

# 2. CPU backend on Hulk
hsh "sudo -S -p '' bash -c 'cd ~decps/ml_p4 && (nohup ./hulk_backend serve enp59s0f1np1 tree.bin $VISION_MAC $HULK_MAC > backend_$LABEL.log 2>&1 & echo \$! > backend.pid)'" <<< "$SSHPASS"
sleep 1

# 3. client on Vision (blocks until 2 s after the last answer)
vsh "sudo -S -p '' bash -c 'cd ~decps/ml_p4 && ./vision_client enp59s0f0np0 $QF rec_$LABEL.bin $RATE $HULK_MAC $VISION_MAC 8'" <<< "$SSHPASS" 2> "$OUT/client_stderr.txt" || true
cat "$OUT/client_stderr.txt" | grep -v '^\[sudo\]' || true

# 4. stop and collect
cleanup; trap - EXIT
sshpass -e scp -q "$VI:~/ml_p4/rec_$LABEL.bin" "$OUT/records.bin"
sshpass -e scp -q "$HU:~/ml_p4/backend_$LABEL.log" "$OUT/backend.log" || true
scp -q -o BatchMode=yes "$SW:~/ml_p4/runs/${LABEL}_ctl.csv" "$OUT/controller.csv"
scp -q -o BatchMode=yes "$SW:~/ml_p4/runs/${LABEL}_ctl.out" "$OUT/controller.out"
printf '{"label":"%s","slice":"%s","rate":%s,"n":%s,"k":%s,"poll_ms":%s,"date":"%s"}\n' \
  "$LABEL" "$SLICE" "$RATE" "$N" "$K" "$POLL" "$(date -Is)" > "$OUT/meta.json"
echo "collected into $OUT"
