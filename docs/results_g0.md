# Gate G0 results: artifact parameters (2026-09-23)

The detailed tables, each value with its `file:line` or paper-page citation, are in `docs/g0/bos.md` and `docs/g0/netbeacon_flowrest_sketchfeature.md`. The artifacts are cloned in `third_party/`, which git ignores; the commits read were NetBeacon 06c6127, Brain-on-Switch 38aafd9, Flowrest 13a527c and SketchFeature 8fcb53b. Everything below was done offline. The P4 programs were compiled with a local bf-p4c 9.13.1, and nothing ran on the switch.

## What each victim does with a flow that has no storage slot

| | NetBeacon (shipped PeerRush build) | BoS (NSDI'24) | Flowrest |
|---|---|---|---|
| Flow slots | 65,536, one hash way | 65,536, one hash way | per the ToN build, one way |
| Hash | unseeded CRC32; its low 16 bits give the index | CRC-32 for the index, CRC-32C for the flow tag; init value 0 and `@symmetric`. The seed is fixed at compile time. | see the G0 file |
| When a new flow may take an occupied slot | the flow-size predictor scores the new flow above 50, **and** the incumbent is determined or idle for about 268 ms | the incumbent has been idle for about 256 ms (3,906 × 65.536 µs). Each packet from the incumbent resets that timer. | the incumbent is idle for about 537 ms, or the controller freed the slot after the verdict at packet 3 |
| When a flow counts as "determined" | at packet 2,048, set by the shipped controller. The verdict memo holds 1,500 flows and drops the oldest first. | never freed explicitly | at packet 3 |
| What a flow without a slot gets | the per-packet tree | IMIS (the server model) for at most 12 of every 256 colliding packets. That budget counts **packets**, not the 5% of **flows** the paper states. The per-packet tree handles the rest. | **no verdict** (class 255) |
| Load at which the paper reports fallback | 0.85% of flows fall back at 1,555 new flows/s | not reported | not reported |
| Trained models shipped | yes: the per-packet tree, seven phase trees and the flow-size model, as table pickles that load in Python | binary RNN checkpoints only. The thresholds (`threshold.json`), the per-packet forest and the IMIS model are missing. | yes, but they need scikit-learn 1.2.2 |
| Training scripts and data | scripts missing; the PeerRush data is not in the repo | scripts present; the datasets are on Google Drive | see the G0 file |
| Stages used (bf-p4c 9.13.1, 0 errors) | all 12 | all 12 (single-pipe normal version) | 10 |

## Consequences for the plan

1. **G1 can start on NetBeacon now.** Its full model and its fallback model load offline from the shipped tables, so we can compare their verdicts table by table. We still need traffic to replay. PeerRush is not in the repo.
2. **The labelled datasets do not support H4 as written.** In BoS, only BoT-IoT has attack classes, and it has no benign class. CICIoT2022 is device-state classification. NetBeacon's tasks classify applications (PeerRush, ISCXVPN), not attacks. Measuring the attacker's own attack flows being missed therefore needs a dataset with both benign traffic and attacks at packet level, plus a victim retrained on it. NetBeacon ships no training scripts, so this means a faithful re-implementation of its phase-tree training, validated against the shipped PeerRush tables. **This needs a decision from Philip on the dataset.**
3. **Kill criterion (h) already applies to both victims.** NetBeacon and BoS each use all 12 stages, so the defense cannot sit next to either unmodified build. The defense goes on a NetBeacon build with fewer phases, and the paper states the reduced resource claim.
4. **Flowrest changes role.** A flow that loses a slot gets no verdict at all, and the shipped build only processes flows pre-loaded from the test set. It becomes the no-fallback point in the generality sweep, not a victim.
5. **Baseline 13 (SketchFeature) runs in the emulator only.** The repo has no P4. Its decoded histograms cannot feed NetBeacon's existing trees, so the classifier has to be retrained on the decoded features. The plan's "about 13% F1, 3 MB, 7 stages" mixes two configurations: the F1 figure was measured at 6 MB, while 3 MB and 7 stages describe the prototype.
6. **Porting notes for later (E1).**
   - **BoS:** port the single-pipe version, write its control plane, and move timestamps to the switch clock. Its IMIS server is hard-wired to CUDA. This machine has an RTX 2070, and the research venv has no `torch` yet.
   - **NetBeacon:** port its Python 2 controller to Python 3. Its ports are hard-coded, and it appears to expect traffic entering on pipe 0 (inferred).
   - **Our switch:** that it has 2 pipes is inferred; check it on the switch.

## Things G0 found in the artifacts

- The ISCXVPN checkpoint directory says the L2 loss, while the paper's Table 2 says L1.
- `dataset/CICIOT2022/labels.json` is a copy of the ISCXVPN labels.
- SketchFeature's CPU code uses Python's per-process salted `hash()`, and has an operator-precedence bug.
