"""Command-line interface: ``agentcontext parse <file> [...]``.

Three forms, per the v0.1 spec — a CLI with three commands that work
perfectly beats twelve that mostly work:

    agentcontext parse report.pdf                 # -> report.md next to source
    agentcontext parse report.pdf --json          # -> report.json (full UDM)
    agentcontext parse report.pdf --cite inline   # markdown with citation anchors
"""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__, parse


def _cmd_parse(args: argparse.Namespace) -> int:
    doc = parse(args.file)
    base, _ = os.path.splitext(args.file)
    if args.json:
        out = doc.to_json()
        target = base + ".json"
    else:
        out = doc.to_markdown(cite=args.cite == "inline")
        target = base + ".md"
    if os.path.abspath(target) == os.path.abspath(args.file):
        target = base + ".parsed" + os.path.splitext(target)[1]  # never clobber the source
    if args.stdout:
        print(out)
    else:
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(out)
        print(f"wrote {target}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentcontext",
        description="Document parsing that never loses provenance.",
    )
    parser.add_argument("--version", action="version", version=f"agentcontext {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_parse = sub.add_parser("parse", help="Parse a document into Markdown or UDM JSON.")
    p_parse.add_argument("file", help="Path to the document to parse.")
    p_parse.add_argument("--json", action="store_true",
                         help="Emit the full UDM as JSON instead of Markdown.")
    p_parse.add_argument("--cite", choices=["none", "inline"], default="none",
                         help="inline: append provenance anchors to each Markdown block.")
    p_parse.add_argument("--stdout", action="store_true",
                         help="Print to stdout instead of writing next to the source.")
    p_parse.set_defaults(func=_cmd_parse)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
