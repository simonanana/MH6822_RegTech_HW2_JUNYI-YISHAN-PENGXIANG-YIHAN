from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree

from build_contents_page import build_contents_page
from build_cover_page import build_cover_page, el, make_cell, make_paragraph, make_row, make_table, qn


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"w": W_NS, "wp": WP_NS, "a": A_NS}

NAVY = "0B234A"
INK = "23364D"
GRID = "D6DCE5"
ALT = "F4F7FA"
WHITE = "FFFFFF"
BODY_WIDTH = 9978
FIGURE_BODY_CX = 6035040


SCHEMA_ROWS = [
    ("EventCategory", "Yes", "Classifies political, macro, regulatory, weather, litigation, or other event types."),
    ("ReferenceEntity", "Yes", "Identifies the official body, index, court, regulator, or source resolving the event."),
    ("EventJurisdiction", "Yes", "Records the jurisdiction where the event is determined."),
    ("EventDate", "Yes", "Records the event determination date."),
    ("ResolutionSource", "Yes", "Defines the authoritative source used for settlement."),
    ("PayoutType", "Yes", "Captures binary, scalar, capped, floored, or multi-outcome payoff."),
    ("SettlementCurrency", "Yes", "Captures fiat or stablecoin settlement and flags non-ISO identifiers."),
    ("PlatformType", "Yes", "Distinguishes CFTC DCM, offshore exchange, decentralised protocol, bilateral OTC, or other venues."),
    ("RegulatoryStatus", "Yes", "Records approved, conditional, prohibited, not applicable, or uncertain status."),
]


def text_of(node: etree._Element) -> str:
    return " ".join(t.text or "" for t in node.findall(".//w:t", namespaces=NS))


def ensure_ppr(paragraph: etree._Element) -> etree._Element:
    p_pr = paragraph.find("w:pPr", namespaces=NS)
    if p_pr is None:
        p_pr = el("w:pPr")
        paragraph.insert(0, p_pr)
    return p_pr


def remove_children(parent: etree._Element, tag: str) -> None:
    for child in list(parent):
        if child.tag == qn(tag):
            parent.remove(child)


def ensure_child(parent: etree._Element, tag: str) -> etree._Element:
    child = parent.find(tag, namespaces=NS)
    if child is None:
        child = el(tag)
        parent.append(child)
    return child


def add_page_break_before(paragraph: etree._Element) -> None:
    p_pr = ensure_ppr(paragraph)
    if p_pr.find("w:pageBreakBefore", namespaces=NS) is None:
        p_pr.append(el("w:pageBreakBefore"))


def remove_page_break_before(paragraph: etree._Element) -> None:
    p_pr = paragraph.find("w:pPr", namespaces=NS)
    if p_pr is None:
        return
    page_break_before = p_pr.find("w:pageBreakBefore", namespaces=NS)
    if page_break_before is not None:
        p_pr.remove(page_break_before)


def replace_numpr(paragraph: etree._Element, *, num_id: int, level: int = 0) -> None:
    p_pr = ensure_ppr(paragraph)
    old = p_pr.find("w:numPr", namespaces=NS)
    if old is not None:
        p_pr.remove(old)
    num_pr = el("w:numPr")
    num_pr.append(el("w:ilvl", val=str(level)))
    num_pr.append(el("w:numId", val=str(num_id)))
    p_pr.append(num_pr)


def replace_paragraph_text(paragraph: etree._Element, text: str) -> None:
    runs = paragraph.findall("w:r", namespaces=NS)
    template_rpr = None
    if runs:
        rpr = runs[0].find("w:rPr", namespaces=NS)
        if rpr is not None:
            template_rpr = copy.deepcopy(rpr)
    for child in list(paragraph):
        if child.tag == qn("w:r"):
            paragraph.remove(child)
    run = el("w:r")
    if template_rpr is not None:
        run.append(template_rpr)
    text_node = el("w:t")
    text_node.text = text
    run.append(text_node)
    paragraph.append(run)


