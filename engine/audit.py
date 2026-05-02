#!/usr/bin/env python3
"""Quality auditor for intracept-registry TOML files.

Scans every tools/*.toml file and flags:
1. Thin entries — tools with 0 flags that should have them
2. Jargon in translations — technical terms a junior dev wouldn't know
3. Weak translations — vague, tautological, or too-technical descriptions
4. Verdict calibration suspects — verdicts that look wrong
5. Combo auditing — jargon and weak translation checks on combos
6. Thin combo candidates — commands with flags but no combos
7. Tag calibration — cross-check tags vs translation text

Outputs a JSON report to stdout, followed by a human-readable summary
to stderr.
"""

import json
import re
import sys
import tomllib
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"

# ── 1. Thin entry classification ────────────────────────────────────────────

HIGH_PRIORITY_TOOLS = {
    # File operations
    "grep", "find", "chmod", "chown", "cp", "mv", "mkdir", "cat", "head",
    "tail", "sort", "uniq", "wc", "cut", "paste", "sed", "awk", "tr",
    "tee", "xargs", "file", "touch", "ln", "readlink", "basename",
    "dirname", "realpath", "install",
    # Archiving / compression
    "tar", "zip", "unzip", "gzip", "gunzip", "bzip2", "xz", "zcat",
    # Networking
    "ssh", "scp", "rsync", "wget", "curl", "ping", "netstat", "ss",
    "dig", "nslookup", "traceroute", "ifconfig", "ip", "nc", "nmap",
    "telnet", "ftp", "sftp", "host",
    # Process / system
    "ps", "kill", "killall", "pkill", "top", "htop", "nice", "renice",
    "nohup", "bg", "fg", "jobs", "wait", "lsof", "strace", "ltrace",
    # Disk / filesystem
    "df", "du", "mount", "umount", "fdisk", "mkfs", "fsck", "lsblk",
    "blkid",
    # User / permissions
    "crontab", "sudo", "su", "chroot", "useradd", "userdel", "usermod",
    "groupadd", "groupdel", "passwd", "id", "whoami", "who", "w",
    # Development
    "make", "gcc", "g++", "cc", "ld", "ar", "nm", "objdump", "strip",
    "python3", "python", "pip", "pip3", "node", "npm", "npx", "yarn",
    "ruby", "gem", "java", "javac", "mvn", "gradle",
    "go", "cargo", "rustc",
    # Shell / misc
    "echo", "printf", "test", "expr", "bc", "date", "cal", "sleep",
    "watch", "time", "timeout", "env", "export", "source", "eval",
    "alias", "unalias", "history", "man", "less", "more", "diff",
    "patch", "strings", "hexdump", "od", "dd",
    # Version control
    "git", "svn", "hg",
    # Containers / cloud
    "docker", "kubectl", "helm", "terraform", "aws", "gcloud", "az",
    "podman", "vagrant",
}

MEDIUM_PRIORITY_TOOLS = {
    "screen", "tmux", "vim", "vi", "nano", "emacs",
    "systemctl", "journalctl", "service", "launchctl",
    "brew", "apt", "apt-get", "yum", "dnf", "pacman", "snap", "flatpak",
    "openssl", "gpg", "ssh-keygen", "ssh-agent", "ssh-add",
    "iptables", "ufw", "firewalld",
    "cron", "at", "batch",
    "ldd", "file", "stat", "uptime", "hostname", "uname", "arch",
    "dmesg", "sysctl", "modprobe", "insmod", "rmmod",
    "mdls", "mdfind", "defaults", "open", "pbcopy", "pbpaste",
    "xdg-open", "xclip", "xsel",
    "sqlite3", "psql", "mysql", "redis-cli", "mongo", "mongosh",
    "jq", "yq", "xmllint", "csvtool",
    "ffmpeg", "convert", "magick", "exiftool",
    "pandoc", "latex", "pdflatex",
    "cmake", "ninja", "meson", "autoconf", "automake",
    "lldb", "gdb", "valgrind",
    "perl", "php", "lua", "swift", "swiftc", "clang", "clang++",
    "dotnet", "nuget",
    "sshfs", "fusermount",
    "column", "comm", "csplit", "expand", "fold", "fmt", "join",
    "nl", "numfmt", "pr", "rev", "shuf", "split", "tsort",
    "unexpand", "yes",
}

