# QuantumVITAS Daemon API Reference

> A stdio JSON-RPC daemon for GUI integration.

## Overview

The QuantumVITAS daemon (`qv-daemon`) provides a JSON-RPC interface over stdin/stdout for GUI applications (e.g., Electron). It calls `QVService` internally, never CLI commands.

### Starting the Daemon

```bash
# As a module
python -m quantumvitas.daemon.server

# Or in Python
from quantumvitas.daemon import QVDaemon
daemon = QVDaemon()
daemon.run()
```

### Protocol

- **Requests**: One JSON object per line to stdin
- **Responses**: One JSON object per line to stdout
- **Logging**: Goes to stderr (never pollutes stdout)

## Request/Response Format

### Request

```json
{
  "id": "unique-request-id",
  "type": "command_name",
  "payload": {
    "param1": "value1",
    "param2": "value2"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique request identifier (returned in response) |
| `type` | string | Yes | Command name |
| `payload` | object | No | Command parameters (default: `{}`) |

### Successful Response

```json
{
  "id": "unique-request-id",
  "ok": true,
  "data": {
    "key": "value"
  }
}
```

### Error Response

```json
{
  "id": "unique-request-id",
  "ok": false,
  "error": {
    "code": "error_code",
    "message": "Human-readable error message"
  }
}
```

### Error Codes

| Code | Description |
|------|-------------|
| `parse_error` | Invalid JSON in request |
| `invalid_request` | Missing required fields (e.g., `type`) |
| `unknown_command` | Command not found |
| `service_error` | Error from QVService |
| `not_found` | File or resource not found |
| `invalid_argument` | Invalid parameter value |
| `handler_error` | Unexpected error in handler |

---

## Commands

### System Commands

#### `ping`

Test daemon connectivity.

**Payload**: None required

**Response**:
```json
{
  "pong": true,
  "version": "2.0.0"
}
```

#### `shutdown`

Gracefully stop the daemon.

**Payload**: None required

**Response**:
```json
{
  "shutdown": true
}
```

---

### Project/Resource Commands

#### `get_project_summary`

Get high-level project information.

**Payload**:
```json
{
  "project_root": "/path/to/project"
}
```

**Response**:
```json
{
  "id": "01ABC123...",
  "name": "my-project",
  "slug": "my-project",
  "path": "/path/to/project",
  "n_structures": 2,
  "n_workflows": 3,
  "structure_names": ["si", "ge"],
  "calculation_names": ["scf", "dos", "bands"]
}
```

#### `list_structures`

List all structures in a project.

**Payload**:
```json
{
  "project_root": "/path/to/project"
}
```

**Response**:
```json
{
  "count": 2,
  "structures": [
    {
      "id": "01ABC...",
      "name": "si",
      "slug": "si",
      "path": "structures/si.json",
      "absolute_path": "/path/to/project/structures/si.json",
      "formula": "Si2",
      "n_atoms": 2,
      "n_species": 1,
      "lattice_params": {
        "a": 3.86,
        "b": 3.86,
        "c": 3.86,
        "alpha": 60.0,
        "beta": 60.0,
        "gamma": 60.0,
        "volume": 40.89
      }
    }
  ]
}
```

#### `list_calculations`

List all calculations in a project.

**Payload**:
```json
{
  "project_root": "/path/to/project"
}
```

**Response**:
```json
{
  "count": 1,
  "calculations": [
    {
      "id": "01ABC...",
      "name": "si-dos",
      "slug": "si-dos",
      "path": "calculations/si-dos",
      "absolute_path": "/path/to/project/calculations/si-dos",
      "structure": "si",
      "mode": "normal",
      "n_steps": 3,
      "steps": [
        {"id": "scf", "type": "scf", "step_file": "steps/scf.step.yaml"},
        {"id": "nscf", "type": "nscf", "step_file": "steps/nscf.step.yaml"},
        {"id": "dos", "type": "dos", "step_file": "steps/dos.step.yaml"}
      ]
    }
  ]
}
```

#### `get_calculation_detail`

Get detailed information about a calculation, including structure elements and species map.

**Payload**:
```json
{
  "project_root": "/path/to/project",
  "calculation": "si-bands"
}
```

**Response**:
```json
{
  "id": "01ABC...",
  "name": "si-bands",
  "slug": "si-bands",
  "path": "calculations/si-bands",
  "absolute_path": "/path/to/project/calculations/si-bands",
  "structure": "si",
  "structure_id": "01SABC123...",
  "structure_elements": ["Si"],
  "mode": "normal",
  "n_steps": 3,
  "steps": [
    {"id": "01TXYZ789...", "slug": "scf", "name": "scf", "type": "scf", "step_file": "steps/scf.step.yaml", "missing": false},
    {"id": "01TUVW456...", "slug": "nscf", "name": "nscf", "type": "nscf", "step_file": "steps/nscf.step.yaml", "missing": false}
  ],
  "species_map": {
    "Si": {
      "pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
      "mass": 28.0855
    }
  }
}
```

**Key fields**:
- `structure_elements`: List of element symbols from the calculation's structure composition (for UI rendering)
- `species_map`: Calculation-level pseudopotential mapping (authoritative source)
- `steps`: Array of step summaries with ULID, metadata, and type

---

### Visualization Data Commands

These commands return pure data (no matplotlib objects) suitable for GUI rendering.

#### `get_structure_vis`

Get structure visualization data for 3D rendering.

**Payload**:
```json
{
  "project_root": "/path/to/project",
  "selector": "si",
  "supercell": [1, 1, 1],
  "repeat_boundary": false
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_root` | string | Yes | Path to project |
| `selector` | string | Yes | Structure name/slug/path |
| `supercell` | [int, int, int] | No | Supercell expansion (default: [1,1,1]) |
| `repeat_boundary` | bool | No | Show periodic images at boundaries (default: false) |

**Response**:
```json
{
  "structure_id": "01ABC...",
  "structure_name": "si",
  "formula": "Si2",
  "n_atoms": 2,
  "n_boundary_atoms": 0,
  "n_bonds": 4,
  "supercell": [1, 1, 1],
  "lattice": {
    "matrix": [[3.86, 0, 0], [0, 3.86, 0], [0, 0, 3.86]],
    "a": 3.86,
    "b": 3.86,
    "c": 3.86,
    "alpha": 90.0,
    "beta": 90.0,
    "gamma": 90.0,
    "volume": 57.5
  },
  "atoms": [
    {
      "index": 0,
      "element": "Si",
      "cart_coords": [0.0, 0.0, 0.0],
      "frac_coords": [0.0, 0.0, 0.0],
      "color": "#F0C8A0",
      "radius": 1.11
    }
  ],
  "boundary_atoms": [],
  "bonds": [
    {
      "idx1": 0,
      "idx2": 1,
      "coord1": [0.0, 0.0, 0.0],
      "coord2": [0.96, 0.96, 0.96],
      "distance": 2.36
    }
  ],
  "element_colors": {"Si": "#F0C8A0", "C": "#333333", ...}
}
```

#### `get_scf_convergence`

Get SCF convergence data for plotting.

**Payload**:
```json
{
  "project_root": "/path/to/project",
  "calculation": "si-scf",
  "step": "scf"
}
```

**Response**:
```json
{
  "calculation": "si-scf",
  "step": "scf",
  "output_file": "/path/to/raw/si.scf.out",
  "converged": true,
  "n_iterations": 7,
  "total_energy_ry": -15.85,
  "fermi_energy_ev": 6.45,
  "iterations": [
    {"iteration": 1, "total_energy_ry": -15.80, "scf_accuracy_ry": 1e-3},
    {"iteration": 2, "total_energy_ry": -15.84, "scf_accuracy_ry": 1e-5}
  ],
  "calculation_type": "scf",
  "n_electrons": 8.0,
  "n_kpoints": 10,
  "ecutwfc_ry": 40.0,
  "units": {"energy": "Ry", "fermi": "eV"}
}
```

#### `get_dos_data`

Get DOS data for plotting.

**Payload**:
```json
{
  "project_root": "/path/to/project",
  "calculation": "si-dos",
  "step": "dos"
}
```

**Response**:
```json
{
  "calculation": "si-dos",
  "step": "dos",
  "data_file": "/path/to/raw/si.dos.dat",
  "n_points": 1001,
  "fermi_energy_ev": 6.45,
  "energy_range_ev": [-10.0, 20.0],
  "energies_ev": [-10.0, -9.97, ...],
  "dos_states_per_ev": [0.0, 0.001, ...],
  "idos": [0.0, 0.0003, ...],
  "units": {"energy": "eV", "dos": "states/eV"}
}
```

#### `get_band_structure_data`

Get band structure data for plotting.

**Payload**:
```json
{
  "project_root": "/path/to/project",
  "calculation": "si-bands",
  "step": "bands"
}
```

**Response**:
```json
{
  "calculation": "si-bands",
  "step": "bands",
  "data_file": "/path/to/raw/si.bands.dat.gnu",
  "n_bands": 8,
  "n_kpoints": 91,
  "fermi_energy_ev": 6.45,
  "k_distances": [0.0, 0.05, 0.1, ...],
  "energies_ev": [
    [-5.2, -5.1, ...],
    [-2.3, -2.2, ...]
  ],
  "high_symmetry_points": [
    {"label": "Γ", "k_distance": 0.0, "k_coords": [0.0, 0.0, 0.0]},
    {"label": "X", "k_distance": 0.87, "k_coords": [0.5, 0.0, 0.5]}
  ],
  "units": {"energy": "eV", "k_distance": "2π/a"}
}
```

---

### Job Management Commands

Long-running operations (calculation/step execution) are submitted as background jobs.

#### `run_calculation`

Submit a calculation for background execution.

**Payload**:
```json
{
  "project_root": "/path/to/project",
  "calculation": "si-bands",
  "strict": false,
  "verbose": false
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_root` | string | Yes | Path to project |
| `calculation` | string | Yes | Calculation selector |
| `strict` | bool | No | Fail on first error (default: false) |
| `verbose` | bool | No | Verbose output (default: false) |

**Response**:
```json
{
  "job_id": "abc-123-def",
  "status": "pending"
}
```

#### `run_step`

Submit a single step for background execution.

**Payload**:
```json
{
  "project_root": "/path/to/project",
  "calculation": "si-bands",
  "step": "scf",
  "verbose": false
}
```

**Response**:
```json
{
  "job_id": "xyz-789-ghi",
  "status": "pending"
}
```

#### `get_job_status`

Get the current status of a job.

**Payload**:
```json
{
  "job_id": "abc-123-def"
}
```

**Response**:
```json
{
  "id": "abc-123-def",
  "job_type": "run_calculation",
  "status": "completed",
  "created_at": "2025-12-05T10:00:00+00:00",
  "started_at": "2025-12-05T10:00:01+00:00",
  "completed_at": "2025-12-05T10:05:30+00:00",
  "result": {
    "calculation": "si-bands",
    "steps": 4,
    "results": [...]
  },
  "error": null,
  "params": {
    "project_root": "/path/to/project",
    "calculation": "si-bands"
  },
  "io_dir": "/path/to/project/calculations/si-bands/raw",
  "steps": [
    {
      "step_id": "01TXYZ789...",
      "step_type": "scf",
      "status": "completed",
      "started_at": "2025-12-05T10:00:10+00:00",
      "ended_at": "2025-12-05T10:02:30+00:00"
    }
  ]
}
```

**Fields**:
- `io_dir`: Absolute path to the I/O directory (the actual directory used by the runner to write QE input/output and artifacts). Available immediately when the job is created (pending state), computed using the same logic as the runner (single source of truth via `compute_io_dir_from_workflow_model()`).
- `steps`: Array of step progress information (available for calculation jobs, initialized at job creation with pending status, updated during execution).

**Job Status Values**:

| Status | Description |
|--------|-------------|
| `pending` | Job queued, waiting to start |
| `running` | Job currently executing |
| `completed` | Job finished successfully |
| `failed` | Job failed with error |
| `cancelled` | Job was cancelled (only from pending) |

#### `list_jobs`

List all jobs, optionally filtered.

**Payload**:
```json
{
  "status": "running",
  "job_type": "run_calculation"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `status` | string | No | Filter by status |
| `job_type` | string | No | Filter by job type |

**Response**:
```json
{
  "count": 2,
  "jobs": [
    {"id": "abc-123", "job_type": "run_calculation", "status": "running", ...},
    {"id": "def-456", "job_type": "run_calculation", "status": "pending", ...}
  ]
}
```

#### `cancel_job`

Attempt to cancel a job.

**Important**: Only `pending` jobs can be cancelled. Running jobs cannot be interrupted - they will complete. This is a limitation of Python's ThreadPoolExecutor.

**Payload**:
```json
{
  "job_id": "abc-123-def"
}
```

**Response**:
```json
{
  "job_id": "abc-123-def",
  "cancelled": true
}
```

---

## Example Session

```
→ {"id": "1", "type": "ping", "payload": {}}
← {"id": "1", "ok": true, "data": {"pong": true, "version": "2.0.0"}}

→ {"id": "2", "type": "get_project_summary", "payload": {"project_root": "/home/user/si_project"}}
← {"id": "2", "ok": true, "data": {"name": "si_project", "n_workflows": 2, ...}}

→ {"id": "3", "type": "run_calculation", "payload": {"project_root": "/home/user/si_project", "calculation": "bands"}}
← {"id": "3", "ok": true, "data": {"job_id": "abc-123", "status": "pending"}}

→ {"id": "4", "type": "get_job_status", "payload": {"job_id": "abc-123"}}
← {"id": "4", "ok": true, "data": {"id": "abc-123", "status": "running", ...}}

→ {"id": "5", "type": "get_job_status", "payload": {"job_id": "abc-123"}}
← {"id": "5", "ok": true, "data": {"id": "abc-123", "status": "completed", "result": {...}}}

→ {"id": "6", "type": "get_band_structure_data", "payload": {"project_root": "/home/user/si_project", "calculation": "bands"}}
← {"id": "6", "ok": true, "data": {"n_bands": 8, "energies_ev": [...], ...}}

→ {"id": "7", "type": "shutdown", "payload": {}}
← {"id": "7", "ok": true, "data": {"shutdown": true}}
```

---

## Pseudopotential Management

### `get_calculation_pseudo_mapping`

Get pseudopotential mapping for a calculation (authoritative source). This is the preferred method for accessing pseudopotential mappings, as they are stored at the calculation level.

**Payload**:
```json
{
  "project_root": "/path/to/project",
  "calculation": "si-bands"
}
```

**Response**:
```json
{
  "species": ["Si"],
  "mapping": {"Si": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"},
  "species_map": {
    "Si": {
      "pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
      "mass": 28.0855
    }
  },
  "pseudo_dir": "../pseudo",
  "available_pseudos": ["Si.pbe-n-rrkjus_psl.1.0.0.UPF", "Si.pz-vbc.UPF"],
  "warnings": [],
  "library_preference": "precision",
  "sssp_defaults": {
    "Si": {
      "precision": "Si.pbe-n-kjpaw_psl.1.0.0.UPF",
      "efficiency": "Si.pbe-n-kjpaw_psl.1.0.0.UPF"
    }
  },
  "sssp_installed": {
    "precision": true,
    "efficiency": true
  }
}
```

### `update_calculation_species_map`

Update pseudopotential mapping for a calculation (authoritative source). This is the preferred method for updating pseudopotential mappings.

**Payload**:
```json
{
  "project_root": "/path/to/project",
  "calculation": "si-bands",
  "species_map": {
    "Si": {
      "pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
      "mass": 28.0855
    }
  }
}
```

**Response**: Updated calculation detail (same as `get_calculation_detail`), with additional `old_species_map` field

### `get_pseudo_mapping` (Legacy)

⚠️ **Deprecated**: Use `get_calculation_pseudo_mapping` instead. This command is kept for backwards compatibility with old step-level pseudo mappings.

Get pseudopotential mapping for a step (legacy method).

**Payload**:
```json
{
  "project_root": "/path/to/project",
  "calculation": "si-bands",
  "step": "scf"
}
```

**Response**: Same format as `get_calculation_pseudo_mapping`, but reads from step-level `species_overrides` if present (legacy)

### `set_pseudo_mapping` (Legacy)

⚠️ **Deprecated**: Use `update_calculation_species_map` instead. This command is kept for backwards compatibility.

Update pseudopotential mapping for a step (legacy method).

**Payload**:
```json
{
  "project_root": "/path/to/project",
  "calculation": "si-bands",
  "step": "scf",
  "mapping": {"Si": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"},
  "library_preference": "precision"
}
```

**Response**: Updated step detail (same as `get_step_detail`)

### `import_pseudo_files`

Import pseudopotential files into the project pseudo directory.

**Payload**:
```json
{
  "project_root": "/path/to/project",
  "file_paths": ["/path/to/Si.UPF", "/path/to/C.UPF"]
}
```

**Response**:
```json
{
  "imported": ["Si.UPF", "C.UPF"],
  "renamed": {"Si.UPF": "Si_1.UPF"},
  "skipped": ["C.UPF (identical to existing C.UPF)"],
  "errors": []
}
```

**Note**: Files are deduplicated by SHA256. If a file with the same content already exists, it is skipped. If filename conflicts but content differs, files are renamed deterministically (`_1`, `_2`, etc.).

### `search_legacy_pseudos`

Search for pseudopotentials by element using QE legacy tables.

**Payload**:
```json
{
  "element": "Si",
  "project_root": "/path/to/project"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `element` | string | Yes | Element symbol (e.g., "Si", "Mo") |
| `project_root` | string | No | Project root (for config) |

**Response**:
```json
{
  "candidates": [
    {
      "filename": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
      "url": "https://pseudopotentials.quantum-espresso.org/upf_files/Si.pbe-n-rrkjus_psl.1.0.0.UPF",
      "element": "Si",
      "xc": "pbe"
    }
  ],
  "errors": []
}
```

**URL Pattern**: 
- Element page: `https://pseudopotentials.quantum-espresso.org/legacy_tables/ps-library/{element_lowercase}`
- Download URL: `https://pseudopotentials.quantum-espresso.org/upf_files/{filename}`

### `download_pseudo_by_filename`

Download a pseudopotential by filename from QE network repository.

**Payload**:
```json
{
  "project_root": "/path/to/project",
  "filename": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
  "dest_dir": "/path/to/project/pseudo"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_root` | string | Yes | Path to project root |
| `filename` | string | Yes | Exact UPF filename |
| `dest_dir` | string | No | Destination directory (default: `project_root/pseudo`) |

**Response**:
```json
{
  "filename": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
  "renamed": false,
  "skipped": false,
  "errors": []
}
```

**Note**: Files are deduplicated by SHA256. If a file with the same content already exists, `skipped` is `true` and `filename` is the existing filename. If filename conflicts but content differs, `renamed` is `true` and `filename` is the new name.

### `download_pseudo_candidate`

Download a pseudopotential from a candidate (URL or filename).

**Payload**:
```json
{
  "project_root": "/path/to/project",
  "candidate": {
    "filename": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
    "url": "https://pseudopotentials.quantum-espresso.org/upf_files/Si.pbe-n-rrkjus_psl.1.0.0.UPF"
  },
  "dest_dir": "/path/to/project/pseudo"
}
```

**Response**: Same as `download_pseudo_by_filename`

**Note**: If `candidate` has `url`, downloads from that URL. If only `filename` is provided, uses `download_pseudo_by_filename` logic.

---

## Architectural Notes

### Daemon Design Principles

1. **No CLI dependency**: Daemon calls `QVService`, never CLI commands or subprocesses
2. **No cwd dependency**: All paths come from request payloads
3. **Pure JSON over stdio**: One request/response per line
4. **Never crashes**: All exceptions become error responses
5. **Sequential QE execution**: `ThreadPoolExecutor(max_workers=1)`
6. **Results in memory, data on disk**: Job status is in-memory; project files on disk

### JSON Serializability

All responses contain only JSON-serializable types:
- `dict`, `list`, `str`, `int`, `float`, `bool`, `None`

No leaking of:
- numpy arrays (converted via `.tolist()`)
- pathlib objects (converted via `str()`)
- dataclasses (use `.to_dict()`)
- matplotlib objects

### Error Handling

The daemon never crashes. All exceptions are caught and returned as error responses:

```python
try:
    result = handler(payload)
    return {"ok": True, "data": result}
except QVServiceError as e:
    return {"ok": False, "error": {"code": "service_error", "message": str(e)}}
except Exception as e:
    return {"ok": False, "error": {"code": "handler_error", "message": str(e)}}
```

---

## Python API

For direct Python usage (e.g., in tests):

```python
from quantumvitas.daemon import QVDaemon
from quantumvitas.daemon.server import RPCRequest

# Create daemon
daemon = QVDaemon()

# Send request directly (no stdin/stdout)
response = daemon.handle_request(RPCRequest(
    id="1",
    type="ping",
    payload={},
))

if response.ok:
    print(response.data)  # {"pong": True, "version": "2.0.0"}
else:
    print(response.error)  # {"code": "...", "message": "..."}
```

### JobManager Direct Usage

```python
from quantumvitas.daemon.jobs import JobManager, JobStatus

manager = JobManager(max_workers=1)

# Submit job
job_id = manager.submit(
    job_type="run_calculation",
    func=my_function,
    params={"calculation": "si-bands"},
    project_root=project_root,
)

# Check status
status = manager.get_job_status(job_id)
print(status["status"])  # "pending", "running", "completed", "failed"

# List jobs
jobs = manager.list_jobs(status=JobStatus.RUNNING)

# Cleanup
manager.shutdown(wait=True)
```

