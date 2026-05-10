# diff-matchers — TD-H1 cross-impl drift guardrail

This directory is the Phase 2 Stream E deliverable for **TD-H1: matcher
consolidation**, shipped as a *diff-CI fallback* (Path 2 from the brief). The
brief's Path 1 (one canonical tokenizer + lookup that all callers depend on) is
captured as a Phase 7 backlog item. Path 2 lands first because the three
impls have genuinely divergent public APIs and a clean cross-repo cargo cutover
is multi-PR risky during foundation phase. The diff-CI guardrail makes the
silent drift visible *now* and validates Path 1 work later.

## What it does

Three matcher implementations exist today:

- `intracept-registry/sdk/rust/src/matcher.rs` — SDK consumer surface
- `intracept/crates/patterns/src/matcher.rs` — runtime engine matcher
- `intracept/crates/translator/src/parser.rs` — translator pipeline parser

For every entry in [`corpus.jsonl`](corpus.jsonl) the harness records each
impl's tokenization, shell-split, and matched command path, writes a
deterministic JSONL row to [`cross-snapshot.jsonl`](cross-snapshot.jsonl), and
fails on byte mismatch. Behavior changes — even ones that *fix* a divergence —
require an explicit snapshot refresh, which surfaces the change in code review.

A separate, lighter SDK-only test ([`../../sdk/rust/tests/diff_matchers.rs`])
runs the SDK side against [`sdk-snapshot.jsonl`](sdk-snapshot.jsonl). This
catches drift in the SDK alone (e.g. when working in this repo without the
intracept sibling clone available).

## Corpus shape

115 rows across five buckets — the four TD-H1 divergence surfaces called out in
roadmap §3.5 plus a sanity bucket of regression cases:

| bucket | count | purpose |
|---|---|---|
| `sanity` | 25 | bare commands, chains, redirects, pipelines — must stay agreeing |
| `env-var-prefix` | 22 | `FOO=bar git push` and friends — TD-H1 surface |
| `shell-keyword` | 20 | leading `do`/`done`/`for`/`while`/etc — TD-H1 surface |
| `command-flag` | 28 | `--command='…'`, `bash -c "…"`, `$(...)` — TD-H1 surface |
| `heredoc` | 20 | `<<EOF`, `<<-EOF`, `<<<word`, here-strings — TD-H1 surface |

Per-row schema:

```jsonl
{"id": "envvar-001", "command": "FOO=bar git push", "bucket": "env-var-prefix", "note": "..."}
```

## Snapshot shape

Per-row produced output:

```jsonl
{
  "id": "envvar-001",
  "sdk":        {"tokens": [...], "splits": [...], "match_path": null},
  "patterns":   {"tokens": [...], "splits": [...], "match_path": "git push"},
  "translator": {"tokens": [...], "splits": [...], "match_path": null},
  "tokens_agree_sdk_patterns": true,
  "splits_agree": true,
  "match_agree_sdk_patterns": false
}
```

The `*_agree_*` booleans are recorded so reviewers can scan for new
disagreements at a glance. The cross-impl harness does **not** fail on
disagreement by default — it fails on snapshot mismatch. Pass `--strict` to fail
on any cross-impl disagreement (intended for the Phase 7 cutover when Path 1
ships and we expect zero day-1 disagreements).

`tokens_agree` is restricted to `sdk` vs `patterns` because the translator uses
`shell_words::split` which legitimately tokenizes quoted strings differently
(`--command='rm -rf'` becomes a single token). Translator tokens are still
recorded in the snapshot so changes are visible.

## Day-1 known divergence (frozen in snapshot)

Of 115 corpus rows, **46 currently disagree across at least one of
{tokens, splits, match_path}**. These are the TD-H1 silent-drift surfaces:

- `env-var-prefix`: patterns/matcher.rs strips `FOO=bar` prefixes (calls
  `is_leading_noise`). SDK and translator pass them through, producing
  `match_path: null` where patterns produces `match_path: "git push"`.
- `shell-keyword`: patterns/matcher.rs skips leading `do`/`done`/`for`/etc.
  Same impact as env-var prefix.
- `command-flag`: patterns/matcher.rs walks into `$(...)`, `--command='…'`,
  and `bash -c "…"` via `collect_nested_commands` and max-verdicts the inner
  command. SDK and translator do not. *(Visible as different translation
  text via per-impl Translation, but `match_path` only differs when the inner
  command has a higher verdict — this corpus emphasizes input shape, not
  verdict.)*
- `heredoc`: byte-level tokenizers (SDK + patterns) treat heredoc body as
  trailing token text. translator's shell-words drops it. None of the three
  understand heredoc as syntax.

Capturing these divergences in the snapshot is the point — they're the bugs
TD-H1 named. Future fixes will refresh the snapshot, which makes the fix
explicit in code review.

## Running

### Cross-impl harness (all three impls — needs both repos cloned as siblings)

```sh
# from intracept-registry root
cargo run --manifest-path tests/diff-matchers/harness/Cargo.toml -- \
  --corpus tests/diff-matchers/corpus.jsonl \
  --snapshot tests/diff-matchers/cross-snapshot.jsonl
```

Refresh the snapshot when behavior changes intentionally:

```sh
cargo run --manifest-path tests/diff-matchers/harness/Cargo.toml -- \
  --corpus tests/diff-matchers/corpus.jsonl \
  --snapshot tests/diff-matchers/cross-snapshot.jsonl --update
```

### SDK-only guardrail (this repo standalone)

```sh
cargo test -p intracept-registry --test diff_matchers
UPDATE_SNAPSHOTS=1 cargo test -p intracept-registry --test diff_matchers  # refresh
```

## CI wiring

Both repos run the cross-impl harness on every PR:

- **intracept-registry**: `.github/workflows/diff-matchers.yml` checks out the
  intracept sibling and runs the harness.
- **intracept**: `.github/workflows/ci.yml` adds a `diff-matchers` job that
  checks out intracept-registry and runs the harness.

A snapshot mismatch fails the PR. The reviewer either approves the snapshot
update (intentional change) or rejects it (regression).

## Crate layout note

The harness is a **standalone** Cargo project (its own `[workspace]` block)
rather than a member of either repo's workspace. This is deliberate: a
path-dep into a sibling repo (`../../../../intracept`) would break
`cargo build --workspace` for anyone who hasn't cloned both repos side-by-side.
The standalone harness only runs when explicitly invoked, and CI handles the
sibling-checkout step.
