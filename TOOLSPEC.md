# TOOLSPEC.md — the ToolSpec shape

**Status:** Phase 1 schema-lock draft. Repos: `[intracept-registry]` (this doc + the TOML carrier) and `[intracept]` (the Rust types).

**Audience:** stream leads (Phase 2 Stream B, Phase 2 Stream C, Phase 3 Stream E), TOML curators (Phase 4a top-50), auto-derive pipeline (Phase 4a).

A `ToolSpec` is the per-tool record the engine consults to turn a raw command into a `ParsedInvocation` — typed flags, typed positionals, and per-element effect annotations. Together with the parser daemon's AST, it is one of two inputs the verdict engine sees; pattern matching on raw text is removed from the hot path.

> **Position in the pipeline.** Raw command → parser daemon (`mvdan/sh`) emits AST → tool resolver picks a ToolSpec for the binary + subcommand chain → argspec parser binds AST to ToolSpec to produce `ParsedInvocation` (typed flags + typed positionals) → effect annotator emits the `effects` set per §1 of EFFECTS.md → verdict engine consumes effects + ParsedInvocation against the rule schema.

---

## 1. The shape

A ToolSpec is keyed by a `(tool, subcommand_chain, version_constraint)` triple and carries a typed flag set, a typed positional list, and per-element effect annotations.

```
ToolSpec {
  tool:                 string                        // binary name, e.g. "git", "gh", "kubectl"
  subcommand_chain:     [string]                      // [], ["push"], ["pr", "create"]
  version_constraint:   VersionConstraint?            // pin or "*"; see §4
  description:          string                        // one-sentence description (registry-side, surfaced to translator)

  flags:                [FlagSpec]                    // typed flag definitions
  positionals:          [PositionalSpec]              // typed positional definitions

  effects_default:      [Effect]                      // effects of the bare invocation (no flags, no positionals)
  effects_when_flag:    map<flag_name, [Effect]>      // additional effects when this flag is present
  effects_when_positional_present: map<positional_name, [Effect]>

  taint_sources:        [TaintSource]                 // which positionals/flags can introduce taint into argv (see EFFECTS.md §3)
  composition_hints:    CompositionHints              // per-tool composition rules (see §6)

  risk_class:           RiskClass                     // single-enum risk classification; values: safe | net_egress | novel | destructive | priv_esc | secret_read (locked, snake_case, per B's snapshot)
}
```

### `FlagSpec`

```
FlagSpec {
  name:               string             // canonical name, e.g. "force"
  short:              string?            // "-f" if any
  long:              [string]            // ["--force"]; multiple aliases supported
  arity:              FlagArity          // Boolean | Single | KeyValue | Repeated
  value_type:         ValueType?         // String | Path | Url | Int | Enum(values) | None for Boolean
  bundled_short_ok:   bool               // can this short form be bundled with others (rm -rf)?
  default_present:    bool               // is this flag implicitly applied by the tool unless suppressed?
  description:        string             // one-sentence; surfaced to translator
  effect_modifiers:   [Effect]?          // per-flag effect contribution (see §3)
  taint_introducing:  bool               // does this flag's value become argv to an exec (e.g., --exec, -c)?
}
```

`FlagArity`:
- `Boolean` — present/absent (e.g., `--force`)
- `Single` — takes exactly one value (e.g., `--message X`, `-m X`)
- `KeyValue` — takes a `key=value` pair (e.g., `-D foo=bar`)
- `Repeated` — may appear multiple times, accumulating values (e.g., `-v -v -v` for verbosity, `-D x -D y`)

`ValueType`:
- `String` — opaque
- `Path` — local filesystem path; the annotator inspects for FS effect attribution
- `Url` — URL; the annotator inspects scheme for `network` effect attribution
- `Int` — integer
- `Enum(values)` — closed set of valid string values
- (No `value_type` for `Boolean` arity)

### `PositionalSpec`

```
PositionalSpec {
  name:               string             // "path" / "url" / "branch"
  index:              int|"variadic"     // 0-indexed; "variadic" means "all remaining"
  required:           bool
  value_type:         ValueType
  description:        string
  effect_modifiers:   [Effect]?          // per-positional effect contribution
  taint_introducing:  bool
}
```

### `Effect`

The six-effect vocabulary defined in EFFECTS.md §1: `reads`, `writes`, `deletes`, `network`, `exec`, `env`, plus the `unknown` sentinel (annotator-internal; never authored). Wire format is snake_case. Aligned with B's frozen JSON-schema snapshot at `intracept/fixtures/schema/effects.json`. AST features (process-substitution, redirection, heredoc) are NOT effect enum members — they are AST detection inputs and are documented in EFFECTS.md §3.

### `TaintSource`

