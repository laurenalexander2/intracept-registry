# EFFECTS.md — typed-effects vocabulary

**Status:** Phase 1 schema-lock — aligned with B's frozen JSON-schema snapshot at `intracept/fixtures/schema/effects.json` (2026-05-09). Repos: `[both]` (`[intracept]` defines the Rust types via `intracept-shared::schema`; `[intracept-registry]` carries the source-of-truth doc).

**Audience:** stream leads (Phase 2 Stream C, Phase 3 Stream F), TOML curators (Phase 4a top-50), auto-derive pipeline (Phase 4a).

This document defines the typed-effects vocabulary the engine assigns to a `ParsedInvocation` (post-parser, post-argspec, pre-verdict). Effects are **auto-populated by the engine annotator from the AST + ToolSpec — curators never set them by hand.** They are the input to the verdict engine (Phase 4b) and to the rule-schema effect-matcher; they replace pattern-match-on-text in the verdict hot path.

> **Scope boundary.** Effects are properties of an *invocation*, not of a *tool* in the abstract. `git push` has effect `network` because of what *this command does at this site*; `git --version` does not, despite both being `git`. The annotator runs after the parser + argspec, so it has the typed flag set, positional arguments, and shell-AST context to reason against.

---

## 1. The vocabulary

**Six first-class effect categories plus an `unknown` sentinel.** Every annotated invocation carries a (possibly empty) set drawn from this enum. Wire format is **snake_case** (matches B's frozen JSON-schema snapshot at `intracept/fixtures/schema/effects.json`; snake_case wins because Rust/serde/schemars output it natively and the snapshot is source of truth).

| Effect      | What it means | Inclusive examples | Exclusive examples |
|-------------|---------------|---------------------|---------------------|
| `reads`     | `open(O_RDONLY)` and equivalent path reads. Includes reads of the environment table (`printenv`, `env`) and process state (`ps`, `top`). | `cat foo`, `ls`, `grep`, `printenv`, `ps`, `git log`, `cat .env`. | Reading a memoized cache the tool just wrote (does not double-count). |
| `writes`    | `open(O_WRONLY|O_CREAT)`, `rename`, mode/owner changes; non-deletion writes. **Includes creation** (no separate `creates` category). | `git commit`, `mkdir`, `cp src dst`, `tee out`, `echo > f`, `chmod 644 f`. | Writes to `/dev/null`, `/dev/stdout`, `/dev/stderr`, ephemeral pipes. |
| `deletes`   | `unlink`, `rmdir`, recursive deletion; irreversible state change on the FS. **Separate from `writes`** because the verdict posture diverges (destructive → `warn` baseline; creating/modifying → typically `allow` or `ask`). | `rm`, `rm -rf`, `git branch -D`, `kubectl delete`, `aws s3 rm`. | Implicit overwrite as a side-effect of `writes` (`cp src existing-dst` is `writes`, not `deletes`, even though it overwrites). |
| `network`   | `socket` + `connect`; outbound or inbound network I/O. **Single category — not split into egress/listen.** Direction (in/out) and host-allowlist concerns are rule-matcher axes, not effect categories. | `curl`, `wget`, `git push`, `git clone <url>`, `nc host port`, `nc -l 4444`, `ssh user@host`. | `curl 127.0.0.1`, `nc -l 127.0.0.1` (loopback-only is filtered by the address argument, not the binary). |
| `exec`      | `execve`; the child may have arbitrary further effects. The annotator treats `exec` as a taint sink — anything piped in or referenced as `$(...)` that becomes argv is flagged. | `bash -c "$x"`, `sh -c "$(curl ...)"`, `eval`, `xargs`, `find -exec`, `npm run`. | Statically-known `exec` (`node script.js` where `script.js` is a literal path) — annotated as `exec` but with a `static_argv` taint flag for the verdict engine to treat differently from tainted `exec`. |
| `env`       | `setenv` / `unsetenv` and shell-level environment changes that persist past the immediate command. **Reads of the env table fold into `reads`** — only *mutations* are categorized here (the `env` effect is the mutation axis; the read axis is `reads`). | `export FOO=bar`, `unset FOO`, `set -a`, `env -i …` (when invoking a child with a stripped env). | `printenv` (read-only — folds to `reads`). `cat .env` (FS read of a credential file — folds to `reads`; the credential-sensitivity is captured by the curator's `risk_class=secret_read`, not by the effect). |

These six are the entire effect enum members. `unknown` is the seventh value present in the schema, but as a sentinel — see "Unknown sentinel" below — not as a co-equal effect category.

### AST features (NOT effect categories)

`process-substitution`, `redirection`, and `heredoc` are **AST detection inputs**, not effect enum members. They are how shell-AST features compose into the six effects above (e.g., `cmd > file` *contributes* a synthetic `writes(file)` to the host invocation; `<(cmd)` *contributes* a synthetic `reads(/dev/fd/N)` plus a taint edge). They are documented in §3 below as composition rules. Earlier drafts of this document listed them in the table above as first-class effects; that was incorrect. The annotator detects them in the AST and folds their consequences into the six-effect enum at annotation time.

**Empty-set is meaningful.** `git --version`, `--help`, `man <x>` annotate to `{}` (no effects). The verdict engine treats `{}` as `allow`-default in the registry layer (per §3 base-verdict posture: read-only / idempotent → `allow`; expressed via `risk_class=safe`).

### Unknown sentinel — distinct from `RiskClass::novel`

A novel binary that the install-time scan hasn't generated a `ToolSpec` for produces effects = `{unknown}`. The verdict engine routes `{unknown}` to the first-encounter background-async path (first invocation = `ask`, spec fills for #2), per the coverage SLA. `unknown` is an annotator-internal sentinel — it bypasses the rule-matcher entirely; the matched verdict is set at the engine layer, not at the rule layer.

> **`Effect::unknown` vs `RiskClass::novel` — different vocabularies, different sentinels, different routing.** `Effect::unknown` is a *runtime/engine* fact: the engine annotator hit an OS-primitive (or a binary) it can't classify because no ToolSpec exists for it; routing goes to the first-encounter background-async path that bypasses the rule-matcher. `RiskClass::novel` is a *curation* fact: the curator hasn't yet assigned a `risk_class` to a registry entry; routing goes through the registry layer with `ask`-baseline and Phase 4a auto-derive replaces it with a real classification. The two sentinels live on different fields (`effects` vs `risk_class`) and never substitute for each other.

---

## 2. Auto-population — curators don't set effects

Effects are derived by the engine annotator from:

1. The parsed AST (parser daemon, `mvdan/sh`).
2. The ToolSpec for the resolved binary + subcommand chain (per TOOLSPEC.md §1).
3. AST shell-construct features (redirection, heredoc, process-substitution) read straight from the AST.

Curators author the ToolSpec — typed flags, typed positionals, per-flag/per-positional `effect_modifiers` — and the curator-set `risk_class` enum. They never set the *invocation's* effects directly; that's the annotator's output.

This is the orchestrator-locked design (2026-05-09): one curator-set field (`risk_class`) drives verdict; one engine-set field (`effects`) drives the rule-matcher's effect axis. Two-field composition, no overlap.

---

## 3. AST features — taint edges and composition rules

Taint flows along data-flow edges in the shell AST. The annotator emits both the *effect set* per invocation **and** the *taint graph* across an invocation chain. The four AST features in this section (`process-substitution`, `redirection`, `heredoc`, and pipeline) are **composition rules, not effect categories**: each is detected in the AST and contributes synthetic entries (or modifications) to the six-effect set on the participating invocations.

### 3.1 Pipeline (`A | B`)

- `A`'s `writes` (to stdout) becomes `B`'s `reads` (from stdin) with a taint edge `A → B`.
- If `B` has `exec` and consumes stdin as argv (e.g., `xargs`, `bash`), the chain receives a `tainted_exec` flag. Verdict-engine treatment is `warn` baseline regardless of either side's individual posture — this is the canonical `curl … | sh` shape.
- `set -o pipefail` does not change effects; it changes exit-code semantics, which the parser daemon tracks separately.

> **Note.** None of pipeline, redirection, heredoc, or process-substitution is an enum member of the effects vocabulary. Pipeline produces taint edges and never a synthetic effect of its own; redirection / heredoc / process-substitution produce taint edges *and* contribute synthetic entries from the six-effect enum (e.g., a synthetic `writes(file)` on `cmd > file`) to the host invocation's effect set.

### 3.2 Subshell substitution (`$(cmd)`, backticks)

- `cmd`'s `writes` (to stdout) becomes a string interpolated into the parent invocation's argv.
- If the parent invocation is `exec`-classed and the substituted string lands in the executed argv, that's `tainted_exec`.
- If the parent is a `writes` and the substitution lands in a path component, that's `tainted_path` (e.g., `rm -rf $(pwd)/build` — `pwd` is read-only but the *target* of `rm` is taint-derived).

### 3.3 Heredoc (`<<EOF … EOF`)

- The consuming command gets a synthetic `reads` (from stdin) with payload type `literal_heredoc`. Heredoc presence is recorded on the AST node (`ast.has_heredoc=true`) for rule-matcher access; it is not an effect enum member.
- If the heredoc is `<<EOF` (variable-expanding, the default), every `$VAR` reference adds a `reads` of the env table to the consuming invocation; if it's `<<'EOF'` or `<<\EOF` (quoted, no expansion), the payload is a static literal and no synthetic env reads are added.
- `<<<` here-strings are annotated identically with `payload_type=here_string`.

### 3.4 Process substitution (`<(cmd)`, `>(cmd)`)

- The outer command's argv contains `/dev/fd/N`; the inner `cmd` runs concurrently. Process-substitution presence is recorded on the AST node (`ast.has_process_substitution=true`); it is not an effect enum member.
- Inner `cmd` is annotated as a standalone invocation; outer command additionally gets a synthetic `reads(/dev/fd/N)` for `<(cmd)` or `writes(/dev/fd/N)` for `>(cmd)`, plus a taint edge to the inner.
- Composition: the outer's effect set is the union of its own effects, the synthetic FD read/write, and (transitively) the inner's effects.

### 3.5 Redirection (`>`, `>>`, `<`, `2>&1`, `&>`)

- Redirection presence is recorded on the AST node (`ast.has_redirection=true`); it is not an effect enum member.
- `cmd > file` adds `writes(file)` to `cmd`'s effect set with merge-rule **union**.
- `cmd >> file` adds `writes(file)` (the append-vs-truncate distinction is tracked as a flag on the writes annotation, not its own effect).
- `cmd < file` adds `reads(file)`.
- `cmd 2>&1` is bookkeeping; no synthetic write.
- `cmd > /dev/null` records the AST redirection but the synthetic `writes` is filtered (ephemeral target).
- `cmd > /dev/tty` or `> /dev/stdout` are ephemeral; same filter.

### 3.6 Compound contexts (`&&`, `||`, `;`)

- Each invocation is annotated independently; the rule schema's `compound_context` matcher inspects the chain.
- Effects do not fold across `&&`/`||`/`;`; a rule that wants to match "any compound chain that contains a `deletes`" uses `compound_context.contains(effect=deletes)`.

---

## 4. Per-flag and per-positional effect annotation (in ToolSpec)

Effects are not only per-invocation; they're per-`ToolSpec`-element. The argspec annotator can attribute an effect to a specific flag or positional, which lets the rule schema match flag-specific or argument-specific effects.

```
git commit -m "msg"   →  effects = {writes}        (positional msg, no taint)
git commit --amend    →  effects = {writes, deletes} (amend rewrites the prior commit)
git commit -S         →  effects = {writes, reads} (-S reads gpg keyring)
```

The rule schema's `flags[].effect` axis matches per-flag effects; the `positional[].effect` axis matches per-positional effects. The engine-side `ParsedInvocation` carries both an aggregated `effects` set (union over all elements) and the per-element annotation. Per-element `effect_modifiers` are declared in TOOLSPEC.md.

---

## 5. Relationship to TOML (registry side)

The orchestrator's 2026-05-09 directive collapses the registry's multi-axis tags into a single curator-set `risk_class` enum. **TOML carries `risk_class`; TOML does not carry effects.** Effects are derived at engine load-time from the AST + ToolSpec by the annotator (Phase 3 Stream F), not from TOML metadata.

Consequence: the v0 `tags.effect` axis on `[[command]]`/`[[combo]]` entries is **dropped** in v2. Migration:

- The ~46 already-tagged TOMLs lose `tags.effect` (and `tags.scope`, `tags.reversibility`, `tags.target`, `tags.safety_override`); their existing tag values are folded into a single `risk_class` value during the v0→v2 migration pass (e.g., `tags.effect=["delete"] + tags.reversibility="impossible"` → `risk_class=destructive`).
- The ~1198 untagged TOMLs default to `risk_class=unknown` until Phase 4a auto-derive backfills.

See SCHEMA-v2.md §migration for the full v0→v2 derivation rules.

---

## 6. Validation rules (test category 5 — Effect annotator coverage)

The effect-annotator test corpus must cover each of the six effect categories on at least one representative invocation, plus each AST-feature composition rule in §3 (pipeline, redirection, heredoc, process-substitution) on at least one fixture, plus the `unknown` sentinel routing path on at least one fixture. The OOD `compgen -c | shuf | head -50` mini-set must produce a non-empty effect set on ≥ 90% of invocations (the residual is novel binaries that legitimately route through first-encounter via `unknown`; that's expected, not a failure).

The gate is: every effect category is exercised; every taint-edge composition in §3 is exercised; the `unknown` sentinel path is exercised; the per-flag and per-positional attribution paths are both exercised. Coverage of less than this fails Phase 3's stream-F gate and refuses to advance to Phase 4b.

---

## 7. Resolved questions

The earlier draft of this document carried four open questions (Q1–Q4). All four are resolved by the orchestrator's 2026-05-09 directive and B's frozen schema snapshot at `intracept/fixtures/schema/effects.json`:

- **Q1 — Network split.** Resolved: single `network` category. Direction and host-allowlist concerns are rule-matcher axes, not effect categories. The `risk_class=net_egress` curator field captures the egress-default posture; if a "service binds a listener" risk class is later needed, it is added as a new `risk_class` value at that time, not now.
- **Q2 — Coverage gate vocabulary.** Resolved: AST features are **not** first-class effects — they are AST detection inputs (composition rules) that contribute synthetic entries from the six-effect enum to the host invocation's effect set. The shadow-mode coverage gate counts the same six categories the rule-matcher matches on, plus exercises each AST-feature composition path in §3 (pipeline, redirection, heredoc, process-substitution) and the `unknown` sentinel path. The locked vocab is `{reads, writes, deletes, network, exec, env}` plus the `unknown` sentinel — six effects + sentinel; AST features stay separate.
- **Q3 — TOML `tags.effect` alignment.** Resolved: TOML does not carry effects. Multi-axis tags drop entirely; `risk_class` is the single curator-set field. Auto-population at engine load-time is the only path from a TOML to an effect set. (The vocab-count question is moot here because the TOML side carries no effect enum at all; the count question only applies to engine-side annotations and the JSON-schema snapshot.)
- **Q4 — `exec` taint granularity.** Resolved: three taint shapes (`static_argv`, `tainted_argv`, `dynamic_argv`) are sufficient. The `network → tainted_exec` shape is composable from the `network` effect plus the `tainted_argv` taint flag; the verdict engine composes the warn from those two facts independently, no fourth primitive needed.
