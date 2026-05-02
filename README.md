# intracept-registry

Plain-English translations of 2,400 CLI commands and 3,738 flag combinations, each tagged with structured metadata for deterministic safety policies.

This is a **data repo** — no code to run, just structured TOML files that any SDK, agent framework, or policy engine can consume.

## What it looks like

A CLI agent is about to run `git push --force`. What does that actually do?

**Before** (raw command):
```
git push --force
```

**After** (registry lookup):
```
Translation:  "Force-upload local commits to a remote repository,
               overwriting its history even if other contributors
               have pushed since."
Verdict:       require_approval
Scope:         remote
Reversibility: impossible
Safety override: true
```

The agent pauses, shows the translation, and waits for confirmation.

## How translations work

The registry uses **two layers** to translate any command invocation:

1. **Pre-composed combos** (premium). Hand-written `[[combo]]` entries for common dangerous combinations like `git push --force` or `rm -rf`. These provide the most accurate, purpose-written translations.

2. **Mechanical composition** (fallback). If no combo exists, the SDK builds a translation by appending each flag's `translation_modifier` to the base command's `translation`:

   > `git push` → "Upload local commits to a remote repository."
   > `git push --force` → "Upload local commits to a remote repository, **overwriting remote history**."

Fallback hits are logged so frequently-seen combinations can be promoted to pre-composed combos.

## Tags for permissions

Every entry carries structured tags that enable **deterministic policy rules** — no LLM, no fuzzy matching:

```toml
tags.scope = "remote"            # local | remote
tags.effect = ["write"]          # read, write, create, delete, execute
tags.reversibility = "impossible" # trivial | difficult | impossible
tags.target = ["repository"]     # filesystem, repository, container, ...
tags.safety_override = true      # bypasses a safety mechanism?
```

Example policy rule:

```
BLOCK IF scope == "remote" AND "delete" IN effect
BLOCK IF reversibility == "impossible" AND safety_override == true
ALLOW IF scope == "local" AND effect == ["read"]
```

No translation parsing needed — tags give you machine-readable dimensions for any policy granularity.

## TOML schema quick reference

Each `tools/*.toml` file contains three entry types. See [SCHEMA.md](SCHEMA.md) for the full specification.

### `[[command]]` — a command or subcommand

```toml
[[command]]
path = "git push"
translation = "Upload local commits to a remote repository."
verdict = "require_approval"
rationale = "Publishes local changes to a shared remote; incorrect pushes can disrupt collaborators."
tags.scope = "remote"
tags.effect = ["write"]
tags.reversibility = "difficult"
tags.target = ["repository"]
tags.safety_override = false
```

### `[[flag]]` — a flag on a specific command

```toml
[[flag]]
applies_to = "git push"
flag = "--force"
translation_modifier = "overwriting remote history"
verdict = "require_approval"
rationale = "Overwrites remote branch history; other contributors' work may be lost."
tag_modifiers.reversibility = "impossible"
tag_modifiers.safety_override = true
```

Flags carry `tag_modifiers` — only the dimensions they change relative to the base command.

### `[[combo]]` — a pre-composed command + flags combination

```toml
[[combo]]
path = "git push --force"
translation = "Force-upload local commits to a remote repository, overwriting its history even if other contributors have pushed since."
verdict = "require_approval"
rationale = "Rewrites the remote branch's commit history, which can permanently discard other contributors' work."
tags.scope = "remote"
tags.effect = ["write"]
tags.reversibility = "impossible"
tags.target = ["repository"]
tags.safety_override = true
```

Combos carry full `tags` (computed from base + flag modifiers, hand-verified).

## Verdict levels

| Level              | Meaning                                                        |
|--------------------|----------------------------------------------------------------|
| `allow`            | Runs automatically — read-only, local, or trivially reversible |
| `require_approval` | Pauses for confirmation — destructive, remote, or sensitive    |

The final verdict is always the **max** of the command's verdict and all flags' verdicts.

## Self-improving registry

The registry grows through a **backfill loop**:

1. An SDK encounters a command + flags combination with no `[[combo]]` entry.
2. It falls back to mechanical composition and **logs the miss**.
3. A generation agent reviews logged misses, drafts a `[[combo]]` entry with a hand-verified translation and tags.
4. The combo is submitted as a PR to this registry.
5. Once merged, all SDKs get the premium translation on next sync.

Over time, the most common dangerous combinations get pre-composed entries, and the fallback path handles the long tail.

## Structure

```
tools/
  git.toml          # one file per CLI tool
  docker.toml
  aws.toml
  ...
SCHEMA.md           # full format specification
```

## Using the registry

- Parse the TOML files with any TOML library
- Look up commands using the [SDK lookup order](SCHEMA.md#sdk-lookup-order): exact combo match → subset combo → mechanical composition
- Use `tags.*` for deterministic policy decisions
- Use `translation` for human-readable explanations
- Filter by `verdict` to surface commands that require approval

## Contributing

1. Read [SCHEMA.md](SCHEMA.md) for the full format specification
2. One TOML file per tool, named `tools/<toolname>.toml`
3. Every `[[flag]]` must reference an existing `[[command]]` path via `applies_to`
4. Every `[[combo]]` must reference valid `[[command]]` and `[[flag]]` entries
5. Translations must be plain English — no jargon, no technical abbreviations
6. All entries must include `tags` (commands, combos) or `tag_modifiers` (flags)
7. Combo flags must be sorted alphabetically in the `path`
8. Verdict rationale must justify the specific level chosen
