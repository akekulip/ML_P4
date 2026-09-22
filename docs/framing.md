# MVM: How Much of a Decision Tree Does Network Traffic Actually Use?

*Project framing, revised 2026-09-22 after the W2 results. Supersedes the pitch in `docs/brief.md`.
All numbers below come from stand-in training pools, because `train_test_network.csv` has not been
downloaded yet. They will be re-run on the official file.*

## Problem

In-network classification places a trained model inside a programmable switch, where table
memory is scarce. A decision tree maps naturally onto switch tables: each leaf is an
axis-aligned box of feature space, and one range-match entry can hold it. When a tree has more
leaves than the switch can hold, the switch can keep only a subset of leaves resident and forward
the remaining flows to a server that runs the full tree. We call a resident leaf a *page* and the
scheme *MVM* (model virtual memory). Leaves of one tree are disjoint, so any subset of leaves can
be resident without priorities or dependency handling, and the switch returns exactly the
prediction of the full tree whenever it answers.

Whether MVM is useful depends on two properties that belong to the model and the traffic rather
than to the switch. The first is locality: under real traffic replayed in time order, do a few
leaves serve most flows? The second is model size: how many leaves does the model need in order
to classify well?

## What the first results changed

The original pitch assumed a trade-off: deeper trees classify better but spread traffic over more
leaves, so a switch designer must give up accuracy to gain cacheability. That assumption holds
only under a random train/test split. TON_IoT contains millions of exact-duplicate flows, and
under a random split 59% of test rows are copies of training rows. A deep tree memorizes those
copies, so its test score keeps rising with depth (macro-F1 from 0.863 at depth 4 to 0.967
unlimited).

When the split keeps every distinct feature vector in a single pool, only about 1% of test vectors
appear in training, and the curve changes shape. Macro-F1 peaks near 100 to 450 leaves (about
0.93) and then declines: the unlimited tree reaches 0.898 with 1,944 leaves. On flows the model
has not seen, the extra leaves fit noise. The same random split overstates random-forest
macro-F1 by 0.074 and decision-tree macro-F1 by 0.057.

The project question therefore changes from "how much accuracy must we give up to fit the
switch?" to the following: **when evaluation excludes duplicate leakage, is the model that
classifies best also the model with the smallest working set, and how small is that working set
under real traffic?**

## Research questions

- **RQ1, prediction.** How well does a compact tree on data-plane features detect attacks when
  duplicate flows cannot cross the train/test boundary, and how does it compare with logistic
  regression, random forest and gradient boosting? *(Answered provisionally in W2.)*
- **RQ2, locality.** Under chronological replay, what fraction of flows do the top K leaves serve,
  and how large are W90 and W99? Does the answer hold for benign traffic alone and within each
  attack phase, and does it hold across three flow orderings?
- **RQ3, size and working set.** Across tree depths, how does the working set grow with leaf
  count, and where does the accuracy peak fall relative to it? Is there a tree on the Pareto
  frontier of macro-F1 against W90 that a small switch table can hold?
- **RQ4, adaptation.** With K resident leaves, how close do LRU, LFU and decayed LFU come to the
  offline optimum (Belady), and how much better are they than a static top-K placement when the
  attack phase changes?

## Hypotheses (revised)

- **H1.** Leaf visits are highly skewed under chronological replay. *Pilot evidence supports it
  for the full stream, where flood attacks dominate. The benign-only stream is the harder test.*
- **H2 (revised).** Under leakage-free evaluation, accuracy peaks at a moderate tree size, so the
  most accurate tree is also far smaller than the unpruned tree. *W2 supports this.* The
  remaining question is whether its working set is small enough for a switch table of 8 to 64
  entries.
- **H3.** A static top-K placement loses hits at attack-phase boundaries that adaptive policies
  recover.
- **H4.** Predictions are identical to the full tree, because a miss falls back to it. *This holds
  by construction; tests check it.*

## Evaluation protocol

- **Data.** TON_IoT processed network flows, 22.34M rows, attacks in day-long phases (Canberra
  local time). Features exclude IP addresses and ports. An ablation shows that they identify
  testbed hosts: IPs plus ports lift a tree to 0.9999 macro-F1.
- **Splits.**
  - *grouped:* each distinct feature vector belongs to one pool (primary IID evaluation);
  - *forward:* grouped, with training drawn only from the first half of each day and replay from
    the second halves (primary replay; injection never appears in training, so it becomes an
    unseen-attack test);
  - *random:* kept only to measure how much duplicate leakage inflates the scores.
- **Metrics.**
  - Classification: macro-F1, MCC, per-class recall and PR-AUC, with the Bayes ceiling from label
    conflicts (0.958 for data-plane features).
  - Locality: top-K coverage, W90/W99, normalized leaf entropy, reuse distance and hourly
    Jensen-Shannon drift.
  - Caching: hit rate, churn, recovery time after a phase change, and the gap to Belady.
- **Intervals.** Mean ± standard deviation over five seeds for IID results, and a block bootstrap
  over hours for replay results.

## Contributions (scoped for a class project)

1. A leakage-controlled evaluation of decision trees on TON_IoT, showing that the apparent gain
   from deeper trees comes from duplicate flows.
2. A measurement of leaf-level locality in time-ordered network traffic, reported separately for
   the flood-dominated stream, benign traffic and each attack phase.
3. A comparison of leaf-cache policies against static placement and the offline optimum, with a
   BMv2 prototype that installs and evicts leaf entries at runtime.

## Limits of the claims

The traffic comes from one testbed and is 96% attack traffic, so its locality may not match an
operational network. The results use stand-in training pools until the official Train_Test file
is available. BMv2 demonstrates correctness and update behavior, not line-rate performance, and
Tofino is future work.
