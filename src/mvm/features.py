"""Feature sets and train-only encoders for TON_IoT network flows.

Feature sets:
  dp        data-plane feasible: byte/packet/duration counters + proto + conn_state (main MVM set)
  full      sanitized ML baseline (brief set A): dp + Zeek service/DNS/HTTP/SSL/weird fields;
            free-text fields (dns_query, http_uri, user agent, cert subject/issuer, ...) dropped
  dp_ports  ablation: dp + src/dst port
  full_ids  ablation: full + ports + IPv4 octets (tests topology memorization)
Never features: ts (ordering only), label, type.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

__all__ = ["FEATURE_SETS", "FeatureSet", "columns_needed", "TreeEncoder", "FORBIDDEN"]

FORBIDDEN = {"ts", "label", "type"}

DP_NUM = ["duration", "src_bytes", "dst_bytes", "missed_bytes", "src_pkts", "dst_pkts", "src_ip_bytes", "dst_ip_bytes"]
DP_CAT = ["proto", "conn_state"]
FULL_NUM_EXTRA = ["dns_qclass", "dns_qtype", "dns_rcode", "http_request_body_len", "http_response_body_len", "http_status_code"]
FULL_CAT_EXTRA = [
    "service", "dns_AA", "dns_RD", "dns_RA", "dns_rejected", "ssl_version", "ssl_cipher", "ssl_resumed",
    "ssl_established", "http_trans_depth", "http_method", "http_version", "http_orig_mime_types",
    "http_resp_mime_types", "weird_name", "weird_notice",
]
PORTS = ["src_port", "dst_port"]
IPS = ["src_ip", "dst_ip"]


@dataclass(frozen=True)
class FeatureSet:
    name: str
    numeric: list[str]
    categorical: list[str]
    ips: list[str] = field(default_factory=list)  # expanded to 4 octet columns each

    @property
    def raw_columns(self) -> list[str]:
        return [*self.numeric, *self.categorical, *self.ips]


FEATURE_SETS = {
    "dp": FeatureSet("dp", DP_NUM, DP_CAT),
    "full": FeatureSet("full", DP_NUM + FULL_NUM_EXTRA, DP_CAT + FULL_CAT_EXTRA),
    "dp_ports": FeatureSet("dp_ports", DP_NUM + PORTS, DP_CAT),
    "full_ids": FeatureSet("full_ids", DP_NUM + FULL_NUM_EXTRA + PORTS, DP_CAT + FULL_CAT_EXTRA, IPS),
}


def columns_needed(fs: FeatureSet) -> list[str]:
    return sorted(set(fs.raw_columns) | {"label", "type", "ts", "file_idx", "row_in_file"})


def _octets(s: pd.Series) -> np.ndarray:
    parts = s.astype(str).str.split(".", expand=True).reindex(columns=range(4))
    out = parts.apply(pd.to_numeric, errors="coerce").to_numpy(float, copy=True)
    bad = np.isnan(out).any(axis=1) | (s.astype(str).str.count(r"\.") != 3).to_numpy()
    out[bad] = -1.0  # non-IPv4 (e.g. IPv6)
    return out


class TreeEncoder:
    """Numeric as-is (NaN -> -1). Each categorical is coded by the rank of its training attack
    rate (Breiman: optimal binary split ordering), categories seen < MIN_FREQ times share one
    bucket, unseen categories map to -1. Fit on training rows only."""

    MIN_FREQ = 20

    def __init__(self, fs: FeatureSet):
        self.fs = fs
        self.maps: dict[str, dict[str, float]] = {}

    def fit(self, df: pd.DataFrame, y: np.ndarray) -> "TreeEncoder":
        y = np.asarray(y, dtype=float)
        for c in self.fs.categorical:
            s = df[c].astype(str)
            counts = s.value_counts()
            rare = set(counts[counts < self.MIN_FREQ].index)
            s = s.where(~s.isin(rare), "__infrequent__")
            rate = pd.Series(y, index=s.index).groupby(s.values).mean()
            order = rate.sort_values(kind="stable")
            codes = {cat: float(i) for i, cat in enumerate(order.index)}
            for r in rare:
                codes[r] = codes["__infrequent__"]
            self.maps[c] = codes
        return self

    @property
    def feature_names(self) -> list[str]:
        return [*self.fs.numeric, *self.fs.categorical,
                *[f"{ip}_o{i}" for ip in self.fs.ips for i in range(4)]]

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        assert not FORBIDDEN & set(self.fs.raw_columns), "label/type/ts must never be features"
        blocks = [df[self.fs.numeric].to_numpy(float)]
        for c in self.fs.categorical:
            blocks.append(df[c].astype(str).map(self.maps[c]).fillna(-1.0).to_numpy(float)[:, None])
        blocks += [_octets(df[ip]) for ip in self.fs.ips]
        X = np.hstack(blocks)
        return np.nan_to_num(X, nan=-1.0)
