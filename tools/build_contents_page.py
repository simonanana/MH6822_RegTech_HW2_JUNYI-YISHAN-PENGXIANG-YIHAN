from __future__ import annotations

import argparse
import copy
import shutil
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree

from build_cover_page import (
    COVER_PAGE_HEIGHT,
    COVER_PAGE_WIDTH,
    FRAME_HEIGHT,
    FRAME_WIDTH,
    el,
    make_cell,
    make_paragraph,
    make_row,
    make_table,
    qn,
)


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
V_NS = "urn:schemas-microsoft-com:vml"
NS = {"w": W_NS, "r": R_NS, "v": V_NS}

FRAME_NAVY = "0B234A"
TEXT_NAVY = "0B234A"
BOX_FILL = "F4F7FA"
BOX_BORDER = "C9D4E3"
INNER_WIDTH = 9400
TAB_POS = 9650
FRAME_BORDER_SIZE = "6"
FRAME_BORDER_SPACE = "18"
FRAME_CELL_TOP = 60
FRAME_CELL_SIDE = 570
FRAME_CELL_BOTTOM = 220
FRAME_PAGE_NUMBER_SPACER = 1620

TOC_ENTRIES = [
    ("1. Thesis and Data Lineage", "3"),
    ("2. Regulatory Framing", "4"),
    ("3. Engine Architecture", "4"),
    ("4. UPI Lookup and Codeset Validation", "5"),
    ("5. Compliance, Scope, and Conclusions", "7"),
    ("6. Prediction Market Classification Frontier", "10"),
    ("7. Proposed EventContract UPI Schema", "12"),
    ("8. Regulatory Arbitrage Analysis—Two Elements from Brandes (2026)", "13"),
    ("9. Dashboard and Deliverables", "14"),
    ("10. Engine Limits and CFTC Recommendations", "15"),
    ("11. Conclusion", "17"),
    ("References", "18"),
    ("Appendix", "19"),
]

FIGURE_ENTRIES = [
    ("Figure 1. Pipeline Architecture Diagram", "5"),
    ("Figure 2. Three-Dimensional Compliance Result", "8"),
    ("Figure 3. EventContract Classification Frontier Matrix", "11"),
    ("Figure 4a. Dashboard KPI Cards and Executive Interpretation", "15"),
    ("Figure 4b. Compliance Heatmap", "15"),
]

TABLE_ENTRIES = [
    ("Table 1. Auditable Data Chain", "3"),
    ("Table 2. Portfolio Asset-Class Distribution", "3"),
    ("Table 3. Engine Parse Status Summary", "5"),
    ("Table 4. Three-Dimensional Compliance Result Summary", "7"),
    ("Table 5. Legacy Overall Status", "8"),
    ("Table 6. Compliance Finding Frequency by Validation Rule", "8"),
    ("Table 7. Event-Contract Scope Assessment Rules", "9"),
    ("Table 8. Key Trade-Level Findings", "9"),
    ("Table 9. Event-Contract Classification Frontier Summary", "10"),
    ("Table 10. Economic Function Test for Event Contracts", "11"),
]

def set_table_border_color(table: etree._Element, color: str) -> None:
    borders = table.find("w:tblPr/w:tblBorders", namespaces=NS)
    if borders is None:
        return
    for border in borders:
        border.set(qn("w:color"), color)


def set_cell_border_color(cell: etree._Element, color: str) -> None:
    borders = cell.find("w:tcPr/w:tcBorders", namespaces=NS)
    if borders is None:
        return
    for border in borders:
        border.set(qn("w:color"), color)


