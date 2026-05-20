"""Tests for the v2 lint rules — verdict (allow/ask/warn), risk_class enum,
v0 multi-axis tag deprecation, combo risk_class derivation.

Inline tmp_path fixtures (no test_fixtures/ dependency).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import lint
from lint import lint_file


def _write(tmp_path: Path, contents: str) -> Path:
    p = tmp_path / "t.toml"
    p.write_text(contents, encoding="utf-8")
    return p


def _errors(issues):
    return [i for i in issues if i.level == "ERROR"]


def _warnings(issues):
    return [i for i in issues if i.level == "WARN"]


def _msgs(issues):
    return [i.message for i in issues]


# Minimal v2-shape fixtures: a [[command]] with risk_class + v2 verdict.
V2_OK = """
[[command]]
path = "demo"
translation = "Run the demo command."
verdict = "allow"
rationale = "Read-only operation that observes a state and returns it to the caller."
risk_class = "safe"
"""


# ── Verdict (v2) ─────────────────────────────────────────────────────────────

class TestVerdictV2:
    def test_v2_verdicts_pass(self, tmp_path):
        # Use an ask/warn-shaped rationale (with blast-radius keywords) so the
        # C-rule "lacks irreversibility/blast-radius" warning doesn't false-positive.
        rationale = "Permanently destroys all matching records with no recovery mechanism in place after the call."
        for verdict in ("allow", "ask", "warn"):
            toml = (
                V2_OK
                .replace('verdict = "allow"', f'verdict = "{verdict}"')
                .replace(
                    'rationale = "Read-only operation that observes a state and returns it to the caller."',
                    f'rationale = "{rationale}"',
                )
            )
            # Use a benign rationale for allow so the inverse C-rule doesn't false-positive.
            if verdict == "allow":
                toml = toml.replace(rationale,
                    "Read-only operation that observes the working tree without modifying it.")
            f = _write(tmp_path, toml)
            issues = lint_file(f)
            # Only test that the verdict VALUE itself is accepted; rationale-quality
            # warnings (the C-rule) are checked elsewhere.
            verdict_value_issues = [
                i for i in issues
                if "invalid verdict" in i.message or "v0 verdict" in i.message
            ]
            assert not verdict_value_issues, (
                f"verdict={verdict} unexpectedly raised: "
                f"{[i.message for i in verdict_value_issues]}"
            )

    def test_v0_alias_require_approval_warns(self, tmp_path):
        f = _write(tmp_path, V2_OK.replace('verdict = "allow"', 'verdict = "require_approval"'))
        issues = lint_file(f)
        warns = _warnings(issues)
        assert any("v0 verdict 'require_approval'" in m for m in _msgs(warns))
        # And NOT an ERROR
        errs = _errors(issues)
        assert not any("verdict" in m and "invalid" in m for m in _msgs(errs))

    def test_invalid_verdict_errors(self, tmp_path):
        f = _write(tmp_path, V2_OK.replace('verdict = "allow"', 'verdict = "deny"'))
        issues = lint_file(f)
        errs = _errors(issues)
        assert any("invalid verdict 'deny'" in m for m in _msgs(errs))


# ── Risk class (v2) ──────────────────────────────────────────────────────────

class TestRiskClass:
    def test_risk_class_present_passes(self, tmp_path):
        f = _write(tmp_path, V2_OK)
        issues = lint_file(f)
        rc_issues = [i for i in issues if "risk_class" in i.message]
        assert rc_issues == []

    def test_missing_risk_class_warns_transitional(self, tmp_path):
        # V2_OK without the risk_class line.
        toml = V2_OK.replace('risk_class = "safe"', '').strip() + "\n"
        f = _write(tmp_path, toml)
        issues = lint_file(f)
        warns = _warnings(issues)
        assert any("missing risk_class" in m for m in _msgs(warns))

    @pytest.mark.parametrize("rc", list(lint.VALID_RISK_CLASSES))
    def test_each_valid_risk_class_passes(self, tmp_path, rc):
        f = _write(tmp_path, V2_OK.replace('risk_class = "safe"', f'risk_class = "{rc}"'))
        issues = lint_file(f)
        errs = [e for e in _errors(issues) if "risk_class" in e.message]
        assert errs == [], f"valid risk_class {rc} flagged as error"

    def test_invalid_risk_class_errors(self, tmp_path):
        f = _write(tmp_path, V2_OK.replace('risk_class = "safe"', 'risk_class = "dangerous"'))
        issues = lint_file(f)
        errs = _errors(issues)
        assert any("invalid risk_class 'dangerous'" in m for m in _msgs(errs))


# ── v0 multi-axis tag deprecation ────────────────────────────────────────────

V0_WITH_TAGS = """
[[command]]
path = "rm-demo"
translation = "Remove a demo file."
verdict = "require_approval"
rationale = "Permanently deletes a named file with no built-in recovery mechanism."
tags.scope = "local"
tags.effect = ["delete"]
tags.reversibility = "difficult"
tags.target = ["filesystem"]
tags.safety_override = false
"""


class TestV0TagDeprecation:
    def test_v0_tags_warns_on_command(self, tmp_path):
        f = _write(tmp_path, V0_WITH_TAGS)
        issues = lint_file(f)
        warns = _msgs(_warnings(issues))
        # Single summary issue; mentions all five axes.
        deprecation = [m for m in warns if "v0 tags." in m]
        assert len(deprecation) == 1
        for axis in ("scope", "effect", "reversibility", "target", "safety_override"):
            assert axis in deprecation[0]

    def test_v0_tag_modifiers_warns_on_flag(self, tmp_path):
        toml = V0_WITH_TAGS + """
