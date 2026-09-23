"""W1 data audit: convert TON_IoT network CSVs to parquet and report ts order, counts, parse failures."""

import json
import logging
from pathlib import Path

import pandas as pd

from mvm.data import convert_all

logging.basicConfig(level=logging.INFO, format="%(message)s")
ROOT = Path(__file__).resolve().parents[1]

audit = convert_all(ROOT / "data/raw/network", ROOT / "data/processed/network")
audit.to_csv(ROOT / "results/w1_file_audit.csv", index=False)
pd.set_option("display.width", 200)
print(audit.drop(columns="parse_failure_cols").to_string(index=False))
print("parse failure columns:", json.dumps(audit["parse_failure_cols"].tolist()))

cols = ["file_idx", "ts", "label", "type"]
df = pd.read_parquet(ROOT / "data/processed/network", columns=cols)
summary = {
    "total_rows": len(df),
    "type_counts": df["type"].value_counts().to_dict(),
    "label_counts": df["label"].value_counts().to_dict(),
    "global_ts_min": int(df.ts.min()),
    "global_ts_max": int(df.ts.max()),
    "files_in_ts_order": bool((audit.sort_values("file").ts_min.diff().dropna() >= 0).all()),
    "file_ts_ranges_overlap": bool((audit.sort_values("ts_min").ts_min.values[1:] < audit.sort_values("ts_min").ts_max.values[:-1]).any()),
    "unique_ts": int(df.ts.nunique()),
    "type_by_day": pd.crosstab(pd.to_datetime(df.ts, unit="s").dt.date.astype(str), df["type"]).to_dict(orient="index"),
}
(ROOT / "results/w1_data_summary.json").write_text(json.dumps(summary, indent=1, default=int))
print(json.dumps({k: v for k, v in summary.items() if k != "type_by_day"}, indent=1, default=int))
print(pd.crosstab(pd.to_datetime(df.ts, unit="s").dt.date, df["type"]).to_string())
