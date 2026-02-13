# AiiDA Storage & Provenance: Concept → Implementation Technical Memo

**Date:** 2026-01-27
**Purpose:** Deep technical analysis of AiiDA's storage and provenance implementation for QMatSuite Level-2 provenance design

---

## Executive Summary

AiiDA implements a **dual-storage architecture** that cleanly separates:
1. **Searchable metadata** → PostgreSQL/SQLite database (JSONB attributes, links, indexes)
2. **Binary files** → Content-addressed disk-object-store (SHA-256 dedup, compression)

The provenance graph is stored as a **link table** connecting immutable nodes. Files are retrieved from remote clusters using a **plugin-defined retrieve_list**, and only selected outputs are persisted—everything else remains on remote as `RemoteData` references.

---

## A) AiiDA's "Data / Process" Node Model

### Node Class Hierarchy

```
Node (base)
├── Data (storable, results/artifacts)
│   ├── FolderData          - directory of files in repository
│   ├── SinglefileData      - single file
│   ├── RemoteData          - reference to remote path (metadata only)
│   ├── Dict                - JSON-serializable dictionary
│   ├── ArrayData           - NumPy arrays (stored as .npy files)
│   ├── StructureData       - atomic structure
│   ├── BandsData, KpointsData, TrajectoryData...
│   └── Code, UpfData...
│
└── ProcessNode (execution records)
    ├── CalculationNode
    │   ├── CalcJobNode     - batch job execution
    │   └── CalcFunctionNode - Python function
    └── WorkflowNode
        ├── WorkChainNode   - multi-step workflow
        └── WorkFunctionNode
```

**Key files:**
- `aiida/orm/nodes/node.py:145` — Base `Node` class
- `aiida/orm/nodes/data/data.py:24` — `Data` base class
- `aiida/orm/nodes/process/calculation/calcjob.py:51` — `CalcJobNode`

### Link Types and Provenance Semantics

| LinkType | Direction | Meaning |
|----------|-----------|---------|
| `INPUT_CALC` | Data → Calculation | Data consumed by calculation |
| `INPUT_WORK` | Data → Workflow | Data consumed by workflow |
| `CREATE` | Calculation → Data | Data produced by calculation |
| `RETURN` | Workflow → Data | Data explicitly returned by workflow |
| `CALL_CALC` | Workflow → Calculation | Workflow spawned calculation |
| `CALL_WORK` | Workflow → Workflow | Workflow spawned sub-workflow |

**Key file:** `aiida/common/links.py:19` — `LinkType` enum with constraint definitions

### Database Tables for Provenance

**`db_dbnode`** (nodes):
```sql
id, uuid, node_type, process_type, label, description,
ctime, mtime,
attributes (JSONB),      -- immutable after storage
extras (JSONB),          -- mutable
repository_metadata (JSONB),  -- virtual file hierarchy → CAS keys
dbcomputer_id, user_id
```

**`db_dblink`** (edges):
```sql
id, input_id, output_id, type, label
-- input_id = source node, output_id = target node
```

**Key files:**
- `aiida/storage/psql_dos/models/node.py` — `DbNode`, `DbLink` SQLAlchemy models
- `aiida/storage/psql_dos/orm/querybuilder/` — Graph query implementation

### Query Paths

Typical provenance queries use the `QueryBuilder`:

```python
# Find all outputs of a CalcJobNode
qb = QueryBuilder()
qb.append(CalcJobNode, filters={'id': node_pk}, tag='calc')
qb.append(Data, with_incoming='calc', edge_filters={'type': 'create'})
results = qb.all()

# Recursive ancestor traversal (uses PostgreSQL CTEs)
qb.append(Node, filters={'id': pk})
qb.append(Node, with_descendants='calc')  # recursive CTE
```

---

## B) File Storage Model: DB vs Repository vs Remote

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AiiDA Storage                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────┐    ┌─────────────────────────────────┐│
│  │   PostgreSQL/SQLite     │    │   Disk-Object-Store (CAS)       ││
│  │   (Searchable Metadata) │    │   (Binary Files)                ││
│  ├─────────────────────────┤    ├─────────────────────────────────┤│
│  │ • Node attributes (JSONB)│   │ • Content-addressed files       ││
│  │ • Node links (graph)    │    │ • SHA-256 keys                  ││
│  │ • repository_metadata   │◄──►│ • Automatic deduplication       ││
│  │   (path → key mapping)  │    │ • zlib compression              ││
│  │ • Timestamps, labels    │    │ • Pack files (4GB targets)      ││
│  │ • Process state         │    │                                 ││
│  └─────────────────────────┘    └─────────────────────────────────┘│
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Retrieval (copy at job end)
                              │
