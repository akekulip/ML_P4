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
