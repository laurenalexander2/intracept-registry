#!/usr/bin/env python3
"""Schema validation test runner (registry side).

Runs every fixture in fixtures/valid/ and fixtures/invalid/ through:
  (a) the snapshot validator (Session B's frozen JSON-schema snapshot at
      /Users/laurenalexander/intracept/fixtures/schema/), AND
  (b) tools/lint.py (the existing linter).

Both must agree per the diff-CI pattern (TD-H1's spirit applied to schema
enforcement). Any disagreement is reported as a schema-vs-linter drift.

Until B posts the snapshot, (a) is stubbed with a hard fail-loud error so
nobody silently runs only half the diff-CI.
"""

from __future__ import annotations

import json
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = Path(__file__).parent / "fixtures"
SNAPSHOT_DIR = Path("/Users/laurenalexander/intracept/fixtures/schema")
LINT_SCRIPT = REPO_ROOT / "tools" / "lint.py"


def snapshot_available() -> bool:
    """Session B's deliverable. Until it lands, half the diff-CI is unrunnable."""
    required = ["rule.schema.json", "toolspec.schema.json", "policy.schema.json"]
    return SNAPSHOT_DIR.is_dir() and all((SNAPSHOT_DIR / r).is_file() for r in required)


def main() -> int:
    valid = sorted((FIXTURE_ROOT / "valid").glob("*.toml"))
    invalid = sorted((FIXTURE_ROOT / "invalid").glob("*.toml"))

    if not snapshot_available():
        print(f"::error:: schema snapshot not found at {SNAPSHOT_DIR}", file=sys.stderr)
        print(
            "::error:: Session B must post the frozen JSON-schema snapshot "
            "before this runner can execute. Until then, only `tools/lint.py` "
            "is runnable; the snapshot half of the diff-CI is gated.",
            file=sys.stderr,
        )
        return 2

    failures: list[str] = []

    for f in valid:
        rc, out = run_lint(f)
        if rc != 0:
            failures.append(f"{f.name}: lint rejected a VALID fixture: {out}")
        # TODO once snapshot lands: also run snapshot validator and assert agreement.

    for f in invalid:
        expected_path = f.with_suffix(".expected_error.json")
        if not expected_path.is_file():
            failures.append(f"{f.name}: missing paired {expected_path.name}")
            continue
        expected = json.loads(expected_path.read_text())
        rc, out = run_lint(f)
        if rc == 0:
            failures.append(f"{f.name}: lint accepted an INVALID fixture")
            continue
        # Check that lint's error message at least mentions the substring
        msg_contains = expected.get("msg_contains", "")
        if msg_contains and msg_contains not in out:
            failures.append(
                f"{f.name}: lint rejected but error message did not mention "
                f"{msg_contains!r}: {out!r}"
            )
        # TODO once snapshot lands: also run snapshot validator and assert
        # both implementations agree on the error 'kind'.

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"OK: {len(valid)} valid + {len(invalid)} invalid fixtures passed.")
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