┌─────────────────────────────────────────────────────────────────────┐
│                     Remote Working Directory                        │
│                     (Scratch / Ephemeral)                           │
├─────────────────────────────────────────────────────────────────────┤
│  /remote/workdir/{uuid[:2]}/{uuid[2:4]}/{uuid[4:]}                 │
│  ├── input files (uploaded)                                        │
│  ├── output files (created by job)                                 │
│  │   ├── Files in retrieve_list      → copied to FolderData repo  │
│  │   ├── Files in retrieve_temporary → parsed, then DELETED        │
│  │   └── All other files             → ABANDONED (not persisted)   │
│  └── Referenced via RemoteData node (metadata pointer)             │
└─────────────────────────────────────────────────────────────────────┘
```

### What Goes Where

| Data Type | Storage Location | How Stored |
|-----------|------------------|------------|
| Node attributes | DB `attributes` column | JSONB, immutable |
| Node extras | DB `extras` column | JSONB, mutable |
| File hierarchy | DB `repository_metadata` | JSONB: `{path → sha256_key}` |
| File content | Disk-object-store | Content-addressed by SHA-256 |
| Provenance links | DB `db_dblink` table | Foreign keys |
| Remote reference | `RemoteData.remote_path` attribute | Just a path string |

### Repository Metadata Serialization

The `repository_metadata` JSONB column stores a virtual file tree:

```json
{
  "o": {
    "aiida.in": {"k": "abc123..."},
    "results": {
      "o": {
        "output.dat": {"k": "def456..."},
        "subdir": {"o": {}}
      }
    }
  }
}
```

**Key files:**
- `aiida/repository/repository.py:77` — `serialize()` method
- `aiida/repository/common.py:24` — `File` class with `{'k': key}` format
- `aiida/orm/nodes/repository.py:104` — `_store()` clones sandbox → permanent

### Storage Flow (Node Store)

```
1. Node created (unstored)
   └── Files written to SandboxRepositoryBackend (temp directory)

2. node.store() called
   ├── _validate_storability()
   ├── _verify_are_parents_stored()
   ├── base.caching._get_same_node()  → check cache (optional)
   ├── base.repository._store():
   │   ├── Clone sandbox files → DiskObjectStoreBackend
   │   │   └── container.add_streamed_object(handle) → returns SHA-256 key
   │   └── Update repository_metadata JSONB
   ├── _backend_entity.store(links)   → INSERT to db_dbnode + db_dblink
   └── base.caching.rehash()

3. Node stored
   └── Immutable: attributes, repository cannot change
```

**Key file:** `aiida/orm/nodes/node.py:592` — `_store()` method

---

## C) Content-Addressed Storage (CAS) and Deduplication

### Implementation: `disk-objectstore` Library

AiiDA uses the external `disk-objectstore` package for CAS:

```python
# aiida/repository/backend/disk_object_store.py:83
def _put_object_from_filelike(self, handle: BinaryIO) -> str:
    with self._container as container:
        return container.add_streamed_object(handle)  # returns SHA-256
