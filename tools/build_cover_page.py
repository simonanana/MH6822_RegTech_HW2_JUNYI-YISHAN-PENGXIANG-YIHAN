from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}

NAVY = "0B234A"
INK = "23364D"
MUTED = "3F4854"
GRID = "D6DCE5"
ALT = "F4F6F8"
WHITE = "FFFFFF"

COVER_PAGE_WIDTH = 11906
COVER_PAGE_HEIGHT = 16838
COVER_MARGIN = 360
FRAME_WIDTH = COVER_PAGE_WIDTH - (2 * COVER_MARGIN)
FRAME_HEIGHT = 15800
LAYOUT_WIDTH = 10600
STUDENT_TABLE_WIDTHS = [3810, 4830]


def qn(tag: str) -> str:
    prefix, local = tag.split(":")
    if prefix != "w":
        raise ValueError(f"Unsupported prefix: {prefix}")
    return f"{{{W_NS}}}{local}"


def el(tag: str, **attrs: str) -> etree._Element:
    node = etree.Element(qn(tag))
    for key, value in attrs.items():
        node.set(qn(f"w:{key}"), str(value))
    return node


def remove_children(parent: etree._Element, tag: str) -> None:
    for child in list(parent):
        if child.tag == qn(tag):
            parent.remove(child)


def append_rpr(
    run: etree._Element,
    *,
    font: str,
    size: int,
    color: str,
    bold: bool = False,
) -> None:
    r_pr = el("w:rPr")
    fonts = el("w:rFonts", ascii=font, hAnsi=font, eastAsia=font, cs=font)
    r_pr.append(fonts)
    if bold:
        r_pr.append(el("w:b"))
    r_pr.append(el("w:color", val=color))
    r_pr.append(el("w:sz", val=str(size)))
    r_pr.append(el("w:szCs", val=str(size)))
    run.append(r_pr)


def make_run(text: str, *, font: str, size: int, color: str, bold: bool = False) -> etree._Element:
    run = el("w:r")
    append_rpr(run, font=font, size=size, color=color, bold=bold)
    text_node = el("w:t")
    if text.startswith(" ") or text.endswith(" "):
        text_node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    text_node.text = text
    run.append(text_node)
    return run


def make_paragraph(
    text: str = "",
    *,
    align: str = "left",
    before: int = 0,
    after: int = 0,
    line: int = 240,
    line_rule: str = "auto",
    font: str = "Georgia",
    size: int = 22,
    color: str = INK,
    bold: bool = False,
) -> etree._Element:
    paragraph = el("w:p")
    p_pr = el("w:pPr")
    p_pr.append(el("w:spacing", before=str(before), after=str(after), line=str(line), lineRule=line_rule))
    p_pr.append(el("w:jc", val=align))
    paragraph.append(p_pr)
    if text:
        paragraph.append(make_run(text, font=font, size=size, color=color, bold=bold))
    return paragraph


def set_cell_width(cell: etree._Element, width: int) -> None:
    tc_pr = cell.find("w:tcPr", namespaces=NS)
    if tc_pr is None:
        tc_pr = el("w:tcPr")
        cell.insert(0, tc_pr)
    tc_pr.append(el("w:tcW", w=str(width), type="dxa"))


def set_cell_shading(cell: etree._Element, fill: str) -> None:
    tc_pr = cell.find("w:tcPr", namespaces=NS)
    if tc_pr is None:
        tc_pr = el("w:tcPr")
        cell.insert(0, tc_pr)
    tc_pr.append(el("w:shd", val="clear", color="auto", fill=fill))


def set_cell_borders(cell: etree._Element, color: str = GRID, size: int = 4) -> None:
    tc_pr = cell.find("w:tcPr", namespaces=NS)
    if tc_pr is None:
        tc_pr = el("w:tcPr")
        cell.insert(0, tc_pr)
    borders = el("w:tcBorders")
    for side in ("top", "left", "bottom", "right"):
        borders.append(el(f"w:{side}", val="single", color=color, sz=str(size), space="0"))
    tc_pr.append(borders)


def make_cell(
    width: int,
    *,
    valign: str = "top",
    shading: str | None = None,
    borders: bool = False,
) -> etree._Element:
    cell = el("w:tc")
    tc_pr = el("w:tcPr")
    tc_pr.append(el("w:tcW", w=str(width), type="dxa"))
    tc_pr.append(el("w:vAlign", val=valign))
    cell.append(tc_pr)
    if shading:
        set_cell_shading(cell, shading)
    if borders:
        set_cell_borders(cell)
    return cell


