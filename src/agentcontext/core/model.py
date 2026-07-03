"""Unified Document Model (UDM) — the keystone data model of AgentContext.

Every parser emits a :class:`Document` (an ordered list of :class:`Block`s
carrying provenance). v0.1 rule set (see agentcontext-v0.1-spec-and-readme.md):

- **No block without provenance.** If a parser can't determine a field it is
  explicitly ``null`` in the JSON output, never omitted.
- The UDM is versioned (``udm_version``). Breaking changes bump it.
- Tables are first-class: present inline as blocks *and* in ``tables[]`` with
  cell-level structure.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable, Optional

UDM_VERSION = "0.1"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class BlockType(str, Enum):
    """The kind of content a block holds. Extend via plugins as needed."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    IMAGE = "image"
    CODE = "code"
    FORMULA = "formula"
    CAPTION = "caption"
    QUOTE = "quote"
    PAGE_BREAK = "page_break"
    OTHER = "other"


@dataclass
class Provenance:
    """Where a piece of content came from — the basis for citations.

    Provenance travels with content through every stage so any output can be
    traced back to an exact location. Unknown fields serialize as explicit
    ``null`` — never omitted (spec rule).
    """

    source: str  # path or URI of the origin document
    page: Optional[int] = None  # 1-indexed page, when applicable
    section_path: Optional[str] = None  # hierarchical, e.g. "2. Methods > 2.1 Setup"
    bbox: Optional[tuple[float, float, float, float]] = None  # (x0, y0, x1, y1)
    char_span: Optional[tuple[int, int]] = None  # char offsets in source text
    confidence: float = 1.0  # 0..1, parser/OCR confidence
    parser: Optional[str] = None  # which parser produced it
    version: Optional[str] = None  # processing version, for reproducibility

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)  # all fields, explicit nulls included


@dataclass
class Block:
    """One atomic unit of a document, in reading order."""

    type: BlockType
    text: str = ""
    id: str = field(default_factory=lambda: _new_id("blk"))
    level: Optional[int] = None  # heading depth / list nesting
    provenance: Optional[Provenance] = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "text": self.text,
            "level": self.level,
            # explicit null when a parser truly could not attribute the block
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "meta": self.meta,
        }


@dataclass
class Table:
    """A structural view over a TABLE block: cell-level rows plus provenance."""

    rows: list[list[str]]
    block_id: str
    provenance: Optional[Provenance] = None
    markdown: str = ""

    def to_rows(self) -> list[list[str]]:
        return self.rows

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_id": self.block_id,
            "rows": self.rows,
            "provenance": self.provenance.to_dict() if self.provenance else None,
        }


@dataclass
class Document:
    """A parsed document: ordered blocks plus document-level metadata."""

    source: str
    blocks: list[Block] = field(default_factory=list)
    id: str = field(default_factory=lambda: _new_id("doc"))
    meta: dict[str, Any] = field(default_factory=dict)

    # -- construction ----------------------------------------------------------
    @classmethod
    def parse(cls, path: str) -> "Document":
        """Parse any supported file into the UDM (dispatches by extension)."""
        from ..parsers import parse as _parse  # runtime import avoids a cycle

        return _parse(path)

    def add(self, block: Block) -> Block:
        self.blocks.append(block)
        return block

    # -- structural views --------------------------------------------------------
    def blocks_of(self, *types: BlockType) -> list[Block]:
        wanted = set(types)
        return [b for b in self.blocks if b.type in wanted]

    @property
    def tables(self) -> list[Table]:
        """Cell-level table views derived from TABLE blocks (spec: first-class)."""
        return [
            Table(
                rows=b.meta.get("rows") or [],
                block_id=b.id,
                provenance=b.provenance,
                markdown=b.meta.get("markdown") or b.text,
            )
            for b in self.blocks
            if b.type == BlockType.TABLE
        ]

    def iter_sections(self) -> Iterable[tuple[str, list[Block]]]:
        """Yield ``(section_title, blocks)`` grouped by top-level headings."""
        current_title = ""
        bucket: list[Block] = []
        for b in self.blocks:
            if b.type == BlockType.HEADING and (b.level or 1) <= 1:
                if bucket:
                    yield current_title, bucket
                current_title = b.text
                bucket = [b]
            else:
                bucket.append(b)
        if bucket:
            yield current_title, bucket

    # -- exporters ------------------------------------------------------------
    def to_text(self) -> str:
        return "\n\n".join(b.text for b in self.blocks if b.text).strip() + "\n"

    def to_markdown(self, cite: bool = False) -> str:
        """Render clean Markdown; ``cite=True`` appends provenance anchors.

        Anchors are HTML comments so the Markdown stays renderable everywhere:
        ``<!-- src: report.pdf | p.7 | 3. Financials > 3.2 Revenue -->``
        """
        out: list[str] = []
        for b in self.blocks:
            if b.type == BlockType.HEADING:
                rendered = f"{'#' * max(1, b.level or 1)} {b.text}"
            elif b.type == BlockType.LIST_ITEM:
                rendered = f"{'  ' * ((b.level or 1) - 1)}- {b.text}"
            elif b.type == BlockType.CODE:
                lang = b.meta.get("language", "")
                rendered = f"```{lang}\n{b.text}\n```"
            elif b.type == BlockType.QUOTE:
                rendered = "\n".join(f"> {line}" for line in b.text.splitlines())
            elif b.type == BlockType.TABLE:
                rendered = b.meta.get("markdown") or b.text
            elif b.type == BlockType.IMAGE:
                rendered = f"![{b.text or 'image'}]({b.meta.get('src', '')})"
            elif b.type == BlockType.PAGE_BREAK:
                rendered = "\n---\n"
            elif b.text:
                rendered = b.text
            else:
                continue
            if cite and b.provenance is not None and b.type != BlockType.PAGE_BREAK:
                rendered += f" {_cite_anchor(b.provenance)}"
            out.append(rendered)
        return "\n\n".join(out).strip() + "\n"

    def to_dict(self) -> dict[str, Any]:
        return {
            "udm_version": UDM_VERSION,
            "id": self.id,
            "source": self.source,
            "metadata": self.meta,
            "blocks": [b.to_dict() for b in self.blocks],
            "tables": [t.to_dict() for t in self.tables],
        }

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def _cite_anchor(p: Provenance) -> str:
    parts = [f"src: {p.source}"]
    if p.page is not None:
        parts.append(f"p.{p.page}")
    if p.section_path:
        parts.append(p.section_path)
    return "<!-- " + " | ".join(parts) + " -->"
