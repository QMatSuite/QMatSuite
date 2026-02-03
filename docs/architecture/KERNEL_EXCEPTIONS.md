# Kernel Architecture Exceptions

**Status**: ACTIVE
**Version**: 3.1
**Last Review**: 2026-02-03
**Next Review**: 2026-05-02
**Governing Document**: [KERNEL_DEPENDENCY_SPEC.md](./KERNEL_DEPENDENCY_SPEC.md)

---

## Overview

This document records all approved exceptions to the [Kernel Dependency Spec](./KERNEL_DEPENDENCY_SPEC.md). Each exception MUST be:

1. Explicitly documented with rationale and code citations
2. Constrained to minimal scope with enforceable guardrails
3. Reviewed quarterly (or at stated expiration)
4. Removed when no longer necessary

**Anti-backdoor principle**: Exceptions MUST NOT become standing permission to ignore laws. Each exception has specific scope constraints and measurable expiration criteria. New usage sites under an existing exception MUST be individually documented and justified in this document before merge.

---

## Active Exceptions

### EXC-001: workflow → engine capability query

- **Law Excepted**: K2 (cross-domain import rules), Dependency DAG (engines at L2 should not be imported by L1 workflow)
- **From**: `quantumvitas.workflow.registry`
- **To**: `quantumvitas.engine.registry`
- **Reason**: Preset validation requires engine capability information to determine which presets are available for a given engine/step-type combination. Without this, the workflow registry cannot validate preset–engine compatibility at registration time.
- **Alternatives considered**:
  1. *Callback/interface injection*: Workflow registry accepts a `get_supported_presets(engine_name)` callable. Adds indirection without reducing coupling. Rejected: premature abstraction.
  2. *Static preset metadata in workflow*: Duplicate engine capability data. Rejected: violates DRY.
  3. *Move preset validation to runtime domain*: Loses early validation. Rejected: worse developer experience.
- **Constraint**:
  - ONLY the following access patterns are allowed:
    ```python
    # ALLOWED in workflow/registry.py:
    from quantumvitas.engine.registry import create_default_registry
    engine = registry.get(engine_name)
    presets = engine.supported_presets  # Property access ONLY
    ```
  - No other engine internals (methods, private attributes, configuration) may be accessed.
  - No engine execution methods (`run_step`, `prepare`, etc.) may be called.
- **Scope**: `workflow/registry.py` only. No other workflow module may import from `engine`.
- **Gate enforcement**: If `test_no_deep_import.py` is implemented, this exception MUST be in its allowlist with a comment referencing EXC-001.
- **Added**: 2026-02-02
- **Review**: Quarterly
- **Expiration criteria**: Remove if preset validation is moved to a shared interface or the runtime domain.

---

### EXC-002: Lazy imports for circular dependency avoidance

- **Law Excepted**: K1 (no cycles), general import hygiene
- **From**: Specific kernel modules (enumerated below)
- **To**: Specific kernel modules (enumerated below)
- **Reason**: Some modules have bidirectional relationships that would create circular imports at module load time. Lazy imports inside function bodies defer the import until runtime, preventing `ImportError` at module load.

#### Permissibility Rules

Lazy imports are a **last resort**. Before adding a new lazy import, the developer MUST:

1. **Attempt DAG restructuring**: Can the dependency be broken by extracting shared code into a lower-level module?
2. **Attempt parameter injection**: Can the dependency be passed as a function argument instead of imported?
3. **Document why restructuring failed**: The lazy import MUST include a comment explaining what was tried and why it failed.

#### Documentation Requirements

Every lazy import MUST include an inline comment with:
- The circular dependency chain it breaks (A → B → A)
- Why DAG restructuring is not feasible for this specific case

```python
def save_yaml_doc(doc, path):
    # LAZY IMPORT: breaks circular yaml_io -> journal -> yaml_io
    # Restructuring not feasible: journal needs yaml_io for save hooks,
    # yaml_io needs journal for recording changes.
    from quantumvitas.core.journal import get_journal
    ...
```

#### Known Instances (exhaustive list)

| From | To | Chain | Justification |
|------|----|-------|---------------|
| `core.yaml_io` | `core.journal` | `yaml_io → journal → yaml_io` | Journal records YAML changes; YAML save triggers Journal. Bidirectional by design. |
| `calculation.runner` | `execution.executor` → `calculation.manifest` | `runner → executor → manifest → runner` (indirect) | Runner provides manifest to executor; executor writes back to manifest. |

**Adding new instances**: A new lazy import MUST be added to this table and reviewed before merge. PRs that add lazy imports without updating this document SHALL be rejected.

