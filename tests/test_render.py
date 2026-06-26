import importlib
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired

import pytest

from stencil import UnsupportedFormatError, render
from stencil.errors import RenderError
from stencil.pdf import LibreOfficePdfConverter, PdfConversionError

render_module = importlib.import_module("stencil.render")


def test_render_rejects_unsupported_template_suffix() -> None:
    with pytest.raises(UnsupportedFormatError):
        render("template.xlsx", {})


def test_render_rejects_unsupported_output_format() -> None:
    with pytest.raises(UnsupportedFormatError):
        render("template.docx", {}, output_format="xlsx")


def test_render_rejects_missing_docx_template() -> None:
    with pytest.raises(RenderError, match="Template file does not exist"):
        render(Path("missing.docx"), {})


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