def make_page_break_paragraph() -> etree._Element:
    paragraph = el("w:p")
    p_pr = el("w:pPr")
    p_pr.append(el("w:spacing", before="0", after="0", line="1", lineRule="exact"))
    paragraph.append(p_pr)
    run = el("w:r")
    run.append(el("w:br", type="page"))
    paragraph.append(run)
    return paragraph


def paragraph_has_page_break(paragraph: etree._Element) -> bool:
    return paragraph.find(".//w:br[@w:type='page']", namespaces=NS) is not None


def set_table_left_aligned_full_width(table: etree._Element) -> None:
    tbl_pr = table.find("w:tblPr", namespaces=NS)
    if tbl_pr is None:
        return

    jc = tbl_pr.find("w:jc", namespaces=NS)
    if jc is not None:
        tbl_pr.remove(jc)

    tbl_ind = tbl_pr.find("w:tblInd", namespaces=NS)
    if tbl_ind is None:
        tbl_ind = el("w:tblInd", w="0", type="dxa")
        tbl_pr.insert(2, tbl_ind)
    else:
        tbl_ind.set(qn("w:w"), "0")
        tbl_ind.set(qn("w:type"), "dxa")

    tbl_layout = tbl_pr.find("w:tblLayout", namespaces=NS)
    if tbl_layout is not None:
        tbl_layout.set(qn("w:type"), "autofit")

    grid = table.find("w:tblGrid", namespaces=NS)
    if grid is not None:
        for grid_col in grid.findall("w:gridCol", namespaces=NS):
            grid_col.set(qn("w:w"), "5097")

    for cell in table.findall(".//w:tc", namespaces=NS):
        tc_w = cell.find("w:tcPr/w:tcW", namespaces=NS)
        if tc_w is not None:
            tc_w.set(qn("w:w"), "2500")
            tc_w.set(qn("w:type"), "pct")


def apply_times_new_roman_to_standalone_numbers(root: etree._Element) -> None:
    pattern = re.compile(r"(?<![A-Za-z])(\d+(?:[.,]\d+)*)(?![A-Za-z])")
    for run in list(root.findall(".//w:r", namespaces=NS)):
        text_nodes = run.findall("w:t", namespaces=NS)
        if len(text_nodes) != 1:
            continue
        if run.find("w:drawing", namespaces=NS) is not None or run.find("w:tab", namespaces=NS) is not None:
            continue
        text = text_nodes[0].text or ""
        matches = list(pattern.finditer(text))
        if not matches:
            continue

        parent = run.getparent()
        if parent is None:
            continue
        insert_at = parent.index(run)
        parent.remove(run)

        cursor = 0
        for match in matches:
            if match.start() > cursor:
                parent.insert(insert_at, clone_run_with_text(run, text[cursor:match.start()]))
                insert_at += 1
            numeric_run = clone_run_with_text(run, match.group(1))
            set_run_font(numeric_run, "Times New Roman")
            parent.insert(insert_at, numeric_run)
            insert_at += 1
            cursor = match.end()
        if cursor < len(text):
            parent.insert(insert_at, clone_run_with_text(run, text[cursor:]))


def clone_run_with_text(run: etree._Element, text: str) -> etree._Element:
    cloned = copy.deepcopy(run)
    for text_node in cloned.findall("w:t", namespaces=NS):
        text_node.text = text
        if text.startswith(" ") or text.endswith(" "):
            text_node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        elif "{http://www.w3.org/XML/1998/namespace}space" in text_node.attrib:
            del text_node.attrib["{http://www.w3.org/XML/1998/namespace}space"]
    return cloned


def set_run_font(run: etree._Element, font: str) -> None:
    r_pr = run.find("w:rPr", namespaces=NS)
    if r_pr is None:
        r_pr = el("w:rPr")
        run.insert(0, r_pr)
    r_fonts = r_pr.find("w:rFonts", namespaces=NS)
    if r_fonts is None:
        r_fonts = el("w:rFonts")
        r_pr.insert(0, r_fonts)
    for attr in ("ascii", "hAnsi", "cs"):
        r_fonts.set(qn(f"w:{attr}"), font)


