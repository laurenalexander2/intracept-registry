#!/usr/bin/env python3
"""Registry TOML linter — validates tool definitions against the schema and rubric."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

VALID_VERDICTS = {"allow", "require_approval"}

COMMAND_REQUIRED = ("path", "translation", "verdict", "rationale")
FLAG_REQUIRED = ("applies_to", "flag", "translation_modifier", "verdict", "rationale")
COMBO_REQUIRED = ("path", "translation", "verdict", "rationale")

# --- Tag enums ---
VALID_SCOPES = {"local", "remote"}
VALID_EFFECTS = {"read", "write", "create", "delete", "execute"}
VALID_REVERSIBILITY = {"trivial", "difficult", "impossible"}
VALID_TARGETS = {"filesystem", "repository", "container", "cluster", "cloud",
                 "package_registry", "database", "credentials", "network",
                 "process", "config"}
TAG_DIMENSIONS = {"scope", "effect", "reversibility", "target", "safety_override"}
TAG_ENUM_MAP = {
    "scope": VALID_SCOPES,
    "effect": VALID_EFFECTS,
    "reversibility": VALID_REVERSIBILITY,
    "target": VALID_TARGETS,
}

IRREVERSIBILITY_KEYWORDS = re.compile(
    r"permanently|irreversible|no recovery|destroys|cannot be undone", re.IGNORECASE
)
BLAST_RADIUS_KEYWORDS = re.compile(
    r"permanently|irreversible|no recovery|destroys|cannot be undone|"
    r"all\b|entire|every|production|widespread|broad|wipe|catastroph",
    re.IGNORECASE,
)

MODIFIER_FIRST_WORD_PREPOSITIONS = {
    "with", "without", "to", "from", "by", "for", "into",
    "using", "including", "excluding", "after", "before",
    "at", "on", "as", "in", "across", "only", "also", "even",
}


class Issue:
    __slots__ = ("level", "entry_kind", "entry_id", "message")

    def __init__(self, level: str, entry_kind: str, entry_id: str, message: str):
        self.level = level  # "ERROR" or "WARN"
        self.entry_kind = entry_kind
        self.entry_id = entry_id
        self.message = message

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "entry_kind": self.entry_kind,
            "entry_id": self.entry_id,
            "message": self.message,
        }


def lint_file(filepath: Path) -> list[Issue]:
    """Lint a single TOML file, returning a list of issues."""
    issues: list[Issue] = []
    try:
        data = tomllib.loads(filepath.read_text(encoding="utf-8"))
    except Exception as e:
        issues.append(Issue("ERROR", "file", str(filepath), f"TOML parse error: {e}"))
        return issues

    commands = data.get("command", [])
    flags = data.get("flag", [])
    combos = data.get("combo", [])

    command_paths: set[str] = set()
    flag_tokens: dict[str, set[str]] = {}  # command_path -> set of flag strings

    # --- A. Schema compliance for commands ---
    for i, cmd in enumerate(commands):
        eid = cmd.get("path", f"command[{i}]")
        for field in COMMAND_REQUIRED:
            val = cmd.get(field)
            if val is None or (isinstance(val, str) and val == ""):
                issues.append(Issue("ERROR", "command", eid, f"missing or empty required field '{field}'"))
        verdict = cmd.get("verdict", "")
        if verdict and verdict not in VALID_VERDICTS:
            issues.append(Issue("ERROR", "command", eid, f"invalid verdict '{verdict}' (must be one of {sorted(VALID_VERDICTS)})"))
        path_val = cmd.get("path", "")
        if path_val:
            command_paths.add(path_val)

        # --- D. Translation rules (commands) ---
        translation = cmd.get("translation", "")
        if isinstance(translation, str) and translation:
            _check_translation(issues, "command", eid, translation, path_val)

        # --- C. Consistency rules ---
        rationale = cmd.get("rationale", "")
        if isinstance(rationale, str) and isinstance(verdict, str):
            if verdict == "allow" and IRREVERSIBILITY_KEYWORDS.search(rationale):
                issues.append(Issue("WARN", "command", eid, "allow-verdict command has irreversibility keywords in rationale"))
            if verdict == "require_approval" and not BLAST_RADIUS_KEYWORDS.search(rationale):
                issues.append(Issue("WARN", "command", eid, "require_approval-verdict command lacks irreversibility/blast-radius keywords in rationale"))

        # --- F. Rationale quality (commands) ---
        if isinstance(rationale, str) and rationale:
            _check_rationale(issues, "command", eid, rationale, translation)

        # --- Tag validation (commands) ---
        _check_tags(issues, "command", eid, cmd, prefix="tags")

    # --- A. Schema compliance for flags ---
    for i, flg in enumerate(flags):
        eid = f"{flg.get('applies_to', '?')} {flg.get('flag', f'flag[{i}]')}"
        for field in FLAG_REQUIRED:
            val = flg.get(field)
            if val is None:
                issues.append(Issue("ERROR", "flag", eid, f"missing required field '{field}'"))
            elif isinstance(val, str) and val == "" and field != "translation_modifier":
                issues.append(Issue("ERROR", "flag", eid, f"empty required field '{field}'"))
        verdict = flg.get("verdict", "")
        if verdict and verdict not in VALID_VERDICTS:
            issues.append(Issue("ERROR", "flag", eid, f"invalid verdict '{verdict}' (must be one of {sorted(VALID_VERDICTS)})"))

        # --- B. Reference integrity ---
        applies_to = flg.get("applies_to", "")
        if applies_to and applies_to not in command_paths:
            issues.append(Issue("ERROR", "flag", eid, f"applies_to '{applies_to}' does not match any command path in this file"))

        # --- E. Modifier grammar ---
        modifier = flg.get("translation_modifier")
        if isinstance(modifier, str) and modifier:
            _check_modifier(issues, "flag", eid, modifier)

        # --- F. Rationale quality (flags) ---
        rationale = flg.get("rationale", "")
        translation = flg.get("translation_modifier", "")
        if isinstance(rationale, str) and rationale:
            _check_rationale(issues, "flag", eid, rationale, translation)

        # --- Tag modifier validation (flags) ---
        _check_tags(issues, "flag", eid, flg, prefix="tag_modifiers")

        # Collect flag tokens for combo validation
        applies_to = flg.get("applies_to", "")
        flag_val = flg.get("flag", "")
        if applies_to and flag_val:
            flag_tokens.setdefault(applies_to, set()).add(flag_val)

    # --- Combo linting ---
    combo_paths: set[str] = set()
    for i, combo in enumerate(combos):
        eid = combo.get("path", f"combo[{i}]")

        # Required fields
        for field in COMBO_REQUIRED:
            val = combo.get(field)
            if val is None or (isinstance(val, str) and val == ""):
                issues.append(Issue("ERROR", "combo", eid, f"missing or empty required field '{field}'"))

        # Verdict validation
        verdict = combo.get("verdict", "")
        if verdict and verdict not in VALID_VERDICTS:
            issues.append(Issue("ERROR", "combo", eid, f"invalid verdict '{verdict}' (must be one of {sorted(VALID_VERDICTS)})"))

        # Translation rules for combos
        translation = combo.get("translation", "")
        if isinstance(translation, str) and translation:
            if not translation.endswith("."):
                issues.append(Issue("ERROR", "combo", eid, "translation must end with a period"))
            length = len(translation)
            if length < 5:
                issues.append(Issue("ERROR", "combo", eid, f"translation too short ({length} chars, min 5)"))
            if length > 300:
                issues.append(Issue("ERROR", "combo", eid, f"translation too long ({length} chars, max 300)"))

        # Rationale rules for combos
        rationale = combo.get("rationale", "")
        if isinstance(rationale, str) and rationale:
            rat_len = len(rationale)
            if rat_len < 20:
                issues.append(Issue("WARN", "combo", eid, f"rationale too short ({rat_len} chars, min 20)"))
            if rat_len > 400:
                issues.append(Issue("WARN", "combo", eid, f"rationale too long ({rat_len} chars, max 400)"))

        # Path must start with a valid command path
        combo_path = combo.get("path", "")
        if combo_path:
            # Duplicate combo paths
            if combo_path in combo_paths:
                issues.append(Issue("ERROR", "combo", eid, "duplicate combo path"))
            combo_paths.add(combo_path)

            # Find the base command: longest command path that is a prefix
            base_cmd = ""
            for cp in command_paths:
                if combo_path == cp or combo_path.startswith(cp + " "):
                    if len(cp) > len(base_cmd):
                        base_cmd = cp
            if not base_cmd:
                issues.append(Issue("ERROR", "combo", eid, "path does not start with any [[command]] path in this file"))
            else:
                # Extract flag tokens from the combo path
                remainder = combo_path[len(base_cmd):].strip()
                if remainder:
                    tokens = remainder.split()
                    known_flags = flag_tokens.get(base_cmd, set())
                    for token in tokens:
                        if token.startswith("-") and token not in known_flags:
                            issues.append(Issue("ERROR", "combo", eid, f"flag '{token}' not found in [[flag]] entries for '{base_cmd}'"))

        # Tag validation (combos)
        _check_tags(issues, "combo", eid, combo, prefix="tags")

        # Coherence checks (WARN)
        _check_coherence(issues, "combo", eid, combo)

    # Coherence checks on commands too
    for i, cmd in enumerate(commands):
        eid = cmd.get("path", f"command[{i}]")
        _check_coherence(issues, "command", eid, cmd)

    return issues


def _check_translation(issues: list[Issue], kind: str, eid: str, translation: str, path: str) -> None:
    """Check D: Translation rules."""
    if path and " " in path and re.search(r"\b" + re.escape(path) + r"\b", translation):
        issues.append(Issue("ERROR", kind, eid, "translation echoes command verbatim"))
    length = len(translation)
    if length < 5:
        issues.append(Issue("ERROR", kind, eid, f"translation too short ({length} chars, min 5)"))
    if length > 200:
        issues.append(Issue("ERROR", kind, eid, f"translation too long ({length} chars, max 200)"))
    if not translation[0].isupper():
        issues.append(Issue("ERROR", kind, eid, "translation must start with a capital letter"))
    if not translation.endswith("."):
        issues.append(Issue("ERROR", kind, eid, "translation must end with a period"))


def _check_modifier(issues: list[Issue], kind: str, eid: str, modifier: str) -> None:
    """Check E: Modifier grammar."""
    if modifier.endswith("."):
        issues.append(Issue("WARN", kind, eid, "translation_modifier should not end with a period"))
    if modifier[0].isupper():
        issues.append(Issue("WARN", kind, eid, "translation_modifier should not start with a capital letter"))
    first_word = re.split(r"[\s,]", modifier, maxsplit=1)[0].lower()
    ok = (
        first_word in MODIFIER_FIRST_WORD_PREPOSITIONS
        or first_word.endswith("ing")
        or first_word.endswith("ed")
        or first_word.endswith("ly")
    )
    if not ok:
        issues.append(Issue("WARN", kind, eid, f"translation_modifier first word '{first_word}' should be a gerund (-ing), past participle (-ed), or preposition"))


def _check_rationale(issues: list[Issue], kind: str, eid: str, rationale: str, translation: str) -> None:
    """Check F: Rationale quality."""
    length = len(rationale)
    if length < 20:
        issues.append(Issue("WARN", kind, eid, f"rationale too short ({length} chars, min 20)"))
    if length > 400:
        issues.append(Issue("WARN", kind, eid, f"rationale too long ({length} chars, max 400)"))
    if rationale == translation:
        issues.append(Issue("WARN", kind, eid, "rationale exactly equals translation"))


def _check_tags(issues: list[Issue], kind: str, eid: str, entry: dict, prefix: str) -> None:
    """Validate tags.* or tag_modifiers.* fields against known enums."""
    found_dims: set[str] = set()
    for key, val in entry.items():
        if not key.startswith(prefix + "."):
            continue
        dim = key[len(prefix) + 1:]
        found_dims.add(dim)

        if dim not in TAG_DIMENSIONS:
            issues.append(Issue("ERROR", kind, eid, f"unknown tag dimension '{dim}' in {prefix}"))
            continue

        if dim == "safety_override":
            if not isinstance(val, bool):
                issues.append(Issue("ERROR", kind, eid, f"{prefix}.safety_override must be a boolean"))
        elif dim in TAG_ENUM_MAP:
            valid = TAG_ENUM_MAP[dim]
            # effect and target can be lists; scope and reversibility are strings
            if dim in ("effect", "target"):
                vals = val if isinstance(val, list) else [val]
                for v in vals:
                    if v not in valid:
                        issues.append(Issue("ERROR", kind, eid, f"invalid value '{v}' for {prefix}.{dim} (must be one of {sorted(valid)})"))
            else:
                if val not in valid:
                    issues.append(Issue("ERROR", kind, eid, f"invalid value '{val}' for {prefix}.{dim} (must be one of {sorted(valid)})"))

    # Tag completeness (WARN): some but not all 5 dimensions → WARN
    if found_dims and found_dims != TAG_DIMENSIONS:
        missing = TAG_DIMENSIONS - found_dims
        issues.append(Issue("WARN", kind, eid, f"incomplete tags: missing {sorted(missing)}"))


def _check_coherence(issues: list[Issue], kind: str, eid: str, entry: dict) -> None:
    """Coherence checks between tags and verdict (WARN level)."""
    verdict = entry.get("verdict", "")
    # Determine prefix based on kind
    prefix = "tags"
    safety = entry.get(f"{prefix}.safety_override")
    reversibility = entry.get(f"{prefix}.reversibility")
    effect = entry.get(f"{prefix}.effect")

    # safety_override=true + verdict="allow" → WARN
    if safety is True and verdict == "allow":
        issues.append(Issue("WARN", kind, eid, "safety_override=true but verdict is 'allow'"))

    # reversibility="impossible" + verdict="allow" → WARN
    if reversibility == "impossible" and verdict == "allow":
        issues.append(Issue("WARN", kind, eid, "reversibility='impossible' but verdict is 'allow'"))

    # effect only ["read"] + verdict="require_approval" → WARN
    if isinstance(effect, list) and effect == ["read"] and verdict == "require_approval":
        issues.append(Issue("WARN", kind, eid, "effect is only ['read'] but verdict is 'require_approval'"))
    elif effect == "read" and verdict == "require_approval":
        issues.append(Issue("WARN", kind, eid, "effect is only 'read' but verdict is 'require_approval'"))


def collect_files(path: Path) -> list[Path]:
    """Collect TOML files from a path (file or directory)."""
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.glob("*.toml"))
    print(f"Error: {path} is not a file or directory", file=sys.stderr)
    sys.exit(2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint intracept-registry TOML files")
    parser.add_argument("path", type=Path, help="File or directory to lint")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--quiet", action="store_true", help="Exit code only, no output on success")
    args = parser.parse_args(argv)

    files = collect_files(args.path)
    if not files:
        if not args.quiet:
            print("No TOML files found.", file=sys.stderr)
        return 0

    all_results: dict[str, list[Issue]] = {}
    total_errors = 0
    total_warnings = 0
    passed = 0

    for f in files:
        file_issues = lint_file(f)
        all_results[str(f)] = file_issues
        errs = sum(1 for i in file_issues if i.level == "ERROR")
        warns = sum(1 for i in file_issues if i.level == "WARN")
        total_errors += errs
        total_warnings += warns
        if errs == 0:
            passed += 1

    if args.json:
        output = {
            "summary": {
                "files": len(files),
                "passed": passed,
                "errors": total_errors,
                "warnings": total_warnings,
            },
            "results": {
                fp: [i.to_dict() for i in issues]
                for fp, issues in all_results.items()
            },
        }
        print(json.dumps(output, indent=2))
    elif not args.quiet or total_errors > 0:
        for fp, file_issues in all_results.items():
            if not file_issues:
                # Count entries for OK line
                try:
                    data = tomllib.loads(Path(fp).read_text(encoding="utf-8"))
                    nc = len(data.get("command", []))
                    nf = len(data.get("flag", []))
                    nb = len(data.get("combo", []))
                except Exception:
                    nc = nf = nb = 0
                if not args.quiet:
                    print(f"{fp}:")
                    print(f"  OK ({nc} commands, {nf} flags, {nb} combos)")
                    print()
            else:
                print(f"{fp}:")
                for issue in file_issues:
                    tag = "ERROR" if issue.level == "ERROR" else "WARN "
                    print(f"  {tag} {issue.entry_kind} '{issue.entry_id}': {issue.message}")
                print()

        # Summary
        print(f"Summary: {total_errors} errors, {total_warnings} warnings across {len(files):,} files ({passed:,} passed)")

    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
