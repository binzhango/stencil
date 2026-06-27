# Changelog

All notable changes to Stencil are documented here.

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
