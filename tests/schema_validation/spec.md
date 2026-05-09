# Schema validation — test spec (registry side)

**Owner (registry side):** the `tools/build-index.py` + `tools/lint.py`
linter pipeline (extended in Phase 4a per TD-H3 / TD-H4 / TD-M15).
**Owner (intracept side):** see `intracept/tests/specs/schema_validation.md`.
**Author of both:** session C, Phase 1.
**Implementations gate on this spec.**

## What this side covers

The intracept-side spec covers the **rule schema** + **ToolSpec schema**
+ **policy.yml schema**. This side covers the **TOML schema** for
`intracept-registry/tools/*.toml`, validated against the same frozen
JSON-schema snapshot (Stream B's deliverable, expected at
`/Users/laurenalexander/intracept/fixtures/schema/`).

The TOML schema must round-trip every `tools/*.toml` file in the registry
without loss, and the linter must reject any TOML file that violates the
schema **fail-loud on missing or extra fields** — the briefing's specific
ask.

## Prerequisites

This spec's tests cannot run until **Stream B has posted the frozen JSON-schema
snapshot** at the path above. Until then:

- The `valid/` and `invalid/` fixtures exist as authored shapes (this
  document's responsibility).
- The test runner exists as a stub that fails with "schema snapshot not
  found at <path> — Session B has not posted yet."
- Once B posts, the test runner reads the snapshot and runs.

Session B's notification on the bus (context category `interface`) is the
trigger; session C will wire the snapshot-loading step then.

## Conformance fixtures

Lives at `intracept-registry/tests/schema_validation/fixtures/`:

### `valid/` (target: 12 cases)

Each is a complete `tools/{name}.toml` file that exercises a different
schema feature. Every fixture is also runnable through the existing
`tools/lint.py` so CI catches regressions in either implementation.

1. `valid/minimal.toml` — single command entry, just `verdict` and `binary`.
2. `valid/full-shape.toml` — every optional field populated.
3. `valid/with-tags.toml` — `tags = {scope = "...", target = [...], ...}`.
4. `valid/no-tags.toml` — exercises the TD-H2 sentinel-default decision.
   (Phase 1 picks: either downgrade `tags` to optional or define a sentinel.
   The fixture matches whichever wins.)
5. `valid/flag-modifiers.toml` — `[[flags.<name>.tag_modifiers]]` entries
   that override base tags per S3/S4/S6/S7's work.
6. `valid/combos.toml` — `[[combos]]` entries with derived tags per TD-M15.
7. `valid/subcommand-chain.toml` — multi-level subcommand structure
   (e.g., `gcloud compute instances delete`).
8. `valid/aliases.toml` — `aliases = ["...", "..."]`.
9. `valid/version-pin.toml` — `version_pin = "..."`.
10. `valid/candidate-only.toml` — `candidate_only = true` (auto-derived,
    not yet promoted).
11. `valid/multi-platform.toml` — `platforms = ["macos", "linux"]`.
12. `valid/all-three-verdicts.toml` — entries for `allow`, `ask`, `warn`
    in the same file.

### `invalid/` (target: 18 cases)

Each fixture is paired with `invalid/{name}.expected_error.json` of
`{kind, line: int?, col: int?, msg: string}`.

1. `invalid/typo-verdict.toml` — `verdict = "alllow"`. Per **TD-H3**
   specifically: this is the typo that motivates the lint rule. Expected
   error: `{kind: "invalid_verdict", msg: "...alllow..."}`.
2. `invalid/uppercase-verdict.toml` — `verdict = "Allow"`.
3. `invalid/legacy-verdict.toml` — `verdict = "require_approval"` (the v0
   alias being removed per TD-H6).
4. `invalid/missing-binary.toml` — required field missing.
5. `invalid/missing-verdict.toml` — required field missing.
6. `invalid/extra-field.toml` — `random_field = "foo"`. `additionalProperties:
   false` fires.
7. `invalid/wrong-type-tags.toml` — `tags = "scope=fs"` (string, not table).
8. `invalid/wrong-type-flags.toml` — `flags = ["--foo"]` (array, not table).
9. `invalid/effect-unknown-name.toml` — `effects = ["levitates"]`.
10. `invalid/duplicate-id.toml` — two entries with same `id` field
    (uniqueness violation).
11. `invalid/combo-bad-tag.toml` — combo declares tags that don't merge
    from base + flag modifiers per TD-M15. Expected error specifically
    cites which tag is unmergeable.
12. `invalid/combo-flag-not-in-flags.toml` — combo references a flag that
    isn't declared in the file's `[flags]` table.
13. `invalid/audience-out-of-enum.toml` — `audience = "wizard"`.
14. `invalid/version-pin-wildcard.toml` — `version_pin = "*"`.
15. `invalid/circular-extends.toml` — `extends = "self"` cycle.
16. `invalid/utf8-bom.toml` — file with BOM at start.
17. `invalid/duplicate-flag.toml` — same `--foo` declared twice in the
    `[flags]` table.
18. `invalid/orphan-tag-modifier.toml` — flag has `tag_modifiers` for
    dimensions the base doesn't declare (per R1's "tag_modifiers must only
    include dimensions the flag CHANGES" convention from prior session
    context).

## Live registry test (smoke)

Beyond the fixtures, the test runner:

19. Loads every `intracept-registry/tools/*.toml` (~1,195 files at time of
    writing) and runs schema validation on each. Asserts: zero failures.
    Any failure here is either a pre-existing TOML bug (file an issue) or
    a schema-too-strict bug (file against this spec).

20. Runs `python tools/build-index.py --check` and asserts exit 0
    (TD-H4 — already plumbed in `--check`). This catches the "TOML edited
    but registry.json not regenerated" drift.

## Linter integration

Per TD-H3 + TD-M15, the linter at `tools/lint.py` must mirror the schema's
`additionalProperties: false` + `verdict` enum + combo-tag-derivation
rules. This spec's tests cover the **schema-snapshot-driven** validator;
the linter is a separate code path that must produce equivalent
errors. The harness asserts:

21. For every `invalid/*.toml`, both the snapshot validator AND `lint.py`
    return a non-zero exit code with an error message that includes the
    fixture's expected error `kind` substring.

22. For every `valid/*.toml`, both the snapshot validator AND `lint.py`
    return exit 0.

The "both implementations agree" assertion is the same diff-CI pattern
TD-H1 uses for the three matchers — it's cheap insurance against schema
drift between the two enforcement points.

## What this spec does NOT cover

- The contents of the schema itself (Session B's deliverable).
- `registry.json` generation correctness (TD-H4 covers the freshness
  invariant; the contents are a downstream of the TOML schema).
- The `tag_modifiers`/`combos` semantics (S3/S4/S6/S7 already shipped
  these; this spec only validates schema-conformance, not the semantics).

## Sign-off

Same as the intracept-side spec.
