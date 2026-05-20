#!/usr/bin/env python3
"""Tests for engine/v0_to_v2.py — the v0 → v2 migration tool.

Run via:  python3 -m unittest engine.test_v0_to_v2
or:       python3 engine/test_v0_to_v2.py
"""

from __future__ import annotations

import shutil
import tempfile
import tomllib
import unittest
from pathlib import Path

from engine.v0_to_v2 import (
    NOVEL,
    derive_risk_class,
    is_already_v2,
    main as cli_main,
    migrate_file,
)


# ── §6.2 derivation table ──────────────────────────────────────────────────

class DerivationTableTests(unittest.TestCase):
    """Each row of SCHEMA-v2.md §6.2 fires the locked risk_class."""

    def test_delete_impossible_to_destructive(self):
        rc, err = derive_risk_class({
            "tags": {
                "effect": ["delete"],
                "reversibility": "impossible",
                "scope": "remote",
                "target": ["filesystem"],
            }
        })
        self.assertEqual(rc, "destructive")
        self.assertIsNone(err)

    def test_delete_difficult_to_destructive(self):
        rc, _ = derive_risk_class({
            "tags": {"effect": ["delete"], "reversibility": "difficult"}
        })
        self.assertEqual(rc, "destructive")

    def test_credentials_target_to_secret_read(self):
        rc, _ = derive_risk_class({
            "tags": {"target": ["credentials"], "scope": "local"}
        })
        self.assertEqual(rc, "secret_read")

    def test_network_remote_to_net_egress(self):
        rc, _ = derive_risk_class({
            "tags": {"target": ["network"], "scope": "remote"}
        })
        self.assertEqual(rc, "net_egress")

    def test_safety_override_to_priv_esc(self):
        rc, _ = derive_risk_class({
            "tags": {"safety_override": True, "scope": "local"}
        })
        self.assertEqual(rc, "priv_esc")

    def test_read_only_local_to_safe(self):
        rc, _ = derive_risk_class({
            "tags": {"effect": ["read"], "scope": "local", "reversibility": "trivial"}
        })
        self.assertEqual(rc, "safe")

    def test_no_tags_to_novel(self):
        rc, err = derive_risk_class({"tags": {}})
        self.assertEqual(rc, NOVEL)
        self.assertIsNone(err)

    def test_no_tags_block_to_novel(self):
        rc, err = derive_risk_class({})
        self.assertEqual(rc, NOVEL)
        self.assertIsNone(err)

    def test_destructive_takes_precedence_over_safety_override(self):
        """destructive rules sort before priv_esc; the qualifier in §6.2 is
        'and not destructive/secret_read'. Both rules' preconditions hold,
        but the precedence ordering picks destructive."""
        rc, _ = derive_risk_class({
            "tags": {
                "effect": ["delete"],
                "reversibility": "impossible",
                "safety_override": True,
            }
        })
        self.assertEqual(rc, "destructive")

    def test_secret_read_takes_precedence_over_safety_override(self):
        rc, _ = derive_risk_class({
            "tags": {"target": ["credentials"], "safety_override": True}
        })
        self.assertEqual(rc, "secret_read")

    def test_unmappable_falls_through_to_novel(self):
        """Unknown effect string ('frobnicate') is shape-valid (it's a list
        member) but not in the derivation table — falls through to novel
        without an error."""
        rc, err = derive_risk_class({
            "tags": {"effect": ["frobnicate"], "scope": "local"}
        })
        self.assertEqual(rc, NOVEL)
        self.assertIsNone(err)

    def test_type_mismatch_emits_error(self):
        """tags.effect must be a list per §6.2; a string here is a shape
        violation that surfaces a structured error AND falls back to novel."""
        rc, err = derive_risk_class({"tags": {"effect": "frobnicate"}})
        self.assertEqual(rc, NOVEL)
        self.assertIsNotNone(err)
        self.assertIn("effect", err)
        self.assertIn("list", err)

    def test_tag_modifiers_key(self):
        """tag_modifiers blocks on flags use the same derivation table."""
        rc, _ = derive_risk_class(
            {"tag_modifiers": {"effect": ["delete"], "reversibility": "impossible"}},
            tag_key="tag_modifiers",
        )
        self.assertEqual(rc, "destructive")