# ── 2. Jargon detection ────────────────────────────────────────────────────

JARGON_WORDS = [
    r"\bdaemon(?:s)?\b",
    r"\bsocket(?:s)?\b",
    r"\binode(?:s)?\b",
    r"\bsymlink(?:s)?\b",
    r"\bFIFO\b",
    r"\bmutex(?:es)?\b",
    r"\bsemaphore(?:s)?\b",
    r"\bSIGTERM\b",
    r"\bSIGKILL\b",
    r"\bSIGHUP\b",
    r"\bSIGINT\b",
    r"\bSIGUSR[12]\b",
    r"\bSIGSTOP\b",
    r"\bSIGCONT\b",
    r"\bPOSIX\b",
    r"\bsyscall(?:s)?\b",
    r"\bTTY\b",
    r"\bPTY\b",
    r"\bSUID\b",
    r"\bSGID\b",
    r"\bumask\b",
    r"\bepoll\b",
    r"\bkqueue\b",
    r"\bfile descriptor(?:s)?\b",
    r"\bnamespace(?:s)?\b",
    r"\bcgroup(?:s)?\b",
    r"\brlimit\b",
    r"\bulimit\b",
    r"\bELF\b",
    r"\bMach-O\b",
    r"\bdylib\b",
    r"\bshared object(?:s)?\b",
    r"\bstdin\b",
    r"\bstdout\b",
    r"\bstderr\b",
    r"\bregexp\b",
    r"\bchroot\b",
    r"\bsetuid\b",
    r"\bsetgid\b",
    r"\bXattr(?:s)?\b",
]

# Acronyms considered acceptable in context.
OK_ACRONYMS = {
    # Networking / protocols
    "HTTP", "HTTPS", "URL", "API", "DNS", "IP", "TCP", "UDP", "SSH",
    "TLS", "SSL", "FTP", "SFTP", "SCP", "SMTP", "IMAP", "POP",
    "LAN", "WAN", "VPN", "MAC", "DHCP", "ARP", "ICMP", "NAT", "CIDR",
    "SNMP", "MIB", "OID", "LLDP", "BGP", "OSPF", "NDP", "SPF",
    "BSSID", "SSID", "NFC", "GPS",
    # Data formats
    "JSON", "XML", "YAML", "TOML", "CSV", "HTML", "CSS", "SQL",
    "PDF", "PNG", "JPG", "JPEG", "GIF", "SVG", "TIFF", "BMP",
    "HEIC", "HEIF", "MP3", "MP4", "WAV", "AAC", "FLAC", "AIFF",
    "ZIP", "TAR", "XZ", "GZ",
    # Crypto / security
    "GPG", "PGP", "RSA", "AES", "SHA", "MD5", "JWT", "HMAC",
    "PEM", "DER", "PKCS", "CA", "SSO", "SSE", "KMS",
    "CORS", "CSRF", "XSS", "CRL", "OCSP", "CSR",
    "OTP", "TOTP", "HOTP", "PIN",
    # Identifiers
    "UUID", "UID", "GID", "PID", "ID",
    # System / hardware
    "CPU", "GPU", "RAM", "USB", "SSD", "HDD", "IO", "ABI",
    "OS", "VM", "EOF", "OCI",
    "KB", "MB", "GB", "TB", "PB", "GHz", "MHz",
    "ANSI", "IEEE", "ASCII", "UTF",
    "NVRAM", "MBR", "GPT", "TRIM",
    # Cloud / infrastructure
    "AWS", "GCP", "IAM", "ARN", "VPC", "ECS", "EKS", "ECR",
    "RDS", "SNS", "SQS", "GKE", "AAD", "EBS",
    "CDN", "URI", "URN", "QR",
    # Development
    "IDE", "CI", "CD", "CLI", "GUI", "SDK", "NDK",
    "JDK", "JRE", "JVM", "GCC", "LLVM", "ARM",
    "NPM", "PIP", "ORM", "MVC", "REST", "GRPC", "RPC",
    "CGI", "WSGI", "ASGI", "RBAC", "CRD",
    "GIT", "GNU", "MIT", "BSD",
    "PR", "MR",
    # Apple / platform
    "APFS", "HFS", "XPC", "SIP",
    "LLDB", "GDB", "DSYM",
    "IPA", "DMG", "PKG", "CUPS",
    "SMB", "AFP", "MDM", "DEP", "SCEP",
    # Common abbreviations and tool/domain-specific terms
    "RGB", "HEX", "ISO", "RFC", "UTC", "GMT",
    "NFS", "LDAP", "SAML", "ACL", "ACE",
    "WWDC",
    # SQL keywords in translations
    "DROP", "CREATE", "ALTER", "SELECT", "INSERT", "UPDATE", "DELETE",
    # Domain-specific that appear often in this codebase
    "LFS", "WAL", "PO", "ASP", "DB", "AI", "ML",
    "AVB", "PPD", "PAR", "DBI", "USD",
    "BSM", "ASA", "NET", "IPC",
}

