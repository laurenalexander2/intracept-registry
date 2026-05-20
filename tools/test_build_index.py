"""Tests for build-index validation (TD-H3): verdict + risk_class value-set checks."""

from pathlib import Path
import textwrap
import importlib.util
import pytest

# tools/build-index.py is hyphenated; import via importlib.
_SPEC = importlib.util.spec_from_file_location(
    "build_index", Path(__file__).parent / "build-index.py"
)
build_index_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(build_index_mod)


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / f"{name}.toml"
    p.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return p


def test_accepts_valid_verdict_and_risk_class(tmp_path):
    _write(tmp_path, "ok", """
        [[command]]
        path = "ok"
        translation = "Test."
        verdict = "allow"
        rationale = "Test rationale."
        risk_class = "safe"
    """)
    index, stats = build_index_mod.build_index(tmp_path)
    assert stats["command_count"] == 1


def test_rejects_unknown_verdict_on_command(tmp_path):
    _write(tmp_path, "bad_cmd_verdict", """
        [[command]]
        path = "bad"
        translation = "Test."
        verdict = "nuke"
        rationale = "Test rationale."
    """)
    with pytest.raises(build_index_mod.ValidationError, match="invalid verdict 'nuke'"):
        build_index_mod.build_index(tmp_path)


def test_rejects_unknown_verdict_on_flag(tmp_path):
    _write(tmp_path, "bad_flag_verdict", """
        [[command]]
        path = "fv"
        translation = "Test."
        verdict = "allow"
        rationale = "Test rationale."

        [[flag]]
        applies_to = "fv"
        flag = "-x"
        translation_modifier = ""
        verdict = "yolo"
        rationale = "Test rationale."
    """)
    with pytest.raises(build_index_mod.ValidationError, match="invalid verdict 'yolo'"):
        build_index_mod.build_index(tmp_path)


def test_rejects_unknown_risk_class(tmp_path):
    _write(tmp_path, "bad_rc", """
        [[command]]
        path = "rc"
        translation = "Test."
        verdict = "allow"
        rationale = "Test rationale."
        risk_class = "extremely_spicy"
    """)
    with pytest.raises(build_index_mod.ValidationError, match="invalid risk_class 'extremely_spicy'"):
        build_index_mod.build_index(tmp_path)


def test_rejects_unknown_risk_class_override(tmp_path):
    _write(tmp_path, "bad_override", """
        [[command]]
        path = "ov"
        translation = "Test."
        verdict = "allow"
        rationale = "Test rationale."

        [[flag]]
        applies_to = "ov"
        flag = "-z"
        translation_modifier = ""
        verdict = "ask"
        rationale = "Test rationale."
        risk_class_override = "doomsday"
    """)
    with pytest.raises(build_index_mod.ValidationError, match="invalid risk_class_override 'doomsday'"):
        build_index_mod.build_index(tmp_path)


def test_accepts_missing_risk_class(tmp_path):
    """risk_class is optional during the v0→v2 transition; absence is not an error here.
    Lint enforces required=True separately for full v2 strictness."""
    _write(tmp_path, "no_rc", """
        [[command]]
        path = "norc"
        translation = "Test."
        verdict = "ask"
        rationale = "Test rationale."
    """)
    index, stats = build_index_mod.build_index(tmp_path)
    assert stats["command_count"] == 1


def test_accepts_v2_locked_verdicts(tmp_path):
    for v in ("allow", "ask", "warn"):
        sub = tmp_path / v
        sub.mkdir()
        _write(sub, f"v_{v}", f"""
            [[command]]
            path = "v_{v}"
            translation = "Test."
            verdict = "{v}"
            rationale = "Test rationale."
        """)
        build_index_mod.build_index(sub)
