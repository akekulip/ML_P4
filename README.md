# ML_P4: two separate tracks

This repository holds two pieces of work that share a testbed and some tooling but answer different questions. They are kept apart on purpose.

## Track 1: MVM-Lite (class project, finished) — `mvm_lite/`

**Question:** how do model complexity and temporal inference locality interact under a bounded model-memory budget, and can adaptive model residency keep predictions exact while speeding up inference?

Decision-tree leaves are paged into a switch table by traffic; misses go to a CPU that runs the full tree. The track covers the leakage-corrected model study, locality and cache-policy measurements, a BMv2 prototype with exact fidelity, and a Tofino-1 implementation with a hardware load sweep against a CPU baseline. Start at `mvm_lite/README.md`. This track is frozen and is not touched by the work below.

## Track 2: state contention and downgrade attacks (research direction) — `src/dgrade/`

**Question:** what happens when a stateful in-network classifier cannot give every flow access to its accurate per-flow path, and can that allocation be manipulated by an attacker or protected by the design?

Emulator of NetBeacon-style flow-slot logic, pre-registered experiments on MAWI and PeerRush, a chain of defences that failed (salt, keyed polynomial, wrap fix, rent, value rules), and one bounded positive result (two-choice table admission). Start at `docs/REPORT.md`; the plan and the pre-registration are `docs/paper_plan.md` and `docs/preregistration.md`. All results are emulator results with an oblivious attacker; deployability on Tofino-1 is not established.

## Layout

- `mvm_lite/`: track 1 (its own `README.md`, source, experiments, hardware code, report).
- `src/dgrade/`, `scripts/`, `tests/test_dgrade_*`, `docs/`: track 2.
- `third_party/` (gitignored): NetBeacon, BoS, Flowrest, SketchFeature artifacts.
- `data/`, `results/` (gitignored): traces and run outputs.

Commits are authored by akekulip only. Tests: `uv run pytest -q`.
