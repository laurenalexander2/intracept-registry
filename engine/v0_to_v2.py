#!/usr/bin/env python3
"""v0 → v2 migration tool for intracept-registry tools/*.toml files.

Mechanical, idempotent, reversible per SCHEMA-v2.md §6:

  - verdict "require_approval" → "ask" (textual rewrite).
  - multi-axis tags (tags.scope/effect/reversibility/target/safety_override)
    collapse into a single risk_class per the §6.2 derivation table.
  - tag_modifiers.* on flags collapse into risk_class_override (dropped when
    not materially different from the base command's risk_class).
  - ToolSpec defaults: arity = "Boolean" on every flag that lacks one.
  - <name>.toml.v0.bak written before any rewrite.
  - --force re-derives v2 from <name>.toml.v0.bak (escape hatch when a
    manual edit has gone wrong; falls back to the original v0 source).
  - Idempotent: re-running on a v2 file logs "already migrated" exit 0.
  - Type-mismatch errors (e.g. tags.effect set to a non-list) fall back to
    risk_class = "novel" with a structured error and the tool exits 1 if
    any file failed.

Phase 2 ships scaffold + dry-run + tests. The actual TOML rewrite runs
in Phase 4a per the SCHEMA-v2.md §10 timeline. Phase 2 callers must pass
--dry-run to avoid unintended writes.

Usage:
    python3 engine/v0_to_v2.py [--dry-run] [--force] [--quiet] [paths...]

Default paths: tools/.
Exit codes:
    0 — every input migrated cleanly (or already v2, or dry-run with no failures).
    1 — at least one input had a structured derivation error.
    2 — invocation error (missing path, --force without backup, malformed CLI).
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── Locked vocabulary (mirrors SCHEMA-v2.md §3) ────────────────────────────

VALID_RISK_CLASSES = frozenset({
    "safe", "net_egress", "novel", "destructive", "priv_esc", "secret_read",
})

# Most-dangerous-wins ordering for combo override resolution. Matches
# tools/lint.py's RISK_CLASS_RANK so derivation and lint agree byte-for-byte.
RISK_CLASS_RANK: dict[str, int] = {
    "safe": 0,
    "net_egress": 1,
    "novel": 1,
    "destructive": 2,
    "priv_esc": 2,
    "secret_read": 2,
}

V0_TAG_DIMENSIONS = frozenset({
    "scope", "effect", "reversibility", "target", "safety_override",
})

# Sentinel to mark a derivation that failed type-mismatch validation.
# Migration still emits risk_class = "novel" for the entry but the file is
# flagged in the result so the caller can exit 1.
NOVEL = "novel"


# ── Result types ───────────────────────────────────────────────────────────

@dataclass
class FileResult:
    path: Path
    status: str  # "migrated" | "already-migrated" | "would-migrate" | "would-skip" | "error"
    errors: list[str] = field(default_factory=list)
    derivation_errors: list[str] = field(default_factory=list)
    dry_run: bool = False
    backup_written: bool = False
    output: str | None = None  # populated in dry-run for inspection / round-trip tests


# ── Public API ─────────────────────────────────────────────────────────────

def migrate_file(
    src_path: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> FileResult:
    """Migrate one TOML file. Returns a FileResult; never raises for shape
    errors (those land in result.errors / result.derivation_errors).

    See module docstring for behavior contract."""
    bak_path = src_path.with_name(src_path.name + ".v0.bak")

    if force:
        if not bak_path.exists():
            return FileResult(
                src_path,
                status="error",
                errors=[f"--force requires {bak_path.name} to exist"],
                dry_run=dry_run,
            )
        source_text = bak_path.read_text(encoding="utf-8")
    else:
        if not src_path.exists():
            return FileResult(
                src_path,
                status="error",
                errors=[f"source file not found: {src_path}"],
                dry_run=dry_run,
            )
        source_text = src_path.read_text(encoding="utf-8")

    try:
        parsed = tomllib.loads(source_text)
    except tomllib.TOMLDecodeError as e:
        return FileResult(
            src_path,
            status="error",
            errors=[f"TOML parse error: {e}"],
            dry_run=dry_run,
        )

    if not force and is_already_v2(parsed):
        return FileResult(src_path, status="already-migrated", dry_run=dry_run)

    cmd_risk, cmd_errs = _derive_command_risks(parsed.get("command", []))
    flag_overrides, flag_errs = _derive_flag_overrides(parsed.get("flag", []), cmd_risk)
    combo_risk, combo_errs = _derive_combo_risks(parsed.get("combo", []), cmd_risk, flag_overrides)

    new_text = _rewrite_source(source_text, cmd_risk, flag_overrides, combo_risk)
    derivation_errors = cmd_errs + flag_errs + combo_errs

    if dry_run:
        return FileResult(
            src_path,
            status="would-migrate",
            derivation_errors=derivation_errors,
            dry_run=True,
            output=new_text,
        )

    # Write backup if not present (and not --force; in --force the backup
    # already exists, otherwise we'd have errored out above).
    backup_written = False
    if not bak_path.exists():
        bak_path.write_bytes(source_text.encode("utf-8"))
        backup_written = True

    src_path.write_text(new_text, encoding="utf-8")

    return FileResult(
        src_path,
        status="migrated",
        derivation_errors=derivation_errors,
        backup_written=backup_written,
        output=new_text,
    )


def is_already_v2(parsed: dict) -> bool:
    """A file is v2 iff every [[command]] (and [[combo]]) has risk_class AND
    no entry carries any tags.* or tag_modifiers.* axes."""
    commands = parsed.get("command", [])
    combos = parsed.get("combo", [])
    flags = parsed.get("flag", [])

    if not commands and not combos and not flags:
        # Empty file or non-tool file: trivially "already migrated".
        return True

    for cmd in commands:
        if "risk_class" not in cmd:
            return False
        if "tags" in cmd:
            return False
    for combo in combos:
        if "risk_class" not in combo:
            return False
        if "tags" in combo:
            return False
    for flg in flags:
        if "tag_modifiers" in flg:
            return False

    return True


# ── Derivation table (SCHEMA-v2.md §6.2) ───────────────────────────────────

def derive_risk_class(
    entry: dict,
    *,
    tag_key: str = "tags",
) -> tuple[str, str | None]:
    """Compute the risk_class for one entry's tag block. Returns
    (risk_class, optional_error_message). Type-mismatch on a tag axis
    surfaces as an error string and falls back to "novel"."""
    tags = entry.get(tag_key)
    if tags is None:
        return NOVEL, None

    if not isinstance(tags, dict):
        return NOVEL, f"{tag_key} is not a table (got {type(tags).__name__})"

    err: str | None = None

    scope, e1 = _typed(tags, "scope", str)
    effect, e2 = _typed(tags, "effect", list)
    reversibility, e3 = _typed(tags, "reversibility", str)
    target, e4 = _typed(tags, "target", list)
    safety_override, e5 = _typed(tags, "safety_override", bool)
    type_errs = [e for e in (e1, e2, e3, e4, e5) if e]
    if type_errs:
        err = "; ".join(f"{tag_key}.{e}" for e in type_errs)

    effect = effect or []
    target = target or []

    # Rules in SCHEMA-v2.md §6.2 order. First match wins.
    if "delete" in effect and reversibility == "impossible":
        return "destructive", err
    if "delete" in effect and reversibility == "difficult":
        return "destructive", err
    if "credentials" in target:
        return "secret_read", err
    if "network" in target and scope == "remote":
        return "net_egress", err
    if safety_override is True:
        # priv_esc qualifier: not destructive/secret_read (already handled
        # above by precedence). Nothing to check here — falling through
        # means we passed all earlier rules.
        return "priv_esc", err
    if effect == ["read"] and scope == "local":
        return "safe", err

    return NOVEL, err


def _typed(tags: dict, key: str, expected_type: type) -> tuple[Any, str | None]:
    """Return (value, error). value is None if the key is absent or its
    type is wrong; in the wrong-type case error is a structured message."""
    if key not in tags:
        return None, None
    val = tags[key]
    if not isinstance(val, expected_type):
        # bool is a subclass of int in Python; tomllib never produces bool
        # for an int-typed value, but be defensive.
        if expected_type is bool and isinstance(val, bool):
            return val, None
        return None, f"{key} expected {expected_type.__name__}, got {type(val).__name__}"
    return val, None


def _derive_command_risks(commands: list[dict]) -> tuple[dict[str, str], list[str]]:
    risks: dict[str, str] = {}
    errors: list[str] = []
    for cmd in commands:
        path = cmd.get("path")
        if not path:
            continue
        rc, err = derive_risk_class(cmd, tag_key="tags")
        if rc not in VALID_RISK_CLASSES:
            errors.append(f"command {path!r}: derived invalid risk_class {rc!r} (defaulting to novel)")
            rc = NOVEL
        risks[path] = rc
        if err:
            errors.append(f"command {path!r}: {err}")
    return risks, errors


def _derive_flag_overrides(
    flags: list[dict],
    cmd_risk: dict[str, str],
) -> tuple[dict[tuple[str, str], str], list[str]]:
    """Compute per-flag risk_class_override. A flag carries an override
    only when the derived class differs from the base command's class
    (drop redundant fields per §6.1.3)."""
    overrides: dict[tuple[str, str], str] = {}
    errors: list[str] = []
    for flg in flags:
        applies_to = flg.get("applies_to")
        flag_name = flg.get("flag")
        if not applies_to or not flag_name:
            continue
        rc, err = derive_risk_class(flg, tag_key="tag_modifiers")
        if err:
            errors.append(f"flag {applies_to} {flag_name}: {err}")
        # NOVEL means "no tag_modifiers block or unmappable" — drop the
        # override entirely (the base command's risk_class governs).
        if rc == NOVEL:
            continue
        base = cmd_risk.get(applies_to, NOVEL)
        if rc != base:
            overrides[(applies_to, flag_name)] = rc
    return overrides, errors


def _derive_combo_risks(
    combos: list[dict],
    cmd_risk: dict[str, str],
    flag_overrides: dict[tuple[str, str], str],
) -> tuple[dict[str, str], list[str]]:
    """Combo risk_class = max-danger(base.risk_class, ∪ active flag overrides).
    Falls back to the entry's own derived risk_class if the base lookup
    cannot resolve. Errors surface but do not abort."""
    risks: dict[str, str] = {}
    errors: list[str] = []
    for combo in combos:
        path = combo.get("path")
        if not path:
            continue
        own_rc, err = derive_risk_class(combo, tag_key="tags")
        if err:
            errors.append(f"combo {path!r}: {err}")

        base_path, flag_tokens = _split_combo_path(path, set(cmd_risk))
        base_rc = cmd_risk.get(base_path, NOVEL)
        active_overrides = [
            flag_overrides[(base_path, tok)]
            for tok in flag_tokens
            if (base_path, tok) in flag_overrides
        ]

        # When the curator hand-set tags on the combo, prefer the derived
        # value; otherwise compute from base + flag overrides per §3.
        derived = own_rc
        if derived == NOVEL:
            derived = _max_danger([base_rc, *active_overrides])
        risks[path] = derived

    return risks, errors


def _split_combo_path(combo_path: str, command_paths: set[str]) -> tuple[str, list[str]]:
    """Split a combo path into (base_command_path, [flag_tokens]). Mirrors
    tools/lint.py's longest-prefix base-command lookup."""
    base = ""
    for cp in command_paths:
        if combo_path == cp or combo_path.startswith(cp + " "):
            if len(cp) > len(base):
                base = cp
    if not base:
        return combo_path, []
    remainder = combo_path[len(base):].strip()
    tokens = [t for t in remainder.split() if t.startswith("-")]
    return base, tokens


