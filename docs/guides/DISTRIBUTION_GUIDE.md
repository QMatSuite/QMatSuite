# QMatSuite Distribution Guide

Permanent reference for version management and release processes.

---

## 1. Version Locations

### Source-of-Truth Files (edit these)

| File | Field | Example |
|------|-------|---------|
| `pyproject.toml` | `version = "X.Y.Z"` | Line 7 |
| `src/qmatsuite/__init__.py` | `__version__ = "X.Y.Z"` | Line 14 |
| `gui/package.json` | `"version": "X.Y.Z"` | Line 4 |

### Derived Locations (do NOT edit)

| File | Notes |
|------|-------|
| `gui/package-lock.json` | Version `"0.0.0"` — auto-generated, not our version |
| `gui/electron-builder.json5` | Uses `${version}` template from `package.json` |

---

## 2. Version Bump Checklist

1. Edit the 3 source-of-truth files listed above
2. Commit: `git commit -m "chore: bump version to vX.Y.Z"`
3. Tag: `git tag vX.Y.Z`
4. Push: `git push origin v2-python --tags`

Tag push is safe — no workflows trigger on tag push (all are `workflow_dispatch`).

---

## 3. Full Release Process

### Phase 1 — Version Bump & Push

```bash
# Edit 3 files, then:
git add pyproject.toml src/qmatsuite/__init__.py gui/package.json
git commit -m "chore: bump version to vX.Y.Z"
git tag vX.Y.Z
git push origin v2-python --tags
```

### Phase 2 — PyPI Publish

- **Workflow**: `release-pip.yml` (manual dispatch)
- **Inputs**: `version` (must match `pyproject.toml` exactly), `target` (testpypi/pypi)
- **Validation**: Workflow reads `pyproject.toml` and rejects mismatched versions

```bash
# Test first (optional):
gh workflow run release-pip.yml -f version=X.Y.Z -f target=testpypi

# Production:
gh workflow run release-pip.yml -f version=X.Y.Z -f target=pypi

# Monitor:
gh run list --workflow=release-pip.yml --limit=1
```

### Phase 3 — macOS Release (requires PyPI first)

- **Workflow**: `release-macos.yml` (manual dispatch)
- **Inputs**: `version`, `variant` (lite/full/both), `sign`, `notarize`, `wait_for_staple`
- **Matrix**: arm64 (`macos-14`) + x64 (`macos-15-intel`)
- **Dependencies**: Installs from PyPI (`pip install qmatsuite==X.Y.Z`), downloads QE + SSSP from `qmatsuite-toolchain` and `qmatsuite-assets` repos
- **Artifacts**: `QMatSuite-macOS-{ver}-{arch}.dmg`, `QMatSuite-Full-macOS-{ver}-{arch}.dmg`
- **Signing**: Developer ID certificate, notarization via Apple notary service, stapling

```bash
gh workflow run release-macos.yml \
  -f version=X.Y.Z \
  -f variant=both \
  -f sign=true \
  -f notarize=true \
  -f wait_for_staple=true

# Monitor:
gh run list --workflow=release-macos.yml --limit=1
```

### Phase 4 — Windows Release (requires PyPI first)

- **Workflow**: `release-windows.yml` (manual dispatch)
- **Inputs**: `version`, `variant` (lite/full/both), `sign`
- **Build**: Two-step — `--dir` build, deep sign, `--prepackaged` build, sign installer
- **Signing**: Azure Trusted Signing (OIDC), auto-skips already-signed QE/Intel/MPI binaries
- **Artifacts**: `QMatSuite-Windows-{ver}.exe`, `QMatSuite-Full-Windows-{ver}.exe`

```bash
gh workflow run release-windows.yml \
  -f version=X.Y.Z \
  -f variant=both \
  -f sign=true

# Monitor:
gh run list --workflow=release-windows.yml --limit=1
```

### Phase 5 — Post-Release Verification

```bash
# PyPI
pip install qmatsuite==X.Y.Z  # in a clean venv
python -c "import qmatsuite; print(qmatsuite.__version__)"

# macOS / Windows
# Download DMGs/EXEs from GitHub Release
# Verify: app launches, daemon starts, version displays correctly
```

---

## 4. Hotfix / Patch Release Process

Same as the full release process above. All releases follow the same workflow regardless of scope. There is no separate hotfix procedure.