```

**Dedup mechanism:**
1. File content is hashed (SHA-256)
2. Hash becomes the storage key
3. If key already exists, no new storage (automatic dedup)
4. Multiple nodes can reference the same key

### Container Configuration

```python
# Default settings
pack_size_target: 4GB    # Pack loose files when target exceeded
loose_prefix_len: 2      # Sharding: loose/ab/cd/full_hash
hash_type: 'sha256'
compression_algorithm: 'zlib+1'
```

### Maintenance Operations

```python
backend.maintain(
    pack_loose=True,      # Pack small loose files into pack files
    do_repack=False,      # Repack existing pack files (offline only)
    clean_storage=True,   # Remove soft-deleted objects
    do_vacuum=False,      # Vacuum sqlite index (offline only)
    compress=True,        # Enable compression
)
```

**Key file:** `aiida/repository/backend/disk_object_store.py:148` — `maintain()` method

### Soft Delete Behavior

Files are **not immediately deleted** from the backend:
- `Repository.delete_object()` removes from virtual hierarchy
- Actual backend object persists (may be referenced elsewhere)
- `clean_storage=True` in maintenance removes orphaned objects

---

## D) How AiiDA Knows Which Files to Retrieve

### CalcInfo: The Plugin Contract

Plugins define retrieval via `CalcInfo` returned from `prepare_for_submission()`:

```python
# aiida/common/datastructures.py
class CalcInfo:
    retrieve_list: List[...]           # Permanent: copied to FolderData
    retrieve_temporary_list: List[...] # Temp: parser only, then deleted
    local_copy_list: List[...]         # Input files from local nodes
    remote_copy_list: List[...]        # Input files already on remote
    provenance_exclude_list: List[...] # Don't store these inputs
```

### Retrieve List Patterns

```python
retrieve_list = [
    'output.txt',                           # Simple filename (basename only)
    ('path/to/file', '.', 1),              # (source, dest, depth)
    ('outputs/*.dat', 'data', 2),          # Glob with depth control
    ('deep/nested/*/file.h5', '.', None),  # Full path preserved
]
```

**Depth semantics:**
- `None`: preserve full relative path
- `1`: keep only basename
- `2`: keep last 2 path components
- etc.

### Retrieval Implementation

```python
# aiida/engine/daemon/execmanager.py (simplified)
async def retrieve_calculation(node, transport, temp_folder):
    retrieve_list = node.get_retrieve_list()

    # Stage 1: Permanent files
    with SandboxFolder() as sandbox:
        for item in retrieve_list:
            # Expand globs, apply depth rules
            await transport.get_async(remote_path, local_path)

        # Store in FolderData repository
        retrieved = FolderData()
        retrieved.base.repository.put_object_from_tree(sandbox.abspath)
        retrieved.store()

    # Stage 2: Temporary files (for parsing)
    for item in retrieve_temporary_list:
        await transport.get_async(remote_path, temp_folder)

    return retrieved  # CREATE link to CalcJobNode
```

**Key file:** `aiida/engine/daemon/execmanager.py:70` — `upload_calculation()`, `retrieve_calculation()`

### Handling Intermediate/Overwritten Files

AiiDA takes an **end-of-run snapshot**:
- No incremental tracking during job execution
- `retrieve_list` patterns matched after job completes
- Globs expand to whatever files exist at retrieval time
- Plugin must design retrieve patterns for "final" state

---

## E) QE-Specific Behavior in `aiida-quantumespresso`

### PwCalculation Retrieve Strategy

**File:** `aiida_quantumespresso/calculations/pw.py`

```python
# Permanent retrieval (stored in FolderData)
calcinfo.retrieve_list = [
    'aiida.out',                                    # stdout
    'CRASH',                                        # error file
    './out/aiida.save/data-file-schema.xml',       # parsed for results
]

# Temporary retrieval (parsed, then deleted)
calcinfo.retrieve_temporary_list = [
    './out/aiida.save/K*[0-9]/eigenval*.xml',      # band eigenvalues
]
```

### Wavefunction Handling

**Wavefunctions are NEVER retrieved** to local storage:
- `evc.dat` files (GB-scale) stay on remote
- `RemoteData` node points to remote `./out/` directory
- Restart calculations use `parent_folder` input (symlink to remote)

```python
# When user sets parent_folder input:
# 1. Symlink (not copy!) created to parent's ./out/
# 2. QE reads evc.dat from symlinked location
# 3. No GB transfer between sequential jobs
```

### Parser Flow (PwParser)

```python
# aiida_quantumespresso/parsers/pw.py (simplified)
def parse(self, retrieved_temporary_folder=None):
    # 1. Read XML from permanent retrieved folder
    xml_path = self.retrieved.open('aiida.save/data-file-schema.xml')
    parsed_data = parse_xml(xml_path)

    # 2. Read eigenvalues from temporary folder (if bands calculation)
    if retrieved_temporary_folder:
        for kpoint_dir in glob('K*/eigenval*.xml'):
            bands_data.append(parse_eigenvalues(kpoint_dir))

    # 3. Create output nodes
    self.out('output_parameters', Dict(dict=parsed_data))
    self.out('output_band', BandsData(bands_data))

    # 4. Temporary folder auto-deleted after this method returns