```
TaintSource {
  via:                FlagOrPositionalRef
  flows_to:           [TaintTarget]      // "argv" | "stdout" | "fs_path"
  default_taint:      Taint              // "static_argv" | "tainted_argv" | "dynamic_argv"
}
```

### `CompositionHints`

```
CompositionHints {
  pipeline_safe_for_dedup: bool          // can the translator collapse repeated flags within a pipeline stage?
  multi_invocation_idempotent: bool      // is `cmd; cmd` equivalent to `cmd`?
  preferred_short_form: string?          // canonical short form for translation (e.g. -rf preferred over -r -f)
}
```

---

## 2. Resolution: tool, subcommand chain, version

The tool resolver (Phase 2 Stream B) maps a raw command to a single `ToolSpec`. Resolution is **most-specific-wins**, the same rule the verdict engine uses.

### 2.1 Polyalias

`gh`, `gh pr`, and `gh pr create` are three distinct ToolSpecs:

| Raw command | Resolves to ToolSpec |
|-------------|----------------------|
| `gh --help` | `(gh, [])` |
| `gh pr` | `(gh, ["pr"])` |
| `gh pr create` | `(gh, ["pr", "create"])` |
| `gh pr create --title X` | `(gh, ["pr", "create"])` (flag is part of the FlagSpec, not the chain) |

Subcommand chains can nest arbitrarily deep (`aws s3api list-objects-v2`, `kubectl get pods`); the resolver walks the longest matching prefix and consumes those tokens before binding flags.

Subcommands that change semantics — `git config` vs `git config --global` — are modeled as flags on `git config`, not as a separate `(git, ["config", "--global"])` chain. The flag `--global` carries its own effect modifier and risk classification.

### 2.2 Version pinning

The registry ships ToolSpecs versioned per major-version family. Resolution prefers the specific version constraint that matches the binary's reported version (resolver runs `tool --version` once at install-time scan, caches in install-hook).

```
ToolSpec(tool=git, subcommand_chain=[], version_constraint="2.x")
ToolSpec(tool=git, subcommand_chain=[], version_constraint="*")  // fallback
```

Resolution order:
1. Exact version match.
2. Major-family match (e.g., `2.x` matches `git 2.43.0`).
3. `*` fallback.

If no fallback exists for a binary, the install-time scan emits an `unknown` ToolSpec stub and the verdict engine routes to the first-encounter background-async path (per §3 coverage SLA).

---

## 3. Per-element effect annotation

Effects are attributed at three levels of an invocation:

1. **Default effects** — what the bare invocation does. `git status` → `{reads}`. `ls` → `{reads}`.
2. **Flag-modified effects** — what changes when a flag is present. `git push --force` adds nothing to the effect set (the effect is `{network, writes}` either way), but flips a `safety_override` taint flag the verdict engine consumes. `git commit --amend` replaces `{writes}` with `{writes, deletes}` because amend rewrites the prior commit.
3. **Positional-modified effects** — what changes when a positional has a particular shape. `cp src dst` is `{reads, writes}`; if `dst` is `/dev/null`, the writes are filtered (per EFFECTS.md §3.5).

The merge rule for a given invocation:

```
effects(invocation) =
    effects_default
  ∪ ⋃ effects_when_flag[f] for each flag f present
  ∪ ⋃ effects_when_positional_present[p] for each positional p present
  ∪ effects from AST features (redirection, heredoc, process_substitution per EFFECTS.md §3)
  ∖ effects filtered by ephemeral-target rules (write to /dev/null, etc.)
```

Order does not matter (set union). Ephemeral filtering happens last.

---

## 4. TOML carrier (registry side)

The registry's `tools/<name>.toml` files extend additively to carry ToolSpec data. Today's TOML carries `[[command]]`, `[[flag]]`, `[[combo]]`. SCHEMA-v2.md adds:

