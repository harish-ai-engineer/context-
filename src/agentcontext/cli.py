"""Command-line interface: ``agentcontext <command> ...``.

Commands cover the pipeline end-to-end:

    agentcontext parse     file.pdf --to markdown
    agentcontext chunk     file.pdf --strategy token
    agentcontext search    "revenue" --docs a.md b.pdf --k 5
    agentcontext summarize file.pdf --sentences 3
    agentcontext context   "my question" --docs a.md b.pdf --k 5 --format prompt
"""

from __future__ import annotations

import argparse
import json
import sys

from . import (
    __version__,
    build_context_from_files,
    chunk as chunk_doc,
    ingest,
    parse,
    retrieve,
    summarize,
)


def _cmd_parse(args: argparse.Namespace) -> int:
    doc = parse(args.file)
    if args.to == "json":
        print(json.dumps(doc.to_dict(), indent=2, ensure_ascii=False))
    elif args.to == "markdown":
        print(doc.to_markdown())
    else:
        print(doc.to_text())
    return 0


def _cmd_chunk(args: argparse.Namespace) -> int:
    doc = parse(args.file)
    chunks = chunk_doc(doc, strategy=args.strategy)
    if args.to == "json":
        print(json.dumps([c.to_dict() for c in chunks], indent=2, ensure_ascii=False))
    else:
        for i, c in enumerate(chunks, 1):
            print(f"--- chunk {i}/{len(chunks)} ({len(c.text.split())} words) ---")
            print(c.text)
            print()
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    _, chunks = ingest(args.docs)
    results = retrieve(chunks, args.query, k=args.k, embedder=args.embedder)
    if args.format == "json":
        print(json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False))
        return 0
    for i, r in enumerate(results, 1):
        loc = ""
        if r.chunk.provenance:
            p = r.chunk.provenance[0]
            loc = f"  [{p.source}{f' p.{p.page}' if p.page else ''}"
            loc += f" — {p.section}]" if p.section else "]"
        print(f"{i}. score={r.score:.4f}{loc}")
        text = " ".join(r.chunk.text.split())
        print(f"   {text[:200]}{'…' if len(text) > 200 else ''}")
    return 0


def _cmd_summarize(args: argparse.Namespace) -> int:
    print(summarize(parse(args.file), max_sentences=args.sentences))
    return 0


def _cmd_context(args: argparse.Namespace) -> int:
    pkg = build_context_from_files(
        args.query,
        args.docs,
        k=args.k,
        embedder=args.embedder,
        chunker=args.chunker,
    )
    if args.format == "json":
        print(json.dumps(pkg.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(pkg.to_prompt())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentcontext",
        description="Turn any document into AI-ready, cited context for LLMs.",
    )
    parser.add_argument("--version", action="version", version=f"agentcontext {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_parse = sub.add_parser("parse", help="Parse a document into the Unified Document Model.")
    p_parse.add_argument("file", help="Path to the document to parse.")
    p_parse.add_argument(
        "--to",
        choices=["text", "markdown", "json"],
        default="markdown",
        help="Output format (default: markdown).",
    )
    p_parse.set_defaults(func=_cmd_parse)

    p_chunk = sub.add_parser("chunk", help="Parse and chunk a document.")
    p_chunk.add_argument("file", help="Path to the document.")
    p_chunk.add_argument("--strategy", default="token", help="Chunker name (default: token).")
    p_chunk.add_argument(
        "--to", choices=["text", "json"], default="text", help="Output format (default: text)."
    )
    p_chunk.set_defaults(func=_cmd_chunk)

    p_search = sub.add_parser("search", help="Semantic search across documents.")
    p_search.add_argument("query", help="The search query.")
    p_search.add_argument(
        "--docs", nargs="+", required=True, metavar="FILE", help="Source documents."
    )
    p_search.add_argument("--k", type=int, default=5, help="Number of results.")
    p_search.add_argument("--embedder", default="hashing", help="Embedder name (default: hashing).")
    p_search.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format."
    )
    p_search.set_defaults(func=_cmd_search)

    p_sum = sub.add_parser("summarize", help="Extractive summary of a document.")
    p_sum.add_argument("file", help="Path to the document.")
    p_sum.add_argument("--sentences", type=int, default=3, help="Sentences to keep (default: 3).")
    p_sum.set_defaults(func=_cmd_summarize)

    p_ctx = sub.add_parser("context", help="Build a cited context package for a query.")
    p_ctx.add_argument("query", help="The question / retrieval query.")
    p_ctx.add_argument(
        "--docs", nargs="+", required=True, metavar="FILE", help="Source documents."
    )
    p_ctx.add_argument("--k", type=int, default=5, help="Number of chunks to retrieve.")
    p_ctx.add_argument("--embedder", default="hashing", help="Embedder name (default: hashing).")
    p_ctx.add_argument("--chunker", default="token", help="Chunker name (default: token).")
    p_ctx.add_argument(
        "--format",
        choices=["prompt", "json"],
        default="prompt",
        help="Output format (default: prompt).",
    )
    p_ctx.set_defaults(func=_cmd_context)
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
