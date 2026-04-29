# intracept-registry

A human-readable registry of CLI commands, flags, and their verdicts. Each tool gets a TOML file describing what its commands do in plain English, whether each flag requires approval, and why.

This is a **data repo** — no code to run, just structured TOML files that other tools can consume.

## Structure

```
tools/
  git.toml          # one file per CLI tool
  docker.toml
  aws.toml
  ...
exemplars/          # gold-standard reference files for quality checks
progress.json       # generation tracking (overall)
progress-B.json     # session B progress
progress-C.json     # session C progress
```

## TOML Schema (quick reference)

Each `.toml` file in `tools/` contains `[[command]]` and `[[flag]]` entries. See [SCHEMA.md](SCHEMA.md) for the full specification.

```toml
[[command]]
path = "git push"
translation = "Upload local commits to a remote repository."
verdict = "require_approval"
rationale = "Publishes local changes to a shared remote; incorrect pushes can disrupt collaborators."

[[flag]]
applies_to = "git push"
flag = "--force"
translation_modifier = "overwriting remote history"
verdict = "require_approval"
rationale = "Rewrites remote branch history, potentially destroying other contributors' work."
```

### Verdict levels

| Level              | Meaning                                                        |
|--------------------|----------------------------------------------------------------|
| `allow`            | Runs automatically — read-only, local, or trivially reversible |
| `require_approval` | Pauses for confirmation — destructive, remote, or sensitive    |

## How translations compose

The base command's `translation` is a complete sentence. A flag's `translation_modifier` is a gerund or prepositional phrase that attaches to the base:

> **git push** → "Upload local commits to a remote repository."
> **git push --force** → "Upload local commits to a remote repository, **overwriting remote history**."

## Using the registry

- Parse the TOML files with any TOML library
- Filter by verdict to surface commands that require approval
- Compose `translation` + `translation_modifier` for human-readable explanations

## Resuming generation

If generation is interrupted, check `progress.json` (and per-session files `progress-B.json`, `progress-C.json`). Each tracks which tools have been completed, skipped, or are in progress. Resume by picking up tools marked `in_progress` or `remaining`.

```json
{
  "schema_version": 1,
  "tools": {
    "git": { "status": "done", "commands": 12, "flags": 34 },
    "docker": { "status": "in_progress", "commands": 5, "flags": 0 }
  },
  "stats": { "done": 1, "skipped": 0, "in_progress": 1, "remaining": 248 }
}
```

## Contributing

1. Read [SCHEMA.md](SCHEMA.md) for the full format specification
2. One TOML file per tool, named `tools/<toolname>.toml`
3. Every `[[flag]]` must reference an existing `[[command]]` path via `applies_to`
4. Translations must be plain English — no jargon, no technical abbreviations
5. Verdict rationale must justify the specific level chosen
