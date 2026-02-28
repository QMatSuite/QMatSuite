# Engine Registry Spec — Discovery / Select / Verify

**Status**: Design spec (not yet implemented)
**Deferred item**: See `docs/plans/DEFERRED_ITEMS.md` item 11

---

## 1. Problem Statement

QMatSuite currently has a two-state engine model: a bundled binary OR a system binary, resolved at startup by `qe_resolver.py`. This has several limitations:

- No support for multiple installations of the same engine
- No persistence of MPI configuration per installation
- No explicit user selection — auto-detection silently picks one
- Silent fallback from MPI to serial causes undiagnosed performance regression
- No BYOE (Bring Your Own Engine) path for custom builds

## 2. Target Model

The registry is a **list of installations** with an **active pointer** per engine.

```yaml
engines:
  qe:
    installations:
      - id: "bundled-7.5"
        path: "~/.qmatsuite/engines/qe/q-e-qe-7.5/bin"
        source: bundled        # bundled | system | byoe
        version: "7.5"
        mpi: false
        discovered_at: "2026-02-20T..."
        verified_at: "2026-02-27T..."

      - id: "system-7.5-mpi"
        path: "/usr/local/bin"
        source: system
        version: "7.5"
        mpi: true
        mpi_command: "mpirun"
        default_cores: 4
        discovered_at: "2026-02-27T..."
        verified_at: "2026-02-27T..."

    active: "system-7.5-mpi"   # user's explicit choice
```

### Installation Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Unique identifier (auto-generated or user-supplied for BYOE) |
| `path` | str | Path to directory containing engine binaries |
| `source` | enum | `bundled` (shipped with QMatSuite), `system` (found in PATH/known locations), `byoe` (user-added) |
| `version` | str | Engine version string (extracted from binary) |
| `mpi` | bool | Whether the binary is linked against MPI |
| `mpi_command` | str? | MPI launcher command (e.g., "mpirun", "mpiexec", "srun") |
| `default_cores` | int? | Default MPI process count for this installation |
| `discovered_at` | str | ISO timestamp of first discovery |
| `verified_at` | str? | ISO timestamp of last successful verification |

## 3. Three Operations

### 3.1 Discovery (`engine discover`)

Scans for engine installations and populates the registry.

**Behavior:**
- Scans: bundled paths, system `PATH`, known common locations (`/opt/homebrew/bin`, `/usr/local/bin`, etc.)
- For each found binary: extracts version, detects MPI (check binary linking via `otool -L` / `ldd`), generates `id`
- **Append-only**: adds new installations, never removes or modifies existing entries
- **Never changes `active`** — discovery is purely informational
- Uses `path` as dedup key — if an installation with the same path already exists, skips it

**Triggers:**
- First run (empty registry) — automatic
- User-initiated: `qms engine discover`
- Suggested after verify failure

**Idempotent**: running twice produces the same result (dedup by path).

### 3.2 Select (`engine select <engine> <id>`)

Sets the `active` pointer for an engine.

**Behavior:**
- Sets `active` to point at the specified installation `id`
- Runs verify on the target before confirming
- If verify fails, does **not** change `active` — returns error

**This is the only operation that changes `active`.**

**BYOE path:**
```bash
qms engine add qe --path /custom/build/bin --id my-custom-build
qms engine select qe my-custom-build
```

The `add` subcommand appends an entry with `source: byoe`, then the user explicitly selects it.

**Initial active selection**: On first discovery (empty registry), the system auto-selects using priority: `bundled > system`. This is the **only** automatic active selection. After that, `active` only changes via explicit `select`.

### 3.3 Verify (`engine verify <engine>`)

Checks that the active installation is functional.

**Behavior:**
- Checks: path exists, binary is executable, runs a trivial test (e.g., `pw.x --version` or empty stdin with timeout)
- Updates `verified_at` timestamp on success
- **On failure: error with guidance, no automatic fallback**

**Failure message:**
```
Active QE 'system-7.5-mpi' at /usr/local/bin is not available.
Run `qms engine discover` then `qms engine select qe <id>`.
```

**Design rationale for no fallback:**
- Fallback from MPI to serial causes silent performance regression (12x slower)
- Fallback to different version may produce different numerical results
- User must make an explicit choice

