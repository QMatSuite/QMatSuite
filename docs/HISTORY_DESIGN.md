# Project History Design Document

## Overview

Project History is an append-only archive that captures the evolution of a QMatSuite project. It provides a "past tense" view of project state, complementing the "present tense" source of truth on disk.

## Core Invariants (DO NOT VIOLATE)

### 1. Present Tense vs History Separation
- **Present tense UI** (non-history pages) must NOT persist digests, plots, preset caches, or any derived artifacts.
- All derived artifacts must be computed on-the-fly from disk state.
- Only History is allowed to persist derived artifacts (run digests, pinned plots, snapshots).

### 2. History is Immutable
- Once an event is recorded, it is NEVER modified or deleted.
- Events are append-only to `events.jsonl`.
- Run revisions are written once and never updated after finalization.

### 3. Run Definition
- **Any** user action that invokes **any** engine (even a single step) creates exactly ONE run.
- Each run has a unique ULID (`run_id`).
- A run spans from engine start to engine completion (success or failure).

### 4. Automatic Digest Computation
- Digests are computed at the end of EVERY run (success OR failure).
- Each step type MUST provide a `digest()` method.
- Digests are resilient: missing fields → `status: "unknown"`, never crash.
- If Fermi energy is missing (insulator), return `status: "na"`.
- If output file is missing, return `status: "missing"`.

### 5. Pin-to-History Restrictions
- Pins are only allowed for steps in the **MOST RECENT** run.
- De-duplicated: `(run_id, step_id, analysis_kind)` is unique.
- Backend writes pin files; UI never writes directly.

### 6. Project-Wide Scope
- History is stored at project level: `project_root/.history/`
- Events cover all calculations in the project.
- Filtering by `calc_id` is supported for calc-specific views.

## Storage Layout

```
project_root/.history/
├── events.jsonl           # Append-only event log
└── runs/
    └── run_<ULID>/
        ├── run_revision.json    # Metadata + digests
        ├── snapshot.tar.zst     # Structure + YAML tree at run start
        └── pins/
            └── <step_id>/
                ├── <analysis_kind>.png
                └── <analysis_kind>.json
```

## Event Types

### `baseline`
First event when history is initialized for a project.
```json
{
  "event_type": "baseline",
  "project_id": "...",
  "structure_ids": [...],
  "calculation_ids": [...]
}
```

### `edit`
Semantic diff event recorded via YAML wrapper.
```json
{
  "event_type": "edit",
  "doc_type": "step|calc|project|structure",
  "doc_path": "relative/path.yaml",
  "changes": [
    {
      "op": "set|delete|create|replace",
      "path": "/parameters/SYSTEM/ecutwfc",
      "old_value": 30.0,
      "new_value": 40.0
    }
  ],
  "summary": "Changed ecutwfc from 30 to 40",
  "actor": "gui|cli|daemon"
}
```

### `run_started`
Recorded at the beginning of `CalculationRunner.run()`.
```json
{
  "event_type": "run_started",
  "run_id": "...",
  "calc_id": "...",
  "step_ids": ["step-001", "step-002"],
  "step_types": ["scf", "nscf"],
  "snapshot_path": "snapshot.tar.zst"
}
```

### `run_finished`
Recorded at the end of `CalculationRunner.run()`.
```json
{
  "event_type": "run_finished",
  "run_id": "...",
  "status": "success|failed|cancelled",
  "duration_seconds": 123.5,
  "step_count": 2,
  "success_count": 2,
  "failure_count": 0,
  "error_summary": null
}
```

### `pin_created`
Recorded when user pins analysis to history.
```json
{
  "event_type": "pin_created",
  "run_id": "...",
  "step_id": "...",
  "analysis_kind": "bands|dos|scf_convergence|...",
  "pin_path": "pins/step-001/bands.png"
}
```

## Run Revision Schema

`run_revision.json` contains:
- Metadata: `id`, `project_id`, `calc_id`, `calc_name`
- Timestamps: `created_at`, `started_at`, `finished_at`
- Status: `status`, `error_summary`
- Engine info: `engine`, `engine_version`, `engine_path`
- Intention: `step_ids`, `step_types`, `preset_options`
- Pseudo refs: `pseudo_refs` (element → {filename, sha256, sha_family})
- Digests: `step_digests`, `run_digest`

## Digest Schema

### DigestValue
```json
{
  "value": 42.5,
  "status": "ok|missing|unknown|na|error",
  "unit": "Ry|eV|s|...",
  "message": "Optional error/info message"
}
```

### StepDigest
- `step_id`, `step_type`, `step_name`, `status`
- `converged`, `total_energy`, `fermi_energy`
- `scf_iterations`, `scf_accuracy`
- `homo`, `lumo`, `band_gap`
- `n_bands`, `n_kpoints`
- `dos_energy_range`
- `n_relax_steps`, `final_forces_max`, `final_pressure`
- `wall_time`, `cpu_time`

### RunDigest
- `run_id`, `calc_id`, `status`
- `started_at`, `finished_at`, `duration_seconds`
- `step_count`, `success_count`, `failure_count`
- `converged`, `total_energy_ry`, `fermi_energy_ev`
- `step_digests` (array)

## Future Considerations

### Restore/Compare (Not Implemented Yet)
The history stores enough information to enable:
- Restore to any run snapshot (extract `snapshot.tar.zst`)
- Replay edit events to reconstruct intermediate states
- Compare digests between runs

### Schema Migration
If schema changes are needed:
- Add new fields with defaults
- Never remove or rename existing fields
- Version events if necessary (`schema_version` field)

## Implementation Notes

### Thread Safety
- `events.jsonl` uses file locking (`fcntl.LOCK_EX`) for concurrent writes.
- Atomic writes via temp file + rename for crash safety.

### Hook Points
1. **YAML I/O**: `save_yaml_doc()` in `core/yaml_io.py` records edit events.
2. **Runner**: `CalculationRunner.run()` creates run revisions and events.
3. **Pins**: `pin_analysis_to_history()` is the sole API for pinning.

### RPC Endpoints
- `get_project_history`: Timeline entries for notebook view
- `get_run_revision`: Detailed run info with digests
- `list_project_runs`: Run list with summaries
- `pin_analysis_to_history`: Create pin (backend validates restrictions)
- `can_pin_to_run`: Check if pinning is allowed
- `get_pin_data`: Retrieve pinned data

### GUI Integration
- **Sidebar**: "History" tab in navigation
- **HistoryPanel**: Notebook-style timeline view
- **Run cards**: Expandable with step digests
- **Edit events**: Compact inline entries
- **Pins**: Shown under associated runs

