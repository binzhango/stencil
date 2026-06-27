# Stencil

Stencil is a Python render engine for reusable Office document templates.

It is designed for workflows where a `.docx`, `.xlsx`, or `.pptx` template contains placeholders, loops, and conditionals, and application data fills the template to produce a finished Office document or PDF.

```bash
stencil render invoice.docx data.json --output invoice.pdf
```

The project started with DOCX because it was the fastest path to a useful internal tool. XLSX and PPTX now use separate Office XML engines behind the same public API.

## Status

Pre-alpha internal Office render package.

What exists now:

- `uv`-compatible Python package metadata
- Python `>=3.12`
- `stencil` import package
- `render()` API for DOCX, PPTX, and XLSX templates
- PPTX text substitutions and repeated-slide loops
- `stencil render` CLI command for JSON data
- PDF output through LibreOffice conversion for DOCX, PPTX, and XLSX templates
- template authoring guidance for supported DOCX, PPTX, and XLSX features
- XLSX cell substitutions and row loops
- versioned sample templates covered by expected-output tests
- DOCX-first roadmap in local ignored docs

What does not exist yet:

- Stable public API

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

DOCX templates can currently render to `docx` or `pdf`. PPTX templates can render to `pptx` or `pdf`. XLSX templates can render to `xlsx` or `pdf`. The local Python API is the stable package boundary for the internal tool while the project remains pre-alpha.

## CLI

```bash
stencil render invoice.docx data.json --output invoice.docx
stencil render invoice.docx data.json --output invoice.pdf
stencil render deck.pptx data.json --output deck.pptx
stencil render deck.pptx data.json --output deck.pdf
stencil render workbook.xlsx data.json --output workbook.xlsx
stencil render workbook.xlsx data.json --output workbook.pdf
```

The CLI reads a top-level JSON object from the data file and writes the rendered document bytes to the output path.

PDF output requires LibreOffice to be installed and available as `soffice` or `libreoffice`.

## Template Authoring

Stencil templates are regular Word documents with Jinja-style tags in editable text. Design the document visually in Word or LibreOffice first, then replace only dynamic values with placeholders.

Supported DOCX features:

- variable replacement, such as `{{ customer.name }}`
- conditionals, such as `{% if invoice.note %}...{% endif %}`
- loops over lists, such as `{% for item in line_items %}...{% endfor %}`
- nested object and list access supported by Jinja2
- formatting inherited from the placeholder text in the template

Supported XLSX features:

- variable replacement in text cells, such as `{{ customer.name }}`
- typed whole-cell expressions, such as `{{ invoice.total }}`
- row loops with one or more body rows between `{% for item in line_items %}` and `{% endfor %}`
- style, number-format, row-height, and multiple-sheet preservation for rendered cells
- relative formula translation inside cloned loop rows

Supported PPTX features:

- variable replacement in slide text, such as `{{ customer.name }}`
- conditionals inside a text paragraph, such as `{% if project.on_track %}...{% endif %}`
- repeated slides with marker slides containing `{% for item in items %}` and `{% endfor %}`
- cloned-slide relationship, presentation-order, and content-type entries for repeated slides

Authoring rules:

- Keep one complete Jinja tag in one editable text run when possible. If Word splits a tag across runs, retype the whole tag in one pass.
- Keep styles, table borders, headers, footers, and layout in the DOCX template, not in JSON data.
- For XLSX row loops, put the loop start and end tags in their own cells on their own rows.
- For PPTX repeated-slide loops, put the loop start and end tags on their own marker slides.
- Use a top-level JSON object for CLI data.
- Use UTF-8 JSON and pass plain values, lists, and objects.
- Keep templates trusted. Stencil does not sandbox untrusted Office templates.

Known limitations:

- DOCX output formats are `docx` and `pdf`; PPTX output formats are `pptx` and `pdf`; XLSX output formats are `xlsx` and `pdf`.
- PDF output requires LibreOffice.
- PPTX chart/data rewriting, speaker-note rewriting, XLSX chart rewriting, complex formula-range adjustment, hosted APIs, Redis, Celery, and sandboxing are intentionally outside the current package boundary.
- Inline image replacement is not part of the packaged internal-tool API yet.

Troubleshooting:

- `Template file does not exist`: check the template path passed to the API or CLI.
- `Unsupported template format`: use a `.docx` or `.xlsx` template.
- `Unsupported output format`: use `docx`, `xlsx`, or `pdf`, or choose an output path with one of those suffixes.
- `Failed to render DOCX template`: check Jinja syntax and confirm every referenced field exists in the JSON object.
- `Failed to render PPTX template`: check Jinja syntax, repeated-slide marker slides, and confirm every referenced field exists in the JSON object.
- `Failed to render XLSX template`: check Jinja syntax, loop rows, and confirm every referenced field exists in the JSON object.
- `PDF conversion requires LibreOffice`: install LibreOffice and confirm `soffice` or `libreoffice` is on `PATH`.
- `LibreOffice PDF conversion timed out`: open the rendered document manually and simplify or repair the template.

## Example

See [examples/](examples/) for a runnable DOCX example with:

- `examples/templates/invoice.docx`
- `examples/data/invoice.json`
- `examples/templates/styled-status-report.docx`
- `examples/data/status-report.json`
- `examples/templates/pptx-status.pptx`
- `examples/data/pptx-status.json`

These examples are versioned with the package and covered by tests that check the rendered user-visible text.

```bash
uv sync --dev
uv run stencil render examples/templates/invoice.docx examples/data/invoice.json --output examples/out/invoice.docx
uv run stencil render examples/templates/invoice.docx examples/data/invoice.json --output examples/out/invoice.pdf
uv run stencil render examples/templates/styled-status-report.docx examples/data/status-report.json --output examples/out/styled-status-report.docx
uv run stencil render examples/templates/pptx-status.pptx examples/data/pptx-status.json --output examples/out/pptx-status.pptx
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
- `openpyxl`: XLSX workbook loading, editing, and serialization
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

External system dependency for PDF output:

- LibreOffice / `soffice`: converts rendered Office documents to PDF

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

## Publishing

The repo includes a GitHub Actions workflow at `.github/workflows/publish.yml`.

It publishes to PyPI when changes land on `main`:

1. Check out the repo.
2. Install `uv`.
3. Set up Python 3.12.
4. Install dependencies with `uv sync --dev`.
5. Run tests with `uv run pytest`.
6. Run linting with `uv run ruff check .`.
7. Build the package with `uv build`.
8. Read the matching release notes from `CHANGELOG.md`.
9. Create a GitHub Release tagged from the package version, such as `v0.1.0`.
10. Attach the built wheel and source distribution to the release.
11. Publish with the `PYPI_API_TOKEN` GitHub Actions secret.

One-time PyPI token setup:

- Create or use the PyPI project named `office-stencil`.
- Create a PyPI API token. Prefer a project-scoped token for `office-stencil` after the first release exists.
- Add the token to GitHub as an Actions secret named `PYPI_API_TOKEN`.
- The publish workflow uses `user: __token__` and `password: ${{ secrets.PYPI_API_TOKEN }}`.

PyPI and GitHub releases both require every upload to have a new version. Before merging a feature branch into `main`, update the `version` in `pyproject.toml` and add a matching section to `CHANGELOG.md`. The runtime `stencil.__version__` is read from installed package metadata, so there is no second version constant to keep in sync. The workflow creates the GitHub tag from that version and uses the matching changelog section as the release notes.

## Dependabot

The repo includes `.github/dependabot.yml`.

Dependabot checks weekly for:

- `uv` dependency updates from `pyproject.toml`
- GitHub Actions updates from `.github/workflows/`

Dependabot will open pull requests. Those PRs should go through the same CI and branch-protection rules as feature branches.

## Design Notes

Office files are zipped XML packages, but each format has different failure modes.

- DOCX can split template tags across Word text runs.
- XLSX often stores text in shared strings, so naive replacement can mutate unrelated cells.
- PPTX repeated slides require cloning slide XML, relationships, presentation ordering, and content type entries.
- PDF conversion through LibreOffice needs timeouts, retries, cleanup, and worker isolation.

Stencil should stay milestone-driven: keep the reliable Office engines focused, then use real needs to decide when service infrastructure is worth the extra complexity.

## License

MIT. See [LICENSE](LICENSE).
