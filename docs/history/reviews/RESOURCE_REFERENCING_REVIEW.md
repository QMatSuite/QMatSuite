# Resource Referencing & Project Nesting — Deep Code Review

**Date:** 2026-02-26
**Scope:** Audit of project nesting guards, resource reference patterns, and MCP boundary resolution. Triggered by the v1.2.2 production blind test where parent-around-child nesting occurred.
**Status:** Read-only review — no source code changes.

---

## 1. Executive Summary

During the v1.2.2 blind test (`docs/history/production-tests/v1.2.2/BLINDTEST_2026-02-26_CLAUDE_CODE.md`), the agent created two QMatSuite projects in a parent-child directory relationship:

1. **Test 1 (CLI):** Project at `~/qms-blindtest/si_scf/silicon-scf/` (inner, created first)
2. **Test 2 (MCP):** Project at `~/qms-blindtest/` (outer, created second via `init_project`)

This is a **parent-around-child** nesting scenario that the current nesting guard does not detect. The guard only walks UP from the target directory looking for an enclosing project — it never scans DOWN into subdirectories for existing projects that would become enclosed.

**Risk assessment:** Low-to-medium. ULID-based identity prevents resource ID collisions between the two projects. The primary risk is operational confusion when `find_project_root` is called from a directory between the two project roots (e.g., `~/qms-blindtest/si_scf/`), which would resolve to the outer project.

---

## 2. Nesting Guard Analysis

### 2.1 How `detect_enclosing_project` Works

**File:** `src/qmatsuite/core/context.py` (lines 156-171)

```python
def detect_enclosing_project(path: Path, max_depth: int = 20) -> Optional[Path]:
    path = Path(path).resolve()
    return _find_project_root(path, max_depth)
```

Delegates to `_find_project_root()` (lines 136-153), which walks `current = current.parent` in a loop — pure upward traversal. Stops at filesystem root or after `max_depth` levels.

**What it blocks:** Creating project B inside existing project A (child-inside-parent).
**What it misses:** Creating project A around an existing project B (parent-around-child).

### 2.2 How `init_project` Uses the Guard

**File:** `src/qmatsuite/api/service.py` (lines 8288-8311)

```python
enclosing_project = detect_enclosing_project(target_dir)
if enclosing_project:
    # Allow only if target is under enclosing_project/.tmp/
    ...
    if not allow_under_tmp:
        raise ValueError("Cannot create a new project inside an existing QMatSuite project.")
```

The guard calls `detect_enclosing_project(target_dir)` which walks UP from `target_dir`. If `target_dir` is the outer directory and the existing project is below it, the upward walk finds nothing — the guard passes.

### 2.3 Test Coverage

**File:** `tests/unit/test_api_service.py`

- `test_init_project_prevents_nested_project` (lines 50-59): Creates parent first, then attempts child. **Correctly blocked.**
- `test_init_project_allows_tmp_subdir_inside_project` (lines 72-81): `.tmp/` exemption works.
- **Missing test:** No test creates a child project first and then attempts to create a parent project around it.

### 2.4 The Blind Test Scenario

```
Timeline:
1. CLI: qms init project --name "Silicon SCF" --path ./si_scf
   → Created: ~/qms-blindtest/si_scf/silicon-scf/project.qms.yml

2. MCP: init_project(name="")
   → CWD: ~/qms-blindtest/
   → detect_enclosing_project(~/qms-blindtest/) walks UP → finds nothing
   → Created: ~/qms-blindtest/project.qms.yml  ← OUTER project wraps inner
```

Result: Two valid `project.qms.yml` files in a parent-child relationship.

### 2.5 Consequence: `find_project_root` from Middle Directory

**File:** `src/qmatsuite/core/project_utils.py` (lines 393-445)

`find_project_root()` also walks upward only (same pattern as `_find_project_root`). If invoked from `~/qms-blindtest/si_scf/` (the middle directory with no `project.qms.yml`), it returns `~/qms-blindtest/` — the OUTER project. A user who `cd`s into `si_scf/` and runs an MCP tool would unknowingly operate on the outer project, not the inner `silicon-scf/` project.

**Note:** There is also a duplicate `_find_project_root()` in `src/qmatsuite/core/yaml_io.py` (lines 273-286) with the same upward-only behavior.

### 2.6 Possible Fixes (Not Implemented)

| Approach | Complexity | Trade-off |
|----------|-----------|-----------|
| Scan immediate children for `project.qms.yml` on init | Low | Only catches depth-1 nesting |
| Recursive `rglob("project.qms.yml")` under target | Medium | Could be slow on large trees; O(n) filesystem scan |
| Advisory warning instead of hard block | Low | User can choose to proceed |
| Ignore (rely on ULID isolation) | None | Operational confusion remains |

