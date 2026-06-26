"""Public render dispatcher."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .docx import render_docx
from .errors import UnsupportedFormatError

SUPPORTED_TEMPLATE_SUFFIXES = {".docx"}
SUPPORTED_OUTPUT_FORMATS = {"docx"}


def render(
    template_path: str | Path,
    data: Mapping[str, Any],
    *,
    output_format: str | None = None,
) -> bytes:
    """Render an Office template with mapping data.

    Phase 1 intentionally supports DOCX input and DOCX output only. PDF,
    XLSX, and PPTX are separate roadmap phases.
    """

    path = Path(template_path)
    suffix = path.suffix.lower()

    if suffix not in SUPPORTED_TEMPLATE_SUFFIXES:
        raise UnsupportedFormatError(
            f"Unsupported template format {suffix or '<none>'}; supported formats: .docx"
        )

    requested_output = (output_format or suffix.removeprefix(".")).lower()
    if requested_output not in SUPPORTED_OUTPUT_FORMATS:
        raise UnsupportedFormatError(
            "Unsupported output format "
            f"{requested_output!r}; Phase 1 supports only 'docx' output"
        )

    if suffix == ".docx":
        return render_docx(path, data)

    raise UnsupportedFormatError(f"No renderer registered for template format {suffix}")
