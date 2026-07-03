"""Parser protocol, format dispatch, and shared parser utilities."""

from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod

from ..core.model import Document
from ..core.registry import parsers


class Parser(ABC):
    """Turn a source file into a :class:`Document`.

    Subclasses declare which extensions they handle and implement ``parse``.
    The protocol is deliberately tiny (spec §6): ``can_parse`` + ``parse``.
    """

    name: str = "base"
    version: str = "base/0.1"
    extensions: tuple[str, ...] = ()

    def can_parse(self, path: str) -> bool:
        return os.path.splitext(path)[1].lower().lstrip(".") in self.extensions

    @abstractmethod
    def parse(self, path: str) -> Document:  # pragma: no cover - interface
        ...


class SectionTracker:
    """Maintains a heading stack so blocks get hierarchical ``section_path``s.

    Feed it every heading (level, title); read ``path`` for the current
    location, e.g. ``"2. Methods > 2.1 Setup"``.
    """

    def __init__(self) -> None:
        self._stack: list[tuple[int, str]] = []

    def push(self, level: int, title: str) -> None:
        while self._stack and self._stack[-1][0] >= level:
            self._stack.pop()
        self._stack.append((level, title))

    @property
    def path(self) -> str | None:
        return " > ".join(title for _, title in self._stack) or None


def register_parser(parser: Parser) -> Parser:
    """Register a parser instance under each extension it handles."""
    for ext in parser.extensions:
        parsers.register(ext.lower().lstrip("."), parser)
    return parser


def get_parser_for(path: str) -> Parser:
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext not in parsers:
        raise ValueError(
            f"No parser registered for '.{ext}'. "
            f"Supported: {', '.join('.' + n for n in parsers.names())}"
        )
    return parsers.get(ext)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def parse(path: str) -> Document:
    """Parse any supported file into the Unified Document Model.

    Guarantees the spec's document-level metadata on every result:
    ``source_path``, ``sha256``, ``parser``, ``parser_version`` (plus
    ``title``/``author``/``created`` when the source format provides them —
    explicit ``None`` otherwise, never omitted).
    """
    parser = get_parser_for(path)
    doc = parser.parse(path)
    doc.meta.setdefault("title", None)
    doc.meta.setdefault("author", None)
    doc.meta.setdefault("created", None)
    doc.meta["source_path"] = os.path.abspath(path)
    doc.meta["sha256"] = _sha256(path)
    doc.meta["parser"] = parser.name
    doc.meta["parser_version"] = parser.version
    return doc
