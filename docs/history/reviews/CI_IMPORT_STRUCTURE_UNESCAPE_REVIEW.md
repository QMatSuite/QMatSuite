# CI Review: `_unescape_content` ImportError in `test_import_structure.py`

**Date**: 2026-02-26
**Severity**: CI blocker (1 ERROR on both macOS and Ubuntu runners)
**Affected commits**: `b379b06c` (introduced test) referencing function never present in `4e8e5f11` (source)

---

## Symptom

Both CI runners (macOS + Ubuntu) fail with an identical ImportError:

```
ERROR tests/mcp/test_import_structure.py - ImportError
E   ImportError: cannot import name '_unescape_content' from
    'qmatsuite.mcp.tools.import_structure'
```

- macOS: 6352 passed, 212 skipped, **1 error**
- Ubuntu: 6351 passed, 213 skipped, **1 error**
- Local (user's prior run): 6562 passed, 5 skipped, 0 errors

## Root Cause

**The `_unescape_content` function was never committed to the source module.**

### Evidence chain

| Fact | Evidence |
|------|----------|
| Source file created | `4e8e5f11` (Feb 22) — `import_structure.py` added as new file |
| Source has no `_unescape_content` | `git show 4e8e5f11 -- ...import_structure.py \| grep -c unescape` → **0** |
| Source never modified after creation | `git log --diff-filter=M -- ...import_structure.py` → **(empty)** |
| Test file committed with import | `b379b06c` (Feb 26, 17:51) — line 21: `from ...import_structure import ..., _unescape_content` |
| Test commit does not touch source | `git show b379b06c --stat \| grep import_structure` → only `tests/mcp/test_import_structure.py` listed |
| No stashed changes | `git stash list` → **(empty)** |
| Current module namespace confirms | `dir(module)` → no `_unescape_content` |
| Local import also fails NOW | `python -c "from qmatsuite.mcp.tools.import_structure import _unescape_content"` → **ImportError** |

### Timeline reconstruction

```
Feb 22 18:15  4e8e5f11  import_structure.py committed (new file, NO _unescape_content)
   ...        (locally)  Developer adds _unescape_content() to working copy (never staged)
   ...        (locally)  Developer creates test_import_structure.py, runs tests — all 32 pass
   ...        (locally)  Developer stages & commits ONLY the test file (source change lost)
Feb 26 17:38            .pyc recompiled from source WITHOUT _unescape_content
Feb 26 17:51  b379b06c  test_import_structure.py committed (imports nonexistent function)
```

### Why the user's prior local run passed

The referenced test output (6562 passed, 5 skipped) was captured during an earlier session when the local working copy of `import_structure.py` still contained the uncommitted `_unescape_content` function. The editable install (`pip install -e .`) serves source files directly, so the uncommitted local change was active during that test run.

After the working tree was cleaned (possibly by `git checkout`, stash, or the commit cycle losing the unstaged change), the function vanished from the source. The current local state now reproduces the CI error identically.

## Impact

### Test impact

- **32 tests lost**: The ImportError at module level prevents pytest from collecting any tests in `test_import_structure.py`
  - 7 `TestUnescapeContent` unit tests
  - 9 `TestCIFInlineImport` tests (including the escaped-newline regression tests)
  - 3 `TestCIFFileImport` tests
  - 6 `TestPOSCARInlineImport` tests
  - 3 `TestPOSCARFileImport` tests
  - 4 `TestImportErrors` tests

### Functional impact

- **The CIF double-encoded newline fix is NOT deployed.** The worklog (`WORKLOG_CIF_IMPORT_FIX.md`) documents the fix in detail, but the actual code change (`_unescape_content` function + its invocation in the `file_content` path) was never committed to the source module.
- MCP agents that double-encode newlines when passing CIF/POSCAR content will still get `import_failed` errors.

## Required Fix (two parts)

### Part 1: Add the missing function to the source module

As documented in `WORKLOG_CIF_IMPORT_FIX.md`, add `_unescape_content()` to `src/qmatsuite/mcp/tools/import_structure.py`:

```python
def _unescape_content(text: str) -> str:
    """Decode double-encoded escape sequences from MCP JSON transport.

    If the text contains literal backslash-n but no real newlines,
    decode common C escape sequences. If real newlines already exist,
    leave the text untouched.
    """
    if "\n" not in text and "\\n" in text:
        text = (
            text
            .replace("\\r\\n", "\r\n")
            .replace("\\n", "\n")
            .replace("\\r", "\r")
            .replace("\\t", "\t")
        )
    return text
```

### Part 2: Wire the function into the `file_content` path

In the `elif file_content:` branch (around line 63), call `_unescape_content` before writing to the temp file:

```python
    elif file_content:
        file_content = _unescape_content(file_content)  # <-- add this line
        fmt = format.lower()
        ...
```

## Classification

This is a **commit hygiene error** — the test and its documentation were committed, but the source code change they depend on was not. The root cause is that `git add` was applied selectively (test file + docs) without including the modified source file, and the pre-commit/CI feedback loop was not consulted before pushing.

No architectural or design issues. The fix itself (documented in the worklog) is correct and well-reasoned.