def make_row(height: int, cells: list[etree._Element], *, valign: str | None = None) -> etree._Element:
    row = el("w:tr")
    tr_pr = el("w:trPr")
    tr_pr.append(el("w:cantSplit"))
    tr_pr.append(el("w:trHeight", val=str(height), hRule="exact"))
    tr_pr.append(el("w:jc", val="center"))
    row.append(tr_pr)
    for cell in cells:
        if valign is not None:
            tc_pr = cell.find("w:tcPr", namespaces=NS)
            if tc_pr is not None:
                existing = tc_pr.find("w:vAlign", namespaces=NS)
                if existing is not None:
                    tc_pr.remove(existing)
                tc_pr.append(el("w:vAlign", val=valign))
        row.append(cell)
    return row


def make_table(
    *,
    width: int,
    grid_widths: list[int],
    alignment: str = "center",
    borders: dict[str, tuple[str, int]] | None = None,
    cell_margins: dict[str, int] | None = None,
) -> etree._Element:
    table = el("w:tbl")
    tbl_pr = el("w:tblPr")
    tbl_pr.append(el("w:tblW", w=str(width), type="dxa"))
    tbl_pr.append(el("w:jc", val=alignment))
    tbl_pr.append(el("w:tblLayout", type="fixed"))

    if borders is not None:
        tbl_borders = el("w:tblBorders")
        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            style, size = borders.get(side, ("nil", 0))
            tbl_borders.append(el(f"w:{side}", val=style, color=NAVY, sz=str(size), space="0"))
        tbl_pr.append(tbl_borders)

    if cell_margins is not None:
        margins = el("w:tblCellMar")
        for side in ("top", "left", "bottom", "right"):
            margins.append(el(f"w:{side}", w=str(cell_margins.get(side, 0)), type="dxa"))
        tbl_pr.append(margins)

    table.append(tbl_pr)
    grid = el("w:tblGrid")
    for grid_width in grid_widths:
        grid.append(el("w:gridCol", w=str(grid_width)))
    table.append(grid)
    return table


def make_short_rule_table() -> etree._Element:
    table = make_table(
        width=1944,
        grid_widths=[1944],
        alignment="left",
        borders={"bottom": ("single", 10)},
        cell_margins={"top": 0, "left": 0, "bottom": 0, "right": 0},
    )
    cell = make_cell(1944, valign="top")
    cell.append(make_paragraph(line=1, line_rule="exact"))
    table.append(make_row(18, [cell]))
    return table


def make_student_table() -> etree._Element:
    table = make_table(
        width=sum(STUDENT_TABLE_WIDTHS),
        grid_widths=STUDENT_TABLE_WIDTHS,
        alignment="center",
        borders={side: ("single", 4) for side in ("top", "left", "bottom", "right", "insideH", "insideV")},
        cell_margins={"top": 95, "left": 125, "bottom": 95, "right": 125},
    )
    rows = [
        ("Student ID", "Name", NAVY, WHITE, True, "Georgia"),
        ("G2505246J", "LIU YISHAN", WHITE, INK, False, "Times New Roman"),
        ("G2505431H", "GONG PENG XIANG", ALT, INK, False, "Times New Roman"),
        ("G2506255B", "GUO YIHAN", WHITE, INK, False, "Times New Roman"),
        ("G2505266E", "ZHANG JUNYI", ALT, INK, False, "Times New Roman"),
    ]
    for index, (student_id, name, fill, color, bold, id_font) in enumerate(rows):
        id_cell = make_cell(STUDENT_TABLE_WIDTHS[0], valign="center", shading=fill, borders=True)
        name_cell = make_cell(STUDENT_TABLE_WIDTHS[1], valign="center", shading=fill, borders=True)
        id_cell.append(
            make_paragraph(
                student_id,
                align="center",
                font=id_font if index > 0 else "Georgia",
                size=22,
                color=color,
                bold=bold,
            )
        )
        name_cell.append(
            make_paragraph(
                name,
                align="center",
                font="Georgia",
                size=22,
                color=color,
                bold=bold,
            )
        )
        table.append(make_row(450, [id_cell, name_cell]))
    return table


