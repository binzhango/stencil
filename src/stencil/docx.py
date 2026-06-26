"""DOCX rendering engine."""

from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from typing import Any

from .errors import RenderError


def render_docx(template_path: str | Path, data: Mapping[str, Any]) -> bytes:
    """Render a DOCX template with Jinja-compatible data.

    The DOCX implementation delegates Word XML run handling to ``docxtpl`` for
    Phase 1. The dependency is imported lazily so the package can still be
    inspected before dependencies are installed.
    """

    path = Path(template_path)

    if not path.exists():
        raise RenderError("Template file does not exist", template_path=path, stage="load")
    if not path.is_file():
        raise RenderError("Template path is not a file", template_path=path, stage="load")

    try:
        from docxtpl import DocxTemplate
    except ImportError as exc:
        raise RenderError(
            "DOCX rendering requires the 'docxtpl' dependency; run 'uv sync --dev'",
            template_path=path,
            stage="import",
        ) from exc

    try:
        document = DocxTemplate(path)
    except Exception as exc:
        raise RenderError("Failed to load DOCX template", template_path=path, stage="load") from exc

    try:
        document.render(dict(data))
    except Exception as exc:
        raise RenderError(
            "Failed to render DOCX template", template_path=path, stage="render"
        ) from exc

    buffer = BytesIO()
    try:
        document.save(buffer)
    except Exception as exc:
        raise RenderError(
            "Failed to serialize rendered DOCX", template_path=path, stage="save"
        ) from exc

    return buffer.getvalue()
