#!/usr/bin/env python3
"""Task 1 coverage analyzer.

Walks ~/.claude/projects/**/*.jsonl, extracts every Bash tool-use command,
classifies each unique command against ~/intracept-registry/registry.json
(full / partial / no match), and writes:

  - <repo>/COVERAGE_REPORT.md
  - <repo>/coverage_data.json
  - <repo>/progress-task-1.json   (resumability checkpoints)

The matcher follows the spec in dispatch-notes/prompt-task-1-coverage.md:
greedy longest-prefix on non-flag tokens, alphabetised flag lookup keyed
by (matched_path, flag), and a simple risk ordering.

Designed to be invoked directly with python3; no external deps.
"""

import json
import re
import shlex
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path.home() / "intracept-registry"
REGISTRY_PATH = REPO_ROOT / "registry.json"
PROJECTS_DIR = Path.home() / ".claude" / "projects"
COVERAGE_MD = REPO_ROOT / "COVERAGE_REPORT.md"
COVERAGE_JSON = REPO_ROOT / "coverage_data.json"
COVERAGE_MD_PUBLIC = REPO_ROOT / "COVERAGE_REPORT_PUBLIC.md"
COVERAGE_JSON_PUBLIC = REPO_ROOT / "coverage_data_public.json"
PARTIAL_ALL_JSONL = REPO_ROOT / "partial_all.jsonl"
MISSED_ALL_JSONL = REPO_ROOT / "missed_all.jsonl"
PROGRESS_PATH = REPO_ROOT / "progress-task-1.json"

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3, "unknown": 4}

# Substrings that mark a command as custom internal tooling — excluded from
# the public-facing coverage report so the metric reflects what real users run.
EXCLUDE_PATTERNS = [
    "claude-swarm",
    "/intracept/scripts/",
    "/intracept/target/",
    "./target/release/intracept",
    "./target/debug/intracept",
    "./engine/run.sh",
    "./engine/run-task-",
    "pilot_infra.sh",
]


def is_excluded(cmd: str) -> bool:
    return any(p in cmd for p in EXCLUDE_PATTERNS)


# Patterns for secrets that may have leaked into command history. We never
# want to commit these to the registry repo (push protection blocks it, but
# also they shouldn't be sitting in working-tree files). Matches are replaced
# with a fixed redaction marker.
SECRET_PATTERNS = [
    re.compile(r"sk-ant-api\d{2}-[A-Za-z0-9_\-]{20,}"),       # Anthropic
    re.compile(r"sk-proj-[A-Za-z0-9_\-]{20,}"),                # OpenAI project
    re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),                    # OpenAI legacy
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),             # GitHub PAT/app
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                       # AWS access key
    re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b"),  # JWT
]
REDACTED = "<redacted-secret>"


def redact_secrets(s: str) -> str:
    out = s
    for pat in SECRET_PATTERNS:
        out = pat.sub(REDACTED, out)
    return out


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_progress(stage: str, extra: dict | None = None) -> None:
    payload = {"stage": stage, "ts": now()}
    if extra:
        payload.update(extra)
    PROGRESS_PATH.write_text(json.dumps(payload, indent=2))


def load_registry() -> tuple[dict, dict]:
    if not REGISTRY_PATH.exists():
        sys.exit(f"FATAL: registry index missing at {REGISTRY_PATH}")
    data = json.loads(REGISTRY_PATH.read_text())
    commands = data.get("commands", {}) or {}
    flags_map = data.get("flags", {}) or {}
    flag_index: dict[tuple[str, str], dict] = {}
    for key, entry in flags_map.items():
        applies_to = entry.get("applies_to", "") or ""
        prefix = applies_to + " "
        if applies_to and key.startswith(prefix):
            flag = key[len(prefix):]
            flag_index[(applies_to, flag)] = entry
        else:
            # Best-effort: try splitting on last space
            if " " in key:
                head, tail = key.rsplit(" ", 1)
                flag_index[(applies_to or head, tail)] = entry
    return commands, flag_index


