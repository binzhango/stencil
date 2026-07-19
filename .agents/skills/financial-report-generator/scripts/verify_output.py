#!/usr/bin/env python3
"""Verify financial-report HTML, render diagnostics, and final PDF geometry."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

REQUIRED_SECTIONS = [
    "executive-summary",
    "income-statement",
    "balance-sheet",
    "cash-flow",
    "controls-and-provenance",
]
PAGE_POINTS = {"A4": (595.28, 841.89), "Letter": (612.0, 792.0)}
PAGE_HEADINGS = [
    "Monthly Management Report",
    "Income statement",
    "Balance sheet",
    "Cash-flow statement",
    "Controls and provenance",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def gate(
    items: list[dict[str, Any]], name: str, passed: bool, detail: str, **evidence: Any
) -> None:
    items.append(
        {"name": name, "status": "PASS" if passed else "FAIL", "detail": detail, **evidence}
    )


def pdf_metadata(path: Path) -> tuple[dict[str, Any], str | None]:
    pdfinfo = shutil.which("pdfinfo")
    if not pdfinfo:
        return {}, "pdfinfo is unavailable; install Poppler to verify page geometry"
    try:
        process = subprocess.run(
            [pdfinfo, str(path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {}, f"pdfinfo failed: {exc}"
    if process.returncode != 0:
        return {}, f"pdfinfo exited {process.returncode}: {process.stderr.strip()}"
    pages = re.search(r"^Pages:\s+(\d+)", process.stdout, re.M)
    size = re.search(r"^Page size:\s+([\d.]+) x ([\d.]+) pts", process.stdout, re.M)
    if not pages or not size:
        return {}, "pdfinfo output did not contain page count and size"
    return {
        "pages": int(pages.group(1)),
        "width_points": float(size.group(1)),
        "height_points": float(size.group(2)),
    }, None


def pdf_text_pages(path: Path) -> tuple[list[str], str | None]:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return [], "pdftotext is unavailable; install Poppler to verify page content"
    try:
        process = subprocess.run(
            [pdftotext, "-layout", str(path), "-"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], f"pdftotext failed: {exc}"
    if process.returncode != 0:
        return [], f"pdftotext exited {process.returncode}: {process.stderr.strip()}"
    return [page.strip() for page in process.stdout.split("\f") if page.strip()], None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--render-diagnostics", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-pages", type=int)
    args = parser.parse_args()
    items: list[dict[str, Any]] = []
    text = args.html.read_text(encoding="utf-8") if args.html.is_file() else ""
    gate(items, "html-exists", bool(text), str(args.html))
    unresolved = sorted(set(re.findall(r"\{[{%].*?[}%]\}", text, re.S)))
    gate(
        items,
        "template-complete",
        not unresolved,
        "no unresolved Jinja syntax"
        if not unresolved
        else f"{len(unresolved)} unresolved block(s)",
    )
    sections = re.findall(r'<section\b[^>]*data-report-section="([^"]+)"', text, re.I)
    gate(
        items,
        "required-sections",
        sections == REQUIRED_SECTIONS,
        "all five sections present once and in order"
        if sections == REQUIRED_SECTIONS
        else f"sections={sections!r}",
    )
    remote = re.findall(r'(?:src|href)=["\']https?://', text, flags=re.I)
    gate(items, "offline-resources", not remote, "no remote resources")
    gate(
        items,
        "print-css",
        "@page" in text and "@media print" in text,
        "paged-media rules present",
    )
    body_page_size = re.search(r'data-page-size="([^"]+)"', text)
    body_page_count = re.search(r'data-expected-pages="(\d+)"', text)
    page_size = body_page_size.group(1) if body_page_size else ""
    expected_pages = args.expected_pages or (
        int(body_page_count.group(1)) if body_page_count else len(REQUIRED_SECTIONS)
    )
    gate(
        items,
        "html-page-contract",
        page_size in PAGE_POINTS and expected_pages > 0,
        f"page_size={page_size or '<missing>'}; expected_pages={expected_pages}",
    )

    if args.pdf:
        pdf_ok = (
            args.pdf.is_file()
            and args.pdf.stat().st_size > 10_000
            and args.pdf.read_bytes()[:4] == b"%PDF"
        )
        gate(
            items,
            "pdf-exists",
            pdf_ok,
            f"{args.pdf} ({args.pdf.stat().st_size if args.pdf.is_file() else 0} bytes)",
            sha256=sha256(args.pdf) if pdf_ok else None,
        )
        if pdf_ok:
            metadata, metadata_error = pdf_metadata(args.pdf)
            gate(
                items,
                "pdf-metadata",
                metadata_error is None,
                metadata_error or "page metadata read with pdfinfo",
                metadata=metadata,
            )
            if metadata_error is None:
                gate(
                    items,
                    "pdf-page-count",
                    metadata["pages"] == expected_pages,
                    f"pages={metadata['pages']}; expected={expected_pages}",
                )
                expected_width, expected_height = PAGE_POINTS.get(page_size, (0.0, 0.0))
                size_ok = (
                    abs(metadata["width_points"] - expected_width) <= 2
                    and abs(metadata["height_points"] - expected_height) <= 2
                )
                gate(
                    items,
                    "pdf-page-size",
                    size_ok,
                    f"actual={metadata['width_points']}x{metadata['height_points']}pt; "
                    f"expected={expected_width}x{expected_height}pt",
                )
            pages, text_error = pdf_text_pages(args.pdf)
            gate(
                items,
                "pdf-text-extraction",
                text_error is None,
                text_error or f"extracted text from {len(pages)} page(s)",
            )
            if text_error is None:
                content_ok = len(pages) == expected_pages and all(
                    heading in page and f"Page {index} of {expected_pages}" in page
                    for index, (heading, page) in enumerate(
                        zip(PAGE_HEADINGS, pages, strict=False), start=1
                    )
                )
                gate(
                    items,
                    "pdf-page-content",
                    content_ok,
                    "required heading and footer found on every physical page"
                    if content_ok
                    else "a required heading or page footer is missing from its physical page",
                )
        diagnostics_path = args.render_diagnostics or args.pdf.with_name("RENDER_REPORT.json")
        try:
            diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
            diagnostics_ok = diagnostics.get("status") == "PASS"
        except (OSError, json.JSONDecodeError):
            diagnostics, diagnostics_ok = {}, False
        gate(
            items,
            "render-diagnostics",
            diagnostics_ok,
            f"{diagnostics_path}: {diagnostics.get('status', 'missing or unreadable')}",
        )

    overall = "PASS" if all(item["status"] == "PASS" for item in items) else "FAIL"
    result = {
        "overall": overall,
        "html": {
            "path": str(args.html),
            "sha256": sha256(args.html) if args.html.is_file() else None,
        },
        "pdf": str(args.pdf) if args.pdf else None,
        "gates": items,
    }
    atomic_write_json(args.output, result)
    print(f"{overall}: wrote {args.output}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
