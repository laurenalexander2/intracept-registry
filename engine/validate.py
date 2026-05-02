#!/usr/bin/env python3
"""Schema validator for intracept-registry tools/*.toml files.

Validates every tools/*.toml file against SCHEMA.md rules:
1. Required fields present on [[command]] and [[flag]] entries
2. risk is one of: low, medium, high, critical, unknown
3. translation ends with a period
4. translation_modifier does NOT end with a period (unless empty)
5. Every flag.applies_to matches a command.path in the same file
6. No duplicate command paths
7. No duplicate (applies_to, flag) pairs
8. translation_modifier should be a gerund/prepositional phrase, not a standalone sentence
9. path tokens starting with - are only flagged if the same token appears
   as a flag on the same applies_to (contradictory: both path and flag)
"""

import re
import sys
import tomllib
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
VALID_VERDICTS = frozenset({"allow", "require_approval"})
COMMAND_REQUIRED = {"path", "translation", "verdict", "rationale"}
FLAG_REQUIRED = {"applies_to", "flag", "translation_modifier", "verdict", "rationale"}
COMBO_REQUIRED = {"path", "translation", "verdict", "rationale"}

VALID_TAG_SCOPES = frozenset({"local", "remote"})
VALID_TAG_EFFECTS = frozenset({"read", "write", "create", "delete", "execute"})
VALID_TAG_REVERSIBILITY = frozenset({"trivial", "difficult", "impossible"})
VALID_TAG_TARGETS = frozenset({
    "filesystem", "repository", "container", "cluster", "cloud",
    "package_registry", "database", "credentials", "network", "process", "config",
})

# Sentence-start patterns that indicate a standalone sentence, not a phrase.
_SENTENCE_STARTERS = re.compile(
    r"^(This |That |It |The [a-z]+ (is|was|does|will|can|could|should|would|has|have|had) )"
)
# Imperative/finite-verb opener: capital letter followed by a non-gerund verb.
_IMPERATIVE_OPENER = re.compile(
    r"^[A-Z][a-z]+(?<!ing)(?<!ed)s?\s"
)
# Legitimate phrase starters (gerunds, adverbs, participles, prepositions, etc.)
_ALLOWED_CAPITALIZED = re.compile(
    r"^(Also |Only |Even |Including |Excluding |Using |Limiting |Simulating "
    r"|Allowing |Applying |Overwriting |Skipping |Removing |Deleting "
    r"|Replacing |Creating |Running |Showing |Displaying |Printing "
    r"|Setting |Enabling |Disabling |Adding |Starting |Stopping "
    r"|Filtering |Searching |Sorting |Listing |Writing |Reading "
    r"|Forcing |Prompting |Recursively |Automatically |Immediately "
    r"|Silently |Explicitly )"
)


def _validate_tags(tags: dict, context: str) -> list[str]:
    """Validate a tags or tag_modifiers dict. Returns errors."""
    errors: list[str] = []

    if "scope" in tags:
        if tags["scope"] not in VALID_TAG_SCOPES:
            errors.append(
                f"{context}: tags.scope '{tags['scope']}' "
                f"must be one of {sorted(VALID_TAG_SCOPES)}"
            )

    if "effect" in tags:
        effects = tags["effect"] if isinstance(tags["effect"], list) else [tags["effect"]]
        for e in effects:
            if e not in VALID_TAG_EFFECTS:
                errors.append(
                    f"{context}: tags.effect '{e}' "
                    f"must be one of {sorted(VALID_TAG_EFFECTS)}"
                )

    if "reversibility" in tags:
        if tags["reversibility"] not in VALID_TAG_REVERSIBILITY:
            errors.append(
                f"{context}: tags.reversibility '{tags['reversibility']}' "
                f"must be one of {sorted(VALID_TAG_REVERSIBILITY)}"
            )

    if "target" in tags:
        targets = tags["target"] if isinstance(tags["target"], list) else [tags["target"]]
        for t in targets:
            if t not in VALID_TAG_TARGETS:
                errors.append(
                    f"{context}: tags.target '{t}' "
                    f"must be one of {sorted(VALID_TAG_TARGETS)}"
                )

    if "safety_override" in tags:
        if not isinstance(tags["safety_override"], bool):
            errors.append(
                f"{context}: tags.safety_override must be a boolean"
            )

    return errors


