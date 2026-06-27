import importlib
import json
import zipfile
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from xml.etree import ElementTree

import pytest

from stencil import UnsupportedFormatError, render
from stencil.errors import RenderError
from stencil.pdf import LibreOfficePdfConverter, PdfConversionError

render_module = importlib.import_module("stencil.render")
WORD_TEXT = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"


def _rendered_docx_text(document: bytes) -> str:
    with zipfile.ZipFile(BytesIO(document)) as archive:
        parts: list[str] = []
        for name in sorted(archive.namelist()):
            if not name.startswith("word/") or not name.endswith(".xml"):
                continue
            root = ElementTree.fromstring(archive.read(name))
            text = " ".join(
                node.text for node in root.iter(WORD_TEXT) if node.text is not None
            )
            if text.strip():
                parts.append(text)
    return " ".join(parts)


def _load_rendered_workbook(document: bytes):
    from openpyxl import load_workbook

    return load_workbook(BytesIO(document), data_only=False)


def test_render_rejects_unsupported_template_suffix() -> None:
    with pytest.raises(UnsupportedFormatError):
        render("template.pptx", {})


def test_render_rejects_unsupported_output_format() -> None:
    with pytest.raises(UnsupportedFormatError):
        render("template.docx", {}, output_format="xlsx")


