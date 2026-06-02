"""
ifckit.builders._expr
=====================

Expression evaluator for JSON component-graph parameter substitution.

Supports +, -, *, / with correct precedence, parentheses, and $variables.
Uses a recursive descent parser.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Tuple


def eval_expr(expr: Any, params: Dict[str, float]) -> float:
    """Evaluate a parameter expression to a float.

    Supports +, -, *, / with correct precedence, parentheses, and $variables.
    Uses a recursive descent parser: no regex token-list mutation.

    Grammar:
        expr   = term   (('+' | '-') term)*
        term   = factor (('*' | '/') factor)*
        factor = '(' expr ')' | number | '$' name | '-' factor
    """
    if isinstance(expr, (int, float)):
        return float(expr)
    if not isinstance(expr, str):
        raise ValueError(f"eval_expr: expected str or number, got {type(expr).__name__!r}")

    src = expr.strip()
    pos = [0]  # mutable int so nested functions can advance it

    def peek() -> str:
        while pos[0] < len(src) and src[pos[0]] == " ":
            pos[0] += 1
        return src[pos[0]] if pos[0] < len(src) else ""

    def consume(expected: str | None = None) -> str:
        ch = peek()
        if expected is not None and ch != expected:
            raise ValueError(f"eval_expr: expected {expected!r} got {ch!r} in {expr!r}")
        pos[0] += 1
        return ch

    def parse_number() -> float:
        start = pos[0]
        while pos[0] < len(src) and src[pos[0]] in "0123456789.":
            pos[0] += 1
        if pos[0] == start:
            raise ValueError(f"eval_expr: expected number at pos {start} in {expr!r}")
        return float(src[start : pos[0]])

    def parse_variable() -> float:
        pos[0] += 1  # skip '$'
        start = pos[0]
        while pos[0] < len(src) and (src[pos[0]].isalnum() or src[pos[0]] == "_"):
            pos[0] += 1
        name = src[start : pos[0]]
        if name not in params:
            raise KeyError(f"Unknown parameter: {name!r}")
        return float(params[name])

    def parse_factor() -> float:
        ch = peek()
        if ch == "(":
            consume("(")
            val = parse_expr()
            consume(")")
            return val
        if ch == "-":
            consume("-")
            return -parse_factor()
        if ch == "$":
            return parse_variable()
        return parse_number()

    def parse_term() -> float:
        val = parse_factor()
        while peek() in ("*", "/"):
            op = consume()
            rhs = parse_factor()
            if op == "*":
                val *= rhs
            else:
                if abs(rhs) < 1e-15:
                    raise ValueError(f"eval_expr: division by zero in {expr!r}")
                val /= rhs
        return val

    def parse_expr() -> float:
        val = parse_term()
        while peek() in ("+", "-"):
            op = consume()
            rhs = parse_term()
            if op == "+":
                val += rhs
            else:
                val -= rhs
        return val

    result = parse_expr()
    if pos[0] != len(src) and src[pos[0] :].strip():
        raise ValueError(f"eval_expr: unexpected trailing input {src[pos[0] :]!r} in {expr!r}")
    return result


def contains_literal(expr: Any) -> bool:
    """Check if expression contains any literal numbers (not just variables).

    Returns True only if the expression has at least one numeric literal.
    Variables like "$name" or expressions with only variables return False.

    Args:
        expr: Expression (str, int, float).

    Returns:
        True if contains at least one literal number; False if all tokens are variables.
    """
    # Numeric literals always have literals
    if isinstance(expr, (int, float)):
        return True

    if not isinstance(expr, str):
        return False

    expr = expr.strip()
    # Pure variable: "$name"
    if re.fullmatch(r"\$[A-Za-z_][A-Za-z0-9_]*", expr):
        return False

    # Tokenize and check if any token is a literal (not starting with $)
    tokens = re.split(r"\s*([\+\-\*\/])\s*", expr)
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        # Skip operators
        if tok in ("+", "-", "*", "/"):
            continue
        # If token doesn't start with $, it's a literal
        if not tok.startswith("$"):
            return True

    # All non-operator tokens are variables
    return False


def eval_point(
    raw: Any,
    params: Dict[str, float],
    scale_x: float = 1.0,
    scale_y: float = 1.0,
) -> Tuple[float, float]:
    """Evaluate a 2-element [x, y] array and apply scale factors.

    Scale factors map reference-space coordinates to actual dimensions.
    ``scale_x = actual_w / ref_w``, ``scale_y = actual_h / ref_h``.

    Literals in the array (e.g., 10, 20) are scaled.
    Variables (e.g., "$w", "$h") are NOT scaled (they are occurrence values).
    Expressions with both (e.g., "$w + 10") scale only the literals.
    """
    if not (isinstance(raw, (list, tuple)) and len(raw) == 2):
        raise ValueError(f"Expected [x, y] point, got {raw!r}")

    # Evaluate X: if it has literals, apply scale_x; else don't scale
    x_val = eval_expr(raw[0], params)
    x = x_val * scale_x if contains_literal(raw[0]) else x_val

    # Evaluate Y: if it has literals, apply scale_y; else don't scale
    y_val = eval_expr(raw[1], params)
    y = y_val * scale_y if contains_literal(raw[1]) else y_val

    return (x, y)


__all__ = [
    "eval_expr",
    "contains_literal",
    "eval_point",
]
