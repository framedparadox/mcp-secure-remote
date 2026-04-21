# Publishing to PyPI

`mcp-secure-remote` is a Python package published on [PyPI](https://pypi.org/project/mcp-secure-remote/)
and runnable directly via `uvx`.

---

## Prerequisites

- Python ≥ 3.10
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) installed
- PyPI account at https://pypi.org/account/register/
- PyPI API token (Settings → API tokens → Add API token)

---

## One-time setup

### 1. Install build tools

```bash
uv tool install build
uv tool install twine
```

### 2. Configure PyPI credentials

Create `~/.pypirc`:

```ini
[distutils]
index-servers = pypi

[pypi]
username = __token__
password = pypi-<your-token-here>
```

Or export for the session:

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-<your-token-here>
```

---

## Pre-publish checklist

```bash
# 1. typecheck / lint (optional but recommended)
uv run mypy src/

# 2. build sdist + wheel
uv build

# 3. inspect the tarball contents
tar tzf dist/mcp_secure_remote-*.tar.gz | head -40
```

Expected files in the wheel:
```
mcp_secure_remote/__init__.py
mcp_secure_remote/args.py
mcp_secure_remote/client.py
mcp_secure_remote/log.py
mcp_secure_remote/mtls.py
mcp_secure_remote/proxy.py
mcp_secure_remote/transport.py
```

---

## Publish

```bash
# upload to PyPI
uvx twine upload dist/*
```

Package lands at: https://pypi.org/project/mcp-secure-remote/

---

## Verify publish

```bash
# install from PyPI in an isolated env and run --help
uvx mcp-secure-remote --help
uvx mcp-secure-remote-client --help
```

---

## Subsequent releases

Bump the version in `pyproject.toml`, then:

```bash
# patch: 0.0.1 → 0.0.2
# edit pyproject.toml: version = "0.0.2"

uv build
uvx twine upload dist/*

git tag v0.0.2
git push && git push --tags
```

### Pre-release

```bash
# pyproject.toml: version = "0.0.2b1"
uv build
uvx twine upload dist/*
```

Users install pre-releases explicitly:

```bash
uvx mcp-secure-remote==0.0.2b1
```

`uvx mcp-secure-remote` still picks the latest stable.

---

## Test on TestPyPI first (recommended)

```bash
uvx twine upload --repository testpypi dist/*

# verify
uvx --index-url https://test.pypi.org/simple/ mcp-secure-remote --help
```

Add TestPyPI credentials to `~/.pypirc` under `[testpypi]` with `repository = https://test.pypi.org/legacy/`.

---

## Automation via CI (GitHub Actions)

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [created]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          version: latest
      - run: uv build
      - run: uvx twine upload dist/*
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
```

Add `PYPI_TOKEN` to GitHub repo → Settings → Secrets → Actions.

Trigger: create a GitHub Release → publish runs automatically.

---

## Unpublish / yank

PyPI does not allow full unpublish after 1 hour (to protect dependents).
Use **yank** instead — the version remains downloadable if pinned, but
`uvx mcp-secure-remote` won't pick it up:

PyPI project page → Your files → Yank release.

To completely delete within the first hour:

```bash
# requires twine + PyPI credentials
uvx twine upload dist/*  # (never remove a published version lightly)
# use the PyPI web UI: project → Manage → Releases → Delete
```
