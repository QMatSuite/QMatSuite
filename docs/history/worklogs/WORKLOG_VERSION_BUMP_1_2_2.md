# Worklog: Version Bump to v1.2.2

**Date**: 2026-02-26
**Branch**: `v2-python`

---

## Summary

Version bump from v1.2.1 to v1.2.2. This release includes 18 bug fixes and 3 performance improvements documented in `V1_2_2_CHANGELOG.md`.

## Files Changed

### Version Bumps (1.2.1 -> 1.2.2)
- `pyproject.toml` — line 7
- `src/qmatsuite/__init__.py` — line 14
- `gui/package.json` — line 4

### New Documents
- `docs/guides/DISTRIBUTION_GUIDE.md` — permanent release process reference
- `docs/history/worklogs/WORKLOG_VERSION_BUMP_1_2_2.md` — this file

## Commands Executed

```bash
# Commit and tag
git add pyproject.toml src/qmatsuite/__init__.py gui/package.json \
  docs/guides/DISTRIBUTION_GUIDE.md \
  docs/history/worklogs/WORKLOG_VERSION_BUMP_1_2_2.md
git commit -m "chore: bump version to v1.2.2"
git tag v1.2.2
git push origin v2-python --tags

# Trigger PyPI publish
gh workflow run release-pip.yml -f version=1.2.2 -f target=pypi
```

## Pending (not triggered)

macOS and Windows release workflows were not triggered. Commands when ready:

```bash
# macOS
gh workflow run release-macos.yml \
  -f version=1.2.2 \
  -f variant=both \
  -f sign=true \
  -f notarize=true \
  -f wait_for_staple=true

# Windows
gh workflow run release-windows.yml \
  -f version=1.2.2 \
  -f variant=both \
  -f sign=true
```