```

### QE outdir Philosophy

| Location | Content | AiiDA Treatment |
|----------|---------|-----------------|
| `./out/aiida.save/data-file-schema.xml` | Results XML | Retrieved permanently |
| `./out/aiida.save/K*/eigenval*.xml` | Band eigenvalues | Retrieved temporarily, parsed, deleted |
| `./out/aiida.save/K*/evc.dat` | Wavefunctions | Left on remote, accessed via RemoteData |
| `./out/aiida.save/charge-density.dat` | Charge density | Left on remote |

---

## F) QE End-to-End Path Narrative

### 1. Input Preparation

```
User creates PwCalculation with inputs:
├── structure: StructureData (atomic positions)
├── parameters: Dict ({'CONTROL': {...}, 'SYSTEM': {...}})
├── pseudos: {'Si': UpfData, 'O': UpfData}
├── kpoints: KpointsData (mesh or explicit)
└── parent_folder: RemoteData (optional, for restart)

CalcJob.prepare_for_submission(folder):
├── Writes aiida.in to SandboxFolder
├── Copies pseudopotentials
├── Returns CalcInfo with retrieve_list
└── Sets blocked keywords (outdir='./out/', prefix='aiida')
```

### 2. Upload to Remote

```
execmanager.upload_calculation():
├── Creates /remote/workdir/{uuid[:2]}/{uuid[2:4]}/{uuid[4:]}
├── Copies SandboxFolder contents → remote
├── Copies PortableCode files (if any)
├── Creates symlink to parent_folder's ./out/ (if restart)
├── Stores input files in CalcJobNode.repository
└── Creates RemoteData output with remote_path attribute
```

### 3. Job Execution

```
QE pw.x runs on remote:
├── Reads aiida.in
├── Writes to ./out/aiida.save/:
│   ├── data-file-schema.xml (results)
│   ├── K00001/eigenval.xml, evc.dat
│   ├── K00002/eigenval.xml, evc.dat
│   └── charge-density.dat
└── Writes aiida.out (stdout)
```

### 4. Retrieval

```
execmanager.retrieve_calculation():

Permanent files (→ FolderData.repository):
├── aiida.out
├── CRASH (if exists)
└── ./out/aiida.save/data-file-schema.xml

Temporary files (→ temp folder for parsing):
└── ./out/aiida.save/K*/eigenval*.xml

NOT retrieved (stays on remote):
├── ./out/aiida.save/K*/evc.dat (wavefunctions)
└── ./out/aiida.save/charge-density.dat
```

### 5. Parsing

```
PwParser.parse(retrieved_temporary_folder):
├── Reads data-file-schema.xml → energy, forces, stress
├── Reads eigenval*.xml from temp folder → band structure
├── Creates output nodes:
│   ├── output_parameters: Dict (energy, forces, etc.)
│   ├── output_band: BandsData (if bands calc)
│   ├── output_structure: StructureData (if relaxation)
│   └── output_trajectory: TrajectoryData (if MD)
└── Temp folder deleted after parsing
```

### 6. Final Provenance Graph

```
                                ┌──────────────────┐
                    INPUT_CALC  │  StructureData   │
                       ┌────────│  (input atoms)   │
                       │        └──────────────────┘
                       │
                       │        ┌──────────────────┐
                       │        │  Dict (params)   │
                       ├────────│  parameters      │
                       │        └──────────────────┘
                       │
                       │        ┌──────────────────┐
                       │        │  KpointsData     │
                       ├────────│  kpoints         │
                       │        └──────────────────┘
                       ▼
               ┌───────────────┐
               │  CalcJobNode  │
               │  (pw.x run)   │
               └───────┬───────┘
                       │
        ┌──────────────┼──────────────┬─────────────────┐
        │              │              │                 │
        ▼ CREATE       ▼ CREATE       ▼ CREATE          ▼ CREATE
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  FolderData  │ │     Dict     │ │  BandsData   │ │  RemoteData  │
│  retrieved   │ │   output_    │ │ output_band  │ │remote_folder │
│              │ │  parameters  │ │              │ │(./out/ path) │
│ ┌──────────┐ │ │              │ │              │ │              │
│ │aiida.out │ │ │{energy: ..., │ │ [k-points,   │ │ References   │
│ │data-file │ │ │ forces: ..., │ │  eigenvals]  │ │ evc.dat etc  │
│ │.xml      │ │ │ stress: ...} │ │              │ │ on remote    │
│ └──────────┘ │ │              │ │              │ │              │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

