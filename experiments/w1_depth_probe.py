"""W1 PROVISIONAL depth probe: does a capacity-constrained regime exist? Same setup as w1_pilot."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, matthews_corrcoef
from sklearn.preprocessing import OrdinalEncoder
from sklearn.tree import DecisionTreeClassifier

from mvm.cache import LRU, simulate
from mvm.locality import coverage, normalized_entropy, working_set

ROOT = Path(__file__).resolve().parents[1]
NUM = ["duration", "src_bytes", "dst_bytes", "missed_bytes", "src_pkts", "dst_pkts", "src_ip_bytes", "dst_ip_bytes"]
CAT = ["proto", "service", "conn_state"]

df = pd.read_parquet(ROOT / "data/processed/network", columns=["ts", *NUM, *CAT, "label", "type"])
df = df.dropna(subset=NUM).sort_values("ts", kind="stable").reset_index(drop=True)
train_idx = df.groupby("type", group_keys=False).apply(lambda g: g.sample(min(len(g), 20_000), random_state=0)).index
train, replay = df.loc[train_idx], df.drop(index=train_idx)
enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1).fit(train[CAT])
def X(d): return np.hstack([d[NUM].to_numpy(float), enc.transform(d[CAT])])
Xt, Xr, y = X(train), X(replay), replay.label.to_numpy()
benign = y == 0

rows = []
for depth in (4, 6, 8, 10, 12, 16, None):
    tree = DecisionTreeClassifier(max_depth=depth, random_state=0).fit(Xt, train.label)
    leaf, pred = tree.apply(Xr), tree.predict(Xr)
    n = tree.get_n_leaves()
    rows.append({
        "depth": depth or "None", "leaves": n, "macro_f1": f1_score(y, pred, average="macro"),
        "mcc": matthews_corrcoef(y, pred), "W90": working_set(leaf, .9), "W99": working_set(leaf, .99),
        "H_norm": normalized_entropy(leaf, n), "benign_W90": working_set(leaf[benign], .9),
        "benign_W99": working_set(leaf[benign], .99),
        **{f"lru_K{k}": simulate(LRU(), leaf, k).hit_rate for k in (8, 32, 128)},
        **{f"benign_lru_K{k}": simulate(LRU(), leaf[benign], k).hit_rate for k in (8, 32, 128)},
    })
    print(rows[-1], flush=True)
out = pd.DataFrame(rows)
out.to_csv(ROOT / "results/w1_depth_probe.csv", index=False)
print(out.round(3).to_string(index=False))
