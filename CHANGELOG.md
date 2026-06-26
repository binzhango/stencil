# Changelog

All notable changes to Stencil are documented here.

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