ACRONYM_RE = re.compile(r"\b([A-Z]{2,6})\b")


def find_jargon(text: str) -> list[str]:
    """Return list of jargon terms found in text."""
    found = []
    for pattern in JARGON_WORDS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            found.extend(matches)
    for m in ACRONYM_RE.finditer(text):
        acr = m.group(1)
        if acr not in OK_ACRONYMS and acr not in found:
            found.append(acr)
    return found


# ── 3. Weak translation detection ──────────────────────────────────────────

VAGUE_PATTERNS = [
    (r"^Run a utility\.$", "too vague: 'Run a utility'"),
    (r"^Execute a command\.$", "too vague: 'Execute a command'"),
    (r"^Run a tool\.$", "too vague: 'Run a tool'"),
    (r"^Perform an? (?:action|operation)\.$", "too vague: generic action"),
    (r"^A .+ utility\.$", "describes what it IS, not what it DOES"),
    (r"^A .+ tool\.$", "describes what it IS, not what it DOES"),
    (r"^An? .+ program\.$", "describes what it IS, not what it DOES"),
    (r"^The .+ command\.$", "describes what it IS, not what it DOES"),
]

MECHANISM_WORDS = [
    r"\binvoke(?:s)?\b",
    r"\bspawn(?:s)?\b",
    r"\binstantiate(?:s)?\b",
    r"\btrigger(?:s)? (?:a|the) \w+ (?:routine|function|subroutine|procedure)\b",
    r"\bcall(?:s)? the \w+ (?:API|interface|subsystem)\b",
]


def check_weak_translation(path: str, translation: str) -> list[str]:
    """Return list of weakness descriptions for a translation."""
    issues = []

    for pattern, reason in VAGUE_PATTERNS:
        if re.match(pattern, translation, re.IGNORECASE):
            issues.append(reason)

    # Tautological: just restating the command name
    tool_name = path.split()[-1].lower()
    t_lower = translation.lower()
    if re.match(
        rf"^(?:run|execute|invoke|use) (?:the )?{re.escape(tool_name)}(?:\s+command)?\.?$",
        t_lower,
    ):
        issues.append(f"tautological: just restates the command name '{tool_name}'")

    # Too short (under 15 chars) and not a well-known pattern
    if len(translation) < 15 and not translation.startswith("Run the "):
        issues.append(f"suspiciously short ({len(translation)} chars)")

    # Mechanism words
    for pattern in MECHANISM_WORDS:
        if re.search(pattern, translation, re.IGNORECASE):
            issues.append(f"uses mechanism language (matched: {pattern})")

    # Missing context: translations that say nothing specific
    generic_verbs = re.match(
        r"^(?:Run|Execute|Start|Launch|Invoke|Use|Call|Perform|Do)\s+(?:a|an|the)\s+\w+\.$",
        translation,
    )
    if generic_verbs and len(translation) < 40:
        issues.append("very generic -- what does this tool actually DO for a human?")

    return issues


