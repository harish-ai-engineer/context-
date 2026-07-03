"""v0.1 spec-compliance tests for the Unified Document Model and parsers.

Covers the spec's hard rules: explicit-null provenance, udm_version, document
metadata (sha256/parser_version), hierarchical section_path, first-class
tables[], citation anchors, the Parser protocol, and the SDK surface.
All offline; only stdlib parsers exercised.
"""

from __future__ import annotations

import json

import agentcontext as ac
from agentcontext.parsers import get_parser_for


SAMPLE_MD = """\
# 1. Overview

Intro paragraph.

## 1.1 Goals

Goals paragraph here.

# 2. Methods

## 2.1 Setup

Setup details paragraph.
"""


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


# ------------------------------------------------------------- UDM rules --

def test_udm_version_present(tmp_path):
    doc = ac.parse(_write(tmp_path, "a.md", SAMPLE_MD))
    d = doc.to_dict()
    assert d["udm_version"] == ac.UDM_VERSION == "0.1"


def test_provenance_explicit_nulls_never_omitted(tmp_path):
    """Spec: unknown provenance fields are explicit null, never omitted."""
    doc = ac.parse(_write(tmp_path, "a.md", SAMPLE_MD))
    d = doc.to_dict()
    for blk in d["blocks"]:
        assert "provenance" in blk  # key always present
        prov = blk["provenance"]
        assert prov is not None  # md parser attributes every block
        # every provenance field serialized, including the null ones
        assert set(prov) == {
            "source", "page", "section_path", "bbox", "char_span",
            "confidence", "parser", "version",
        }
        assert prov["page"] is None  # markdown has no pages -> explicit null
        assert blk["level"] is not None or blk["level"] is None  # key present


def test_document_metadata_complete(tmp_path):
    path = _write(tmp_path, "a.md", SAMPLE_MD)
    meta = ac.parse(path).to_dict()["metadata"]
    assert meta["sha256"] and len(meta["sha256"]) == 64
    assert meta["source_path"].endswith("a.md")
    assert meta["parser"] == "markdown"
    assert meta["parser_version"] == "md-parser/0.1"
    # title/author/created present as explicit nulls when unknown
    assert "title" in meta and "author" in meta and "created" in meta


def test_section_path_is_hierarchical(tmp_path):
    doc = ac.parse(_write(tmp_path, "a.md", SAMPLE_MD))
    paras = [b for b in doc.blocks if b.type == ac.BlockType.PARAGRAPH]
    assert paras[0].provenance.section_path == "1. Overview"
    assert paras[1].provenance.section_path == "1. Overview > 1.1 Goals"
    assert paras[2].provenance.section_path == "2. Methods > 2.1 Setup"


def test_html_section_path(tmp_path):
    path = _write(tmp_path, "a.html",
                  "<h1>Guide</h1><h2>Install</h2><p>pip install it</p>")
    doc = ac.parse(path)
    para = doc.blocks_of(ac.BlockType.PARAGRAPH)[0]
    assert para.provenance.section_path == "Guide > Install"


def test_text_parser_char_span(tmp_path):
    path = _write(tmp_path, "a.txt", "First para.\n\nSecond para.")
    doc = ac.parse(path)
    spans = [b.provenance.char_span for b in doc.blocks]
    assert spans[0] == (0, 11)
    assert all(s is not None for s in spans)


# -------------------------------------------------------- tables first-class --

def test_tables_first_class(tmp_path):
    """Tables appear inline as blocks AND in tables[] with cell structure."""
    doc = ac.Document(source="x")
    md = "| a | b |\n| --- | --- |\n| 1 | 2 |"
    doc.add(ac.Block(
        type=ac.BlockType.TABLE, text=md,
        meta={"markdown": md, "rows": [["a", "b"], ["1", "2"]]},
        provenance=ac.Provenance(source="x", page=3),
    ))
    tables = doc.tables
    assert len(tables) == 1
    assert tables[0].to_rows() == [["a", "b"], ["1", "2"]]
    assert tables[0].provenance.page == 3

    d = doc.to_dict()
    assert len(d["tables"]) == 1  # doc-level tables[]
    assert d["tables"][0]["rows"] == [["a", "b"], ["1", "2"]]
    assert d["blocks"][0]["type"] == "table"  # still inline as a block


# ------------------------------------------------------------- SDK surface --

def test_document_parse_classmethod(tmp_path):
    path = _write(tmp_path, "a.md", SAMPLE_MD)
    doc = ac.Document.parse(path)
    assert isinstance(doc, ac.Document)
    assert doc.blocks


def test_to_json_roundtrip(tmp_path):
    doc = ac.Document.parse(_write(tmp_path, "a.md", SAMPLE_MD))
    parsed = json.loads(doc.to_json())
    assert parsed["udm_version"] == "0.1"
    assert len(parsed["blocks"]) == len(doc.blocks)


def test_markdown_cite_anchors(tmp_path):
    doc = ac.Document.parse(_write(tmp_path, "a.md", SAMPLE_MD))
    plain = doc.to_markdown()
    cited = doc.to_markdown(cite=True)
    assert "<!--" not in plain
    assert "<!-- src:" in cited
    assert "2. Methods > 2.1 Setup -->" in cited


def test_parser_protocol_can_parse(tmp_path):
    path = _write(tmp_path, "a.md", "# hi")
    parser = get_parser_for(path)
    assert parser.can_parse(path)
    assert not parser.can_parse("report.pdf")
    assert parser.version == "md-parser/0.1"


def test_unsupported_extension_message(tmp_path):
    try:
        ac.parse(str(tmp_path / "a.xyz"))
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert ".xyz" in str(exc) and "Supported" in str(exc)


# --------------------------------------------------------------------- CLI --

def test_cli_writes_markdown_next_to_source(tmp_path):
    from agentcontext.cli import main
    path = _write(tmp_path, "doc.txt", "Hello world.\n\nSecond paragraph.")
    assert main(["parse", path]) == 0
    out = tmp_path / "doc.md"
    assert "Hello world." in out.read_text(encoding="utf-8")


def test_cli_never_clobbers_source(tmp_path):
    from agentcontext.cli import main
    path = _write(tmp_path, "doc.md", SAMPLE_MD)
    assert main(["parse", path]) == 0
    # .md source stays untouched; output goes to .parsed.md
    assert (tmp_path / "doc.md").read_text(encoding="utf-8") == SAMPLE_MD
    assert (tmp_path / "doc.parsed.md").read_text(encoding="utf-8").startswith("# 1. Overview")


def test_cli_json_output(tmp_path):
    from agentcontext.cli import main
    path = _write(tmp_path, "doc.md", SAMPLE_MD)
    assert main(["parse", path, "--json"]) == 0
    data = json.loads((tmp_path / "doc.json").read_text(encoding="utf-8"))
    assert data["udm_version"] == "0.1"
    assert data["metadata"]["sha256"]


def test_cli_cite_inline(tmp_path):
    from agentcontext.cli import main
    path = _write(tmp_path, "doc.md", SAMPLE_MD)
    assert main(["parse", path, "--cite", "inline"]) == 0
    assert "<!-- src:" in (tmp_path / "doc.parsed.md").read_text(encoding="utf-8")
