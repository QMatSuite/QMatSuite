# QMatSuite — Claude Code Instructions (also for GPT Codex)

## Authoritative Laws

This project has a binding constitution and law specs. Before making changes to any area, you MUST read the relevant law document(s).

### Document Hierarchy (highest to lowest authority)
1. `CONSTITUTION.md` (repo root) — L0 central constitution. Read the relevant section before any architectural decision.
2. `docs/laws/L1/` — Laws & constitutions (8 files). Read the specific law before working in that domain.
3. `docs/laws/L2/` — Specs, policies, playbooks (15 files). Binding operational rules.
4. `docs/design/` — Design docs. Reference only; not binding.

### Which Law to Read by Domain

| If working on... | Read these FIRST |
|-------------------|-----------------|
| API surface, utils, DTOs, imports | `docs/laws/L1/API_CONSTITUTION.md` + Constitution §18 |
| Kernel internals, domain boundaries | `docs/laws/L1/KERNEL_DEPENDENCY_SPEC.md` + Constitution §19 |
| Kernel exceptions, lazy imports | `docs/laws/L1/KERNEL_EXCEPTIONS.md` |
| Step types (GEN/SPEC), conversion | `docs/laws/L1/STEP_TYPE_GEN_SPEC_CONSTITUTION.md` + Constitution §7 |
| Engine integration, drivers | `docs/laws/L1/ENGINE_INTEGRATION_CONSTITUTION.md` + Constitution §17 |
| Engine recipes, runner, adding engines | `docs/laws/L1/ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md` + Constitution §17.4 |
| Presets, ParamSpace, IR, detection | `docs/laws/L1/PARAMSPACE_SPEC.md` + Constitution §8 |
| YAML, SSOT, persistence | Constitution §2 |
| History, runs, revisions | Constitution §3 + `docs/laws/L1/PROVENANCE_VERSIONED_HISTORY_SPEC.md` |
| Provenance, versioned history, CAS, rollback | `docs/laws/L1/PROVENANCE_VERSIONED_HISTORY_SPEC.md` |
| Locks, concurrency | Constitution §4 |
| Incremental run, manifest, skip | Constitution §5 |
| Identity, ULID, meta | Constitution §6 |
| Species, pseudopotentials | Constitution §9 |
| Parameter scans | Constitution §10 |
| Relax workflows | Constitution §13 |
| LAMMPS | Constitution §14 |
| Geometry, canonicalization | Constitution §15 |

### Cross-Reference Index

The full cross-reference mapping (invariants to definitions to enforcement gates) is at:
`docs/laws/README.md`

## Test Rules

1. **Always activate venv**: `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
2. **Gate tests** are in `tests/gates/` — these enforce constitutional invariants via CI. Never disable or weaken a gate test without explicit author approval.

## Engine Recipe & Runner — Hard Bans

When working on engine-related code, these are absolute prohibitions (from ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md §9):

1. **No scattered mapping dicts**: No ad-hoc `step_type -> engine` mapping dicts outside the recipe/registry SSOT. Not in tests, handlers, runner, or daemon/CLI.
2. **No runner engine imports**: Runner and executor code MUST NOT directly import engine-specific modules. Use `DriverRegistry.get_handler()` and `DriverRegistry.get_recipe_class()`.
3. **No prefix inference**: Never determine engine from step type by prefix pattern matching (e.g., `if step_type.startswith("vasp_")`). Use explicit registry lookup.
4. **No silent fallbacks**: Never default to any engine when lookup fails (e.g., `mapping.get(step_type, "qe")`). Unknown types must raise hard errors.

## How to Add a New Engine

When adding a new engine, follow the checklist in `docs/laws/L1/ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md` §10. Key points:

1. Create driver bundle at `src/qmatsuite/drivers/<engine>/` (driver.py, handler.py, recipe.py, step_types.py, __init__.py)
2. Implement the 7-item MUST interface in driver.py (engine_family, display_name, driver_api_version, get_step_type_specs, get_handler, get_recipe_class, get_materialization_map)
3. Choose recipe archetype: Directory-state (QE-like), Strong-chain (QC-like), or Cleanup (VASP-like)
4. Register via `DriverRegistry.register()` in the driver's `__init__.py`
5. Add import to `src/qmatsuite/drivers/__init__.py`
6. **You MUST NOT modify**: `runner.py`, `executor.py`, `handlers.py`, `driver_registry.py`, `driver_protocol.py`, or any kernel routing/dispatch code

## Sensitive Information — Hard Ban (Law S1)

No real usernames, hostnames, absolute home paths, or other locally-identifying strings may appear in any committed file (code, docs, tests, fixtures, golden refs, templates, resources).

### Prohibited patterns (non-exhaustive)
- Real usernames (e.g. `jsmith`, login names from `whoami`)
- Real hostnames (e.g. `WORKSTATION-XYZ`, output of `hostname`)
- Absolute home paths (e.g. `/Users/<name>/...`, `/home/<name>/...`, `C:\Users\<name>\...`)
- Session/temp paths that embed usernames or hostnames

### Required replacements
| Instead of... | Use... |
|---------------|--------|
| `/Users/<real-name>/...` | `$HOME/...` or `<HOME>/...` or a relative path |
| Real username in output | `<USER>` |
| Real hostname in output | `<HOST>` |
| Engine install path | `<ENGINE_ROOT>` or env var |
| Scratchpad temp paths | `<TMPDIR>/...` |

### Where sensitive data MAY live (uncommitted only)
- `.tmp/` (gitignored)
- Local scratchpad directories
- User's `~/.claude/` directory

### Enforcement
- **Gate test**: `tests/gates/test_no_sensitive_paths.py` scans all tracked files on every CI run.
- Any PR that introduces a real local identifier will be caught and must be fixed before merge.

## Key Invariants (Quick Reference)

- **SSOT**: Only `calculation.yaml` + `step.yaml`. No other files are truth.
- **ULID-only**: No `id`, `calc_id`, `step_id` fields. Use `*_ulid` fields.
- **GEN/SPEC only**: `step_type_gen` (intent) + `step_type_spec` (execution). No bare `step_type`.
- **No conversion above kernel**: Daemon/CLI must NOT call gen_from/spec_from/prefix_from.
- **Frontend no YAML write**: Only kernel writes SSOT files (Law H9).
- **No legacy, no compat**: Delete legacy code; do not maintain backward compatibility shims.
- **Runner is engine-agnostic**: All dispatch through DriverRegistry; no engine-specific imports in runner.
- **One engine, one recipe**: Each engine has exactly one driver class with PREFIX + SUPPORTED_GEN_STEPS.
- **History world independence**: Deleting `.provenance/` must leave project runnable. SQLite/CAS never in runtime paths.
- **OperationContext required**: All `save_yaml_doc()` calls must carry an opctx. No opctx = hard error.
