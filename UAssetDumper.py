#!/usr/bin/env python3
"""
UAssetDumper — Standalone .uasset / .umap file dumper.

Parses Unreal Engine 5 assets without the editor by delegating to the
uasset_read library.

Usage:
    python UAssetDumper.py path/to/file.uasset           # JSON output
    python UAssetDumper.py path/to/file.uasset --markdown # Markdown output
    python UAssetDumper.py path/to/file.uasset --info     # Brief summary only
    python UAssetDumper.py path/to/dir/ --batch           # Batch directory
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_src_dir = Path(__file__).resolve().parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from uasset_read.core import parse_single, parse_batch, list_formats, ParseError

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
_logger = logging.getLogger("UAssetDumper")

EXIT_SUCCESS = 0
EXIT_PARSE_ERROR = 1
EXIT_FILE_NOT_FOUND = 2
EXIT_ARG_ERROR = 3


def _make_brief(data: dict) -> str:
    """Return a concise human-readable summary."""
    summary = data.get("summary", {})
    exports = data.get("exports", [])
    name_count = len(data.get("name_map", []))
    import_count = len(data.get("imports", []))
    lines = [
        f"Package:   {summary.get('package_name', '?')}",
        f"UE Ver:    {summary.get('ue_version', '?')}",
        f"Names:     {name_count}",
        f"Imports:   {import_count}",
        f"Exports:   {len(exports)}",
        "",
    ]
    for exp in exports:
        name = exp.get("object_name", "?")
        cls = exp.get("object_class", "") or exp.get("ue_export_raw", {}).get("class_index", "?")
        props = exp.get("properties", [])
        serial_size = exp.get("serial_size", 0)
        pnames = [p.get("name") for p in props if isinstance(p, dict)]
        lines.append(
            f"  [{name}] class={cls}  size={serial_size}  "
            f"props={len(props)}  {', '.join(pnames[:5]) if pnames else ''}"
        )
    return "\n".join(lines)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="UAssetDumper",
        description="Standalone Unreal Engine 5 .uasset file dumper"
    )
    parser.add_argument("file", nargs="?", default=None,
                        help="Path to .uasset file or directory (with --batch)")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true", help="Output JSON (default)")
    group.add_argument("--markdown", action="store_true", help="Output Markdown")
    group.add_argument("--info", action="store_true", help="Brief summary only")

    parser.add_argument("--output", metavar="FILE", help="Write to file")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--batch", action="store_true", help="Batch mode (directory input)")
    parser.add_argument("--batch-dir", metavar="DIR", help="Output directory for batch mode")
    parser.add_argument("--strict", action="store_true", help="Disable tolerant mode")
    parser.add_argument("--list-formats", action="store_true", help="List available formats")

    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger("UAssetDumper").setLevel(logging.DEBUG)
        logging.getLogger("uasset_read").setLevel(logging.DEBUG)

    if args.list_formats:
        print("Available formats:", ", ".join(list_formats()))
        sys.exit(EXIT_SUCCESS)

    if args.batch:
        if not args.file or not Path(args.file).is_dir():
            print("Error: --batch requires a directory path", file=sys.stderr)
            sys.exit(EXIT_ARG_ERROR)
        result = parse_batch(
            args.file, format="json",
            output_dir=args.batch_dir,
            tolerant=not args.strict,
        )
        print(f"Batch complete: {result.total} files ({len(result.success)} ok, "
              f"{len(result.failed)} failed)")
        sys.exit(EXIT_SUCCESS)

    if not args.file:
        print("Error: file argument is required", file=sys.stderr)
        sys.exit(EXIT_ARG_ERROR)

    path = Path(args.file)
    if not path.is_file():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(EXIT_FILE_NOT_FOUND)

    # Determine format
    fmt = "json"
    if args.markdown:
        fmt = "markdown"

    try:
        output_str = parse_single(
            str(path), format=fmt,
            tolerant=not args.strict,
            verbose=args.verbose,
        )
    except ParseError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)
    except Exception as e:
        _logger.debug("Fatal error", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)

    if args.info and fmt == "json":
        data = json.loads(output_str)
        output_str = _make_brief(data)

    if args.output:
        Path(args.output).write_text(output_str, encoding="utf-8")
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(output_str)


if __name__ == "__main__":
    main()