---

## G) Most Transferable Ideas for QMatSuite Level-2 Provenance

### 1. Dual Storage Architecture: DB + CAS

**Why valuable:** Clean separation of searchable metadata (fast queries) from large files (efficient dedup).

**Implementation difficulty:** Medium. Need SQLite for metadata, separate file store for CAS.

**QMatSuite mapping:**
```
.history/
├── provenance.db          # SQLite: nodes, links, attributes
└── objects/               # CAS: content-addressed files
    ├── ab/
    │   └── cdef123...     # SHA-256 keyed files
    └── loose/             # Unpacked recent files
```

### 2. Content-Addressed Storage with SHA-256 Keys

**Why valuable:** Automatic deduplication, integrity verification, immutability guarantee.

**Implementation difficulty:** Easy. Hash on write, use hash as filename.

**QMatSuite mapping:**
```python
def store_file(content: bytes) -> str:
    key = hashlib.sha256(content).hexdigest()
    path = objects_dir / key[:2] / key[2:4] / key
    if not path.exists():
        path.write_bytes(content)
    return key
```

### 3. Repository Metadata as JSON in DB

**Why valuable:** Virtual file hierarchy stored in single JSONB column, reconstructed on access.

**Implementation difficulty:** Easy.

**QMatSuite mapping:**
```sql
CREATE TABLE runs (
    id INTEGER PRIMARY KEY,
    uuid TEXT UNIQUE,
    ...
    file_manifest JSON  -- {"results/band.dat": "abc123...", ...}
);
```

### 4. Link Table for Provenance Graph

**Why valuable:** Flexible DAG storage, efficient traversal with indexes, semantic link types.

**Implementation difficulty:** Easy.

**QMatSuite mapping:**
```sql
CREATE TABLE links (
    id INTEGER PRIMARY KEY,
    source_id INTEGER REFERENCES artifacts(id),
    target_id INTEGER REFERENCES artifacts(id),
    link_type TEXT,  -- 'input', 'output', 'derived_from', 'analyzed_by'
    link_label TEXT
);
CREATE INDEX idx_links_source ON links(source_id);
CREATE INDEX idx_links_target ON links(target_id);
```

### 5. Selective Retrieval with Plugin-Defined Patterns

**Why valuable:** Only persist what matters, leave large files as references.

**Implementation difficulty:** Medium. Define per-code "retrieve manifest".

**QMatSuite mapping:**
```yaml
# code_profiles/pw.yaml
retrieve_patterns:
  permanent:
    - "*.xml"
    - "aiida.out"
  temporary:  # parsed then deleted
    - "K*/eigenval*.xml"
  reference_only:  # metadata pointer, not copied
    - "*.wfc*"
    - "charge-density.dat"
```

### 6. RemoteData Pattern: Metadata-Only References

**Why valuable:** Track large remote files without copying GBs.

**Implementation difficulty:** Easy.

**QMatSuite mapping:**
```python
@dataclass
class RemoteReference:
    """Pointer to file on remote/scratch, not stored locally."""
    original_path: str
    size_bytes: int
    mtime: datetime
    checksum: str  # computed at job end, for verification
```

### 7. Immutability After Storage

**Why valuable:** Guarantees provenance integrity, enables caching.

**Implementation difficulty:** Easy (enforcement in API layer).

**QMatSuite mapping:**
- Artifacts are immutable once committed to `.history/`
- "Current" files in workspace are mutable (user-facing)
- Commit creates new version in history, doesn't modify old

### 8. Caching Based on Content Hash

**Why valuable:** Skip redundant calculations if inputs haven't changed.

**Implementation difficulty:** Medium.

**QMatSuite mapping:**
```python
def get_cache_key(run_config: dict, input_files: dict[str, str]) -> str:
    """Hash of (code_version, parameters, input_file_hashes)."""
    return make_hash({
        'code': run_config['code_version'],
        'params': run_config['parameters'],
        'inputs': {k: v for k, v in sorted(input_files.items())}
    })

# Before running, check: SELECT * FROM runs WHERE cache_key = ?
```

