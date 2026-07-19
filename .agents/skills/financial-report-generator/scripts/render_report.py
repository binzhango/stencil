#!/usr/bin/env python3
"""Render a self-contained financial-report HTML file to a checked PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

EXPECTED_SECTIONS = [
    "executive-summary",
    "income-statement",
    "balance-sheet",
    "cash-flow",
    "controls-and-provenance",
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


def static_preflight(source: Path) -> list[str]:
    text = source.read_text(encoding="utf-8")
    errors: list[str] = []
    if re.search(r"(?:src|href)=[\"']https?://", text, re.I):
        errors.append("remote resources are forbidden")
    if re.search(r"\{[{%].*?[}%]\}", text, re.S):
        errors.append("unresolved Jinja template syntax remains in the HTML")
    sections = re.findall(r'<section\b[^>]*data-report-section="([^"]+)"', text, re.I)
    if sections != EXPECTED_SECTIONS:
        errors.append(f"report sections are {sections!r}; expected {EXPECTED_SECTIONS!r}")
    return errors


def collect_layout_diagnostics(page: Any) -> dict[str, Any]:
    return page.evaluate(
        """(expectedSections) => {
          const tolerance = 2;
          const sections = [...document.querySelectorAll('[data-report-section]')];
          const sectionDiagnostics = sections.map((section) => {
            const rect = section.getBoundingClientRect();
            const overflow = [...section.querySelectorAll('*')].filter((element) => {
              if (element.matches('style, script, defs, title, metadata')) return false;
              const child = element.getBoundingClientRect();
              return child.left < rect.left - tolerance || child.right > rect.right + tolerance ||
                child.top < rect.top - tolerance || child.bottom > rect.bottom + tolerance;
            }).slice(0, 20).map((element) => ({
              tag: element.tagName,
              className: String(element.className || ''),
              text: (element.textContent || '').trim().slice(0, 100),
            }));
            const footer = section.querySelector('.footer');
            const footerRect = footer ? footer.getBoundingClientRect() : null;
            return {
              name: section.dataset.reportSection,
              clientHeight: section.clientHeight,
              scrollHeight: section.scrollHeight,
              clientWidth: section.clientWidth,
              scrollWidth: section.scrollWidth,
              overflow,
              footerInsidePage: Boolean(footerRect) && footerRect.top >= rect.top - tolerance &&
                footerRect.bottom <= rect.bottom + tolerance,
            };
          });
          const brokenImages = [...document.images].filter((image) =>
            !image.complete || image.naturalWidth === 0
          ).map((image) => image.getAttribute('src') || '<inline>');
          const names = sectionDiagnostics.map((section) => section.name);
          const failures = [];
          if (JSON.stringify(names) !== JSON.stringify(expectedSections)) {
            failures.push(`section order mismatch: ${JSON.stringify(names)}`);
          }
          for (const section of sectionDiagnostics) {
            if (section.scrollHeight > section.clientHeight + tolerance) {
              const overflow = section.scrollHeight - section.clientHeight;
              failures.push(`${section.name}: vertical overflow ${overflow}px`);
            }
            if (section.scrollWidth > section.clientWidth + tolerance) {
              const overflow = section.scrollWidth - section.clientWidth;
              failures.push(`${section.name}: horizontal overflow ${overflow}px`);
            }
            if (section.overflow.length) {
              failures.push(`${section.name}: child content leaves page bounds`);
            }
            if (!section.footerInsidePage) {
              failures.push(`${section.name}: footer is outside page bounds`);
            }
          }
          if (brokenImages.length) failures.push(`broken images: ${brokenImages.join(', ')}`);
          return {sections: sectionDiagnostics, brokenImages, failures};
        }""",
        EXPECTED_SECTIONS,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=1)
    args = parser.parse_args()
    source = args.html.resolve()
    output = args.output.resolve()
    diagnostics_path = (args.diagnostics or args.output.with_name("RENDER_REPORT.json")).resolve()
    if not source.is_file():
        print(f"ERROR: HTML file not found: {source}", file=sys.stderr)
        return 2
    if args.timeout_seconds <= 0 or args.retries < 0:
        print("ERROR: timeout must be positive and retries cannot be negative", file=sys.stderr)
        return 2
    try:
        preflight_errors = static_preflight(source)
    except (OSError, UnicodeError) as exc:
        print(f"ERROR: could not read HTML: {exc}", file=sys.stderr)
        return 2
    if preflight_errors:
        diagnostics = {"status": "FAIL", "stage": "preflight", "errors": preflight_errors}
        atomic_write_json(diagnostics_path, diagnostics)
        print(f"FAIL: HTML preflight failed; see {diagnostics_path}", file=sys.stderr)
        return 1
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "ERROR: Playwright is required. Install it and its Chromium browser before rendering.",
            file=sys.stderr,
        )
        return 2

    output.parent.mkdir(parents=True, exist_ok=True)
    attempts: list[dict[str, Any]] = []
    timeout_ms = int(args.timeout_seconds * 1000)
    for attempt in range(1, args.retries + 2):
        temporary_pdf = output.with_name(f".{output.name}.attempt-{attempt}.tmp")
        browser = None
        try:
            with sync_playwright() as runtime:
                browser = runtime.chromium.launch(
                    headless=True,
                    args=["--disable-dev-shm-usage"],
                )
                page = browser.new_page(
                    viewport={"width": 1280, "height": 900}, device_scale_factor=1
                )
                page.set_default_timeout(timeout_ms)
                page.emulate_media(media="print")
                page.goto(source.as_uri(), wait_until="load", timeout=timeout_ms)
                page.evaluate("async () => { if (document.fonts) await document.fonts.ready; }")
                page.wait_for_function(
                    "() => [...document.images].every((image) => image.complete)",
                    timeout=timeout_ms,
                )
                layout = collect_layout_diagnostics(page)
                attempts.append({"attempt": attempt, "layout": layout})
                if layout["failures"]:
                    diagnostics = {
                        "status": "FAIL",
                        "stage": "layout",
                        "html": str(source),
                        "html_sha256": sha256(source),
                        "attempts": attempts,
                    }
                    atomic_write_json(diagnostics_path, diagnostics)
                    print(
                        f"FAIL: report layout gates failed; see {diagnostics_path}", file=sys.stderr
                    )
                    return 1
                page.pdf(
                    path=str(temporary_pdf),
                    print_background=True,
                    prefer_css_page_size=True,
                    tagged=True,
                )
                browser.close()
                browser = None
            if temporary_pdf.stat().st_size < 10_000 or not temporary_pdf.read_bytes().startswith(
                b"%PDF"
            ):
                raise RuntimeError("Chromium produced an invalid or unexpectedly small PDF")
            temporary_pdf.replace(output)
            diagnostics = {
                "status": "PASS",
                "stage": "complete",
                "html": str(source),
                "html_sha256": sha256(source),
                "pdf": str(output),
                "pdf_sha256": sha256(output),
                "pdf_bytes": output.stat().st_size,
                "attempts": attempts,
            }
            atomic_write_json(diagnostics_path, diagnostics)
            print(f"PASS: wrote {output}")
            return 0
        except Exception as exc:
            attempts.append({"attempt": attempt, "error": str(exc)})
            if browser is not None:
                browser.close()
            temporary_pdf.unlink(missing_ok=True)
            if attempt > args.retries:
                diagnostics = {
                    "status": "ERROR",
                    "stage": "chromium",
                    "html": str(source),
                    "attempts": attempts,
                }
                atomic_write_json(diagnostics_path, diagnostics)
                print(
                    f"ERROR: Chromium render failed after {attempt} attempt(s): {exc}",
                    file=sys.stderr,
                )
                return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
