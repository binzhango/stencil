# Stencil DOCX Example

This folder contains a small DOCX template and JSON payload that show the Phase 1 Stencil workflow.

## Files

- `templates/invoice.docx`: a DOCX template with Jinja-style placeholders
- `data/invoice.json`: sample data used to fill the template
- `templates/styled-status-report.docx`: a styled DOCX template showing style preservation
- `data/status-report.json`: sample data for the styled report
- `scripts/create_styled_status_template.py`: helper script that generated the styled template

The template includes:

- simple variables such as `{{ invoice.number }}`
- a conditional block for notes
- a loop over `line_items`

The styled status report example shows the recommended workflow for complex formatting: design the Word document visually first, then replace only the dynamic text with placeholders. The rendered values inherit the styles from the template.

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

Render the styled example:

```bash
uv run stencil render examples/templates/styled-status-report.docx examples/data/status-report.json --output examples/out/styled-status-report.docx
```

Open `examples/out/styled-status-report.docx` and compare it with `examples/templates/styled-status-report.docx`. The title, subtitle, table colors, status color, and risk-note styling come from the template.

## Run With Python

```python
import json
from pathlib import Path

from stencil import render

data = json.loads(Path("examples/data/invoice.json").read_text())

document = render(
    "examples/templates/invoice.docx",
    data,
    output_format="docx",
)

Path("examples/out/invoice.docx").parent.mkdir(parents=True, exist_ok=True)
Path("examples/out/invoice.docx").write_bytes(document)
```

## Current Limitation

Phase 1 supports DOCX input and DOCX output only. PDF, XLSX, and PPTX are later roadmap phases.
