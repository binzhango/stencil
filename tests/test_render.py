from pathlib import Path

import pytest

from stencil import UnsupportedFormatError, render
from stencil.errors import RenderError


def test_render_rejects_unsupported_template_suffix() -> None:
    with pytest.raises(UnsupportedFormatError):
        render("template.xlsx", {})


def test_render_rejects_unsupported_output_format() -> None:
    with pytest.raises(UnsupportedFormatError):
        render("template.docx", {}, output_format="pdf")


def test_render_rejects_missing_docx_template() -> None:
    with pytest.raises(RenderError, match="Template file does not exist"):
        render(Path("missing.docx"), {})
