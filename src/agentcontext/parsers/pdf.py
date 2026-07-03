"""PDF parser for digital / text-layer PDFs (optional dependency: pypdf).

Install with:  pip install "agentcontext[pdf]"

Scanned PDFs / OCR are explicitly out of scope for v0.1 (spec); an OCR parser
arrives as a plugin in v0.2 through the same Parser protocol.
"""

from __future__ import annotations

import re

from ..core.model import Block, BlockType, Document, Provenance
from .base import Parser, register_parser


class PDFParser(Parser):
    name = "pdf"
    version = "pdf-parser/0.1"
    extensions = ("pdf",)

    def parse(self, path: str) -> Document:
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise ImportError(
                "PDF parsing needs pypdf. Install with: pip install \"agentcontext[pdf]\""
            ) from exc

        reader = PdfReader(path)
        doc = Document(source=path, meta={"pages": len(reader.pages)})
        info = getattr(reader, "metadata", None)
        if info is not None:
            doc.meta["title"] = str(info.title) if info.title else None
            doc.meta["author"] = str(info.author) if info.author else None

        for page_no, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            for para in re.split(r"\n\s*\n", text):
                para = para.strip()
                if not para:
                    continue
                doc.add(
                    Block(
                        type=BlockType.PARAGRAPH,
                        text=" ".join(para.split()),
                        provenance=Provenance(
                            source=path,
                            page=page_no,
                            # bbox/section_path stay null: text-layer extraction
                            # has no layout model in v0.1 (explicit, per spec)
                            parser=self.name,
                            version=self.version,
                            confidence=0.9,  # extracted text; OCR path would set lower
                        ),
                    )
                )
            doc.add(
                Block(
                    type=BlockType.PAGE_BREAK,
                    provenance=Provenance(source=path, page=page_no,
                                          parser=self.name, version=self.version),
                )
            )
        return doc


register_parser(PDFParser())