**Does NOT delete failed entries** — the user may reinstall or fix the path.

**Triggers:**
- User-initiated: `qms engine verify qe`
- Auto before calculation run (lightweight check, cached for session)

## 4. MPI Configuration

MPI config lives **per-installation**:

| Field | Source | Description |
|-------|--------|-------------|
| `mpi` | Auto-detected | Whether binary is MPI-linked |
| `mpi_command` | User-configurable | MPI launcher (`mpirun`, `mpiexec`, `srun`) |
| `default_cores` | User-configurable | Default process count |

### Priority Chain (highest to lowest)

1. **Environment variables**: `QMS_MPI_COMMAND`, `QMS_MPI_CORES` — override everything at runtime
2. **Installation config**: `mpi_command`, `default_cores` from the active installation entry
3. **Default**: serial execution (no MPI)

Environment variables are the escape hatch for one-off overrides without modifying the registry. They also serve as the **current workaround** before this spec is implemented.

## 5. Scope

All engines follow the same model:

| Engine | Binary to detect | Version extraction | MPI detection |
|--------|-----------------|-------------------|---------------|
| QE | `pw.x` | `pw.x --version` or startup banner | `otool -L` / `ldd` for libmpi |
| VASP | `vasp_std` | startup banner | `otool -L` / `ldd` for libmpi |
| ORCA | `orca` | `orca --version` or startup banner | `otool -L` / `ldd` for libmpi |
| CP2K | `cp2k.psmp` / `cp2k.sopt` | `cp2k --version` | Binary suffix (`.psmp` = MPI+OMP, `.sopt` = serial) |
| LAMMPS | `lmp` / `lmp_mpi` | `lmp -h` | Binary suffix or `ldd` |
| ABINIT | `abinit` | `abinit --version` | `otool -L` / `ldd` |
| Siesta | `siesta` | startup banner | `otool -L` / `ldd` |
| Gaussian | `g16` / `g09` | startup banner | N/A (uses Linda, not MPI) |
| GPAW | Python module | `gpaw --version` | `gpaw-python` vs `python` |
| xTB | `xtb` | `xtb --version` | N/A (serial only) |
| Psi4 | Python module | `psi4 --version` | N/A (internal threading) |
| PySCF | Python module | `pyscf.__version__` | N/A (internal threading) |
| QMCPACK | `qmcpack` | startup banner | `otool -L` / `ldd` |
| Yambo | `yambo` | `yambo -h` | `otool -L` / `ldd` |
| Wannier90 | `wannier90.x` | startup banner | `otool -L` / `ldd` |

## 6. Key Design Rules

1. **Discovery is append-only, never changes active.** Users may have carefully selected an installation; discovery must not silently override it.

2. **Select is the only way to change active.** One operation, one responsibility.

3. **Verify never falls back.** A broken active installation is an error, not an opportunity for auto-switching. The user must be aware of what engine they're running.

4. **Disappearance is not deletion.** If a binary disappears (uninstalled, path changed), verify fails but the registry entry stays. The user might reinstall it.

5. **Environment variables override everything.** `QMS_MPI_COMMAND` and `QMS_MPI_CORES` are the highest-priority knobs. This is the current workaround and remains useful for HPC job scripts.

6. **One registry file, all engines.** Stored at `~/.qmatsuite/engines.yaml` (or `engines.json`). No per-engine config fragmentation.

## 7. Migration Path

**Current state** (pre-implementation):
- `qe_resolver.py` handles QE-specific two-state resolution
- `EngineConfig` dataclass holds `mpi_command` / `mpi_cores`
- Environment variables `QMS_MPI_COMMAND` / `QMS_MPI_CORES` provide runtime override (implemented separately)

**Implementation order:**
1. Implement `engines.yaml` schema + read/write
2. Implement `discover` for QE (proof of concept)
3. Implement `select` + `verify` for QE
4. Migrate `qe_resolver.py` to use new registry
5. Extend to other engines
6. Add CLI commands (`qms engine discover/select/verify`)
7. Add MCP tools (`discover_engines`, `select_engine`, `verify_engine`)