### 9. Pack Files for Old Objects

**Why valuable:** Reduces inode overhead, enables compression of cold data.

**Implementation difficulty:** Medium-Hard.

**QMatSuite mapping:**
- Recent files: loose in `objects/ab/cd/...`
- Old files: packed into `packs/pack-001.tar.zst` with index
- Maintenance task: `pack_loose_objects(older_than=30_days)`

### 10. Soft Delete with Periodic Cleanup

**Why valuable:** Safe deletion (objects may be referenced by other nodes), eventual cleanup.

**Implementation difficulty:** Easy.

**QMatSuite mapping:**
```sql
-- Mark file for deletion (remove from manifest, don't delete yet)
UPDATE runs SET file_manifest = json_remove(file_manifest, '$.path/to/file')
WHERE id = ?;

-- Periodic cleanup: find unreferenced objects
DELETE FROM objects WHERE key NOT IN (
    SELECT DISTINCT value FROM runs, json_each(runs.file_manifest)
);
```

---

## H) Things We Should NOT Copy from AiiDA

### 1. Global Daemon Architecture

**What it is:** AiiDA runs a persistent daemon process that monitors all calculations, manages job submission, polling, and retrieval.

**Why avoid:** Adds operational complexity (daemon crashes, restarts, state recovery). QMatSuite should use on-demand CLI execution.

### 2. Profile System with Multiple Databases

**What it is:** AiiDA supports multiple "profiles" each with separate database and repository.

**Why avoid:** Unnecessary for single-user CLI tool. One `.history/` per project is sufficient.

### 3. Full PostgreSQL Requirement

**What it is:** Production AiiDA requires PostgreSQL for scalability.

**Why avoid:** SQLite is sufficient for per-project provenance (thousands of runs, not millions). Eliminates server dependency.

### 4. Complex Computer/AuthInfo/Transport Abstractions

**What it is:** AiiDA has elaborate abstractions for remote computers, authentication, and transport protocols.

**Why avoid:** QMatSuite runs locally or uses simple SSH. No need for pluggable transport layer.

### 5. WorkChain State Machine

**What it is:** Complex coroutine-based workflow engine with checkpointing, persistence, and recovery.

**Why avoid:** Over-engineered for CLI tool. Simple sequential scripts with explicit checkpoints are clearer.

### 6. Node Type Proliferation

**What it is:** Dozens of specialized node types (Bool, Int, Float, Str, etc.).

**Why avoid:** JSON attributes handle scalar types fine. Focus on: Run, Artifact, Analysis as main types.

### 7. Plugin Entry Points System

**What it is:** Sophisticated plugin discovery via setuptools entry points.

**Why avoid:** Simpler config-file or directory-based code profiles are sufficient.

### 8. Recursive CTE Graph Queries by Default

**What it is:** AiiDA's QueryBuilder supports arbitrary graph traversal with recursive CTEs.

**Why avoid:** Expensive for simple cases. Implement only when needed (e.g., full lineage export).

### 9. Immutable Attributes, Mutable Extras Distinction

**What it is:** Nodes have immutable `attributes` and mutable `extras` columns.

**Why avoid:** Confusing. Better: everything immutable in history, add new "annotation" records for mutable notes.

### 10. Global Settings Table

**What it is:** `db_dbsetting` stores global configuration in database.

**Why avoid:** Use config files (`.qmatsuite/config.yaml`) for settings, not database.

---

## I) Recommended QMatSuite Architecture

Based on AiiDA's best patterns, here's a minimal but powerful architecture:

```
project/
├── Si_bulk/                      # User-facing "always current" workspace
│   ├── scf/
│   │   ├── pw.in
│   │   └── pw.out               # Latest outputs, overwritten on rerun
│   └── bands/
│       ├── pw.in
│       └── pw.out
│
└── .history/                     # Level-2 provenance (hidden)
    ├── provenance.db            # SQLite: runs, artifacts, links, attributes
    ├── objects/                 # CAS: SHA-256 keyed files
    │   ├── ab/cd/abcdef...
    │   └── ...
    └── packs/                   # Compressed archives of old objects
        └── pack-2024-01.tar.zst
```

