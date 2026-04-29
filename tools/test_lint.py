"""Tests for the registry TOML linter."""

from pathlib import Path

import pytest

from lint import lint_file

FIXTURES = Path(__file__).parent / "test_fixtures"


def _errors(issues):
    return [i for i in issues if i.level == "ERROR"]


def _warnings(issues):
    return [i for i in issues if i.level == "WARN"]


# ── A. Schema compliance ─────────────────────────────────────────────────────


class TestSchemaCompliance:
    def test_pass(self):
        issues = lint_file(FIXTURES / "a_pass.toml")
        assert _errors(issues) == []

    def test_fail_bad_risk(self):
        issues = lint_file(FIXTURES / "a_fail.toml")
        errs = _errors(issues)
        msgs = [e.message for e in errs]
        assert any("invalid risk" in m for m in msgs)

    def test_fail_missing_field(self):
        issues = lint_file(FIXTURES / "a_fail.toml")
        errs = _errors(issues)
        msgs = [e.message for e in errs]
        assert any("missing" in m for m in msgs)


# ── B. Reference integrity ───────────────────────────────────────────────────


class TestReferenceIntegrity:
    def test_pass(self):
        issues = lint_file(FIXTURES / "b_pass.toml")
        assert _errors(issues) == []

    def test_fail_orphan_flag(self):
        issues = lint_file(FIXTURES / "b_fail.toml")
        errs = _errors(issues)
        msgs = [e.message for e in errs]
        assert any("does not match any command path" in m for m in msgs)


# ── C. Consistency rules ─────────────────────────────────────────────────────


class TestConsistencyRules:
    def test_pass(self):
        issues = lint_file(FIXTURES / "c_pass.toml")
        warns = _warnings(issues)
        consistency_warns = [w for w in warns if "irreversibility" in w.message or "blast-radius" in w.message]
        assert consistency_warns == []

    def test_fail_low_risk_irreversible(self):
        issues = lint_file(FIXTURES / "c_fail.toml")
        warns = _warnings(issues)
        msgs = [w.message for w in warns]
        assert any("low-risk command has irreversibility" in m for m in msgs)

    def test_fail_critical_no_keywords(self):
        issues = lint_file(FIXTURES / "c_fail.toml")
        warns = _warnings(issues)
        msgs = [w.message for w in warns]
        assert any("critical-risk command lacks" in m for m in msgs)


# ── D. Translation rules ─────────────────────────────────────────────────────


class TestTranslationRules:
    def test_pass(self):
        issues = lint_file(FIXTURES / "d_pass.toml")
        assert _errors(issues) == []

    def test_fail_echoes_command(self):
        issues = lint_file(FIXTURES / "d_fail.toml")
        errs = _errors(issues)
        msgs = [e.message for e in errs]
        assert any("echoes command verbatim" in m for m in msgs)

    def test_fail_no_capital(self):
        issues = lint_file(FIXTURES / "d_fail.toml")
        errs = _errors(issues)
        msgs = [e.message for e in errs]
        assert any("capital letter" in m for m in msgs)

    def test_fail_no_period(self):
        issues = lint_file(FIXTURES / "d_fail.toml")
        errs = _errors(issues)
        msgs = [e.message for e in errs]
        assert any("end with a period" in m for m in msgs)


# ── E. Modifier grammar ──────────────────────────────────────────────────────


class TestModifierGrammar:
    def test_pass(self):
        issues = lint_file(FIXTURES / "e_pass.toml")
        warns = _warnings(issues)
        modifier_warns = [w for w in warns if "translation_modifier" in w.message]
        assert modifier_warns == []

    def test_fail_ends_with_period(self):
        issues = lint_file(FIXTURES / "e_fail.toml")
        warns = _warnings(issues)
        msgs = [w.message for w in warns]
        assert any("should not end with a period" in m for m in msgs)

    def test_fail_starts_capital(self):
        issues = lint_file(FIXTURES / "e_fail.toml")
        warns = _warnings(issues)
        msgs = [w.message for w in warns]
        assert any("should not start with a capital" in m for m in msgs)

    def test_fail_bad_first_word(self):
        issues = lint_file(FIXTURES / "e_fail.toml")
        warns = _warnings(issues)
        msgs = [w.message for w in warns]
        assert any("first word" in m and "gerund" in m for m in msgs)


# ── F. Rationale quality ─────────────────────────────────────────────────────


class TestRationaleQuality:
    def test_pass(self):
        issues = lint_file(FIXTURES / "f_pass.toml")
        warns = _warnings(issues)
        rationale_warns = [w for w in warns if "rationale" in w.message]
        assert rationale_warns == []

    def test_fail_too_short(self):
        issues = lint_file(FIXTURES / "f_fail.toml")
        warns = _warnings(issues)
        msgs = [w.message for w in warns]
        assert any("rationale too short" in m for m in msgs)

    def test_fail_equals_translation(self):
        issues = lint_file(FIXTURES / "f_fail.toml")
        warns = _warnings(issues)
        msgs = [w.message for w in warns]
        assert any("rationale exactly equals translation" in m for m in msgs)


# ── CLI integration ──────────────────────────────────────────────────────────


class TestCLI:
    def test_exit_zero_on_clean(self):
        from lint import main
        rc = main([str(FIXTURES / "a_pass.toml")])
        assert rc == 0

    def test_exit_one_on_errors(self):
        from lint import main
        rc = main([str(FIXTURES / "a_fail.toml")])
        assert rc == 1

    def test_json_output(self, capsys):
        import json
        from lint import main
        main(["--json", str(FIXTURES / "a_pass.toml")])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "summary" in data
        assert data["summary"]["errors"] == 0

    def test_quiet_no_output_on_success(self, capsys):
        from lint import main
        rc = main(["--quiet", str(FIXTURES / "a_pass.toml")])
        out = capsys.readouterr().out
        assert rc == 0
        assert out == ""
