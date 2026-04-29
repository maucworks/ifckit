"""
ifckit command-line interface
============================

Usage:
    ifckit build input.json -o output.ifc
    ifckit build input.json --output output.ifc
    cat input.json | ifckit build - -o output.ifc  (read from stdin)
"""

import argparse
import sys
from pathlib import Path

from ifckit import build, validate_json


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="ifckit",
        description="IFC builder library - convert JSON to IFC",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    build_parser = subparsers.add_parser("build", help="Build IFC from JSON")
    build_parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="Input JSON file (default: stdin)",
    )
    build_parser.add_argument(
        "-o", "--output",
        required=True,
        help="Output IFC file path",
    )
    build_parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate JSON, don't create IFC",
    )

    args = parser.parse_args()

    if args.command == "build":
        return handle_build(args)

    parser.print_help()
    return 1


def handle_build(args) -> int:
    input_path = args.input

    if input_path == "-":
        json_str = sys.stdin.read()
    else:
        p = Path(input_path)
        if not p.exists():
            print(f"Error: Input file not found: {input_path}", file=sys.stderr)
            return 1
        json_str = p.read_text(encoding="utf-8")

    import json

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        return 1

    result = validate_json(data)
    if not result.ok:
        print("JSON validation failed:", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    if args.validate_only:
        print("JSON is valid")
        return 0

    try:
        model = build(data, args.output)
        print(f"Successfully created: {args.output}")
        return 0
    except Exception as e:
        print(f"Error building IFC: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())