def set_cell_borders(cell: etree._Element, color: str = GRID, size: int = 4) -> None:
    tc_pr = cell.find("w:tcPr", namespaces=NS)
    if tc_pr is None:
        tc_pr = el("w:tcPr")
        cell.insert(0, tc_pr)
    remove_children(tc_pr, "w:tcBorders")
    borders = el("w:tcBorders")
    for side in ("top", "left", "bottom", "right"):
        borders.append(el(f"w:{side}", val="single", color=color, sz=str(size), space="0"))
    tc_pr.append(borders)


def set_cell_shading(cell: etree._Element, fill: str) -> None:
    tc_pr = cell.find("w:tcPr", namespaces=NS)
    if tc_pr is None:
        tc_pr = el("w:tcPr")
        cell.insert(0, tc_pr)
    remove_children(tc_pr, "w:shd")
    tc_pr.append(el("w:shd", val="clear", color="auto", fill=fill))


def set_cell_width(cell: etree._Element, width: int) -> None:
    tc_pr = cell.find("w:tcPr", namespaces=NS)
    if tc_pr is None:
        tc_pr = el("w:tcPr")
        cell.insert(0, tc_pr)
    tc_w = tc_pr.find("w:tcW", namespaces=NS)
    if tc_w is None:
        tc_w = el("w:tcW")
        tc_pr.insert(0, tc_w)
    tc_w.set(qn("w:w"), str(width))
    tc_w.set(qn("w:type"), "dxa")
    cell.set(qn("w:w"), str(width))


def set_cell_vertical_alignment(cell: etree._Element, value: str = "center") -> None:
    tc_pr = cell.find("w:tcPr", namespaces=NS)
    if tc_pr is None:
        tc_pr = el("w:tcPr")
        cell.insert(0, tc_pr)
    remove_children(tc_pr, "w:vAlign")
    tc_pr.append(el("w:vAlign", val=value))


def set_table_cell_margins(
    table: etree._Element,
    *,
    top: int = 58,
    left: int = 95,
    bottom: int = 58,
    right: int = 95,
) -> None:
    tbl_pr = table.find("w:tblPr", namespaces=NS)
    if tbl_pr is None:
        tbl_pr = el("w:tblPr")
        table.insert(0, tbl_pr)
    remove_children(tbl_pr, "w:tblCellMar")
    margins = el("w:tblCellMar")
    for side, width in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        margins.append(el(f"w:{side}", w=str(width), type="dxa"))
    tbl_pr.append(margins)


def set_table_geometry(table: etree._Element, widths: list[int]) -> None:
    tbl_pr = table.find("w:tblPr", namespaces=NS)
    if tbl_pr is None:
        tbl_pr = el("w:tblPr")
        table.insert(0, tbl_pr)

    tbl_w = tbl_pr.find("w:tblW", namespaces=NS)
    if tbl_w is None:
        tbl_w = el("w:tblW")
        tbl_pr.insert(0, tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths)))
    tbl_w.set(qn("w:type"), "dxa")

    jc = tbl_pr.find("w:jc", namespaces=NS)
    if jc is None:
        jc = el("w:jc")
        tbl_pr.append(jc)
    jc.set(qn("w:val"), "center")

    layout = tbl_pr.find("w:tblLayout", namespaces=NS)
    if layout is None:
        layout = el("w:tblLayout")
        tbl_pr.append(layout)
    layout.set(qn("w:type"), "fixed")

    grid = table.find("w:tblGrid", namespaces=NS)
    if grid is not None:
        table.remove(grid)
    grid = el("w:tblGrid")
    for width in widths:
        grid.append(el("w:gridCol", w=str(width)))
    insert_at = 1 if len(table) and table[0].tag == qn("w:tblPr") else 0
    table.insert(insert_at, grid)

    for row in table.findall("w:tr", namespaces=NS):
        cells = row.findall("w:tc", namespaces=NS)
        for index, cell in enumerate(cells):
            set_cell_width(cell, widths[min(index, len(widths) - 1)])


