# Plan: UI Parameter Typing - Class A vs Class B Keys

**Status**: Ready for implementation  
**Created**: 2026-01-17  
**Related**: `spec-preset-paramspace-ir-engine-contract.md`, `spec-ir-bool-canonicalization.md`

---

## 0. Executive Summary

Implement strict typing for "Class A" (preset/IR-participating) keys while keeping "Class B" (other engine-specific) keys flexible. Class A keys must be validated and stored with Python native types; Class B keys are stored as trimmed strings only.

---

## 1. Code Review Findings

### 1.1 UI Control Type Source

**Location**: `src/quantumvitas/data/qe_ui_parameters.json`  
**Loaded by**: `src/quantumvitas/data/qe_metadata.py:_load_ui_parameters()`  
**Daemon handler**: `server.py:_handle_list_qe_ui_parameters()`

Current types in JSON:
- `"number"` → numeric input
- `"select"` → dropdown with options
- `"text"` → freeform text

**Issue**: No explicit `"bool"` type. Boolean parameters (noncolin, lspinorb, nosym, noinv) are not listed in qe_ui_parameters.json at all.

### 1.2 YAML Patching (Critical Bug)

**Location**: `src/quantumvitas/api.py:4545`
```python
# STRING-ONLY: Convert all values to strings for YAML storage
param_patch[namelist_upper][key] = str(value)
```

**Issue**: This converts ALL values to strings, including booleans (`True` → `"True"`). This violates the Class A contract where booleans must be stored as native `true`/`false` in YAML.

### 1.3 ParamSpace Owned Keys (Class A definition)

**Location**: `src/quantumvitas/presets/paramspace.py`

| Dimension | Keys | Types |
|-----------|------|-------|
| Magnetism | nspin, noncolin, lspinorb | int, bool, bool |
| OccupationsScheme | occupations, smearing | enum/str, enum/str |
| Precision | ecutwfc, ecutrho, conv_thr, degauss, K_POINTS | int, int, float, float, special |
| Convergence | mixing_beta, electron_maxstep, mixing_mode, mixing_ndim, diagonalization | float, int, str, int, str |

### 1.4 IR Key Mapping

**Location**: `src/quantumvitas/ir/backends/qe/mapping.py:IR_TO_QE_MAPPING`

This provides the complete list of IR-mapped keys (Class A candidates).

### 1.5 QE Writer Behavior (Correct)

**Location**: `src/quantumvitas/io/generator/qe_generator.py:20-30`
```python
def format_value(value: Any) -> str:
    if isinstance(value, bool):
        return ".true." if value else ".false."
    if isinstance(value, str):
        return f"'{value}'"
    ...
```

**Status**: Already handles bool→.true. and str→quoted correctly. No changes needed.

### 1.6 StepDoc Normalization

**Location**: `src/quantumvitas/core/yamldoc.py:551-554`

Only does alias normalization for specific keys (gauss→gaussian). Does NOT globally lowercase values. This is correct behavior.

### 1.7 Existing Parse Helpers

**Location**: `src/quantumvitas/presets/integration.py:41-52`
- `_parse_bool_value()`: Parses various bool representations (.true., true, t, etc.)

**Location**: `src/quantumvitas/presets/paramspace.py`
- `parse_bool()`, `parse_int()`, `parse_float()`: Used for ParamSpace matching

These are for detection/matching, not UI validation.

---

## 2. Contract Specification

### 2.1 Class A Keys (Strict)

**Definition**: Keys that are:
1. Listed in `IR_TO_QE_MAPPING`, OR
2. Owned by any ParamSpace (ParamKey definitions)

**UI Behavior**:
- `bool`: Toggle/checkbox control (no freeform text)
- `int`/`float`: Numeric input with validation on submit
- `enum`/`select`: Dropdown (no freeform text)
- On validation failure: Show error, do NOT write to YAML

**YAML Storage**:
- `bool`: YAML native `true`/`false`
- `int`: YAML native integer
- `float`: YAML native float
- `str/enum`: YAML native string

### 2.2 Class B Keys (Flexible)

**Definition**: All keys NOT in Class A

**UI Behavior**:
- Any value accepted
- On submit: Only trim leading/trailing whitespace
- Do NOT lowercase
- Do NOT parse types

**YAML Storage**:
- Store as string (after trim)