[[flag]]
applies_to = "rm-demo"
flag = "-r"
translation_modifier = "recursively through subdirectories"
verdict = "require_approval"
rationale = "Recursive removal increases the blast radius significantly."
tag_modifiers.reversibility = "impossible"
"""
        f = _write(tmp_path, toml)
        issues = lint_file(f)
        warns = _msgs(_warnings(issues))
        flag_dep = [m for m in warns if "v0 tag_modifiers." in m]
        assert len(flag_dep) == 1
        assert "reversibility" in flag_dep[0]

    def test_v2_clean_file_no_deprecation(self, tmp_path):
        f = _write(tmp_path, V2_OK)
        issues = lint_file(f)
        warns = _msgs(_warnings(issues))
        assert not any("v0 tags." in m or "v0 tag_modifiers." in m for m in warns)


# ── Combo risk_class derivation ──────────────────────────────────────────────

COMBO_BASE = """
[[command]]
path = "rm-demo"
translation = "Remove a demo file."
verdict = "ask"
rationale = "Permanently deletes a named file; recoverable only with backups in place."
risk_class = "destructive"

[[flag]]
applies_to = "rm-demo"
flag = "-f"
translation_modifier = "without confirmation"
verdict = "ask"
rationale = "Suppresses confirmation prompts which removes the recovery prompt that protects against typos."
risk_class_override = "destructive"
"""


class TestComboDerivation:
    def test_combo_at_base_rank_passes(self, tmp_path):
        toml = COMBO_BASE + """
[[combo]]
path = "rm-demo -f"
translation = "Force-delete a demo file without prompts."
verdict = "warn"
rationale = "Permanently destroys the named file with no confirmation step or recovery mechanism in place."
risk_class = "destructive"
"""
        f = _write(tmp_path, toml)
        issues = lint_file(f)
        derivation = [m for m in _msgs(_errors(issues)) if "less dangerous than derived" in m]
        assert derivation == []

    def test_combo_below_base_rank_errors(self, tmp_path):
        toml = COMBO_BASE + """
[[combo]]
path = "rm-demo -f"
translation = "Force-delete a demo file without prompts."
verdict = "warn"
rationale = "Permanently destroys the named file with no confirmation step or recovery mechanism in place."
risk_class = "safe"
"""
        f = _write(tmp_path, toml)
        issues = lint_file(f)
        errs = _msgs(_errors(issues))
        assert any("less dangerous than derived" in m for m in errs)

    def test_combo_above_base_rank_passes(self, tmp_path):
        # Base safe + flag override destructive: combo claims destructive — fine.
        toml = """
[[command]]
path = "ls-demo"
translation = "List demo files."
verdict = "allow"
rationale = "Read-only enumeration with no side effects on disk or network."
risk_class = "safe"

[[flag]]
applies_to = "ls-demo"
flag = "--bomb"
translation_modifier = "exploding everything"
verdict = "warn"
rationale = "Hypothetical destructive flag for fixture purposes; permanently destroys the listed entries."
risk_class_override = "destructive"

[[combo]]
path = "ls-demo --bomb"
translation = "List entries while exploding them."
verdict = "warn"
rationale = "Permanently destroys every listed entry with no confirmation step in place."
risk_class = "destructive"
"""
        f = _write(tmp_path, toml)
        issues = lint_file(f)
        derivation = [m for m in _msgs(_errors(issues)) if "less dangerous than derived" in m]
        assert derivation == []


# ── Flag risk_class_override ─────────────────────────────────────────────────

class TestFlagRiskClassOverride:
    def test_invalid_override_errors(self, tmp_path):
        toml = V2_OK + """
[[flag]]
applies_to = "demo"
flag = "-x"
translation_modifier = "doing something"
verdict = "ask"
rationale = "Some hypothetical flag whose override is malformed for the test fixture purposes."
risk_class_override = "ultra_destructive"
"""
        f = _write(tmp_path, toml)
        issues = lint_file(f)
        errs = _msgs(_errors(issues))
        assert any("invalid risk_class_override 'ultra_destructive'" in m for m in errs)

    def test_valid_override_passes(self, tmp_path):
        toml = V2_OK + """
[[flag]]
applies_to = "demo"
flag = "-x"
translation_modifier = "doing something"
verdict = "warn"
rationale = "Hypothetical flag elevating the base safe command to destructive; covered for fixture testing."
risk_class_override = "destructive"
"""
        f = _write(tmp_path, toml)
        issues = lint_file(f)
        errs = [m for m in _msgs(_errors(issues)) if "risk_class_override" in m]
        assert errs == []


# ── STRICT_V2 mode flip ──────────────────────────────────────────────────────

class TestStrictMode:
    def test_strict_v2_promotes_warns_to_errors(self, tmp_path, monkeypatch):
        """Phase 4a flip: STRICT_V2=True should make v0 patterns ERRORs, not WARNs."""
        monkeypatch.setattr(lint, "STRICT_V2", True)
        f = _write(tmp_path, V0_WITH_TAGS)
        issues = lint_file(f)
        errs = _msgs(_errors(issues))
        # Multi-axis tag deprecation now an ERROR.
        assert any("v0 tags." in m for m in errs)
        # require_approval verdict alias now an ERROR.
        assert any("v0 verdict 'require_approval'" in m for m in errs)
        # Missing risk_class now an ERROR.
        assert any("missing risk_class" in m for m in errs)