def set_frame_table_geometry(table: etree._Element) -> None:
    tbl_w = table.find("w:tblPr/w:tblW", namespaces=NS)
    if tbl_w is not None:
        tbl_w.set(qn("w:w"), str(FRAME_WIDTH))
        tbl_w.set(qn("w:type"), "dxa")
    grid_col = table.find("w:tblGrid/w:gridCol", namespaces=NS)
    if grid_col is not None:
        grid_col.set(qn("w:w"), str(FRAME_WIDTH))
    first_cell_w = table.find("w:tr/w:tc/w:tcPr/w:tcW", namespaces=NS)
    if first_cell_w is not None:
        first_cell_w.set(qn("w:w"), str(FRAME_WIDTH))
        first_cell_w.set(qn("w:type"), "dxa")
    tr_height = table.find("w:tr/w:trPr/w:trHeight", namespaces=NS)
    if tr_height is not None:
        tr_height.set(qn("w:val"), str(FRAME_HEIGHT))
        tr_height.set(qn("w:hRule"), "exact")


def restyle_existing_cover_frame(root: etree._Element) -> None:
    body = root.find("w:body", namespaces=NS)
    if body is None or len(body) == 0:
        raise ValueError("Could not find document body.")
    cover_table = body[0]
    if cover_table.tag != qn("w:tbl"):
        raise ValueError("Expected the cover frame table as the first body element.")
    set_frame_table_geometry(cover_table)
    set_table_border_color(cover_table, FRAME_NAVY)


def append_tabs(paragraph: etree._Element, *, position: int = TAB_POS) -> None:
    p_pr = paragraph.find("w:pPr", namespaces=NS)
    if p_pr is None:
        p_pr = el("w:pPr")
        paragraph.insert(0, p_pr)
    tabs = el("w:tabs")
    tabs.append(el("w:tab", val="right", leader="dot", pos=str(position)))
    p_pr.append(tabs)


def make_toc_entry(text: str, page: str) -> etree._Element:
    paragraph = make_paragraph(
        align="left",
        before=0,
        after=16,
        line=236,
        line_rule="exact",
        font="Georgia",
        size=25,
        color=TEXT_NAVY,
    )
    append_tabs(paragraph)
    paragraph.append(make_text_run(text, size=25))
    paragraph.append(make_tab_run())
    paragraph.append(make_text_run(page, size=25))
    return paragraph


def make_text_run(text: str, *, size: int, bold: bool = False) -> etree._Element:
    run = el("w:r")
    r_pr = el("w:rPr")
    r_pr.append(el("w:rFonts", ascii="Georgia", hAnsi="Georgia", eastAsia="Georgia", cs="Georgia"))
    if bold:
        r_pr.append(el("w:b"))
    r_pr.append(el("w:color", val=TEXT_NAVY))
    r_pr.append(el("w:sz", val=str(size)))
    r_pr.append(el("w:szCs", val=str(size)))
    run.append(r_pr)
    text_node = el("w:t")
    if text.startswith(" ") or text.endswith(" "):
        text_node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    text_node.text = text
    run.append(text_node)
    return run


def make_tab_run() -> etree._Element:
    run = el("w:r")
    run.append(el("w:tab"))
    return run


def make_heading(text: str, *, title: bool = False) -> etree._Element:
    return make_paragraph(
        text,
        align="left",
        before=20 if title else 150,
        after=8 if title else 6,
        line=308 if title else 242,
        line_rule="exact",
        font="Georgia",
        size=53 if title else 35,
        color=TEXT_NAVY,
        bold=True,
    )


def make_contents_nodes() -> list[etree._Element]:
    nodes: list[etree._Element] = [make_heading("Table of Contents", title=True)]
    for text, page in TOC_ENTRIES:
        nodes.append(make_toc_entry(text, page))
    nodes.append(make_heading("List of Figures"))
    for text, page in FIGURE_ENTRIES:
        nodes.append(make_toc_entry(text, page))
    nodes.append(make_heading("List of Tables"))
    for text, page in TABLE_ENTRIES:
        nodes.append(make_toc_entry(text, page))
    return nodes


