# future-lint/ — fixtures that gate on Phase-4a TD-H3 lint update

These fixtures encode behaviors the lint MUST exhibit after the TD-H3 work
in Phase 4a lands:

1. **New verdict vocabulary** (`allow`, `ask`, `warn`) is the locked Phase 1
   vocabulary per TD-H6. Today's `tools/lint.py` only accepts the legacy
   2-tier `{allow, require_approval}`. The forward-vocab fixtures
   (`valid/all-three-verdicts.toml`, `valid/full-shape.toml`) sit here
   because today's lint REJECTS them; post-TD-H3 lint MUST ACCEPT them.

2. **Reject extra fields** (`additionalProperties: false` semantics).
   Today's lint accepts unknown TOML fields silently — the registry has no
   schema enforcement on extra-field shape, only on the values it knows.
   `invalid/extra-field.toml` is the canary fixture from the briefing.

3. **Reject duplicate paths** within a single `tools/*.toml` file.
   `path` is the de-facto id; today's lint silently accepts duplicates.
   `invalid/duplicate-id.toml` covers this.

The runner at `../../run.py` skips these fixtures by default and reports
"future-lint pending" so they don't show up as ordinary failures during
Phase 1. Once TD-H3 lands in Phase 4a:
- Move `valid/*` and `invalid/*` back up one level (out of `future-lint/`).
- Drop the runner's skip-future flag.
- The lint and the snapshot validator will agree, closing the diff.

The new-verdict-vocabulary work also requires that `tools/build-index.py`
emit the new vocabulary (or pass `require_approval` through unchanged for
backward compat — Phase 4a design call).
