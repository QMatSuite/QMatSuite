# Journal/YamlDoc High-Impact Review Note

**Date**: 2026-01-01  
**Reviewer**: AI Assistant

## Summary

The prior implementation is **mostly correct** with one **medium-impact issue** that needs attention during the workflow refactor.

---

## Review Results

### 1. Journal Hook Ordering ✅ CORRECT

The ordering in `save_yaml_doc()` is safe:
1. Capture `before` (snapshot) and `after` (current state)
2. Write to disk via `_save_yaml_raw()`
3. Update doc snapshot via `commit_changes()`
4. Record journal entry

**Failure behavior**: If journal recording fails, the save already succeeded (wrapped in try/except). This is correct - data integrity takes priority over audit logging.

### 2. Branch-Write Rejection ✅ SAFE

The `set(path, dict)` rejection does **not** break existing code:
- `presets/integration.py` uses `apply_patch()`, which recursively walks to leaves
- `apply_patch()` calls `set()` only on non-dict values
- No existing code was found that calls `doc.set(path, {dict_value})`

**Conclusion**: Safe. If needed, use `apply_patch()` for nested structures.

### 3. Delete Semantics ✅ CORRECT

- `set(path, None)` stores `None` as a value (explicit null)
- `delete(path)` removes the key
- `apply_patch()` treats `None` as delete (Semantics A)

These are correctly separated. No leakage.

### 4. YAML IO Bypass Paths ⚠️ MEDIUM-IMPACT ISSUE

**17 files** still contain `yaml.safe_load/dump`. Most are acceptable:

| File | Usage | Status |
|------|-------|--------|
| `yaml_io.py` | Canonical load/dump | ✅ Correct |
| `api.py:877` | **Step creation bypasses yaml_io** | ⚠️ **Fix during workflow refactor** |
| `models.py:347` | Calculation model save | ⚠️ Should migrate to CalcDoc |
| `project/storage.py` | Project settings | ⚠️ Should migrate to ProjectDoc |
| Others | Read-only, snapshots, migration | ✅ Acceptable |

**Key Issue**: `api.py:877` writes step YAML directly:
```python
step_yaml_path.write_text(yaml.safe_dump(spec.to_dict(), sort_keys=False))
```

This bypasses:
- StepDoc abstraction
- Journal recording
- Any future validation

**Action**: This will be fixed in Part 5 (Centralize step creation) of the workflow refactor.

---

## Recommendations

1. **No immediate code changes needed** - the current implementation is functional
2. **During workflow refactor**: Centralize step creation through `StepDoc` + `yaml_io.save_yaml_doc()`
3. **Future work**: Migrate `models.py` save functions to use CalcDoc/ProjectDoc

---

## Verification

The following tests confirm correctness:
- 64 YamlDoc unit tests passing
- 23 Journal unit tests passing
- 810 unit+integration tests passing (network-blocked excluded)

