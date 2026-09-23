#!/usr/bin/env bash
# Rebuild and relaunch MVM on the Tofino switch (only replaces our own mvm_tna program).
# Compiles into ~/ml_p4/build_new (never over the running build), stops the running MVM
# bf_switchd, swaps builds, rewrites the conf to absolute paths, relaunches, waits until the
# program is registered, and runs `controller.py setup` (ports, port_fwd, static feature tables).
set -euo pipefail
cd "$(dirname "$0")/.."
SW=decps@10.10.54.81
scp -q -o BatchMode=yes hw/build/mvm_tna.p4 hw/build/model.json hw/controller.py "$SW:~/ml_p4/"
ssh -o BatchMode=yes "$SW" 'bash -s' <<'REMOTE'
set -euo pipefail
cd ~/ml_p4
export SDE_INSTALL=/home/decps/Downloads/bf-sde-9.13.2/install
rm -rf build_new
$SDE_INSTALL/bin/bf-p4c --target tofino --arch tna -o build_new/mvm_tna.tofino \
  --bf-rt-schema build_new/mvm_tna.tofino/bfrt.json mvm_tna.p4 2>&1 | grep -E "error|generated"
[ -f build_new/mvm_tna.tofino/pipe/tofino.bin ] || { echo "compile failed"; exit 1; }
# stop the running MVM (launcher, bf_switchd, its tail) -- pkill -x only
L=$(pgrep -f -x "/bin/bash ./launch_mvm.sh" || true); T=""
for p in $(pgrep -x tail || true); do [ "$(ps -o ppid= -p $p | tr -d ' ')" = "$L" ] && T=$p; done
[ -n "$L" ] && sudo -n kill $L || true
sudo -n pkill -x bf_switchd || true
[ -n "$T" ] && sudo -n kill $T || true
for i in 1 2 3 4 5 6; do pgrep -x bf_switchd >/dev/null || break; sleep 2; done
pgrep -x bf_switchd && { echo "bf_switchd still running"; exit 1; }
rm -rf build_old; [ -d build ] && mv build build_old; mv build_new build
sed -E 's#"build[^/"]*/mvm_tna.tofino#"/home/decps/ml_p4/build/mvm_tna.tofino#g' build/mvm_tna.tofino/mvm_tna.conf > build/mvm_tna_abs.conf
grep -q build_new build/mvm_tna_abs.conf && { echo "conf still references build_new"; exit 1; }
(sudo -n nohup ./launch_mvm.sh > switchd.log 2>&1 &)
for i in $(seq 1 60); do ss -ltn | grep -q ":50052" && break; sleep 2; done
if grep -a -q -E "BF_SWITCHD ERROR|BF_PIPE ERROR" switchd.log; then grep -a -E "BF_SWITCHD ERROR|BF_PIPE ERROR" switchd.log | head -5; exit 1; fi
for i in $(seq 1 12); do
  out=$(timeout 300 python3 controller.py setup 2>&1 | grep -v -i warn || true)
  echo "$out" | grep -q "Object not found" || break; sleep 5
done
echo "$out" | grep -E "dp[0-9]|installed|Error|index" | head -6
echo "$out" | grep -q "static tables installed" || exit 1
REMOTE
echo "switch redeployed"
