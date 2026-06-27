"""Public render dispatcher."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .docx import render_docx
from .errors import UnsupportedFormatError
from .pdf import convert_docx_to_pdf, convert_pptx_to_pdf, convert_xlsx_to_pdf
from .pptx import render_pptx
from .xlsx import render_xlsx

SUPPORTED_TEMPLATE_SUFFIXES = {".docx", ".pptx", ".xlsx"}
SUPPORTED_OUTPUT_FORMATS = {"docx", "pdf", "pptx", "xlsx"}


def render(
    template_path: str | Path,
    data: Mapping[str, Any],
    *,
    output_format: str | None = None,
) -> bytes:
    """Render an Office template with mapping data.

    DOCX, PPTX, and XLSX templates can be rendered directly or converted to PDF.
    """

    path = Path(template_path)
    suffix = path.suffix.lower()

    if suffix not in SUPPORTED_TEMPLATE_SUFFIXES:
        raise UnsupportedFormatError(
            "Unsupported template format "
            f"{suffix or '<none>'}; supported formats: .docx, .pptx, .xlsx"
        )

    requested_output = (output_format or suffix.removeprefix(".")).lower()
    if requested_output not in SUPPORTED_OUTPUT_FORMATS:
        raise UnsupportedFormatError(
            "Unsupported output format "
            f"{requested_output!r}; supported output formats: docx, pdf, pptx, xlsx"
        )

    if suffix == ".docx":
        if requested_output not in {"docx", "pdf"}:
            raise UnsupportedFormatError("DOCX templates can render only to docx or pdf")
        rendered_docx = render_docx(path, data)
        if requested_output == "docx":
            return rendered_docx
        if requested_output == "pdf":
            return convert_docx_to_pdf(rendered_docx)

    if suffix == ".xlsx":
        if requested_output not in {"xlsx", "pdf"}:
            raise UnsupportedFormatError("XLSX templates can render only to xlsx or pdf")
        rendered_xlsx = render_xlsx(path, data)
        if requested_output == "xlsx":
            return rendered_xlsx
        if requested_output == "pdf":
            return convert_xlsx_to_pdf(rendered_xlsx)

    if suffix == ".pptx":
        if requested_output not in {"pptx", "pdf"}:
            raise UnsupportedFormatError("PPTX templates can render only to pptx or pdf")
        rendered_pptx = render_pptx(path, data)
        if requested_output == "pptx":
            return rendered_pptx
        if requested_output == "pdf":
            return convert_pptx_to_pdf(rendered_pptx)

    raise UnsupportedFormatError(f"No renderer registered for template format {suffix}")