- **Constraint**:
  - Lazy imports MUST be inside function bodies, NEVER at module level
  - Lazy imports MUST have the inline comment described above
  - Each lazy import relationship MUST be listed in the Known Instances table above
  - New lazy imports require architecture owner approval
- **Added**: 2026-02-02
- **Review**: Quarterly
- **Expiration criteria**: Each instance is individually reviewed. Remove when DAG restructuring eliminates the cycle. Target: reduce to ≤1 instance by 2026-Q4.

---

### EXC-003: Legacy package temporary bypass (DELETION SCHEDULED)

- **Law Excepted**: All kernel dependency rules (K0–K9)
- **From**: `quantumvitas.legacy.*`
- **To**: Any kernel module (and API)
- **Policy**: Our stance is **delete legacy; no compat**. This exception exists solely to allow a controlled deletion window. It is NOT a license to maintain or extend legacy code.

#### Allowed Call Sites (exhaustive)

| File | Purpose | Status |
|------|---------|--------|
| `legacy/migrate.py` | One-time format migration from v1 → v2 YAML structure | Allowed until deletion deadline |

No other files in `legacy/` may be added to this list. No new code SHALL be written in `legacy/`.

#### Constraints

- ONLY files in `quantumvitas/legacy/` may use this exception.
- Legacy code MUST NOT be called from new code paths (no reverse dependency from kernel → legacy).
- Legacy code MUST NOT introduce new SSOT write patterns.
- No new files SHALL be added to `legacy/`.
- No new imports of `legacy` from any kernel or frontend module SHALL be added.
- **PRs that add new usage of legacy code (new call sites, new imports, new callers) SHALL be rejected outright.** The only acceptable legacy-related PRs are those that *remove* legacy code or *reduce* legacy call sites.

#### Deletion Plan

| Phase | Action | Deadline |
|-------|--------|----------|
| Phase 1 (current) | Legacy code exists; exception active | Now |
| Phase 2 | Remove all callers of `legacy/` from kernel and frontends | 2026-04-01 |
| Phase 3 | Delete `quantumvitas/legacy/` directory entirely | 2026-05-01 |
| Phase 4 | Remove EXC-003 from this document; remove gate allowlist entries | 2026-05-01 |

#### CI Enforcement

- **Hard deadline**: 2026-05-01.
- After this date, `test_kernel_no_api_import.py` and all gate tests SHALL remove `legacy/` from their allowlists.
- If `quantumvitas/legacy/` still exists after 2026-05-01, CI SHALL fail.
- Gate test `test_no_legacy_imports.py` (existing) SHALL be updated to enforce zero imports from `legacy/` after the deadline.

- **Added**: 2026-02-02
- **Expiration**: Hard deadline **2026-05-01**. No renewal without new architecture owner justification and a new exception ID.

---

### EXC-004: `yaml.safe_dump` for non-SSOT export files (WHITELIST)

- **Law Excepted**: K3 (YAML writes through single entry point)
- **From**: Kernel modules that produce export artifacts
- **To**: Direct `yaml.safe_dump` calls
- **Reason**: Some operations produce YAML output that is NOT an SSOT file — e.g., history snapshots, analysis caches, user-requested exports. These do not need Journal tracking, edit locking, or History integration.

#### Whitelist Approach

`yaml.safe_dump` outside `core/yaml_io.py` is FORBIDDEN by default. It is allowed ONLY when ALL of the following conditions hold:

1. **The operation is an export**: The write MUST be a user-requested export, an immutable history artifact, or a non-SSOT materialization/cache. It MUST NOT be an SSOT mutation.