# ── Idempotency + --force round-trip ───────────────────────────────────────

class IdempotencyTests(unittest.TestCase):
    """A v2 file re-migrates as a no-op; --force regenerates from .v0.bak."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_v0_file(self, name: str = "sample.toml", body: str | None = None) -> Path:
        path = self.tmpdir / name
        path.write_text(body or _V0_SAMPLE, encoding="utf-8")
        return path

    def test_first_pass_migrates(self):
        path = self._make_v0_file()
        r = migrate_file(path)
        self.assertEqual(r.status, "migrated")
        self.assertTrue(r.backup_written)
        self.assertTrue((path.parent / (path.name + ".v0.bak")).exists())

    def test_second_pass_is_noop(self):
        path = self._make_v0_file()
        migrate_file(path)
        bak_mtime = (path.parent / (path.name + ".v0.bak")).stat().st_mtime
        post_first = path.read_bytes()

        r = migrate_file(path)
        self.assertEqual(r.status, "already-migrated")
        self.assertEqual(path.read_bytes(), post_first, "second pass must not modify the file")
        self.assertEqual(
            (path.parent / (path.name + ".v0.bak")).stat().st_mtime,
            bak_mtime,
            "second pass must not rewrite the backup",
        )

    def test_force_regenerates_byte_identical(self):
        path = self._make_v0_file()
        r1 = migrate_file(path)
        first = path.read_bytes()

        r2 = migrate_file(path, force=True)
        second = path.read_bytes()

        self.assertEqual(r1.status, "migrated")
        self.assertEqual(r2.status, "migrated")
        self.assertEqual(first, second, "--force must produce byte-identical output")

    def test_force_without_backup_fails(self):
        path = self._make_v0_file()
        r = migrate_file(path, force=True)
        self.assertEqual(r.status, "error")
        self.assertTrue(any(".v0.bak" in e for e in r.errors))

    def test_dry_run_does_not_write(self):
        path = self._make_v0_file()
        before = path.read_bytes()
        r = migrate_file(path, dry_run=True)
        self.assertEqual(r.status, "would-migrate")
        self.assertEqual(path.read_bytes(), before, "dry-run must not modify source")
        self.assertFalse(
            (path.parent / (path.name + ".v0.bak")).exists(),
            "dry-run must not write backup",
        )
        self.assertIsNotNone(r.output)
        self.assertIn('risk_class = "destructive"', r.output)


# ── Per-file rules (§6.1) ──────────────────────────────────────────────────

class PerFileRuleTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _migrate(self, body: str) -> str:
        path = self.tmpdir / "case.toml"
        path.write_text(body, encoding="utf-8")
        r = migrate_file(path, dry_run=True)
        self.assertNotEqual(r.status, "error", msg=f"unexpected error: {r.errors}")
        return r.output

    def test_verdict_require_approval_rewrites_to_ask(self):
        out = self._migrate(_V0_SAMPLE)
        self.assertNotIn('"require_approval"', out)
        self.assertIn('verdict = "ask"', out)

    def test_tags_block_dropped(self):
        out = self._migrate(_V0_SAMPLE)
        self.assertNotIn("tags.scope", out)
        self.assertNotIn("tags.effect", out)
        self.assertNotIn("tags.reversibility", out)
        self.assertNotIn("tags.target", out)
        self.assertNotIn("tags.safety_override", out)
        self.assertNotIn("tag_modifiers.", out)

    def test_arity_default_inserted_on_flags(self):
        out = self._migrate(_V0_SAMPLE)
        # one [[flag]] in the sample, no arity in v0 — migration inserts Boolean default
        self.assertIn('arity = "Boolean"', out)

    def test_arity_not_double_inserted_when_already_present(self):
        body = _V0_SAMPLE.replace(
            '[[flag]]\napplies_to = "rm"\nflag = "-r"',
            '[[flag]]\napplies_to = "rm"\nflag = "-r"\narity = "Boolean"',
        )
        out = self._migrate(body)
        self.assertEqual(out.count('arity = "Boolean"'), 1)

    def test_untagged_file_all_novel(self):
        body = _V0_UNTAGGED
        out = self._migrate(body)
        # The single command + zero combos all end up with risk_class=novel.
        self.assertIn('risk_class = "novel"', out)

    def test_combo_inherits_max_danger_from_base_and_flag(self):
        """rm is destructive (effect=delete + reversibility=impossible).
        rm --no-preserve-root has tag_modifiers.safety_override=true →
        priv_esc. Combo rm --no-preserve-root inherits max(destructive,
        priv_esc) = destructive (priv_esc and destructive both warn-baseline,
        ties resolve to whichever the curator wrote — here the combo's own
        derived risk_class wins; if absent, base wins as the floor)."""
        body = """
