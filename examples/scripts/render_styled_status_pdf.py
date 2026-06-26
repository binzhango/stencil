"""Render the styled status report example to PDF."""

import json
from pathlib import Path

from stencil import render

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "styled-status-report.docx"
DATA = ROOT / "data" / "status-report.json"
OUTPUT = ROOT / "out" / "styled-status-report.pdf"


def main() -> None:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    pdf = render(TEMPLATE, payload, output_format="pdf")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(pdf)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