2. **The target path is within a whitelisted non-SSOT zone inside the project**. The complete whitelist of allowed relative path patterns (from project root):

   | Zone | Relative Pattern | Scope | Purpose |
   |------|-----------------|-------|---------|
   | History | `.history/**` | Project-level | Immutable run snapshots, event logs |
   | Analysis cache | `<calc_dir>/.analysis/**` | Calc-scoped (inside each calculation directory) | Per-calculation analysis materializations (see `core/analysis/cache.py:18` `ANALYSIS_CACHE_DIR = ".analysis"`) |
   | Exports | `exports/**` | Project-level | User-requested export files |

   **Strictness**: All patterns are relative to the resolved project root. The target path MUST resolve to a descendant of the project root. Writing outside the project root from kernel code is FORBIDDEN (user-facing exports outside the project are the facade layer's responsibility per API Constitution H9.3, out of scope here). Paths outside these zones are FORBIDDEN for `yaml.safe_dump`.

3. **The target path MUST NOT match any SSOT pattern**:
   - `project.qv.yml`
   - `calculation.yaml`
   - `*.step.yaml`
   - Any path under the SSOT resource tree that is read by `load_yaml_doc()` or `_load_yaml_raw()`

4. **Inline documentation**: Each usage MUST include a comment:
   ```python
   # EXC-004: Non-SSOT export to whitelisted zone (.history/).
   # Not tracked by Journal.
   yaml.safe_dump(data, outfile)
   ```

#### Path Validation

Code using this exception MUST call `is_export_zone(path, project_root)` before writing. The helper SHALL validate that the resolved path is (a) a descendant of the resolved project root, and (b) within one of the whitelisted zones:

```python
# Required validation pattern (implementation in core/yaml_io.py or a dedicated helper):

# Project-level zones (directly under project root)
_PROJECT_ZONES = {".history", "exports"}
# Calc-scoped zones (may appear inside any calculation subdirectory)
_CALC_SCOPED_ZONES = {".analysis"}

def is_export_zone(path: Path, project_root: Path) -> bool:
    """Return True if path is within a whitelisted non-SSOT export zone.

    Rules:
    - Path MUST resolve inside project_root.
    - .history/ and exports/ must be direct children of project_root.
    - .analysis/ may appear inside any calculation subdirectory.
    """
    resolved = path.resolve()
    root = project_root.resolve()
    # Must be inside project root
    if not str(resolved).startswith(str(root) + "/"):
        return False
    rel = resolved.relative_to(root)
    parts = rel.parts
    # Project-level zones: first component must match
    if parts[0] in _PROJECT_ZONES:
        return True
    # Calc-scoped zones: .analysis/ may appear at any depth inside a calc dir
    if _CALC_SCOPED_ZONES & set(parts):
        return True
    return False
```

Every call site MUST include the assertion:

```python
assert is_export_zone(path, project_root), f"EXC-004: {path} is not in a whitelisted export zone"
```

#### Gate Enforcement

`test_yaml_write_single_entry.py` (G-K3) SHALL:
1. Scan all `yaml.safe_dump` calls in kernel code.
2. Allow only `core/yaml_io.py` unconditionally.
3. For any other call site: require it to be in the gate's allowlist AND require the source line to contain the `is_export_zone` assertion or `# EXC-004` comment.
4. The allowlist MUST match this document exactly. Undocumented entries are CI failures.

#### Frontend Note

Frontend modules (`api/service.py`, `cli/main.py`) that write non-SSOT YAML for export are governed by API Constitution H9.3, not by this kernel exception. This exception covers only kernel-internal writes.

- **Added**: 2026-02-02
- **Review**: Quarterly
- **Expiration criteria**: Remove individual usages when the export functionality is moved to a dedicated export service with its own write policy. The whitelist itself persists as long as any kernel module needs to write non-SSOT YAML.

---

## Removed Exceptions

*None yet.*

---

## Exception Request Process

To request a new exception:

1. Open an issue with title `[KERNEL-EXC] <brief description>`
2. Include:
   - **Law excepted**: Which specific law (K0–K9) is being bypassed
   - **From/To**: Which modules are involved (file paths)
   - **Reason**: Why the exception is necessary
   - **Constraint**: How the exception will be limited (scope, patterns, assertions)
   - **Alternatives considered**: What other approaches were tried and why they failed
   - **Expiration criteria**: Under what conditions the exception should be removed
   - **Deletion plan**: If temporary, explicit phase+deadline for removal
3. Get approval from architecture owner
4. Add to this document with review date
5. Update relevant gate test allowlists with a comment referencing the exception ID

**Rejection criteria**: An exception request SHALL be rejected if:
- It lacks expiration criteria or deletion plan
- It applies to more than one law without individual justification per law
- The scope constraint is not enforceable by a gate test
- Alternatives were not documented

---

## Quarterly Review Checklist

- [ ] Review each active exception against its expiration criteria
- [ ] Confirm exception is still necessary (code still requires it)
- [ ] Check that constraints are being followed (no scope creep):
  - [ ] EXC-001: Only `workflow/registry.py` imports from `engine.registry`; only `supported_presets` accessed
  - [ ] EXC-002: Lazy imports table matches actual code; no undocumented lazy imports added
  - [ ] EXC-003: No new code paths import from `legacy/`; deletion deadline not passed; if passed, verify deletion complete
  - [ ] EXC-004: All `yaml.safe_dump` usages outside `yaml_io.py` have `# EXC-004` comment AND `is_export_zone` assertion; target paths are within whitelist zones only
- [ ] Verify gate test allowlists match this document (no undocumented entries)
- [ ] Update review dates
- [ ] Remove exceptions that meet their expiration criteria
- [ ] File issues for exceptions approaching expiration without resolution

---

**End of Kernel Exceptions v3.1**
