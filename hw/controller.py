#!/usr/bin/env python3
"""MVM-Lite controller for the Tofino-1 switch (runs on the switch CPU, Python 3.8 + bfrt_grpc).

Standalone: needs only model.json (from experiments/w8_prepare.py) and the SDE's bfrt_grpc.
  setup   bring up dev ports 9 (Vision) and 10 (Hulk), install port_fwd and the static per-feature
          fine/coarse tables (thermometer codes)
  run     clear leaf_tbl, then serve miss digests: find the query's leaf from its feature keys,
          update decayed LFU (gamma per query id), and install / evict leaf entries so that at most
          K are resident. Hits never reach the controller, so resident leaves are credited from
          their direct counters, polled every --poll-ms (the implementable form of decayed LFU).
          Every digest and every table write is logged with wall-clock times.
"""

import argparse
import csv
import json
import math
import os
import signal
import sys
import threading
import time

SDE_INSTALL = os.environ.get("SDE_INSTALL", "/home/decps/Downloads/bf-sde-9.13.2/install")
for sub in ("tofino", "tofino/bfrt_grpc"):
    sys.path.append(os.path.join(SDE_INSTALL, "lib/python3.8/site-packages", sub))
import bfrt_grpc.client as gc  # noqa: E402

PROG = "mvm_tna"
DP_VISION, DP_HULK = 9, 10


def connect(addr):
    intf = gc.ClientInterface(addr, client_id=0, device_id=0)
    intf.bind_pipeline_config(PROG)
    return intf, intf.bfrt_info_get(PROG), gc.Target(device_id=0, pipe_id=0xFFFF)


def table(bfrt, name):
    for n in (name, "pipe." + name, "pipe.Ingress." + name, "Ingress." + name):
        try:
            return bfrt.table_get(n)
        except Exception:
            continue
    raise KeyError(name)


def setup(bfrt, tgt, model):
    port = bfrt.table_get("$PORT")
    have = {}
    for data, key in port.entry_get(tgt, flags={"from_hw": False}):
        have[key.to_dict()["$DEV_PORT"]["value"]] = data.to_dict()
    for dp in (DP_VISION, DP_HULK):
        if dp in have:
            print("dp%d present: enable=%s up=%s" % (dp, have[dp].get("$PORT_ENABLE"), have[dp].get("$PORT_UP")))
            continue
        port.entry_add(tgt, [port.make_key([gc.KeyTuple("$DEV_PORT", dp)])], [port.make_data([
            gc.DataTuple("$SPEED", str_val="BF_SPEED_25G"),
            gc.DataTuple("$FEC", str_val="BF_FEC_TYP_REED_SOLOMON"),
            gc.DataTuple("$AUTO_NEGOTIATION", str_val="PM_AN_DEFAULT"),
            gc.DataTuple("$LOOPBACK_MODE", str_val="BF_LPBK_NONE"),
            gc.DataTuple("$PORT_ENABLE", bool_val=True)])])
        print("dp%d added 25G RS-FEC" % dp)

    pf = table(bfrt, "port_fwd")
    pf.entry_del(tgt)
    pf.entry_add(tgt, [pf.make_key([gc.KeyTuple("ig_intr_md.ingress_port", a)]) for a in (DP_HULK, DP_VISION)],
                 [pf.make_data([gc.DataTuple("port", b)], "Ingress.fwd") for b in (DP_VISION, DP_HULK)])

    n_fine = n_coarse = 0
    for f in model["features"]:
        if f["width"] == 0:
            continue
        i = f["index"]
        fine, coarse = table(bfrt, "fine%d" % i), table(bfrt, "coarse%d" % i)
        fine.entry_del(tgt)
        coarse.entry_del(tgt)
        act = "Ingress.set_code%d" % i
        keys = [fine.make_key([gc.KeyTuple("f%d_hi" % i, b), gc.KeyTuple("f%d_lo" % i, low=lo, high=hi),
                               gc.KeyTuple("$MATCH_PRIORITY", 1)]) for b, lo, hi, _ in f["fine"]]
        data = [fine.make_data([gc.DataTuple("c", c)], act) for _, _, _, c in f["fine"]]
        if keys:
            fine.entry_add(tgt, keys, data)
        keys = [coarse.make_key([gc.KeyTuple("f%d_hi" % i, low=lo, high=hi), gc.KeyTuple("$MATCH_PRIORITY", 1)])
                for lo, hi, _ in f["coarse"]]
        data = [coarse.make_data([gc.DataTuple("c", c)], act) for _, _, c in f["coarse"]]
        coarse.entry_add(tgt, keys, data)
        n_fine += len(f["fine"])
        n_coarse += len(f["coarse"])
    print("static tables installed: %d fine, %d coarse entries" % (n_fine, n_coarse))


class DecayedLFU:
    """Decayed LFU with the exact time-free eviction key log S - t_last * ln(gamma) (see mvm.cache)."""

    def __init__(self, k, gamma):
        self.k, self.lng = k, math.log(gamma)
        self.gamma = gamma
        self.score, self.last, self.resident = {}, {}, set()

    def credit(self, leaf, t, n=1):
        prev = self.score[leaf] * self.gamma ** (t - self.last[leaf]) if leaf in self.score else 0.0
        self.score[leaf], self.last[leaf] = prev + n, t

    def evict_key(self, leaf):
        return math.log(self.score[leaf]) - self.last[leaf] * self.lng

    def miss(self, leaf, t):
        """Returns (install, victim) for a miss on leaf at query time t."""
        self.credit(leaf, t)
        if self.k == 0:               # CPU-only mode: nothing is ever resident in the switch
            return False, None
        if leaf in self.resident:     # already installed; the packet raced the install
            return False, None
        victim = None
        if len(self.resident) >= self.k:
            victim = min(self.resident, key=lambda j: (self.evict_key(j), self.last[j]))
            self.resident.remove(victim)
        self.resident.add(leaf)
        return True, victim