def _max_danger(risks: list[str]) -> str:
    if not risks:
        return NOVEL
    best = risks[0]
    for r in risks[1:]:
        if RISK_CLASS_RANK.get(r, 0) > RISK_CLASS_RANK.get(best, 0):
            best = r
    return best


# ── Textual rewrite ────────────────────────────────────────────────────────

_SECTION_HEADERS = ("[[command]]", "[[flag]]", "[[combo]]")
_VERDICT_REQ_APPROVAL = re.compile(r'(\bverdict\s*=\s*)"require_approval"')
_TAG_LINE = re.compile(r"^\s*(?:tags|tag_modifiers)\.[a-z_]+\s*=")


def _rewrite_source(
    source: str,
    cmd_risk: dict[str, str],
    flag_overrides: dict[tuple[str, str], str],
    combo_risk: dict[str, str],
) -> str:
    """Walk source line-by-line. For each [[command]]/[[flag]]/[[combo]]
    block: drop tags/tag_modifiers lines, rewrite require_approval verdict,
    append v2 fields (risk_class / risk_class_override / arity) at the
    block's tail.

    Insertion point: at the end of the block (last non-blank line before
    the next section header or EOF), preserving any trailing blank lines."""
    lines = source.splitlines(keepends=True)
    out: list[str] = []

    section_kind: str | None = None
    section_payload: dict[str, Any] = {}
    section_lines: list[str] = []
    pending_after_section: list[str] = []  # blank/comment lines after a section that belong before the next

    def flush_section() -> None:
        nonlocal section_kind, section_payload, section_lines, pending_after_section
        if section_kind is None:
            return
        rendered = _render_section(section_kind, section_payload, section_lines)
        out.extend(rendered)
        out.extend(pending_after_section)
        section_kind = None
        section_payload = {}
        section_lines = []
        pending_after_section = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Section header — flush prior, start new.
        if stripped in _SECTION_HEADERS:
            flush_section()
            section_kind = stripped
            section_payload = _new_payload(section_kind, cmd_risk, flag_overrides, combo_risk)
            section_lines = [line]
            i += 1
            continue

        # Outside any section: emit verbatim.
        if section_kind is None:
            out.append(line)
            i += 1
            continue

        # Inside a section: classify line.
        if _TAG_LINE.match(line):
            i += 1  # drop
            continue

        if 'verdict' in line and 'require_approval' in line:
            line = _VERDICT_REQ_APPROVAL.sub(r'\1"ask"', line)

        # Track applies_to / flag / path for v2 field lookup.
        m = re.match(r'\s*(\w+)\s*=\s*"([^"]*)"', line)
        if m:
            key, value = m.group(1), m.group(2)
            if key in ("path", "applies_to", "flag"):
                section_payload.setdefault("_fields", {})[key] = value

        # Blank line ends the block — but the section may continue with
        # more entries of the same kind. We treat blank lines as block
        # separators and flush at the next section header.
        if stripped == "":
            # Stash trailing blank/comment lines so they emit AFTER the
            # appended v2 fields (preserving the original spacing).
            pending_after_section.append(line)
            i += 1
            continue

        section_lines.append(line)
        i += 1

    flush_section()
    return "".join(out)


