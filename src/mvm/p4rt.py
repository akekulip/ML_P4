"""Minimal P4Runtime client for the MVM BMv2 prototype (mastership, pipeline, range entries, packet I/O).

Bindings are generated from the P4Runtime v1.4.1 protos into src/p4gen (see p4/README.md); the
PyPI `p4runtime` package ships pb2 code too old for the installed protobuf.
"""

from __future__ import annotations

import queue
import sys
import threading
from pathlib import Path

import grpc
from google.protobuf import text_format

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "p4gen"))
from p4.config.v1 import p4info_pb2  # noqa: E402
from p4.v1 import p4runtime_pb2 as pr  # noqa: E402
from p4.v1 import p4runtime_pb2_grpc as prg  # noqa: E402

__all__ = ["P4RTClient", "canonical"]


def canonical(value: int) -> bytes:
    """P4Runtime canonical bytestring: big-endian, no leading zero bytes, at least one byte."""
    n = max(1, (int(value).bit_length() + 7) // 8)
    return int(value).to_bytes(n, "big")


class P4RTClient:
    def __init__(self, addr: str, p4info_txt: Path, device_id: int = 0):
        self.device_id = device_id
        self.election = pr.Uint128(high=0, low=1)
        self.channel = grpc.insecure_channel(addr)
        grpc.channel_ready_future(self.channel).result(timeout=20)
        self.stub = prg.P4RuntimeStub(self.channel)
        self.p4info = text_format.Parse(Path(p4info_txt).read_text(), p4info_pb2.P4Info())
        self._req: queue.Queue = queue.Queue()
        self.packet_in: queue.Queue = queue.Queue()
        self._arb = threading.Event()
        self._stream = self.stub.StreamChannel(iter(self._req.get, None))
        threading.Thread(target=self._reader, daemon=True).start()
        self._req.put(pr.StreamMessageRequest(arbitration=pr.MasterArbitrationUpdate(
            device_id=device_id, election_id=self.election)))
        if not self._arb.wait(10):
            raise TimeoutError("no mastership arbitration response")

    def _reader(self):
        try:
            for resp in self._stream:
                kind = resp.WhichOneof("update")
                if kind == "arbitration":
                    self._arb.set()
                elif kind == "packet":
                    self.packet_in.put(resp.packet)
        except grpc.RpcError as e:  # CANCELLED on close() is the normal shutdown path
            if e.code() != grpc.StatusCode.CANCELLED:
                raise

    # --- P4Info lookups -------------------------------------------------------------------------
    def table(self, name):
        return next(t for t in self.p4info.tables if t.preamble.name.endswith(name))

    def action(self, name):
        return next(a for a in self.p4info.actions if a.preamble.name.endswith(name))

    def packet_md(self, name):
        cpm = next(c for c in self.p4info.controller_packet_metadata if c.preamble.name == name)
        return {m.name: m.id for m in cpm.metadata}

    # --- pipeline and entries -------------------------------------------------------------------
    def set_pipeline(self, bmv2_json: Path):
        cfg = pr.ForwardingPipelineConfig(p4info=self.p4info, p4_device_config=Path(bmv2_json).read_bytes())
        self.stub.SetForwardingPipelineConfig(pr.SetForwardingPipelineConfigRequest(
            device_id=self.device_id, election_id=self.election,
            action=pr.SetForwardingPipelineConfigRequest.VERIFY_AND_COMMIT, config=cfg))

    def range_entry(self, table: str, ranges, action: str, params: dict, priority: int = 1, width_max=0xFFFFFFFF):
        """ranges: per key field (lo, hi); full-width ranges are omitted (P4Runtime don't-care rule)."""
        t, a = self.table(table), self.action(action)
        matches = []
        for mf, (lo, hi) in zip(t.match_fields, ranges):
            if int(lo) == 0 and int(hi) == width_max:
                continue
            matches.append(pr.FieldMatch(field_id=mf.id, range=pr.FieldMatch.Range(low=canonical(lo), high=canonical(hi))))
        pid = {p.name: p.id for p in a.params}
        act = pr.Action(action_id=a.preamble.id,
                        params=[pr.Action.Param(param_id=pid[k], value=canonical(v)) for k, v in params.items()])
        return pr.TableEntry(table_id=t.preamble.id, match=matches, priority=priority,
                             action=pr.TableAction(action=act))

    def write(self, entries, kind: str = "INSERT"):
        typ = {"INSERT": pr.Update.INSERT, "DELETE": pr.Update.DELETE, "MODIFY": pr.Update.MODIFY}[kind]
        self.stub.Write(pr.WriteRequest(device_id=self.device_id, election_id=self.election,
                                        updates=[pr.Update(type=typ, entity=pr.Entity(table_entry=e)) for e in entries]))

    def read_table_count(self, table: str) -> int:
        req = pr.ReadRequest(device_id=self.device_id,
                             entities=[pr.Entity(table_entry=pr.TableEntry(table_id=self.table(table).preamble.id))])
        return sum(len(r.entities) for r in self.stub.Read(req))

    # --- packet I/O -----------------------------------------------------------------------------
    def packet_out(self, payload: bytes, metadata: dict[int, int]):
        self._req.put(pr.StreamMessageRequest(packet=pr.PacketOut(
            payload=payload, metadata=[pr.PacketMetadata(metadata_id=k, value=canonical(v)) for k, v in metadata.items()])))

    def close(self):
        self._req.put(None)
        self.channel.close()