def leaf_of(keys, leaves):
    for lf in leaves:
        lo, hi = lf["key_lo"], lf["key_hi"]
        if all(lo[i] <= keys[i] <= hi[i] for i in range(10)):
            return lf
    raise ValueError("no leaf matches %r" % (keys,))


def run(intf, bfrt, tgt, model, args):
    leaf_tbl = table(bfrt, "leaf_tbl")
    leaf_tbl.entry_del(tgt)
    feats = [f for f in model["features"] if f["width"] > 0]
    by_id = {lf["leaf_id"]: lf for lf in model["leaves"]}

    def key_for(lf):
        return leaf_tbl.make_key([gc.KeyTuple("md.code%d" % f["index"], value=lf["tern"][f["index"]][0],
                                              mask=lf["tern"][f["index"]][1]) for f in feats]
                                 + [gc.KeyTuple("$MATCH_PRIORITY", 1)])

    learn = None
    for n in ("pipe.IgDeparser.miss_digest", "IgDeparser.miss_digest", "miss_digest"):
        try:
            learn = bfrt.learn_get(n)
            break
        except Exception:
            continue
    assert learn is not None, "digest learn object not found"

    pol = DecayedLFU(args.k, args.gamma)
    keys_of, last_count = {}, {}
    lock = threading.Lock()
    stop = threading.Event()
    t_now = [0]
    log = open(args.log, "w", newline="")
    _w = csv.writer(log)
    log_lock = threading.Lock()   # TextIOWrapper is not thread-safe: two unsynchronized writers corrupted a log

    class _LockedWriter:
        def writerow(self, row):
            with log_lock:
                _w.writerow(row)

    w = _LockedWriter()
    w.writerow(["event", "wall_ns", "qid", "leaf", "installed", "victim", "write_done_ns", "credited"])

    def poller():
        while not stop.is_set():
            time.sleep(args.poll_ms / 1000.0)
            with lock:
                res = list(pol.resident)
            if not res:
                continue
            try:
                got = leaf_tbl.entry_get(tgt, [keys_of[l] for l in res if l in keys_of], {"from_hw": True})
                counts = {}
                for data, key in got:
                    d = data.to_dict()
                    counts[int(d["leaf"])] = int(d.get("$COUNTER_SPEC_PKTS", 0))
            except Exception as e:  # entry evicted between snapshot and read
                w.writerow(["poll_error", time.time_ns(), -1, -1, 0, -1, 0, str(e)[:60]])
                continue
            with lock:
                for l, c in counts.items():
                    d = c - last_count.get(l, 0)
                    last_count[l] = c
                    if d > 0 and l in pol.resident:
                        pol.credit(l, t_now[0], d)
                        w.writerow(["credit", time.time_ns(), t_now[0], l, 0, -1, 0, d])

    threading.Thread(target=poller, daemon=True).start()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    print("serving digests (K=%d, gamma=%g, poll=%d ms)" % (args.k, args.gamma, args.poll_ms), flush=True)
    while not stop.is_set():
        try:
            digest = intf.digest_get(timeout=1)
        except Exception:
            continue
        recv = time.time_ns()
        for d in learn.make_data_list(digest):
            dd = d.to_dict()
            qid = int(dd["qid"])
            keys = [int(dd["f%d" % i]) for i in range(10)]
            lf = leaf_of(keys, model["leaves"])
            leaf = lf["leaf_id"]
            with lock:
                t_now[0] = max(t_now[0], qid)
                install, victim = pol.miss(leaf, qid)
                if install:
                    if victim is not None:
                        leaf_tbl.entry_del(tgt, [keys_of.pop(victim)])
                        last_count.pop(victim, None)
                    keys_of[leaf] = key_for(lf)
                    leaf_tbl.entry_add(tgt, [keys_of[leaf]],
                                       [leaf_tbl.make_data([gc.DataTuple("leaf", leaf), gc.DataTuple("klass", lf["klass"])],
                                                           "Ingress.leaf_hit")])
                    last_count[leaf] = 0
            w.writerow(["miss", recv, qid, leaf, int(install), -1 if victim is None else victim, time.time_ns(), 0])
        try:
            learn.message_digest_notify_ack(digest.msg_ptr)
        except Exception:
            pass
    time.sleep(args.poll_ms / 1000.0 * 2)   # let the poller finish its last write before closing
    with log_lock:
        log.close()
    print("controller stopped", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["setup", "run"])
    ap.add_argument("--model", default=os.path.expanduser("~/ml_p4/model.json"))
    ap.add_argument("--grpc", default="localhost:50052")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--gamma", type=float, default=0.99)
    ap.add_argument("--poll-ms", type=int, default=20)
    ap.add_argument("--log", default="controller_log.csv")
    args = ap.parse_args()
    model = json.load(open(args.model))
    intf, bfrt, tgt = connect(args.grpc)
    if args.cmd == "setup":
        setup(bfrt, tgt, model)
    else:
        run(intf, bfrt, tgt, model, args)


if __name__ == "__main__":
    main()