def _new_payload(
    kind: str,
    cmd_risk: dict[str, str],
    flag_overrides: dict[tuple[str, str], str],
    combo_risk: dict[str, str],
) -> dict:
    return {
        "_kind": kind,
        "_cmd_risk": cmd_risk,
        "_flag_overrides": flag_overrides,
        "_combo_risk": combo_risk,
        "_fields": {},
    }


def _render_section(kind: str, payload: dict, lines: list[str]) -> list[str]:
    """Emit the section's surviving lines plus the v2 tail fields."""
    out = list(lines)
    fields: dict[str, str] = payload.get("_fields", {})
    cmd_risk: dict[str, str] = payload["_cmd_risk"]
    flag_overrides: dict[tuple[str, str], str] = payload["_flag_overrides"]
    combo_risk: dict[str, str] = payload["_combo_risk"]

    tail: list[str] = []
    if kind == "[[command]]":
        path = fields.get("path", "")
        rc = cmd_risk.get(path, NOVEL)
        tail.append(f'risk_class = "{rc}"\n')
    elif kind == "[[combo]]":
        path = fields.get("path", "")
        rc = combo_risk.get(path, NOVEL)
        tail.append(f'risk_class = "{rc}"\n')
    elif kind == "[[flag]]":
        applies_to = fields.get("applies_to", "")
        flag_name = fields.get("flag", "")
        # arity default per SCHEMA-v2.md §6.1.4
        if "arity" not in _section_keys(lines):
            tail.append('arity = "Boolean"\n')
        if (applies_to, flag_name) in flag_overrides:
            tail.append(f'risk_class_override = "{flag_overrides[(applies_to, flag_name)]}"\n')

    out.extend(tail)
    return out


