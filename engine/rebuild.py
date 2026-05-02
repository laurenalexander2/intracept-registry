#!/usr/bin/env python3
"""Deterministically rebuild registry.json from tools/*.toml files.

Usage:
    python engine/rebuild.py              # rebuild registry.json in place
    python engine/rebuild.py --stdout      # print to stdout instead of writing
    python engine/rebuild.py --check       # exit 1 if registry.json would change
    python engine/rebuild.py --diff        # show what would change
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
REGISTRY_PATH = REPO_ROOT / "registry.json"


def build_registry() -> tuple[dict, dict, dict, int]:
    """Parse all tools/*.toml files and return (commands, flags, combos, tool_count)."""
    commands: dict[str, dict] = {}
    flags: dict[str, dict] = {}
    combos: dict[str, dict] = {}
    toml_files = sorted(TOOLS_DIR.glob("*.toml"))

    for toml_path in toml_files:
        tool_name = toml_path.stem
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        for entry in data.get("command", []):
            path = entry["path"]
            cmd_entry: dict = {
                "tool": tool_name,
                "verdict": entry["verdict"],
                "translation": entry["translation"],
                "rationale": entry["rationale"],
            }
            if "tags" in entry:
                cmd_entry["tags"] = entry["tags"]
            commands[path] = cmd_entry

        for entry in data.get("flag", []):
            applies_to = entry["applies_to"]
            flag_value = entry["flag"]
            key = f"{applies_to} {flag_value}"
            flag_entry: dict = {
                "applies_to": applies_to,
                "tool": tool_name,
                "verdict": entry["verdict"],
                "translation_modifier": entry["translation_modifier"],
                "rationale": entry["rationale"],
            }
            if "tag_modifiers" in entry:
                flag_entry["tag_modifiers"] = entry["tag_modifiers"]
            flags[key] = flag_entry

        for entry in data.get("combo", []):
            path = entry["path"]
            combo_entry: dict = {
                "tool": tool_name,
                "verdict": entry["verdict"],
                "translation": entry["translation"],
                "rationale": entry["rationale"],
            }
            if "tags" in entry:
                combo_entry["tags"] = entry["tags"]
            combos[path] = combo_entry

    return commands, flags, combos, len(toml_files)


def serialize(commands: dict, flags: dict, combos: dict) -> str:
    """Produce deterministic JSON output with sorted keys."""
    registry = {
        "commands": dict(sorted(commands.items())),
        "flags": dict(sorted(flags.items())),
        "combos": dict(sorted(combos.items())),
    }
    return json.dumps(registry, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild registry.json from tools/*.toml files."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--stdout",
        action="store_true",
        help="Print generated JSON to stdout instead of writing to disk.",
    )
    group.add_argument(
        "--check",
        action="store_true",
        help="Check whether registry.json matches what would be generated; exit 1 on drift.",
    )
    group.add_argument(
        "--diff",
        action="store_true",
        help="Show a unified diff of what would change in registry.json.",
    )
    args = parser.parse_args()

    commands, flags, combos, tool_count = build_registry()
    generated = serialize(commands, flags, combos)

    summary = (
        f"{len(commands)} commands, {len(flags)} flags, "
        f"{len(combos)} combos from {tool_count} tools"
    )

    if args.stdout:
        sys.stdout.write(generated)
        print(f"\n# {summary}", file=sys.stderr)
        return 0

    if args.check or args.diff:
        if not REGISTRY_PATH.exists():
            print(f"ERROR: {REGISTRY_PATH} does not exist.", file=sys.stderr)
            return 1

        existing = REGISTRY_PATH.read_text(encoding="utf-8")

        if existing == generated:
            print(f"OK: registry.json is in sync. {summary}")
            return 0

        # There is drift.
        if args.check:
            print(f"DRIFT: registry.json is out of sync. {summary}")
            # Show a brief summary of differences.
            existing_data = json.loads(existing)
            generated_data = json.loads(generated)
            for section in ("commands", "flags", "combos"):
                old_keys = set(existing_data.get(section, {}).keys())
                new_keys = set(generated_data.get(section, {}).keys())
                added = new_keys - old_keys
                removed = old_keys - new_keys
                changed = 0
                for k in old_keys & new_keys:
                    if existing_data[section][k] != generated_data[section][k]:
                        changed += 1
                parts = []
                if added:
                    parts.append(f"+{len(added)} added")
                if removed:
                    parts.append(f"-{len(removed)} removed")
                if changed:
                    parts.append(f"~{changed} changed")
                if parts:
                    print(f"  {section}: {', '.join(parts)}")
            return 1

        # --diff mode
        diff = difflib.unified_diff(
            existing.splitlines(keepends=True),
            generated.splitlines(keepends=True),
            fromfile="registry.json (current)",
            tofile="registry.json (generated)",
        )
        sys.stdout.writelines(diff)
        print(f"\n# {summary}", file=sys.stderr)
        return 1

    # Default: write to disk.
    REGISTRY_PATH.write_text(generated, encoding="utf-8")
    print(f"Wrote {REGISTRY_PATH.name}: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