# ── 4. Verdict calibration checks ──────────────────────────────────────────

# Strongly destructive verbs -- not "remove from a list"
DESTRUCTIVE_WORDS = re.compile(
    r"\b(?:delet(?:e|es|ing)|destroy(?:s|ing|ed)?|eras(?:e|es|ing)|"
    r"wip(?:e|es|ing)|purg(?:e|es|ing)|nuk(?:e|es|ing)|"
    r"kill(?:s|ing|ed)?|terminat(?:e|es|ing))\b",
    re.IGNORECASE,
)
# Softer removal terms
SOFT_REMOVE = re.compile(
    r"\b(?:remov(?:e|es|ing)|uninstall(?:s|ing|ed)?|unlink(?:s|ing|ed)?|"
    r"untap(?:s|ping|ped)?|unregist|unset|unlock|detach|disconnect|"
    r"disassociat|dissociat|drop(?:s|ping|ped)?)\b",
    re.IGNORECASE,
)
# Contexts that elevate soft-remove to genuine data risk
DESTRUCTIVE_CONTEXT = re.compile(
    r"\b(?:permanent|irrevers|cannot be|no.+recov|data.+loss|"
    r"all.+(?:files|data|objects|volumes|containers)|"
    r"directory tree|filesystem|entire)\b",
    re.IGNORECASE,
)

READONLY_WORDS = re.compile(
    r"\b(?:list|show|display|print|view|inspect|describe|dump)\b",
    re.IGNORECASE,
)
# State-changing verbs that mean a command is NOT purely read-only
STATE_CHANGING = re.compile(
    r"\b(?:modif|edit|repair|reset|updat|upgrad|creat|set|configur|"
    r"chang|writ|remov|delet|replac|overwrite|manag|add|assign|"
    r"install|eras|destroy|format|partition|evict|drain)\b",
    re.IGNORECASE,
)

# Only long-form force flags
FORCE_FLAGS_EXACT = {
    "--force", "--force-with-lease", "--no-verify", "--no-check",
    "--skip-verify", "--no-confirm", "--no-prompt",
}
# Short flags that might mean "force" -- confirmed via modifier/rationale
# using strict force-specific language (not just "overwrite" which is
# common for file-output flags like -f meaning "file").
FORCE_SHORT_AMBIGUOUS = {"-f", "-y", "--yes"}
FORCE_CONFIRM_RE = re.compile(
    r"\b(?:force|bypass|skip|suppress|without asking|without confirm|"
    r"no.?confirm|no.?prompt)\b",
    re.IGNORECASE,
)

DRYRUN_FLAGS = {
    "--dry-run", "--dryrun", "--simulate", "--noop",
    "--what-if", "--pretend",
}

DRYRUN_CONFIRM_RE = re.compile(
    r"\b(?:simulat|dry.?run|preview|without actually|no.+change|nothing is|"
    r"verif|confirm|prompt)\b",
    re.IGNORECASE,
)


