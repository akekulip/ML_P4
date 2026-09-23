"""TON_IoT processed network CSVs -> typed parquet, one file per source CSV."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.csv as pacsv

__all__ = ["NUMERIC_COLUMNS", "read_network_csv", "convert_all"]

logger = logging.getLogger(__name__)

NUMERIC_COLUMNS = [
    "ts", "src_port", "dst_port", "duration", "src_bytes", "dst_bytes", "missed_bytes",
    "src_pkts", "src_ip_bytes", "dst_pkts", "dst_ip_bytes", "dns_qclass", "dns_qtype",
    "dns_rcode", "http_request_body_len", "http_response_body_len", "http_status_code", "label",
]


def read_network_csv(path: Path) -> tuple[pd.DataFrame, dict[str, int]]:
    """Read one CSV with every column as string, then coerce the numeric columns.

    Returns the frame and, per numeric column, how many non-empty values failed to parse
    (those become NaN; the caller reports them rather than silently dropping rows).
    """
    header = path.open(encoding="utf-8-sig").readline().strip().split(",")
    table = pacsv.read_csv(
        path,
        read_options=pacsv.ReadOptions(column_names=header, skip_rows=1),
        convert_options=pacsv.ConvertOptions(column_types={c: pa.string() for c in header}),
    )
    df = table.to_pandas()
    failures: dict[str, int] = {}
    for col in NUMERIC_COLUMNS:
        parsed = pd.to_numeric(df[col], errors="coerce")
        failures[col] = int((parsed.isna() & df[col].notna() & (df[col] != "")).sum())
        df[col] = parsed
    df["ts"] = df["ts"].astype("int64")
    df["label"] = df["label"].astype("int8")
    return df, failures


def convert_all(src_dir: Path, dst_dir: Path) -> pd.DataFrame:
    """Convert every Network_dataset_*.csv to parquet; return a per-file audit table."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    files = sorted(src_dir.glob("Network_dataset_*.csv"), key=lambda p: int(p.stem.split("_")[-1]))
    for path in files:
        df, failures = read_network_csv(path)
        idx = int(path.stem.split("_")[-1])
        df.insert(0, "file_idx", idx)
        df.insert(1, "row_in_file", range(len(df)))
        df.to_parquet(dst_dir / f"{path.stem}.parquet", index=False)
        ts = df["ts"]
        rows.append({
            "file": idx,
            "rows": len(df),
            "ts_min": int(ts.min()),
            "ts_max": int(ts.max()),
            "ts_nondecreasing": bool(ts.is_monotonic_increasing),
            "ts_backsteps": int((ts.diff() < 0).sum()),
            "attack_rows": int(df["label"].sum()),
            "parse_failures": sum(failures.values()),
            "parse_failure_cols": {k: v for k, v in failures.items() if v},
        })
        logger.info("converted %s: %d rows", path.name, len(df))
    return pd.DataFrame(rows)
