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
- optional FastAPI service wrapper for trusted internal callers
- template authoring guidance for supported DOCX, PPTX, and XLSX features
- XLSX cell substitutions and row loops
- versioned sample templates covered by expected-output tests
- optional validated financial-report skill with HTML and Chromium PDF output
- DOCX-first roadmap in local ignored docs

What does not exist yet:

- distributed queues, untrusted template sandboxing, or hosted multi-tenant operations
- a general-purpose CSV/DataFrame-to-financial-contract adapter; tabular finance data must first be mapped to the documented canonical JSON contract

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

## Financial Report Skill

The repository includes an optional
[`financial-report-generator`](.agents/skills/financial-report-generator/SKILL.md) skill for
validated monthly management reports. It is separate from the Office-template
`stencil render` command: it renders a self-contained HTML report with Jinja2 and
converts that HTML to a print-ready PDF with Playwright Chromium.

The report contains five fixed sections:

- executive summary, KPIs, charts, and sourced commentary
- income statement
- balance sheet
- cash-flow statement
- controls, warnings, source inventory, and reproducibility hashes

Install the optional PDF runtime once:

```bash
uv sync --extra reports --dev
uv run playwright install chromium
```

Poppler commands `pdfinfo` and `pdftotext` must also be available for final PDF
geometry and physical-page content verification.

### Generate a report from canonical JSON

The builder accepts the canonical contract documented in
[`data-contract.md`](.agents/skills/financial-report-generator/references/data-contract.md).
Start with the bundled example:

```bash
uv run python .agents/skills/financial-report-generator/scripts/build_report.py \
  .agents/skills/financial-report-generator/assets/example-input.json \
  --out-dir report-output

uv run python .agents/skills/financial-report-generator/scripts/render_report.py \
  report-output/report.html \
  --output report-output/report.pdf

uv run python .agents/skills/financial-report-generator/scripts/verify_output.py \
  report-output/report.html \
  --pdf report-output/report.pdf \
  --render-diagnostics report-output/RENDER_REPORT.json \
  --output report-output/VERIFY_REPORT.json
```

Treat any failed gate as a release blocker. Review every warning and visually
inspect all PDF pages before distributing the report.

The output package contains:

- `report.html`: self-contained report source
- `report.pdf`: final Chromium-rendered report
- `GATE_REPORT.json`: financial validation results and warnings
- `DATA_MANIFEST.json`: input, template, and generation metadata
- `RENDER_REPORT.json`: browser attempts and layout diagnostics
- `VERIFY_REPORT.json`: HTML and physical-PDF verification results

### Use CSV or DataFrame input

CSV, Excel, pandas, and Polars DataFrames are not injected directly into the
Jinja template. First normalize their rows into the canonical JSON contract; the
builder then validates and derives the financial values before constructing the
template view model.

For a straightforward monthly export, a useful intermediate table is:

```csv
section,field,current,prior
income,revenue,12850,11960
income,cost_of_revenue,7710,7415
balance,cash,4680,4210
cash_flow,operating_cash_flow,1180,920
cash_flow,investing_cash_flow,-430,-355
```

When asking an agent to generate a report from a financial CSV, use a request
similar to:

> Read `monthly-financials.csv`, inspect its columns and sign conventions, map
> it to the financial report canonical contract, preserve decimal values as
> strings, record the source file and hash, run every build/render/verification
> gate, visually inspect all five pages, and deliver the complete report package.

The normalization step must:

- map every source column or row to an allowed canonical section and field
- preserve monetary values as decimal strings rather than binary floats
- reject duplicate fields, blanks, NaN, and missing required values
- never replace missing financial values with zero
- make currency, scale, periods, and cash-flow signs explicit
- retain the original source and record its stable identifier and SHA-256 hash

This boundary keeps arbitrary spreadsheet layouts out of the presentation
template and makes the report reproducible. A reusable automatic DataFrame
normalizer is planned but is not currently part of the package.

## Optional Service

The Python API and CLI are the primary package boundary. When another internal
system needs HTTP access, install the optional API dependencies and run the
trusted service wrapper:

```bash
uv sync --extra api --dev
uv run uvicorn 'stencil.api:create_app' --factory
```

The service exposes:

- `GET /healthz` for process health
- `GET /metrics` for in-memory render and failure counters
- `POST /render` with `template_path`, `data`, and optional `output_format`

For deployments that serve a known template directory, pass a template root from
application code:

```python
from stencil.api import create_app

app = create_app(template_root="/srv/stencil/templates")
```

The service is still trusted-internal infrastructure. It logs render outcomes and
keeps per-process counters, but it does not sandbox untrusted templates or add a
distributed queue.

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
- `Unsupported template format`: use a `.docx`, `.xlsx`, or `.pptx` template.
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

All roadmap phases now have a first internal implementation. Future work should
be driven by specific production needs, such as persistent metrics export,
queue-backed workloads, sandboxing for untrusted templates, image replacement,
or richer chart/formula rewrites.

The detailed local roadmap lives in `docs/`, which is intentionally ignored by git because it is personal planning material.

## Dependencies

Runtime dependencies:

- `jinja2`: template expressions, conditionals, and loops
- `docxtpl`: DOCX rendering for the first production milestone
- `lxml`: Office XML parsing and manipulation
- `openpyxl`: XLSX workbook loading, editing, and serialization
- `typer`: CLI framework

Optional API dependencies:

- `fastapi`: optional HTTP service layer
- `uvicorn[standard]`: ASGI server for the optional API

Optional worker dependencies:

- `rq`: lightweight Redis-backed queue option
- `celery`: larger distributed worker option
- `redis`: queue/backend client

Optional financial report dependencies:

- `playwright`: deterministic HTML-to-PDF rendering with Chromium

Development dependencies:

- `pytest`: test runner
- `pytest-cov`: coverage reporting
- `ruff`: linting and import sorting
- `mypy`: static type checking

External system dependency for PDF output:

- LibreOffice / `soffice`: converts rendered Office documents to PDF
- Playwright Chromium: renders the optional financial report HTML to PDF
- Poppler / `pdfinfo` / `pdftotext`: verifies financial report page geometry and content

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

The repo uses Release Please and the GitHub Actions workflow at
`.github/workflows/publish.yml`. A push to `main` runs tests, linting, and the
package build before any release action. Release Please then opens or updates a
release pull request containing the next version and generated changelog entry.

Use Conventional Commit prefixes in pull-request squash commit titles:

- `fix:` creates a patch release, such as `0.6.0` to `0.6.1`
- `feat:` creates a minor release, such as `0.6.0` to `0.7.0`
- `feat!:` or a `BREAKING CHANGE:` footer creates a major release
- `chore:` and most documentation-only changes do not create releases

The release sequence is:

1. Merge feature and fix pull requests into `main` using Conventional Commit titles.
2. The workflow tests, lints, and builds the package.
3. Release Please opens or refreshes the release pull request.
4. Review and merge that release pull request.
5. The workflow repeats its quality gates against the versioned release commit.
6. Release Please creates the version tag and GitHub Release.
7. The workflow attaches the wheel and source distribution to the release.
8. The workflow publishes the same distributions to PyPI.

The PyPI job runs only when Release Please creates a new release. Existing
versions are not silently skipped; an attempted duplicate upload fails visibly.

If artifact attachment or PyPI upload fails after the GitHub Release was already
created, fix the workflow and run it manually from `main` with the existing tag
in the `release_tag` input. This recovery path rebuilds, retests, and republishes
that exact release without requiring Release Please to create another tag.

One-time PyPI token setup:

- Create or use the PyPI project named `office-stencil`.
- Create a PyPI API token. Prefer a project-scoped token for `office-stencil` after the first release exists.
- Add the token to GitHub as an Actions secret named `PYPI_API_TOKEN`.
- The publish workflow uses `user: __token__` and `password: ${{ secrets.PYPI_API_TOKEN }}`.

In repository settings, GitHub Actions must have permission to create pull
requests. The workflow grants its token `contents: write` and
`pull-requests: write` only to the Release Please job.

Release Please updates `pyproject.toml` and `CHANGELOG.md`; contributors should
not manually bump routine release versions. To force a specific version, put a
`Release-As: x.y.z` footer in a releasable Conventional Commit. The runtime
`stencil.__version__` continues to come from installed package metadata, so there
is no second version constant to maintain.

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