def make_layout_table() -> etree._Element:
    table = make_table(
        width=LAYOUT_WIDTH,
        grid_widths=[LAYOUT_WIDTH],
        alignment="center",
        borders={},
        cell_margins={"top": 0, "left": 0, "bottom": 0, "right": 0},
    )

    # Header block.
    cell = make_cell(LAYOUT_WIDTH, valign="top")
    cell.append(make_paragraph("Nanyang Technological University", before=72, after=34, font="Georgia", size=33, color=NAVY, bold=True))
    cell.append(make_paragraph("MH6822 Assignment 2 | Regulatory Technology", after=24, font="Georgia", size=24, color=MUTED))
    cell.append(make_short_rule_table())
    cell.append(make_paragraph(line=1, line_rule="exact"))
    table.append(make_row(2088, [cell]))

    # Spacer.
    cell = make_cell(LAYOUT_WIDTH, valign="center")
    cell.append(make_paragraph(line=1, line_rule="exact"))
    table.append(make_row(533, [cell]))

    # Title.
    cell = make_cell(LAYOUT_WIDTH, valign="top")
    for line in (
        "OTC Derivatives Trade Reporting",
        "Compliance Engine and Prediction",
        "Market Classification Frontier",
    ):
        cell.append(
            make_paragraph(
                line,
                align="center",
                line=800,
                line_rule="exact",
                font="Georgia",
                size=44,
                color=NAVY,
                bold=True,
            )
        )
    table.append(make_row(2592, [cell]))

    # Spacer.
    cell = make_cell(LAYOUT_WIDTH, valign="center")
    cell.append(make_paragraph(line=1, line_rule="exact"))
    table.append(make_row(670, [cell]))

    # Explainer text, deliberately two paragraphs instead of a manual break.
    cell = make_cell(LAYOUT_WIDTH, valign="top")
    cell.append(
        make_paragraph(
            "A rule-based RegTech pipeline for UPI, UTI, LEI, and CFTC/EMIR validation",
            align="center",
            line=420,
            line_rule="exact",
            font="Georgia",
            size=28,
            color=MUTED,
        )
    )
    cell.append(
        make_paragraph(
            "with EventContract classification analysis",
            align="center",
            line=420,
            line_rule="exact",
            font="Georgia",
            size=28,
            color=MUTED,
        )
    )
    table.append(make_row(1372, [cell]))

    # Scope lines.
    cell = make_cell(LAYOUT_WIDTH, valign="top")
    cell.append(
        make_paragraph(
            "UPI / UTI / LEI validation · CFTC / EMIR reporting logic · T026–T028 EventContract frontier",
            align="center",
            after=10,
            font="Georgia",
            size=19,
            color=INK,
        )
    )
    cell.append(
        make_paragraph(
            "Data quality · Reporting scope · Regulatory conclusion · Rule-based engine · Dashboard · Final report",
            align="center",
            after=10,
            font="Georgia",
            size=19,
            color=INK,
        )
    )
    table.append(make_row(881, [cell]))

    # Spacer.
    cell = make_cell(LAYOUT_WIDTH, valign="center")
    cell.append(make_paragraph(line=1, line_rule="exact"))
    table.append(make_row(1584, [cell]))

    # Prepared by.
    cell = make_cell(LAYOUT_WIDTH, valign="top")
    cell.append(make_paragraph("Prepared by", align="center", font="Georgia", size=35, color=NAVY, bold=True))
    table.append(make_row(504, [cell]))

    # Student table.
    cell = make_cell(LAYOUT_WIDTH, valign="center")
    cell.append(make_student_table())
    cell.append(make_paragraph(line=1, line_rule="exact"))
    table.append(make_row(3240, [cell]))

    # Tight spacer.
    cell = make_cell(LAYOUT_WIDTH, valign="center")
    cell.append(make_paragraph(line=1, line_rule="exact"))
    table.append(make_row(216, [cell]))

    # Footer.
    cell = make_cell(LAYOUT_WIDTH, valign="top")
    cell.append(
        make_paragraph(
            "Regulatory Technology   |   May 2026",
            align="center",
            font="Georgia",
            size=23,
            color=MUTED,
        )
    )
    table.append(make_row(720, [cell]))
    return table