def check_verdict_calibration(entry_type: str, entry: dict) -> list[str]:
    """Check if an entry's verdict seems miscalibrated."""
    issues = []
    verdict = entry.get("verdict", "unknown")
    translation = entry.get("translation", "")
    modifier = entry.get("translation_modifier", "")
    flag_name = entry.get("flag", "")
    rationale = entry.get("rationale", "")
    path = entry.get("path", entry.get("applies_to", ""))

    if entry_type == "command":
        # Destructive commands should be require_approval
        if DESTRUCTIVE_WORDS.search(translation) and verdict == "allow":
            bare_cmd = path.split()[-1] if path else ""
            # rm bare is calibrated as allow in SCHEMA.md; tr "delete chars"
            # is text processing, not file destruction
            if bare_cmd not in ("rm", "tr"):
                issues.append(
                    f"translation uses destructive language but verdict is 'allow' "
                    f"(expected 'require_approval')"
                )

        # Soft-remove commands with destructive context should be require_approval
        if SOFT_REMOVE.search(translation) and verdict == "allow":
            combined = f"{translation} {rationale}"
            if DESTRUCTIVE_CONTEXT.search(combined):
                issues.append(
                    f"translation describes removal with destructive context "
                    f"but verdict is 'allow' (expected 'require_approval')"
                )

        # Read-only commands should be allow
        if READONLY_WORDS.search(translation) and verdict == "require_approval":
            if not STATE_CHANGING.search(translation):
                issues.append(
                    f"translation suggests read-only operation but verdict is "
                    f"'require_approval' (expected 'allow')"
                )

    elif entry_type == "flag":
        flag_lower = flag_name.lower()

        # Force flags should be require_approval
        if flag_lower in FORCE_FLAGS_EXACT:
            if verdict == "allow":
                issues.append(
                    f"'{flag_name}' bypasses a safety check but verdict is 'allow' "
                    f"(expected 'require_approval')"
                )

        # Ambiguous short force flags: require strict force-specific language
        if flag_lower in FORCE_SHORT_AMBIGUOUS:
            combined = f"{modifier} {rationale}"
            if FORCE_CONFIRM_RE.search(combined) and verdict == "allow":
                issues.append(
                    f"'{flag_name}' appears to bypass a safety check but "
                    f"verdict is 'allow' (expected 'require_approval')"
                )

        # --dry-run should be allow
        if flag_lower in DRYRUN_FLAGS:
            if verdict != "allow":
                issues.append(
                    f"'{flag_name}' is a dry-run/simulation flag but verdict is "
                    f"'{verdict}' (expected 'allow')"
                )

        # Modifier mentions destruction but verdict is allow
        if DESTRUCTIVE_WORDS.search(modifier) and verdict == "allow":
            if not DRYRUN_CONFIRM_RE.search(modifier):
                issues.append(
                    f"modifier uses destructive language but verdict is 'allow' "
                    f"(expected 'require_approval')"
                )

    return issues


# ── 5. Tag calibration checks ─────────────────────────────────────────────

TAG_DELETE_RE = re.compile(
    r"\b(?:delet(?:e|es|ing)|destroy(?:s|ing|ed)?|remov(?:e|es|ing)|"
    r"eras(?:e|es|ing)|wip(?:e|es|ing)|purg(?:e|es|ing)|drop(?:s|ping|ped)?)\b",
    re.IGNORECASE,
)
TAG_READ_RE = re.compile(
    r"\b(?:read(?:s|ing)?|list(?:s|ing)?|show(?:s|ing)?|display(?:s|ing)?|"
    r"view(?:s|ing)?|inspect(?:s|ing)?|print(?:s|ing)?|dump(?:s|ing)?)\b",
    re.IGNORECASE,
)
TAG_REMOTE_RE = re.compile(
    r"\b(?:remote|server|cloud|upload|download|push|pull|fetch|deploy)\b",
    re.IGNORECASE,
)