### 2.3 QE Writer (Unchanged)

- `bool` → `.true.`/`.false.`
- `str` → quoted verbatim
- `int`/`float` → numeric literal

---

## 3. Implementation Plan

### PR0: Export Class A Key Registry

**Goal**: Provide a single SSOT function to determine if a key is Class A.

**Files to modify**:
- `src/quantumvitas/ir/backends/qe/mapping.py`

**Changes**:
1. Add function:
```python
def is_class_a_key(section: str, key: str) -> bool:
    """Check if (section, key) is a Class A (strict-typed) key."""
    # Check IR mapping
    ir_key = key.lower()
    if ir_key in IR_TO_QE_MAPPING:
        return True
    # Check full tuple match (for keys that have section context)
    for _, (_, sec, k) in IR_TO_QE_MAPPING.items():
        if sec.upper() == section.upper() and k.lower() == key.lower():
            return True
    return False

def get_class_a_type(section: str, key: str) -> Optional[str]:
    """Get expected type for Class A key: 'bool', 'int', 'float', 'str', or None."""
    # Return type based on ParamKey definitions
    ...
```

2. Add `CLASS_A_TYPES` dict mapping (section, key) → expected type

**Tests**:
- `tests/unit/test_class_a_keys.py`:
  - `test_ir_mapped_keys_are_class_a()`
  - `test_non_ir_keys_are_class_b()`
  - `test_class_a_type_returns_correct_type()`

**Verification**:
```bash
pytest tests/unit/test_class_a_keys.py -v
```

**Do NOT change**:
- ParamSpace semantics
- IR mapping values
- Any existing detection logic

**Done**: [ ]

---

### PR1: Backend Validation Helpers

**Goal**: Add type parsing/validation functions for Class A keys.

**Files to create**:
- `src/quantumvitas/core/param_validation.py`

**Content**:
```python
"""
Parameter validation for Class A (strict-typed) keys.

Class A keys must be validated and parsed to their canonical types.
Class B keys are stored as trimmed strings without parsing.
"""

from typing import Any, Optional, Tuple, Union

class ValidationError(Exception):
    """Raised when a Class A parameter value fails validation."""
    pass

def validate_and_parse(
    section: str,
    key: str,
    raw_value: str,
    expected_type: str,
) -> Any:
    """
    Validate and parse a raw string value to its canonical type.
    
    Args:
        section: YAML section (e.g., "SYSTEM")
        key: Parameter key
        raw_value: Raw string from UI
        expected_type: 'bool', 'int', 'float', 'str'
        
    Returns:
        Parsed value with correct Python type
        
    Raises:
        ValidationError: If parsing fails
    """
    raw_value = raw_value.strip()
    
    if expected_type == "bool":
        return _parse_bool_strict(raw_value, section, key)
    elif expected_type == "int":
        return _parse_int_strict(raw_value, section, key)
    elif expected_type == "float":
        return _parse_float_strict(raw_value, section, key)
    elif expected_type == "str":
        return raw_value  # Already a string, just trimmed
    else:
        raise ValidationError(f"Unknown type '{expected_type}' for {section}.{key}")

def _parse_bool_strict(value: str, section: str, key: str) -> bool:
    """Parse bool strictly - no .true./.false. strings allowed."""
    v = value.lower()
    if v in ("true", "1", "yes", "on"):
        return True
    if v in ("false", "0", "no", "off"):
        return False
    raise ValidationError(
        f"Invalid boolean value for {section}.{key}: '{value}'. "
        f"Use true/false, yes/no, or 1/0."
    )

def _parse_int_strict(value: str, section: str, key: str) -> int:
    """Parse int strictly."""
    try:
        return int(value)
    except ValueError:
        raise ValidationError(
            f"Invalid integer value for {section}.{key}: '{value}'. "
            f"Enter a whole number."
        )

def _parse_float_strict(value: str, section: str, key: str) -> float:
    """Parse float strictly."""
    try:
        return float(value)
    except ValueError:
        raise ValidationError(
            f"Invalid numeric value for {section}.{key}: '{value}'. "
            f"Enter a number."
        )

def normalize_class_b_value(value: str) -> str:
    """Normalize a Class B value: trim whitespace only."""
    return value.strip()
```

