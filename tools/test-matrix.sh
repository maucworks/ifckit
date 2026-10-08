#!/usr/bin/env bash
# This file was generated with the assistance of an AI coding tool.
# Local dependency matrix for ifckit (no CI — run this instead).
#
# Proves both edges of the ifcopenshell band green and signals the next line:
#   tools/test-matrix.sh [--fresh] [spec ...]
#
# A spec is a version (e.g. 0.9.0, 0.8.4.post1) or `latest`. Default specs
# are both band edges from pyproject.toml plus `latest`. One venv per spec
# is (re)used under ${IFCKIT_MATRIX_DIR:-$TMPDIR/ifckit-matrix}, so nothing
# pollutes the repo. Venvs are built with ${IFCKIT_MATRIX_PYTHON:-python3};
# point it at a 3.9 interpreter to prove the Rhino 8 floor.
#
# Exit code: nonzero iff a BAND EDGE fails. Any other spec (notably
# `latest`) is signal-only: red means "max stays, file an issue", green
# means "max may move at release". See AGENTS.md pin-beleid.

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MATRIX_DIR="${IFCKIT_MATRIX_DIR:-${TMPDIR:-/tmp}/ifckit-matrix}"
FRESH=0
SPEC_LINE="$(grep -m1 'ifcopenshell>=' "$ROOT/pyproject.toml")"
BAND_LOWER="$(echo "$SPEC_LINE" | sed 's/.*ifcopenshell>=\([^,"]*\).*/\1/')"
BAND_UPPER="$(echo "$SPEC_LINE" | sed 's/.*<=\([^,"]*\).*/\1/')"

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
    SPECS="$BAND_LOWER $BAND_UPPER latest"
fi

MATRIX_PY="${IFCKIT_MATRIX_PYTHON:-python3}"
PY_MINOR="$($MATRIX_PY -c "import sys; print(sys.version_info[1])")"
if [ "$PY_MINOR" -lt 10 ]; then
    # Pre-3.10 (e.g. Rhino 8's 3.9): dev extras cannot install here
    # (mypy/ruff lines need >= 3.10). Minimal install: library + pytest.
    MINIMAL=1
else
    MINIMAL=0
fi

fail=0
failed=""
ran=""
echo "matrix dir: $MATRIX_DIR | band: $BAND_LOWER..$BAND_UPPER | specs:$SPECS | python: $MATRIX_PY"
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
    if [ "$MINIMAL" = 1 ]; then
        case "$spec" in
            latest|$BAND_UPPER)
                echo "SKIP $spec on $MATRIX_PY (needs Python >= 3.10 by design; proven in the 3.10+ run)"
                continue
                ;;
        esac
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
    ran="$ran $spec"
    if "$vdir/bin/python" -m pytest "$ROOT/tests/" -q -p no:cacheprovider >"$log" 2>&1; then
        echo "GREEN $spec (ifcopenshell $installed)"
    else
        tail -n 3 "$log"
        case "$spec" in
            "$BAND_LOWER"|"$BAND_UPPER")
                echo "RED $spec (ifcopenshell $installed) -- band edge broken"
                fail=1
                failed="$failed $spec"
                ;;
            *)
                echo "SIGNAL-RED $spec (ifcopenshell $installed) -- max stays, file an issue"
                ;;
        esac
    fi
done

missing=""
for edge in $BAND_LOWER $BAND_UPPER; do
    case " $ran " in
        *" $edge "*) ;;
        *) missing="$missing $edge" ;;
    esac
done
if [ "$fail" = 0 ] && [ -z "$missing" ]; then
    echo "matrix OK (band $BAND_LOWER..$BAND_UPPER green)"
elif [ "$fail" = 0 ]; then
    echo "matrix done (band edges not run:$missing)"
else
    echo "matrix FAILED ($failed)"
fi
exit "$fail"