**Recommendation:** A shallow scan (depth 1-2) on `init_project` would catch the most common case without performance concerns. Not urgent — the ULID identity layer prevents data corruption.

---

## 3. Resource Reference Audit

### 3.1 Constitutional Authority

**Constitution §6** (lines 126-151 of `CONSTITUTION.md`) establishes:

> Resources may only reference each other via **ULID**.
> Paths, filenames, slugs may only serve as Info — never as cross-resource reference keys.
> DTOs/meta MUST NOT contain legacy identity fields (`id`, `calc_id`, `step_id`, `run_id`, etc.).

Canonical fields: `project_ulid`, `calc_ulid`, `step_ulid`, `run_ulid`.

Immutable truth keys: ULID, `step_type_spec`, engine.
Mutable info keys: name, slug, path, description.

Gate enforcement: `tests/gates/test_no_legacy_identity_fields.py`

### 3.2 ULID Reference Fields (Cross-Resource)

All cross-resource references in the codebase use ULID:

| Resource | Field | Location | Validation |
|----------|-------|----------|------------|
| ResourceMeta | `ulid` | `core/resources.py:219` | 26 chars, starts "01"; hard error on legacy `id` (line 246-249) |
| CalculationModel | `structure_ulid` | `core/models.py:190` | Immutable once set |
| CalculationStepEntry | `step_ulid` | `core/models.py:70` | 26 chars starting "01" (line 139); hard error on legacy `step_file` (line 135) |
| CalculationDTO | `calc_ulid`, `structure_ulid`, `step_ulids` | `api/types/calculation.py:35-104` | ULID format |
| StepDTO | `step_ulid`, `calc_ulid` | `api/types/calculation.py:108-139` | ULID format |
| StructureDTO | `structure_ulid` | `api/types/structure.py:18-80` | ULID format |

### 3.3 The `reference_output` Exception

**File:** `src/qmatsuite/calculation/step.py` (line 32)

```python
@dataclass(slots=True)
class Step:
    reference_output: Optional[Path] = None  # FILE PATH, not ULID
```

This is the **only cross-step artifact reference that uses a file path** instead of a ULID. It stores a path to an upstream step's output file for debugging/comparison purposes.

**Usage in runner.py:** Passed as `reference_file=step.reference_output` during skip-case handling (line 587) and normal execution (line 642). These are for logging/reporting only — not for functional step dispatch or identity resolution.

**Risk:** Low. This field is optional, used for developer diagnostics, and is not persisted in YAML SSOT files. It does not participate in resource identity or cross-resource referencing.

### 3.4 The `restart_from` Pattern

**File:** `src/qmatsuite/engine/lammps_engine.py` (lines 132-460)

`restart_from` references an upstream step by ULID (or slug/index) within the same calculation. It resolves to an artifact directory: `raw_dir / upstream_step_ulid`.

Validation:
- Self-reference detection with hard error (line 427)
- Lookup by ULID, slug, or index (lines 440-447)
- Same-calculation scope enforced — never cross-calculation

**Assessment:** Compliant with §6. The ULID is the canonical reference; slug/index are convenience aliases resolved to ULID before use.

### 3.5 Info-Layer Fields (Non-Cross-Reference)

| Resource | Field | Type | Purpose |
|----------|-------|------|---------|
| ResourceMeta | `name` | str | Display name (mutable) |
| ResourceMeta | `slug` | str | Filesystem-friendly ID (mutable) |
| ResourceMeta | `path` | str | Relative path from project root (mutable) |
| CalculationModel | `structure_name` | str | Cosmetic display only |
| Step | `reference_output` | Path | Developer diagnostics only |

These are all correctly categorized as Info-layer per Constitution §6.4.

### 3.6 Gate Test Coverage

**File:** `tests/gates/test_no_legacy_identity_fields.py`

Enforcement scope:
- **YAML/JSON scanning** (lines 140-205): Scans `tests/fixtures/`, `tests/data/`, `src/qmatsuite/resources/` for forbidden fields
- **Python source scanning** (lines 320-394): Scans `src/` for class field definitions containing `id`, `calc_id`, `step_id`, etc.
- **Allowlisted classes:** `RPCRequest`, `RPCResponse` (JSON-RPC `id`), `Job` (execution graph), `JournalEntry`, `LibraryMetadata`, `WorkflowTemplate`, `HistoryEvent`, `RunRevision`

**Assessment:** Gate test is comprehensive. The allowlist is justified (JSON-RPC spec requires `id`; Job graph uses `id` for internal scheduling, not cross-resource identity).

---

## 4. MCP Boundary Resolution

### 4.1 Project Root Scoping

**File:** `src/qmatsuite/mcp/project.py` (lines 16-51)