**Tests**:
- `tests/unit/test_param_validation.py`:
  - `test_parse_bool_true_variants()`
  - `test_parse_bool_false_variants()`
  - `test_parse_bool_rejects_dotted()`  # .true. should fail for strict parse
  - `test_parse_int_valid()`
  - `test_parse_int_rejects_float()`
  - `test_parse_float_valid()`
  - `test_class_b_preserves_case()`
  - `test_class_b_trims_whitespace()`

**Verification**:
```bash
pytest tests/unit/test_param_validation.py -v
```

**Do NOT change**:
- Existing _parse_bool_value in integration.py (used for detection robustness)
- ParamSpace parsers (used for matching)

**Done**: [ ]

---

### PR2: Fix YAML Patching for Class A/B

**Goal**: Fix `update_step_params` to respect Class A/B typing.

**Files to modify**:
- `src/quantumvitas/api.py` (update_step_params method)

**Changes**:
Replace lines 4539-4545:
```python
for key, value in params.items():
    # Set or remove the parameter
    if value is None:
        param_patch[namelist_upper][key] = None
    else:
        # STRING-ONLY: Convert all values to strings for YAML storage
        param_patch[namelist_upper][key] = str(value)
```

With:
```python
from quantumvitas.ir.backends.qe.mapping import is_class_a_key, get_class_a_type
from quantumvitas.core.param_validation import (
    validate_and_parse,
    normalize_class_b_value,
    ValidationError,
)

for key, value in params.items():
    if value is None:
        param_patch[namelist_upper][key] = None
    else:
        raw_value = str(value)  # Ensure string for parsing
        
        if is_class_a_key(namelist_upper, key):
            # Class A: Validate and store typed
            expected_type = get_class_a_type(namelist_upper, key)
            if expected_type:
                try:
                    typed_value = validate_and_parse(
                        namelist_upper, key, raw_value, expected_type
                    )
                    param_patch[namelist_upper][key] = typed_value
                except ValidationError as e:
                    raise QVServiceError(str(e))
            else:
                # Class A but no type info - store as trimmed string
                param_patch[namelist_upper][key] = raw_value.strip()
        else:
            # Class B: Store as trimmed string only
            param_patch[namelist_upper][key] = normalize_class_b_value(raw_value)
```

**Tests**:
- `tests/unit/test_update_step_params.py`:
  - `test_class_a_bool_stored_as_bool()`
  - `test_class_a_int_stored_as_int()`
  - `test_class_a_float_stored_as_float()`
  - `test_class_b_stored_as_string()`
  - `test_class_b_preserves_case()`
  - `test_class_a_invalid_raises_error()`

**Verification**:
```bash
pytest tests/unit/test_update_step_params.py -v
pytest tests/unit/test_param_validation.py -v
```

**Do NOT change**:
- Card update logic
- StepDoc save logic
- Any preset/detection logic

**Done**: [ ]

---

### PR3: Add Class A Keys to qe_ui_parameters.json

**Goal**: Ensure UI metadata includes all Class A keys with correct types.

**Files to modify**:
- `src/quantumvitas/data/qe_ui_parameters.json`

**Changes**:
Add missing Class A parameters with correct types:

```json
{
  "namelist": "SYSTEM",
  "name": "noncolin",
  "label": "Noncollinear",
  "type": "bool",
  "description": "Enable noncollinear magnetism",
  "importance": "advanced"
},
{
  "namelist": "SYSTEM",
  "name": "lspinorb",
  "label": "Spin-Orbit Coupling",
  "type": "bool",
  "description": "Enable spin-orbit coupling",
  "importance": "advanced"
},
{
  "namelist": "SYSTEM",
  "name": "nspin",
  "label": "Spin Polarization",
  "type": "select",
  "options": ["1", "2", "4"],
  "description": "1=non-magnetic, 2=collinear, 4=noncollinear",
  "importance": "core"
},
{
  "namelist": "SYSTEM",
  "name": "nosym",
  "label": "Disable Symmetry",
  "type": "bool",
  "description": "Disable symmetry operations",
  "importance": "advanced"
},
{
  "namelist": "SYSTEM",
  "name": "noinv",
  "label": "Disable Inversion",
  "type": "bool",
  "description": "Disable inversion symmetry",
  "importance": "advanced"
}
```

**Tests**:
- `tests/unit/test_ui_param_metadata.py`:
  - `test_all_class_a_keys_have_type()`
  - `test_bool_keys_have_bool_type()`

