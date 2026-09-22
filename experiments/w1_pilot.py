"""W1 PROVISIONAL locality pilot (go/no-go).

Provisional because train_test_network.csv is not yet downloaded: the tree is trained on a
class-stratified sample (<=20k per type, as Train_Test was built) drawn from the full set, and
those rows are removed from the replay stream. Features: data-plane set, no IPs or ports.
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, matthews_corrcoef, recall_score
from sklearn.preprocessing import OrdinalEncoder
from sklearn.tree import DecisionTreeClassifier

from mvm.cache import LRU, Belady, StaticTopK, WindowOracle, simulate
from mvm.locality import coverage, normalized_entropy, working_set

ROOT = Path(__file__).resolve().parents[1]
NUM = ["duration", "src_bytes", "dst_bytes", "missed_bytes", "src_pkts", "dst_pkts", "src_ip_bytes", "dst_ip_bytes"]
CAT = ["proto", "service", "conn_state"]
SEED = 0

df = pd.read_parquet(ROOT / "data/processed/network", columns=["ts", *NUM, *CAT, "label", "type"])
n0 = len(df)
df = df.dropna(subset=NUM)
dropped = n0 - len(df)
df = df.sort_values("ts", kind="stable").reset_index(drop=True)

train_idx = df.groupby("type", group_keys=False).apply(
    lambda g: g.sample(min(len(g), 20_000), random_state=SEED)).index
train, replay = df.loc[train_idx], df.drop(index=train_idx)

enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1).fit(train[CAT])
def X(d): return np.hstack([d[NUM].to_numpy(float), enc.transform(d[CAT])])

tree = DecisionTreeClassifier(max_depth=8, random_state=SEED).fit(X(train), train.label)
Xr = X(replay)
leaf = tree.apply(Xr)
pred = tree.predict(Xr)
y = replay.label.to_numpy()

n_leaves = tree.get_n_leaves()
res = {
    "provisional": True,
    "dropped_malformed_rows": int(dropped),
    "train_rows": len(train), "replay_rows": len(replay),
    "depth": 8, "n_leaves": int(n_leaves),
    "replay_macro_f1": f1_score(y, pred, average="macro"),
    "replay_mcc": matthews_corrcoef(y, pred),
    "replay_attack_recall": recall_score(y, pred),
    "replay_benign_recall": recall_score(y, pred, pos_label=0),
    "leaves_visited": int(len(np.unique(leaf))),
    "C": {k: coverage(leaf, k) for k in (1, 4, 8, 16, 32, 64)},
    "W": {q: working_set(leaf, q) for q in (0.9, 0.95, 0.99)},
    "H_norm": normalized_entropy(leaf, n_leaves),
}
day = pd.to_datetime(replay.ts.to_numpy(), unit="s").date
res["per_day"] = {}
for d in sorted(set(day)):
    m = day == d
    res["per_day"][str(d)] = {"rows": int(m.sum()), "leaves": int(len(np.unique(leaf[m]))),
                              "C8": coverage(leaf[m], 8), "W90": working_set(leaf[m], 0.9)}
benign = leaf[y == 0]
res["benign_only"] = {"rows": int(len(benign)), "leaves": int(len(np.unique(benign))),
                      "C8": coverage(benign, 8), "C32": coverage(benign, 32), "W90": working_set(benign, 0.9)}

train_leaf = tree.apply(X(train))
ids, cnt = np.unique(train_leaf, return_counts=True)
static_order = ids[np.argsort(-cnt)].tolist()
res["hit_rate"] = {}
for k in (4, 8, 16, 32):
    res["hit_rate"][k] = {
        "static_topk_from_train": simulate(StaticTopK(static_order), leaf, k).hit_rate,
        "lru": simulate(LRU(), leaf, k).hit_rate,
        "window_oracle_1M": simulate(WindowOracle(1_000_000), leaf, k).hit_rate,
        "belady": simulate(Belady(), leaf, k).hit_rate,
    }
(ROOT / "results/w1_pilot.json").write_text(json.dumps(res, indent=1, default=float))
print(json.dumps(res, indent=1, default=lambda v: round(float(v), 4)))

fig, ax = plt.subplots(1, 2, figsize=(9, 3.2))
_, c = np.unique(leaf, return_counts=True)
ax[0].loglog(np.arange(1, len(c) + 1), np.sort(c)[::-1] / c.sum(), marker=".")
ax[0].set(xlabel="leaf rank", ylabel="fraction of inferences", title="Leaf popularity (replay)")
_, cb = np.unique(benign, return_counts=True)
ax[1].loglog(np.arange(1, len(cb) + 1), np.sort(cb)[::-1] / cb.sum(), marker=".", color="C1")
ax[1].set(xlabel="leaf rank", title="Benign flows only")
fig.suptitle("PROVISIONAL pilot: DT depth 8, TON_IoT network, chronological replay", fontsize=9)
fig.tight_layout()
(ROOT / "figures").mkdir(exist_ok=True)
fig.savefig(ROOT / "figures/w1_pilot_leaf_popularity.pdf")
fig.savefig(ROOT / "figures/w1_pilot_leaf_popularity.png", dpi=130)
