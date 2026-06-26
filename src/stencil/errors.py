"""Stencil exception types."""

from pathlib import Path


class StencilError(Exception):
    """Base exception for Stencil."""


class UnsupportedFormatError(StencilError):
    """Raised when a requested template or output format is not supported."""


class RenderError(StencilError):
    """Raised when a template cannot be rendered."""

    def __init__(
        self,
        message: str,
        *,
        template_path: str | Path | None = None,
        stage: str | None = None,
    ) -> None:
        self.template_path = Path(template_path) if template_path is not None else None
        self.stage = stage

        details: list[str] = []
        if self.template_path is not None:
            details.append(f"template={self.template_path}")
        if stage is not None:
            details.append(f"stage={stage}")

        if details:
            message = f"{message} ({', '.join(details)})"

        super().__init__(message)