def make_contents_frame_table() -> etree._Element:
    table = make_table(
        width=FRAME_WIDTH,
        grid_widths=[FRAME_WIDTH],
        alignment="center",
        cell_margins={
            "top": FRAME_CELL_TOP,
            "left": FRAME_CELL_SIDE,
            "bottom": FRAME_CELL_BOTTOM,
            "right": FRAME_CELL_SIDE,
        },
    )
    cell = make_cell(FRAME_WIDTH, valign="top")
    cell.append(make_page_frame_shape_paragraph())
    for node in make_contents_nodes():
        cell.append(node)
    cell.append(
        make_paragraph(
            "2",
            align="center",
            before=FRAME_PAGE_NUMBER_SPACER,
            after=0,
            line=220,
            line_rule="exact",
            font="Georgia",
            size=20,
            color=TEXT_NAVY,
        )
    )
    cell.append(make_paragraph(line=1, line_rule="exact"))
    table.append(make_row(FRAME_HEIGHT, [cell]))
    return table


def make_page_frame_shape_paragraph() -> etree._Element:
    paragraph = make_paragraph(line=1, line_rule="exact")
    run = el("w:r")
    pict = etree.Element(qn("w:pict"))
    rect = etree.Element(f"{{{V_NS}}}rect")
    rect.set("id", "tocPageFrame")
    rect.set("stroked", "t")
    rect.set("strokecolor", f"#{FRAME_NAVY}")
    rect.set("strokeweight", "1pt")
    rect.set("filled", "f")
    rect.set(
        "style",
        "position:absolute;"
        "margin-left:0pt;"
        "margin-top:0pt;"
        "width:559pt;"
        "height:806pt;"
        "z-index:-251654144;"
        "mso-position-horizontal-relative:page;"
        "mso-position-vertical-relative:page;",
    )
    pict.append(rect)
    run.append(pict)
    paragraph.append(run)
    return paragraph


def make_contents_section_properties(portrait_body_sect_pr: etree._Element) -> etree._Element:
    sect_pr = copy.deepcopy(portrait_body_sect_pr)

    for section_child in list(sect_pr):
        if section_child.tag in {qn("w:headerReference"), qn("w:footerReference"), qn("w:titlePg")}:
            sect_pr.remove(section_child)
    sect_pr.append(el("w:titlePg"))

    pg_sz = sect_pr.find("w:pgSz", namespaces=NS)
    if pg_sz is None:
        pg_sz = el("w:pgSz")
        sect_pr.insert(0, pg_sz)
    pg_sz.set(qn("w:w"), str(COVER_PAGE_WIDTH))
    pg_sz.set(qn("w:h"), str(COVER_PAGE_HEIGHT))
    if qn("w:orient") in pg_sz.attrib:
        del pg_sz.attrib[qn("w:orient")]

    pg_borders = sect_pr.find("w:pgBorders", namespaces=NS)
    if pg_borders is not None:
        sect_pr.remove(pg_borders)
    pg_borders = el("w:pgBorders", offsetFrom="page")
    for side in ("top", "left", "bottom", "right"):
        pg_borders.append(
            el(
                f"w:{side}",
                val="single",
                sz=FRAME_BORDER_SIZE,
                space=FRAME_BORDER_SPACE,
                color=FRAME_NAVY,
            )
        )
    sect_pr.append(pg_borders)

    pg_mar = sect_pr.find("w:pgMar", namespaces=NS)
    if pg_mar is not None:
        # Match the cover-page frame geometry; the table cell handles the inner inset.
        pg_mar.set(qn("w:top"), "360")
        pg_mar.set(qn("w:right"), "360")
        pg_mar.set(qn("w:bottom"), "360")
        pg_mar.set(qn("w:left"), "360")

    section_type = sect_pr.find("w:type", namespaces=NS)
    if section_type is None:
        section_type = el("w:type", val="nextPage")
        sect_pr.insert(0, section_type)
    else:
        section_type.set(qn("w:val"), "nextPage")
    return sect_pr


