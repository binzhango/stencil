# Python Package CI/CD Agent Guide

This guide captures the Python package release lessons from Stencil. Use it when setting up a future Python project with GitHub Actions, Dependabot, GitHub Releases, and PyPI publishing.

The goal is a boring release path:

- every pull request runs CI before merge,
- merges to `main` publish exactly one new package version,
- GitHub Releases are created from `CHANGELOG.md`,
- PyPI never receives a reused file/version,
- rerunning a workflow is safe where possible,
- version metadata has one source of truth.

## 1. Project Metadata

Use `pyproject.toml` as the single source of truth for the package version.

```toml
[project]
name = "your-package-name"
version = "0.1.0"
readme = "README.md"
requires-python = ">=3.12"
license = "MIT"

[build-system]
requires = ["hatchling", "editables"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/your_import_package"]
```

Important details:

- If the distribution name differs from the import package, explicitly configure `[tool.hatch.build.targets.wheel]`.
- Include `editables` in `build-system.requires` if local/dev installs use editable mode.
- Do not maintain a second hardcoded version in package code.

Recommended runtime version module:

```python
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("your-package-name")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"
```

This lets installed package metadata drive `__version__`.

## 2. Changelog Requirement

Add a tracked `CHANGELOG.md`.

```md
# Changelog

All notable changes are documented here.

## 0.1.0 - 2026-06-26

### Added

- Initial package release.
```

Release rule:

- every `pyproject.toml` version must have a matching `## x.y.z` changelog section;
- the release workflow should fail if that section is missing or empty;
- GitHub Release notes should come from that changelog section.

Do not rely only on generated release notes. Generated notes are useful, but a package maintainer should own user-facing release notes.

## 3. Pull Request CI

Do not use the publish workflow as the required PR check. Publishing happens after merge; branch protection needs checks before merge.

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  pull_request:
    branches:
      - main

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - run: uv sync --dev
      - run: uv run pytest
      - run: uv run ruff check .
      - run: uv build
```

After this workflow runs once, require its `test` job in branch protection or a repository ruleset.

## 4. Publish Workflow

Publish on pushes to `main`, not on pull requests.

Use `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  push:
    branches:
      - main
  workflow_dispatch:

permissions:
  contents: read

