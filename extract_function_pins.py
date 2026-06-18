#!/usr/bin/env python3
"""Extract function parameter/pin information from .uasset files.

Usage:
    python extract_function_pins.py <path_to_uasset>
    python extract_function_pins.py <path_to_uasset> --json  (machine-readable)
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from uasset_read.parse_uasset import parse_package
from uasset_read.archive import FArchive
from uasset_read.constants import PACKAGE_FILE_TAG, PACKAGE_FILE_TAG_SWAPPED
from uasset_read.graph import extract_blueprint_graphs
from uasset_read.blueprint.variable_extractor import _extract_functions_from_graphs


def open_archive_with_swap(path: str, tolerant: bool = True) -> FArchive:
    """Open an FArchive and auto-detect byte swapping from the package tag."""
    archive = FArchive(path, tolerant=tolerant)
    tag = archive.read_u32()
    if tag == PACKAGE_FILE_TAG_SWAPPED:
        archive.set_byte_swapping(True)
    elif tag != PACKAGE_FILE_TAG:
        print(f"Warning: Unexpected package tag: {hex(tag)}", file=sys.stderr)
    archive.seek(0)
    return archive


def extract_function_pins(uasset_path: str) -> list[dict]:
    """Extract function pin/parameter info from a .uasset file.

    Uses a two-phase approach:
    1. Lightweight parse to get the package structure (skip expensive full property parsing)
    2. Direct archive-based graph extraction to read function entry node pins
    """
    path = str(Path(uasset_path).resolve())

    # Phase 1: Parse package structure (lightweight mode)
    result = parse_package(path, tolerant=True)

    if not result.summary or not result.export_map:
        print(f"Error: Could not parse package structure for {path}", file=sys.stderr)
        if result.errors:
            for err in result.errors:
                print(f"  {err}", file=sys.stderr)
        return []

    # Phase 2: Open a new archive and extract graphs directly
    archive = open_archive_with_swap(path, tolerant=True)
    try:
        graphs = extract_blueprint_graphs(
            archive,
            result.summary,
            result.name_map or [],
            result.import_map or [],
            result.export_map,
            linker=result.linker,
        )

        if not graphs:
            print("No blueprint graphs found.", file=sys.stderr)
            return []

        # Extract function info from graph nodes
        functions = _extract_functions_from_graphs(graphs)

        output = []
        for func in functions:
            func_data = {
                "function_name": func.name,
                "return_type": func.return_type,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.param_type,
                        "is_input": p.is_input,
                        "is_output": p.is_output,
                    }
                    for p in func.parameters
                ],
            }
            output.append(func_data)

        return output

    finally:
        archive.close()


def main():
    parser = argparse.ArgumentParser(description="Extract function pin info from .uasset files")
    parser.add_argument("path", type=str, help="Path to .uasset file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    functions = extract_function_pins(args.path)

    if not functions:
        print("No functions found.")
        sys.exit(1)

    if args.json:
        print(json.dumps(functions, indent=2, ensure_ascii=False))
    else:
        for func in functions:
            params_str = ", ".join(
                f"{p['type']} {p['name']}"
                for p in func["parameters"]
            )
            print(f"{func['return_type'] or 'void'} {func['function_name']}({params_str})")
            for p in func["parameters"]:
                arrow = "->" if p["is_output"] else "<-"
                print(f"    {arrow} {p['type']} {p['name']}")


if __name__ == "__main__":
    main()
