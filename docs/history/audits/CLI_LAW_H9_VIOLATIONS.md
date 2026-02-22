# CLI Law H9 Violations Analysis

**Date**: 2026-02-02
**Status**: Investigation Complete
**Goal**: Document CLI violations and migration plan to use API functions

---

## 1. Law H9 Recap

Per API Constitution:
> **Only kernel is allowed to modify the filesystem.**
>
> Frontends (daemon, CLI, GUI, Jupyter adapters) MUST NOT write to YAML files directly.
> All filesystem mutations MUST go through kernel via API calls.

---

## 2. Violation Summary

| Line | Command | File Written | Violation Type |
|------|---------|--------------|----------------|
| 750-752 | `init project` | `project.qms.yml` | SSOT write |
| 936 | `init calculation` | `calculation.yaml` | SSOT write |
| 1393 | `init step` | `calculation.yaml` | SSOT write |
| 2569 | `update step` | `*.step.yaml` | SSOT write |
| 2577 | `update step` | `calculation.yaml` | SSOT write |
| 2968 | `delete step` | `calculation.yaml` | SSOT write |
| 3234 | `modify step` (rename) | `calculation.yaml` | SSOT write |
| 3508 | `modify calculation` (structure) | `*.step.yaml` | SSOT write |
| 3592 | `modify calculation` | `calculation.yaml` | SSOT write |
| 5044 | `_write_step_spec` | `*.step.yaml` | SSOT write |

**Allowed Exception:**
- Line 1448: `save-project` - writes to user-specified export file (H9.3 exception for scratch/export files)

---

## 3. CLI to API Mapping

### 3.1 Project Operations

| CLI Command | Current CLI Code | Required API Function | API Location |
|-------------|------------------|----------------------|--------------|
| `qms init project` | Direct YAML write (L750-752) | `QMSService.init_project()` | service.py:6742 |

### 3.2 Calculation Operations

| CLI Command | Current CLI Code | Required API Function | API Location |
|-------------|------------------|----------------------|--------------|
| `qms init calculation` | Direct YAML write (L936) | `svc.project.init_calculation()` | service.py:5865 |
| `qms modify calculation --structure` | Direct YAML write (L3508,3592) | `svc.calculation.change_structure()` | service.py:3585 |
| `qms modify calculation --reorder` | Direct YAML write (L3592) | `svc.calculation.reorder_steps()` | service.py:4371 |

### 3.3 Step Operations

| CLI Command | Current CLI Code | Required API Function | API Location |
|-------------|------------------|----------------------|--------------|
| `qms init step` | `_write_step_spec()` (L1393,5044) | `svc.calculation.add_step()` | service.py:3743 |
| `qms update step --params` | Direct YAML write (L2569,2577) | `svc.calculation.update_step_params()` | service.py:3074 |
| `qms delete step` | Direct YAML write (L2968) | `svc.calculation.remove_step()` | service.py:3918 |
| `qms modify step --name` | Direct YAML write (L3234) | `svc.calculation.update_step_params()` | service.py:3074* |

*Note: Step rename may need a dedicated `rename_step()` method or use `update_step_params()` with name in meta.

---

## 4. Migration Priority

### 4.1 High Priority (Core Operations)

| Rank | Command | Lines | Impact | Notes |
|------|---------|-------|--------|-------|
| 1 | `init step` | 1393, 5044 | HIGH | Most common operation |
| 2 | `update step` | 2569, 2577 | HIGH | Frequent user operation |
| 3 | `delete step` | 2968 | MEDIUM | Straightforward mapping |

### 4.2 Medium Priority (Calculation Level)

| Rank | Command | Lines | Impact | Notes |
|------|---------|-------|--------|-------|
| 4 | `init calculation` | 936 | MEDIUM | Has API equivalent |
| 5 | `modify calculation` | 3508, 3592 | MEDIUM | API exists |

### 4.3 Lower Priority (Project Level)

| Rank | Command | Lines | Impact | Notes |
|------|---------|-------|--------|-------|
| 6 | `init project` | 750-752 | LOW | Foundational but rare |

---

## 5. Pre-Migration Tests Required

Each CLI command needs behavior-preservation tests before migration:

### 5.1 init step
```
Test: CLI creates step with correct structure
- Creates step YAML file in steps/ directory
- Updates calculation.yaml with step reference
- Sets correct step_type_gen and step_type_spec
- Copies parameters from template if --template provided
- Returns correct step ULID
```

### 5.2 update step
```
Test: CLI updates step parameters correctly
- Modifies parameters in step YAML
- Preserves existing parameters not being updated
- Updates cards and species_overrides
- Returns success message
```

### 5.3 delete step
```
Test: CLI removes step correctly
- Moves step YAML to trash
- Removes step from calculation.yaml steps array
- Does not affect other steps
- Returns success message
```

### 5.4 init calculation
```
Test: CLI creates calculation correctly
- Creates calculation directory
- Creates calculation.yaml with correct structure
- Links to specified structure via structure_ulid
- Adds calculation to project.qms.yml
- Returns calculation ULID
```

### 5.5 modify calculation
```
Test: CLI modifies calculation correctly
- --structure: Updates calculation and all step structure_ulid fields
- --reorder: Reorders steps array correctly
- Returns success with change summary
```

### 5.6 init project
```
Test: CLI creates project correctly
- Creates project directory structure
- Creates project.qms.yml with correct schema
- Creates structures/ and calculations/ subdirectories
- Returns success message
```

---

## 6. Implementation Plan

### Phase 1: Test Coverage
1. Write E2E tests for each CLI command capturing current behavior
2. Tests should use CLI invocation, not internals
3. Verify tests pass with current implementation

### Phase 2: API Verification
1. Ensure each required API function exists and works correctly
2. If API method is missing, add to service.py
3. Verify daemon uses same API methods correctly

### Phase 3: CLI Migration
For each command:
1. Replace direct YAML write with API call
2. Ensure error handling maps correctly
3. Verify test still passes
4. Verify CLI output matches previous behavior

### Phase 4: Cleanup
1. Remove unused internal helpers (e.g., `_write_step_spec`)
2. Remove YAML import from CLI where no longer needed
3. Update worklog with final counts

---

## 7. Code Patterns

### Before (Violation)
```python
# Direct YAML write - FORBIDDEN
calculation_yaml.write_text(yaml.safe_dump(calculation_data, sort_keys=False))
```

### After (Compliant)
```python
# Use API - REQUIRED
svc = QMSService(project_root)
svc.calculation.add_step(calc_selector, step_spec)
```

---

## 8. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Behavior change after migration | Pre-migration tests capture exact behavior |
| Error message changes | Tests verify user-facing messages |
| Performance regression | API calls may add overhead - acceptable |
| Missing API capabilities | Add new methods before migration |

---

**End of Violations Analysis**