def set_run_style(
    run: etree._Element,
    *,
    font: str,
    size: int,
    color: str,
    bold: bool,
) -> None:
    r_pr = run.find("w:rPr", namespaces=NS)
    if r_pr is None:
        r_pr = el("w:rPr")
        run.insert(0, r_pr)
    r_fonts = r_pr.find("w:rFonts", namespaces=NS)
    if r_fonts is None:
        r_fonts = el("w:rFonts")
        r_pr.insert(0, r_fonts)
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        r_fonts.set(qn(f"w:{attr}"), font)

    color_node = r_pr.find("w:color", namespaces=NS)
    if color_node is None:
        color_node = el("w:color")
        r_pr.append(color_node)
    color_node.set(qn("w:val"), color)

    for tag in ("w:sz", "w:szCs"):
        size_node = r_pr.find(tag, namespaces=NS)
        if size_node is None:
            size_node = el(tag)
            r_pr.append(size_node)
        size_node.set(qn("w:val"), str(size))

    remove_children(r_pr, "w:b")
    remove_children(r_pr, "w:bCs")
    if bold:
        r_pr.append(el("w:b"))
        r_pr.append(el("w:bCs"))


def set_paragraph_format(
    paragraph: etree._Element,
    *,
    align: str,
    line: int = 220,
    before: int = 0,
    after: int = 0,
) -> None:
    p_pr = ensure_ppr(paragraph)
    jc = p_pr.find("w:jc", namespaces=NS)
    if jc is None:
        jc = el("w:jc")
        p_pr.append(jc)
    jc.set(qn("w:val"), align)

    spacing = p_pr.find("w:spacing", namespaces=NS)
    if spacing is None:
        spacing = el("w:spacing")
        p_pr.append(spacing)
    spacing.set(qn("w:before"), str(before))
    spacing.set(qn("w:after"), str(after))
    spacing.set(qn("w:line"), str(line))
    spacing.set(qn("w:lineRule"), "exact")


def set_row_behavior(row: etree._Element, *, header: bool = False) -> None:
    tr_pr = row.find("w:trPr", namespaces=NS)
    if tr_pr is None:
        tr_pr = el("w:trPr")
        row.insert(0, tr_pr)
    remove_children(tr_pr, "w:trHeight")
    if header:
        if tr_pr.find("w:tblHeader", namespaces=NS) is None:
            tr_pr.append(el("w:tblHeader", val="true"))
        tr_pr.append(el("w:trHeight", val="360", hRule="atLeast"))


def polish_appendix_a_table(table: etree._Element) -> None:
    widths = [1120, 1320, 2260, 3970, 1308]
    set_table_geometry(table, widths)
    set_table_cell_margins(table, top=48, bottom=48, left=90, right=90)

    rows = table.findall("w:tr", namespaces=NS)
    for row_index, row in enumerate(rows):
        set_row_behavior(row, header=row_index == 0)
        cells = row.findall("w:tc", namespaces=NS)
        for col_index, cell in enumerate(cells):
            set_cell_vertical_alignment(cell, "center")
            set_cell_width(cell, widths[min(col_index, len(widths) - 1)])
            if row_index == 0:
                set_cell_shading(cell, NAVY)
            else:
                set_cell_shading(cell, WHITE if row_index % 2 == 1 else ALT)
            set_cell_borders(cell, color=GRID, size=4)

            align = "center" if row_index == 0 or col_index in {0, 1, 4} else "left"
            for paragraph in cell.findall("w:p", namespaces=NS):
                set_paragraph_format(paragraph, align=align, line=205 if row_index == 0 else 230)
                for run in paragraph.findall("w:r", namespaces=NS):
                    set_run_style(
                        run,
                        font="Georgia" if row_index == 0 else "Times New Roman",
                        size=17 if row_index == 0 else 18,
                        color=WHITE if row_index == 0 else INK,
                        bold=row_index == 0,
                    )