**Verification**:
```bash
pytest tests/unit/test_ui_param_metadata.py -v
python -c "from quantumvitas.data.qe_metadata import validate_ui_parameters; print(validate_ui_parameters())"
```

**Do NOT change**:
- Existing parameter entries (only add new ones)

**Done**: [ ]

---

### PR4: QE Writer Regression Tests

**Goal**: Verify QE writer handles Class A booleans and Class B strings correctly.

**Files to modify**:
- `tests/unit/test_qe_generator.py` (or create if missing)

**Tests to add**:
```python
class TestQEGeneratorClassAB:
    """Test QE generator handles Class A (typed) and Class B (string) correctly."""
    
    def test_bool_true_becomes_dot_true(self):
        """Python True → .true. in QE output."""
        assert QEInputGenerator.format_value(True) == ".true."
    
    def test_bool_false_becomes_dot_false(self):
        """Python False → .false. in QE output."""
        assert QEInputGenerator.format_value(False) == ".false."
    
    def test_string_preserved_verbatim(self):
        """String values are quoted but preserved."""
        assert QEInputGenerator.format_value("gaussian") == "'gaussian'"
        assert QEInputGenerator.format_value("Gaussian") == "'Gaussian'"  # Case preserved
    
    def test_string_dot_true_preserved(self):
        """String '.true.' is quoted as string, not converted."""
        # This is for Class B keys where user explicitly types .true.
        result = QEInputGenerator.format_value(".true.")
        assert result == "'.true.'"
    
    def test_int_not_quoted(self):
        """Integer values are not quoted."""
        assert QEInputGenerator.format_value(50) == "50"
    
    def test_float_not_quoted(self):
        """Float values are not quoted."""
        assert QEInputGenerator.format_value(1.0e-6) == "1e-06"
```

**Verification**:
```bash
pytest tests/unit/test_qe_generator.py -v
pytest tests/unit/test_no_qe_bool_strings.py -v
```

**Do NOT change**:
- QE generator implementation (only add tests)

**Done**: [ ]

---

### PR5: Integration Tests and Documentation

**Goal**: End-to-end tests for Class A/B behavior.

**Files to create**:
- `tests/integration/test_class_a_b_params.py`

**Tests**:
```python
class TestClassABIntegration:
    """Integration tests for Class A/B parameter handling."""
    
    def test_class_a_bool_roundtrip(self, tmp_path):
        """Class A bool: UI → YAML (bool) → QE (.true.)"""
        # Create step, update noncolin=True
        # Verify YAML stores true (not "True" or ".true.")
        # Verify QE output has .true.
        pass
    
    def test_class_a_validation_error_blocks_save(self, tmp_path):
        """Invalid Class A value should raise error, not save."""
        # Try to set ecutwfc="not a number"
        # Verify raises QVServiceError
        pass
    
    def test_class_b_dot_true_preserved(self, tmp_path):
        """Class B key: .true. string preserved exactly."""
        # Set some_unknown_param=".true."
        # Verify YAML stores ".true." (string)
        # Verify QE output has '.true.' (quoted string)
        pass
    
    def test_class_b_case_preserved(self, tmp_path):
        """Class B key: case is preserved."""
        # Set some_param="MixedCase"
        # Verify YAML stores "MixedCase" (not lowercased)
        pass
```

**Documentation update**:
Add section to `docs/dev/spec-preset-paramspace-ir-engine-contract.md`:

```markdown
## Class A vs Class B Parameters

### Class A (Strict Typing)
Parameters participating in IR/Preset system:
- Listed in `IR_TO_QE_MAPPING`
- Owned by any ParamSpace (ParamKey definitions)

**Rules**:
- UI enforces type-appropriate controls (toggle for bool, numeric input for numbers)
- On submit: validate and parse to canonical Python type
- YAML stores native types (bool as true/false, int as integer, etc.)
- Invalid input shows error and blocks save

### Class B (Flexible)
All other engine-specific parameters.

**Rules**:
- UI allows freeform text input
- On submit: only trim leading/trailing whitespace
- YAML stores as string (preserving case)
- QE writer outputs verbatim (quoted)
```

**Verification**:
```bash
pytest tests/integration/test_class_a_b_params.py -v
pytest tests/unit/ tests/presets/ -v --tb=short
```

