"""PPTX and XLSX parsers — pure stdlib (zipfile + ElementTree).

OOXML files are zip archives of XML parts, so slides and worksheets can be
read without python-pptx/openpyxl, keeping the zero-dependency core intact.

Provenance mapping:
- PPTX: each slide number becomes ``page``; the slide title (first text run)
  becomes a level-2 heading and the slide's ``section_path``.
- XLSX: each worksheet becomes one TABLE block whose ``section_path`` is the
  sheet name from workbook.xml (``sheetN`` as fallback).
"""

from __future__ import annotations

import re
import zipfile
from xml.etree import ElementTree as ET

from ..core.model import Block, BlockType, Document, Provenance
from .base import Parser, register_parser
from .docx import _rows_to_markdown


def _numbered(names: list[str], pattern: str) -> list[str]:
    """Filter zip member names by pattern and sort by their embedded number."""
    rx = re.compile(pattern)
    hits = [n for n in names if rx.fullmatch(n)]
    return sorted(hits, key=lambda n: int(re.search(r"\d+", n.rsplit("/", 1)[-1]).group()))


def _iter_local(elem: ET.Element, localname: str):
    """Iterate descendants by local tag name, ignoring the XML namespace.

    (``Element.iter`` matches tags exactly — the ``{*}`` wildcard only works in
    find/findall — so namespace-agnostic walking needs this helper.)
    """
    for e in elem.iter():
        if e.tag.rsplit("}", 1)[-1] == localname:
            yield e


class PptxParser(Parser):
    """Each slide: first text run becomes a level-2 heading, the rest paragraphs."""

    name = "pptx"
    version = "pptx-parser/0.2"
    extensions = ("pptx",)

    def parse(self, path: str) -> Document:
        doc = Document(source=path)
        with zipfile.ZipFile(path) as z:
            slides = _numbered(z.namelist(), r"ppt/slides/slide\d+\.xml")
            doc.meta["slides"] = len(slides)
            for num, name in enumerate(slides, 1):
                root = ET.fromstring(z.read(name))
                texts: list[str] = []
                for p in _iter_local(root, "p"):  # a:p paragraphs inside shapes
                    text = "".join(t.text or "" for t in _iter_local(p, "t")).strip()
                    if text:
                        texts.append(text)
                if not texts:
                    continue
                title, *rest = texts

                def prov() -> Provenance:
                    return Provenance(source=path, page=num, section_path=title,
                                      parser=self.name, version=self.version)

                doc.add(Block(type=BlockType.HEADING, text=title, level=2,
                              provenance=prov(), meta={"slide": num}))
                for text in rest:
                    doc.add(Block(type=BlockType.PARAGRAPH, text=text,
                                  provenance=prov(), meta={"slide": num}))
        return doc


class XlsxParser(Parser):
    """Each worksheet becomes one markdown TABLE block."""

    name = "xlsx"
    version = "xlsx-parser/0.2"
    extensions = ("xlsx",)

    def parse(self, path: str) -> Document:
        doc = Document(source=path)
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            shared: list[str] = []
            if "xl/sharedStrings.xml" in names:
                root = ET.fromstring(z.read("xl/sharedStrings.xml"))
                shared = ["".join(t.text or "" for t in _iter_local(si, "t"))
                          for si in _iter_local(root, "si")]
            sheets = _numbered(names, r"xl/worksheets/sheet\d+\.xml")
            sheet_names = self._sheet_names(z, len(sheets))
            for idx, name in enumerate(sheets):
                rows = self._sheet_rows(ET.fromstring(z.read(name)), shared)
                if not rows:
                    continue
                md = _rows_to_markdown(rows)
                doc.add(
                    Block(
                        type=BlockType.TABLE,
                        text=md,
                        meta={"markdown": md, "rows": rows, "sheet": sheet_names[idx]},
                        provenance=Provenance(source=path, section_path=sheet_names[idx],
                                              parser=self.name, version=self.version),
                    )
                )
        return doc

    @staticmethod
    def _sheet_names(z: zipfile.ZipFile, count: int) -> list[str]:
        """Sheet display names from workbook.xml; ``sheetN`` when unavailable."""
        fallback = [f"sheet{i + 1}" for i in range(count)]
        if "xl/workbook.xml" not in z.namelist():
            return fallback
        try:
            root = ET.fromstring(z.read("xl/workbook.xml"))
            names = [s.get("name") or fallback[i]
                     for i, s in enumerate(_iter_local(root, "sheet"))]
        except ET.ParseError:
            return fallback
        return names if len(names) == count else fallback

    @staticmethod
    def _sheet_rows(root: ET.Element, shared: list[str]) -> list[list[str]]:
        rows: list[list[str]] = []
        for row in _iter_local(root, "row"):
            cells: list[str] = []
            for c in _iter_local(row, "c"):
                kind = c.get("t", "")
                v = next(_iter_local(c, "v"), None)
                if kind == "s" and v is not None and v.text is not None:
                    val = shared[int(v.text)] if int(v.text) < len(shared) else ""
                elif kind == "inlineStr":
                    val = "".join(t.text or "" for t in _iter_local(c, "t"))
                else:
                    val = v.text if v is not None and v.text is not None else ""
                cells.append(val)
            if any(cells):
                rows.append(cells)
        return rows


register_parser(PptxParser())
register_parser(XlsxParser())
