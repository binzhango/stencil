"""Optional FastAPI service layer for trusted internal callers."""

from __future__ import annotations

import logging
import time
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, cast

from .errors import StencilError
from .render import render

logger = logging.getLogger("stencil.api")


@dataclass
class RenderMetrics:
    """Small in-memory counters for a single service process."""

    renders_total: int = 0
    failures_total: int = 0
    render_seconds_total: float = 0.0
    renders_by_format: Counter[str] = field(default_factory=Counter)
    failures_by_stage: Counter[str] = field(default_factory=Counter)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def record_success(self, *, output_format: str, duration_seconds: float) -> None:
        with self._lock:
            self.renders_total += 1
            self.render_seconds_total += duration_seconds
            self.renders_by_format[output_format] += 1

    def record_failure(self, *, stage: str, duration_seconds: float) -> None:
        with self._lock:
            self.failures_total += 1
            self.render_seconds_total += duration_seconds
            self.failures_by_stage[stage] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            average = (
                self.render_seconds_total / self.renders_total
                if self.renders_total
                else 0.0
            )
            return {
                "renders_total": self.renders_total,
                "failures_total": self.failures_total,
                "render_seconds_total": round(self.render_seconds_total, 6),
                "render_seconds_average": round(average, 6),
                "renders_by_format": dict(self.renders_by_format),
                "failures_by_stage": dict(self.failures_by_stage),
            }


def create_app(
    *,
    template_root: str | Path | None = None,
    renderer: Callable[..., bytes] = render,
    metrics: RenderMetrics | None = None,
) -> Any:
    """Create the optional trusted-internal FastAPI app.

    FastAPI is imported lazily so the core package remains usable without the
    `api` extra installed.
    """

    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import Response
    except ImportError as exc:  # pragma: no cover - depends on optional extras
        raise RuntimeError(
            "Stencil API requires the 'api' extra; install with office-stencil[api]"
        ) from exc

    resolved_template_root = (
        Path(template_root).expanduser().resolve() if template_root is not None else None
    )
    app_metrics = metrics or RenderMetrics()

    app = FastAPI(
        title="Stencil Render API",
        version="0.1.0",
        description="Trusted internal HTTP wrapper around the Stencil render API.",
    )

    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    def metrics_endpoint() -> dict[str, Any]:
        return app_metrics.snapshot()

    def render_endpoint(payload: dict[str, Any]) -> Any:
        started = time.perf_counter()
        template_path = _template_path_from_payload(payload, resolved_template_root)
        output_format = _output_format_from_payload(payload, template_path)
        data = payload.get("data", {})
        if not isinstance(data, dict):
            raise HTTPException(status_code=422, detail="data must be a JSON object")

        try:
            rendered = renderer(template_path, data, output_format=output_format)
        except StencilError as exc:
            duration = time.perf_counter() - started
            stage = getattr(exc, "stage", None) or "render"
            app_metrics.record_failure(stage=stage, duration_seconds=duration)
            logger.warning(
                "render_failed",
                extra={
                    "template_path": str(template_path),
                    "output_format": output_format,
                    "duration_seconds": duration,
                    "stage": stage,
                },
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        duration = time.perf_counter() - started
        app_metrics.record_success(output_format=output_format, duration_seconds=duration)
        logger.info(
            "render_completed",
            extra={
                "template_path": str(template_path),
                "output_format": output_format,
                "duration_seconds": duration,
            },
        )
        return Response(
            content=rendered,
            media_type=_media_type_for(output_format),
            headers={
                "X-Stencil-Output-Format": output_format,
                "X-Stencil-Render-Seconds": f"{duration:.6f}",
            },
        )

    app.add_api_route("/healthz", healthz, methods=["GET"])
    app.add_api_route("/metrics", metrics_endpoint, methods=["GET"])
    app.add_api_route("/render", render_endpoint, methods=["POST"])

    return app


def _template_path_from_payload(
    payload: Mapping[str, Any],
    template_root: Path | None,
) -> Path:
    raw_template_path = payload.get("template_path")
    if not isinstance(raw_template_path, str) or not raw_template_path:
        raise _http_exception(422, "template_path must be a non-empty string")

    template_path = Path(raw_template_path).expanduser()
    if template_root is None:
        return template_path

    resolved = (template_root / template_path).resolve()
    if not resolved.is_relative_to(template_root):
        raise _http_exception(400, "template_path must stay inside template_root")
    return resolved


def _output_format_from_payload(payload: Mapping[str, Any], template_path: Path) -> str:
    raw_output_format = payload.get("output_format")
    if raw_output_format is None:
        return template_path.suffix.removeprefix(".").lower()
    if not isinstance(raw_output_format, str) or not raw_output_format:
        raise _http_exception(422, "output_format must be a non-empty string")
    return raw_output_format.lower()


def _media_type_for(output_format: str) -> str:
    return {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
    }.get(output_format, "application/octet-stream")


def _http_exception(status_code: int, detail: str) -> Exception:
    try:
        from fastapi import HTTPException
    except ImportError as exc:  # pragma: no cover - depends on optional extras
        raise RuntimeError(
            "Stencil API requires the 'api' extra; install with office-stencil[api]"
        ) from exc
    return cast(Exception, HTTPException(status_code=status_code, detail=detail))
