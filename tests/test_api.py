import importlib.util
from pathlib import Path
from typing import Any

import pytest

from stencil.api import RenderMetrics, create_app
from stencil.errors import RenderError

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("fastapi") is None,
    reason="FastAPI extra is not installed",
)


def _test_client(app: Any) -> Any:
    testclient = pytest.importorskip("fastapi.testclient")
    return testclient.TestClient(app)


def test_api_renders_document_and_records_metrics() -> None:
    def fake_renderer(
        template_path: Path,
        data: dict[str, Any],
        *,
        output_format: str,
    ) -> bytes:
        assert template_path == Path("template.docx")
        assert data == {"name": "Acme"}
        assert output_format == "pdf"
        return b"%PDF rendered"

    app = create_app(renderer=fake_renderer)
    client = _test_client(app)

    response = client.post(
        "/render",
        json={
            "template_path": "template.docx",
            "data": {"name": "Acme"},
            "output_format": "pdf",
        },
    )

    assert response.status_code == 200
    assert response.content == b"%PDF rendered"
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["x-stencil-output-format"] == "pdf"
    assert client.get("/metrics").json()["renders_total"] == 1


def test_api_constrains_templates_to_configured_root(tmp_path: Path) -> None:
    app = create_app(template_root=tmp_path, renderer=lambda *args, **kwargs: b"unused")
    client = _test_client(app)

    response = client.post(
        "/render",
        json={"template_path": "../escape.docx", "data": {}},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "template_path must stay inside template_root"


def test_api_records_render_failures() -> None:
    def fake_renderer(
        template_path: Path,
        data: dict[str, Any],
        *,
        output_format: str,
    ) -> bytes:
        raise RenderError("broken template", stage="render", template_path=template_path)

    metrics = RenderMetrics()
    app = create_app(renderer=fake_renderer, metrics=metrics)
    client = _test_client(app)

    response = client.post(
        "/render",
        json={"template_path": "template.docx", "data": {}},
    )

    assert response.status_code == 400
    assert "broken template" in response.json()["detail"]
    assert client.get("/metrics").json()["failures_by_stage"] == {"render": 1}
