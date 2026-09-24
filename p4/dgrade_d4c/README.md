# D4c (two-table admission) for NetBeacon on Tofino-1: compile-only study

`switch.p4` and `headers.p4` are NetBeacon's data plane (third_party/NetBeacon, MIT licence, Copyright (c) 2023 IDP) modified to implement the D4c
variant "P-b" (identity registers split per way, second hash, D4c placement). `parsers.p4` and `util.p4` are unchanged; take them from the NetBeacon
artifact. `pb_vs_base.diff` is the change against the unmodified NetBeacon sources. `compile.sh` and `extract.py` are the helpers used for the offline
compile with the local SDE 9.13.1 (`bf-p4c --target tofino --arch tna`). **Compile-only: nothing was run on the switch or the model.** Results and caveats:
`docs/results_d4c_compile.md`.
