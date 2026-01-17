# Spec: IR Boolean Canonicalization

**Status**: Authoritative
**Date**: 2026-01-17
**Scope**: Boolean representation across YAML / IR / ParamSpace / Engine layers

---

## 1. Motivation

The current codebase has inconsistent boolean representations:
- ParamSpace `compile_profile_patch()` converts Python `bool` → `.true.`/`.false.` strings
- step.yaml potentially stores `.true.`/`.false.` strings instead of YAML native booleans
- Tests use `.true.`/`.false.` strings when testing detection/compilation

This creates:
1. **Type confusion**: Bool vs string equality checks fail silently
2. **YAML non-canonicity**: YAML parsers treat `.true.` as a plain string, not boolean
3. **Tech debt**: Maintenance burden of two representations

This spec mandates a "no-tech-debt" migration to Python-native booleans everywhere inside the app.

---

## 2. Boundaries and Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL LAYER                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐ │
│  │ QE .in file │    │ User CLI    │    │ Legacy QE Import        │ │
│  │ (.true.)    │    │ input       │    │ (.true. strings)        │ │
│  └──────┬──────┘    └──────┬──────┘    └────────────┬────────────┘ │
└─────────┼──────────────────┼───────────────────────┼───────────────┘
          │                  │                       │
          │ QE Writer        │ CLI Parser            │ QE Import Parser
          │ bool→.true.      │ .true.→bool           │ .true.→bool
          ▼                  ▼                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        INTERNAL LAYER (Python bool)                 │
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐ │
│  │ IR Patches  │    │ ParamSpace  │    │ step.yaml / YAML SSOT   │ │
│  │ (bool)      │    │ Profiles    │    │ (true/false)            │ │
│  │             │    │ (bool)      │    │                         │ │
│  └─────────────┘    └─────────────┘    └─────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.1 Internal Layer (Python bool)

Everything inside the Python application uses native Python `bool`:
- IR patches from ParamSpace compilation
- Profile cell values in ParamSpace definitions
- Loaded step.yaml dictionaries
- Detection results
- All internal function parameters and returns

### 2.2 External Layer (Engine-specific text)

Engine-specific textual formats only appear at IO boundaries:
- QE `.in` files: `.true.` / `.false.`
- QE import from `.in`: parse `.true.` → `bool`
- QE export to `.in`: `bool` → `.true.`
- User CLI input: accept `.true.` as convenience, parse to `bool`

---

## 3. MUST Rules (Non-Negotiable)

### 3.1 YAML SSOT Stores Native Booleans

**MUST**: `step.yaml` and `calculation.yaml` store booleans as YAML `true`/`false`, never as strings `.true.`/`.false.`.

```yaml
# CORRECT (step.yaml)
parameters:
  SYSTEM:
    noncolin: true
    lspinorb: false

# FORBIDDEN (never store this)
parameters:
  SYSTEM:
    noncolin: ".true."
    lspinorb: ".false."
```

**MUST**: If YAML contains string `.true.` or `.false.` where a boolean is expected, raise a hard error. No legacy compatibility parsing.

### 3.2 IR Patches Use Python bool

**MUST**: IR patches (output of `compile_profile_patch()`, input to engine materialization) use Python `bool` values.

```python
# CORRECT
ir_patch = {"SYSTEM": {"noncolin": True, "lspinorb": False}}

# FORBIDDEN
ir_patch = {"SYSTEM": {"noncolin": ".true.", "lspinorb": ".false."}}
```

### 3.3 ParamSpace Profile Cells Use Python bool

**MUST**: ParamSpace profile definitions use Python `bool` for boolean cells.

```python
# CORRECT
Cell.VALUE(True)
Cell.VALUE(False)

# FORBIDDEN
Cell.VALUE(".true.")
Cell.VALUE(".false.")
```

### 3.4 Engine Writer Converts to Text Format

**MUST**: The QE writer (`qe_generator.py`) converts Python `bool` to `.true.`/`.false.` when generating `.in` files.

**MUST**: This is the ONLY place where `.true.`/`.false.` strings are produced.

### 3.5 Engine Parser Converts from Text Format

**MUST**: The QE parser (`qe_parser.py`) converts `.true.`/`.false.` to Python `bool` when importing `.in` files.

**MUST**: After import, YAML written to disk uses native YAML booleans.

### 3.6 ParamSpace Does NOT Parse Types

**MUST**: ParamSpace matching may do minimal robustness normalization on strings: `strip()` and `lower()` only.

**MUST NOT**: ParamSpace parse `.true.` into `bool`. YAML should never contain `.true.` anyway.

**MUST NOT**: ParamSpace contain synonym dictionaries for type conversion.

---

## 4. ROBUSTNESS Rules (Optional but Recommended)

### 4.1 Detector Robustness

**SHOULD**: Detection functions may accept both `bool` and string representations for robustness when reading potentially malformed data from external sources.

```python
def _parse_bool(value: Any) -> bool:
    """Parse boolean, accepting various representations for robustness."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lower = value.lower().strip()
        if lower in (".true.", "true", "t", ".t."):
            return True
        if lower in (".false.", "false", "f", ".f."):
            return False
    return False
```

**Note**: This robustness is for reading external data, not for internal YAML. Internal YAML with `.true.` strings is an error.

### 4.2 CLI Input Robustness

**SHOULD**: CLI parsers accept `.true.`/`.false.` from user input for convenience, converting to Python `bool` immediately.

---

## 5. Forbidden Patterns

### 5.1 Forbidden in Production Code

