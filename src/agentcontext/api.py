"""The agent-facing object API: one handle over the whole pipeline.

    import agentcontext as ac

    doc = ac.Doc("report.pdf")
    doc.summary()                  # extractive summary
    doc.search("revenue")          # ranked, cited chunks
    doc.context("What changed?")   # cited ContextPackage for an LLM
    doc.tables(); doc.sections()   # structural views
    doc.to_markdown()

Everything is lazy and cached: parsing happens on first access, chunking and
indexing on first search. (``Doc`` wraps the :class:`Document` data model —
the model stays a plain dataclass; the behavior lives here.)
"""

from __future__ import annotations

from typing import Optional

from .chunking import chunk as _chunk
from .context import build_context
from .core.model import Block, BlockType, Chunk, Citation, ContextPackage, Document
from .parsers import parse as _parse
from .retrieval import ScoredChunk, VectorRetriever
from .understanding import summarize as _summarize


class Doc:
    """Lazy, cached pipeline over a single source file."""

    def __init__(self, path: str, *, chunker: str = "token", embedder: str = "hashing") -> None:
        self.path = path
        self.chunker = chunker
        self.embedder = embedder
        self._document: Optional[Document] = None
        self._chunks: Optional[list[Chunk]] = None
        self._retriever: Optional[VectorRetriever] = None

    def __repr__(self) -> str:
        state = "parsed" if self._document is not None else "unparsed"
        return f"Doc({self.path!r}, {state})"

    # -- pipeline stages (lazy, cached) ---------------------------------------
    @property
    def document(self) -> Document:
        if self._document is None:
            self._document = _parse(self.path)
        return self._document

    def parse(self) -> "Doc":
        """Force parsing now. Chainable; normally implicit."""
        _ = self.document
        return self

    def chunks(self, **kwargs) -> list[Chunk]:
        if self._chunks is None or kwargs:
            chunks = _chunk(self.document, strategy=self.chunker, **kwargs)
            if kwargs:  # ad-hoc chunking: don't poison the cache
                return chunks
            self._chunks = chunks
        return self._chunks

    def _index(self) -> VectorRetriever:
        if self._retriever is None:
            self._retriever = VectorRetriever(self.embedder).index(self.chunks())
        return self._retriever

    # -- agent API -------------------------------------------------------------
    def search(self, query: str, k: int = 5) -> list[ScoredChunk]:
        """Semantic search over the document. Results carry provenance."""
        return self._index().search(query, k)

    def context(self, query: str, k: int = 5, summary: bool = False) -> ContextPackage:
        """Build a cited :class:`ContextPackage` for ``query`` — ready for an LLM."""
        pkg = build_context(
            query,
            self.search(query, k),
            documents=[self.document],
            metadata={"source": self.path, "embedder": self.embedder, "chunker": self.chunker},
        )
        if summary:
            pkg.summary = _summarize(" ".join(c.text for c in pkg.chunks))
        return pkg

    def summary(self, max_sentences: int = 3) -> str:
        """Extractive summary of the whole document."""
        return _summarize(self.document, max_sentences)

    def citations(self, query: str, k: int = 5) -> list[Citation]:
        """The citations that back an answer to ``query``."""
        return self.context(query, k).citations

    # -- structural views --------------------------------------------------------
    def tables(self) -> list[Block]:
        return self.document.blocks_of(BlockType.TABLE)

    def images(self) -> list[Block]:
        return self.document.blocks_of(BlockType.IMAGE)

    def headings(self) -> list[Block]:
        return self.document.blocks_of(BlockType.HEADING)

    def sections(self) -> list[tuple[str, list[Block]]]:
        return list(self.document.iter_sections())

    # -- exports -----------------------------------------------------------------
    def to_text(self) -> str:
        return self.document.to_text()

    def to_markdown(self) -> str:
        return self.document.to_markdown()

    def to_dict(self) -> dict:
        return self.document.to_dict()
