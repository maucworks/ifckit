#!/usr/bin/env bash
# This file was generated with the assistance of an AI coding tool.
# Local dependency matrix for ifckit (no CI — run this instead).
#
# Proves the pinned ifcopenshell line green and signals the next line:
#   tools/test-matrix.sh [--fresh] [spec ...]
#
# A spec is a version (e.g. 0.9.0, 0.8.5) or `latest`. Default specs are the
# pin from pyproject.toml plus `latest`. One venv per spec is (re)used under
# ${IFCKIT_MATRIX_DIR:-$TMPDIR/ifckit-matrix}, so nothing pollutes the repo.
#
# Exit code: nonzero iff the PINNED spec fails. Any other spec (notably
# `latest`) is signal-only: red means "band stays, file an issue", green
# means "the pin may move to a band". See AGENTS.md pin-beleid.

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MATRIX_DIR="${IFCKIT_MATRIX_DIR:-${TMPDIR:-/tmp}/ifckit-matrix}"
FRESH=0
PIN="$(grep -o 'ifcopenshell==[0-9.][0-9.]*' "$ROOT/pyproject.toml" | head -n 1 | cut -d= -f3)"

# Collect flags and non-flag args (specs).
SPECS=""
for arg in "$@"; do
    case "$arg" in
        -h|--help)
            sed -n '2,/^$/p' "$0" | sed 's/^# //; s/^#//'
            exit 0 ;;
        --fresh) ;;
        *) SPECS="$SPECS $arg" ;;
    esac
done
if [ -z "$SPECS" ]; then
    SPECS="$PIN latest"
fi

fail=0
echo "matrix dir: $MATRIX_DIR | pinned: $PIN | specs:$SPECS"
for spec in $SPECS; do
    # shellcheck disable=SC2001
    label="$(echo "$spec" | sed 's/[^A-Za-z0-9.]/_/g')"
    vdir="$MATRIX_DIR/oc-$label"
    if [ "$FRESH" = 1 ] && [ -d "$vdir" ]; then
        rm -rf "$vdir"
    fi
    if [ ! -d "$vdir" ]; then
        python3 -m venv "$vdir" || { echo "FAIL $spec: venv creation failed"; fail=1; continue; }
    fi
    if [ "$spec" = "latest" ]; then
        "$vdir/bin/pip" install -q -e "$ROOT[dev]" || { echo "FAIL $spec: install failed"; fail=1; continue; }
        "$vdir/bin/pip" install -q -U ifcopenshell || { echo "FAIL $spec: upgrade failed"; fail=1; continue; }
    else
        "$vdir/bin/pip" install -q -e "$ROOT[dev]" || { echo "FAIL $spec: install failed"; fail=1; continue; }
        "$vdir/bin/pip" install -q "ifcopenshell==$spec" || { echo "FAIL $spec: pin failed"; fail=1; continue; }
    fi
    installed="$("$vdir/bin/python" -c "import ifcopenshell; print(ifcopenshell.version)" 2>/dev/null || echo "?")"
    log="$MATRIX_DIR/pytest-$label.log"
    if "$vdir/bin/python" -m pytest "$ROOT/tests/" -q -p no:cacheprovider >"$log" 2>&1; then
        echo "GREEN $spec (ifcopenshell $installed)"
    else
        tail -n 3 "$log"
        if [ "$spec" = "$PIN" ]; then
            echo "RED $spec (ifcopenshell $installed) -- pinned line broken"
            fail=1
        else
            echo "SIGNAL-RED $spec (ifcopenshell $installed) -- band stays, file an issue"
        fi
    fi
done

if [ "$fail" = 0 ]; then
    echo "matrix OK (pinned $PIN green)"
else
    echo "matrix FAILED (pinned $PIN red)"
fi
exit "$fail"