def check_tag_calibration(entry_type: str, entry: dict) -> list[str]:
    """Cross-check tags vs translation text for consistency."""
    issues = []
    translation = entry.get("translation", "")
    if entry_type == "flag":
        translation = entry.get("translation_modifier", "")

    # Determine tag prefix
    prefix = "tags" if entry_type in ("command", "combo") else "tag_modifiers"

    effect = entry.get(f"{prefix}.effect")
    scope = entry.get(f"{prefix}.scope")

    # Normalize effect to a list
    if effect is None:
        return issues
    effect_list = effect if isinstance(effect, list) else [effect]

    # Translation says delete/remove but effect missing "delete"
    if TAG_DELETE_RE.search(translation) and "delete" not in effect_list:
        issues.append(
            f"translation mentions deletion/removal but {prefix}.effect "
            f"does not include 'delete'"
        )

    # Translation says read/list/show but effect missing "read"
    if TAG_READ_RE.search(translation) and "read" not in effect_list:
        issues.append(
            f"translation mentions read/list/show but {prefix}.effect "
            f"does not include 'read'"
        )

    # Translation says remote/server/cloud but scope is "local"
    if scope == "local" and TAG_REMOTE_RE.search(translation):
        issues.append(
            f"translation mentions remote/server/cloud but {prefix}.scope "
            f"is 'local'"
        )

    return issues


# ── Main scan ───────────────────────────────────────────────────────────────