def resize_drawing_paragraph(paragraph: etree._Element, *, target_cx: int) -> None:
    for drawing in paragraph.findall(".//w:drawing", namespaces=NS):
        extent = drawing.find(".//wp:extent", namespaces=NS)
        if extent is None:
            continue
        old_cx = int(extent.get("cx", str(target_cx)))
        old_cy = int(extent.get("cy", str(target_cx)))
        if old_cx <= 0:
            continue
        target_cy = int(round(old_cy * target_cx / old_cx))
        extent.set("cx", str(target_cx))
        extent.set("cy", str(target_cy))
        for a_ext in drawing.findall(".//a:ext", namespaces=NS):
            a_ext.set("cx", str(target_cx))
            a_ext.set("cy", str(target_cy))
    p_pr = ensure_ppr(paragraph)
    jc = p_pr.find("w:jc", namespaces=NS)
    if jc is None:
        jc = el("w:jc")
        p_pr.append(jc)
    jc.set(qn("w:val"), "center")
    spacing = p_pr.find("w:spacing", namespaces=NS)
    if spacing is None:
        spacing = el("w:spacing")
        p_pr.append(spacing)
    spacing.set(qn("w:before"), "0")
    spacing.set(qn("w:after"), "70")
    for attr in ("line", "lineRule"):
        namespaced_attr = qn(f"w:{attr}")
        if namespaced_attr in spacing.attrib:
            del spacing.attrib[namespaced_attr]


def make_rich_paragraph(
    *,
    align: str = "left",
    before: int = 0,
    after: int = 0,
    line: int = 240,
    font: str = "Georgia",
    size: int = 22,
    color: str = INK,
    bold: bool = False,
    text: str = "",
) -> etree._Element:
    return make_paragraph(
        text,
        align=align,
        before=before,
        after=after,
        line=line,
        line_rule="exact",
        font=font,
        size=size,
        color=color,
        bold=bold,
    )


def make_schema_overview_table() -> etree._Element:
    widths = [2200, 1450, 6328]
    table = make_table(
        width=sum(widths),
        grid_widths=widths,
        alignment="center",
        borders={side: ("single", 4) for side in ("top", "left", "bottom", "right", "insideH", "insideV")},
        cell_margins={"top": 80, "left": 110, "bottom": 80, "right": 110},
    )
    headers = ("Field", "Required", "Purpose")
    header_cells = []
    for width, text in zip(widths, headers):
        cell = make_cell(width, valign="center", shading=NAVY)
        set_cell_borders(cell)
        cell.append(make_rich_paragraph(text=text, font="Georgia", size=20, color=WHITE, bold=True))
        header_cells.append(cell)
    table.append(make_row(360, header_cells))

    for idx, row in enumerate(SCHEMA_ROWS):
        fill = WHITE if idx % 2 == 0 else ALT
        cells = []
        for width, value in zip(widths, row):
            cell = make_cell(width, valign="center", shading=fill)
            set_cell_borders(cell)
            cell.append(make_rich_paragraph(text=value, font="Georgia", size=19, color=INK))
            cells.append(cell)
        table.append(make_row(350, cells))
    return table


def make_note_box() -> etree._Element:
    table = make_table(
        width=BODY_WIDTH,
        grid_widths=[BODY_WIDTH],
        alignment="center",
        borders={side: ("single", 4) for side in ("top", "left", "bottom", "right")},
        cell_margins={"top": 100, "left": 130, "bottom": 100, "right": 130},
    )
    cell = make_cell(BODY_WIDTH, valign="center", shading=ALT)
    set_cell_borders(cell, color=GRID)
    p = make_rich_paragraph(
        text="Design note: The overview keeps the written report readable; the complete JSON schema is reproduced below as the implementation-level template used by the compliance engine.",
        font="Georgia",
        size=20,
        color=INK,
        line=220,
    )
    cell.append(p)
    table.append(make_row(540, [cell]))
    return table


