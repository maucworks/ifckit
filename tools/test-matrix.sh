#!/usr/bin/env bash
# This file was generated with the assistance of an AI coding tool.
# Local dependency matrix for ifckit (no CI — run this instead).
#
# Proves the pinned ifcopenshell line green and signals the next line:
#   tools/test-matrix.sh [--fresh] [spec ...]
#
# A spec is a version (e.g. 0.9.0, 0.8.4.post1) or `latest`. Default specs
# are the pin from pyproject.toml plus `latest`. One venv per spec is
# (re)used under ${IFCKIT_MATRIX_DIR:-$TMPDIR/ifckit-matrix}, so nothing
# pollutes the repo. Venvs are built with ${IFCKIT_MATRIX_PYTHON:-python3};
# point it at a 3.9 interpreter to prove the Rhino 8 floor.
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
        --fresh) FRESH=1 ;;
        *) SPECS="$SPECS $arg" ;;
    esac
done
if [ -z "$SPECS" ]; then
    SPECS="$PIN latest"
fi

MATRIX_PY="${IFCKIT_MATRIX_PYTHON:-python3}"
PY_MINOR="$($MATRIX_PY -c "import sys; print(sys.version_info[1])")"
if [ "$PY_MINOR" -lt 10 ]; then
    # Pre-3.10 (e.g. Rhino 8's 3.9): dev extras pull ifcopenshell==0.9.0,
    # which cannot install here by design. Minimal install instead.
    MINIMAL=1
else
    MINIMAL=0
fi

fail=0
failed=""
echo "matrix dir: $MATRIX_DIR | pinned: $PIN | specs:$SPECS | python: $MATRIX_PY"
for spec in $SPECS; do
    # shellcheck disable=SC2001
    label="$(echo "$spec" | sed 's/[^A-Za-z0-9.]/_/g')"
    vdir="$MATRIX_DIR/oc-$label"
    if [ "$FRESH" = 1 ] && [ -d "$vdir" ]; then
        rm -rf "$vdir"
    fi
    if [ ! -d "$vdir" ]; then
        "${IFCKIT_MATRIX_PYTHON:-python3}" -m venv "$vdir" || { echo "FAIL $spec: venv creation failed"; fail=1; continue; }
    fi
    install_fail=0
    if [ "$spec" = "latest" ] && [ "$MINIMAL" = 1 ]; then
        echo "SKIP latest on $MATRIX_PY (0.9+ cannot install pre-3.10 by design)"
        continue
    fi
    if [ "$MINIMAL" = 1 ]; then
        "$vdir/bin/pip" install -q -e "$ROOT" --no-deps || install_fail=1
        "$vdir/bin/pip" install -q pytest || install_fail=1
    else
        "$vdir/bin/pip" install -q -e "$ROOT[dev]" || install_fail=1
    fi
    if [ "$spec" = "latest" ]; then
        "$vdir/bin/pip" install -q -U ifcopenshell || install_fail=1
    else
        "$vdir/bin/pip" install -q "ifcopenshell==$spec" || install_fail=1
    fi
    if [ "$install_fail" = 1 ]; then
        echo "FAIL $spec: install failed"
        fail=1
        failed="$failed $spec"
        continue
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
            failed="$failed $spec"
        else
            echo "SIGNAL-RED $spec (ifcopenshell $installed) -- band stays, file an issue"
        fi
    fi
done

case " $SPECS " in
    *" $PIN "*) ran_pinned=1 ;;
    *) ran_pinned=0 ;;
esac
if [ "$fail" = 0 ] && [ "$ran_pinned" = 1 ]; then
    echo "matrix OK (pinned $PIN green)"
elif [ "$fail" = 0 ]; then
    echo "matrix done (pinned $PIN not run this time)"
else
    echo "matrix FAILED ($failed)"
fi
exit "$fail"