```python
# FORBIDDEN: Converting bool to string in IR/ParamSpace
value = ir_bool(True)  # Returns ".true." string - WRONG

# FORBIDDEN: Storing string in IR patch
patch = {"SYSTEM": {"noncolin": ".true."}}  # WRONG

# FORBIDDEN: String literal in ParamSpace profile
Cell.VALUE(".true.")  # WRONG
```

### 5.2 Forbidden in YAML

```yaml
# FORBIDDEN: String literals for booleans in step.yaml
parameters:
  SYSTEM:
    noncolin: ".true."  # String, not boolean - WRONG
```

---

## 6. Allowed Patterns

### 6.1 Allowed in Production Code

```python
# CORRECT: Native bool in IR patch
patch = {"SYSTEM": {"noncolin": True, "lspinorb": False}}

# CORRECT: Native bool in ParamSpace profile
Cell.VALUE(True)
Cell.VALUE(False)

# CORRECT: QE writer converts at output boundary
def format_value(value: Any) -> str:
    if isinstance(value, bool):
        return ".true." if value else ".false."  # Only here!
```

### 6.2 Allowed in YAML

```yaml
# CORRECT: Native YAML booleans in step.yaml
parameters:
  SYSTEM:
    noncolin: true
    lspinorb: false
```

---

## 7. Examples

### 7.1 Example: step.yaml with Boolean

```yaml
# File: steps/01_scf.step.yaml
step_type: qe_scf
parameters:
  SYSTEM:
    ecutwfc: 30.0
    noncolin: true       # YAML native boolean
    lspinorb: true       # YAML native boolean
    nspin: 4
  ELECTRONS:
    conv_thr: 1.0e-8
```

### 7.2 Example: QE .in Output

```fortran
&SYSTEM
    ecutwfc = 30.0
    noncolin = .true.    ! QE Fortran format
    lspinorb = .true.    ! QE Fortran format
    nspin = 4
/
&ELECTRONS
    conv_thr = 1.0e-8
/
```

### 7.3 Example: Import .in → YAML

Input `.in` file:
```fortran
&SYSTEM
    noncolin = .TRUE.
    lspinorb = .true.
/
```

After import, step.yaml stores:
```yaml
parameters:
  SYSTEM:
    noncolin: true    # Converted to YAML boolean
    lspinorb: true    # Converted to YAML boolean
```

---

## 8. Failure Modes

### 8.1 Hard Error: String in YAML

If step.yaml contains:
```yaml
parameters:
  SYSTEM:
    noncolin: ".true."  # String literal
```

**Action**: Raise `ValueError` with message:
```
Invalid boolean representation in step.yaml: 
Found string ".true." where boolean expected for key "noncolin".
YAML must store native booleans (true/false), not QE strings (.true./.false.).
```

### 8.2 Guard Test Failures

Guard tests scan:
1. Loaded YAML dicts: no string equal to `.true.`/`.false.`
2. IR patches from ParamSpace: no `.true.`/`.false.` strings
3. QE `.in` output: `.true.`/`.false.` IS allowed and expected

---

## 9. Test Strategy

### 9.1 Guard Tests Required

```python
def test_no_qe_bool_strings_in_yaml():
    """YAML dicts must not contain .true./.false. strings."""
    # Load any step.yaml
    # Recursively scan for string values equal to ".true." or ".false."
    # Assert none found

def test_no_qe_bool_strings_in_ir_patch():
    """IR patches from ParamSpace must not contain .true./.false. strings."""
    # For each profile in each ParamSpace
    # Compile to IR patch
    # Recursively scan for string values equal to ".true." or ".false."
    # Assert none found

def test_qe_output_uses_fortran_format():
    """QE .in output must use .true./.false. for booleans."""
    # Generate QE input from dict with bool values
    # Assert output contains ".true." or ".false." as appropriate
```

### 9.2 Existing Test Updates

All tests currently using `.true.`/`.false.` strings in Python dicts must be updated to use Python `bool`.

---

## 10. Evidence Locations (Current Violations)

| Location | Issue | Fix Required |
|----------|-------|--------------|
| `paramspace.py:601-605` | `compile_profile_patch()` calls `ir_bool()` | Remove conversion |
| `paramspace.py:619-636` | `parse_bool()` parses `.true.` | Mark as deprecated/internal |
| `ir/backends/qe/mapping.py:14-41` | `ir_bool()` returns `.true.` string | Delete function |
| `ir/backends/qe/mapping.py:118-122` | `ir_to_qe_param()` converts to string | Move to QE writer only |
| `tests/unit/test_magnetism_paramspace_contract.py` | Uses `.true.` strings | Update to `bool` |
| `tests/unit/test_preset_integration.py` | Expects `.true.` in output | Update to `bool` |
| `tests/unit/test_detector_b.py` | Uses `.true.` strings | Update to `bool` |
| `tests/integration/test_preset_broadcast.py` | Uses `.true.` strings | Update to `bool` |

---

## 11. Migration Checklist

- [ ] Remove `ir_bool()` calls from `compile_profile_patch()`
- [ ] Update `ir_to_qe_param()` to NOT convert booleans (keep as Python bool)
- [ ] Ensure QE writer (`qe_generator.py`) handles conversion (already correct)
- [ ] Ensure QE parser (`qe_parser.py`) returns Python bool (already correct)
- [ ] Update all tests to use Python `bool` instead of `.true.`/`.false.` strings
- [ ] Add guard tests for no `.true.` strings in YAML/IR
- [ ] Add guard test for `.true.` present in QE output
- [ ] Update/regenerate any fixtures or demos if needed

