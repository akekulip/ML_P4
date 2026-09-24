# P13 (fixed): exploratory implementation study, not the evaluated design

This is P13, a post-hoc exploratory implementation study. It is **not** the paper's evaluated
design. The evaluated design is D4c, in `p4/dgrade_d4c/`, and nothing in this directory changes it.
Only the offline compiler was used: nothing here has run on the switch, on tofino-model, or on a lab host.

P13 is D4c with four changes: Pkt_Tree moved earlier (P1), a keyed additive identity tag
`tag = CRC_k(src, sport, proto) + CRC_k(dst, dport, proto)` (an ADD, which survives the linear
XOR-fold alias of the `@symmetric` hash), a lease packed into the existing 16-bit result register,
and the unwrapped (D1) clock.

## The bug this version fixes

The first P13 probe kept the keyed tag in its own register pair (`Register_ktag_A/B`) and read it
in a separate stateful ALU. Ownership was still decided by the weak 32-bit `flow_hash` match
(`Probe_id_*`), so a flow that aliased the weak hash but failed the keyed check still ran `Own_*`.
`Own_*` copied the victim's stored verdict into `ig_md.result`, and `Treatment` wrote it to the
packet. A failed alias therefore **inherited the victim's stale verdict**. The alias was also
treated as the owner in two other ways: the probe refreshed the victim's last-seen time, and the
placement logic never considered the slot as held by someone else.

The fix folds the keyed tag into the identity word that the probe's stateful ALU already compares:

```
id_key  = flow_hash[31:16] ++ (ep1 + ep2)      // stored in id_pair_t.hi, written by Claim_*
own     = (v.hi == id_key)                     // cmplo of the probe predicate
recent  = (now - v.lo < timeout_thres)         // cmphi, unchanged
```

The probe still uses two comparators and one predicate output, so it stays within the Tofino-1
stateful-ALU limits. A keyed-tag mismatch now makes the probe return `P_RECENT` or `P_IDLE`, never
`P_OWN*`. The results are:
- `Own_*` never runs, so the stored result is never copied. The alias takes the newcomer path,
  which sets `ig_md.result = 0` (the per-packet fallback).
- The probe does not refresh the victim's last-seen time, because that update is guarded by the
  same `v.hi == id_key` test.
- A live victim slot looks HELD to the alias (`st == P_RECENT`, unresolved, lease not expired), so
  the alias cannot take it over. The "prefer never-claimed B" test (`res != 0`) is a property of
  the slot, and it still marks the victim's slot as claimed.

The separate keyed-tag registers and their two stateful ALUs are removed. One side effect: the weak
part of the stored identity is now `flow_hash[31:16]` instead of all 32 bits. For way A the index
already implies `flow_hash[14:0]`, so only bit 15 is lost there. For way B, `flow_hash[15:0]` is no
longer checked. The keyed part stays at 16 bits, the same width as before.

## Compile

Local SDE 9.13.1 (`SDE=/home/philip/bf-sde-9.13.1`, `SDE_INSTALL=$SDE/install`), same invocation
as `p4/dgrade_d4c/compile.sh`:

```bash
$SDE_INSTALL/bin/bf-p4c --target tofino --arch tna -g --verbose 2 -o <build_dir> switch.p4
```

`parsers.p4` and `util.p4` are unchanged from `third_party/NetBeacon/switch/data_plane/`. They
differ only in CRLF line endings. Copy them next to `switch.p4` before you compile.

## Result (quoted from the compiler logs)

- Compile: `0 errors, 16 warnings generated.` (14 are `No size defined`); `tofino.bin` produced.
- `table_summary.log`: `Number of stages in table allocation: 12`,
  `Critical path length through the table dependency graph: 11`.

**This version uses 12 of 12 ingress stages, not 11.** It no longer saves a stage relative to
D4c, which also uses 12. The keyed tag is now an input to the probe, so the probe waits one stage
for the `ep1 + ep2` add. In the logs, the probe moves from stage 1 to stage 2 and every later table
moves one stage down. When it was first compiled with the stage pragmas inherited from NetBeacon,
it needed 13 stages (`tofino supports up to 12 stages, using 13`). Moving every `@pragma stage N`
with N >= 3 to N+1 (a placement hint only, with no change in behaviour) gives the 12-stage fit.
Removing those pragmas instead fails placement (`Register_min_pkt_length`).

| (mau.resources.log totals / metrics.json) | P13 original | P13 fixed (this dir) | delta |
|---|---|---|---|
| ingress stages | 11 | **12** | +1 |
| critical path | 10 | 11 | +1 |
| SRAM blocks | 201 | 191 | -10 |
| TCAM blocks | 91 | 94 | +3 |
| Meter ALU (stateful ALUs) | 16 | 14 | -2 |
| Hash Dist Units | 19 | 17 | -2 |
| Hash bits | 414 | 384 | -30 |
| Gateways | 49 | 45 | -4 |
| VLIW instr | 66 | 65 | -1 |
| logical tables | 102 | 96 | -6 |
| PHV containers 8b/16b/32b | 18/19/20 | 22/16/32 | +4/-3/+12 |
| Overall PHV bits | 1065 (26 %) | 1380 (33.7 %) | +315 |

## Alternative kept for the record: `p13gate_vs_p13.diff` (fits 11 stages, weaker fix)

This alternative keeps the separate keyed-tag registers and, on a mismatch in the owner branch, sets
`ig_md.result = 0` and skips the feature update. It compiles in `Number of stages in table
allocation: 11` with critical path 10, and its resources are identical to the original P13 except
for +1 gateway, +1 VLIW instruction and +1 logical table. It fixes the stale verdict only. The alias still refreshes
the victim's last-seen time (the probe's stateful ALU acts before the keyed check can be known), so
an attacker can keep a stale slot alive indefinitely. An alias that lands on an idle slot is also
refused when a normal newcomer would be admitted. Gating the placement decision itself on the
keyed check brings back the extra stage. Use the fixed design in this directory.

## Caveats carried over from P13

- The one-hot probe-predicate encoding (`P_IDLE..P_OWN_RECENT`) is assumed, not verified on the
  model or the switch.
- The lease expires 2^30 ns epochs after the last result *write*, not after the claim. Its
  semantics differ from the emulated D4age arm.
- Compile-feasible is not deployed. A run on the switch host (SDE 9.13.2) needs Philip's approval.

`p13fix_vs_p13.diff` is the full change of this directory's sources against the original P13 probe.