**Done**: [ ]

---

## 4. Implementation Log

```
PR0: [x] Export Class A Key Registry
PR1: [ ] Backend Validation Helpers
PR2: [ ] Fix YAML Patching for Class A/B
PR3: [ ] Add Class A Keys to qe_ui_parameters.json
PR4: [ ] QE Writer Regression Tests
PR5: [ ] Integration Tests and Documentation
```

---

## 5. Acceptance Criteria

- [ ] All Class A keys have type information accessible via `get_class_a_type()`
- [ ] `update_step_params` validates Class A keys and rejects invalid values
- [ ] YAML stores Class A booleans as native `true`/`false`, not strings
- [ ] YAML stores Class B values as trimmed strings, preserving case
- [ ] QE writer outputs `bool` as `.true.`/`.false.`
- [ ] QE writer outputs `str` as quoted verbatim
- [ ] Guard tests prevent regression
- [ ] All existing tests pass

---

## 6. Prompts for Cursor Auto

### PR0 Prompt

```
You are AUTO implementing PR0 from docs/dev/plan-ui-param-typing-a-vs-b.md

TASK: Export Class A Key Registry

MODIFY: src/quantumvitas/ir/backends/qe/mapping.py

ADD after IR_TO_QE_MAPPING:

CLASS_A_TYPES: Dict[Tuple[str, str], str] = {
    # (SECTION, key) → expected_type
    # Magnetism
    ("SYSTEM", "nspin"): "int",
    ("SYSTEM", "noncolin"): "bool",
    ("SYSTEM", "lspinorb"): "bool",
    # OccupationsScheme
    ("SYSTEM", "occupations"): "str",
    ("SYSTEM", "smearing"): "str",
    ("SYSTEM", "degauss"): "float",
    # Precision
    ("SYSTEM", "ecutwfc"): "float",
    ("SYSTEM", "ecutrho"): "float",
    ("ELECTRONS", "conv_thr"): "float",
    # Convergence
    ("ELECTRONS", "mixing_beta"): "float",
    ("ELECTRONS", "electron_maxstep"): "int",
    ("ELECTRONS", "mixing_mode"): "str",
    ("ELECTRONS", "mixing_ndim"): "int",
    ("ELECTRONS", "diagonalization"): "str",
    # Other IR-mapped
    ("SYSTEM", "nbnd"): "int",
    ("SYSTEM", "nosym"): "bool",
    ("SYSTEM", "noinv"): "bool",
}

def is_class_a_key(section: str, key: str) -> bool:
    """Check if (section, key) is a Class A (strict-typed) key."""
    return (section.upper(), key.lower()) in CLASS_A_TYPES or \
           (section.upper(), key) in CLASS_A_TYPES

def get_class_a_type(section: str, key: str) -> Optional[str]:
    """Get expected type for Class A key, or None if not Class A."""
    return CLASS_A_TYPES.get((section.upper(), key.lower())) or \
           CLASS_A_TYPES.get((section.upper(), key))

CREATE TEST: tests/unit/test_class_a_keys.py

VERIFICATION:
pytest tests/unit/test_class_a_keys.py -v

TICK CHECKBOX: PR0 in plan file
COMMIT: "IR: add Class A key registry for strict typing (PR0)"
```

### PR1 Prompt

```
You are AUTO implementing PR1 from docs/dev/plan-ui-param-typing-a-vs-b.md

TASK: Backend Validation Helpers

CREATE: src/quantumvitas/core/param_validation.py
(Use content from plan file section PR1)

CREATE TEST: tests/unit/test_param_validation.py

Test cases:
- test_parse_bool_true_variants: "true", "True", "1", "yes" → True
- test_parse_bool_false_variants: "false", "False", "0", "no" → False
- test_parse_bool_rejects_dotted: ".true." raises ValidationError
- test_parse_int_valid: "50" → 50
- test_parse_int_rejects_float: "1.5" raises ValidationError
- test_parse_float_valid: "1e-6" → 1e-6
- test_class_b_preserves_case: " MixedCase " → "MixedCase"

VERIFICATION:
pytest tests/unit/test_param_validation.py -v

TICK CHECKBOX: PR1 in plan file
COMMIT: "Core: add param validation for Class A/B typing (PR1)"
```

### PR2 Prompt

