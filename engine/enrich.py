#!/usr/bin/env python3
"""enrich.py — discover flags from the local system and compare against registry entries.

Usage:
    python engine/enrich.py curl           # single tool
    python engine/enrich.py --all          # every tool in tools/
    python engine/enrich.py --thin         # only tools with 0 flags
    python engine/enrich.py --thin --top 30  # show top 30 results (default 20)
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
TIMEOUT = 5  # seconds for subprocess calls

# Common dev tools get a priority boost so they sort higher when missing-flag
# counts are equal.
IMPORTANT_TOOLS = {
    "git", "docker", "kubectl", "terraform", "aws", "npm", "yarn", "pip",
    "python", "python3", "node", "curl", "wget", "ssh", "scp", "rsync",
    "make", "cmake", "cargo", "go", "rustc", "gcc", "clang", "javac",
    "java", "mvn", "gradle", "ruby", "gem", "bundle", "brew", "apt",
    "yum", "dnf", "pacman", "snap", "flatpak", "systemctl", "journalctl",
    "tar", "zip", "unzip", "gzip", "bzip2", "xz", "zstd", "sed", "awk",
    "grep", "find", "xargs", "sort", "cut", "tr", "wc", "head", "tail",
    "cat", "less", "more", "diff", "patch", "chmod", "chown", "chgrp",
    "cp", "mv", "rm", "mkdir", "rmdir", "ln", "ls", "ps", "kill",
    "top", "htop", "df", "du", "mount", "umount", "fdisk", "lsblk",
    "openssl", "gpg", "base64", "jq", "yq", "helm", "kind", "minikube",
    "podman", "skopeo", "buildah", "nmap", "dig", "nslookup", "ping",
    "traceroute", "netstat", "ss", "ip", "ifconfig", "iptables",
}

# Regex patterns to extract flags from help/man output
FLAG_PATTERNS = [
    # --long-flag, --long-flag=VALUE, --long-flag VALUE
    re.compile(r"(?:^|\s)(-{2}[a-zA-Z][a-zA-Z0-9_-]*)(?:\s|=|,|$)"),
    # -x (single char short flag)
    re.compile(r"(?:^|\s)(-[a-zA-Z0-9])(?:\s|,|$)"),
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ToolReport:
    """Result of enriching a single tool."""
    name: str
    toml_path: Path
    existing_flags: set[str] = field(default_factory=set)
    system_flags: set[str] = field(default_factory=set)
    missing_flags: set[str] = field(default_factory=set)
    source: str = ""  # where we got the flags from
    error: str = ""   # if we could not get flags at all

    @property
    def coverage(self) -> str:
        total = len(self.existing_flags | self.system_flags)
        if total == 0:
            return "0/0"
        return f"{len(self.existing_flags)}/{total}"

    @property
    def priority_score(self) -> int:
        """Higher = needs more work. Used for sorting."""
        missing = len(self.missing_flags)
        importance_bonus = 50 if self.name in IMPORTANT_TOOLS else 0
        return missing + importance_bonus


# ---------------------------------------------------------------------------
# TOML parsing (minimal — avoids external dependency)
# ---------------------------------------------------------------------------

def parse_existing_flags(toml_path: Path) -> set[str]:
    """Extract flag values from a TOML file without a TOML library."""
    flags: set[str] = set()
    try:
        text = toml_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return flags

    for line in text.splitlines():
        line = line.strip()
        # Match:  flag = "--something"  or  flag = "-x"
        m = re.match(r'^flag\s*=\s*"([^"]+)"', line)
        if m:
            flags.add(m.group(1))
    return flags


def count_existing_flags(toml_path: Path) -> int:
    """Quick count of [[flag]] entries."""
    try:
        text = toml_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return 0
    return text.count("[[flag]]")


# ---------------------------------------------------------------------------
# System flag extraction
# ---------------------------------------------------------------------------

def _run(cmd: list[str], timeout: int = TIMEOUT) -> str | None:
    """Run a command and return combined stdout+stderr, or None on failure."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        return output.strip() if output.strip() else None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _has_man_page(tool: str) -> bool:
    """Check if a man page exists (without rendering it)."""
    result = _run(["man", "-w", tool])
    return result is not None and "No manual entry" not in result


