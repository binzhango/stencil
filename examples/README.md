# Stencil Examples

This folder contains DOCX templates and JSON payloads that show the Stencil workflow.

The examples are versioned package fixtures. When a template or payload changes, update the expected-output tests in `tests/test_render.py` in the same change.

## Files

- `templates/invoice.docx`: a DOCX template with Jinja-style placeholders
- `data/invoice.json`: sample data used to fill the template
- `templates/styled-status-report.docx`: a styled DOCX template with a page header, sections, tables, and a risk callout
- `data/status-report.json`: sample data for the styled report
- `scripts/render_styled_status_pdf.py`: minimal Python example that renders the styled report to PDF
- `scripts/create_styled_status_template.py`: helper script that generated the styled template

The template includes:

- simple variables such as `{{ invoice.number }}`
- a conditional block for notes
- a loop over `line_items`

The styled status report example shows the recommended workflow for complex formatting: design the Word document visually first, then replace only the dynamic text with placeholders. The rendered values inherit the styles from the template.

## Authoring Rules

- Keep dynamic data in JSON and visual design in the DOCX template.
- Use complete Jinja tags such as `{{ project.name }}` and `{% if risk_note %}`.
- Retype a whole tag if Word splits or styles only part of it.
- Test templates with the CLI before using them in another application.
- Keep templates trusted; Stencil does not sandbox untrusted documents.

## Run With The CLI

Install dependencies first:

```bash
uv sync --dev
```

Render the example:

```bash
uv run stencil render examples/templates/invoice.docx examples/data/invoice.json --output examples/out/invoice.docx
```

Open `examples/out/invoice.docx` in Word, LibreOffice, or another DOCX viewer.

Render the invoice to PDF:

```bash
uv run stencil render examples/templates/invoice.docx examples/data/invoice.json --output examples/out/invoice.pdf
```

PDF output requires LibreOffice to be installed and available as `soffice` or `libreoffice`.

Render the styled report to PDF:

```bash
uv run python examples/scripts/render_styled_status_pdf.py
```

Render the styled example:

```bash
uv run stencil render examples/templates/styled-status-report.docx examples/data/status-report.json --output examples/out/styled-status-report.docx
```

Open `examples/out/styled-status-report.docx` and compare it with `examples/templates/styled-status-report.docx`. The page header, title, section headings, table colors, status color, footer, and risk-note styling come from the template.

## Run With Python

```python
import json
from pathlib import Path

from stencil import render

data = json.loads(Path("examples/data/invoice.json").read_text())

document = render(
    "examples/templates/styled-status-report.docx",
    data,
    output_format="pdf",
)

Path("examples/out/styled-status-report.pdf").parent.mkdir(parents=True, exist_ok=True)
Path("examples/out/styled-status-report.pdf").write_bytes(document)
```

## Current Limitation

Stencil currently supports DOCX input with DOCX or PDF output, and XLSX input with XLSX or PDF output. PPTX is a later roadmap phase.
