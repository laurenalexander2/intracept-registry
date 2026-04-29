#!/usr/bin/env python3
"""Rebuild registry.json from the tools/*.toml sources.

Walks every TOML file in this directory, parses [[command]] and [[flag]] entries,
validates each file, and emits a flat, deterministically-ordered JSON index at
the repo root.

Run from any directory:

    python tools/build-index.py
    python /abs/path/to/intracept-registry/tools/build-index.py

Or programmatically by importing `build_index()`.

Stdlib-only (Python 3.11+).
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

# Repo layout: <repo-root>/tools/build-index.py and <repo-root>/registry.json.
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
TOOLS_DIR = SCRIPT_DIR
DEFAULT_INDEX_PATH = REPO_ROOT / "registry.json"

# Field order on disk is governed by sort_keys=True; the tuples below document
# the canonical record schema for readers, not the on-disk ordering. The path
# is the dict key and is therefore not duplicated inside the command record;
# likewise the flag string is part of the composite flag key.
COMMAND_FIELDS = ("tool", "translation", "verdict", "rationale")
FLAG_FIELDS = ("applies_to", "tool", "translation_modifier", "verdict", "rationale")


class ValidationError(Exception):
    """Raised when the TOML inputs violate cross-file or per-file invariants."""


def _flag_key(applies_to: str, flag: str) -> str:
    """Composite key used in the flat flags dict.

    Matches the existing registry.json shape: "<applies_to> <flag>" joined by a
    single space (e.g. "git push --force", "ls -l").
    """
    return f"{applies_to} {flag}"


def _load_toml(path: Path) -> dict:
    with path.open("rb") as fh:
        return tomllib.load(fh)


_REQUIRED_COMMAND_KEYS = ("path", "translation", "verdict", "rationale")
_REQUIRED_FLAG_KEYS = ("applies_to", "flag", "translation_modifier", "verdict", "rationale")


def _missing_required(entry: dict, required: tuple[str, ...]) -> list[str]:
    return [k for k in required if k not in entry]


def _command_record(entry: dict, tool: str) -> dict:
    # Path is the dict key in the flat index, so it is intentionally not
    # included as a field on the value record (matches existing registry.json).
    return {
        "tool": tool,
        "translation": entry["translation"],
        "verdict": entry["verdict"],
        "rationale": entry["rationale"],
    }


def _flag_record(entry: dict, tool: str) -> dict:
    # The flag string is part of the composite key ("<applies_to> <flag>") and
    # is therefore not duplicated as a field (matches existing registry.json).
    return {
        "applies_to": entry["applies_to"],
        "tool": tool,
        "translation_modifier": entry["translation_modifier"],
        "verdict": entry["verdict"],
        "rationale": entry["rationale"],
    }


def _validate_file(path: Path, commands: list[dict], flags: list[dict]) -> list[str]:
    """Return a list of validation error strings for one TOML file."""
    errors: list[str] = []
    seen_paths: set[str] = set()
    for idx, cmd in enumerate(commands):
        missing = _missing_required(cmd, _REQUIRED_COMMAND_KEYS)
        if missing:
            errors.append(
                f"{path.name}: [[command]] #{idx} missing required field(s): "
                f"{', '.join(missing)}"
            )
            continue
        cmd_path = cmd["path"]
        if cmd_path in seen_paths:
            errors.append(f"{path.name}: duplicate command path '{cmd_path}'")
        seen_paths.add(cmd_path)

    seen_flag_keys: set[str] = set()
    for idx, flag in enumerate(flags):
        missing = _missing_required(flag, _REQUIRED_FLAG_KEYS)
        if missing:
            errors.append(
                f"{path.name}: [[flag]] #{idx} missing required field(s): "
                f"{', '.join(missing)}"
            )
            continue
        applies_to = flag["applies_to"]
        flag_name = flag["flag"]
        if applies_to not in seen_paths:
            errors.append(
                f"{path.name}: flag '{flag_name}' references applies_to='{applies_to}' "
                f"which has no matching [[command]] in the same file"
            )
        key = _flag_key(applies_to, flag_name)
        if key in seen_flag_keys:
            errors.append(
                f"{path.name}: duplicate flag entry '{key}' (same applies_to+flag)"
            )
        seen_flag_keys.add(key)
    return errors


def build_index(tools_dir: Path = TOOLS_DIR) -> tuple[dict, dict]:
    """Build the (index_dict, stats_dict) pair from tools_dir/*.toml.

    Raises ValidationError listing every per-file and cross-file violation.
    """
    toml_paths = sorted(p for p in tools_dir.glob("*.toml") if p.is_file())

    commands: dict[str, dict] = {}
    flags: dict[str, dict] = {}
    # Track which file first defined each command path to localize cross-file
    # collisions in error messages.
    path_origin: dict[str, str] = {}

    all_errors: list[str] = []
    duplicate_path_errors: list[str] = []

    for toml_path in toml_paths:
        tool = toml_path.stem
        try:
            data = _load_toml(toml_path)
        except tomllib.TOMLDecodeError as exc:
            all_errors.append(f"{toml_path.name}: TOML parse error: {exc}")
            continue

        cmd_entries = data.get("command", []) or []
        flag_entries = data.get("flag", []) or []

        all_errors.extend(_validate_file(toml_path, cmd_entries, flag_entries))

        for cmd in cmd_entries:
            if _missing_required(cmd, _REQUIRED_COMMAND_KEYS):
                # Already reported by _validate_file; skip building the record.
                continue
            cmd_path = cmd["path"]
            if cmd_path in path_origin:
                duplicate_path_errors.append(
                    f"duplicate command path '{cmd_path}' defined in both "
                    f"{path_origin[cmd_path]} and {toml_path.name}"
                )
                continue
            path_origin[cmd_path] = toml_path.name
            commands[cmd_path] = _command_record(cmd, tool)

        for flag in flag_entries:
            if _missing_required(flag, _REQUIRED_FLAG_KEYS):
                # Already reported by _validate_file; skip building the record.
                continue
            key = _flag_key(flag["applies_to"], flag["flag"])
            # Same-file duplicates are caught in _validate_file. A cross-file
            # collision on the same flag key is unusual but possible (and
            # benign-ish since duplicate command paths are already a hard
            # error); the last-write-wins fallback is fine here.
            flags[key] = _flag_record(flag, tool)

    if all_errors or duplicate_path_errors:
        raise ValidationError("\n".join(all_errors + duplicate_path_errors))

    index = {"commands": commands, "flags": flags}
    stats = {
        "files_processed": len(toml_paths),
        "command_count": len(commands),
        "flag_count": len(flags),
    }
    return index, stats


def render(index: dict) -> str:
    """Return the canonical, byte-deterministic JSON serialization."""
    # sort_keys=True sorts every dict at every level → byte-identical output for
    # the same input. Trailing newline matches POSIX text-file convention.
    return json.dumps(index, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def write_index(index: dict, output_path: Path) -> bool:
    """Write the index to disk. Returns True if the file changed, False otherwise."""
    new_text = render(index)
    if output_path.exists():
        existing = output_path.read_text(encoding="utf-8")
        if existing == new_text:
            return False
    output_path.write_text(new_text, encoding="utf-8")
    return True


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild registry.json from tools/*.toml sources."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_INDEX_PATH,
        help=f"Output path for the index (default: {DEFAULT_INDEX_PATH}).",
    )
    parser.add_argument(
        "--tools-dir",
        type=Path,
        default=TOOLS_DIR,
        help=f"Directory containing tool TOML files (default: {TOOLS_DIR}).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Verify mode: do not write. Exit 0 if the on-disk index already "
            "matches what would be generated, exit 2 if it differs."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        index, stats = build_index(args.tools_dir)
    except ValidationError as exc:
        print("Validation failed:", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1

    new_text = render(index)
    output_path: Path = args.output

    if args.check:
        if not output_path.exists():
            print(f"check: {output_path} does not exist", file=sys.stderr)
            return 2
        existing = output_path.read_text(encoding="utf-8")
        if existing != new_text:
            print(f"check: {output_path} is out of sync with TOML sources", file=sys.stderr)
            return 2
        print(
            f"check: ok ({stats['files_processed']} files, "
            f"{stats['command_count']} commands, {stats['flag_count']} flags)"
        )
        return 0

    changed = write_index(index, output_path)

    print(
        f"Processed {stats['files_processed']} files: "
        f"{stats['command_count']} commands, {stats['flag_count']} flags. "
        f"Validation errors: 0. "
        f"{'Wrote' if changed else 'No changes to'} {output_path}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