- `[[command]].arity` (default `Boolean` if omitted, but `Boolean` only valid on flags — for `[[command]]` this is reserved future use).
- `[[command]].positionals` — array of inline tables with `name`, `index`, `required`, `value_type`, `description`, `effect_modifiers?`, `taint_introducing?`.
- `[[command]].effects_default` — array of effect strings drawn from EFFECTS.md §1.
- `[[command]].risk_class` — single enum; values `safe | net_egress | novel | destructive | priv_esc | secret_read` (snake_case, locked per B's snapshot at `intracept/fixtures/schema/toolspec.json`).
- `[[flag]].arity` — required.
- `[[flag]].value_type` — required when arity ≠ `Boolean`.
- `[[flag]].long`, `[[flag]].short` — split out of the existing `flag` field; the existing `flag = "--force"` stays as the canonical name and the resolver normalizes.
- `[[flag]].bundled_short_ok` — bool; default `true` if `short` is one character.
- `[[flag]].default_present` — bool; default `false`.
- `[[flag]].effect_modifiers` — array of effect strings.
- `[[flag]].taint_introducing` — bool; default `false`.

The existing tag axes (`tags.scope`, `tags.effect`, `tags.reversibility`, `tags.target`, `tags.safety_override`) are **dropped**. Per orchestrator's directive (2026-05-09), multi-axis tags collapse into a single `risk_class` enum on each `[[command]]` and `[[combo]]`. The 1,149 currently-untagged TOML files require only a single `risk_class` value, not the 5-axis backfill that the original schema would have demanded; the Phase 4a auto-derive pipeline supplies this single value during the curation pass.

> **Locked.** Field name `risk_class` and enum `{safe, net_egress, novel, destructive, priv_esc, secret_read}` are settled per orchestrator's autopilot ruling (2026-05-09) and B's frozen JSON-schema snapshot. SCHEMA-v2.md §3 is the authoritative reference; `tools/lint.py` enforces.

---

## 5. Validation rules

Lint enforces, in addition to current rules (period at end of translation, no flag duplicates, etc.):

1. Every `[[flag]].arity` must be one of `Boolean | Single | KeyValue | Repeated`.
2. Every `[[flag]]` with arity ≠ `Boolean` must declare `value_type`.
3. Every `value_type=Enum(...)` must include a non-empty value set.
4. Every `[[command]].positionals[].index` must be a non-negative integer or the literal string `"variadic"`; `"variadic"` may appear at most once and must be the highest-index positional.
5. Every effect string in `effects_default`, `effect_modifiers` must be drawn from EFFECTS.md §1's six-effect vocabulary (`reads`, `writes`, `deletes`, `network`, `exec`, `env`). The `unknown` sentinel is annotator-only and must not appear in author-supplied modifiers.
6. Every `[[command]].risk_class` value must be drawn from the locked enum: `{safe, net_egress, novel, destructive, priv_esc, secret_read}`.
7. Every `[[combo]].risk_class` is computed from the base command's `risk_class` plus flag modifiers and hand-verified — same pattern as the current combo-tag derivation rule (TD-M15, lint-recompute-and-error-on-mismatch).
8. `taint_introducing=true` on a flag or positional requires that flag/positional be referenced in the parent ToolSpec's `taint_sources` list.

---

## 6. Composition hints

Per-tool hints help the translator dedup and collapse output. Examples:

- `git`: `pipeline_safe_for_dedup=true` (a pipeline of `git log | grep` stays `git log` — the `grep` part is annotated separately).
- `find -exec`: `taint_introducing=true` on the positional `command` of `-exec`; the consuming command is parsed and annotated as a child ToolSpec.
- `xargs`: `taint_introducing=true` on stdin; the executed program is parsed and annotated independently.

The composition hints are advisory for the translator; they are not consulted by the verdict engine, which routes purely on effects + risk_class + rule matchers.

---

## 7. Migration: v0 → v2 TOML

Existing TOMLs migrate forward via the `engine/v0_to_v2.py` script (Phase 4a deliverable). Migration is mechanical for the structural fields:

- `[[command]].path` → unchanged (still the canonical key).
- `[[command]].translation`, `.verdict`, `.rationale` → unchanged.
- `[[command]].tags.*` (5-axis) → dropped; a `risk_class` value is generated either by hand-curation (top-50) or by the auto-derive pipeline (rest).
- `[[flag]].*` existing fields → unchanged; new fields (`arity`, `value_type`, etc.) are auto-derived from `--help` parse where possible, hand-curated for the top-50.
- `[[combo]].tags.*` → dropped, replaced by `risk_class`.

Re-running migration on a v2 file is a no-op (logs `already migrated` and exits 0). `--force` re-derives v2 from `tools/<name>.toml.v0.bak`.

---

## 8. Open questions

1. **Q5 — Severity-field shape on `Rule` (when verdict=warn).** Spelling and value set follow B's snapshot at `intracept/fixtures/schema/rule-schema-v2.json`. (The risk_class spelling question that earlier sat under Q5 is resolved — see §1 and §4 above.) Not a Phase 1 blocker.
2. **Q6 — `default_present` semantics.** Some tools have flags that are *implicitly applied* unless a `--no-FOO` form suppresses them (`git`'s `--quiet` defaulting; some shells' `set -e` defaulting). Should ToolSpec carry both the implicit flag and an explicit `--no-FOO` suppressor as a paired entry? Lean: yes — model both, mark the default-present one with `default_present=true`. Not a Phase 1 blocker.
3. **Q7 — Variadic positional semantics.** A variadic positional (`rm path...`) accumulates as a list; the annotator must apply each instance's `effect_modifiers` independently (so `rm a b c` is three writes/deletes, not one). Lean: yes — variadic = "apply effects per element"; `taint_introducing=true` on a variadic means "any element introduces taint" rather than "all elements together do." Not a Phase 1 blocker.