def make_code_table(lines: list[str]) -> etree._Element:
    line_height = 160
    table = make_table(
        width=BODY_WIDTH,
        grid_widths=[BODY_WIDTH],
        alignment="center",
        borders={side: ("single", 4) for side in ("top", "left", "bottom", "right")},
        cell_margins={"top": 110, "left": 130, "bottom": 110, "right": 130},
    )
    cell = make_cell(BODY_WIDTH, valign="top", shading="F5F7FA")
    set_cell_borders(cell, color=GRID)
    for line in lines:
        cell.append(
            make_rich_paragraph(
                text=line or " ",
                font="Courier New",
                size=16,
                color=INK,
                line=line_height,
            )
        )
    table.append(make_row(max(220, len(lines) * line_height + 260), [cell]))
    return table


def make_appendix_c_nodes(schema_lines: list[str]) -> list[etree._Element]:
    first_chunk = schema_lines[:37]
    second_chunk = schema_lines[37:]

    nodes: list[etree._Element] = [
        make_rich_paragraph(
            text="Appendix C: Proposed EventContract Schema",
            font="Georgia",
            size=34,
            color=NAVY,
            bold=True,
            line=300,
            after=40,
        ),
        make_rich_paragraph(
            text="This appendix summarises the event-specific fields used by the proposed EventContract design and reproduces the full implementation JSON schema in readable technical form.",
            font="Georgia",
            size=21,
            color=INK,
            line=240,
            after=80,
        ),
        make_rich_paragraph(
            text="C1. Schema field overview",
            font="Georgia",
            size=28,
            color=NAVY,
            bold=True,
            line=260,
            after=36,
        ),
        make_schema_overview_table(),
        make_note_box(),
        make_rich_paragraph(
            text="C2. Full JSON schema",
            font="Georgia",
            size=28,
            color=NAVY,
            bold=True,
            line=260,
            before=70,
            after=36,
        ),
        make_code_table(first_chunk),
        make_rich_paragraph(),
        make_rich_paragraph(
            text="C2. Full JSON schema (continued)",
            font="Georgia",
            size=28,
            color=NAVY,
            bold=True,
            line=260,
            after=36,
        ),
        make_code_table(second_chunk),
    ]
    add_page_break_before(nodes[8])
    return nodes


def make_portrait_section_break_from_body(root: etree._Element) -> etree._Element:
    portrait_body_section = None
    for sect_pr in root.findall(".//w:sectPr", namespaces=NS):
        pg_sz = sect_pr.find("w:pgSz", namespaces=NS)
        pg_mar = sect_pr.find("w:pgMar", namespaces=NS)
        if pg_sz is not None and pg_mar is not None and pg_sz.get(qn("w:w")) == "11906" and pg_sz.get(qn("w:h")) == "16838":
            if pg_mar.get(qn("w:top")) == "1134":
                portrait_body_section = sect_pr
                break
    if portrait_body_section is None:
        raise ValueError("Could not find portrait body section.")
    section = copy.deepcopy(portrait_body_section)
    pg_borders = section.find("w:pgBorders", namespaces=NS)
    if pg_borders is not None:
        section.remove(pg_borders)
    pg_borders = el("w:pgBorders")
    for side in ("top", "left", "bottom", "right"):
        pg_borders.append(el(f"w:{side}", val="none", sz="0", space="0"))
    section.append(pg_borders)
    return section


def replace_section_properties(paragraph: etree._Element, sect_pr: etree._Element) -> None:
    p_pr = ensure_ppr(paragraph)
    old = p_pr.find("w:sectPr", namespaces=NS)
    if old is not None:
        p_pr.remove(old)
    p_pr.append(sect_pr)


