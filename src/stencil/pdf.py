"""PDF conversion workers."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .errors import RenderError


class ConversionWorker(Protocol):
    """Convert rendered Office document bytes into another format."""

    def convert(self, source: bytes, *, source_suffix: str) -> bytes:
        """Convert source bytes and return converted bytes."""
        ...


class PdfConversionError(RenderError):
    """Raised when rendered Office bytes cannot be converted to PDF."""


@dataclass(frozen=True)
class LibreOfficePdfConverter:
    """Convert Office documents to PDF through a bounded LibreOffice subprocess."""

    timeout_seconds: float = 30.0
    retries: int = 1
    executable: str | None = None
    temp_root: Path | None = None

    def convert(self, source: bytes, *, source_suffix: str) -> bytes:
        """Convert rendered Office bytes to PDF.

        Each attempt uses a fresh workspace and LibreOffice user profile so
        stuck lock files or profile state do not leak between conversions.
        """

        normalized_suffix = source_suffix.lower()
        if normalized_suffix != ".docx":
            raise PdfConversionError(
                f"PDF conversion from {normalized_suffix or '<none>'} is not supported",
                stage="convert",
            )

        executable = self._resolve_executable()
        attempts = max(0, self.retries) + 1
        last_error: PdfConversionError | None = None

        for attempt in range(1, attempts + 1):
            try:
                return self._convert_once(
                    source,
                    source_suffix=normalized_suffix,
                    executable=executable,
                    attempt=attempt,
                )
            except PdfConversionError as exc:
                last_error = exc

        if last_error is not None:
            raise last_error

        raise PdfConversionError("PDF conversion failed before starting", stage="convert")

    def _resolve_executable(self) -> str:
        if self.executable is not None:
            return self.executable

        executable = shutil.which("soffice") or shutil.which("libreoffice")
        if executable is None:
            raise PdfConversionError(
                "PDF conversion requires LibreOffice; install 'soffice' or 'libreoffice'",
                stage="convert",
            )
        return executable

    def _convert_once(
        self,
        source: bytes,
        *,
        source_suffix: str,
        executable: str,
        attempt: int,
    ) -> bytes:
        temp_root = str(self.temp_root) if self.temp_root is not None else None
        with tempfile.TemporaryDirectory(prefix="stencil-pdf-", dir=temp_root) as workspace_name:
            workspace = Path(workspace_name)
            outdir = workspace / "out"
            profile = workspace / "profile"
            outdir.mkdir()
            profile.mkdir()

            source_path = workspace / f"source{source_suffix}"
            source_path.write_bytes(source)

            command = [
                executable,
                "--headless",
                "--nologo",
                "--nofirststartwizard",
                "--norestore",
                "--nodefault",
                "--nolockcheck",
                f"-env:UserInstallation={profile.as_uri()}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(outdir),
                str(source_path),
            ]

            try:
                result = subprocess.run(
                    command,
                    cwd=workspace,
                    capture_output=True,
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise PdfConversionError(
                    f"LibreOffice PDF conversion timed out after {self.timeout_seconds:g}s "
                    f"(attempt {attempt})",
                    stage="convert",
                ) from exc
            except OSError as exc:
                raise PdfConversionError(
                    f"Could not start LibreOffice PDF conversion (attempt {attempt}): {exc}",
                    stage="convert",
                ) from exc

            if result.returncode != 0:
                output = _summarize_process_output(result.stdout, result.stderr)
                raise PdfConversionError(
                    f"LibreOffice PDF conversion failed (attempt {attempt}, "
                    f"exit={result.returncode}){output}",
                    stage="convert",
                )

            pdf_path = outdir / "source.pdf"
            if not pdf_path.exists():
                output = _summarize_process_output(result.stdout, result.stderr)
                raise PdfConversionError(
                    f"LibreOffice PDF conversion did not produce a PDF (attempt {attempt})"
                    f"{output}",
                    stage="convert",
                )

            pdf = pdf_path.read_bytes()
            if not pdf:
                raise PdfConversionError(
                    f"LibreOffice PDF conversion produced an empty PDF (attempt {attempt})",
                    stage="convert",
                )

            return pdf


def convert_docx_to_pdf(source: bytes, converter: ConversionWorker | None = None) -> bytes:
    """Convert rendered DOCX bytes to PDF bytes."""

    worker = converter or LibreOfficePdfConverter()
    return worker.convert(source, source_suffix=".docx")


def _summarize_process_output(stdout: bytes, stderr: bytes) -> str:
    combined = b"\n".join(part for part in (stdout, stderr) if part).decode(
        "utf-8", errors="replace"
    )
    if not combined.strip():
        return ""

    summary = " ".join(combined.split())
    if len(summary) > 300:
        summary = f"{summary[:297]}..."
    return f": {summary}"