def validate_file(filepath: Path) -> list[str]:
    """Return a list of error strings for a single TOML file."""
    errors: list[str] = []

    try:
        with open(filepath, "rb") as f:
            data = tomllib.load(f)
    except Exception as exc:
        return [f"PARSE ERROR: {exc}"]

    commands = data.get("command", [])
    flags = data.get("flag", [])

    # ── Collect command paths ────────────────────────────────────────────
    command_paths: set[str] = set()
    for i, cmd in enumerate(commands):
        tag = f"command[{i}]"

        missing = COMMAND_REQUIRED - set(cmd.keys())
        if missing:
            errors.append(f"{tag}: missing required fields: {sorted(missing)}")
            continue  # can't validate further without required fields

        path: str = cmd["path"]
        translation: str = cmd["translation"]
        verdict: str = cmd["verdict"]

        # Duplicate path
        if path in command_paths:
            errors.append(f"{tag}: duplicate path '{path}'")
        command_paths.add(path)

        # Verdict value
        if verdict not in VALID_VERDICTS:
            errors.append(f"{tag} ({path}): invalid verdict '{verdict}' "
                          f"(must be one of {sorted(VALID_VERDICTS)})")

        # Validate tags if present
        if "tags" in cmd:
            errors.extend(_validate_tags(cmd["tags"], f"{tag} ({path})"))

        # Translation must end with a period
        if not translation.endswith("."):
            errors.append(f"{tag} ({path}): translation must end with a period")

    # ── Build a lookup of flag entries keyed by (applies_to, flag) ───────
    # Used for the contradictory-path-and-flag check below.
    flag_set: set[tuple[str, str]] = set()
    for flg in flags:
        at = flg.get("applies_to", "")
        fn = flg.get("flag", "")
        if at and fn:
            flag_set.add((at, fn))

    # ── Check command paths for contradictory flag-like tokens ───────────
    for i, cmd in enumerate(commands):
        path = cmd.get("path", "")
        tokens = path.split()
        if len(tokens) < 2:
            continue
        for token in tokens[1:]:  # skip the tool name itself
            if token.startswith("-"):
                # Only warn if there is also a [[flag]] entry with the same
                # applies_to and flag, which would be contradictory.
                # The parent is everything before this token.
                parent = " ".join(tokens[: tokens.index(token)])
                if (parent, token) in flag_set:
                    errors.append(
                        f"command[{i}] ({path}): path token '{token}' is also "
                        f"declared as a flag on '{parent}' — contradictory"
                    )

    # ── Validate flags ──────────────────────────────────────────────────
    seen_pairs: set[tuple[str, str]] = set()
    for i, flg in enumerate(flags):
        tag = f"flag[{i}]"

        missing = FLAG_REQUIRED - set(flg.keys())
        if missing:
            errors.append(f"{tag}: missing required fields: {sorted(missing)}")
            continue

        applies_to: str = flg["applies_to"]
        flag_name: str = flg["flag"]
        modifier: str = flg["translation_modifier"]
        verdict: str = flg["verdict"]

        # applies_to must match an existing command path
        if applies_to not in command_paths:
            errors.append(
                f"{tag} ({flag_name}): applies_to '{applies_to}' "
                f"does not match any command path"
            )

        # Duplicate (applies_to, flag) pair
        pair = (applies_to, flag_name)
        if pair in seen_pairs:
            errors.append(
                f"{tag}: duplicate (applies_to, flag) pair "
                f"('{applies_to}', '{flag_name}')"
            )
        seen_pairs.add(pair)

        # Verdict value
        if verdict not in VALID_VERDICTS:
            errors.append(
                f"{tag} ({flag_name}): invalid verdict '{verdict}' "
                f"(must be one of {sorted(VALID_VERDICTS)})"
            )

        # Validate tag_modifiers if present
        if "tag_modifiers" in flg:
            errors.extend(_validate_tags(flg["tag_modifiers"], f"{tag} ({flag_name})"))

        # Modifier must NOT end with a period (unless empty)
        if modifier and modifier.endswith("."):
            errors.append(
                f"{tag} ({flag_name}): translation_modifier must not "
                f"end with a period"
            )

        # Modifier should be a gerund/prepositional phrase, not a sentence
        if modifier:
            # Check for obvious sentence starters
            if _SENTENCE_STARTERS.match(modifier):
                errors.append(
                    f"{tag} ({flag_name}): translation_modifier looks like "
                    f"a standalone sentence, not a phrase"
                )
            # Check for imperative/finite-verb openers that aren't
            # legitimate participial/gerund starters
            elif (_IMPERATIVE_OPENER.match(modifier)
                  and not _ALLOWED_CAPITALIZED.match(modifier)
                  and not modifier.split()[0].endswith("ing")
                  and not modifier.split()[0].endswith("ed")
                  and not modifier.split()[0].endswith("ly")):
                errors.append(
                    f"{tag} ({flag_name}): translation_modifier appears to "
                    f"start with a finite verb — should be a gerund or "
                    f"prepositional phrase"
                )

    # ── Validate combos ─────────────────────────────────────────────────
    combos = data.get("combo", [])
    seen_combo_paths: set[str] = set()
    for i, combo in enumerate(combos):
        tag = f"combo[{i}]"

        missing = COMBO_REQUIRED - set(combo.keys())
        if missing:
            errors.append(f"{tag}: missing required fields: {sorted(missing)}")
            continue

        combo_path: str = combo["path"]
        combo_verdict: str = combo["verdict"]

        # Duplicate combo path
        if combo_path in seen_combo_paths:
            errors.append(f"{tag}: duplicate combo path '{combo_path}'")
        seen_combo_paths.add(combo_path)

        # Verdict value
        if combo_verdict not in VALID_VERDICTS:
            errors.append(
                f"{tag} ({combo_path}): invalid verdict '{combo_verdict}' "
                f"(must be one of {sorted(VALID_VERDICTS)})"
            )

        # Combo path must start with a valid command path
        combo_tokens = combo_path.split()
        base_found = False
        for length in range(len(combo_tokens), 0, -1):
            candidate = " ".join(combo_tokens[:length])
            if candidate in command_paths:
                base_found = True
                break
        if not base_found:
            errors.append(
                f"{tag} ({combo_path}): combo path does not start with "
                f"a valid command path"
            )

        # Every flag token in combo path must match a flag entry
        for token in combo_tokens:
            if token.startswith("-"):
                # Find the base command for this flag
                token_idx = combo_tokens.index(token)
                base = " ".join(combo_tokens[:token_idx])
                # Walk back to find the longest matching command path
                base_tokens = base.split()
                matched_base = None
                for length in range(len(base_tokens), 0, -1):
                    candidate = " ".join(base_tokens[:length])
                    if candidate in command_paths:
                        matched_base = candidate
                        break
                if matched_base and (matched_base, token) not in flag_set:
                    errors.append(
                        f"{tag} ({combo_path}): flag token '{token}' "
                        f"is not a declared flag on '{matched_base}'"
                    )

        # Validate tags if present
        if "tags" in combo:
            errors.extend(_validate_tags(combo["tags"], f"{tag} ({combo_path})"))

    return errors


def main() -> None:
    files = sorted(TOOLS_DIR.glob("*.toml"))
    if not files:
        print(f"No TOML files found in {TOOLS_DIR}")
        sys.exit(1)

    total_errors = 0
    error_files: dict[str, list[str]] = {}

    for filepath in files:
        errs = validate_file(filepath)
        if errs:
            error_files[filepath.name] = errs
            total_errors += len(errs)

    clean = len(files) - len(error_files)
    print(
        f"{len(files)} files validated, {clean} clean, "
        f"{len(error_files)} with errors, {total_errors} total errors"
    )

    if error_files:
        print()
        # Sort by error count descending, then filename ascending
        for name, errs in sorted(
            error_files.items(), key=lambda x: (-len(x[1]), x[0])
        ):
            print(f"--- {name} ({len(errs)} error{'s' if len(errs) != 1 else ''}) ---")
            for err in errs:
                print(f"  {err}")
            print()

    sys.exit(1 if total_errors > 0 else 0)


if __name__ == "__main__":
    main()
