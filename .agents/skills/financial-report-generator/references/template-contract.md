# Financial report Jinja template contract

## Purpose

Templates are presentation-only. Financial validation, derivation, sign conventions, source
controls, and commentary-reference checks run before template rendering. A template must never
recalculate financial statements or silently supply missing values.

## Environment

The builder loads the selected template through Jinja2 with:

- `StrictUndefined` so unknown or misspelled fields fail the build;
- HTML autoescaping enabled by default;
- a filesystem loader rooted at the selected template's directory, allowing local includes and
  macros without searching unrelated directories;
- atomic output replacement after all template release gates pass.

User-provided values are ordinary autoescaped strings. The only trusted `Markup` values are the
SVG charts generated internally from validated decimal values.

## Top-level context

- `document_title`: combined company and report title.
- `meta`: canonical metadata plus `scale_label`.
- `page_height`: printable content height matching the selected page size.
- `generated_at`, `generated_date`: UTC build timestamp.
- `summary_metrics`, `kpi_cards`: metric objects with `label`, `value`, and a `delta` object.
- `performance_chart`, `cash_chart`: internally generated safe SVG.
- `commentary`: validated commentary objects from the input contract.
- `income_rows`, `balance_rows`, `cash_flow_rows`: formatted statement row objects.
- `gross_margin_note`, `operating_margin_note`: current/prior formatted percentages.
- `controls`, `warnings`: validation gate objects.
- `sources`: source objects with a normalized `location` display field.
- `input_hash`, `template_hash`: reproducibility hashes.

Statement rows expose `label`, `current`, `prior`, `change`, and `class_name`. Metric deltas expose
`class_name` (`up` or `down`) and `text`.

## Required document structure

The default release contract contains exactly five ordered section elements:

1. `executive-summary`
2. `income-statement`
3. `balance-sheet`
4. `cash-flow`
5. `controls-and-provenance`

Each page uses `<section class="page" data-report-section="...">`. The `<body>` declares
`data-page-size` and `data-expected-pages`. The renderer measures each page under print media and
fails if content or a footer leaves its page bounds.

## Customization rules

- Prefer macros and loops over generated HTML fragments.
- Keep design values in CSS custom properties.
- Keep all resources local and self-contained.
- Do not apply `|safe` to user content.
- Preserve semantic tables, repeating `thead`, and `break-inside` defenses.
- Version the verifier and this contract together before changing required sections or page count.