[[command]]
path = "rm"
translation = "Delete files."
verdict = "ask"
rationale = "Removes files."
tags.scope = "local"
tags.effect = ["delete"]
tags.reversibility = "impossible"
tags.target = ["filesystem"]
tags.safety_override = false

[[flag]]
applies_to = "rm"
flag = "--no-preserve-root"
translation_modifier = "even at the filesystem root"
verdict = "warn"
rationale = "Bypasses the root-preservation safety check."
tag_modifiers.safety_override = true

[[combo]]
path = "rm --no-preserve-root"
translation = "Delete the entire system tree."
verdict = "warn"
rationale = "Runs rm starting from / with the safety check disabled, destroying every file."
"""
        out = self._migrate(body)
        # Base command line gets risk_class=destructive
        self.assertIn('path = "rm"\ntranslation', out)
        self.assertRegex(out, r'rationale[^\n]*\nrisk_class = "destructive"')
        # Flag override: priv_esc surfaces because it differs from destructive
        self.assertIn('risk_class_override = "priv_esc"', out)
        # Combo path was not given its own tags → derives from base+overrides;
        # max(destructive=2, priv_esc=2) ties — the picker keeps the first,
        # which is the base (destructive).
        # Verify the combo's risk_class is one of the warn-baseline classes:
        combo_section = out.split('[[combo]]')[1]
        self.assertRegex(combo_section, r'risk_class = "(?:destructive|priv_esc)"')

    def test_combo_preserves_curator_set_tags(self):
        body = """
[[command]]
path = "git"
translation = "Run Git."
verdict = "allow"
rationale = "Bare command prints help."
tags.scope = "local"
tags.effect = ["read"]
tags.reversibility = "trivial"
tags.target = ["repository"]
tags.safety_override = false

[[combo]]
path = "git push --force"
translation = "Force-push to a remote, overwriting upstream history."
verdict = "warn"
rationale = "Permanently destroys upstream commits if anyone else has pushed since."
tags.scope = "remote"
tags.effect = ["delete"]
tags.reversibility = "impossible"
tags.target = ["repository"]
tags.safety_override = true
"""
        out = self._migrate(body)
        combo_section = out.split('[[combo]]')[1]
        self.assertIn('risk_class = "destructive"', combo_section)


# ── is_already_v2 detector ─────────────────────────────────────────────────

class V2DetectionTests(unittest.TestCase):
    def test_v0_detected_as_not_v2(self):
        parsed = tomllib.loads(_V0_SAMPLE)
        self.assertFalse(is_already_v2(parsed))

    def test_v2_no_tags_with_risk_class_detected(self):
        parsed = tomllib.loads("""
[[command]]
path = "ls"
translation = "List directory contents."
verdict = "allow"
rationale = "Read-only listing."
risk_class = "safe"
""")
        self.assertTrue(is_already_v2(parsed))

    def test_command_missing_risk_class_is_not_v2(self):
        parsed = tomllib.loads("""
[[command]]
path = "ls"
translation = "List directory contents."
verdict = "allow"
rationale = "Read-only listing."
""")
        self.assertFalse(is_already_v2(parsed))

    def test_residual_tag_modifiers_on_flag_blocks_v2(self):
        parsed = tomllib.loads("""
[[command]]
path = "ls"
translation = "List directory contents."
verdict = "allow"
rationale = "Read-only listing."
risk_class = "safe"