def _section_keys(lines: list[str]) -> set[str]:
    keys: set[str] = set()
    for line in lines:
        m = re.match(r'\s*([a-zA-Z_][\w]*)\s*=', line)
        if m:
            keys.add(m.group(1))
    return keys


# ── CLI entry point ────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="v0 → v2 migration tool for intracept-registry tools/*.toml",
    )
    parser.add_argument(
        "paths", nargs="*", default=["tools"],
        help="Files or directories to migrate (default: tools/)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Compute migration but do not write any files",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-derive v2 from <name>.toml.v0.bak rather than the current file",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-file output; print only the summary",
    )
    args = parser.parse_args(argv)

    targets: list[Path] = []
    for p in args.paths:
        path = Path(p)
        if path.is_dir():
            targets.extend(sorted(path.glob("*.toml")))
        elif path.is_file():
            targets.append(path)
        else:
            print(f"error: {p} is neither a file nor a directory", file=sys.stderr)
            return 2

    if not targets:
        print("error: no .toml files to migrate", file=sys.stderr)
        return 2

    counts: dict[str, int] = {
        "migrated": 0,
        "already-migrated": 0,
        "would-migrate": 0,
        "would-skip": 0,
        "error": 0,
    }
    derivation_failures = 0

    for target in targets:
        result = migrate_file(target, force=args.force, dry_run=args.dry_run)
        counts[result.status] = counts.get(result.status, 0) + 1
        if result.derivation_errors:
            derivation_failures += 1

        if args.quiet:
            continue
        if result.status == "error":
            print(f"ERROR  {target}: {'; '.join(result.errors)}")
        elif result.derivation_errors:
            print(f"{result.status:18s} {target}  ({len(result.derivation_errors)} derivation warning(s))")
            for err in result.derivation_errors:
                print(f"    - {err}")
        else:
            print(f"{result.status:18s} {target}")

    print()
    print(
        f"summary: migrated={counts['migrated']} "
        f"already-migrated={counts['already-migrated']} "
        f"would-migrate={counts['would-migrate']} "
        f"would-skip={counts['would-skip']} "
        f"error={counts['error']} "
        f"derivation-failures={derivation_failures}"
    )

    if counts["error"] > 0 or derivation_failures > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
