# Request: emulator-to-SDE validation (needs Philip's approval before anything runs)

Nothing in this file has been run. Every conclusion in `docs/` about NetBeacon's flow slots, and about the defences D1 and D2, comes from the software emulator in `src/dgrade/netbeacon_sim.py`. Two things stand between those results and a claim about hardware:

1. **Hash equivalence.** The emulator sorts the 5-tuple before hashing and uses CRC-32. The P4 program's `@symmetric` hash may be built by `bf-p4c` in a way that depends only on `src ^ dst` and `sport ^ dport`, in which case tuples with equal XORs collide whatever the key. That would change benign collision counts and the meaning of the keyed-hash arms.
2. **Resource fit.** D1 (no wrap window, takeover timestamp refresh, gap-wrap fix) and D2 (a secret polynomial) are claimed to fit next to NetBeacon's 12 stages. NetBeacon already uses all 12. This is unverified.

## What is asked

| Step | What it does | Touches the running switch? |
|---|---|---|
| S1: SDE software-model diff | Runs NetBeacon's P4 on the SDE model (no chip) with recorded packets and compares slot indices and verdicts with the emulator | No |
| S2: compile-only stage-fit for D1 | `bf-p4c` compile of NetBeacon plus D1 in a separate directory; reads the stage, SRAM and stateful-ALU summary | No |
| S3: compile-only stage-fit for D2 | Same with a configurable CRC polynomial (`set_default_with_user_defined`) | No |

Constraints (from `CLAUDE.md` and earlier decisions): build only in `~/ml_p4/build_new`; SDE 9.13.2 only; no `bf_switchd` restart; kill by PID, never `pkill -f`; no credentials printed.

## What each result would change

- S1 shows the emulator's slot assignment matches the model (or measures how far it is off). A mismatch invalidates the benign-downgrade counts, not only the defences.
- S2 and S3 turn "fits" from an assumption into a resource report. If D1 does not fit next to NetBeacon, it is deployable only next to a smaller build, and the claim must say so.
- Until S1 to S3 are done, D1 is described as having negligible measured emulator cost with hardware cost unverified.

## Decision needed

Approve S1, S2 and S3 (compile-only, separate build directory), or name which to skip.

## G9-A / G9-B: exact steps for D4c on the real SDE 9.13.2 toolchain (written for review; not run)

Philip has not yet approved switch-host access for these. Nothing below has been executed. Both steps are compile/model-only: no `bf_switchd` restart, no change to the running program.

### G9-A: compile the frozen, evaluated D4c (not P13) on SDE 9.13.2

```bash
# On the switch host (decps@10.10.54.81), in a fresh, separate build directory (never ~/ml_p4's existing build):
mkdir -p ~/ml_p4/build_new/d4c_g9a && cd ~/ml_p4/build_new/d4c_g9a
export SDE=/home/decps/Downloads/bf-sde-9.13.2
export SDE_INSTALL=$SDE/install
# copy p4/dgrade_d4c/switch.p4 and headers.p4 from this repo, plus parsers.p4/util.p4 from third_party/NetBeacon (unchanged)
$SDE_INSTALL/bin/bf-p4c --target tofino --arch tna -g --verbose 2 -o build_d4c switch.p4 > build_d4c.log 2>&1
echo "rc=$?"
cat build_d4c/pipe/logs/table_summary.log
cat build_d4c/pipe/logs/mau.resources.log
```

Record: exit code, stage count and critical path (`table_summary.log`), per-stage stateful ALU/SRAM/map-RAM/hash-bit/hash-distribution counts (`mau.resources.log`), and every warning. Diff these against the 9.13.1 numbers already in `docs/results_d4c_compile.md` (12 stages, critical path 11, 14 stateful ALUs, 191 SRAM, 155 map RAM, 330 hash bits, 15 hash-distribution units, 15 warnings). **A change in any of these numbers means the 9.13.1 result does not carry over**, and `docs/results_d4c_compile.md` and `docs/REPORT.md` must say so.

### G9-B: SDE software-model packet fidelity (no chip)

1. **Freeze a small deterministic packet subset** (a few thousand packets) from the existing saved streams, covering: a plain owner path, a takeover, a collision refusal with both candidates held, and (if G9-A compiles) both a table-A and a table-B admission under D4c. Extract with a short script from `results/g1/stream.npz` (PeerRush) and `results/g2/prep_p.npz` (MAWI) — do not regenerate the traces.
2. **Run the frozen subset through the SDE software model** (`$SDE_INSTALL`'s model tools; exact invocation to be confirmed from the model's own `--help` and the tofino-p4 skill's model-bringup notes before running, since this has not been done before in this repo) with the G9-A-compiled program, no chip, no `bf_switchd`.
3. **Compare packet-by-packet against `TofinoSim`** (`src/dgrade/netbeacon_tofino.py`) on the same subset: slot/way chosen, admit-vs-refuse, full-vs-fallback path, final class. Report exact and mismatched counts, and which fields disagree first when they do.
4. This directly checks the assumptions `TofinoSim` had to make without hardware evidence: the hash message's exact bit order, the predicate encoding (one-hot 1/2/4/8, from `docs/lit/innovation_memos_2026-09-24.md`), whether the idle test (`lss.u`) treats `now < last-seen` as the emulator assumes, and recirculation ordering.

### Constraints (unchanged from the top of this file)

Build only in a separate `~/ml_p4/build_new` subdirectory; SDE 9.13.2 only; no `bf_switchd` restart; kill by PID, never `pkill -f`; no credentials printed; nothing touches the currently running program.

### Decision needed

Approve G9-A and G9-B (compile-only and model-only, as detailed above), or name which to skip. G9-C (a small hardware smoke test) and G9-D (a 4-condition hardware campaign: no attack, MAWI 10%, MAWI 25%, PeerRush 25%) are explicitly **not** requested here — they are a separate, later decision after G9-B's result is known, and would need their own snapshot/restore plan since they take over the switch from whatever is currently running.