def audit_file(filepath: Path) -> dict:
    """Audit a single TOML file. Returns dict of findings by category."""
    findings = {
        "thin_entries": [],
        "jargon": [],
        "weak_translations": [],
        "verdict_suspects": [],
        "thin_combos": [],
        "tag_suspects": [],
    }

    try:
        with open(filepath, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        findings["parse_errors"] = [str(e)]
        return findings

    commands = data.get("command", [])
    flags = data.get("flag", [])
    combos = data.get("combo", [])
    tool_name = filepath.stem

    # 1. Thin entry check
    if len(flags) == 0 and len(commands) > 0:
        if tool_name in HIGH_PRIORITY_TOOLS:
            priority = "HIGH"
        elif tool_name in MEDIUM_PRIORITY_TOOLS:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        findings["thin_entries"].append({
            "tool": tool_name,
            "commands": len(commands),
            "priority": priority,
        })

    # 2 & 3 & 4: Check each command
    for cmd in commands:
        path = cmd.get("path", "")
        translation = cmd.get("translation", "")

        jargon = find_jargon(translation)
        rationale_jargon = find_jargon(cmd.get("rationale", ""))
        if jargon or rationale_jargon:
            findings["jargon"].append({
                "path": path,
                "field": "command",
                "translation_jargon": jargon,
                "rationale_jargon": rationale_jargon,
                "text": translation,
            })

        weaknesses = check_weak_translation(path, translation)
        if weaknesses:
            findings["weak_translations"].append({
                "path": path,
                "field": "command",
                "issues": weaknesses,
                "text": translation,
            })

        verdict_issues = check_verdict_calibration("command", cmd)
        if verdict_issues:
            findings["verdict_suspects"].append({
                "path": path,
                "field": "command",
                "verdict": cmd.get("verdict", ""),
                "issues": verdict_issues,
                "text": translation,
            })

        # Tag calibration for commands
        tag_issues = check_tag_calibration("command", cmd)
        if tag_issues:
            findings["tag_suspects"].append({
                "path": path,
                "field": "command",
                "issues": tag_issues,
                "text": translation,
            })

    # Check each flag
    for flg in flags:
        applies_to = flg.get("applies_to", "")
        flag_name = flg.get("flag", "")
        modifier = flg.get("translation_modifier", "")
        label = f"{applies_to} {flag_name}"

        mod_jargon = find_jargon(modifier)
        rat_jargon = find_jargon(flg.get("rationale", ""))
        if mod_jargon or rat_jargon:
            findings["jargon"].append({
                "path": label,
                "field": "flag",
                "translation_jargon": mod_jargon,
                "rationale_jargon": rat_jargon,
                "text": modifier,
            })

        verdict_issues = check_verdict_calibration("flag", flg)
        if verdict_issues:
            findings["verdict_suspects"].append({
                "path": label,
                "field": "flag",
                "verdict": flg.get("verdict", ""),
                "issues": verdict_issues,
                "text": modifier,
            })

        # Tag calibration for flags
        tag_issues = check_tag_calibration("flag", flg)
        if tag_issues:
            findings["tag_suspects"].append({
                "path": label,
                "field": "flag",
                "issues": tag_issues,
                "text": modifier,
            })

    # 5. Combo auditing — jargon + weak translation checks
    for combo in combos:
        combo_path = combo.get("path", "")
        translation = combo.get("translation", "")

        jargon = find_jargon(translation)
        rationale_jargon = find_jargon(combo.get("rationale", ""))
        if jargon or rationale_jargon:
            findings["jargon"].append({
                "path": combo_path,
                "field": "combo",
                "translation_jargon": jargon,
                "rationale_jargon": rationale_jargon,
                "text": translation,
            })

        weaknesses = check_weak_translation(combo_path, translation)
        if weaknesses:
            findings["weak_translations"].append({
                "path": combo_path,
                "field": "combo",
                "issues": weaknesses,
                "text": translation,
            })

        # Tag calibration for combos
        tag_issues = check_tag_calibration("combo", combo)
        if tag_issues:
            findings["tag_suspects"].append({
                "path": combo_path,
                "field": "combo",
                "issues": tag_issues,
                "text": translation,
            })

    # 6. Thin combo check (INFO): commands with flags but no combos
    if len(flags) > 0 and len(combos) == 0:
        findings["thin_combos"].append({
            "tool": tool_name,
            "commands": len(commands),
            "flags": len(flags),
            "message": "candidate for combo generation",
        })

    return findings


def main():
    files = sorted(TOOLS_DIR.glob("*.toml"))
    if not files:
        print(f"No TOML files found in {TOOLS_DIR}", file=sys.stderr)
        sys.exit(1)

    all_thin: list[dict] = []
    all_jargon: list[dict] = []
    all_weak: list[dict] = []
    all_verdict: list[dict] = []
    all_thin_combos: list[dict] = []
    all_tag: list[dict] = []
    parse_errors: list[dict] = []

    for filepath in files:
        findings = audit_file(filepath)
        tool = filepath.stem

        if "parse_errors" in findings:
            parse_errors.append({"tool": tool, "errors": findings["parse_errors"]})
            continue

        for item in findings["thin_entries"]:
            all_thin.append(item)
        for item in findings["jargon"]:
            item["tool"] = tool
            all_jargon.append(item)
        for item in findings["weak_translations"]:
            item["tool"] = tool
            all_weak.append(item)
        for item in findings["verdict_suspects"]:
            item["tool"] = tool
            all_verdict.append(item)
        for item in findings["thin_combos"]:
            all_thin_combos.append(item)
        for item in findings["tag_suspects"]:
            item["tool"] = tool
            all_tag.append(item)

    # Sort thin entries by priority
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    all_thin.sort(key=lambda x: (priority_order.get(x["priority"], 3), x["tool"]))

    report = {
        "summary": {
            "files_scanned": len(files),
            "thin_entries": len(all_thin),
            "thin_high": sum(1 for t in all_thin if t["priority"] == "HIGH"),
            "thin_medium": sum(1 for t in all_thin if t["priority"] == "MEDIUM"),
            "thin_low": sum(1 for t in all_thin if t["priority"] == "LOW"),
            "jargon_findings": len(all_jargon),
            "weak_translations": len(all_weak),
            "verdict_suspects": len(all_verdict),
            "thin_combos": len(all_thin_combos),
            "tag_suspects": len(all_tag),
            "parse_errors": len(parse_errors),
        },
        "thin_entries": all_thin,
        "jargon": all_jargon,
        "weak_translations": all_weak,
        "verdict_suspects": all_verdict,
        "thin_combos": all_thin_combos,
        "tag_suspects": all_tag,
        "parse_errors": parse_errors,
    }

    # JSON report to stdout
    print(json.dumps(report, indent=2))

    # Human-readable summary to stderr
    s = report["summary"]
    print("\n" + "=" * 70, file=sys.stderr)
    print("AUDIT SUMMARY", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(f"Files scanned:       {s['files_scanned']}", file=sys.stderr)
    print(f"Parse errors:        {s['parse_errors']}", file=sys.stderr)
    print(file=sys.stderr)

    print(f"--- THIN ENTRIES (no flags): {s['thin_entries']} total ---",
          file=sys.stderr)
    print(f"  HIGH priority:   {s['thin_high']}", file=sys.stderr)
    print(f"  MEDIUM priority: {s['thin_medium']}", file=sys.stderr)
    print(f"  LOW priority:    {s['thin_low']}", file=sys.stderr)
    if all_thin:
        high_tools = [t["tool"] for t in all_thin if t["priority"] == "HIGH"]
        if high_tools:
            print(f"  HIGH examples:   {', '.join(high_tools[:15])}",
                  file=sys.stderr)
        med_tools = [t["tool"] for t in all_thin if t["priority"] == "MEDIUM"]
        if med_tools:
            print(f"  MEDIUM examples: {', '.join(med_tools[:10])}",
                  file=sys.stderr)
    print(file=sys.stderr)

    print(f"--- JARGON IN TRANSLATIONS: {s['jargon_findings']} findings ---",
          file=sys.stderr)
    if all_jargon:
        for item in all_jargon[:8]:
            terms = item.get("translation_jargon", []) + item.get("rationale_jargon", [])
            print(f"  {item['tool']}: {item['path']} -> {', '.join(terms)}",
                  file=sys.stderr)
        if len(all_jargon) > 8:
            print(f"  ... and {len(all_jargon) - 8} more", file=sys.stderr)
    print(file=sys.stderr)

    print(f"--- WEAK TRANSLATIONS: {s['weak_translations']} findings ---",
          file=sys.stderr)
    if all_weak:
        for item in all_weak[:8]:
            print(f"  {item['tool']}: {item['path']} -> {'; '.join(item['issues'])}",
                  file=sys.stderr)
            print(f"    \"{item['text']}\"", file=sys.stderr)
        if len(all_weak) > 8:
            print(f"  ... and {len(all_weak) - 8} more", file=sys.stderr)
    print(file=sys.stderr)

    print(f"--- VERDICT CALIBRATION SUSPECTS: {s['verdict_suspects']} findings ---",
          file=sys.stderr)
    if all_verdict:
        for item in all_verdict[:8]:
            print(f"  {item['tool']}: {item['path']} (verdict={item['verdict']}) "
                  f"-> {'; '.join(item['issues'])}",
                  file=sys.stderr)
        if len(all_verdict) > 8:
            print(f"  ... and {len(all_verdict) - 8} more", file=sys.stderr)
    print(file=sys.stderr)

    print(f"--- THIN COMBO CANDIDATES: {s['thin_combos']} findings ---",
          file=sys.stderr)
    if all_thin_combos:
        for item in all_thin_combos[:8]:
            print(f"  {item['tool']}: {item['commands']} commands, {item['flags']} flags — {item['message']}",
                  file=sys.stderr)
        if len(all_thin_combos) > 8:
            print(f"  ... and {len(all_thin_combos) - 8} more", file=sys.stderr)
    print(file=sys.stderr)

    print(f"--- TAG CALIBRATION SUSPECTS: {s['tag_suspects']} findings ---",
          file=sys.stderr)
    if all_tag:
        for item in all_tag[:8]:
            print(f"  {item['tool']}: {item['path']} -> {'; '.join(item['issues'])}",
                  file=sys.stderr)
        if len(all_tag) > 8:
            print(f"  ... and {len(all_tag) - 8} more", file=sys.stderr)
    print(file=sys.stderr)

    print("=" * 70, file=sys.stderr)

    if s["thin_high"] > 0 or s["verdict_suspects"] > 0 or s["parse_errors"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