### Database Schema (Simplified)

```sql
CREATE TABLE runs (
    id INTEGER PRIMARY KEY,
    uuid TEXT UNIQUE,
    run_type TEXT,              -- 'scf', 'bands', 'relax'
    code_name TEXT,             -- 'pw.x', 'ph.x'
    status TEXT,                -- 'pending', 'running', 'completed', 'failed'
    created_at TIMESTAMP,
    completed_at TIMESTAMP,
    attributes JSON,            -- {energy: -123.45, nscf: true, ...}
    file_manifest JSON,         -- {path: sha256_key}
    workspace_path TEXT         -- 'Si_bulk/scf'
);

CREATE TABLE artifacts (
    id INTEGER PRIMARY KEY,
    uuid TEXT UNIQUE,
    artifact_type TEXT,         -- 'structure', 'bands', 'dos', 'plot'
    created_at TIMESTAMP,
    attributes JSON,
    file_manifest JSON
);

CREATE TABLE links (
    source_id INTEGER,
    target_id INTEGER,
    source_type TEXT,           -- 'run' or 'artifact'
    target_type TEXT,
    link_type TEXT,             -- 'input', 'output', 'derived', 'analyzed'
    link_label TEXT
);

-- Indexes for efficient traversal
CREATE INDEX idx_links_source ON links(source_id, source_type);
CREATE INDEX idx_links_target ON links(target_id, target_type);
CREATE INDEX idx_runs_workspace ON runs(workspace_path);
CREATE INDEX idx_runs_status ON runs(status);
```

### Key Operations

1. **Run completion:** Snapshot workspace → store files in CAS → record in DB → update workspace symlinks
2. **Query lineage:** `SELECT * FROM links WHERE target_id = ?` (immediate parents)
3. **Restore version:** Reconstruct workspace from `file_manifest` + CAS
4. **Dedup check:** Files with same SHA-256 share storage automatically

---

## J) Key Source Files Reference

### AiiDA-Core Repository (`aiida-core/src/aiida/`)

| Component | Path | Key Classes/Functions |
|-----------|------|----------------------|
| Node base | `orm/nodes/node.py` | `Node`, `NodeBase`, `store()` |
| Data nodes | `orm/nodes/data/` | `Data`, `FolderData`, `RemoteData` |
| CalcJobNode | `orm/nodes/process/calculation/calcjob.py` | `CalcJobNode` |
| Link types | `common/links.py` | `LinkType` enum |
| Repository | `repository/repository.py` | `Repository`, `serialize()` |
| CAS backend | `repository/backend/disk_object_store.py` | `DiskObjectStoreRepositoryBackend` |
| Node repository | `orm/nodes/repository.py` | `NodeRepository`, `_store()` |
| DB models | `storage/psql_dos/models/node.py` | `DbNode`, `DbLink` |
| Exec manager | `engine/daemon/execmanager.py` | `upload_calculation()`, `retrieve_calculation()` |
| CalcInfo | `common/datastructures.py` | `CalcInfo` |

### AiiDA-QuantumESPRESSO (`aiida-quantumespresso/src/`)

| Component | Path | Key Classes/Functions |
|-----------|------|----------------------|
| PwCalculation | `aiida_quantumespresso/calculations/pw.py` | `PwCalculation` |
| Base generator | `aiida_quantumespresso/calculations/__init__.py` | `BasePwCpInputGenerator` |
| PwParser | `aiida_quantumespresso/parsers/pw.py` | `PwParser` |
| XML parsing | `aiida_quantumespresso/parsers/parse_xml/` | `parse()` |

---

## Conclusion

AiiDA provides a mature, well-designed provenance system that we can learn from without adopting wholesale. The key insights for QMatSuite Level-2 provenance are:

1. **Dual storage** (DB + CAS) provides the best of both worlds
2. **Content-addressing** gives automatic dedup and integrity
3. **Selective retrieval** keeps storage manageable
4. **Link tables** enable flexible provenance graphs
5. **Immutability** guarantees reproducibility

The complexity we should avoid includes the daemon architecture, profile system, PostgreSQL requirement, and elaborate plugin machinery. A simpler SQLite + file-based CAS approach will serve QMatSuite's needs well while maintaining the core provenance guarantees.