def test_xlsx_simple_substitutions_preserve_types_and_styles(tmp_path: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    template = tmp_path / "template.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Invoice"
    sheet["A1"] = "Invoice {{ invoice.id }}"
    sheet["A1"].font = Font(bold=True)
    sheet["B2"] = "{{ invoice.total }}"
    sheet["B2"].number_format = "$#,##0.00"
    sheet["A3"] = "{{ invoice.note }}"
    workbook.create_sheet("Summary")["A1"] = "{{ customer.name }}"
    workbook.save(template)

    rendered = render(
        template,
        {
            "invoice": {"id": "INV-1001", "total": 1800, "note": "A&B <ok>"},
            "customer": {"name": "Acme Studio"},
        },
    )

    rendered_workbook = _load_rendered_workbook(rendered)
    sheet = rendered_workbook["Invoice"]
    assert sheet["A1"].value == "Invoice INV-1001"
    assert sheet["A1"].font.bold is True
    assert sheet["B2"].value == 1800
    assert sheet["B2"].number_format == "$#,##0.00"
    assert sheet["A3"].value == "A&B <ok>"
    assert rendered_workbook["Summary"]["A1"].value == "Acme Studio"


def test_xlsx_row_loop_clones_rows_and_translates_formulas(tmp_path: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill

    template = tmp_path / "template.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = "Description"
    sheet["B1"] = "Qty"
    sheet["C1"] = "Unit"
    sheet["D1"] = "Amount"
    sheet["A2"] = "{% for item in line_items %}"
    sheet["A3"] = "{{ item.description }}"
    sheet["B3"] = "{{ item.quantity }}"
    sheet["C3"] = "{{ item.unit_price }}"
    sheet["D3"] = "=B3*C3"
    sheet["A3"].fill = PatternFill("solid", fgColor="FFFF00")
    sheet["A4"] = "{% endfor %}"
    sheet["C5"] = "Total"
    sheet["D5"] = "=SUM(D3:D3)"
    workbook.save(template)

    rendered = render(
        template,
        {
            "line_items": [
                {"description": "Implementation", "quantity": 1, "unit_price": 1200},
                {"description": "QA", "quantity": 2, "unit_price": 300},
            ]
        },
    )

    rendered_workbook = _load_rendered_workbook(rendered)
    sheet = rendered_workbook.active
    assert sheet["A2"].value == "Implementation"
    assert sheet["B2"].value == 1
    assert sheet["C2"].value == 1200
    assert sheet["D2"].value == "=B2*C2"
    assert sheet["A3"].value == "QA"
    assert sheet["B3"].value == 2
    assert sheet["C3"].value == 300
    assert sheet["D3"].value == "=B3*C3"
    assert sheet["A2"].fill.fgColor.rgb == "00FFFF00"
    assert sheet["C4"].value == "Total"
    assert sheet["D4"].value == "=SUM(D3:D3)"


def test_render_converts_xlsx_to_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(render_module, "render_xlsx", lambda path, data: b"xlsx")
    monkeypatch.setattr(render_module, "convert_xlsx_to_pdf", lambda source: b"%PDF spreadsheet")

    assert render("template.xlsx", {}, output_format="pdf") == b"%PDF spreadsheet"


def test_render_rejects_missing_docx_template() -> None:
    with pytest.raises(RenderError, match="Template file does not exist"):
        render(Path("missing.docx"), {})


def test_invoice_example_matches_expected_output_text() -> None:
    payload = json.loads(Path("examples/data/invoice.json").read_text(encoding="utf-8"))

    rendered = render("examples/templates/invoice.docx", payload)

    text = _rendered_docx_text(rendered)
    assert "{{" not in text
    assert "{%" not in text
    assert "Invoice INV-1001" in text
    assert "Customer: Acme Studio (hello@example.com)" in text
    assert "Template implementation x 1: $1,200.00" in text
    assert "DOCX rendering QA x 2: $300.00" in text
    assert "Total: $1,800.00" in text
    assert "Note: Thanks for building with Stencil." in text


def test_styled_status_report_example_matches_expected_output_text() -> None:
    payload = json.loads(Path("examples/data/status-report.json").read_text(encoding="utf-8"))

    rendered = render("examples/templates/styled-status-report.docx", payload)

    text = _rendered_docx_text(rendered)
    assert "{{" not in text
    assert "{%" not in text
    assert "STENCIL STATUS" in text
    assert "Project Status Report" in text
    assert "Stencil DOCX MVP" in text
    assert "The template defines the layout and styles." in text
    assert "Owner Bin Zhang" in text
    assert "Status On track" in text
    assert "Create styled template Design 2026-06-27" in text
    assert "Render with JSON data Engineering 2026-06-28" in text
    assert "Review output formatting Operations 2026-06-29" in text
    assert "Risk note: Do not put style instructions in JSON" in text


def test_render_converts_docx_to_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(render_module, "render_docx", lambda path, data: b"docx")
    monkeypatch.setattr(render_module, "convert_docx_to_pdf", lambda source: b"%PDF rendered")

    assert render("template.docx", {}, output_format="pdf") == b"%PDF rendered"


def test_render_pdf_dispatch_is_safe_for_concurrent_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_render_docx(path: Path, data: Mapping[str, object]) -> bytes:
        return f"docx-{data['value']}".encode()

    def fake_convert_docx_to_pdf(source: bytes) -> bytes:
        return b"%PDF " + source

    monkeypatch.setattr(render_module, "render_docx", fake_render_docx)
    monkeypatch.setattr(render_module, "convert_docx_to_pdf", fake_convert_docx_to_pdf)

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(
            executor.map(
                lambda value: render("template.docx", {"value": value}, output_format="pdf"),
                range(12),
            )
        )

    assert sorted(results) == sorted(f"%PDF docx-{value}".encode() for value in range(12))


def test_libreoffice_converter_writes_pdf_and_cleans_temp_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("stencil.pdf.shutil.which", lambda name: "/usr/bin/soffice")

    def fake_run(command: list[str], **kwargs: object) -> CompletedProcess[list[str]]:
        outdir = Path(command[command.index("--outdir") + 1])
        outdir.joinpath("source.pdf").write_bytes(b"%PDF success")
        return CompletedProcess(command, 0, stdout=b"converted", stderr=b"")

    monkeypatch.setattr("stencil.pdf.subprocess.run", fake_run)

    converter = LibreOfficePdfConverter(timeout_seconds=1, temp_root=tmp_path)

    assert converter.convert(b"docx", source_suffix=".docx") == b"%PDF success"
    assert list(tmp_path.iterdir()) == []


def test_libreoffice_converter_retries_transient_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("stencil.pdf.shutil.which", lambda name: "/usr/bin/soffice")
    attempts = 0

    def fake_run(command: list[str], **kwargs: object) -> CompletedProcess[list[str]]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return CompletedProcess(command, 1, stdout=b"", stderr=b"temporary failure")

        outdir = Path(command[command.index("--outdir") + 1])
        outdir.joinpath("source.pdf").write_bytes(b"%PDF after retry")
        return CompletedProcess(command, 0, stdout=b"converted", stderr=b"")

    monkeypatch.setattr("stencil.pdf.subprocess.run", fake_run)

    converter = LibreOfficePdfConverter(timeout_seconds=1, retries=1, temp_root=tmp_path)

    assert converter.convert(b"docx", source_suffix=".docx") == b"%PDF after retry"
    assert attempts == 2
    assert list(tmp_path.iterdir()) == []


def test_libreoffice_converter_retries_after_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("stencil.pdf.shutil.which", lambda name: "/usr/bin/soffice")
    attempts = 0

    def fake_run(command: list[str], **kwargs: object) -> CompletedProcess[list[str]]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutExpired(cmd=command, timeout=1)

        outdir = Path(command[command.index("--outdir") + 1])
        outdir.joinpath("source.pdf").write_bytes(b"%PDF after timeout")
        return CompletedProcess(command, 0, stdout=b"converted", stderr=b"")

    monkeypatch.setattr("stencil.pdf.subprocess.run", fake_run)

    converter = LibreOfficePdfConverter(timeout_seconds=1, retries=1, temp_root=tmp_path)

    assert converter.convert(b"docx", source_suffix=".docx") == b"%PDF after timeout"
    assert attempts == 2
    assert list(tmp_path.iterdir()) == []


def test_libreoffice_converter_reports_missing_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("stencil.pdf.shutil.which", lambda name: None)

    converter = LibreOfficePdfConverter()

    with pytest.raises(PdfConversionError, match="requires LibreOffice"):
        converter.convert(b"docx", source_suffix=".docx")
