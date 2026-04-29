# tools/

Source-of-truth TOML files for the registry, plus the script that rebuilds the
flat JSON index.

## `build-index.py` — registry index rebuild

Walks every `tools/*.toml` and writes `registry.json` at the repo root.

### Usage

```bash
# Rebuild the index from sources
python tools/build-index.py

# Verify the on-disk index is in sync with the TOML sources
python tools/build-index.py --check

# Write to a different path (useful for diffing or CI)
python tools/build-index.py --output /tmp/registry.json
```

The script resolves `tools/` and `registry.json` from its own location, so it
works from any current directory:

```bash
python ~/intracept-registry/tools/build-index.py
```

### What it does

1. Reads every `tools/*.toml` with `tomllib`.
2. Extracts `[[command]]` and `[[flag]]` arrays. The `tool` field on each record
   is derived from the filename (e.g. `git.toml` → `"git"`).
3. Validates per file: every `flag.applies_to` must reference a `path` defined
   in a `[[command]]` entry **in the same file**, and no `path` may repeat.
4. Validates across files: no two files may define the same `path`.
5. Writes a flat `registry.json` with two top-level keys:
   - `commands` — keyed by `path` (e.g. `"git push"`).
   - `flags` — keyed by `"<applies_to> <flag>"` (e.g. `"git push --force"`).
6. Output is byte-deterministic (`sort_keys=True`, `indent=2`, trailing newline)
   so re-running on the same inputs produces an identical file.

### When to run it

After any edit to `tools/*.toml`. Commit the regenerated `registry.json`
alongside the TOML change so consumers stay in sync.

### Requirements

Pure stdlib. Python 3.11+ (for `tomllib`).

---

## `lint.py` — registry linter

Validates TOML tool definitions against the schema and style rubric.

### Usage

```bash
# Lint all tools
python tools/lint.py tools/

# Lint a single file
python tools/lint.py tools/git.toml

# Machine-readable JSON output
python tools/lint.py --json tools/

# Exit code only, no output on success
python tools/lint.py --quiet tools/
```

### What it checks

- **Schema compliance** (error): required fields, valid risk values
- **Reference integrity** (error): flag `applies_to` must match a command in the same file
- **Translation rules** (error): length, capitalization, no command echo, ends with period
- **Modifier grammar** (warning): no trailing period, starts lowercase, gerund/preposition form
- **Consistency** (warning): low-risk with irreversibility language, critical without it
- **Rationale quality** (warning): length, not a copy of translation

### Exit codes

- `0` — no errors (warnings are OK)
- `1` — errors found

### Requirements

Pure stdlib. Python 3.11+ (for `tomllib`).
