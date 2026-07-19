# Changelog

All notable changes to Stencil are documented here.

## [0.6.1](https://github.com/binzhango/stencil/compare/v0.6.0...v0.6.1) (2026-07-19)


### Bug Fixes

* **ci:** recover release artifact publishing ([d89fb8d](https://github.com/binzhango/stencil/commit/d89fb8df263a70f489235565118c01af149e94a8))
* **ci:** recover release artifact publishing ([6beebf8](https://github.com/binzhango/stencil/commit/6beebf848a6171dad482d12def78c34e0de1999a))

## [0.6.0](https://github.com/binzhango/stencil/compare/v0.5.0...v0.6.0) (2026-07-19)


### Features

* **ci:** automate versioned package releases ([4dc1a50](https://github.com/binzhango/stencil/commit/4dc1a50ca80fc3183417f3a2a99ca308b4d92b2a))
* **ci:** automate versioned package releases ([678a67e](https://github.com/binzhango/stencil/commit/678a67e01e0f7fbb9ab33eaf0920825d0d206212))


### Dependencies

* **deps-dev:** bump httpx2 from 2.5.0 to 2.7.0 ([9fd476b](https://github.com/binzhango/stencil/commit/9fd476b78ec3f1c9dadb3a7018b81ea473231984))
* **deps-dev:** bump mypy from 2.1.0 to 2.3.0 ([35a2f1e](https://github.com/binzhango/stencil/commit/35a2f1e2308b29a888da5b4e1c4cd26135053cd3))
* **deps-dev:** bump ruff from 0.15.20 to 0.15.22 ([1378a84](https://github.com/binzhango/stencil/commit/1378a8463ef660e3b75ccd34bc0be434403edc26))
* **deps:** bump fastapi from 0.138.1 to 0.139.2 ([fe96011](https://github.com/binzhango/stencil/commit/fe9601132e73f01b51407f783764ba58cc998d86))
* **deps:** bump typer from 0.26.8 to 0.27.0 ([f74a2f0](https://github.com/binzhango/stencil/commit/f74a2f0cdfc6aba52bc81cdb83598d053893eb97))

## 0.5.0 - 2026-06-27

### Added

- Added PPTX rendering with slide text substitutions and repeated-slide loops.
- Added an optional FastAPI service layer for trusted internal callers.
- Added health and metrics endpoints with per-process render/failure counters.
- Documented the optional service entrypoint and operational boundary.

## 0.4.0 - 2026-06-26

### Added

- Added XLSX rendering with cell substitutions, row loops, style preservation, and multiple-sheet support.
- Added XLSX-to-PDF dispatch through the existing LibreOffice PDF conversion worker.
- Added regression tests for XLSX typed values, formatting, row cloning, formula translation, and PDF routing.

## 0.3.0 - 2026-06-26

### Added

- Documented DOCX template authoring rules, supported Jinja features, limitations, and troubleshooting steps.
- Added expected-output tests for the packaged invoice and styled status report examples.
- Clarified the internal-tool package boundary before starting XLSX or PPTX work.

## 0.2.0 - 2026-06-26

### Added

- Added DOCX-to-PDF output through LibreOffice with timeout handling, one retry, isolated temp workspaces, and cleanup.
- Added PDF conversion tests for retry, timeout, cleanup, and concurrent render dispatch.

## 0.1.1 - 2026-06-26

### Fixed

- Bumped the package version after the first PyPI upload.
- Made the publish workflow safer for reruns when GitHub releases or PyPI files already exist.
- Kept GitHub Release notes backed by the matching changelog section.

## 0.1.0 - 2026-06-26

### Added

- Initial `office-stencil` Python package scaffold.
- `stencil` import package and CLI entrypoint.
- DOCX rendering through `docxtpl`.
- Public `render()` API for DOCX templates.
- Structured render and unsupported-format errors.
- Example DOCX templates and JSON payloads.
- PyPI publishing workflow.
- Dependabot configuration.
