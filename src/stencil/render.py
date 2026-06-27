"""Public render dispatcher."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .docx import render_docx
from .errors import UnsupportedFormatError
from .pdf import convert_docx_to_pdf, convert_xlsx_to_pdf
from .xlsx import render_xlsx

SUPPORTED_TEMPLATE_SUFFIXES = {".docx", ".xlsx"}
SUPPORTED_OUTPUT_FORMATS = {"docx", "pdf", "xlsx"}


def render(
    template_path: str | Path,
    data: Mapping[str, Any],
    *,
    output_format: str | None = None,
) -> bytes:
    """Render an Office template with mapping data.

    DOCX and XLSX templates can be rendered directly or converted to PDF.
    PPTX is a separate roadmap phase.
    """

    path = Path(template_path)
    suffix = path.suffix.lower()

    if suffix not in SUPPORTED_TEMPLATE_SUFFIXES:
        raise UnsupportedFormatError(
            f"Unsupported template format {suffix or '<none>'}; supported formats: .docx, .xlsx"
        )

    requested_output = (output_format or suffix.removeprefix(".")).lower()
    if requested_output not in SUPPORTED_OUTPUT_FORMATS:
        raise UnsupportedFormatError(
            "Unsupported output format "
            f"{requested_output!r}; supported output formats: docx, pdf, xlsx"
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

    raise UnsupportedFormatError(f"No renderer registered for template format {suffix}")
