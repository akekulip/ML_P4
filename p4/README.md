# MVM-Lite on BMv2

`mvm.p4` (v1model) holds up to K decision-tree leaves in `leaf_tbl`, one range-match entry per
leaf over ten 32-bit feature keys. The controller (`experiments/w5_bmv2.py`) sends each flow's
features as a P4Runtime packet-out and receives a packet-in with the query id, a hit flag, the
class and the leaf id. On a miss it runs the full tree and installs or evicts leaf entries.

## Feature keys (exact, no quantization)

The tree compares float32 inputs with float64 thresholds. `src/mvm/p4encode.py` maps each
float32 value to an order-preserving uint32 key: positive values get the sign bit set, and
negative values have all bits inverted. Each leaf box becomes one inclusive key range per
feature, so a range match reproduces the tree's comparisons exactly. `tests/test_p4encode.py`
checks this against `tree.apply`, including values at every split threshold.

## Build and run

```bash
p4c-bm2-ss --arch v1model --p4runtime-files p4/build/mvm.p4info.txt -o p4/build/mvm.json p4/mvm.p4
uv run python experiments/w5_bmv2.py --quick   # gate: 1,000 queries per slice
uv run python experiments/w5_bmv2.py           # 30,000 queries per slice
```

The script starts and stops `simple_switch_grpc` itself (`--no-p4`, gRPC on 127.0.0.1:50071,
CPU port 255). No network interfaces or sudo are needed.

## P4Runtime Python bindings

The PyPI `p4runtime` package ships generated code that is too old for protobuf 7. The bindings
in `src/p4gen` were generated from the P4Runtime v1.4.1 protos (`p4/proto_src`, from
github.com/p4lang/p4runtime) and googleapis `google/rpc` with:

```bash
uv run python -m grpc_tools.protoc -I p4/proto_src --python_out=src/p4gen --grpc_python_out=src/p4gen \
  p4/v1/p4runtime.proto p4/v1/p4data.proto p4/config/v1/p4info.proto p4/config/v1/p4types.proto \
  google/rpc/status.proto google/rpc/code.proto
```

## Scope

BMv2 is a software switch. Its latencies and update rates show that the mechanism works and how
it behaves, not ASIC performance. A Tofino-1 port would need 4–8-bit feature quantization,
because range keys there are limited to about 20 bits per table. See `docs/research_findings.md`.