def make_cover_frame_table() -> etree._Element:
    table = make_table(
        width=FRAME_WIDTH,
        grid_widths=[FRAME_WIDTH],
        alignment="center",
        borders={},
        cell_margins={"top": 120, "left": 0, "bottom": 0, "right": 0},
    )
    cell = make_cell(FRAME_WIDTH, valign="top")
    cell.append(make_layout_table())
    cell.append(make_paragraph(line=1, line_rule="exact"))
    table.append(make_row(FRAME_HEIGHT, [cell]))
    return table


def configure_cover_section(root: etree._Element) -> None:
    sect_pr = root.find(".//w:body/w:p/w:pPr/w:sectPr", namespaces=NS)
    if sect_pr is None:
        raise ValueError("Could not find the first section properties.")

    pg_sz = sect_pr.find("w:pgSz", namespaces=NS)
    if pg_sz is not None:
        pg_sz.set(qn("w:w"), str(COVER_PAGE_WIDTH))
        pg_sz.set(qn("w:h"), str(COVER_PAGE_HEIGHT))

    pg_mar = sect_pr.find("w:pgMar", namespaces=NS)
    if pg_mar is not None:
        for side in ("top", "right", "bottom", "left"):
            pg_mar.set(qn(f"w:{side}"), str(COVER_MARGIN))

    pg_borders = sect_pr.find("w:pgBorders", namespaces=NS)
    if pg_borders is not None:
        sect_pr.remove(pg_borders)
    pg_borders = el("w:pgBorders", offsetFrom="page")
    for side in ("top", "left", "bottom", "right"):
        pg_borders.append(el(f"w:{side}", val="single", sz="6", space="18", color=NAVY))
    sect_pr.append(pg_borders)


def make_cover_section_properties() -> etree._Element:
    sect_pr = el("w:sectPr")
    sect_pr.append(el("w:pgSz", w=str(COVER_PAGE_WIDTH), h=str(COVER_PAGE_HEIGHT)))
    sect_pr.append(
        el(
            "w:pgMar",
            top=str(COVER_MARGIN),
            right=str(COVER_MARGIN),
            bottom=str(COVER_MARGIN),
            left=str(COVER_MARGIN),
            header="851",
            footer="992",
            gutter="0",
        )
    )
    borders = el("w:pgBorders", offsetFrom="page")
    for side in ("top", "left", "bottom", "right"):
        borders.append(el(f"w:{side}", val="single", sz="6", space="18", color=NAVY))
    sect_pr.append(borders)
    sect_pr.append(el("w:cols", space="425", num="1"))
    sect_pr.append(el("w:titlePg"))
    sect_pr.append(el("w:docGrid", type="lines", linePitch="312", charSpace="0"))
    return sect_pr


def make_cover_section_break_paragraph() -> etree._Element:
    paragraph = el("w:p")
    p_pr = el("w:pPr")
    p_pr.append(el("w:spacing", before="0", after="0", line="1", lineRule="exact"))
    p_pr.append(make_cover_section_properties())
    paragraph.append(p_pr)
    return paragraph


def looks_like_existing_cover(table: etree._Element) -> bool:
    text = "".join(table.xpath(".//w:t/text()", namespaces=NS))
    return "Nanyang Technological University" in text and "Prepared by" in text


def upsert_cover_page(root: etree._Element) -> None:
    body = root.find("w:body", namespaces=NS)
    if body is None:
        raise ValueError("Could not find the document body.")

    first_child = body[0]
    if first_child.tag == qn("w:tbl") and looks_like_existing_cover(first_child):
        body.replace(first_child, make_cover_frame_table())
        configure_cover_section(root)
        return

    body.insert(0, make_cover_frame_table())
    body.insert(1, make_cover_section_break_paragraph())


def build_cover_page(input_path: Path, output_path: Path) -> None:
    with ZipFile(input_path) as source_zip:
        document_xml = source_zip.read("word/document.xml")
        root = etree.fromstring(document_xml)
        upsert_cover_page(root)

        new_document_xml = etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=True,
        )

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
    parser = argparse.ArgumentParser(description="Rebuild the report cover page from stable Word-native OOXML.")
    parser.add_argument("input_docx", type=Path)
    parser.add_argument("--out", type=Path, default=None, help="Output path. Defaults to in-place update.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.out or args.input_docx
    build_cover_page(args.input_docx, output)
    print(output)


if __name__ == "__main__":
    main()
