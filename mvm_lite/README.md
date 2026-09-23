# MVM-Lite (class project, W1–W8, finished)

MVM-Lite keeps only K leaves of a decision tree in a switch table and sends misses to a CPU that runs the full tree. It pages leaves in and out by traffic. The study measures three things on the TON_IoT network data: how skewed leaf use is, how tree complexity trades against cacheability, and how replacement policies behave under drift. It then runs the design on BMv2 and on the lab's Tofino-1.

## Results

| Doc | What it covers |
|---|---|
| `docs/results_w2.md` | Model families and depth, and the leakage-corrected split |
| `docs/results_w3.md` | Leaf locality and working sets |
| `docs/results_w4.md`, `docs/results_w4_recovery.md` | Cache policies and recovery after phase changes |
| `docs/results_w5.md` | BMv2 prototype |
| `docs/results_w8.md` | Tofino-1 with Vision and Hulk, against CPU-only |
| `docs/report/report.pdf`, `docs/report/slides.pdf` | Report (13 pages) and slides. Every number comes from `experiments/w7_numbers.py` → `docs/report/numbers.json` |

Headline hardware results (`docs/results_w8.md`), from a depth-10 tree with 394 leaves and K = 8:
- **Fidelity:** 1,080,000 of 1,080,000 queries answered, with the served class equal to the offline tree on every query.
- **Switch hit rate:** 0.956 on the full stream and 0.846 on benign flows.
- **Median round trip:** 102.5 µs for a switch hit, 232.2 µs for a miss answered by Hulk, and 300.7 µs for CPU-only.

## Layout and rerunning

Every script resolves paths from this directory. `experiments/*.py` use `ROOT = Path(__file__).resolve().parents[1]`, and the shell scripts `cd` here. Run everything from the repo root through the shared uv environment:

```bash
uv run python mvm_lite/experiments/w7_numbers.py     # regenerate report numbers from results/
uv run pytest -q mvm_lite/tests                      # the 51 MVM tests
cd mvm_lite/docs/report && pandoc report.md -o report.pdf --pdf-engine=tectonic
```

`data/` (TON_IoT raw and processed) and `results/` are untracked and live inside this folder. `src/mvm` is installed through the repo's `pyproject.toml`.

## Switch state

As of 2026-09-23, MVM (`mvm_tna`) is left running on the Tofino-1, and the DNP3 program it displaced has not been restored. To restore it, run `~/ml_p4/RESTORE_dnp3_20260923.sh` on the switch. See `hw/README.md` for details.

## Known limitation

The official TON_IoT `train_test_network.csv` was never obtained. Training used stand-in pools drawn from the processed network data (see `docs/results_w2.md`).