def _get_man_text(tool: str) -> str | None:
    """Get the rendered man page text."""
    # Use col -bx to strip backspace formatting from man output
    try:
        man_proc = subprocess.Popen(
            ["man", tool],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        col_proc = subprocess.Popen(
            ["col", "-bx"],
            stdin=man_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        man_proc.stdout.close()
        output, _ = col_proc.communicate(timeout=10)
        text = output.decode("utf-8", errors="replace").strip()
        return text if text else None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _extract_options_section(man_text: str) -> str:
    """Pull out the OPTIONS / FLAGS / DESCRIPTION section from man output."""
    lines = man_text.splitlines()
    capture = False
    captured: list[str] = []
    section_pattern = re.compile(
        r"^[A-Z][A-Z ]{2,}$|^[A-Z][A-Z ]*:$"
    )
    options_pattern = re.compile(
        r"^(?:OPTIONS|FLAGS|COMMAND OPTIONS|GLOBAL OPTIONS)", re.IGNORECASE
    )

    for line in lines:
        stripped = line.strip()
        if options_pattern.match(stripped):
            capture = True
            continue
        if capture:
            # Stop when we hit the next top-level section header
            if section_pattern.match(stripped) and stripped not in (
                "OPTIONS", "FLAGS", "COMMAND OPTIONS", "GLOBAL OPTIONS"
            ):
                break
            captured.append(line)

    return "\n".join(captured) if captured else man_text


def extract_flags_from_text(text: str) -> set[str]:
    """Extract flags from help/man text using regex patterns."""
    flags: set[str] = set()
    for line in text.splitlines():
        for pat in FLAG_PATTERNS:
            for m in pat.finditer(line):
                flag = m.group(1)
                # Filter out noise
                if flag in ("-", "--"):
                    continue
                # Skip things that look like negative numbers
                if re.match(r"^-\d+$", flag):
                    continue
                flags.add(flag)
    return flags


def get_system_flags(tool: str) -> tuple[set[str], str]:
    """Try to get flags from the local system. Returns (flags, source)."""
    # 1. Try man page first
    if _has_man_page(tool):
        man_text = _get_man_text(tool)
        if man_text:
            options_text = _extract_options_section(man_text)
            flags = extract_flags_from_text(options_text)
            if flags:
                return flags, "man"

    # 2. Try --help
    help_text = _run([tool, "--help"])
    if help_text:
        flags = extract_flags_from_text(help_text)
        if flags:
            return flags, "--help"

    # 3. Try -h
    h_text = _run([tool, "-h"])
    if h_text:
        flags = extract_flags_from_text(h_text)
        if flags:
            return flags, "-h"

    return set(), "none"


# ---------------------------------------------------------------------------
# Enrichment logic
# ---------------------------------------------------------------------------

def enrich_tool(tool_name: str) -> ToolReport:
    """Enrich a single tool: compare system flags against registry."""
    toml_path = TOOLS_DIR / f"{tool_name}.toml"
    report = ToolReport(name=tool_name, toml_path=toml_path)

    # Parse existing flags from TOML
    report.existing_flags = parse_existing_flags(toml_path)

    # Get flags from the system
    system_flags, source = get_system_flags(tool_name)
    report.system_flags = system_flags
    report.source = source

    if not system_flags:
        report.error = "Could not retrieve flags (tool may not be installed)"

    # Compute missing = on system but not in registry
    report.missing_flags = report.system_flags - report.existing_flags

    return report


def get_tool_names(mode: str, specific: str | None = None) -> list[str]:
    """Get the list of tool names to process."""
    if specific:
        return [specific]

    names: list[str] = []
    for f in sorted(TOOLS_DIR.glob("*.toml")):
        tool_name = f.stem
        if mode == "thin":
            if count_existing_flags(f) == 0:
                names.append(tool_name)
        else:
            names.append(tool_name)

    return names


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def print_single_report(report: ToolReport) -> None:
    """Print a detailed report for a single tool."""
    print(f"\n{'='*60}")
    print(f"  Tool: {report.name}")
    print(f"  TOML: {report.toml_path}")
    print(f"  Source: {report.source}")
    print(f"  Coverage: {report.coverage} flags documented")
    print(f"{'='*60}")

    if report.error:
        print(f"  WARNING: {report.error}")

    if report.existing_flags:
        print(f"\n  Documented flags ({len(report.existing_flags)}):")
        for f in sorted(report.existing_flags):
            print(f"    {f}")

    if report.missing_flags:
        print(f"\n  MISSING from registry ({len(report.missing_flags)}):")
        for f in sorted(report.missing_flags):
            marker = " ***" if f.startswith("--") else ""
            print(f"    {f}{marker}")
    elif report.system_flags:
        print("\n  All system flags are documented!")

    print()


def print_batch_report(reports: list[ToolReport], top_n: int) -> None:
    """Print a prioritized work queue."""
    # Filter to reports that actually have missing flags
    actionable = [r for r in reports if r.missing_flags]

    # Sort by priority score descending
    actionable.sort(key=lambda r: r.priority_score, reverse=True)

    # Also collect tools where we couldn't get flags
    no_data = [r for r in reports if not r.system_flags and r.error != ""]

    total_tools = len(reports)
    total_actionable = len(actionable)
    total_no_data = len(no_data)
    total_complete = total_tools - total_actionable - total_no_data

    print(f"\n{'='*72}")
    print(f"  ENRICHMENT WORK QUEUE")
    print(f"{'='*72}")
    print(f"  Tools scanned:       {total_tools}")
    print(f"  Fully covered:       {total_complete}")
    print(f"  Need enrichment:     {total_actionable}")
    print(f"  No flag data found:  {total_no_data}")
    print(f"{'='*72}\n")

    if not actionable:
        print("  No tools need enrichment — all flags are documented!\n")
        return

    shown = actionable[:top_n]

    print(f"  Top {len(shown)} tools needing enrichment:\n")
    print(f"  {'Rank':<6}{'Tool':<25}{'Missing':>8}{'Documented':>12}"
          f"{'Source':<10}{'Important':>10}")
    print(f"  {'-'*6}{'-'*25}{'-'*8}{'-'*12}{'-'*10}{'-'*10}")

    for i, r in enumerate(shown, 1):
        important = "  YES" if r.name in IMPORTANT_TOOLS else ""
        print(
            f"  {i:<6}{r.name:<25}"
            f"{len(r.missing_flags):>8}"
            f"{r.coverage:>12}"
            f"  {r.source:<10}"
            f"{important:>8}"
        )

    if len(actionable) > top_n:
        print(f"\n  ... and {len(actionable) - top_n} more tools need work.")

    # Show details for top 5
    print(f"\n{'='*72}")
    print(f"  DETAILS — Top 5 Missing Flags")
    print(f"{'='*72}")

    for r in shown[:5]:
        print(f"\n  {r.name} (missing {len(r.missing_flags)}, "
              f"documented {len(r.existing_flags)}, source: {r.source}):")
        sorted_flags = sorted(r.missing_flags)
        # Show first 20 missing flags
        for f in sorted_flags[:20]:
            print(f"    {f}")
        if len(sorted_flags) > 20:
            print(f"    ... and {len(sorted_flags) - 20} more")

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich registry entries with real flag data from the local system."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("tool", nargs="?", help="Tool name to enrich (e.g. curl)")
    group.add_argument("--all", action="store_true", help="Enrich all tools")
    group.add_argument("--thin", action="store_true",
                       help="Enrich only tools with 0 flags")
    parser.add_argument("--top", type=int, default=20,
                        help="Number of results to show in batch mode (default: 20)")
    args = parser.parse_args()

    if not TOOLS_DIR.is_dir():
        print(f"ERROR: Tools directory not found: {TOOLS_DIR}", file=sys.stderr)
        sys.exit(1)

    # Determine mode
    if args.tool:
        toml_path = TOOLS_DIR / f"{args.tool}.toml"
        if not toml_path.exists():
            print(f"ERROR: No registry entry found: {toml_path}", file=sys.stderr)
            sys.exit(1)
        report = enrich_tool(args.tool)
        print_single_report(report)
    else:
        mode = "thin" if args.thin else "all"
        tool_names = get_tool_names(mode)
        print(f"Scanning {len(tool_names)} tools ({mode} mode)...",
              file=sys.stderr)

        reports: list[ToolReport] = []
        for i, name in enumerate(tool_names):
            if (i + 1) % 50 == 0:
                print(f"  ... {i + 1}/{len(tool_names)}", file=sys.stderr)
            reports.append(enrich_tool(name))

        print(f"  ... done.\n", file=sys.stderr)
        print_batch_report(reports, args.top)


if __name__ == "__main__":
    main()
