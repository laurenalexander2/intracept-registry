# SCHEMA-v2.md — additive TOML migration spec

**Status:** Phase 1 schema-lock authoritative. Repo: `[intracept-registry]`. Extends `SCHEMA.md` (v0) additively; v0 fields stay valid through the migration window with documented `serde` aliases on the engine side. **The acceptance gate for this phase is that every downstream stream lead can produce a passing test fixture against the frozen JSON-schema snapshot at `intracept/fixtures/schema/{rule-schema-v2,toolspec,effects}.json` before they cut their branch.**

**Audience:** TOML curators (Phase 4a top-50 hand-curate), the auto-derive pipeline (Phase 4a), the v0→v2 migration tool, lint authors.

**Companions:** `TOOLSPEC.md` (the Rust ToolSpec shape), `EFFECTS.md` (the typed-effects vocabulary).

---

## 1. What changed from v0

Five locked changes from `SCHEMA.md`:

1. **Verdicts collapse from four to three.** v0's `{allow, require_approval}` (TOML side) and v0/v1's Rust `Verdict { Allow, Warn, RequireApproval, Deny }` collapse to `{allow, ask, warn}`. `require_approval` is preserved as a deserialization alias for `ask` for v0/v1 policy.yaml compatibility (per session B's lock); the canonical wire form is `ask`. `Deny` is deleted (TD-H6, TD-H12).
2. **Multi-axis tags drop, single `risk_class` enum replaces them.** v0's five-axis tag block (`tags.scope`, `tags.effect`, `tags.reversibility`, `tags.target`, `tags.safety_override`) is removed. Each `[[command]]` and `[[combo]]` carries one `risk_class` value drawn from a six-member enum. (Per orchestrator directive 2026-05-09.)
3. **Effects move out of TOML.** v0's `tags.effect` axis is gone; effects are auto-populated by the engine annotator from the AST + ToolSpec at parse time (see EFFECTS.md). Curators never set effects by hand.
4. **`ToolSpec` shape extends additively.** New required fields on `[[command]]` and `[[flag]]` (typed flag arity, value types, positional declarations, per-flag/per-positional effect modifiers, taint-source declarations) — see TOOLSPEC.md §4 for the full TOML carrier.
5. **Resolution algorithm formalized.** The layered composition and same-layer refuse-to-load behavior is locked here authoritatively (§5).

Everything else in `SCHEMA.md` (file naming, translation/rationale style guides, composition rule for `translation_modifier`, lookup order including combo subset matching, validation rules unrelated to tags) carries forward unchanged.

---

## 2. Verdict tiers

Three tiers, all deterministic. Locked.

| Tier    | Semantics |
|---------|-----------|
| `allow` | Command runs automatically. Logged. Use for read-only operations, local dev workflow, trivially reversible actions. |
| `ask`   | Command pauses for a neutral confirmation prompt. Use for non-allowlisted network egress, novel/unknown operations, irreversible-but-recoverable actions. |
| `warn`  | Command pauses for a *severity-framed* confirmation prompt — the same blocking behavior as `ask` plus a severity layer surfaced to the user. Use for destructive operations, privileged escalation, secret reads, and other cases where the user benefits from an explicit "this is dangerous" framing. |

`ask` and `warn` block identically; the difference is the prompt text the user sees. Both are first-class severity tiers — `warn` is **not** a stricter type of `ask` in any technical sense, but the prompt UX makes it look stricter.

### v0/v1 compatibility (deserialization aliases, locked by B in `intracept-shared::schema`)

| v0/v1 wire string | v2 wire string | Rust variant |
|--------------------|----------------|---------------|
| `"allow"`         | `"allow"`     | `Verdict::Allow` |
| `"require_approval"` | `"ask"`       | `Verdict::Ask` (alias) |
| `"warn"` (legacy alias for `RequireApproval`) | (no v2 equivalent) | rejected at the new schema's JSON-Schema level — per C's runner |

The `require_approval` alias exists only so that v0/v1 `policy.yaml` files deserialize without breaking; new authoring must use `ask`. Migration produces v2-only output.

### Severity field (optional, on `Rule` only — not on `[[command]]`/`[[combo]]`)

Rules whose `verdict = warn` may carry an optional `severity` field. Used by the prompt UX to populate the severity-framed prompt copy. **Not** consulted by the verdict engine for routing — verdict resolution still routes purely on `risk_class` plus rule matchers. Spelling and value set follow B's snapshot at `intracept/fixtures/schema/rule-schema-v2.json`.

---

## 3. Risk_class enum

Each `[[command]]` and `[[combo]]` carries a single `risk_class` field. Six values, snake_case wire format, locked in coordination with B (2026-05-09).

| `risk_class`             | Default verdict (registry layer) | When to use |
|---------------------------|----------------------------------|-------------|
| `safe`                   | `allow`                          | Read-only or trivially-reversible local operations. `ls`, `cat`, `git status`, `cd`, `echo`. |
| `net_egress`             | `ask`                            | Outbound network operations. Default posture is "talking to a host the user has not allowlisted." `curl <url>`, `wget`, `nc <host> <port>`, `ssh <user>@<host>` (when the host is not in `~/.ssh/known_hosts` or the org allowlist). Authenticated egress to a known target (`git push` to a configured remote) is *also* tagged `net_egress` at curation time; the rule schema's host-allowlist matcher refines authed/unauthed at runtime. (No `_unauthed` suffix on the enum value — authed/unauthed is a runtime-matcher concern, not a curator vocabulary axis.) |
| `novel`                  | `ask`                            | Sentinel for uncurated entries. Auto-derive pipeline (Phase 4a) replaces with a real `risk_class` once the tool is curated. The first-encounter background-async path treats novel-classed invocations as the canonical "first invocation = ask, spec fills for #2" case. |
| `destructive`            | `warn`                           | Operations that destroy persistent state. `rm`, `git push --force`, `kubectl delete --all`, `aws s3 rm --recursive`, `terraform destroy`, `docker system prune --volumes`. |
| `priv_esc`               | `warn`                           | Privilege escalation or capability elevation. `sudo`, `doas`, `setuid`, `chmod +s`, container-escape constructs. |
| `secret_read`            | `warn`                           | Operations whose primary purpose is reading credential or secret material. `cat .env`, `printenv` of secret-shaped vars, `aws secretsmanager get-secret-value`, `kubectl get secret -o yaml`. |

### Sentinel separation

`novel` is the **risk_class sentinel** — applied to uncurated registry entries pending Phase 4a backfill. `unknown` is reserved for the **Effect first-encounter sentinel** — applied to invocations of binaries the install-time scan hasn't generated a ToolSpec for. The two sentinels are distinct vocabularies (risk_class vs. effects) and the verdict engine routes them through different paths (`novel` → registry-layer `ask` baseline; `unknown` → first-encounter background-async path that bypasses the rule-matcher entirely).

### Combo derivation

A `[[combo]]`'s `risk_class` is the most-dangerous of (a) the base `[[command]]`'s `risk_class`, and (b) any `[[flag]]`-supplied `risk_class_override`. Lint recomputes and errors on mismatch — same pattern as v0's combo-tag-derivation rule (TD-M15), narrowed to a single field. Danger ordering:

```
safe < net_egress = novel < destructive = priv_esc = secret_read
```

`net_egress` and `novel` are both `ask`-baseline; ties between them resolve to whichever the curator wrote (no implicit promotion). The three `warn`-baseline classes are equally severe and ties resolve the same way.

### Multi-flag override resolution

When multiple flags on the same invocation carry `risk_class_override` of equal danger tier, the resolved class is **the tier value itself**, not the flag identity. Ordering of flags on the command line and ordering of flag declarations in the TOML file are both irrelevant — the resolver computes `max-danger(base.risk_class, ∪ active_flags.risk_class_override)` deterministically. Example: an invocation with both `--force` (override = `destructive`) and `--no-preserve-root` (override = `destructive`) resolves to `risk_class = destructive`, regardless of which flag appeared first.

### Combo + extra-flag composition

A `[[combo]]`'s stored `risk_class` is a **lower bound**, not a ceiling. When a combo matches an invocation and the invocation also carries flags with `risk_class_override` that are *not* part of the combo's flag set, the resolved class is `max-danger(combo.risk_class, ∪ extra_flag_overrides.risk_class_override)`. Lint validates the combo's stored class against base + combo-flag overrides only; the runtime resolver layers any additional overriding flags on top. (Worked example: §5 Example 5.)

### `[[flag]]` modifiers

A `[[flag]]` may carry `risk_class_override` to elevate the base command's risk_class when this flag is present. Example:

```toml
[[command]]
path = "rm"
risk_class = "safe"
# rm of a single file is allow-base (Trash on macOS makes it trivially recoverable)

[[flag]]
applies_to = "rm"
flag = "-r"
risk_class_override = "destructive"
# -r elevates to destructive (recursive removal)
```

Combos preempt this: `[[combo]] path = "rm -r"` carries its own `risk_class = "destructive"` directly, hand-verified.

---

## 4. ToolSpec extensions to TOML

See TOOLSPEC.md §4 for the full carrier. Summary of the new required and optional fields on `[[command]]`, `[[flag]]`, `[[combo]]`:

### `[[command]]`

| Field                | Required (v2) | Description |
|----------------------|---------------|-------------|
| `path`               | yes (v0)      | Unchanged. |
| `translation`        | yes (v0)      | Unchanged. |
| `verdict`            | yes (v0)      | Now `allow|ask|warn`; `require_approval` accepted as alias. |
| `rationale`          | yes (v0)      | Unchanged. |
| `risk_class`         | **yes (v2)**  | One of `safe | net_egress | novel | destructive | priv_esc | secret_read`. |
| `version_constraint` | no (default `"*"`) | Per TOOLSPEC.md §4. |
| `description`        | no            | Per TOOLSPEC.md; surfaced to translator. |
| `positionals`        | no            | Array of inline tables; per TOOLSPEC.md §4. |
| `effects_default`    | no            | Curators **do not set this**; it's auto-populated by the engine annotator. Documented for completeness — should not appear in TOMLs Phase 4a writes. |
| `tags.*`             | **REMOVED**   | All five v0 tag axes drop. Migration tool replaces with `risk_class`. |

### `[[flag]]`

| Field                  | Required (v2) | Description |
|------------------------|---------------|-------------|
| `applies_to`           | yes (v0)      | Unchanged. |
| `flag`                 | yes (v0)      | Unchanged — canonical name. |
| `translation_modifier` | yes (v0)      | Unchanged. |
| `verdict`              | yes (v0)      | Now `allow|ask|warn`. |
| `rationale`            | yes (v0)      | Unchanged. |
| `arity`                | **yes (v2)**  | `Boolean | Single | KeyValue | Repeated`. Migration tool defaults to `Boolean` for any flag whose v0 entry lacks the field; auto-derive corrects in Phase 4a. |
| `value_type`           | yes (v2) when `arity ≠ Boolean` | `String | Path | Url | Int | Enum(...)`. |
| `short`, `long`        | no            | Per TOOLSPEC.md; resolver derives if absent. |
| `bundled_short_ok`     | no (default `true` if `short` is single char) | Per TOOLSPEC.md. |
| `default_present`      | no (default `false`) | Per TOOLSPEC.md. |
| `effect_modifiers`     | no            | Per TOOLSPEC.md §3; effect names drawn from EFFECTS.md §1's six-effect vocabulary (`reads`, `writes`, `deletes`, `network`, `exec`, `env`). The `unknown` sentinel never appears in author-supplied modifiers — it's an annotator-only routing marker for binaries lacking a ToolSpec. |
| `taint_introducing`    | no (default `false`) | Per TOOLSPEC.md §1. |
| `risk_class_override`  | no            | Elevates the base `risk_class` when this flag is present. |
| `tag_modifiers.*`      | **REMOVED**   | All five v0 tag-modifier axes drop. Migration replaces with `risk_class_override` where appropriate. |

### `[[combo]]`

| Field         | Required (v2) | Description |
|---------------|---------------|-------------|
| `path`        | yes (v0)      | Unchanged — flags sorted alphabetically per v0 rule. |
| `translation` | yes (v0)      | Unchanged. |
| `verdict`     | yes (v0)      | Now `allow|ask|warn`. |
| `rationale`   | yes (v0)      | Unchanged. |
| `risk_class`  | **yes (v2)**  | Computed from base + flag overrides; lint recomputes and errors on mismatch. |
| `tags.*`      | **REMOVED**   | Per `[[command]]`. |

---

## 5. Layered composition + resolution algorithm

Five layers. Stacked, with the most-recent-applied at the top:

```
user-override        (~/.intracept/policy.yaml, the user's per-rule overrides)
agent-authored       (rules an agent has written explicitly into the policy via tool-use)
profile-default      (rules generated by the 5q profile flow at intracept init)
org-default          (rules pulled from the user's org policy.yml, if joined)
registry-default     (the registry's curated default per-tool rules)
```

### Resolution algorithm

For each invocation (a `ParsedInvocation` with effects + risk_class + ToolSpec context), the engine collects every rule that matches and resolves down to one verdict via:

1. **Most-specific match wins.** Specificity = count of constraints satisfied. A rule that matches on `(tool=rm, flags.contains=-r, effects.contains=deletes)` has specificity 3; a rule that matches on `(tool=rm)` has specificity 1; the higher-specificity rule wins outright.

2. **On equal specificity, layer priority wins.** Order, highest to lowest:
   ```
   user-override > agent-authored > profile-default > org-default > registry-default
   ```
   A user-override match always beats an org-default match of equal specificity.

3. **On equal specificity AND equal layer, most-restrictive wins.** Order:
   ```
   warn > ask > allow
   ```
   This case applies when two **independent** rules at the same layer happen to both match a given invocation through different match paths (e.g., R1 matches on `flags.contains=-r`, R2 matches on `effects.contains=deletes`, both at the registry layer, both specificity 2). They are not in textual conflict but they overlap on this invocation; the verdict engine picks the more restrictive of the two.

4. **Same-layer textual conflicts refuse-to-load at policy-load time.** Two rules at the same layer with **identical matchers** and **different verdicts** are not resolved at runtime — the policy loader rejects them at load. The error message surfaces both conflicting rule IDs and source files. This rule fires at every layer; "registry-default conflicts with itself" is just as fatal as "user-override conflicts with itself." Silently picking one rule over another at the same layer is a footgun regardless of which layer it happens at.

### Worked examples

**Example 1: most-specific wins.**
- Registry-default rule R1: `tool=rm → ask`. Specificity 1.
- Registry-default rule R2: `tool=rm AND flags.contains=-rf → warn`. Specificity 2.
- Invocation `rm -rf foo/`: R2 wins. Verdict: `warn`.

**Example 2: layer priority on tie.**
- Registry-default R3: `tool=git AND subcommand_chain=[push] AND flags.contains=--force → warn`. Specificity 3.
- User-override R4: `tool=git AND subcommand_chain=[push] AND flags.contains=--force → allow`. Specificity 3.
- Invocation `git push --force`: equal specificity (3); user-override wins. Verdict: `allow`.

**Example 3: most-restrictive on equal-specificity-equal-layer.**
- Registry-default R5: `tool=rm AND flags.contains=-r → warn`. Specificity 2.
- Registry-default R6: `tool=rm AND effects.contains=deletes → ask`. Specificity 2.
- Invocation `rm -r foo/`: both match, both specificity 2, both registry-default layer. Most-restrictive wins. Verdict: `warn`.

**Example 4: same-layer conflict refuse-to-load.**
- Registry-default R7: `tool=docker AND subcommand_chain=[stop] → ask`.
- Registry-default R8: `tool=docker AND subcommand_chain=[stop] → allow`.
- Identical matchers, different verdicts, same layer. Policy-load fails with `same-layer conflict at registry-default: R7 and R8 disagree on (tool=docker, subcommand_chain=[stop])`. The engine refuses to start until the conflict is resolved.

**Example 5: combo + extra overriding flag (composition rule).**
- Registry-default R9 (combo): `tool=git AND flags={push, --force} → risk_class=destructive`. The combo's `risk_class` is stored as `destructive` because base `git push` is `safe` and `--force` overrides to `destructive`.
- Registry-default R10 (flag): `--no-verify` carries `risk_class_override = destructive` (signed-commit bypass).
- Invocation `git push --force --no-verify origin main`: the combo R9 matches (covering the `--force` override), and the flag R10 also matches (`--no-verify`). The resolver computes `max-danger(R9.risk_class, R10.risk_class_override) = max(destructive, destructive) = destructive`. Verdict: `warn` (per the destructive → warn baseline). Lint validated R9's stored value against base + combo-flag overrides; the extra `--no-verify` is layered at runtime by the resolver, not by lint.

### 5.1 Permissive overrides — load-time warning

When a user-override or org-default rule produces a *less-restrictive* verdict than a registry-default rule it shadows at equal specificity, the policy loader emits a structured `permissive_override` warning (not an error) listing the shadowed rule, the overriding rule, and both verdicts. The override still wins per layer-priority — this is by design (the user is in charge of their own machine) — but the warning surfaces the safety-rail downgrade so it isn't silent.

```
permissive_override at user-override: rule "user-allow-force-push" downgrades
  registry-default "registry-warn-force-push" from `warn` to `allow`
  (matched: tool=git, subcommand_chain=[push], flags.contains=--force)
```

The warning is structured so Phase 4b's prompt UX can surface a one-time confirmation at first invocation of any command that hits a permissive-override path: "you've configured this command to skip the safety prompt; confirm once." After confirmation, future invocations run at the configured verdict silently. Lint emits the warning at policy-load time; the engine carries the list of permissive overrides through to the prompt UX layer for the first-invocation surfacing.

This rule applies whenever `verdict_priority(override) < verdict_priority(shadowed_registry_rule)` per the most-restrictive ordering `warn > ask > allow`. Equal-priority overrides do not warn (the user explicitly matched the registry posture). More-restrictive overrides do not warn (tightening is always safe).

---

## 6. v0 → v2 migration

The migration tool (planned for Phase 4a; scaffolded in `engine/v0_to_v2.py`) is mechanical, idempotent, and reversible.

### Per-file migration rules

For each `tools/<name>.toml`:

1. **Verdicts.** `verdict = "require_approval"` → `verdict = "ask"` (textual rewrite). `verdict = "allow"` unchanged. Other values rejected.

2. **Multi-axis tags → risk_class.** For each `[[command]]` and `[[combo]]`:
   - If the v0 entry has no `tags.*` block: `risk_class = "novel"` (sentinel; Phase 4a auto-derive replaces).
   - If the v0 entry has tags: derive `risk_class` per the table below. Migration tool surfaces "novel" for any entry whose tags don't unambiguously map.

   | v0 tag pattern | Derived `risk_class` |
   |----------------|----------------------|
   | `tags.effect contains "delete" AND tags.reversibility="impossible"` | `destructive` |
   | `tags.effect contains "delete" AND tags.reversibility="difficult"` | `destructive` |
   | `tags.target contains "credentials"` | `secret_read` |
   | `tags.target contains "network" AND tags.scope="remote"` | `net_egress` |
   | `tags.safety_override = true` (and not destructive/secret_read) | `priv_esc` |
   | `tags.effect = ["read"] AND tags.scope="local"` | `safe` |
   | (no unambiguous match) | `novel` |

3. **Tag-modifiers on flags → risk_class_override.** Same derivation table applied to `tag_modifiers.*`. If no override is materially different from the base command's risk_class, drop the field entirely.

4. **ToolSpec fields.** v0 TOMLs lack `arity`, `value_type`, `positionals`, `effect_modifiers`, etc. Migration:
   - `arity` defaults to `Boolean` for every existing flag.
   - `value_type` defaults to `String` if the auto-derive heuristic flags the flag as taking a value (presence of `=`, `<value>`, etc. in the `--help` output).
   - `positionals` is left empty; Phase 4a hand-curate or auto-derive supplies.
   - `effect_modifiers`, `taint_introducing` left absent; Phase 4a supplies.

5. **v0 backup.** The migration tool writes `tools/<name>.toml.v0.bak` before rewriting. `--force` re-derives v2 from the `.v0.bak`.

6. **Idempotency.** Running migration on an already-v2 file logs `already migrated` and exits 0. Detection is by the presence of `risk_class` on every `[[command]]` and absence of `tags.*` blocks.

### Cross-cutting observations

- **The 1198 untagged TOMLs all migrate to `risk_class = "novel"` plus `arity = "Boolean"` / `value_type = "String"` defaults on their flags.** This is intentional sentinel-fill; Phase 4a top-50 hand-curates the 50 highest-frequency tools and the auto-derive pipeline backfills the remainder. Lint enforces `risk_class` presence on every `[[command]]` and `[[combo]]` (ERROR severity); a `risk_class = "novel"` entry is *valid* but flagged in CI dashboards as "needs Phase 4a curation."

- **No data is lost in the v0→v2 migration that the auto-derive can't recover.** v0 `tags.effect` values aren't preserved on the TOML side because effects are now engine-derived, but the engine annotator re-derives them at every parse from the AST + ToolSpec. The tag axes that *don't* survive (`tags.scope`, `tags.target`, etc.) collapse into `risk_class` per the table above; the curated examples that informed the original tag values inform the derived risk_class.

---

## 7. Validation rules (lint changes)

Lint runs in **transitional mode through Phase 4a** (during which the v0→v2 migration tool runs across the 1244 TOMLs) and **locked mode after Phase 4a**. The two modes share the same rule set; the only difference is the severity assigned to v0 patterns.

### Transitional mode (Phase 1 → Phase 4a)

Lint accepts v0 inputs without breaking CI; v0 patterns are WARN-level so the migration window doesn't go red. Strict v2 inputs pass clean.

1. `verdict` must be one of `{allow, ask, warn, require_approval}`. `require_approval` is the v0 alias for `ask`; transitional WARN ("v0 verdict; will be migrated to `ask`"). Other values → ERROR.
2. `risk_class` is optional on `[[command]]` and `[[combo]]` in transitional mode. Missing → WARN ("v0 entry without risk_class; will be set to `novel` by v0→v2 migration unless tags map unambiguously"). Present with invalid value → ERROR.
3. `risk_class` value (when present) must be one of `{safe, net_egress, novel, destructive, priv_esc, secret_read}`. Unknown → ERROR.
4. `[[flag]].risk_class_override` (when present) must use the same enum. Unknown → ERROR.
5. `[[combo]].risk_class` (when present, alongside its base `[[command]].risk_class`) must be ≥ the most-dangerous of the base + any flag overrides. Mismatch → ERROR.
6. Multi-axis tag fields (`tags.scope`, `tags.effect`, `tags.reversibility`, `tags.target`, `tags.safety_override`) — present → WARN ("v0 axis; will be removed by v0→v2 migration"). Same applies to `tag_modifiers.*` on flags.
7. `[[flag]].arity` is optional in transitional mode. Missing → WARN; present with invalid value → ERROR.
8. `[[flag]].value_type` is optional in transitional mode. Missing when `arity ≠ Boolean` → WARN; present with invalid value → ERROR.
9. `effects_default` and `effect_modifiers` (if present) — TOML authors should not write these; if present they must use only effect names drawn from EFFECTS.md §1. Curators are reminded these are auto-populated by the engine annotator (per §1 of this doc and TOOLSPEC.md §3). WARN ("effects should be auto-populated; remove from TOML unless intentional").

### Locked mode (post-Phase 4a)

Each WARN above becomes ERROR after the migration tool runs across all TOMLs. Mode flip is one constant in `tools/lint.py` (`STRICT_V2 = True`); Phase 4a's PR ships the flip alongside the migration commit. No code structure change between modes.

Existing v0 lint rules — translation period, capital letter, modifier grammar, rationale length, combo path-must-start-with-command, etc. — carry forward unchanged in both modes.

---

## 8. Outstanding open questions

The following questions surfaced during Phase 1 drafting and remain open for HITL pending resolution:

1. **Q5 — Severity-field shape on `Rule` (when verdict=warn).** B is scaffolding the snapshot; spelling and value set follow B's lock. SCHEMA-v2.md will reference whatever B settles on.
2. **Q6 — `default_present` flag pairs (`--quiet` vs `--no-quiet`).** Surface to HITL in TOOLSPEC.md context. Lean: model both, mark one with `default_present=true`. Not a blocker for Phase 1 freeze; can land in Phase 4a refinement.
3. **Q7 — Variadic positional taint semantics.** Surface to HITL in TOOLSPEC.md context. Lean: variadic = "apply effects per element"; `taint_introducing=true` means "any element introduces taint." Not a blocker for Phase 1 freeze.

None of Q5–Q7 block downstream streams from cutting their branches against the frozen JSON-schema snapshot.

---

## 9. Frozen snapshot reference

The JSON-schema snapshot every downstream stream imports is at:
- `intracept/fixtures/schema/rule-schema-v2.json` — the rule schema (matchers + verdict + severity + risk_class).
- `intracept/fixtures/schema/toolspec.json` — the ToolSpec shape.
- `intracept/fixtures/schema/effects.json` — the typed-effects vocabulary; the locked categories live in EFFECTS.md §1, kept in lockstep with this snapshot.

These are derived by `schemars` from `intracept-shared::schema` (B's authoring). Drift between TOML lint and these snapshots fails CI via the diff-CI assertion (C's runner).

---

## 10. Migration timeline reference

- **Phase 1 (this phase):** SCHEMA-v2.md locked; lint updated to enforce the new rules; v0→v2 migration tool scaffolded. No TOMLs are migrated yet.
- **Phase 4a:** `engine/v0_to_v2.py` runs across the 1244 TOMLs. The 50 hand-curated tools land with real `risk_class` values; the rest land with `risk_class = "novel"` and Phase 4a auto-derive backfills.
- **Phase 4b:** Verdict engine refactor consumes the new schema end-to-end; v0 deserialization aliases (`require_approval` → `ask`) remain available for v0/v1 `policy.yaml` compatibility.
- **Post-sprint:** Aliases retire when the v0/v1 user base is fully migrated; tracked in §8 of the launch-sprint roadmap.
