# Worklog: CIF Import Fix for MCP `import_structure` Tool

**Date**: 2026-02-26
**Status**: Complete
**Files changed**:
- `src/qmatsuite/mcp/tools/import_structure.py` (fix)
- `tests/mcp/test_import_structure.py` (new, 32 tests)

---

## Problem

During a production blind test, an MCP agent passed inline CIF content to
`import_structure(file_content="data_Si\n_symmetry...", format="cif")` and
received an `import_failed` error. The same structure imported successfully
via POSCAR format.

## Root Cause

**Double-encoded newlines in MCP JSON transport.**

When an LLM agent constructs a CIF string and passes it via MCP's JSON-RPC
layer, the newlines should be encoded as `\n` in the JSON string value and
decoded back to real newline characters by the JSON parser. However, certain
agents double-encode the content — either by:

1. Pre-escaping the string before JSON serialization (`json.dumps(json.dumps(cif))`)
2. Manually constructing the JSON with already-escaped content
3. Template string interpolation that preserves literal `\n` sequences

This results in `file_content` arriving at the tool with literal two-character
`\` + `n` sequences instead of real newline characters (U+000A). The CIF parser
(pymatgen's `CifParser`) then sees the entire file as a single line and fails
with "Invalid CIF file with no structures!".

### Why POSCAR worked

POSCAR likely worked because the agent happened to send it with real newlines,
or because the specific POSCAR content was simple enough that the agent
formatted it correctly. The underlying issue is format-agnostic — any
line-oriented format would fail with double-encoded newlines.

## Diagnostic Results

| Test Case | Result |
|-----------|--------|
| CIF inline (real newlines) | PASS |
| CIF file import | PASS |
| POSCAR inline (real newlines) | PASS |
| POSCAR file import | PASS |
| Minimal hand-crafted CIF (with Fd-3m) | PASS |
| CIF with CRLF line endings | PASS |
| CIF without space group tag | PASS |
| **CIF with literal `\n` (escaped newlines)** | **FAIL** |

Only the escaped-newline case failed, confirming the root cause.

## Fix

Added `_unescape_content()` helper in `import_structure.py`:

```python
def _unescape_content(text: str) -> str:
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

**Heuristic**: If the text contains literal `\n` but *no* real newlines,
decode the common C escape sequences. If real newlines are already present
(indicating correct transport), the text is left untouched.

Applied at line 86 of `import_structure.py`, immediately when `file_content`
is received (before temp file creation).

## Test Coverage

New test file: `tests/mcp/test_import_structure.py` — 32 tests:

- **TestUnescapeContent** (7 tests): Unit tests for the unescape helper
  - Literal `\n` decoded, real newlines untouched, mixed left alone,
    CRLF decoded, tabs decoded, empty string, no escapes
- **TestCIFInlineImport** (9 tests): CIF via `file_content`
  - 3 structures x real newlines, 3 x escaped newlines, CRLF, hand-crafted,
    no space group
- **TestCIFFileImport** (3 tests): CIF via `file_path` (Si, Al, Fe)
- **TestPOSCARInlineImport** (6 tests): POSCAR via `file_content`
  - 3 structures x real newlines, 3 x escaped newlines
- **TestPOSCARFileImport** (3 tests): POSCAR via `file_path` (Si, Al, Fe)
- **TestImportErrors** (4 tests): Error handling
  - Missing input, file not found, invalid CIF, no project

All 32 tests pass.
