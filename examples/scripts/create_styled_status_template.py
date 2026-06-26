"""Create the styled DOCX template used by the style-preservation example."""

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


def shade_cell(cell, fill: str) -> None:
    """Apply a background fill color to a table cell."""

    tc_pr = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    tc_pr.append(shading)


def main() -> None:
    out = Path("examples/templates/styled-status-report.docx")
    out.parent.mkdir(parents=True, exist_ok=True)

    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)

    normal = document.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(10)

    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title.add_run("Project Status Report")
    title_run.bold = True
    title_run.font.size = Pt(24)
    title_run.font.color.rgb = RGBColor(31, 78, 121)

    subtitle = document.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle_run = subtitle.add_run("{{ project.name }}")
    subtitle_run.italic = True
    subtitle_run.font.size = Pt(13)
    subtitle_run.font.color.rgb = RGBColor(89, 89, 89)

    document.add_paragraph()

    summary = document.add_paragraph()
    summary.add_run("Executive summary: ").bold = True
    summary.add_run("{{ summary }}")

    meta = document.add_table(rows=3, cols=2)
    meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta.style = "Table Grid"
    rows = [
        ("Owner", "{{ owner.name }}"),
        ("Status", "{{ status }}"),
        ("Reporting date", "{{ report_date }}"),
    ]
    for index, (label, value) in enumerate(rows):
        label_cell, value_cell = meta.rows[index].cells
        label_cell.text = label
        value_cell.text = value
        shade_cell(label_cell, "EAF2F8")
        shade_cell(value_cell, "FFFFFF")
        label_cell.paragraphs[0].runs[0].bold = True
        if label == "Status":
            value_cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(0, 112, 192)

    document.add_paragraph()

    milestones_heading = document.add_paragraph()
    heading_run = milestones_heading.add_run("Milestones")
    heading_run.bold = True
    heading_run.font.size = Pt(15)
    heading_run.font.color.rgb = RGBColor(31, 78, 121)

    table = document.add_table(rows=2, cols=3)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    headers = ["Milestone", "Owner", "Due"]
    for index, text in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.text = text
        shade_cell(cell, "1F4E79")
        run = cell.paragraphs[0].runs[0]
        run.bold = True
        run.font.color.rgb = RGBColor(255, 255, 255)

    cells = table.rows[1].cells
    cells[0].text = "{% for item in milestones %}{{ item.name }}"
    cells[1].text = "{{ item.owner }}"
    cells[2].text = "{{ item.due }}{% endfor %}"
    for cell in cells:
        shade_cell(cell, "F7FBFD")

    document.add_paragraph()

    note = document.add_paragraph()
    note_run = note.add_run("{% if risk_note %}Risk note: {{ risk_note }}{% endif %}")
    note_run.bold = True
    note_run.font.color.rgb = RGBColor(192, 0, 0)

    document.save(out)
    print(out)


if __name__ == "__main__":
    main()