def make_section_break_paragraph(sect_pr: etree._Element) -> etree._Element:
    paragraph = el("w:p")
    p_pr = el("w:pPr")
    p_pr.append(el("w:spacing", before="0", after="0", line="1", lineRule="exact"))
    p_pr.append(sect_pr)
    paragraph.append(p_pr)
    return paragraph


def find_portrait_body_section(root: etree._Element) -> etree._Element:
    for sect_pr in root.findall(".//w:sectPr", namespaces=NS):
        pg_sz = sect_pr.find("w:pgSz", namespaces=NS)
        if pg_sz is None:
            continue
        width = pg_sz.get(qn("w:w"))
        height = pg_sz.get(qn("w:h"))
        orient = pg_sz.get(qn("w:orient"))
        pg_mar = sect_pr.find("w:pgMar", namespaces=NS)
        top = pg_mar.get(qn("w:top")) if pg_mar is not None else None
        if width == "11906" and height == "16838" and orient is None and top == "1134":
            return sect_pr
    raise ValueError("Could not find the portrait body section properties.")


def looks_like_toc_node(node: etree._Element) -> bool:
    text = "".join(node.xpath(".//w:t/text()", namespaces=NS))
    return "Table of Contents" in text and "List of Figures" in text and "List of Tables" in text


def replace_toc_and_split_section(root: etree._Element) -> None:
    body = root.find("w:body", namespaces=NS)
    if body is None:
        raise ValueError("Could not find document body.")

    portrait_body_sect_pr = find_portrait_body_section(root)
    body_children = list(body)
    toc_index = None
    toc_end_index = None
    for index, child in enumerate(body_children):
        if looks_like_toc_node(child):
            toc_index = index
            toc_end_index = index + 1
            break
        text = "".join(child.xpath(".//w:t/text()", namespaces=NS)).strip()
        if text == "Table of Contents":
            toc_index = index
            for end_index in range(index + 1, len(body_children)):
                if body_children[end_index].find("w:pPr/w:sectPr", namespaces=NS) is not None:
                    toc_end_index = end_index
                    break
            break
    if toc_index is None or toc_end_index is None:
        raise ValueError("Could not find the existing contents block.")

    for child in body_children[toc_index:toc_end_index]:
        body.remove(child)
    contents_frame = make_contents_frame_table()
    body.insert(toc_index, contents_frame)

    break_index = toc_index + 1
    next_child = body[break_index] if break_index < len(body) else None
    toc_sect_pr = make_contents_section_properties(portrait_body_sect_pr)
    if next_child is None or next_child.find("w:pPr/w:sectPr", namespaces=NS) is None:
        body.insert(break_index, make_section_break_paragraph(toc_sect_pr))
    else:
        p_pr = next_child.find("w:pPr", namespaces=NS)
        old_sect_pr = p_pr.find("w:sectPr", namespaces=NS) if p_pr is not None else None
        if p_pr is not None and old_sect_pr is not None:
            p_pr.remove(old_sect_pr)
            p_pr.append(toc_sect_pr)


def build_contents_page(input_path: Path, output_path: Path) -> None:
    with ZipFile(input_path) as source_zip:
        root = etree.fromstring(source_zip.read("word/document.xml"))
        restyle_existing_cover_frame(root)
        replace_toc_and_split_section(root)

        new_document_xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            with ZipFile(tmp_path, "w", compression=ZIP_DEFLATED) as target_zip:
                for item in source_zip.infolist():
                    data = new_document_xml if item.filename == "word/document.xml" else source_zip.read(item.filename)
                    target_zip.writestr(item, data)
            shutil.move(tmp_path, output_path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild the report contents page and isolate it from the body section.")
    parser.add_argument("input_docx", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_contents_page(args.input_docx, args.out)
    print(args.out)


if __name__ == "__main__":
    main()
