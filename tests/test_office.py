"""PPTX / XLSX parser tests — fixtures built in-test as minimal OOXML zips."""

from __future__ import annotations

import zipfile

import agentcontext as ac

_A = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
_S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'


def _make_pptx(tmp_path) -> str:
    slide1 = (f'<sld {_A}><a:p><a:r><a:t>Q3 Results</a:t></a:r></a:p>'
              f'<a:p><a:r><a:t>Revenue grew 40 percent.</a:t></a:r></a:p></sld>')
    slide2 = (f'<sld {_A}><a:p><a:r><a:t>Outlook</a:t></a:r></a:p>'
              f'<a:p><a:r><a:t>We expect steady growth.</a:t></a:r></a:p></sld>')
    path = tmp_path / "deck.pptx"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("ppt/slides/slide1.xml", slide1)
        z.writestr("ppt/slides/slide2.xml", slide2)
    return str(path)


def _make_xlsx(tmp_path, with_workbook: bool = True) -> str:
    sst = (f'<sst {_S}><si><t>item</t></si><si><t>price</t></si>'
           f'<si><t>widget</t></si></sst>')
    sheet = (f'<worksheet {_S}><sheetData>'
             '<row><c t="s"><v>0</v></c><c t="s"><v>1</v></c></row>'
             '<row><c t="s"><v>2</v></c><c><v>9.99</v></c></row>'
             "</sheetData></worksheet>")
    path = tmp_path / "book.xlsx"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/sharedStrings.xml", sst)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
        if with_workbook:
            z.writestr("xl/workbook.xml",
                       f'<workbook {_S}><sheets><sheet name="Prices" sheetId="1"/></sheets></workbook>')
    return str(path)


def test_pptx_slides_headings_and_page_provenance(tmp_path):
    doc = ac.parse(_make_pptx(tmp_path))
    headings = doc.blocks_of(ac.BlockType.HEADING)
    assert [h.text for h in headings] == ["Q3 Results", "Outlook"]
    assert doc.meta["slides"] == 2
    assert headings[0].provenance.page == 1
    assert headings[1].provenance.page == 2
    # slide title doubles as the section_path for its paragraphs
    para = doc.blocks_of(ac.BlockType.PARAGRAPH)[1]
    assert para.provenance.section_path == "Outlook"
    assert para.provenance.page == 2


def test_pptx_udm_metadata(tmp_path):
    d = ac.parse(_make_pptx(tmp_path)).to_dict()
    assert d["metadata"]["parser"] == "pptx"
    assert d["metadata"]["parser_version"] == "pptx-parser/0.2"
    assert d["metadata"]["sha256"]
    for blk in d["blocks"]:
        assert blk["provenance"] is not None


def test_xlsx_sheet_to_table_with_sheet_name(tmp_path):
    doc = ac.parse(_make_xlsx(tmp_path))
    tables = doc.tables
    assert len(tables) == 1
    assert tables[0].to_rows() == [["item", "price"], ["widget", "9.99"]]
    assert tables[0].provenance.section_path == "Prices"  # from workbook.xml
    assert "| widget | 9.99 |" in tables[0].markdown
    # doc-level tables[] present in the UDM JSON too
    assert ac.parse(_make_xlsx(tmp_path)).to_dict()["tables"][0]["rows"][0] == ["item", "price"]


def test_xlsx_sheet_name_fallback(tmp_path):
    doc = ac.parse(_make_xlsx(tmp_path, with_workbook=False))
    assert doc.tables[0].provenance.section_path == "sheet1"


def test_office_extensions_registered():
    from agentcontext.core.registry import parsers
    assert "pptx" in parsers and "xlsx" in parsers
