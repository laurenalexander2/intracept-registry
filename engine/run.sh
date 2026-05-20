#!/usr/bin/env bash
# engine/run.sh — intracept-registry quality engine
#
# Runs all engine stages and produces a consolidated report.
# Use this between improvement passes to measure progress.
#
# Usage:
#   ./engine/run.sh              # full run: validate + audit + enrich + rebuild check
#   ./engine/run.sh validate     # schema validation only
#   ./engine/run.sh audit        # quality audit only
#   ./engine/run.sh enrich       # flag coverage gaps only
#   ./engine/run.sh rebuild      # rebuild registry.json and check for drift
#   ./engine/run.sh report       # just the summary (no enrich — fastest)
#   ./engine/run.sh fix          # rebuild registry.json in place

set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON=python3
ENGINE=engine
REPORTS=engine/reports
mkdir -p "$REPORTS"

TIMESTAMP=$(date +%Y%m%dT%H%M%S)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

header() { echo -e "\n${BOLD}${BLUE}── $1 ──${NC}\n"; }
ok()     { echo -e "  ${GREEN}✓${NC} $1"; }
warn()   { echo -e "  ${YELLOW}!${NC} $1"; }
fail()   { echo -e "  ${RED}✗${NC} $1"; }

# ── Stage: Validate ──────────────────────────────────────────────────────────
run_validate() {
    header "VALIDATE — Schema Compliance"
    if $PYTHON $ENGINE/validate.py > "$REPORTS/validate-$TIMESTAMP.txt" 2>&1; then
        ok "All files pass schema validation"
    else
        fail "Schema errors found"
        cat "$REPORTS/validate-$TIMESTAMP.txt"
    fi
}

# ── Stage: Audit ─────────────────────────────────────────────────────────────
run_audit() {
    header "AUDIT — Quality Issues"
    # audit.py exits 1 when issues exist (expected), so don't let set -e kill us
    $PYTHON $ENGINE/audit.py > "$REPORTS/audit-$TIMESTAMP.json" 2>"$REPORTS/audit-$TIMESTAMP.txt" || true

    # Show the human-readable summary from stderr
    cat "$REPORTS/audit-$TIMESTAMP.txt"

    # Count issues by category from JSON
    local thin=$(  $PYTHON -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('thin_entries',[])))"   < "$REPORTS/audit-$TIMESTAMP.json" 2>/dev/null || echo "?")
    local jargon=$($PYTHON -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('jargon',[])))"        < "$REPORTS/audit-$TIMESTAMP.json" 2>/dev/null || echo "?")
    local weak=$(  $PYTHON -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('weak_translations',[])))" < "$REPORTS/audit-$TIMESTAMP.json" 2>/dev/null || echo "?")
    local risk=$(  $PYTHON -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('risk_suspects',[])))" < "$REPORTS/audit-$TIMESTAMP.json" 2>/dev/null || echo "?")

    echo ""
    echo -e "  ${BOLD}Audit totals:${NC}"
    [ "$thin"   != "0" ] && warn "Thin entries (no flags):  $thin" || ok "Thin entries: 0"
    [ "$jargon" != "0" ] && warn "Jargon instances:         $jargon" || ok "Jargon: 0"
    [ "$weak"   != "0" ] && warn "Weak translations:        $weak" || ok "Weak translations: 0"
    [ "$risk"   != "0" ] && warn "Risk calibration issues:  $risk" || ok "Risk calibration: 0"
}

# ── Stage: Enrich ────────────────────────────────────────────────────────────
run_enrich() {
    header "ENRICH — Flag Coverage Gaps"
    echo "  Scanning man pages and --help output (this takes a few minutes)..."
    $PYTHON $ENGINE/enrich.py --thin --top 40 > "$REPORTS/enrich-$TIMESTAMP.txt" 2>&1
    cat "$REPORTS/enrich-$TIMESTAMP.txt"
}

# ── Stage: Rebuild ───────────────────────────────────────────────────────────
run_rebuild_check() {
    header "REBUILD — Registry Sync Check"
    if $PYTHON $ENGINE/rebuild.py --check > "$REPORTS/rebuild-$TIMESTAMP.txt" 2>&1; then
        ok "registry.json is in sync with tools/*.toml"
    else
        warn "registry.json has drift from TOML source"
        head -20 "$REPORTS/rebuild-$TIMESTAMP.txt"
        echo ""
        echo "  Run: ./engine/run.sh fix  (to rebuild in place)"
    fi
}

run_rebuild_fix() {
    header "REBUILD — Regenerating registry.json"
    $PYTHON $ENGINE/rebuild.py
    ok "registry.json rebuilt from tools/*.toml"
}

# ── Summary ──────────────────────────────────────────────────────────────────
summary() {
    header "ENGINE SUMMARY"
    local total_tools=$(ls tools/*.toml 2>/dev/null | wc -l | tr -d ' ')
    local total_commands=$($PYTHON -c "
import json
with open('registry.json') as f: d = json.load(f)
print(len(d.get('commands',{})))
" 2>/dev/null || echo "?")
    local total_flags=$($PYTHON -c "
import json
with open('registry.json') as f: d = json.load(f)
print(len(d.get('flags',{})))
" 2>/dev/null || echo "?")
    local thin_count=$(ls tools/*.toml 2>/dev/null | while read f; do
        $PYTHON -c "
import tomllib,sys
with open('$f','rb') as fh: d=tomllib.load(fh)
if not d.get('flag',[]): print(1)
" 2>/dev/null
    done | wc -l | tr -d ' ')

    echo -e "  Tools:      ${BOLD}$total_tools${NC}"
    echo -e "  Commands:   ${BOLD}$total_commands${NC}"
    echo -e "  Flags:      ${BOLD}$total_flags${NC}"
    echo -e "  Thin (0 flags): ${BOLD}$thin_count${NC} ($(( thin_count * 100 / total_tools ))%)"
    echo -e "  Reports:    ${BOLD}$REPORTS/*-$TIMESTAMP.*${NC}"
    echo ""
}

# ── Main ─────────────────────────────────────────────────────────────────────
case "${1:-full}" in
    validate)  run_validate ;;
    audit)     run_audit ;;
    enrich)    run_enrich ;;
    rebuild)   run_rebuild_check ;;
    fix)       run_rebuild_fix ;;
    report)    run_validate; run_audit; run_rebuild_check; summary ;;
    full)      run_validate; run_audit; run_enrich; run_rebuild_check; summary ;;
    *)         echo "Usage: $0 [validate|audit|enrich|rebuild|fix|report|full]"; exit 1 ;;
esac
