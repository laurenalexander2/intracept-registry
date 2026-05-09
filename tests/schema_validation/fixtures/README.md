# Schema validation fixtures (registry side)

Each `valid/*.toml` should round-trip through both the snapshot validator
and `tools/lint.py` cleanly (exit 0).

Each `invalid/*.toml` has a paired `invalid/{name}.expected_error.json`.
The snapshot validator AND `tools/lint.py` must both reject the file.
The error must include the `kind` substring and (where present) the
`msg_contains` substring.

This directory contains a representative slice of the 30 cases declared
in `spec.md` — enough to anchor the test runner. The remaining cases
follow the same shape and are added as the linter implementation ships
in Phase 4a (per TD-H3 / TD-M15).

The full snapshot validator awaits Session B's frozen JSON-schema
snapshot at `/Users/laurenalexander/intracept/fixtures/schema/`. Until
then, only the `tools/lint.py` half of the diff-CI pattern is runnable;
the snapshot half is stubbed.
