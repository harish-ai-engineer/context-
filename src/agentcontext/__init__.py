"""AgentContext — document parsing that never loses provenance.

Every block of output knows exactly where it came from: source page, section
path, and character span. When your agent cites something, you can prove
where it came from.

Quick start::

    from agentcontext import Document

    doc = Document.parse("report.pdf")

    doc.to_markdown()                 # clean markdown
    doc.to_json()                     # full UDM, lossless
    doc.blocks                        # iterate blocks with provenance
    doc.tables                        # structured tables
    doc.blocks[12].provenance.page    # -> 7
"""

from __future__ import annotations

from .core.model import (
    UDM_VERSION,
    Block,
    BlockType,
    Document,
    Provenance,
    Table,
)
from .parsers import Parser, parse, register_parser

__version__ = "0.1.0"

__all__ = [
    "UDM_VERSION",
    "Block",
    "BlockType",
    "Document",
    "Provenance",
    "Table",
    "Parser",
    "parse",
    "register_parser",
]
