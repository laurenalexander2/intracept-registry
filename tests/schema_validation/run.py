#!/usr/bin/env python3
"""Schema validation test runner (registry side).

Two surfaces:

  (a) JSON fixtures (`fixtures/{valid,invalid}/json/`) validated against
      Session B's frozen snapshot at
      /Users/laurenalexander/intracept/fixtures/schema/{rule-schema-v2,
      toolspec, effects}.json.
  (b) TOML fixtures (`fixtures/{valid,invalid}/*.toml`) validated against
      tools/lint.py — the registry's own linter, which carries the
      authoring-time schema declared in SCHEMA.md.

Both must pass. Disagreement between the lint and the snapshot validator
on a case where they cover the same field (e.g. verdict vocabulary) is a
diff signal that gets surfaced — it's not the runner's job to silence it.
"""

from __future__ import annotations

import json
import sys
import subprocess
from pathlib import Path

try:
    from jsonschema import Draft7Validator, FormatChecker
    from jsonschema.exceptions import ValidationError
except ImportError:
    print("jsonschema not installed; run `pip install jsonschema`", file=sys.stderr)
    sys.exit(127)

FORMAT_CHECKER = FormatChecker()

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = Path(__file__).parent / "fixtures"
SNAPSHOT_DIR = Path("/Users/laurenalexander/intracept/fixtures/schema")
LINT_SCRIPT = REPO_ROOT / "tools" / "lint.py"

SNAPSHOT_FILES = {
    "rule": SNAPSHOT_DIR / "rule-schema-v2.json",
    "toolspec": SNAPSHOT_DIR / "toolspec.json",
    "effects": SNAPSHOT_DIR / "effects.json",
}


def snapshot_available() -> bool:
    return all(p.is_file() for p in SNAPSHOT_FILES.values())


def load_validators() -> dict[str, Draft7Validator]:
    return {
        name: Draft7Validator(
            json.loads(path.read_text()), format_checker=FORMAT_CHECKER
        )
        for name, path in SNAPSHOT_FILES.items()
    }


def detect_schema(fixture_name: str) -> str:
    """Pick which snapshot to validate against based on fixture filename prefix."""
    n = fixture_name.lower()
    if n.startswith("toolspec"):
        return "toolspec"
    if n.startswith("rule"):
        return "rule"
    if n.startswith("effect"):
        return "effects"
    raise ValueError(f"can't detect schema for fixture {fixture_name!r}")


def main() -> int:
    if not snapshot_available():
        missing = [str(p) for p in SNAPSHOT_FILES.values() if not p.is_file()]
        print(
            f"::error:: schema snapshot incomplete; missing: {missing}",
            file=sys.stderr,
        )
        print(
            "::error:: Session B must post the frozen JSON-schema snapshot at "
            f"{SNAPSHOT_DIR} before this runner can execute the JSON half.",
            file=sys.stderr,
        )
        return 2

    validators = load_validators()
    failures: list[str] = []

    # JSON fixtures — snapshot validation.
    for f in sorted((FIXTURE_ROOT / "valid" / "json").glob("*.json")):
        try:
            schema_key = detect_schema(f.stem)
        except ValueError as e:
            failures.append(str(e))
            continue
        doc = json.loads(f.read_text())
        errs = list(validators[schema_key].iter_errors(doc))
        if errs:
            failures.append(
                f"{f.relative_to(FIXTURE_ROOT)}: snapshot rejected a VALID fixture: "
                f"{[e.message for e in errs]}"
            )

    for f in sorted((FIXTURE_ROOT / "invalid" / "json").glob("*.json")):
        if f.name.endswith(".expected_error.json"):
            continue
        expected_path = f.with_suffix("").with_suffix(".expected_error.json")
        if not expected_path.is_file():
            failures.append(f"{f.name}: missing paired {expected_path.name}")
            continue
        expected = json.loads(expected_path.read_text())
        try:
            schema_key = detect_schema(f.stem)
        except ValueError as e:
            failures.append(str(e))
            continue
        doc = json.loads(f.read_text())
        errs = list(validators[schema_key].iter_errors(doc))
        if not errs:
            failures.append(f"{f.name}: snapshot accepted an INVALID fixture")
            continue
        msg_contains = expected.get("msg_contains", "")
        if msg_contains and not any(msg_contains in e.message for e in errs):
            failures.append(
                f"{f.name}: snapshot rejected but error message did not mention "
                f"{msg_contains!r}: {[e.message for e in errs]!r}"
            )

    # TOML fixtures — lint validation.
    # Files under future-lint/ are skipped here; they target the Phase 4a
    # TD-H3 lint update. See future-lint/README.md.
    skipped_future = 0
    for f in (FIXTURE_ROOT / "future-lint").rglob("*.toml"):
        skipped_future += 1
    for f in sorted((FIXTURE_ROOT / "valid").glob("*.toml")):
        rc, out = run_lint(f)
        if rc != 0:
            failures.append(f"{f.name}: lint rejected a VALID fixture: {out}")

    for f in sorted((FIXTURE_ROOT / "invalid").glob("*.toml")):
        expected_path = f.with_suffix(".expected_error.json")
        if not expected_path.is_file():
            failures.append(f"{f.name}: missing paired {expected_path.name}")
            continue
        expected = json.loads(expected_path.read_text())
        rc, out = run_lint(f)
        if rc == 0:
            failures.append(f"{f.name}: lint accepted an INVALID fixture")
            continue
        msg_contains = expected.get("msg_contains", "")
        if msg_contains and msg_contains not in out:
            failures.append(
                f"{f.name}: lint rejected but error message did not mention "
                f"{msg_contains!r}: {out!r}"
            )

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1

    json_v = len(list((FIXTURE_ROOT / "valid" / "json").glob("*.json")))
    json_i = sum(1 for f in (FIXTURE_ROOT / "invalid" / "json").glob("*.json")
                 if not f.name.endswith(".expected_error.json"))
    toml_v = len(list((FIXTURE_ROOT / "valid").glob("*.toml")))
    toml_i = len(list((FIXTURE_ROOT / "invalid").glob("*.toml")))
    print(f"OK: {json_v} valid + {json_i} invalid JSON fixtures (snapshot), "
          f"{toml_v} valid + {toml_i} invalid TOML fixtures (lint), "
          f"{skipped_future} future-lint fixtures pending TD-H3.")
    return 0


def run_lint(toml_path: Path) -> tuple[int, str]:
    if not LINT_SCRIPT.is_file():
        return 127, f"lint script not found at {LINT_SCRIPT}"
    proc = subprocess.run(
        ["python3", str(LINT_SCRIPT), str(toml_path)],
        capture_output=True, text=True,
    )
    return proc.returncode, (proc.stdout + proc.stderr)


if __name__ == "__main__":
    sys.exit(main())