def discover_jsonl() -> list[Path]:
    if not PROJECTS_DIR.exists():
        sys.exit(
            "FATAL: no session logs found.\n"
            f"Searched: {PROJECTS_DIR} (does not exist)"
        )
    files = sorted(PROJECTS_DIR.glob("**/*.jsonl"))
    if not files:
        sys.exit(f"FATAL: no .jsonl files under {PROJECTS_DIR}")
    return files


def collect_bash(obj) -> list[str]:
    """Recursively scan a JSON object for Bash tool_use commands."""
    out: list[str] = []
    if isinstance(obj, dict):
        if obj.get("type") == "tool_use" and obj.get("name") == "Bash":
            inp = obj.get("input") or {}
            cmd = inp.get("command")
            if isinstance(cmd, str) and cmd:
                out.append(cmd)
        for v in obj.values():
            out.extend(collect_bash(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(collect_bash(v))
    return out


def extract(files: list[Path]) -> tuple[Counter, int, int]:
    counter: Counter = Counter()
    malformed = 0
    total_lines = 0
    for fp in files:
        try:
            with fp.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    total_lines += 1
                    try:
                        obj = json.loads(line)
                    except Exception:
                        malformed += 1
                        continue
                    for cmd in collect_bash(obj):
                        counter[cmd] += 1
        except Exception:
            malformed += 1
            continue
    return counter, malformed, total_lines


def tokenize(cmd: str) -> list[str]:
    try:
        return shlex.split(cmd, posix=True)
    except ValueError:
        return cmd.split()


def is_flag(tok: str) -> bool:
    return tok.startswith("-") and tok not in ("-", "--")


def parse_command(toks: list[str]) -> tuple[list[str], list[str]]:
    non_flag, flags = [], []
    for t in toks:
        if is_flag(t):
            base = t.split("=", 1)[0] if "=" in t else t
            flags.append(base)
        else:
            non_flag.append(t)
    return non_flag, flags


def match_path(non_flag: list[str], commands: dict) -> str:
    for i in range(len(non_flag), 0, -1):
        candidate = " ".join(non_flag[:i])
        if candidate in commands:
            return candidate
    return ""


def classify(cmd: str, commands: dict, flag_index: dict) -> tuple[str, str, list[str], list[str]]:
    toks = tokenize(cmd)
    non_flag, flags = parse_command(toks)
    flags_sorted = sorted(flags)
    matched = match_path(non_flag, commands)
    if not matched:
        return ("no_match", "", flags_sorted, [])
    missing = [f for f in flags_sorted if (matched, f) not in flag_index]
    if missing:
        return ("partial_match", matched, flags_sorted, missing)
    return ("full_match", matched, flags_sorted, [])


def first_token(cmd: str) -> str:
    for t in tokenize(cmd):
        if not t.startswith("-"):
            return t
    return ""


def render_md(report: dict, malformed: int, total_lines: int) -> str:
    full = sum(1 for r in report["_status"].values() if r == "full_match")
    partial = sum(1 for r in report["_status"].values() if r == "partial_match")
    miss = sum(1 for r in report["_status"].values() if r == "no_match")
    total_unique = report["total_unique"]
    rates = report["rates"]

    out = []
    out.append("# Coverage Report")
    out.append("")
    out.append(f"Generated: {now()}")
    out.append("")
    out.append(f"- Total unique commands analyzed: **{total_unique}**")
    out.append(f"- Total command invocations: **{report['total_invocations']}**")
    out.append(f"- Hit rate (full match): **{rates['full']:.1%}** ({full} / {total_unique})")
    out.append(f"- Partial rate: **{rates['partial']:.1%}** ({partial} / {total_unique})")
    out.append(f"- Miss rate: **{rates['miss']:.1%}** ({miss} / {total_unique})")
    out.append(f"- JSONL lines scanned: **{total_lines}**")
    out.append(f"- Malformed JSONL lines skipped: **{malformed}**")
    if report.get("excluded_unique") or report.get("excluded_invocations"):
        out.append(
            f"- Excluded as custom internal tooling: "
            f"**{report['excluded_unique']}** unique / "
            f"**{report['excluded_invocations']}** invocations"
        )
    out.append("")
    out.append("## Top 50 missed commands by frequency")
    out.append("")
    if not report["top_50_missed"]:
        out.append("_None — every parsed command path resolved to a registry entry._")
    else:
        out.append("| # | Freq | Command | Parsed path | Flags |")
        out.append("|---|------|---------|-------------|-------|")
        for i, row in enumerate(report["top_50_missed"], 1):
            cmd_disp = row["command"].replace("|", "\\|").replace("\n", " ")
            if len(cmd_disp) > 140:
                cmd_disp = cmd_disp[:137] + "..."
            flags_disp = " ".join(row["parsed_flags"]) or "—"
            path_disp = row["parsed_path"] or "(none)"
            out.append(
                f"| {i} | {row['frequency']} | `{cmd_disp}` | `{path_disp}` | `{flags_disp}` |"
            )
    out.append("")
    out.append("## Top 50 partial-match commands by frequency")
    out.append("")
    if not report["top_50_partial"]:
        out.append("_None._")
    else:
        out.append("| # | Freq | Command | Matched path | Missing flags |")
        out.append("|---|------|---------|--------------|---------------|")
        for i, row in enumerate(report["top_50_partial"], 1):
            cmd_disp = row["command"].replace("|", "\\|").replace("\n", " ")
            if len(cmd_disp) > 140:
                cmd_disp = cmd_disp[:137] + "..."
            missing_disp = " ".join(row["missing_flags"]) or "—"
            out.append(
                f"| {i} | {row['frequency']} | `{cmd_disp}` | `{row['matched_path']}` | `{missing_disp}` |"
            )
    out.append("")
    out.append("## Tools by frequency (top 50)")
    out.append("")
    out.append("| Tool | Invocations |")
    out.append("|------|-------------|")
    for row in report["tools_by_frequency"][:50]:
        out.append(f"| `{row['tool']}` | {row['invocations']} |")
    out.append("")
    return "\n".join(out)


def main() -> None:
    write_progress("start")
    commands, flag_index = load_registry()
    write_progress(
        "registry_loaded",
        {"command_count": len(commands), "flag_count": len(flag_index)},
    )

    files = discover_jsonl()
    write_progress("files_discovered", {"file_count": len(files)})

    counter, malformed, total_lines = extract(files)
    total_invocations = sum(counter.values())
    write_progress(
        "parsing_complete",
        {
            "unique_commands": len(counter),
            "total_invocations": total_invocations,
            "malformed_lines": malformed,
            "total_lines": total_lines,
        },
    )

    def analyze_and_write(
        cnt: Counter,
        md_path: Path,
        json_path: Path,
        excluded_unique: int = 0,
        excluded_invocations: int = 0,
    ) -> tuple[int, int, int]:
        classifications: dict[str, tuple[str, str, list[str], list[str]]] = {}
        for cmd in cnt:
            classifications[cmd] = classify(cmd, commands, flag_index)

        full = [c for c, v in classifications.items() if v[0] == "full_match"]
        partial = [c for c, v in classifications.items() if v[0] == "partial_match"]
        miss = [c for c, v in classifications.items() if v[0] == "no_match"]
        total_unique = len(cnt)

        rates = {
            "full": round(len(full) / total_unique, 6) if total_unique else 0.0,
            "partial": round(len(partial) / total_unique, 6) if total_unique else 0.0,
            "miss": round(len(miss) / total_unique, 6) if total_unique else 0.0,
        }

        miss_sorted = sorted(miss, key=lambda c: (-cnt[c], c))[:50]
        top_50_missed = []
        for cmd in miss_sorted:
            _, mp, fs, _ = classifications[cmd]
            top_50_missed.append(
                {
                    "command": redact_secrets(cmd),
                    "frequency": cnt[cmd],
                    "parsed_path": mp,
                    "parsed_flags": fs,
                }
            )

        partial_sorted = sorted(partial, key=lambda c: (-cnt[c], c))[:50]
        top_50_partial = []
        for cmd in partial_sorted:
            _, mp, _, mf = classifications[cmd]
            top_50_partial.append(
                {
                    "command": redact_secrets(cmd),
                    "frequency": cnt[cmd],
                    "matched_path": mp,
                    "missing_flags": mf,
                }
            )

        tool_counts: Counter = Counter()
        for cmd, freq in cnt.items():
            first = first_token(cmd)
            if first:
                tool_counts[first] += freq

        tools_by_frequency = [
            {"tool": t, "invocations": int(n)}
            for t, n in sorted(tool_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ]

        coverage_data = {
            "total_unique": total_unique,
            "total_invocations": sum(cnt.values()),
            "rates": rates,
            "top_50_missed": top_50_missed,
            "top_50_partial": top_50_partial,
            "tools_by_frequency": tools_by_frequency,
            "excluded_unique": excluded_unique,
            "excluded_invocations": excluded_invocations,
        }
        json_path.write_text(json.dumps(coverage_data, indent=2))

        md_payload = dict(coverage_data)
        md_payload["_status"] = {c: v[0] for c, v in classifications.items()}
        md_path.write_text(render_md(md_payload, malformed, total_lines))

        return len(full), len(partial), len(miss)

    full_n, partial_n, miss_n = analyze_and_write(counter, COVERAGE_MD, COVERAGE_JSON)
    write_progress("matching_complete")

    public_counter = Counter({c: v for c, v in counter.items() if not is_excluded(c)})
    excluded_unique = len(counter) - len(public_counter)
    excluded_invocations = sum(counter.values()) - sum(public_counter.values())
    pub_full, pub_partial, pub_miss = analyze_and_write(
        public_counter,
        COVERAGE_MD_PUBLIC,
        COVERAGE_JSON_PUBLIC,
        excluded_unique=excluded_unique,
        excluded_invocations=excluded_invocations,
    )

    # Dump every partial / missed command from the public set, sorted by
    # descending frequency. Drives registry expansion + parser hardening work.
    with PARTIAL_ALL_JSONL.open("w") as fh, MISSED_ALL_JSONL.open("w") as fm:
        for cmd, freq in sorted(public_counter.items(), key=lambda kv: (-kv[1], kv[0])):
            status, matched, flags, missing = classify(cmd, commands, flag_index)
            if status == "partial_match":
                fh.write(
                    json.dumps(
                        {
                            "command": redact_secrets(cmd),
                            "frequency": freq,
                            "matched_path": matched,
                            "missing_flags": missing,
                            "all_flags": flags,
                        }
                    )
                    + "\n"
                )
            elif status == "no_match":
                fm.write(
                    json.dumps(
                        {
                            "command": redact_secrets(cmd),
                            "frequency": freq,
                            "parsed_flags": flags,
                        }
                    )
                    + "\n"
                )

    write_progress(
        "report_written",
        {
            "coverage_md": str(COVERAGE_MD),
            "coverage_md_public": str(COVERAGE_MD_PUBLIC),
            "full": full_n,
            "partial": partial_n,
            "miss": miss_n,
            "public_full": pub_full,
            "public_partial": pub_partial,
            "public_miss": pub_miss,
        },
    )

    print(
        f"OK unique={len(counter)} invocations={total_invocations} "
        f"full={full_n} partial={partial_n} miss={miss_n} "
        f"malformed={malformed} files={len(files)}"
    )
    print(
        f"PUBLIC unique={len(public_counter)} "
        f"invocations={sum(public_counter.values())} "
        f"full={pub_full} partial={pub_partial} miss={pub_miss} "
        f"excluded_unique={excluded_unique} "
        f"excluded_invocations={excluded_invocations}"
    )


if __name__ == "__main__":
    main()