jobs:
  publish:
    name: Test, build, release, and publish
    runs-on: ubuntu-latest

    permissions:
      contents: write

    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: uv sync --dev

      - name: Run tests
        run: uv run pytest

      - name: Run lint
        run: uv run ruff check .

      - name: Build package
        run: uv build

      - name: Read package version
        id: version
        run: |
          VERSION=$(uv run python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
          echo "version=${VERSION}" >> "$GITHUB_OUTPUT"
          echo "tag=v${VERSION}" >> "$GITHUB_OUTPUT"

      - name: Read changelog entry
        run: |
          uv run python - <<'PY'
          import os
          import pathlib
          import re
          import tomllib

          version = tomllib.loads(pathlib.Path("pyproject.toml").read_text())["project"]["version"]
          changelog = pathlib.Path("CHANGELOG.md").read_text()
          pattern = rf"^## {re.escape(version)}(?:\s+-\s+[^\n]*)?\n(?P<body>.*?)(?=^## \d|\Z)"
          match = re.search(pattern, changelog, flags=re.MULTILINE | re.DOTALL)
          if match is None:
              raise SystemExit(f"CHANGELOG.md is missing a section for version {version}")

          body = match.group("body").strip()
          if not body:
              raise SystemExit(f"CHANGELOG.md section for version {version} is empty")

          path = pathlib.Path(os.environ["RUNNER_TEMP"]) / "release-notes.md"
          path.write_text(body + "\n")
          print(path)
          PY

      - name: Create GitHub release
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          if gh release view "${{ steps.version.outputs.tag }}" >/dev/null 2>&1; then
            gh release edit "${{ steps.version.outputs.tag }}" \
              --title "Project ${{ steps.version.outputs.tag }}" \
              --notes-file "$RUNNER_TEMP/release-notes.md"
            gh release upload "${{ steps.version.outputs.tag }}" dist/* --clobber
          else
            gh release create "${{ steps.version.outputs.tag }}" \
              dist/* \
              --title "Project ${{ steps.version.outputs.tag }}" \
              --notes-file "$RUNNER_TEMP/release-notes.md"
          fi

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          user: __token__
          password: ${{ secrets.PYPI_API_TOKEN }}
          skip-existing: true
```

Why this shape:

- `contents: write` is needed to create or edit GitHub Releases.
- Release notes come from `CHANGELOG.md`, not generated text.
- Existing GitHub Releases are edited and artifacts are uploaded with `--clobber`, which makes reruns safer.
- `skip-existing: true` avoids hard failure when rerunning after a successful PyPI upload.

Still, do not use reruns as a substitute for version bumps. PyPI does not allow filename reuse.

## 5. PyPI Token Setup

For token-based publishing:

1. Create or claim the PyPI project.
2. Create a PyPI API token.
3. Prefer a project-scoped token after the first release exists.
4. Add it to GitHub Actions secrets as `PYPI_API_TOKEN`.
5. Do not print the token in logs.

Workflow publish config:

```yaml
with:
  user: __token__
  password: ${{ secrets.PYPI_API_TOKEN }}
```

Trusted Publishing is also a good option, but do not mix both approaches in the same workflow unless there is a clear reason.

## 6. Dependabot

Create `.github/dependabot.yml`:

```yaml
version: 2

updates:
  - package-ecosystem: "uv"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
    commit-message:
      prefix: "deps"
      include: "scope"

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
    commit-message:
      prefix: "ci"
      include: "scope"
```

Notes:

- Dependabot is more useful with a committed lockfile.
- If the project intentionally avoids `uv.lock`, dependency PRs may be less precise.
- Dependabot PRs should go through the same CI and branch protection as feature PRs.

## 7. Branch Protection

Protect `main` with a branch ruleset.

Recommended settings:

- require pull requests before merging;
- require at least one approval if the project has collaborators;
- require conversation resolution;
- require the `CI / test` status check;
- require branch to be up to date before merging if the project has active contributors;
- block force pushes;
- block branch deletion;
- avoid admin bypass unless there is a deliberate emergency path.

Common mistake: requiring a publish workflow as a PR check. The publish workflow runs after merge to `main`, so it cannot satisfy PR protection.

## 8. Release Checklist

Before merging a release PR into `main`:

- Bump `[project].version` in `pyproject.toml`.
- Add a matching `CHANGELOG.md` section.
- Confirm package import metadata derives from installed distribution metadata.
- Run tests locally.
- Run lint locally.
- Run build locally.
- Confirm no generated files like `dist/`, `.cache/`, `.venv/`, or example outputs are staged.

Local verification:

```bash
uv sync --dev
uv run pytest
uv run ruff check .
uv build
```

If using a local project venv without `uv sync`, equivalent checks are:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m build --no-isolation
```

## 9. Common Failure Modes

### PyPI says file already exists

Cause: the same package version was already uploaded.

Fix:

- bump `pyproject.toml` version;
- add a matching changelog section;
- rebuild and republish.

Do not delete the PyPI file and retry. PyPI still does not allow filename reuse.

### GitHub Release exists but PyPI failed

Cause: release creation succeeded, then upload failed.

Fix:

- either rerun after fixing the PyPI issue if the same package version has not uploaded successfully;
- or bump the version and create a new release.

Workflow mitigation:

- make release creation idempotent with `gh release view/edit/upload --clobber`;
- use changelog-backed notes.

### PR cannot merge even for repo owner

Cause: branch protection or rulesets apply to owners too unless bypass is allowed.

Fix:

- add a PR CI workflow;
- require that check, not the publish workflow;
- check approvals, unresolved conversations, and “branch must be up to date” requirements.

### Runtime version disagrees with package version

Cause: duplicate hardcoded version constants.

Fix:

- keep `pyproject.toml` as the source of truth;
- read runtime `__version__` from `importlib.metadata.version()`.

### Editable install fails with Hatch

Cause: missing `editables` in build requirements.

Fix:

```toml
[build-system]
requires = ["hatchling", "editables"]
build-backend = "hatchling.build"
```

## 10. Agent Instructions For Future Setup

When an agent sets up CI/CD for a Python package:

1. Inspect existing repo files before changing anything.
2. Confirm package manager: `uv`, Poetry, Hatch, PDM, or plain pip.
3. Use project-local venv/cache if the user does not want home-directory changes.
4. Create PR CI separately from publish CI.
5. Add Dependabot.
6. Add `CHANGELOG.md`.
7. Add PyPI publish with either token auth or Trusted Publishing, not both.
8. Make release creation changelog-backed.
9. Make reruns safe where possible.
10. Verify tests, lint, build, version extraction, and changelog extraction locally.
11. Commit and push only after the working tree has exactly the intended files.