```
You are AUTO implementing PR2 from docs/dev/plan-ui-param-typing-a-vs-b.md

TASK: Fix YAML Patching for Class A/B

MODIFY: src/quantumvitas/api.py

In update_step_params() method (around line 4539-4545):
Replace the loop that converts all values to str(value).
Use Class A/B logic from plan file.

VERIFICATION:
pytest tests/unit/test_param_validation.py -v
pytest tests/presets/ -v

TICK CHECKBOX: PR2 in plan file
COMMIT: "API: fix update_step_params for Class A/B typing (PR2)"
```

### PR3 Prompt

```
You are AUTO implementing PR3 from docs/dev/plan-ui-param-typing-a-vs-b.md

TASK: Add Class A Keys to qe_ui_parameters.json

MODIFY: src/quantumvitas/data/qe_ui_parameters.json

Add missing boolean parameters under "pw" -> "scf":
- noncolin (type: "bool")
- lspinorb (type: "bool")
- nosym (type: "bool")
- noinv (type: "bool")

VERIFICATION:
python -c "from quantumvitas.data.qe_metadata import validate_ui_parameters; errors = validate_ui_parameters(); print('OK' if not errors else errors)"

TICK CHECKBOX: PR3 in plan file
COMMIT: "Data: add bool parameters to qe_ui_parameters.json (PR3)"
```

### PR4 Prompt

```
You are AUTO implementing PR4 from docs/dev/plan-ui-param-typing-a-vs-b.md

TASK: QE Writer Regression Tests

MODIFY: tests/unit/test_no_qe_bool_strings.py

ADD class TestQEGeneratorClassAB with tests from plan file.

VERIFICATION:
pytest tests/unit/test_no_qe_bool_strings.py -v

TICK CHECKBOX: PR4 in plan file
COMMIT: "Tests: add QE generator Class A/B regression tests (PR4)"
```

### PR5 Prompt

```
You are AUTO implementing PR5 from docs/dev/plan-ui-param-typing-a-vs-b.md

TASK: Integration Tests and Documentation

CREATE: tests/integration/test_class_a_b_params.py
(Use test cases from plan file)

UPDATE: docs/dev/spec-preset-paramspace-ir-engine-contract.md
Add "Class A vs Class B Parameters" section.

VERIFICATION:
pytest tests/integration/test_class_a_b_params.py -v
pytest tests/unit/ tests/presets/ -v --tb=short

TICK ALL CHECKBOXES in plan file
COMMIT: "Docs/Tests: Class A/B integration tests and spec update (PR5)"
```

---

## 7. Risk Register

| Risk | Trigger | Detection | Mitigation |
|------|---------|-----------|------------|
| Existing YAML has string booleans | Reading old step.yaml files | Detection returns wrong preset | Add migration note; detection still parses strings |
| UI sends typed values, not strings | Frontend passes bool directly | No issue (we handle both) | validate_and_parse handles typed input |
| Class A type registry incomplete | New IR keys added later | Tests fail | Add registry update to IR key addition process |
| Performance impact | Extra lookup per parameter | Profile update_step_params | CLASS_A_TYPES is O(1) dict lookup |

---

## 8. Appendix: Class A Key Complete List

```python
CLASS_A_TYPES = {
    # Magnetism dimension
    ("SYSTEM", "nspin"): "int",
    ("SYSTEM", "noncolin"): "bool",
    ("SYSTEM", "lspinorb"): "bool",
    
    # OccupationsScheme dimension
    ("SYSTEM", "occupations"): "str",
    ("SYSTEM", "smearing"): "str",
    ("SYSTEM", "degauss"): "float",
    
    # Precision dimension
    ("SYSTEM", "ecutwfc"): "float",
    ("SYSTEM", "ecutrho"): "float",
    ("ELECTRONS", "conv_thr"): "float",
    
    # Convergence dimension
    ("ELECTRONS", "mixing_beta"): "float",
    ("ELECTRONS", "electron_maxstep"): "int",
    ("ELECTRONS", "mixing_mode"): "str",
    ("ELECTRONS", "mixing_ndim"): "int",
    ("ELECTRONS", "diagonalization"): "str",
    
    # Other IR-mapped keys
    ("SYSTEM", "nbnd"): "int",
    ("SYSTEM", "nosym"): "bool",
    ("SYSTEM", "noinv"): "bool",
}
```

