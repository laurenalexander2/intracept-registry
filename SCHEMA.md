# SCHEMA.md — intracept-registry TOML format

This document is the **source of truth** for the TOML schema used in all `tools/*.toml` files.

## File naming

- One file per CLI tool: `tools/<toolname>.toml`
- Use the base tool name (e.g., `git.toml`, `docker.toml`, `aws.toml`)

---

## Entry types

### `[[command]]` — a command or subcommand

| Field         | Type   | Required | Description |
|---------------|--------|----------|-------------|
| `path`        | string | yes      | Full command path including subcommands, no flags. Examples: `"git push"`, `"aws s3 cp"`, `"docker container ls"`. |
| `translation` | string | yes      | One sentence, plain English, describing what the bare command does. No jargon. Must be a complete, standalone sentence ending with a period. |
| `verdict`     | string | yes      | One of: `allow`, `require_approval`. |
| `rationale`   | string | yes      | One sentence explaining why this verdict was chosen. |

### `[[flag]]` — a flag on a specific command

| Field                  | Type   | Required | Description |
|------------------------|--------|----------|-------------|
| `applies_to`           | string | yes      | Must exactly match a `path` value from a `[[command]]` entry in the same file. No global/standalone flags. |
| `flag`                 | string | yes      | The literal flag including dashes. Examples: `"--force"`, `"-rf"`, `"--recursive"`, `"-v"`. |
| `translation_modifier` | string | yes      | A gerund or prepositional phrase that grammatically attaches to the base command's `translation`. See [Composition rule](#composition-rule) below. Set to `""` if the flag causes no meaningful change to the translation. |
| `verdict`              | string | yes      | One of: `allow`, `require_approval`. This is the **flag's own verdict**, independent of the base command. |
| `rationale`            | string | yes      | One sentence justifying this flag's verdict. |
| `tag_modifiers.*`      | varies | no       | Only the tag dimensions this flag changes relative to the base command. See [Tag modifiers on flags](#tag-modifiers-on-flags). |

### `[[combo]]` — a pre-composed command + flags combination

A combo entry captures a specific command-plus-flags invocation whose combined behavior is worth describing as a unit. Combos provide **premium translations** that are more accurate than mechanical composition from individual flag modifiers.

| Field         | Type     | Required | Description |
|---------------|----------|----------|-------------|
| `path`        | string   | yes      | Command + flags, with flags sorted alphabetically. Example: `"git push --force"`, `"rm -rf"`. |
| `translation` | string   | yes      | One sentence, plain English, describing what this specific combination does. Standalone sentence ending with a period. Max 300 characters. |
| `verdict`     | string   | yes      | One of: `allow`, `require_approval`. |
| `rationale`   | string   | yes      | One sentence explaining the consequence of the combination, not the individual flags. |
| `tags.*`      | varies   | yes      | Full tags computed from base command tags + flag tag_modifiers, hand-verified. See [Tags](#tags). |

#### Combo rules

- `path` contains the command followed by flags, with **flags sorted alphabetically**. Example: `"docker system prune --all --volumes"`, not `"docker system prune --volumes --all"`.
- `translation` is a standalone sentence (same style as `[[command]]`), but with a **max of 300 characters** (vs 200 for commands) to accommodate the richer behavior.
- `verdict` follows the same grading guidelines as commands and flags.
- `rationale` describes the **consequence of the combination**, not the individual pieces. "Rewrites the remote branch's commit history, which can permanently discard other contributors' work." not "Uses --force which is dangerous."
- Every combo `path` must **start with a valid `[[command]]` path** from the same file.
- Every flag in the combo `path` must **match a `[[flag]]` entry** in the same file.
- Combos carry **full `tags.*`** (not `tag_modifiers`), computed from the base command's tags with all flag modifiers applied and hand-verified.

---

## Tags

Tags provide **categorical metadata** on each entry, enabling deterministic policy decisions (e.g., "block if `scope == remote` and `delete` in `effect`") without parsing free-text translations.

### Tags on `[[command]]` entries

Every `[[command]]` entry carries these dotted-key tags:

| Tag                    | Type     | Values | Description |
|------------------------|----------|--------|-------------|
| `tags.scope`           | string   | `"local"`, `"remote"` | Whether the command's effects stay on the local machine or reach a remote system. |
| `tags.effect`          | string[] | `"read"`, `"write"`, `"create"`, `"delete"`, `"execute"` | What the command does. A command can have multiple effects. |
| `tags.reversibility`   | string   | `"trivial"`, `"difficult"`, `"impossible"` | How hard it is to undo the command's effects. |
| `tags.target`          | string[] | `"filesystem"`, `"repository"`, `"container"`, `"cluster"`, `"cloud"`, `"package_registry"`, `"database"`, `"credentials"`, `"network"`, `"process"`, `"config"` | What the command acts on. A command can have multiple targets. |
| `tags.safety_override` | boolean  | `true`, `false` | Whether the command bypasses a safety mechanism (e.g., confirmation prompts, hooks, guardrails). |

Example on a `[[command]]`:

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

### Tag modifiers on `[[flag]]` entries

Flags do NOT carry full tags. Instead, they carry **`tag_modifiers.*`** — only the dimensions that the flag **changes** relative to the base command.

| Modifier                         | Type     | Description |
|----------------------------------|----------|-------------|
| `tag_modifiers.scope`            | string   | Overrides the base command's scope. |
| `tag_modifiers.effect`           | string[] | Replaces the base command's effect list entirely. |
| `tag_modifiers.reversibility`    | string   | Overrides the base command's reversibility. |
| `tag_modifiers.target`           | string[] | Replaces the base command's target list entirely. |
| `tag_modifiers.safety_override`  | boolean  | Overrides the base command's safety_override. |

Only include dimensions the flag actually changes. Most flags modify one or two dimensions.

Example on a `[[flag]]`:

```toml
[[flag]]
applies_to = "git push"
flag = "--force"
translation_modifier = "overwriting remote history"
verdict = "require_approval"
rationale = "Overwrites remote branch history; recoverable via reflog if someone acts quickly, but other contributors' work may be lost."
tag_modifiers.reversibility = "impossible"
tag_modifiers.safety_override = true
```

### Tags on `[[combo]]` entries

Combos carry **full `tags.*`** (same schema as `[[command]]`), computed from the base command's tags with all flag `tag_modifiers` applied and then hand-verified.

Example on a `[[combo]]`:

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

### Tag merge semantics

When computing a combo's tags from the base command's tags plus one or more flag `tag_modifiers`:

| Dimension type | Merge rule | Example |
|----------------|-----------|---------|
| **String** (`scope`, `reversibility`) | Flag **replaces** the base value. | Base `"difficult"` + flag `"impossible"` → `"impossible"` |
| **Array** (`effect`, `target`) | Flag **replaces** the base array entirely. | Base `["write"]` + flag `["write", "delete"]` → `["write", "delete"]` |
| **Boolean** (`safety_override`) | **OR** — once `true`, stays `true`. | Base `false` + flag `true` → `true` |
| **Multiple flags** | Apply all flag modifiers. For string fields, take the **most dangerous** value per dimension. For arrays, union all values. For booleans, OR. | `"difficult"` + flag₁ `"impossible"` + flag₂ `"difficult"` → `"impossible"` |

Danger ordering for string fields:
- `scope`: `local` < `remote`
- `reversibility`: `trivial` < `difficult` < `impossible`

---

## SDK lookup order

When an SDK needs to look up the translation and tags for a command invocation (e.g., `git push --force --no-verify`), it follows this order:

1. **Exact combo match.** Look for a `[[combo]]` whose `path` matches the command + sorted flags exactly. If found, use its `translation`, `verdict`, and `tags`.

2. **Subset combo match.** Find the longest `[[combo]]` whose flags are a subset of the invocation's flags. Apply the remaining flags' `tag_modifiers` on top. Compose the remaining flags' `translation_modifier` phrases onto the combo's `translation`.

3. **Mechanical composition.** No combo matched. Start from the `[[command]]` entry. For each flag, apply its `tag_modifiers` (using merge semantics above) and compose its `translation_modifier` onto the base `translation`. Compute the final verdict as the max of the command's verdict and all flags' verdicts.

SDKs should **log fallback hits** (steps 2 and 3) so that frequently-seen combinations can be promoted to pre-composed `[[combo]]` entries via the backfill loop.

---

## Verdict levels

The verdict answers one question: **should this command run automatically, or pause for user confirmation?**

| Level              | When to use |
|--------------------|-------------|
| `allow`            | Command runs automatically. Use for read-only operations, local dev workflow, trivially reversible actions. |
| `require_approval` | Command pauses for user confirmation. Use for destructive operations, remote/shared state mutations, credential access, data exfiltration vectors, privilege escalation. |

### Grading guidelines

- **The flag's verdict is independent of the base command's verdict.** A `--dry-run` flag is `allow` even on a `require_approval` command. A `--force` flag may be `require_approval` even on an `allow` command.
- **Take the max.** If either the command or any flag is `require_approval`, the overall verdict is `require_approval`.
- **Rate the flag's own contribution, not the combination.** If `rm` is `allow` and `-rf` is `require_approval`, that's because `-rf` is what introduces the danger — the bare command only deletes a single named file.
- **A required flag does not change the verdict by itself.** If a flag is required for the command to function at all (e.g., `git clean -f`), it is part of the baseline — rate it at the same level as the command itself.
- **Don't rate by worst-case misuse.** `curl` could pipe to `sh`, but the bare command just transfers data. Rate what the command *does*, not what a creative attacker could chain it into.
- **When in doubt, use `require_approval`.** It is safer to pause for confirmation than to allow a destructive command to run automatically.

### Calibration examples

These are fixed reference points. Use them to anchor your verdicts:

| Entry | Verdict | Why |
|-------|---------|-----|
| `ls` | `allow` | Read-only directory listing. |
| `git commit` | `allow` | Local-only, trivially amendable or resetable. |
| `git push` (to a branch) | `require_approval` | Publishes commits to a shared remote; can disrupt collaborators. |
| `docker stop` | `require_approval` | Interrupts a running service. |
| `rm` (single file) | `allow` | Deletes one named file. Trivially reversible from Trash on macOS. |
| `rm -r` | `require_approval` | Deletes a directory tree. Recovery requires backups. |
| `rm -rf` | `require_approval` | Recursive deletion, no prompts, no safeguard. |
| `git push --force` | `require_approval` | Overwrites remote branch history; other contributors' work may be lost. |
| `git push --mirror` | `require_approval` | Makes remote an exact copy of local, deleting all non-matching refs. |
| `terraform apply -auto-approve` | `require_approval` | Modifies live cloud infrastructure with no confirmation prompt. |
| `terraform destroy -auto-approve` | `require_approval` | Destroys all managed infrastructure with no prompt. |
| `aws rds delete-db-instance --skip-final-snapshot` | `require_approval` | Irrecoverable production data loss. |
| `aws s3 rm --recursive` | `require_approval` | Wipes all objects under a prefix. |
| `kubectl delete --all` | `require_approval` | Deletes all resources of a type in a namespace. |
| `docker system prune` | `require_approval` | Bulk-deletes unused resources. |
| `docker system prune --volumes` | `require_approval` | Extends prune to volumes — persistent data is destroyed. |
| `--dry-run` (any command) | `allow` | Simulates without acting. |
| `--no-verify` (any command) | `require_approval` | Bypasses safety hooks; disables a guardrail. |

---

## Composition rule

The translation system works by composing a command's `translation` with a flag's `translation_modifier`:

> **Base:** `translation` (complete sentence)
> **With flag:** `translation`, **`translation_modifier`**.

### How `translation_modifier` works

The modifier is a **gerund phrase** (starting with a verb in -ing form) or a **prepositional phrase** that grammatically continues the base sentence. It is NOT a standalone sentence.

**Good modifiers:**
- `"overwriting remote history"` — gerund phrase
- `"without asking for confirmation"` — prepositional phrase
- `"including untracked files"` — gerund phrase
- `"limited to the first 10 results"` — participial phrase
- `"recursively through all subdirectories"` — adverbial phrase

**Bad modifiers (do NOT use):**
- `"This overwrites remote history."` — standalone sentence
- `"Overwrites remote history"` — imperative/verb phrase without gerund
- `"--force flag"` — flag name, not a description
- `"dangerous"` — adjective, not a phrase

### Composition examples

| Command | Flag | Composed result |
|---------|------|----------------|
| `git push` → "Upload local commits to a remote repository." | `--force` → `"overwriting remote history"` | "Upload local commits to a remote repository, **overwriting remote history**." |
| `rm` → "Delete files." | `-r` → `"recursively through all subdirectories"` | "Delete files, **recursively through all subdirectories**." |
| `docker ps` → "List running containers." | `-a` → `"including stopped containers"` | "List running containers, **including stopped containers**." |
| `git log` → "Show the commit history." | `--oneline` → `""` | "Show the commit history." (no change — formatting-only flag) |

### When to use an empty modifier

Set `translation_modifier = ""` when a flag:
- Only changes output formatting (e.g., `--json`, `--oneline`, `--color`)
- Has no user-facing behavioral change worth describing
- Is purely cosmetic or default-equivalent

---

## Complete example file

```toml
# tools/git.toml

[[command]]
path = "git"
translation = "Run the Git version control system."
verdict = "allow"
rationale = "The bare command prints help text and modifies nothing."
tags.scope = "local"
tags.effect = ["read"]
tags.reversibility = "trivial"
tags.target = ["repository"]
tags.safety_override = false

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

[[flag]]
applies_to = "git push"
flag = "--force"
translation_modifier = "overwriting remote history"
verdict = "require_approval"
rationale = "Overwrites remote branch history; recoverable via reflog if someone acts quickly, but other contributors' work may be lost."
tag_modifiers.reversibility = "impossible"
tag_modifiers.safety_override = true

[[flag]]
applies_to = "git push"
flag = "--force-with-lease"
translation_modifier = "overwriting remote history only if no one else has pushed"
verdict = "require_approval"
rationale = "Safer than --force but still rewrites history; fails if the remote has diverged."
tag_modifiers.reversibility = "impossible"

[[flag]]
applies_to = "git push"
flag = "--dry-run"
translation_modifier = "simulating the push without actually sending data"
verdict = "allow"
rationale = "No data is transmitted; only shows what would happen."
tag_modifiers.effect = ["read"]
tag_modifiers.reversibility = "trivial"

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

[[command]]
path = "git reset"
translation = "Move the current branch pointer to a different commit."
verdict = "require_approval"
rationale = "Changes which commit HEAD points to; can unstage changes or rewrite local history."
tags.scope = "local"
tags.effect = ["write"]
tags.reversibility = "difficult"
tags.target = ["repository"]
tags.safety_override = false

[[flag]]
applies_to = "git reset"
flag = "--hard"
translation_modifier = "discarding all uncommitted changes in the working directory"
verdict = "require_approval"
rationale = "Permanently deletes uncommitted work with no built-in recovery mechanism."
tag_modifiers.reversibility = "impossible"
tag_modifiers.effect = ["write", "delete"]
```

---

## Style guide

### Base translations (`translation` field)

- **One sentence, plain English, present tense.** A junior engineer who has never used the tool should understand it.
- **Describe what the command does, not what it is.** Write "Delete files." not "A file deletion utility."
- **End with a period.** Always.
- **No jargon.** "Upload local commits to a remote repository." not "Push refs to a remote."
- **For bare tool commands**, use the pattern: "[Verb] [what it manages/does]." Examples:
  - `git` → "Run the Git version control system."
  - `docker` → "Run the Docker container management tool."
  - `kubectl` → "Run the Kubernetes command-line tool."
  - `npm` → "Run the Node.js package manager."
  - The pattern is: "Run the [full name] [category word: system/tool/manager/interface]."
- **For subcommand-only parents** (e.g., `aws s3`, `terraform state`): "Manage [what]." or the bare subcommand's help text behavior: "The bare subcommand prints help text."
- **For leaf commands**: describe the action, not the mechanism. "Delete one or more running containers." not "Send SIGKILL to container processes."
- **Don't hedge.** "Delete files." not "Can be used to delete files."

### Translation modifiers (`translation_modifier` field)

- **Gerund phrase** ("overwriting remote history"), **prepositional phrase** ("without asking for confirmation"), or **participial phrase** ("limited to a specific resource").
- **Must compose grammatically** when appended with a comma: "[translation], [modifier]." Read it out loud. If it's a run-on, add a comma-separated clause or restructure.
- **Don't restate the base translation.** The modifier adds what changes, not what stays the same.
- **For scope-widening flags** (`--all`, `--recursive`, `-A`): use "including" or "across" patterns. "including all modified, deleted, and new files" / "across every namespace in the cluster."
- **For safety-bypass flags** (`--force`, `--no-verify`): use "without" or "skipping" patterns. "without asking for confirmation" / "skipping pre-commit hook checks."
- **For mode-changing flags** (`--dry-run`, `-d`): use "simulating" or "in" patterns. "simulating the operation without actually deleting anything" / "in the background."
- **For verdict-reducing flags** (`--dry-run`, `-i`, `--interactive`): the modifier should make clear nothing destructive happens. "simulating the operation without actually [verb]ing anything" / "prompting for confirmation before each [noun]."
- **Empty string** (`""`) for flags that don't meaningfully change the translation (output formatting, cosmetic).

### Rationales (`rationale` field)

- **One sentence.** No more.
- **Explain the consequence, not the mechanism.** "Permanently deletes uncommitted work with no recovery mechanism." not "Calls reset with the hard flag which modifies the working tree."
- **No theatrical language.** "Removes all data from the table irreversibly." not "Could be exploited by hackers to destroy the company."
- **Be specific.** "Permanently removes the remote branch, which may disrupt other contributors' workflows." not "This is dangerous."
- **For `allow` verdict**: explain why it's safe. "Read-only operation that modifies nothing." / "Creates a local commit that can be amended or reset."
- **For `require_approval` verdict**: explain the danger. "Permanently deletes uncommitted work with no recovery mechanism." / "Publishes to a shared remote, potentially disrupting collaborators."

---

## Validation rules

### All entries

1. `verdict` must be one of: `allow`, `require_approval`.
2. `translation` must end with a period.
3. No duplicate `path` values within a file (across `[[command]]` and `[[combo]]` entries).

### `[[command]]` entries

4. `path` must not contain flags (no dashes unless part of the command name itself, e.g., `docker-compose`).
5. All `tags.*` fields are required: `scope`, `effect`, `reversibility`, `target`, `safety_override`.
6. Tag values must use only the allowed values listed in [Tags](#tags).

### `[[flag]]` entries

7. Every `[[flag]].applies_to` must match exactly one `[[command]].path` in the same file.
8. No duplicate `(applies_to, flag)` pairs within a file.
9. `translation_modifier` must NOT end with a period (it gets appended to the translation).
10. `translation_modifier` must be a gerund/prepositional/participial phrase, not a standalone sentence.
11. `tag_modifiers.*` may only use the same keys and value types as `tags.*`.
12. `tag_modifiers.*` should only include dimensions the flag actually changes.

### `[[combo]]` entries

13. Every combo `path` must start with a valid `[[command]].path` from the same file.
14. Every flag in the combo `path` must match a `[[flag]]` entry for that command in the same file.
15. Flags in the combo `path` must be sorted alphabetically.
16. `translation` max length is 300 characters.
17. All `tags.*` fields are required (same as `[[command]]`).
18. Combo `tags.*` must be consistent with the base command's tags + flag `tag_modifiers` (using [tag merge semantics](#tag-merge-semantics)).
