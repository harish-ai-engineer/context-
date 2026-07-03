"""Structured-data parsers: CSV, JSON, XML (stdlib only)."""

from __future__ import annotations

import csv
import json
from xml.etree import ElementTree as ET

from ..core.model import Block, BlockType, Document, Provenance
from .base import Parser, register_parser


def _rows_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    header, *body = rows
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    for r in body:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


class CSVParser(Parser):
    """One TABLE block per file, rendered to markdown for LLM consumption."""

    name = "csv"
    extensions = ("csv", "tsv")

    def parse(self, path: str) -> Document:
        with open(path, encoding="utf-8-sig", errors="replace", newline="") as fh:
            sample = fh.read(4096)
            fh.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            except csv.Error:
                dialect = csv.excel
            rows = [[c.strip() for c in row] for row in csv.reader(fh, dialect) if any(row)]
        doc = Document(source=path, meta={"parser": self.name})
        if rows:
            md = _rows_to_markdown(rows)
            doc.add(
                Block(
                    type=BlockType.TABLE,
                    text=md,
                    meta={"markdown": md, "rows": rows},
                    provenance=Provenance(source=path, parser=self.name, version="csv-parser/0.1"),
                )
            )
        return doc


def _flatten(obj, prefix: str = ""):
    """Yield ``(path, scalar)`` pairs for every leaf value in a JSON structure."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _flatten(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _flatten(v, f"{prefix}[{i}]")
    else:
        yield prefix or "$", obj


class JSONParser(Parser):
    """Flatten leaves into ``path: value`` lines — retrievable and citable.

    One block per top-level key (or list item) keeps related fields together.
    """

    name = "json"
    extensions = ("json", "jsonl")

    def parse(self, path: str) -> Document:
        doc = Document(source=path, meta={"parser": self.name})
        with open(path, encoding="utf-8", errors="replace") as fh:
            if path.lower().endswith(".jsonl"):
                data = [json.loads(line) for line in fh if line.strip()]
            else:
                data = json.load(fh)

        if isinstance(data, dict):
            groups = [(str(k), v) for k, v in data.items()]
        elif isinstance(data, list):
            groups = [(f"[{i}]", v) for i, v in enumerate(data)]
        else:
            groups = [("$", data)]

        for key, value in groups:
            lines = [f"{p}: {v}" for p, v in _flatten(value, key)]
            if lines:
                doc.add(
                    Block(
                        type=BlockType.PARAGRAPH,
                        text="\n".join(lines),
                        meta={"key": key},
                        provenance=Provenance(
                            source=path, section=key, parser=self.name, version="json-parser/0.1"
                        ),
                    )
                )
        return doc


class XMLParser(Parser):
    """One paragraph per direct child of the root, tagged with its element path."""

    name = "xml"
    extensions = ("xml",)

    def parse(self, path: str) -> Document:
        root = ET.parse(path).getroot()
        doc = Document(source=path, meta={"parser": self.name, "root_tag": root.tag})
        children = list(root) or [root]
        for child in children:
            text = " ".join(" ".join(child.itertext()).split())
            if not text:
                continue
            doc.add(
                Block(
                    type=BlockType.PARAGRAPH,
                    text=text,
                    meta={"tag": child.tag},
                    provenance=Provenance(
                        source=path, section=child.tag, parser=self.name, version="xml-parser/0.1"
                    ),
                )
            )
        return doc


register_parser(CSVParser())
register_parser(JSONParser())
register_parser(XMLParser())
