"""Phase-1 completion tests: data/office parsers, Doc agent API, summarize, CLI.

All offline, stdlib-only fixtures — PPTX/XLSX files are built in-test as
minimal OOXML zips.
"""

from __future__ import annotations

import json
import zipfile

import agentcontext as ac
from agentcontext.cli import build_parser
from agentcontext.understanding import summarize


# ---------------------------------------------------------------- fixtures --

def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def _make_pptx(tmp_path) -> str:
    """Minimal two-slide pptx: just the slide XML parts matter to the parser."""
    ns = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
    slide1 = f'<sld {ns}><a:p><a:r><a:t>Q3 Results</a:t></a:r></a:p>' \
             f'<a:p><a:r><a:t>Revenue grew 40 percent.</a:t></a:r></a:p></sld>'
    slide2 = f'<sld {ns}><a:p><a:r><a:t>Outlook</a:t></a:r></a:p>' \
             f'<a:p><a:r><a:t>We expect steady growth.</a:t></a:r></a:p></sld>'
    path = tmp_path / "deck.pptx"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("ppt/slides/slide1.xml", slide1)
        z.writestr("ppt/slides/slide2.xml", slide2)
    return str(path)


def _make_xlsx(tmp_path) -> str:
    """Minimal one-sheet xlsx with shared strings."""
    sst = (
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<si><t>item</t></si><si><t>price</t></si><si><t>widget</t></si></sst>"
    )
    sheet = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        '<row><c t="s"><v>0</v></c><c t="s"><v>1</v></c></row>'
        '<row><c t="s"><v>2</v></c><c><v>9.99</v></c></row>'
        "</sheetData></worksheet>"
    )
    path = tmp_path / "book.xlsx"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/sharedStrings.xml", sst)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return str(path)


SAMPLE_MD = """\
# Refund Policy

Customers may request a full refund within 30 days of purchase. Refunds are
processed to the original payment method within five business days.

# Shipping

Orders ship within two business days. International shipping can take up to
three weeks depending on customs.
"""


# ------------------------------------------------------------ data parsers --

def test_csv_parser_builds_table(tmp_path):
    path = _write(tmp_path, "prices.csv", "item,price\nwidget,9.99\ngadget,19.99\n")
    doc = ac.parse(path)
    tables = doc.blocks_of(ac.BlockType.TABLE)
    assert len(tables) == 1
    assert tables[0].meta["rows"][0] == ["item", "price"]
    assert "| widget | 9.99 |" in tables[0].text


def test_json_parser_flattens_leaves(tmp_path):
    path = _write(tmp_path, "cfg.json", json.dumps(
        {"server": {"host": "localhost", "ports": [80, 443]}, "debug": True}
    ))
    doc = ac.parse(path)
    text = doc.to_text()
    assert "server.host: localhost" in text
    assert "server.ports[1]: 443" in text
    assert "debug: True" in text


def test_jsonl_parser(tmp_path):
    path = _write(tmp_path, "log.jsonl", '{"event": "start"}\n{"event": "stop"}\n')
    doc = ac.parse(path)
    assert len(doc.blocks) == 2
    assert "event: start" in doc.blocks[0].text


def test_xml_parser(tmp_path):
    path = _write(tmp_path, "feed.xml",
                  "<feed><entry>First post here</entry><entry>Second post</entry></feed>")
    doc = ac.parse(path)
    assert [b.text for b in doc.blocks] == ["First post here", "Second post"]
    assert doc.blocks[0].meta["tag"] == "entry"


# ---------------------------------------------------------- office parsers --

def test_pptx_parser(tmp_path):
    doc = ac.parse(_make_pptx(tmp_path))
    headings = doc.blocks_of(ac.BlockType.HEADING)
    assert [h.text for h in headings] == ["Q3 Results", "Outlook"]
    assert doc.meta["slides"] == 2
    # provenance carries the slide number as the page
    assert headings[0].provenance.page == 1
    assert headings[1].provenance.page == 2


def test_xlsx_parser(tmp_path):
    doc = ac.parse(_make_xlsx(tmp_path))
    tables = doc.blocks_of(ac.BlockType.TABLE)
    assert len(tables) == 1
    assert tables[0].meta["rows"] == [["item", "price"], ["widget", "9.99"]]
    assert "| widget | 9.99 |" in tables[0].text


# -------------------------------------------------------------- summarize --

def test_summarize_picks_top_sentences():
    text = (
        "Revenue grew fast. Revenue growth came from the new revenue product line. "
        "The office cat slept. Weather was mild. Revenue will keep growing next year."
    )
    out = summarize(text, max_sentences=2)
    assert "Revenue" in out
    assert "cat" not in out


def test_summarize_short_text_passthrough():
    assert summarize("One sentence only.", max_sentences=3) == "One sentence only."


# ---------------------------------------------------------------- Doc API --

def test_doc_api_end_to_end(tmp_path):
    path = _write(tmp_path, "doc.md", SAMPLE_MD)
    doc = ac.Doc(path)
    assert "unparsed" in repr(doc)

    results = doc.search("refund my money", k=2)
    assert results and "refund" in results[0].chunk.text.lower()

    pkg = doc.context("refund policy", k=1, summary=True)
    assert isinstance(pkg, ac.ContextPackage)
    assert pkg.citations and pkg.citations[0].source == path
    assert pkg.summary  # summary=True filled it

    assert doc.summary(2)
    assert len(doc.headings()) == 2
    assert len(doc.sections()) == 2
    assert doc.citations("shipping time")
    assert doc.to_markdown().startswith("# Refund Policy")
    assert "parsed" in repr(doc)


def test_doc_api_tables(tmp_path):
    path = _write(tmp_path, "prices.csv", "item,price\nwidget,9.99\n")
    doc = ac.Doc(path)
    assert len(doc.tables()) == 1


# --------------------------------------------------------------------- CLI --

def test_cli_has_all_phase1_commands():
    parser = build_parser()
    sub = next(a for a in parser._actions if hasattr(a, "choices") and a.choices)
    assert {"parse", "chunk", "search", "summarize", "context"} <= set(sub.choices)


def test_cli_search_and_summarize_run(tmp_path, capsys=None):
    path = _write(tmp_path, "doc.md", SAMPLE_MD)
    from agentcontext.cli import main
    assert main(["search", "refund", "--docs", path, "--k", "1"]) == 0
    assert main(["summarize", path, "--sentences", "1"]) == 0
    assert main(["chunk", path, "--strategy", "section"]) == 0