def patch_document(root: etree._Element, schema_lines: list[str]) -> None:
    body = root.find("w:body", namespaces=NS)
    if body is None:
        raise ValueError("Could not find document body.")

    children = list(body)

    # 5. Start the whole section cleanly on a fresh page so Table 4 does not split.
    for child in children:
        if text_of(child) == "Compliance, Scope, and Conclusions":
            add_page_break_before(child)
            break
    for child in children:
        if child.tag == qn("w:tbl") and text_of(child).startswith("Data quality status Count Pass 5"):
            set_table_left_aligned_full_width(child)
            break
    for i, child in enumerate(children[:-1]):
        next_text = text_of(children[i + 1])
        if (
            child.findall(".//w:drawing", namespaces=NS)
            and "Figure" in next_text
            and "Three-Dimensional Compliance Result" in next_text
        ):
            remove_page_break_before(child)
            previous_child = children[i - 1] if i > 0 else None
            if previous_child is None or previous_child.tag != qn("w:p") or not paragraph_has_page_break(previous_child):
                body.insert(i, make_page_break_paragraph())
            resize_drawing_paragraph(child, target_cx=FIGURE_BODY_CX)
            children = list(body)
            break

    for child in children:
        table_text = text_of(child)
        if (
            child.tag == qn("w:tbl")
            and "Student ID" in table_text
            and "Main Deliverables" in table_text
            and "Related Module" in table_text
        ):
            polish_appendix_a_table(child)
            break

    # 9. Dashboard list should use the same bullet style as Section 7.
    for child in children:
        text = text_of(child)
        if text.startswith("— ") and any(
            key in text
            for key in (
                "Compliance heatmap",
                "Compliance Finding Frequency",
                "Asset-class compliance breakdown",
                "Classification frontier panel",
            )
        ):
            replace_paragraph_text(child, text.removeprefix("— "))
            replace_numpr(child, num_id=2, level=0)

    # Appendix should use an explicit page break so Word and PDF agree.
    appendix_heading = next(child for child in children if text_of(child) == "Appendix")
    remove_page_break_before(appendix_heading)
    appendix_index = children.index(appendix_heading)
    previous_child = children[appendix_index - 1] if appendix_index > 0 else None
    if previous_child is None or previous_child.tag != qn("w:p") or not paragraph_has_page_break(previous_child):
        body.insert(appendix_index, make_page_break_paragraph())
        children = list(body)

    # Rebuild Appendix C as portrait, stacked content.
    appendix_c_break_index = None
    appendix_c_start_index = None
    for i, child in enumerate(children):
        if text_of(child) == "Appendix C: Proposed EventContract Schema":
            appendix_c_start_index = i
            appendix_c_break_index = i - 1
            break
    if appendix_c_start_index is None or appendix_c_break_index is None:
        raise ValueError("Could not find Appendix C block.")

    # The paragraph before Appendix C closes the previous portrait section;
    # the final body-level sectPr controls Appendix C itself.
    final_sect_pr = body.find("w:sectPr", namespaces=NS)
    if final_sect_pr is None:
        raise ValueError("Could not find final body section properties.")
    body.remove(final_sect_pr)
    body.append(make_portrait_section_break_from_body(root))

    # Remove existing Appendix C content until final body sectPr.
    remove_until = len(children) - 1
    for child in children[appendix_c_start_index:remove_until]:
        body.remove(child)

    insert_at = appendix_c_start_index
    for node in make_appendix_c_nodes(schema_lines):
        body.insert(insert_at, node)
        insert_at += 1


def refine_layout(input_path: Path, output_path: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        cover_docx = Path(tmp_dir) / "cover.docx"
        tmp_docx = Path(tmp_dir) / "toc.docx"
        build_cover_page(input_path, cover_docx)
        build_contents_page(cover_docx, tmp_docx)

        with ZipFile(tmp_docx) as source_zip:
            root = etree.fromstring(source_zip.read("word/document.xml"))
            schema = json.loads(Path("config/eventcontract_schema_full.json").read_text())
            schema_lines = json.dumps(schema, indent=2).splitlines()
            patch_document(root, schema_lines)
            new_document_xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)

            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                staged_path = Path(tmp.name)
            try:
                with ZipFile(staged_path, "w", compression=ZIP_DEFLATED) as target_zip:
                    for item in source_zip.infolist():
                        data = new_document_xml if item.filename == "word/document.xml" else source_zip.read(item.filename)
                        target_zip.writestr(item, data)
                shutil.move(staged_path, output_path)
            finally:
                if staged_path.exists():
                    staged_path.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply the final report layout refinements requested for the written report.")
    parser.add_argument("input_docx", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.out or args.input_docx
    refine_layout(args.input_docx, output)
    print(output)


if __name__ == "__main__":
    main()
