# ML_P4

The MVM-Lite class project (in-network decision-tree inference on Tofino-1, W1–W8) lives in `mvm_lite/`; see `mvm_lite/README.md`. The current direction is the downgrade-attack paper in `docs/paper_plan.md` (code in `src/dgrade/`). History and status are in `WORKING_NOTES.md`.

## Standing rules
- Every commit is authored by akekulip <akekulip@gmail.com>, with no co-author or attribution lines. Never push.
- Never restart `bf_switchd` without Philip's explicit approval. Compile on the switch only in a separate build directory, and only with the switch's SDE 9.13.2.
- Kill processes by PID or `pkill -x` only, never `pkill -f`.
- Never print credentials. They come from `~/.lab_env`.

## Agent skills

### Issue tracker

Issues and specs are local markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default label strings (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root, created lazily. See `docs/agents/domain.md`.
