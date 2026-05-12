#!/usr/bin/env python3
"""Registry TOML linter — validates tool definitions against the schema and rubric."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

# --- Mode toggle ---
# False through Phase 4a (transitional); True after the v0→v2 migration runs.
# In transitional mode, v0 patterns are WARN; locked mode promotes them to ERROR.
STRICT_V2 = False

# --- Verdict (v2) ---
# v2 collapses {Allow, Warn, RequireApproval, Deny} → {allow, ask, warn}.
# The engine accepts "require_approval" as a deserialization alias for "ask"
# for v0/v1 policy.yaml compat (per session B's lock); lint flags it because
# new TOML authoring must use the v2 wire form.
VALID_VERDICTS = {"allow", "ask", "warn"}
V0_VERDICT_ALIAS = "require_approval"  # → ask, transitional WARN

# --- Risk class (v2) ---
# Single curator-set enum on every [[command]] and [[combo]]. Replaces the v0
# multi-axis tags. Default verdicts: safe→allow; net_egress,novel→ask;
# destructive,priv_esc,secret_read→warn.
VALID_RISK_CLASSES = {
    "safe",
    "net_egress",
    "novel",
    "destructive",
    "priv_esc",
    "secret_read",
}

# Most-dangerous-wins ordering for combo derivation check (lint rule 5).
RISK_CLASS_RANK = {
    "safe": 0,
    "net_egress": 1,
    "novel": 1,
    "destructive": 2,
    "priv_esc": 2,
    "secret_read": 2,
}

# --- Forbidden v0 tag axes (multi-axis tags drop in v2) ---
V0_TAG_DIMENSIONS = {"scope", "effect", "reversibility", "target", "safety_override"}

COMMAND_REQUIRED = ("path", "translation", "verdict", "rationale")
FLAG_REQUIRED = ("applies_to", "flag", "translation_modifier", "verdict", "rationale")
COMBO_REQUIRED = ("path", "translation", "verdict", "rationale")

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
    command_by_path: dict[str, dict] = {}  # for combo derivation check (rule 5)
    flag_tokens: dict[str, set[str]] = {}  # command_path -> set of flag strings
    flag_by_key: dict[tuple[str, str], dict] = {}  # (applies_to, flag) -> entry

    # --- A. Schema compliance for commands ---
    for i, cmd in enumerate(commands):
        eid = cmd.get("path", f"command[{i}]")
        for field in COMMAND_REQUIRED:
            val = cmd.get(field)
            if val is None or (isinstance(val, str) and val == ""):
                issues.append(Issue("ERROR", "command", eid, f"missing or empty required field '{field}'"))
        verdict = cmd.get("verdict", "")
        _check_verdict_v2(issues, "command", eid, verdict)
        path_val = cmd.get("path", "")
        if path_val:
            if path_val in command_paths:
                issues.append(Issue("ERROR", "command", eid, f"duplicate command path '{path_val}'"))
            command_paths.add(path_val)
            command_by_path[path_val] = cmd

        # --- Risk class (v2) ---
        _check_risk_class(issues, "command", eid, cmd, required=True)

        # --- D. Translation rules (commands) ---
        translation = cmd.get("translation", "")
        if isinstance(translation, str) and translation:
            _check_translation(issues, "command", eid, translation, path_val)

        # --- C. Consistency rules ---
        rationale = cmd.get("rationale", "")
        if isinstance(rationale, str) and isinstance(verdict, str):
            if verdict == "allow" and IRREVERSIBILITY_KEYWORDS.search(rationale):
                issues.append(Issue("WARN", "command", eid, "allow-verdict command has irreversibility keywords in rationale"))
            if verdict in {"ask", "warn", V0_VERDICT_ALIAS} and not BLAST_RADIUS_KEYWORDS.search(rationale):
                issues.append(Issue("WARN", "command", eid, f"{verdict}-verdict command lacks irreversibility/blast-radius keywords in rationale"))

        # --- F. Rationale quality (commands) ---
        if isinstance(rationale, str) and rationale:
            _check_rationale(issues, "command", eid, rationale, translation)

        # --- v0 multi-axis tag deprecation ---
        _check_v0_tag_deprecation(issues, "command", eid, cmd, prefix="tags")

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
        _check_verdict_v2(issues, "flag", eid, verdict)

        # --- Risk class override (v2) — optional on flags ---
        override = flg.get("risk_class_override", "")
        if override and override not in VALID_RISK_CLASSES:
            issues.append(Issue("ERROR", "flag", eid, f"invalid risk_class_override '{override}' (must be one of {sorted(VALID_RISK_CLASSES)})"))

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

        # --- v0 tag_modifiers deprecation ---
        _check_v0_tag_deprecation(issues, "flag", eid, flg, prefix="tag_modifiers")

        # Collect flag tokens + entries for combo validation
        applies_to = flg.get("applies_to", "")
        flag_val = flg.get("flag", "")
        if applies_to and flag_val:
            if (applies_to, flag_val) in flag_by_key:
                issues.append(Issue("ERROR", "flag", eid, f"duplicate flag entry '{applies_to} {flag_val}'"))
            flag_tokens.setdefault(applies_to, set()).add(flag_val)
            flag_by_key[(applies_to, flag_val)] = flg

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
        _check_verdict_v2(issues, "combo", eid, verdict)

        # Risk class (v2)
        _check_risk_class(issues, "combo", eid, combo, required=True)

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
        base_cmd = ""
        combo_flag_tokens: list[str] = []
        combo_path = combo.get("path", "")
        if combo_path:
            # Duplicate combo paths
            if combo_path in combo_paths:
                issues.append(Issue("ERROR", "combo", eid, "duplicate combo path"))
            combo_paths.add(combo_path)

            # Find the base command: longest command path that is a prefix
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
                        if token.startswith("-"):
                            combo_flag_tokens.append(token)
                            if token not in known_flags:
                                issues.append(Issue("ERROR", "combo", eid, f"flag '{token}' not found in [[flag]] entries for '{base_cmd}'"))

        # --- Combo risk_class derivation check (rule 5) ---
        if base_cmd and combo.get("risk_class") in VALID_RISK_CLASSES:
            _check_combo_risk_class_derivation(
                issues, eid, combo, base_cmd,
                command_by_path, flag_by_key, combo_flag_tokens,
            )

        # --- v0 multi-axis tag deprecation ---
        _check_v0_tag_deprecation(issues, "combo", eid, combo, prefix="tags")

        # Coherence checks (WARN) — v0 only; no-ops on v2-shape entries
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


def _v0_severity() -> str:
    """Severity for v0-deprecation patterns; WARN until Phase 4a, ERROR after."""
    return "ERROR" if STRICT_V2 else "WARN"


def _check_verdict_v2(issues: list[Issue], kind: str, eid: str, verdict: str) -> None:
    """v2 verdict validation: accept allow/ask/warn; v0 alias 'require_approval' WARN; unknown ERROR."""
    if not verdict:
        return
    if verdict in VALID_VERDICTS:
        return
    if verdict == V0_VERDICT_ALIAS:
        issues.append(Issue(_v0_severity(), kind, eid,
            f"v0 verdict '{V0_VERDICT_ALIAS}'; v2 wire form is 'ask' (alias accepted by engine for v0/v1 policy.yaml compat)"))
        return
    issues.append(Issue("ERROR", kind, eid,
        f"invalid verdict '{verdict}' (must be one of {sorted(VALID_VERDICTS)})"))


def _check_risk_class(issues: list[Issue], kind: str, eid: str, entry: dict, required: bool) -> None:
    """v2 risk_class validation: presence (transitional WARN; locked ERROR) + value enum."""
    rc = entry.get("risk_class", "")
    if not rc:
        if required:
            issues.append(Issue(_v0_severity(), kind, eid,
                "missing risk_class (v2); v0→v2 migration sets to 'novel' if tags don't unambiguously map"))
        return
    if rc not in VALID_RISK_CLASSES:
        issues.append(Issue("ERROR", kind, eid,
            f"invalid risk_class '{rc}' (must be one of {sorted(VALID_RISK_CLASSES)})"))


def _check_combo_risk_class_derivation(
    issues: list[Issue],
    eid: str,
    combo: dict,
    base_cmd_path: str,
    command_by_path: dict[str, dict],
    flag_by_key: dict[tuple[str, str], dict],
    combo_flag_tokens: list[str],
) -> None:
    """Combo risk_class must be ≥ most-dangerous(base, *flag overrides). Lint rule 5."""
    declared = combo.get("risk_class")
    base_cmd = command_by_path.get(base_cmd_path, {})
    base_rc = base_cmd.get("risk_class")
    if base_rc not in VALID_RISK_CLASSES:
        # Base lacks a valid risk_class — transitional pass; nothing to derive against.
        return

    expected_rank = RISK_CLASS_RANK[base_rc]
    expected_source = f"base '{base_rc}'"
    for token in combo_flag_tokens:
        flag_entry = flag_by_key.get((base_cmd_path, token), {})
        override = flag_entry.get("risk_class_override")
        if override in VALID_RISK_CLASSES:
            r = RISK_CLASS_RANK[override]
            if r > expected_rank:
                expected_rank = r
                expected_source = f"flag '{token}' override '{override}'"

    declared_rank = RISK_CLASS_RANK[declared]
    if declared_rank < expected_rank:
        issues.append(Issue("ERROR", "combo", eid,
            f"risk_class '{declared}' (rank {declared_rank}) is less dangerous than derived from {expected_source} (rank {expected_rank}); combo risk_class must be ≥ most-dangerous of base + flag overrides"))


def _check_v0_tag_deprecation(issues: list[Issue], kind: str, eid: str, entry: dict, prefix: str) -> None:
    """Detect v0 multi-axis tags / tag_modifiers; transitional WARN, locked ERROR.

    v2 drops the 5-axis tag block; the v0→v2 migration tool removes these fields.
    Lint emits one issue per entry (not per-axis) summarizing which v0 axes were found.

    tomllib parses `tags.scope = "x"` as nested {"tags": {"scope": "x"}}, not as a
    flat key "tags.scope" — the original v0 _check_tags missed this and silently
    no-op'd on every real TOML. We walk both shapes here for forensic completeness.
    """
    found: list[str] = []
    nested = entry.get(prefix)
    if isinstance(nested, dict):
        for dim in nested:
            if dim in V0_TAG_DIMENSIONS:
                found.append(dim)
    for key in entry:
        if not key.startswith(prefix + "."):
            continue
        dim = key[len(prefix) + 1:]
        if dim in V0_TAG_DIMENSIONS:
            found.append(dim)
    if found:
        issues.append(Issue(_v0_severity(), kind, eid,
            f"v0 {prefix}.{{{','.join(sorted(set(found)))}}} present; v0→v2 migration drops multi-axis tags (collapsed to single risk_class)"))


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
