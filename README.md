# Stencil

Stencil is a Python render engine for reusable Office document templates.

It is designed for workflows where a `.docx`, `.xlsx`, or `.pptx` template contains placeholders, loops, and conditionals, and application data fills the template to produce a finished Office document or PDF.

```bash
stencil render invoice.docx data.json --output invoice.pdf
```

The project starts with DOCX because it is the fastest path to a useful internal tool. XLSX and PPTX are planned as separate format engines behind the same public API.

## Status

Pre-alpha DOCX MVP.

What exists now:

- `uv`-compatible Python package metadata
- Python `>=3.12`
- `stencil` import package
- `render()` API for DOCX templates
- `stencil render` CLI command for JSON data
- DOCX-first roadmap in local ignored docs

What does not exist yet:

- Stable public API
- PDF conversion worker
- XLSX rendering
- PPTX rendering

## Naming

The product, import package, and CLI command are named `stencil`.

The PyPI distribution name is currently `office-stencil` because `stencil` is already taken on PyPI by an old package.

```toml
[project]
name = "office-stencil"

[project.scripts]
stencil = "stencil.cli:app"
```

## API

```python
from stencil import render

document = render(
    template_path="invoice.docx",
    data={
        "customer": "Acme",
        "line_items": [
            {"description": "Implementation", "amount": 1200},
        ],
    },
    output_format="docx",
)
```

Phase 1 supports DOCX input and DOCX output only. The exact API may change while the project is pre-alpha.

## CLI

```bash
stencil render invoice.docx data.json --output invoice.docx
```

The CLI reads a top-level JSON object from the data file and writes the rendered document bytes to the output path.

PDF output is planned for a later phase.

## Example

See [examples/](examples/) for a runnable DOCX example with:

- `examples/templates/invoice.docx`
- `examples/data/invoice.json`
- `examples/templates/styled-status-report.docx`
- `examples/data/status-report.json`

```bash
uv sync --dev
uv run stencil render examples/templates/invoice.docx examples/data/invoice.json --output examples/out/invoice.docx
uv run stencil render examples/templates/styled-status-report.docx examples/data/status-report.json --output examples/out/styled-status-report.docx
```

## Roadmap

1. Foundation and proof of shape
2. DOCX MVP
3. PDF conversion and reliability
4. Internal package polish
5. XLSX engine
6. PPTX engine
7. Optional service layer and operations

The detailed local roadmap lives in `docs/`, which is intentionally ignored by git because it is personal planning material.

## Dependencies

Runtime dependencies:

- `jinja2`: template expressions, conditionals, and loops
- `docxtpl`: DOCX rendering for the first production milestone
- `lxml`: Office XML parsing and manipulation
- `openpyxl`: XLSX workbook inspection and future spreadsheet support
- `typer`: CLI framework

Optional API dependencies:

- `fastapi`: future HTTP service layer
- `uvicorn[standard]`: ASGI server for the optional API

Optional worker dependencies:

- `rq`: lightweight Redis-backed queue option
- `celery`: larger distributed worker option
- `redis`: queue/backend client

Development dependencies:

- `pytest`: test runner
- `pytest-cov`: coverage reporting
- `ruff`: linting and import sorting
- `mypy`: static type checking

External system dependency:

- LibreOffice / `soffice`: planned conversion engine for PDF output

## Local Development

This repo uses `uv`, but dependencies have not been installed yet.

Install dependencies when ready:

```bash
uv sync --dev
```

Run tests:

```bash
uv run pytest
```

Run linting:

```bash
uv run ruff check .
```

Run type checking:

```bash
uv run mypy
```

## Design Notes

Office files are zipped XML packages, but each format has different failure modes.

- DOCX can split template tags across Word text runs.
- XLSX often stores text in shared strings, so naive replacement can mutate unrelated cells.
- PPTX repeated slides require cloning slide XML, relationships, presentation ordering, and content type entries.
- PDF conversion through LibreOffice needs timeouts, retries, cleanup, and worker isolation.

Stencil should stay milestone-driven: ship a reliable DOCX engine first, then use real needs to decide when XLSX, PPTX, and service infrastructure are worth the extra complexity.

## License

MIT. See [LICENSE](LICENSE).