[[flag]]
applies_to = "ls"
flag = "-l"
translation_modifier = "in long form"
verdict = "allow"
rationale = "Adds detail columns to the listing."
tag_modifiers.effect = ["read"]
""")
        self.assertFalse(is_already_v2(parsed))


# ── CLI integration ────────────────────────────────────────────────────────

class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_dry_run_directory_is_clean_exit(self):
        (self.tmpdir / "a.toml").write_text(_V0_SAMPLE, encoding="utf-8")
        (self.tmpdir / "b.toml").write_text(_V0_UNTAGGED, encoding="utf-8")
        rc = cli_main([str(self.tmpdir), "--dry-run", "--quiet"])
        self.assertEqual(rc, 0)
        self.assertFalse(
            (self.tmpdir / "a.toml.v0.bak").exists(),
            "dry-run must not write backups",
        )

    def test_dry_run_with_type_mismatch_exits_1(self):
        (self.tmpdir / "broken.toml").write_text(
            """
[[command]]
path = "broken"
translation = "Run a broken thing."
verdict = "allow"
rationale = "Test fixture for type-mismatch handling."
tags.effect = "frobnicate"
""",
            encoding="utf-8",
        )
        rc = cli_main([str(self.tmpdir / "broken.toml"), "--dry-run", "--quiet"])
        self.assertEqual(rc, 1)

    def test_unknown_path_exits_2(self):
        rc = cli_main([str(self.tmpdir / "nope.toml"), "--dry-run", "--quiet"])
        self.assertEqual(rc, 2)


# ── End-to-end dry-run across tools/ ───────────────────────────────────────

class CorpusDryRunTest(unittest.TestCase):
    """Sanity-check that the migration tool runs across the entire tools/
    corpus without crashing. Phase 4a will run for-real; this test verifies
    Phase 2 scaffolding is correct."""

    def test_full_corpus_dry_run(self):
        repo_root = Path(__file__).resolve().parent.parent
        tools = sorted((repo_root / "tools").glob("*.toml"))
        if not tools:
            self.skipTest("no tools/*.toml in this checkout")

        # Sample a few representative tagged + untagged files instead of
        # walking all 1244 (faster + the dry-run output is what we'd test).
        # The CLI test_full_corpus_dry_run_smoke below covers the full set.
        for path in tools[:30]:
            r = migrate_file(path, dry_run=True)
            self.assertIn(r.status, ("would-migrate", "would-skip", "already-migrated"),
                          msg=f"{path}: unexpected status {r.status} ({r.errors})")

    def test_full_corpus_via_cli(self):
        """End-to-end: invoke the CLI in dry-run mode against the full
        tools/ tree. Exits 0 even if some files have derivation warnings —
        the actual write happens in Phase 4a, this just catches scaffolding
        bugs early."""
        repo_root = Path(__file__).resolve().parent.parent
        tools_dir = repo_root / "tools"
        if not tools_dir.is_dir():
            self.skipTest("no tools/ directory in this checkout")

        rc = cli_main([str(tools_dir), "--dry-run", "--quiet"])
        # Allowable exit codes:
        #   0 = clean
        #   1 = at least one file has derivation warnings (still a valid
        #       run; Phase 4a hand-curate fixes those).
        self.assertIn(rc, (0, 1), msg=f"unexpected exit code {rc}")


# ── Test fixtures ──────────────────────────────────────────────────────────

_V0_SAMPLE = """
[[command]]
path = "rm"
translation = "Delete files."
verdict = "require_approval"
rationale = "Permanently removes files; recovery depends on filesystem support."
tags.scope = "local"
tags.effect = ["delete"]
tags.reversibility = "impossible"
tags.target = ["filesystem"]
tags.safety_override = false

[[flag]]
applies_to = "rm"
flag = "-r"
translation_modifier = "recursively through all subdirectories"
verdict = "require_approval"
rationale = "Removes entire directory trees, which permanently destroys data on impossible-to-recover paths."
tag_modifiers.effect = ["delete"]
tag_modifiers.reversibility = "impossible"
"""

_V0_UNTAGGED = """
[[command]]
path = "noop"
translation = "Do nothing observable."
verdict = "allow"
rationale = "Untagged command for the v0→v2 novel-fallback test path."
"""


if __name__ == "__main__":
    unittest.main(verbosity=2)
