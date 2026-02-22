# Debug Logs Documentation

## Overview

QMatSuite provides debug logging features to help diagnose issues with resource resolution, workflow detection, and step detail loading. These logs are **OFF by default** to avoid spamming normal users, but can be enabled via Settings → Debug.

## Debug Toggles

### Resolution/Addressing Debug Logs

**Location**: Settings → Diagnostics / Debug → Resolution/Addressing Debug Logs

**Default**: OFF

**What it enables**:

When enabled, emits detailed trace logs for:

1. **Resource Resolution** (`[RESOLVE_ID]`, `[RESOLVE_STEP]`):
   - Which resolution strategy was used (ULID, slug, name, path)
   - Expected resource kind vs resolved kind
   - Slug collision detection and filtering
   - Step resolution within calculation context

2. **Step Detail Loading** (`[GET_STEP_DETAIL]`):
   - Calculation ULID and step selector provided by UI
   - Whether step selector is a ULID or slug
   - `calculation.yaml.steps[]` entries (step_id, type)
   - Step entry found in calculation.yaml
   - Step resolved via ResourceIndex (id, slug, kind, path)

3. **Workflow Detection** (`[WORKFLOW_DETECT]`):
   - Starting workflow detection (calc_dir, project_root, steps_count)
   - Processing each step entry (step_id, type_in_entry)
   - Resolving step by ULID (step_id → step_type from step YAML)
   - Using type from calculation.yaml.steps[] entry
   - Resolving step by file path (legacy format)
   - Step added to present_steps
   - Final collected present_steps list

4. **RPC Boundary Logging** (`[STEP_DETAIL_RPC]`, `[GET_CALCULATION_DETAIL_RPC]`, etc.):
   - UI-provided identifiers (calculation selector, step selector)
   - ULID detection (is_ulid, len)
   - Resolving calculation selector to ULID (slug/name → ULID conversion)
   - Resolved calculation/step metadata

## What to Look For

### ULID vs Slug Issues

Look for logs showing:
- `is_ulid=False` - UI is passing slug/name instead of ULID
- `WARNING: Step identifier is NOT a ULID!` - Step selector is not a ULID (may cause slug collisions)
- `WARNING: Non-ULID calculation identifier received` - Core endpoint received non-ULID (should not happen)

### Expected Kind Mismatches

Look for logs showing:
- `resolved to kind='calculation', expected='step'` - Slug collision detected (resolver found wrong resource kind)
- `expected_kind='step'` but resolved to different kind - Resolver filtering is working correctly

### Missing Type Fields

Look for logs showing:
- `WARNING: Step entry has no type field!` - `calculation.yaml.steps[]` entry missing `type` field
- `Step {i+1} could not be resolved: no step_type found` - Workflow detection cannot determine step type

### Calculation Selector Issues

Look for logs showing:
- `Resolving calculation selector to ULID: '{slug}'` - UI passed slug, daemon converting to ULID
- `Resolved calculation '{slug}' -> ULID '{ulid}'` - Successful conversion

## Log Levels

**When flag is OFF (default)**:
- Only high-level INFO logs (RPC timings, etc.)
- Warnings about real correctness issues (non-ULID in core endpoint, resolver kind mismatch, missing type fields)
- No detailed trace logs

**When flag is ON**:
- Full trace logs with all context (project, calc_ulid, step_ulid/selector, expected_kind)
- All resolution steps logged
- All workflow detection steps logged
- All RPC boundary conversions logged

## Examples

### Example 1: Slug Collision Detection

```
[RESOLVE_ID] Resolved by SLUG: 'bands' -> 01ABCDEFGHIJKLMNOPQRSTUVWX (kind=calculation, expected_kind=step, name=bands)
[RESOLVE_STEP] ERROR: Resource 'bands' resolved to kind='calculation', expected='step'.
```

This shows that slug "bands" resolved to a calculation, but we expected a step. The resolver should filter by `expected_kind="step"` to prevent this.

### Example 2: Missing Type Field

```
[WORKFLOW_DETECT] Processing step entry 1/3: step_id=01ABCDEFGHIJKLMNOPQRSTUVWX, type_in_entry=None
[WORKFLOW_DETECT] WARNING: Step entry has no type field! step_id=01ABCDEFGHIJKLMNOPQRSTUVWX, entry_keys=['step_id']
[WORKFLOW_DETECT] Resolved step by ULID: step_id=01ABCDEFGHIJKLMNOPQRSTUVWX -> step_type=scf (from step YAML)
```

This shows that `calculation.yaml.steps[]` entry is missing `type` field, so workflow detection falls back to reading step YAML file.

### Example 3: Non-ULID Step Identifier

```
[STEP_DETAIL_RPC] UI provided step identifier: 'bands' (is_ulid=False, len=5, expected_kind=step)
[STEP_DETAIL_RPC] WARNING: Step identifier is NOT a ULID! Value='bands', Type=string.
```

This shows that UI is passing slug "bands" instead of ULID. This may cause slug collision issues.

## Enabling Debug Logs

1. Open Settings panel
2. Expand "Diagnostics / Debug" section
3. Toggle "Enable resolution/addressing debug logs" to ON
4. Debug logs will appear in the daemon logs panel

## Disabling Debug Logs

1. Open Settings panel
2. Expand "Diagnostics / Debug" section
3. Toggle "Enable resolution/addressing debug logs" to OFF
4. Trace logs will stop, but warnings about correctness issues will still appear

## Technical Details

- Debug flag is stored in `.qmatsuite/config/settings.json` as `debug_resolution: true/false`
- Flag is checked via `qmatsuite.core.debug.is_resolution_debug_enabled()`
- Logs are gated at call sites (not by changing global logger level)
- Warnings about correctness issues are **not** gated (always visible)

