from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
BUILD = SKILL_DIR / "scripts" / "build_report.py"
RENDER = SKILL_DIR / "scripts" / "render_report.py"
VERIFY = SKILL_DIR / "scripts" / "verify_output.py"
EXAMPLE = SKILL_DIR / "assets" / "example-input.json"
GENERATED_AT = "2026-07-18T12:00:00Z"


def run(*arguments: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *(str(argument) for argument in arguments)],
        capture_output=True,
        text=True,
        check=False,
    )


def build(
    input_path: Path, output_dir: Path, *extra: str | Path
) -> subprocess.CompletedProcess[str]:
    return run(
        BUILD,
        input_path,
        "--out-dir",
        output_dir,
        "--generated-at",
        GENERATED_AT,
        *extra,
    )


def test_build_is_reproducible_and_autoescapes_input(tmp_path: Path) -> None:
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["metadata"]["company_name"] = '<script>alert("unsafe")</script>'
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(data), encoding="utf-8")
    first, second = tmp_path / "first", tmp_path / "second"

    first_result = build(input_path, first)
    second_result = build(input_path, second)

    assert first_result.returncode == 0, first_result.stderr
    assert second_result.returncode == 0, second_result.stderr
    first_html = (first / "report.html").read_text(encoding="utf-8")
    assert first_html == (second / "report.html").read_text(encoding="utf-8")
    assert "<script>alert" not in first_html
    assert "&lt;script&gt;alert" in first_html
    gate_report = json.loads((first / "GATE_REPORT.json").read_text(encoding="utf-8"))
    assert gate_report["overall"] == "PASS"
    manifest = json.loads((first / "DATA_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["render_contract"] == {
        "engine": "jinja2",
        "undefined": "strict",
        "autoescape": True,
    }


def test_strict_undefined_fails_closed(tmp_path: Path) -> None:
    template = tmp_path / "broken.html"
    template.write_text("<html><body>{{ missing_value }}</body></html>", encoding="utf-8")
    output_dir = tmp_path / "output"

    result = build(EXAMPLE, output_dir, "--template", template)

    assert result.returncode == 1
    assert not (output_dir / "report.html").exists()
    report = json.loads((output_dir / "GATE_REPORT.json").read_text(encoding="utf-8"))
    assert report["overall"] == "FAIL"
    assert any(gate["name"] == "template-render" for gate in report["gates"])


def test_html_verifier_accepts_checked_build(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    assert build(EXAMPLE, output_dir).returncode == 0

    result = run(
        VERIFY,
        output_dir / "report.html",
        "--output",
        output_dir / "VERIFY_REPORT.json",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    verification = json.loads((output_dir / "VERIFY_REPORT.json").read_text(encoding="utf-8"))
    assert verification["overall"] == "PASS"


@pytest.mark.skipif(
    os.environ.get("RUN_FINANCIAL_PDF_TESTS") != "1" or shutil.which("pdfinfo") is None,
    reason="set RUN_FINANCIAL_PDF_TESTS=1 with Chromium and pdfinfo installed",
)
def test_full_pdf_pipeline(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    assert build(EXAMPLE, output_dir).returncode == 0
    render = run(
        RENDER,
        output_dir / "report.html",
        "--output",
        output_dir / "report.pdf",
    )
    assert render.returncode == 0, render.stdout + render.stderr
    verify = run(
        VERIFY,
        output_dir / "report.html",
        "--pdf",
        output_dir / "report.pdf",
        "--output",
        output_dir / "VERIFY_REPORT.json",
    )
    assert verify.returncode == 0, verify.stdout + verify.stderr
