# Schema validation fixtures (registry side)

Two enforcement surfaces, one runner:

## `valid/json/` + `invalid/json/`

Validated against Session B's frozen JSON-schema snapshot at
`/Users/laurenalexander/intracept/fixtures/schema/{rule-schema-v2,
toolspec, effects}.json`. These exercise the *compiled* `ToolSpec` /
`Rule` records the matcher consumes.

Vocabulary: locked Phase 1 `{allow, ask, warn}`. `require_approval` is
rejected at the JSON-Schema level — the alias is a deserializer-side
convenience on the Rust types, not part of the published schema enum.

## `valid/*.toml` + `invalid/*.toml`

Validated against the registry's existing `tools/lint.py`. These exercise
the *source* `tools/*.toml` shape declared in `SCHEMA.md`. Today's lint
enforces the v0/v1 vocabulary `{allow, require_approval}`; new vocab
lands with TD-H3 in Phase 4a.

## `future-lint/`

Fixtures that gate on the Phase 4a TD-H3 lint update — new vocabulary,
`additionalProperties: false`, duplicate-path detection. Runner skips
these and reports `N future-lint fixtures pending TD-H3`. Once TD-H3
ships, move them up one level and the diff between snapshot and lint
collapses.

## Running

```sh
python3 tests/schema_validation/run.py
```

Exit codes: `0` = all green, `1` = a fixture failed, `2` = snapshot not
found at the expected path (Session B regression), `127` = `jsonschema`
not installed (`pip install jsonschema`).