All MCP tools resolve the current project via:

```
MCP Tool → get_service() → get_project_root() → find_project_root()
```

`get_project_root()` returns `_project_root_override` if set (for testing), otherwise calls `find_project_root()` which walks up from CWD. On failure, raises `ProjectNotFoundError`.

`QMSService(project_root)` is then instantiated, and `ResourceIndex` is built scoped to that single project root.

**Isolation guarantee:** `ResourceIndex` only scans `calculations/**/calculation.yaml`, `calculations/**/steps/*.step.yaml`, and `structures/*.json` under the given `project_root`. No cross-project resources are ever indexed.

### 4.2 `structure_selector` Resolution

**File:** `src/qmatsuite/core/resolution.py`

`structure_selector` (used by `create_calculation`, `quick_run`, `generate_kpath`) accepts name, slug, or ULID. Resolution order:

1. **ULID** (26-char uppercase alphanumeric) — exact match in `by_id`
2. **Slug** — exact match in `by_slug`
3. **Name** — case-insensitive exact match in `by_name`
4. **Path** — relative path match in `by_path` (fallback)

All lookups are scoped to the current project's `ResourceIndex`.

### 4.3 `calc_ulid` — Strict ULID-Only

`calc_ulid` parameters (used by `inspect_calculation`, `run_calculation`, `set_parameters`, etc.) are strict ULID-only. Validation happens downstream via `validate_ulid()` (resolution.py lines 488-508):

```python
def validate_ulid(ulid_str: str, kind: str = "resource") -> str:
    if not _is_ulid_like(ulid_str):  # 26 chars, alphanumeric, uppercase
        raise ValueError(f"Invalid {kind} identifier: '{ulid_str}' is not a ULID.")
    return ulid_str
```

No slug/name resolution is performed for `calc_ulid` parameters — this is by design.

### 4.4 `AmbiguousSelectorError`

**File:** `src/qmatsuite/core/resolution.py` (lines 43-45)

Raised when a name/slug selector matches multiple resources of the same kind. Triggered in:
- `ResourceIndex.resolve_id()` (line 375-378): When `expected_kind` filter is active
- `resolve_structure()` (lines 982, 989, 996): ULID/slug/name ambiguity in legacy fallback
- `resolve_calculation()`: Same pattern

**Cross-project collision:** Not possible by design. `ResourceIndex` is built per-project, so selectors from project A never resolve against resources from project B.

### 4.5 Missing: Cross-Project Leakage Test

There is no explicit test that:
1. Creates two projects (parent/child or sibling)
2. Verifies that MCP tools operating on project A cannot see resources from project B

**Implicit protection:** Each test uses an isolated `tmp_path` fixture, and `ResourceIndex` is strictly scoped. The lack of an explicit test is a documentation gap, not a security gap.

---

## 5. Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Parent-around-child nesting created silently | Medium (happened in blind test) | Low (ULID prevents data corruption) | Shallow downward scan on `init_project` |
| `find_project_root` returns wrong project from middle dir | Low (requires `cd` into specific intermediate dir) | Medium (operations target wrong project) | User education; consider warning on project load |
| `reference_output` path leaks across projects | Very low (field is optional, diagnostic-only) | Low (no functional effect) | None needed |
| Same slug in nested projects causes confusion | Low (requires deliberate naming overlap) | Low (ULID is canonical, slug is info-only) | None needed |
| ResourceIndex indexes child project's resources | None (impossible by design) | N/A | Scan is bounded to `project_root` |

---

## 6. Conclusions

1. **ULID policy is well-enforced.** Constitution §6 is codified, gate-tested, and consistently implemented across DTOs, models, and YAML persistence. The `reference_output` exception is justified (diagnostic path, not identity).

2. **Nesting guard has a one-directional gap.** `detect_enclosing_project` only walks UP. The blind test demonstrated that creating a project in a parent directory of an existing project is silently allowed. This is a gap in the guard, not a gap in data integrity.

3. **MCP boundary resolution is sound.** `ResourceIndex` is strictly project-scoped. `structure_selector` resolves via a well-defined priority chain (ULID > slug > name > path). `calc_ulid` enforces strict ULID format. `AmbiguousSelectorError` handles name collisions within a project.

4. **No cross-project leakage is possible** through the resource resolution layer. Each project's `ResourceIndex` scans only its own filesystem subtree. The risk of operating on the wrong project exists only at the `find_project_root` level (upward walk from ambiguous directory), not at the resource resolution level.

5. **The blind test nesting scenario is operationally confusing but data-safe.** Both projects have independent ULIDs, independent `project.qms.yml` files, and independent resource namespaces. The risk is a user accidentally targeting the wrong project, not data corruption.
