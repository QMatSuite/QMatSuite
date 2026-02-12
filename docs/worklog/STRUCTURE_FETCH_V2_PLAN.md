# Structure Fetch v2 Implementation Plan

**Date:** 2026-02-11 (Revised: 2026-02-11)  
**Status:** Plan Only (No Code Changes)  
**Authoritative Source:** `docs/design/ONLINE_STRUCTURE_SOURCES.md`

**Revision Notes:**
This plan has been revised to address review feedback:
- **R1:** Added `update_online_sources()` API method for settings persistence
- **R2:** Reordered PRs - API capability port + daemon/CLI migration moved to PR0 (before provider registry)
- **R3:** Removed `project_root` argument from `fetch_structure()` - uses global cache instead
- **R4:** Clarified module ownership - providers are I/O layer (network I/O), not kernel-core; added dependency diagram
- **R5:** Added test-infra audit section; specified non-flaky tests using `unittest.mock`
- **R6:** Registry v2 defaults to curated allowlist enabled; registry providers disabled by default (user opt-in)
- **R7:** Fixed test data references - use `tests/data/optimade/` fixtures, not unrelated NMR data
- **F1:** Removed ALL `project_root` from GUI/RPC examples; added concrete CLI wiring steps (exact files, commands, flags)
- **F2:** Added live network tests section (single file `test_optimade_online.py`, 5 test cases)
- **F3:** Added skippable policy (pytest selection only, no env vars); added verification checklist
- **F4:** Removed overengineering (circuit breaker marked optional/out of scope)

---

## 1. Summary of Goals and Constraints

### 1.1 Goals

Implement "Structure Fetch v2" that expands online structure search capabilities:

1. **Crystals via OPTIMADE Federation:**
   - Expand from 4 hardcoded endpoints to curated default set (MP, COD OPTIMADE, Alexandria, OQMD, JARVIS, Materials Cloud)
   - Implement dynamic provider discovery via `providers.optimade.org` registry
   - Parallel query with per-provider timeouts
   - De-duplication and aggregation across providers
   - Ranking/scoring with provider trust weights
   - Remove broken COD MySQL fallback (replace with COD OPTIMADE HTTP)

2. **Molecules via PubChem:**
   - Name/formula search → PubChem CID list
   - Fetch 3D conformer (SDF) when available
   - Parse SDF into project's Structure schema (cell=None, pbc=false for molecules)
   - Support molecular codes (ORCA, Gaussian, Psi4, PySCF, xTB)

3. **Optional MP Native API:**
   - Add Materials Project native API pathway (requires API key)
   - Must NOT be required by default
   - Integrated behind same minimal API capability port

### 1.2 Hard Constraints (Non-Negotiable)

**A) API Capability Port Must Be Minimal and Single-Source-of-Truth:**
- CLI and daemon MUST call the same API capability entrypoints
- No duplicated "fetch logic" in CLI or daemon; no second truth
- All provider-specific logic must live in I/O layer (below API) (R4: clarified as I/O layer, not kernel-core)

**B) Layering/Import Laws:**
- CLI MUST NOT import kernel (`quantumvitas.io.*`, `quantumvitas.core.*`, etc.)
- Daemon MUST NOT import kernel
- Follow all existing "no import" gate tests; plan must include new/updated gate tests if needed
- Gate tests: `tests/gates/test_import_gate.py`, `tests/gates/test_daemon_kernel_ban.py`, `tests/gates/test_import_rules.py`

**C) Plan-Only:**
- Do not change code. Do not add files. Do not refactor. Only propose changes in the plan.

**D) Tests Are Mandatory:**
- Plan must specify what tests to add, where, and what each asserts
- Plan must specify mocking strategy for network calls + timeouts + provider registry

**E) Implement All Features:**
- v2 dynamic OPTIMADE provider discovery via registry
- Molecules via PubChem
- Optional MP native API key path

---

## 2. Current State Audit

### 2.1 Existing Implementation

**Location:** `src/quantumvitas/io/online_search.py`

**Current Flow:**
1. `search_online_structures(query, max_results)` → tries OPTIMADE first, COD fallback
2. OPTIMADE: Sequential search across 4 hardcoded base URLs:
   - `https://optimade.materialsproject.org` (primary)
   - `https://optimade.materialscloud.org/main/mc3d-pbe-v1` (fallback)
   - `https://optimade.materialscloud.org/main/mc3d-pbesol-v2` (fallback)
   - `https://optimade.materialscloud.org/main/mc3d-pbesol-v1` (fallback)
3. COD: Uses `pymatgen.ext.cod.COD()` (MySQL dependency, broken for most users)
4. 2-step fetch: OPTIMADE search returns metadata only; full structure fetched on demand
5. Cache: SQLite with msgpack-serialized structures, 30-day TTL (`src/quantumvitas/io/online_cache.py`)

**Current API Surface:**
- `search_online_structures()` in `quantumvitas.io.online_search` (kernel)
- Re-exported in `quantumvitas.api.utils` (violates Law H3 per `API_CONSTITUTION.md`)
- Daemon handler: `_handle_structure_search_online()` in `src/quantumvitas/daemon/server.py` (line 2146)
- Daemon calls `search_online_structures()` directly (violates layering - imports from `quantumvitas.io.online_search`)

**Current Cache (R3: To Migrate to Global Cache):**
- `OnlineStructureCache` in `src/quantumvitas/io/online_cache.py`
- Current location: `structures/cache/structure_fetch_cache.sqlite3` (project-specific, violates resolver laws)
- **New location:** `~/.qmatsuite/cache/online_structures/structure_fetch_cache.sqlite3` (global user cache)
- TTL: 30 days
- Stores: sessions, candidates, structures (msgpack blobs)
- Migration: Update cache path to use `quantumvitas.core.paths.get_qmatsuite_home_root() / "cache" / "online_structures"`

**Current GUI Integration:**
- `gui/src/components/panels/OnlineImportPanel.tsx`
- RPC method: `structure_search_online`
- Payload: `{query: str, max_results: int}`
- Response: `{session_id: str, candidates: OnlineCandidate[]}`

**Current Settings:**
- Global settings: `src/quantumvitas/core/settings.py` → `QMatSuiteSettings`
- Settings file: `.qmatsuite/config/settings.json`
- No online structure provider configuration exists today

### 2.2 Import Violations (To Fix)

**Current Violations:**
1. `src/quantumvitas/daemon/server.py:58` imports `search_online_structures` from `quantumvitas.io.online_search` (kernel)
2. `src/quantumvitas/api/utils.py:1698` re-exports `search_online_structures` (violates Law H3)

**Gate Tests to Update:**
- `tests/gates/test_import_gate.py` - already enforces CLI/daemon no kernel imports
- `tests/gates/test_daemon_kernel_ban.py` - already enforces daemon no kernel imports
- No new gate tests needed, but violations must be fixed

### 2.3 Structure Schema

**Current Structure Representation:**
- Crystals: pymatgen `Structure` with lattice (3x3 matrix) and `pbc=[True,True,True]`
- Molecules: Not currently supported (no `cell=None` or `pbc=False` in current schema)
- Structure files: JSON with pymatgen dict format
- Structure DTO: `quantumvitas.api.types.structure.StructureDTO` (summary only, no positions)

**Molecular Structure Support:**
- PySCF integration spec (`docs/architecture/PYSCF_INTEGRATION_SPEC.md`) shows molecular structures use `atoms` array with Cartesian coordinates, no lattice
- Demo store (`src/quantumvitas/demo_store/translator.py`) shows molecular structures can omit lattice
- Need to support `cell=None` and `pbc=False` (or equivalent) for molecules

---

## 3. Proposed Architecture

### 3.1 Module Layout and Ownership (R4: Clarify I/O Layer)

**Existing Modules:**
- **API Layer:** `src/quantumvitas/api/service.py` (QVService class)
- **CLI:** `src/quantumvitas/cli/main.py` (Typer commands)
- **Daemon:** `src/quantumvitas/daemon/server.py` (JSON-RPC handlers)
- **GUI RPC Client:** `gui/src/types/qv.ts` (TypeScript RPC definitions)
- **I/O Layer (Network):** `src/quantumvitas/io/online_search.py` (current implementation)
- **I/O Layer (Cache):** `src/quantumvitas/io/online_cache.py` (SQLite cache)

**New Modules to Create (I/O Layer - Network/Providers):**

**Note (R4):** Providers are I/O layer (network I/O), not kernel-core. They perform HTTP requests and parse responses. They MUST NOT import API types (use provider-local models or primitives).

1. **`src/quantumvitas/io/providers/optimade.py`**
   - OPTIMADE provider registry fetching (HTTP)
   - Provider configuration management (local models, not API DTOs)
   - Parallel query orchestration (HTTP requests)
   - Deduplication and aggregation logic (pure functions)

2. **`src/quantumvitas/io/providers/pubchem.py`**
   - PubChem name/formula search (HTTP)
   - SDF fetching and parsing (HTTP + text parsing)
   - Molecule structure conversion (pymatgen, no API types)

3. **`src/quantumvitas/io/providers/materials_project.py`**
   - MP native API client (mp-api wrapper, HTTP)
   - API key handling (from settings, not API DTOs)
   - Rich metadata extraction (local models)

4. **`src/quantumvitas/io/providers/__init__.py`**
   - Provider registry (local models)
   - Provider factory (returns provider instances)
   - Unified search interface (returns local Candidate models, not API DTOs)

**New Modules to Create (API Layer):**

1. **`src/quantumvitas/api/types/online_search.py`**
   - DTOs for online search:
     - `SearchRequestDTO`
     - `SearchResultDTO`
     - `CandidateDTO`
     - `ProviderConfigDTO`
     - `ProviderListDTO`

**Settings Extension (R1: Settings Write Pathway):**
- Extend `src/quantumvitas/core/settings.py` → `QMatSuiteSettings` with `online_structures` field
- Settings storage location: `.qmatsuite/config/settings.json` (global, not project-specific)
- Settings file path: Uses `quantumvitas.core.paths.get_settings_json_path()` (same as existing settings)
- Settings schema:
  ```python
  @dataclass
  class OnlineStructuresConfig:
      optimade_providers: List[ProviderConfigDict]  # [{"id": "mp", "enabled": true}, ...]
      pubchem_enabled: bool = True
      materials_project: MaterialsProjectConfig
      timeout_seconds: float = 8.0
      max_results_per_provider: int = 10
      max_total_results: int = 50
  ```
- Settings update: `QVService.OnlineSearch.update_online_sources()` calls `set_settings()` from `api.utils` (reuses existing capability)
- Settings persistence: `set_settings()` calls `quantumvitas.core.settings.save_settings()` (existing infrastructure)

### 3.2 Architecture Diagram (Text, R4: I/O Layer Clarification)

```
┌─────────────────────────────────────────────────────────────┐
│ Frontend Layer (CLI/Daemon/GUI)                            │
│                                                             │
│  CLI: qv search-structure <query>                          │
│  Daemon: structure_search_online RPC                        │
│  GUI: OnlineImportPanel.tsx → RPC call                     │
└────────────────────┬───────────────────────────────────────┘
                     │ (imports allowed)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ API Facade Layer (quantumvitas.api)                        │
│                                                             │
│  QVService.OnlineSearch.search(...) → SearchResultDTO       │
│  QVService.OnlineSearch.fetch(...) → StructureDocDTO        │
│  QVService.OnlineSearch.list_providers() → ProviderListDTO │
│  QVService.OnlineSearch.update_online_sources() → Settings │
│                                                             │
│  DTOs: SearchRequestDTO, CandidateDTO, ProviderConfigDTO   │
│  Model→DTO conversion: Provider Candidate → CandidateDTO    │
└────────────────────┬───────────────────────────────────────┘
                     │ (imports allowed)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ I/O Layer (quantumvitas.io.providers) - Network I/O        │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ ProviderRegistry                                      │ │
│  │  - fetch_registry() → List[ProviderConfig] (local)   │ │
│  │  - get_curated_defaults() → List[ProviderConfig]     │ │
│  │  - cache with TTL (global cache)                     │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ OPTIMADEProvider                                       │ │
│  │  - search_parallel() → List[Candidate] (local model) │ │
│  │  - fetch_structure() → Structure (pymatgen)         │ │
│  │  - deduplicate() → List[Candidate]                   │ │
│  │  - rank() → List[Candidate]                          │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ PubChemProvider                                        │ │
│  │  - search_by_name() → List[CID]                       │ │
│  │  - search_by_formula() → List[CID]                    │ │
│  │  - fetch_3d_sdf() → SDF string                        │ │
│  │  - parse_sdf_to_structure() → Molecule (pymatgen)   │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ MaterialsProjectProvider                               │ │
│  │  - search_native() → List[Candidate] (local model)  │ │
│  │  - requires_api_key: bool                             │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ OnlineStructureCache (global cache)                   │ │
│  │  - Location: ~/.qmatsuite/cache/online_structures/    │ │
│  │  - Cache key: provider + query + filters + version   │ │
│  └──────────────────────────────────────────────────────┘ │
└────────────────────┬───────────────────────────────────────┘
                     │ (imports allowed)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Core/Kernel Layer (quantumvitas.core.*)                    │
│                                                             │
│  - Settings: quantumvitas.core.settings                    │
│  - Paths: quantumvitas.core.paths                          │
│  - Models: quantumvitas.core.models                        │
└─────────────────────────────────────────────────────────────┘

IMPORT RULES (R4):
- I/O Layer MUST NOT import API types (no reverse dependency)
- I/O Layer uses local models (ProviderConfig, Candidate) not API DTOs
- API Layer converts I/O models → DTOs
```

### 3.3 Dependency Diagram and Import Rules (R4)

**Dependency Flow:**
```
Frontend (CLI/Daemon/GUI)
    ↓ (imports allowed)
API Facade (quantumvitas.api)
    ↓ (imports allowed)
I/O Layer (quantumvitas.io.providers.*, quantumvitas.io.online_cache.*)
    ↓ (imports allowed)
Core/Kernel (quantumvitas.core.*, etc.)
```

**Allowed Imports:**
- CLI/Daemon → `quantumvitas.api.*` only
- API → I/O Layer (`quantumvitas.io.providers.*`, `quantumvitas.io.online_cache.*`)
- API → Core/Kernel (for settings, paths, etc.)
- I/O Layer → Core/Kernel (for settings, paths, pymatgen, etc.)
- I/O Layer → Standard library + third-party (requests, pymatgen, etc.)

**Forbidden Imports (Enforced by Gates):**
- CLI/Daemon → `quantumvitas.io.*` (I/O layer)
- CLI/Daemon → `quantumvitas.core.*` (kernel)
- I/O Layer → `quantumvitas.api.*` (NO reverse imports to API)
- I/O Layer → API DTOs (providers use local models, not API types)

**Provider Local Models:**
- Providers define their own dataclasses (e.g., `ProviderConfig`, `Candidate`, `ProviderResult`)
- API layer converts provider models → DTOs
- This prevents reverse dependency (providers don't import API types)

---

## 4. API Capability Port (Minimal Single-Source-of-Truth)

### 4.1 Proposed API Methods

**Location:** `src/quantumvitas/api/service.py` → `QVService.OnlineSearch` nested class

**Method 1: `search_structures()`**
```python
@staticmethod
def search_structures(
    query: str,
    *,
    mode: Literal["crystal", "molecule", "auto"] = "auto",
    sources: Optional[SourceConfig] = None,
    limit: int = 10,
    timeout_s: float = 8.0,
    refresh_registry: bool = False,
) -> SearchResultDTO:
    """
    Search online structures (OPTIMADE crystals + PubChem molecules).
    
    Args:
        query: Chemical formula or molecule name (e.g., "Si", "caffeine", "H2O")
        mode: Search mode - "crystal" (OPTIMADE only), "molecule" (PubChem only), "auto" (both)
        sources: Source configuration (provider enable/disable, ordering). If None, uses settings defaults.
        limit: Maximum total results to return
        timeout_s: Per-provider timeout in seconds
        refresh_registry: If True, force refresh OPTIMADE provider registry cache
        
    Returns:
        SearchResultDTO with:
        - candidates: List[CandidateDTO] (deduplicated, ranked, aggregated)
        - session_id: str (for 2-step fetch)
        - providers_queried: List[str] (provider IDs that were queried)
        - partial: bool (True if some providers timed out)
    """
```

**Method 2: `fetch_structure()` (R3: No project_root argument)**
```python
@staticmethod
def fetch_structure(
    ref: StructureRefDTO,
) -> StructureDocDTO:
    """
    Fetch full structure from online source (2-step fetch for OPTIMADE).
    
    Uses global user cache at ~/.qmatsuite/cache/online_structures (not project-specific).
    This avoids resolver/path laws violations and creates single cache location.
    
    Args:
        ref: StructureRefDTO with:
            - session_id: str (from search_structures)
            - candidate_id: str (from CandidateDTO)
            - OR: direct_ref: dict with provider-specific ref (e.g., {"provider": "optimade", "base_url": "...", "entry_id": "..."})
        
    Returns:
        StructureDocDTO with full structure data (atoms, lattice if crystal, etc.)
    """
```

**Method 3: `list_providers()`**
```python
@staticmethod
def list_providers(
    *,
    refresh_registry: bool = False,
) -> ProviderListDTO:
    """
    List available online structure providers.
    
    Args:
        refresh_registry: If True, force refresh OPTIMADE provider registry cache
        
    Returns:
        ProviderListDTO with:
        - optimade_providers: List[ProviderInfoDTO] (id, name, base_url, enabled, structure_count)
        - pubchem_enabled: bool
        - materials_project_enabled: bool (requires API key)
    """
```

**Method 4: `update_online_sources()` (R1: Settings Write Pathway)**
```python
@staticmethod
def update_online_sources(
    patch: OnlineSourcesPatchDTO,
) -> OnlineSourcesSettingsDTO:
    """
    Update online structure source settings.
    
    This method patches only the online_structures subtree of global settings.
    Reuses existing settings update capability (set_settings in api.utils).
    
    Args:
        patch: OnlineSourcesPatchDTO with fields to update:
            - optimade_providers: Optional[List[ProviderPatchDTO]] (id + enabled)
            - pubchem_enabled: Optional[bool]
            - materials_project: Optional[MaterialsProjectPatchDTO] (enabled + api_key)
            - timeout_seconds: Optional[float]
            - max_results_per_provider: Optional[int]
            - max_total_results: Optional[int]
        
    Returns:
        OnlineSourcesSettingsDTO with current settings after patch
    """
```

### 4.2 DTO Definitions

**Location:** `src/quantumvitas/api/types/online_search.py`

```python
@dataclass
class SearchRequestDTO(BaseDTO):
    """Search request parameters."""
    query: str
    mode: Literal["crystal", "molecule", "auto"] = "auto"
    sources: Optional[SourceConfigDTO] = None
    limit: int = 10
    timeout_s: float = 8.0
    refresh_registry: bool = False

@dataclass
class SourceConfigDTO(BaseDTO):
    """Source configuration (provider enable/disable, ordering)."""
    optimade_provider_ids: Optional[List[str]] = None  # If None, use settings defaults
    pubchem_enabled: Optional[bool] = None  # If None, use settings default
    materials_project_enabled: Optional[bool] = None  # If None, use settings default

@dataclass
class CandidateDTO(BaseDTO):
    """Online structure candidate (search result)."""
    candidate_id: str
    label: str  # Display label (e.g., "Si (2 sites)")
    source: str  # Provider ID (e.g., "mp", "cod", "pubchem")
    source_id: str  # Provider-specific ID
    structure_type: Literal["crystal", "molecule"]
    formula: str
    nsites: int
    spacegroup: Optional[str] = None  # For crystals
    providers: List[str] = field(default_factory=list)  # Aggregated: ["mp", "cod", "oqmd"]
    score: float = 0.0
    flags: List[str] = field(default_factory=list)  # e.g., ["experimental", "partial_occ"]
    metadata: Dict[str, Any] = field(default_factory=dict)  # Provider-specific metadata

@dataclass
class SearchResultDTO(BaseDTO):
    """Search results."""
    session_id: str
    candidates: List[CandidateDTO]
    providers_queried: List[str]  # Provider IDs that were queried
    partial: bool  # True if some providers timed out
    query: str
    mode: str

@dataclass
class StructureRefDTO(BaseDTO):
    """Reference to an online structure (for 2-step fetch)."""
    session_id: Optional[str] = None
    candidate_id: Optional[str] = None
    direct_ref: Optional[Dict[str, Any]] = None  # Provider-specific ref

@dataclass
class StructureDocDTO(BaseDTO):
    """Full structure document (crystal or molecule)."""
    structure_type: Literal["crystal", "molecule"]
    formula: str
    atoms: List[Dict[str, Any]]  # [{"element": "Si", "coords": [x, y, z], ...}]
    lattice: Optional[List[List[float]]] = None  # 3x3 matrix for crystals, None for molecules
    pbc: Optional[List[bool]] = None  # [True, True, True] for crystals, [False, False, False] for molecules
    provenance: Dict[str, Any]  # Provider metadata

@dataclass
class ProviderInfoDTO(BaseDTO):
    """Provider information."""
    id: str  # Provider ID (e.g., "mp", "cod", "pubchem")
    name: str  # Display name
    base_url: Optional[str] = None  # OPTIMADE base URL (if applicable)
    enabled: bool
    structure_count: Optional[int] = None
    requires_api_key: bool = False

@dataclass
class ProviderListDTO(BaseDTO):
    """List of available providers."""
    optimade_providers: List[ProviderInfoDTO]
    pubchem_enabled: bool
    materials_project_enabled: bool
    materials_project_has_key: bool  # True if API key is configured

@dataclass
class ProviderPatchDTO(BaseDTO):
    """Patch for a single provider."""
    id: str
    enabled: bool

@dataclass
class MaterialsProjectPatchDTO(BaseDTO):
    """Patch for Materials Project settings."""
    enabled: Optional[bool] = None
    api_key: Optional[str] = None

@dataclass
class OnlineSourcesPatchDTO(BaseDTO):
    """Patch for online structure sources settings (R1: Settings write pathway)."""
    optimade_providers: Optional[List[ProviderPatchDTO]] = None
    pubchem_enabled: Optional[bool] = None
    materials_project: Optional[MaterialsProjectPatchDTO] = None
    timeout_seconds: Optional[float] = None
    max_results_per_provider: Optional[int] = None
    max_total_results: Optional[int] = None

@dataclass
class OnlineSourcesSettingsDTO(BaseDTO):
    """Current online structure sources settings (returned after patch)."""
    optimade_providers: List[ProviderInfoDTO]
    pubchem_enabled: bool
    materials_project: MaterialsProjectConfigDTO
    timeout_seconds: float
    max_results_per_provider: int
    max_total_results: int

@dataclass
class MaterialsProjectConfigDTO(BaseDTO):
    """Materials Project configuration."""
    enabled: bool
    has_key: bool  # True if API key is configured (key value not returned for security)
```

### 4.3 Justification for Each Function

**`search_structures()`:**
- Single entrypoint for all online searches (crystals + molecules)
- Mode parameter allows explicit crystal/molecule search or auto-detect
- Sources parameter allows per-request override of settings (useful for CLI flags)
- Returns aggregated, deduplicated, ranked results
- Session ID enables 2-step fetch pattern (existing behavior)

**`fetch_structure()` (R3: No project_root):**
- Required for 2-step fetch (OPTIMADE returns metadata only in search)
- Supports both session-based refs (from search) and direct refs (for programmatic access)
- Returns full structure document (atoms, lattice if crystal)
- Uses global cache: `~/.qmatsuite/cache/online_structures/` (not project-specific)
- No resolver needed: cache location determined by `quantumvitas.core.paths.get_qmatsuite_home_root()`
- Cache key computation: `f"{provider_id}:{source_id}:{registry_version}"` (no project path in key)

**`list_providers()`:**
- Needed for GUI settings panel (show available providers, enable/disable)
- Needed for CLI help/status commands
- Returns provider metadata (name, structure count, enabled status)

**`update_online_sources()` (R1: Settings Write Pathway):**
- Required for GUI settings panel to persist provider toggles and MP API key
- Required for CLI to set providers/key via same API
- Patches only `online_structures` subtree (minimal, single-purpose)
- Reuses existing `set_settings()` in `api.utils` (no new settings infrastructure)
- Returns updated settings after patch (for GUI to reload)

**No Additional Functions:**
- No `score_candidate()` - internal to search capability
- No `extract_provenance()` - internal to fetch capability
- No `reduce_formula()` - internal helper (or pure function in utils if truly needed)

---

## 5. Provider Registry Design

### 5.1 Registry Fetching

**Location:** `src/quantumvitas/io/providers/optimade.py`

**Registry URL:**
- Primary: `https://providers.optimade.org/v1/links`
- Fallback: Curated default list (hardcoded)

**Registry Cache (R3: Global Cache Location, R6: Registry Storage):**
- Cache location: `~/.qmatsuite/cache/online_structures/registry_cache.json` (global user cache, not project-specific)
- Cache directory: Uses `quantumvitas.core.paths.get_qmatsuite_home_root() / "cache" / "online_structures"`
- Cache key: `registry_v1_links` (or include registry URL in key)
- TTL: 24 hours (configurable, default 24h)
- Cache invalidation: On `refresh_registry=True` or TTL expiry
- Registry storage in settings: When registry is fetched, discovered providers are stored in `settings.online_structures.optimade_providers` with `enabled=false` by default (R6)
- Registry providers vs curated: Curated defaults have `enabled=true` by default; registry-discovered providers have `enabled=false` by default (user must opt-in)

**Registry Response Parsing (R6: Registry Providers Disabled by Default):**
```python
def fetch_optimade_registry(
    *,
    refresh: bool = False,
    cache_dir: Path,
) -> List[ProviderConfig]:
    """
    Fetch OPTIMADE provider registry.
    
    Returns curated default list if registry unavailable.
    Registry-discovered providers default to enabled=False (user must opt-in).
    """
    # 1. Check cache (unless refresh=True)
    # 2. If cache miss or refresh, fetch from providers.optimade.org/v1/links
    # 3. Parse response (JSON API format)
    # 4. Merge with curated defaults:
    #    - Curated defaults: enabled=True (unless user disabled)
    #    - Registry providers: enabled=False (unless user enabled)
    # 5. Merge with user settings (user preferences override defaults)
    # 6. Cache result (registry + settings merge)
    # 7. Return List[ProviderConfig] (with enabled flags from settings)
```

**ProviderConfig Structure (R6: Enabled Flag Logic):**
```python
@dataclass
class ProviderConfig:
    id: str  # e.g., "mp", "cod", "alexandria"
    name: str  # Display name
    base_url: str  # OPTIMADE base URL
    enabled: bool  # From user settings:
                   # - Curated defaults: enabled=True by default (unless user disabled)
                   # - Registry providers: enabled=False by default (user must opt-in)
    structure_count: Optional[int] = None  # From registry metadata
    trust_weight: float = 1.0  # For ranking (experimental > computed > ML)
    source: Literal["curated", "registry"]  # Track if provider is from curated list or registry
```

### 5.2 Curated Default List

**Location:** `src/quantumvitas/io/providers/optimade.py` → `CURATED_DEFAULT_PROVIDERS`

**Default Providers (R6: Curated Allowlist Enabled by Default):**
```python
CURATED_DEFAULT_PROVIDERS = [
    ProviderConfig(
        id="mp",
        name="Materials Project",
        base_url="https://optimade.materialsproject.org",
        enabled=True,  # Enabled by default (curated allowlist)
        trust_weight=0.9,  # Computed, high quality
    ),
    ProviderConfig(
        id="cod",
        name="COD (Crystallography Open Database)",
        base_url="https://www.crystallography.net/cod/optimade/v1",
        enabled=True,  # Enabled by default (curated allowlist)
        trust_weight=1.0,  # Experimental, highest priority
    ),
    ProviderConfig(
        id="alexandria",
        name="Alexandria",
        base_url="https://alexandria.icams.rub.de/optimade/v1",  # Verify actual URL
        enabled=True,  # Enabled by default (curated allowlist)
        trust_weight=0.8,  # Computed, large database
    ),
    ProviderConfig(
        id="oqmd",
        name="OQMD",
        base_url="http://oqmd.org/optimade/v1",
        enabled=True,  # Enabled by default (curated allowlist)
        trust_weight=0.8,  # Computed
    ),
    ProviderConfig(
        id="jarvis",
        name="JARVIS",
        base_url="https://jarvis.nist.gov/optimade/jarvisdft/v1",
        enabled=True,  # Enabled by default (curated allowlist)
        trust_weight=0.85,  # NIST quality
    ),
    ProviderConfig(
        id="mcloud",
        name="Materials Cloud",
        base_url="https://www.materialscloud.org/optimade/main",
        enabled=True,  # Enabled by default (curated allowlist)
        trust_weight=0.8,  # Computed
    ),
]
```

**Registry Providers (R6: Disabled by Default):**
- When registry is fetched, discovered providers are added to available list
- Registry providers default to `enabled=False` (user must opt-in)
- Only curated defaults are enabled by default
- Settings store: `optimade_providers: [{"id": "aflow", "enabled": false}, ...]`
- GUI shows "available but disabled" providers with enable checkbox

**Fallback Behavior:**
- If registry fetch fails (network error, timeout, invalid response), use curated defaults
- Log warning but continue (don't fail search)
- User can still enable/disable providers via settings

**Registry Refresh Behavior (R6):**
- On `refresh_registry=True`: Fetch fresh registry, merge with curated defaults
- Registry providers added to available list with `enabled=False` (unless user previously enabled)
- Settings updated: `optimade_providers` list includes both curated and registry providers
- GUI displays: "Available but disabled" providers with enable checkbox
- User can enable registry providers via settings UI (calls `update_online_sources` RPC)

### 5.3 Registry Version Stamping

**Cache Key Inclusion (R3: Global Cache, No Project Path):**
- Include registry fetch timestamp or version in cache keys for search results
- Format: `search_cache_key = f"{provider_id}:{query}:{filters}:{registry_version}"`
- Registry version: Timestamp of last successful registry fetch (or "default" if using curated list)
- **No project path in cache key** (global cache, not project-specific)
- Cache location: `~/.qmatsuite/cache/online_structures/structure_fetch_cache.sqlite3`
- Cache directory: `quantumvitas.core.paths.get_qmatsuite_home_root() / "cache" / "online_structures"`

**Rationale:**
- If registry updates (new providers added), old cached results should be invalidated
- Prevents stale results from showing providers that no longer exist
- Global cache avoids resolver/path law violations (no project_root needed)

---

## 6. OPTIMADE Federation Details

### 6.1 Parallel Query Strategy

**Location:** `src/quantumvitas/io/providers/optimade.py` → `OPTIMADEProvider.search_parallel()`

**Implementation:**
```python
def search_parallel(
    self,
    query: str,
    providers: List[ProviderConfig],
    max_per_provider: int = 10,
    timeout_s: float = 8.0,
) -> List[ProviderResult]:
    """
    Query multiple OPTIMADE providers in parallel.
    
    Returns:
        List[ProviderResult] (one per provider, includes timeout/error info)
    """
    # Use concurrent.futures.ThreadPoolExecutor (not asyncio - keep sync API)
    # Each provider query:
    #   1. Build OPTIMADE filter (chemical_formula_reduced="...")
    #   2. GET {base_url}/v1/structures?filter=...&page_limit=...
    #   3. Parse response (JSON API format)
    #   4. Convert to ProviderResult (entries + metadata)
    #   5. Handle timeout (return empty ProviderResult with timeout flag)
    #   6. Handle errors (return empty ProviderResult with error flag)
```

**Threading Model:**
- Use `concurrent.futures.ThreadPoolExecutor` (not asyncio)
- Reason: Keep API synchronous (no async/await in QVService)
- Max workers: `min(len(providers), 10)` (don't spawn too many threads)

**Timeout Handling:**
- Per-provider timeout: `timeout_s` (default 8s)
- Use `requests.get(..., timeout=timeout_s)`
- If timeout: Return empty `ProviderResult` with `timed_out=True`
- Don't retry (users shouldn't wait)

**Error Handling:**
- Network errors: Return empty `ProviderResult` with `error=str(e)`
- HTTP errors (4xx, 5xx): Return empty `ProviderResult` with `error=f"HTTP {status_code}"`
- Invalid JSON: Return empty `ProviderResult` with `error="Invalid JSON"`
- Don't fail entire search if one provider fails

### 6.2 Deduplication Strategy

**Location:** `src/quantumvitas/io/providers/optimade.py` → `deduplicate_candidates()`

**Deduplication Key:**
```python
def compute_dedup_key(candidate: Candidate) -> tuple:
    """
    Compute deduplication key.
    
    Key: (reduced_formula, space_group_number, nsites)
    """
    return (
        candidate.reduced_formula,
        candidate.space_group_number or 0,  # 0 if unknown
        candidate.nsites,
    )
```

**Merge Strategy:**
```python
def deduplicate_candidates(
    provider_results: List[ProviderResult],
) -> List[AggregatedCandidate]:
    """
    Deduplicate candidates across providers.
    
    Returns:
        List[AggregatedCandidate] with:
        - primary_candidate: Candidate (highest scored)
        - providers: List[str] (all provider IDs that had this structure)
        - aggregated_metadata: Dict (merged metadata from all providers)
    """
    # 1. Group candidates by dedup_key
    # 2. For each group:
    #    - Select primary candidate (highest score)
    #    - Collect all provider IDs
    #    - Merge metadata (prefer experimental > computed > ML)
    # 3. Return aggregated candidates
```

**Aggregation Rules:**
- If same structure appears in COD (experimental) and MP (computed), prefer COD as primary
- Merge provider badges: `providers: ["cod", "mp", "oqmd"]`
- Merge metadata: Prefer experimental values (COD) over computed (MP)

### 6.3 Ranking/Scoring

**Location:** `src/quantumvitas/io/providers/optimade.py` → `rank_candidates()`

**Scoring Function:**
```python
def score_candidate(
    candidate: Candidate,
    provider: ProviderConfig,
    query_formula: str,
) -> float:
    """
    Score a candidate structure.
    
    Returns:
        Score (higher is better, 0.0 to 1.0+)
    """
    score = 1.0
    
    # 1. Provider trust weight (experimental > computed > ML)
    score *= provider.trust_weight
    
    # 2. Formula match (exact match = +0.2, mismatch = -0.5)
    if candidate.reduced_formula == query_formula:
        score += 0.2
    else:
        score -= 0.5
    
    # 3. Partial occupancy penalty (-0.4)
    if candidate.has_partial_occupancy:
        score -= 0.4
    
    # 4. Size penalty (large cells: -0.2 if nsites > 200)
    if candidate.nsites > 200:
        score -= 0.2
    
    # 5. Size bonus (small cells: +0.1 if nsites < 50, +0.2 if < 20)
    if candidate.nsites < 50:
        score += 0.1
    if candidate.nsites < 20:
        score += 0.2
    
    # 6. Space group bonus (+0.05 if known)
    if candidate.space_group_number:
        score += 0.05
    
    return max(0.0, score)
```

**Provider Trust Weights (Constant Table):**
```python
PROVIDER_TRUST_WEIGHTS = {
    "cod": 1.0,      # Experimental (highest)
    "mp": 0.9,       # Computed, high quality
    "jarvis": 0.85,  # NIST quality
    "alexandria": 0.8,  # Computed, large
    "oqmd": 0.8,     # Computed
    "mcloud": 0.8,   # Computed
    "aflow": 0.75,   # Computed, alloys
    "nomad": 0.7,    # Heterogeneous quality
    "matterverse": 0.5,  # ML-predicted (lowest)
}
```

**Ranking:**
- Sort by score (descending)
- Then by nsites (ascending, prefer smaller structures)
- Then by provider order (if scores equal)

**Avoid Provider-Specific Fields in v1:**
- Don't use `_mp_band_gap`, `_alexandria_formation_energy` in v1 ranking
- Keep v1 simple (formula, space group, nsites, provider trust)
- Allow future extension (v2 ranking can use provider-specific fields)

### 6.4 COD OPTIMADE Migration

**Remove COD MySQL Fallback:**
- Delete `search_cod()` function that uses `pymatgen.ext.cod.COD()` (MySQL)
- Replace with COD OPTIMADE HTTP endpoint
- Update all references to use COD OPTIMADE provider config

**Migration Steps:**
1. Add COD OPTIMADE to curated defaults (already in list above)
2. Remove `search_cod()` from `src/quantumvitas/io/online_search.py`
3. Remove `COD_AVAILABLE` check and `pymatgen.ext.cod` import
4. Update tests to mock COD OPTIMADE endpoint (not MySQL)

---

## 7. PubChem Details

### 7.1 Search Implementation

**Location:** `src/quantumvitas/io/providers/pubchem.py`

**Search Strategy:**
```python
def search_pubchem(
    query: str,
    max_results: int = 10,
) -> List[PubChemCandidate]:
    """
    Search PubChem for molecules.
    
    Strategy:
    1. Try name search first (more specific): GET /compound/name/{query}/cids/JSON
    2. If no results, try formula search: GET /compound/formula/{query}/cids/JSON
    3. For each CID, fetch 3D SDF: GET /compound/cid/{cid}/record/SDF?record_type=3d
    4. Parse SDF to structure
    5. Return List[PubChemCandidate]
    """
```

**API Endpoints:**
- Name search: `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/cids/JSON`
- Formula search: `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/formula/{formula}/cids/JSON`
- 3D SDF fetch: `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/record/SDF?record_type=3d`

**Rate Limiting:**
- PubChem rate limit: 5 req/sec
- Strategy: Add 200ms delay between requests
- Use `time.sleep(0.2)` between sequential requests

**Error Handling:**
- If name search returns 404 (not found), try formula search
- If formula search returns 404, return empty list
- If SDF fetch fails (no 3D conformer), skip that CID (don't fail entire search)
- Log warnings for skipped CIDs

### 7.2 SDF Parsing

**Location:** `src/quantumvitas/io/providers/pubchem.py` → `parse_sdf_to_structure()`

**SDF Format:**
- SDF (Structure Data File) is text format
- Contains MOL block with atom coordinates
- Format: `ATOM_LINE: "  C    0.0000    0.0000    0.0000"` (element, x, y, z)

**Parsing Strategy:**
```python
def parse_sdf_to_structure(
    sdf_content: str,
    cid: str,
) -> Structure:
    """
    Parse SDF content to pymatgen Molecule or Structure.
    
    Returns:
        pymatgen Molecule (no lattice, Cartesian coordinates)
    """
    # Option 1: Use pymatgen Molecule.from_str(sdf_content, fmt="sdf")
    # Option 2: Manual parsing (if pymatgen doesn't support SDF well)
    # 
    # For molecules:
    # - Use pymatgen.core.Molecule (not Structure)
    # - Molecule has no lattice (cell=None equivalent)
    # - Coordinates are Cartesian (not fractional)
```

**Structure Schema Mapping:**
- PubChem molecule → pymatgen `Molecule` (not `Structure`)
- `Molecule` has: `species`, `coords` (Cartesian), no `lattice`
- Convert to project's Structure schema:
  ```python
  {
      "structure_type": "molecule",
      "atoms": [
          {"element": "C", "coords": [x, y, z]},
          ...
      ],
      "lattice": None,  # No lattice for molecules
      "pbc": [False, False, False],  # No periodic boundary conditions
  }
  ```

**Fallback Behavior:**
- If 3D SDF not available (only 2D), options:
  1. Return error (preferred - molecules need 3D)
  2. Use 2D coordinates with z=0 (not recommended)
  3. Skip candidate (preferred if 3D unavailable)

### 7.3 Auto-Detection Heuristic

**Location:** `src/quantumvitas/io/providers/__init__.py` → `detect_search_mode()`

**Heuristic:**
```python
def detect_search_mode(query: str) -> Literal["crystal", "molecule", "auto"]:
    """
    Auto-detect search mode from query.
    
    Rules:
    - If query is single element (Si, Fe, Mo) → "crystal"
    - If query matches common crystal formula (MoS2, Fe2O3, SiO2) → "crystal"
    - If query is common molecule name (caffeine, aspirin, ethanol) → "molecule"
    - If query matches organic formula pattern (C6H6, C8H10N4O2) → "molecule"
    - If ambiguous (H2O) → "auto" (search both)
    """
    # Simple heuristics (can be extended)
    if query.lower() in COMMON_MOLECULE_NAMES:
        return "molecule"
    
    if re.match(r'^[A-Z][a-z]?\d*$', query):  # Single element
        return "crystal"
    
    if re.match(r'^C\d+H\d+', query):  # Organic formula
        return "molecule"
    
    if query.lower() in ["h2o", "water"]:
        return "auto"  # Ambiguous
    
    return "auto"  # Default: search both
```

**Implementation:**
- Called by `QVService.OnlineSearch.search()` if `mode="auto"`
- If `mode="auto"`, search both OPTIMADE and PubChem, merge results
- Merge strategy: Sort by score (crystals and molecules can be interleaved)

---

## 8. MP Native API Details

### 8.1 API Key Handling

**Location:** `src/quantumvitas/core/settings.py` → `MaterialsProjectConfig`

**Settings Schema:**
```python
@dataclass
class MaterialsProjectConfig:
    enabled: bool = False  # Default: disabled (requires key)
    api_key: Optional[str] = None  # User-provided API key
    
    def has_key(self) -> bool:
        return self.api_key is not None and self.api_key.strip() != ""
```

**Key Storage:**
- Store in `.qmatsuite/config/settings.json` (global settings)
- Never commit API keys to git (already handled by .gitignore)
- Settings file location: `~/.qmatsuite/config/settings.json` (or platform-specific)

**Key Validation:**
- Test key on first use: Make test request to MP API
- If invalid, log error and disable MP native (fallback to OPTIMADE)
- Don't fail entire search if MP native fails

### 8.2 MP Native Search

**Location:** `src/quantumvitas/io/providers/materials_project.py`

**Implementation:**
```python
def search_materials_project(
    query: str,
    api_key: str,
    max_results: int = 10,
) -> List[MPCandidate]:
    """
    Search Materials Project via native API (mp-api).
    
    Uses mp-api MPRester client.
    """
    from mp_api.client import MPRester
    
    with MPRester(api_key) as mpr:
        docs = mpr.summary.search(
            formula=query,
            num_results=max_results,
            fields=[
                "material_id",
                "structure",
                "band_gap",
                "formation_energy_per_atom",
                "energy_above_hull",
                "is_stable",
                "symmetry",
            ],
        )
    
    return [mp_doc_to_candidate(doc) for doc in docs]
```

**Dependency:**
- `mp-api` package (optional dependency)
- Add to `pyproject.toml`: `mp-api = {version = "...", optional = true}`
- Extras: `pip install qmatsuite[mp-api]` (optional)

**Rich Metadata:**
- Band gap, formation energy, hull distance, stability
- Store in `CandidateDTO.metadata` for GUI display
- Don't use in v1 ranking (keep simple), but expose for future use

### 8.3 Integration with Search

**Location:** `src/quantumvitas/io/providers/__init__.py` → `UnifiedSearch.search()`

**Integration:**
- If MP native enabled and has key, include in parallel search
- Merge MP native results with OPTIMADE results
- Deduplicate: MP native and MP OPTIMADE may return same structures
- Prefer MP native if available (richer metadata)

---

## 9. GUI Wiring Steps

### 9.1 Current GUI Integration

**Current Files:**
- `gui/src/components/panels/OnlineImportPanel.tsx` (search UI)
- `gui/src/types/qv.ts` (RPC type definitions)
- `gui/src/App.tsx` (main app, may have structure import logic)

**Current RPC:**
- Method: `structure_search_online`
- Payload: `{query: str, max_results: int}`
- Response: `{session_id: str, candidates: OnlineCandidate[]}`

### 9.2 Proposed GUI Changes

**File 1: `gui/src/types/qv.ts`**

**Add RPC Type Definitions:**
```typescript
// Add to qv.ts RPC method definitions
structure_search_online: {
  request: {
    query: string;
    mode?: "crystal" | "molecule" | "auto";
    sources?: {
      optimade_provider_ids?: string[];
      pubchem_enabled?: boolean;
      materials_project_enabled?: boolean;
    };
    limit?: number;
    timeout_s?: number;
    refresh_registry?: boolean;
  };
  response: {
    session_id: string;
    candidates: OnlineCandidate[];
    providers_queried: string[];
    partial: boolean;
    query: string;
    mode: string;
  };
};

structure_fetch_online: {
  request: {
    session_id: string;
    candidate_id: string;
    // R3: No project_root - uses global cache
  };
  response: {
    structure: StructureModel;  // Full structure with atoms, lattice, etc.
  };
};

structure_update_online_sources: {
  request: {
    patch: {
      optimade_providers?: Array<{id: string, enabled: boolean}>;
      pubchem_enabled?: boolean;
      materials_project?: {enabled?: boolean, api_key?: string};
      timeout_seconds?: number;
      max_results_per_provider?: number;
      max_total_results?: number;
    };
  };
  response: {
    settings: OnlineSourcesSettings;  // Updated settings after patch
  };
};

structure_list_providers: {
  request: {
    refresh_registry?: boolean;
  };
  response: {
    optimade_providers: ProviderInfo[];
    pubchem_enabled: boolean;
    materials_project_enabled: boolean;
    materials_project_has_key: boolean;
  };
};
```

**Update OnlineCandidate Type:**
```typescript
interface OnlineCandidate {
  candidate_id: string;
  label: string;
  source: string;  // Provider ID
  source_id: string;
  structure_type: "crystal" | "molecule";
  formula: string;
  nsites: number;
  spacegroup?: string;  // For crystals
  providers: string[];  // Aggregated provider badges
  score: number;
  flags: string[];
  metadata: Record<string, any>;
}
```

**File 2: `gui/src/components/panels/OnlineImportPanel.tsx`**

**Add Mode Selection:**
```typescript
// Add state for mode selection
const [mode, setMode] = useState<"crystal" | "molecule" | "auto">("auto");

// Add UI for mode tabs
<div className="online-import-panel__mode-tabs">
  <button
    className={mode === "crystal" ? "active" : ""}
    onClick={() => setMode("crystal")}
  >
    Crystals
  </button>
  <button
    className={mode === "molecule" ? "active" : ""}
    onClick={() => setMode("molecule")}
  >
    Molecules
  </button>
  <button
    className={mode === "auto" ? "active" : ""}
    onClick={() => setMode("auto")}
  >
    All
  </button>
</div>
```

**Update Search Call (F1: No project_root):**
```typescript
const response = await qv.call('structure_search_online', {
  query: query.trim(),
  mode: mode,
  limit: 10,
});
```

**Add Provider Badges:**
```typescript
// In candidate list, show provider badges
{candidate.providers.map(providerId => (
  <span key={providerId} className="provider-badge">
    {providerId.toUpperCase()}
  </span>
))}
```

**Add Structure Type Indicator:**
```typescript
// Show crystal vs molecule icon
{candidate.structure_type === "molecule" ? (
  <span className="structure-type-icon">🧪</span>
) : (
  <span className="structure-type-icon">💎</span>
)}
```

**File 3: `gui/src/components/panels/SettingsPanel.tsx` (if exists, or create new)**

**Add Online Structures Settings Section (R1: Settings Write):**
```typescript
// Add section for online structure providers
// Load providers on mount: call structure_list_providers RPC
// Save changes: call structure_update_online_sources RPC with patch

const [providers, setProviders] = useState<ProviderList | null>(null);

useEffect(() => {
  // Load providers on mount
  qv.call('structure_list_providers', {}).then(response => {
    if (response.ok) {
      setProviders(response.data);
    }
  });
}, []);

const handleProviderToggle = async (providerId: string, enabled: boolean) => {
  const patch = {
    optimade_providers: [{id: providerId, enabled}],
  };
  const response = await qv.call('structure_update_online_sources', {patch});
  if (response.ok) {
    // Reload providers to get updated state
    const reloadResponse = await qv.call('structure_list_providers', {});
    if (reloadResponse.ok) {
      setProviders(reloadResponse.data);
    }
  }
};

// Add section for online structure providers
<div className="settings-section">
  <h3>Online Structure Sources</h3>
  
  {/* OPTIMADE Providers */}
  <div className="settings-subsection">
    <h4>OPTIMADE Providers</h4>
    {providers?.optimade_providers.map(provider => (
      <label key={provider.id}>
        <input
          type="checkbox"
          checked={provider.enabled}
          onChange={(e) => handleProviderToggle(provider.id, e.target.checked)}
        />
        {provider.name} ({provider.structure_count?.toLocaleString() || "?"} structures)
        {!provider.enabled && <span className="hint">(Available, disabled)</span>}
      </label>
    ))}
  </div>
  
  {/* PubChem */}
  <div className="settings-subsection">
    <label>
      <input
        type="checkbox"
        checked={providers?.pubchem_enabled || false}
        onChange={(e) => {
          qv.call('structure_update_online_sources', {
            patch: {pubchem_enabled: e.target.checked}
          }).then(response => {
            if (response.ok) {
              // Reload providers
              qv.call('structure_list_providers', {}).then(reloadResponse => {
                if (reloadResponse.ok) {
                  setProviders(reloadResponse.data);
                }
              });
            }
          });
        }}
      />
      PubChem (Molecules)
    </label>
  </div>
  
  {/* Materials Project API Key (Pitfall 3: Fix chicken-and-egg UX) */}
  <div className="settings-subsection">
    <h4>Materials Project Native API</h4>
    {/* API Key Input: Always visible, not blocked by checkbox (Pitfall 3) */}
    <label>
      MP API Key:
      <input
        type="password"
        placeholder="Enter MP API key (optional)"
        value={mpApiKey}
        onChange={(e) => setMPApiKey(e.target.value)}
        onBlur={() => {
          // Save API key on blur (even if checkbox not enabled yet)
          if (mpApiKey.trim()) {
            qv.call('structure_update_online_sources', {
              patch: {materials_project: {api_key: mpApiKey.trim()}}
            }).then(response => {
              if (response.ok) {
                // Reload providers to update has_key status
                qv.call('structure_list_providers', {}).then(reloadResponse => {
                  if (reloadResponse.ok) {
                    setProviders(reloadResponse.data);
                  }
                });
              }
            });
          }
        }}
      />
      {!providers?.materials_project_has_key && mpApiKey.trim() && (
        <span className="hint">(Key entered, save to enable)</span>
      )}
      {providers?.materials_project_has_key && (
        <span className="hint">(Key configured)</span>
      )}
    </label>
    {/* Enable Checkbox: Not disabled, allows enabling after key entry (Pitfall 3) */}
    <label>
      <input
        type="checkbox"
        checked={providers?.materials_project_enabled || false}
        onChange={(e) => {
          qv.call('structure_update_online_sources', {
            patch: {materials_project: {enabled: e.target.checked}}
          }).then(response => {
            if (response.ok) {
              // Reload providers
              qv.call('structure_list_providers', {}).then(reloadResponse => {
                if (reloadResponse.ok) {
                  setProviders(reloadResponse.data);
                }
              });
            }
          });
        }}
        // NOT disabled - user can enable even if key not yet saved (Pitfall 3)
      />
      Enable Materials Project Native API
      {!providers?.materials_project_has_key && (
        <span className="hint">(Enter API key above first)</span>
      )}
    </label>
  </div>
</div>
```

**File 4: `gui/src/App.tsx` (if structure import logic exists)**

**Update Import Handler:**
- Ensure import handler supports molecules (no lattice)
- Check `structure_type === "molecule"` when importing
- Handle `lattice: null` and `pbc: [false, false, false]` for molecules

### 9.3 Streaming/Partial Results

**Current Pattern:**
- Single RPC response with all results
- No streaming/polling currently

**Proposed Pattern (Keep Simple):**
- Single response with `partial: boolean` flag
- If `partial: true`, show message: "Some providers timed out. Results may be incomplete."
- No server push/websocket (keep it simple)
- No polling (single response is sufficient)

**Future Extension (Out of Scope):**
- If streaming needed later, can add polling endpoint: `structure_search_online_status(session_id)`
- But v1: single response is fine

---

## 10. Test Plan

### 10.0 Repo Audit: Testing/Mocking Utilities (R5)

**Existing Test Infrastructure Audit:**

**HTTP Mocking Tools:**
- **Primary:** `unittest.mock` (standard library) - used extensively in tests
- **Custom:** `tests/contract_crawler/http_recording.py` - HTTPRecorder class for recording/replaying HTTP requests
- **No `responses` library found** - plan must use `unittest.mock.patch` or custom HTTPRecorder
- **No `pytest-httpserver` found** - plan must use `unittest.mock.patch` for HTTP mocking

**Concurrency Utilities:**
- `concurrent.futures.ThreadPoolExecutor` - available in standard library (used in `src/quantumvitas/api/service.py:5107`)
- No `asyncio` usage found in existing codebase - keep synchronous API

**Existing Online Search Tests:**
- `tests/integration/test_optimade_online.py` - Live network tests (marked `@pytest.mark.network`, `@pytest.mark.integration`)
- `tests/unit/test_optimade_offline.py` - Offline tests using fixtures from `tests/data/optimade/`
- `tests/integration/test_pipeline_alignment.py` - Tests online vs project pipeline alignment
- `tests/unit/test_online_structure_supercell.py` - Tests online structure processing
- `tests/unit/test_online_import.py` - Tests online structure import
- `tests/daemon/test_online_candidate_handler.py` - Tests daemon online candidate handlers

**Test Data Locations:**
- `tests/data/optimade/` - OPTIMADE JSON fixtures (referenced in `test_optimade_offline.py`)
- `tests/fixtures/golden_0873ebf/daemon/structure_search_online.json` - Golden RPC fixture
- No PubChem test data exists yet - must be created in implementation

**Mocking Strategy (R5: Non-Flaky Tests):**
- Use `unittest.mock.patch('requests.get')` to mock HTTP calls (not `responses` library)
- Use `unittest.mock.patch('time.time')` to mock clock for TTL tests (deterministic)
- Assert concurrency by counting `ThreadPoolExecutor.submit()` calls (NOT timing)
- Use `unittest.mock.Mock` for provider responses (deterministic JSON)
- All tests must be deterministic (no real network, no timing assertions)

### 10.1 Unit Tests

**Test File 1: `tests/unit/test_optimade_provider_registry.py`**

**Test Cases:**
1. `test_fetch_registry_success()` - Mock successful registry fetch, verify parsing
2. `test_fetch_registry_timeout()` - Mock timeout, verify fallback to curated defaults
3. `test_fetch_registry_invalid_json()` - Mock invalid JSON, verify fallback
4. `test_registry_cache_ttl()` - Verify cache TTL (24h default) using mocked `time.time()`
5. `test_registry_cache_refresh()` - Verify `refresh_registry=True` bypasses cache
6. `test_curated_defaults()` - Verify curated default list is correct
7. `test_registry_providers_disabled_by_default()` - Verify registry providers have `enabled=False` (R6)
8. `test_curated_providers_enabled_by_default()` - Verify curated providers have `enabled=True` (R6)

**Fixtures/Mocks (R5: Use unittest.mock):**
- Use `unittest.mock.patch('requests.get')` to mock `providers.optimade.org/v1/links`
- Mock registry response JSON (sample from actual registry, stored in test file or fixture)
- Mock timeout: `mock_get.side_effect = requests.exceptions.Timeout()`
- Mock clock: `unittest.mock.patch('time.time', return_value=fixed_timestamp)` for TTL tests

**Assertions:**
- Registry fetch returns `List[ProviderConfig]`
- Fallback to curated defaults on error
- Cache key includes registry version
- TTL respected

**Test File 2: `tests/unit/test_optimade_parallel_search.py`**

**Test Cases:**
1. `test_parallel_search_success()` - Mock 3 providers, all succeed, verify merged results
2. `test_parallel_search_timeout()` - Mock 1 provider times out, verify others still return
3. `test_parallel_search_partial_failure()` - Mock 2 succeed, 1 fails, verify partial flag
4. `test_parallel_search_all_timeout()` - All timeout, verify empty results with partial=True
5. `test_parallel_search_deduplication()` - Same structure from 2 providers, verify dedup
6. `test_parallel_search_ranking()` - Verify ranking by score (experimental > computed)

**Fixtures/Mocks (R5: Use unittest.mock, R7: Fix test data reference, Pitfall 2: URL-keyed side_effect):**
- Mock OPTIMADE endpoints: `unittest.mock.patch('requests.get')` with URL-keyed side_effect function (NOT list ordering)
- **CRITICAL (Pitfall 2):** Use side_effect function keyed by URL to ensure deterministic behavior under ThreadPoolExecutor:
  ```python
  def url_keyed_side_effect(url, **kwargs):
      response_map = {
          "https://optimade.materialsproject.org/v1/structures?filter=...": mock_mp_response,
          "https://www.crystallography.net/cod/optimade/v1/v1/structures?filter=...": mock_cod_response,
          "https://alexandria.icams.rub.de/optimade/v1/v1/structures?filter=...": mock_alexandria_response,
      }
      if url in response_map:
          return response_map[url]
      raise requests.exceptions.RequestException(f"Unexpected URL: {url}")
  
  mock_get.side_effect = url_keyed_side_effect
  ```
- **FORBIDDEN:** Do NOT use `side_effect = [response1, response2, ...]` (list ordering is non-deterministic with ThreadPoolExecutor)
- Mock responses with sample OPTIMADE JSON from `tests/data/optimade/` (existing fixtures) or create new fixture file
- Mock timeout: Use URL-keyed function that raises `requests.exceptions.Timeout()` for specific URLs
- Use `ThreadPoolExecutor` in tests (same as implementation)
- Assert concurrency: Count `ThreadPoolExecutor.submit()` calls (NOT timing-based assertions)

**Assertions (R5: Non-Flaky):**
- All providers queried in parallel (count `ThreadPoolExecutor.submit()` calls = len(providers))
- Timeout respected (verify `requests.get(..., timeout=8.0)` called with correct timeout)
- Results merged correctly (verify merged candidate list)
- Deduplication works (same structure from multiple providers → one candidate)
- Ranking correct (COD > MP > others, verify sorted by score)

**Test File 3: `tests/unit/test_pubchem_provider.py`**

**Test Cases:**
1. `test_search_by_name()` - Mock name search, verify CID list
2. `test_search_by_formula()` - Mock formula search, verify CID list
3. `test_search_fallback()` - Name search 404, verify formula search attempted
4. `test_fetch_3d_sdf()` - Mock SDF fetch, verify parsing
5. `test_fetch_3d_sdf_missing()` - No 3D conformer, verify skip (not error)
6. `test_rate_limiting()` - Verify `time.sleep(0.2)` called between requests (mock time.sleep, count calls)
7. `test_parse_sdf_to_structure()` - Verify SDF → Molecule conversion

**Fixtures/Mocks (R5: Use unittest.mock, R7: Create test data):**
- Mock PubChem API: `unittest.mock.patch('requests.get')` with side_effect returning Mock response
- Mock SDF content: Create fixture file `tests/data/pubchem/sample_3d.sdf` with minimal valid SDF content
- Mock 404 for missing compounds: `mock_get.side_effect = requests.exceptions.HTTPError(response=Mock(status_code=404))`

**Assertions:**
- Name search tried first
- Formula search fallback works
- SDF parsed correctly to Molecule
- Rate limiting respected (200ms delay)

**Test File 4: `tests/unit/test_deduplication.py`**

**Test Cases:**
1. `test_dedup_key_computation()` - Verify dedup key: (formula, space_group, nsites)
2. `test_dedup_same_structure_multiple_providers()` - Same structure from MP and COD → one candidate
3. `test_dedup_different_structures()` - Different structures → separate candidates
4. `test_aggregation_provider_badges()` - Verify `providers: ["mp", "cod"]` in aggregated candidate
5. `test_aggregation_metadata_preference()` - Prefer experimental (COD) metadata over computed (MP)

**Fixtures:**
- Create mock candidates with same/different dedup keys
- Use real structure data from tests/data

**Assertions:**
- Dedup key correct
- Aggregation works (multiple providers → one candidate)
- Provider badges correct
- Metadata preference correct (experimental > computed)

**Test File 5: `tests/unit/test_ranking.py`**

**Test Cases:**
1. `test_ranking_experimental_vs_computed()` - COD (experimental) ranks higher than MP (computed)
2. `test_ranking_formula_match()` - Exact formula match gets bonus
3. `test_ranking_partial_occupancy_penalty()` - Partial occupancy gets penalty
4. `test_ranking_size_penalty()` - Large cells (nsites > 200) get penalty
5. `test_ranking_size_bonus()` - Small cells (nsites < 20) get bonus
6. `test_ranking_provider_trust_weights()` - Verify trust weights applied correctly

**Fixtures:**
- Create mock candidates with different attributes
- Use real structure data

**Assertions:**
- Ranking order correct (experimental > computed > ML)
- Score computation correct (formula match, size, etc.)
- Trust weights applied

### 10.2 Live Network Tests (Single File, Skippable) (F2, F3)

**Test File: `tests/integration/test_optimade_online.py` (Update Existing)**

**Policy (F3: Skippable via pytest selection only):**
- ALL live network tests MUST be in this single file (do not create additional network-test files)
- Mark all tests with `@pytest.mark.network` (and register marker in `tests/conftest.py` if repo requires)
- Skipping achieved by pytest selection only (NO env vars, NO CI conditions):
  - `pytest -m "not network"` (excludes network tests)
  - `pytest --ignore=tests/integration/test_optimade_online.py` (excludes entire file)
- Implementer MUST run `pytest tests/integration/test_optimade_online.py -v` (without `-m "not network"` or `--ignore`) to prove tests do not get skipped locally

**New Test Cases to Add (F2: Real Live Network Tests):**

1. `test_registry_fetch_live()`
   - **Purpose:** Verify OPTIMADE provider registry is accessible and returns valid data
   - **Implementation:** Call `fetch_optimade_registry()` (or equivalent API method) with `refresh=True`
   - **Assertions:**
     - Registry fetch succeeds (no exception)
     - Returns list of providers (non-empty)
     - Each provider has required fields (id, name, base_url)
     - At least one curated default provider is present (MP, COD, etc.)
   - **Mark:** `@pytest.mark.integration` and `@pytest.mark.network`

2. `test_optimade_search_mp_live_si()`
   - **Purpose:** Verify MP OPTIMADE endpoint is accessible and returns Si structures
   - **Implementation:** Call `QVService.OnlineSearch.search_structures(query="Si", mode="crystal")` or equivalent
   - **Assertions:**
     - Search succeeds (no exception)
     - Returns candidates (non-empty list)
     - At least one candidate has `source="mp"` or `providers` includes "mp"
     - Candidate has required fields (candidate_id, label, formula, nsites)
     - Formula contains "Si" (case-insensitive)
   - **Mark:** `@pytest.mark.integration` and `@pytest.mark.network`

3. `test_optimade_search_cod_live_salt_or_si()`
   - **Purpose:** Verify COD OPTIMADE endpoint is accessible (replaces MySQL fallback)
   - **Implementation:** Call `QVService.OnlineSearch.search_structures(query="Si", mode="crystal")` or search for common salt (NaCl)
   - **Assertions:**
     - Search succeeds (no exception)
     - Returns candidates (non-empty list)
     - At least one candidate has `source="cod"` or `providers` includes "cod"
     - Candidate has required fields
     - Verifies COD via OPTIMADE HTTP (NOT MySQL)
   - **Mark:** `@pytest.mark.integration` and `@pytest.mark.network`

4. `test_fetch_structure_live_roundtrip()`
   - **Purpose:** Verify full roundtrip: search → fetch structure → verify structure data
   - **Implementation:**
     - Step 1: Call `QVService.OnlineSearch.search_structures(query="Si", mode="crystal", limit=1)`
     - Step 2: Extract first candidate's `candidate_id` and `session_id`
     - Step 3: Call `QVService.OnlineSearch.fetch_structure(ref=StructureRefDTO(session_id=..., candidate_id=...))`
   - **Assertions:**
     - Fetch succeeds (no exception)
     - Returns `StructureDocDTO` with required fields
     - Structure has atoms (non-empty list)
     - Structure has lattice (3x3 matrix for crystals)
     - Structure has formula matching search query
   - **Mark:** `@pytest.mark.integration` and `@pytest.mark.network`

5. `test_pubchem_search_live_caffeine()` (OPTIONAL - only if stable)
   - **Purpose:** Verify PubChem molecule search is accessible (optional, may be fragile)
   - **Implementation:** Call `QVService.OnlineSearch.search_structures(query="caffeine", mode="molecule")`
   - **Assertions (non-fragile):**
     - Search succeeds (no exception) OR gracefully handles PubChem unavailability
     - If succeeds: Returns candidates with `structure_type="molecule"`
     - If succeeds: At least one candidate has `source="pubchem"` or `providers` includes "pubchem"
     - Candidate has required fields (candidate_id, label, formula)
   - **Mark:** `@pytest.mark.integration` and `@pytest.mark.network`
   - **Note:** Mark as optional/skip if PubChem is frequently unavailable

**Existing Tests in File (Keep):**
- `test_optimade_search_basic()` - Keep existing test (may overlap with new tests, that's OK)
- `test_optimade_fetch_structure()` - Keep existing test
- `test_optimade_structure_has_required_fields()` - Keep existing test

**Test Registration (if needed):**
- If `tests/conftest.py` requires marker registration, add:
  ```python
  pytest_plugins = ["pytest_plugins"]
  
  def pytest_configure(config):
      config.addinivalue_line("markers", "network: marks tests as requiring network access")
  ```

**Verification Command (F3: Must run directly to prove not skipped):**
```bash
source .venv/bin/activate
pytest tests/integration/test_optimade_online.py -v
# Must run WITHOUT -m "not network" or --ignore to prove tests execute locally
```

### 10.3 Integration Tests (Network-Free)

**Test File 6: `tests/integration/test_online_search_api.py`**

**Test Cases:**
1. `test_search_structures_crystal_mode()` - Call `QVService.OnlineSearch.search(mode="crystal")`, verify OPTIMADE only
2. `test_search_structures_molecule_mode()` - Call `QVService.OnlineSearch.search(mode="molecule")`, verify PubChem only
3. `test_search_structures_auto_mode()` - Call `QVService.OnlineSearch.search(mode="auto")`, verify both OPTIMADE and PubChem
4. `test_fetch_structure_optimade()` - Call `QVService.OnlineSearch.fetch()` for OPTIMADE candidate, verify structure (R3: no project_root)
5. `test_fetch_structure_pubchem()` - Call `QVService.OnlineSearch.fetch()` for PubChem candidate, verify molecule (R3: no project_root)
6. `test_list_providers()` - Call `QVService.OnlineSearch.list_providers()`, verify provider list
7. `test_update_online_sources()` - Call `QVService.OnlineSearch.update_online_sources()`, verify settings updated (R1)
8. `test_fetch_structure_uses_global_cache()` - Verify fetch uses global cache location, not project cache (R3)

**Fixtures/Mocks (R5: Use unittest.mock):**
- Mock all network calls (OPTIMADE, PubChem, registry) using `unittest.mock.patch('requests.get')`
- Use sample data from `tests/data/optimade/` (existing fixtures) or create new fixtures

**Assertions:**
- API methods return correct DTOs
- Mode filtering works (crystal/molecule/auto)
- 2-step fetch works (search → fetch)
- Provider list correct

**Test File 7: `tests/integration/test_online_search_daemon.py`**

**Test Cases:**
1. `test_daemon_structure_search_online()` - Call daemon RPC `structure_search_online`, verify response
2. `test_daemon_structure_fetch_online()` - Call daemon RPC `structure_fetch_online`, verify structure (R3: no project_root in request)
3. `test_daemon_list_providers()` - Call daemon RPC `structure_list_providers`, verify provider list
4. `test_daemon_update_online_sources()` - Call daemon RPC `structure_update_online_sources`, verify settings updated (R1)
5. `test_daemon_no_kernel_imports()` - Verify daemon doesn't import kernel (gate test)

**Fixtures:**
- Mock network calls
- Use daemon test fixtures from `tests/contract_crawler/`

**Assertions:**
- Daemon RPC methods work
- Response format matches TypeScript types
- No kernel imports in daemon (gate)

**Test File 8: `tests/integration/test_online_search_cli.py`**

**Test Cases:**
1. `test_cli_search_structure_command()` - Run `qv search-structure Si`, verify output
2. `test_cli_search_structure_molecule()` - Run `qv search-structure caffeine --mode molecule`, verify PubChem
3. `test_cli_update_online_sources()` - Run `qv configure online-sources --enable-provider aflow`, verify settings updated (R1)
4. `test_cli_no_kernel_imports()` - Verify CLI doesn't import kernel (gate test)

**CLI Command Wiring (F1: Concrete CLI Steps):**

**File: `src/quantumvitas/cli/main.py`**

**Add new Typer command group (if needed) or add to existing `configure_app`:**

```python
# Add to existing configure_app or create new online_app
online_app = typer.Typer(help="Online structure search and configuration.", no_args_is_help=True)
app.add_typer(online_app, name="online")

@online_app.command("search")
def search_structure_command(
    query: str = typer.Argument(..., help="Search query (formula or molecule name)"),
    mode: str = typer.Option("auto", "--mode", "-m", help="Search mode: crystal, molecule, or auto"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum results to return"),
    timeout: float = typer.Option(8.0, "--timeout", "-t", help="Per-provider timeout in seconds"),
) -> None:
    """
    Search online structures (OPTIMADE crystals + PubChem molecules).
    """
    from quantumvitas.api import QVService
    
    svc = _svc_from_cwd()
    
    # Call API method
    result = svc.OnlineSearch.search_structures(
        query=query,
        mode=mode,  # "crystal", "molecule", or "auto"
        limit=limit,
        timeout_s=timeout,
    )
    
    # Print results
    typer.echo(f"Found {len(result.candidates)} results for '{query}'")
    for i, candidate in enumerate(result.candidates, 1):
        typer.echo(f"{i}. {candidate.label} ({candidate.formula}) - {candidate.source}")
        if candidate.providers:
            typer.echo(f"   Providers: {', '.join(candidate.providers)}")

@online_app.command("configure")
def configure_online_sources_command(
    enable_provider: Optional[str] = typer.Option(None, "--enable-provider", help="Enable provider by ID"),
    disable_provider: Optional[str] = typer.Option(None, "--disable-provider", help="Disable provider by ID"),
    enable_pubchem: Optional[bool] = typer.Option(None, "--enable-pubchem/--disable-pubchem", help="Enable/disable PubChem"),
    mp_api_key: Optional[str] = typer.Option(None, "--mp-api-key", help="Set Materials Project API key"),
) -> None:
    """
    Configure online structure sources (providers, API keys).
    """
    from quantumvitas.api import QVService
    
    svc = _svc_from_cwd()
    
    # Build patch
    patch = {}
    if enable_provider:
        patch.setdefault("optimade_providers", []).append({"id": enable_provider, "enabled": True})
    if disable_provider:
        patch.setdefault("optimade_providers", []).append({"id": disable_provider, "enabled": False})
    if enable_pubchem is not None:
        patch["pubchem_enabled"] = enable_pubchem
    if mp_api_key:
        patch.setdefault("materials_project", {})["api_key"] = mp_api_key
    
    # Call API method
    updated = svc.OnlineSearch.update_online_sources(patch=patch)
    
    typer.echo("✓ Online structure sources updated")
```

**Command Examples:**
- `qv online search Si` - Search for Si (auto mode)
- `qv online search caffeine --mode molecule` - Search for caffeine (molecule mode)
- `qv online configure --enable-provider aflow` - Enable AFLOW provider
- `qv online configure --mp-api-key YOUR_KEY` - Set MP API key

**Fixtures:**
- Mock network calls
- Use CLI test fixtures

**Assertions:**
- CLI commands work
- Output format correct
- No kernel imports in CLI (gate)

### 10.4 Gate Tests

**Test File 9: `tests/gates/test_import_gate.py` (Update Existing)**

**Changes:**
- No changes needed (already enforces CLI/daemon no kernel imports)
- Verify new code doesn't violate (run after implementation)

**Test File 10: `tests/gates/test_daemon_kernel_ban.py` (Update Existing)**

**Changes:**
- No changes needed (already enforces daemon no kernel imports)
- Verify new code doesn't violate (run after implementation)

**Test File 11: `tests/gates/test_api_utils_online_search_removed.py` (New)**

**Purpose:**
- Verify `search_online_structures` removed from `quantumvitas.api.utils`
- Enforce Law H3: Online search is domain capability, not utility

**Test Cases:**
1. `test_utils_no_online_search_reexports()` - Verify no `search_online_structures` in `api.utils`
2. `test_utils_no_fetch_structure_reexports()` - Verify no `fetch_structure_from_optimade` in `api.utils`

**Assertions:**
- `quantumvitas.api.utils` doesn't export online search functions
- All online search via `QVService.OnlineSearch.*` only

### 10.5 Mocking Strategy (R5: Non-Flaky, Deterministic, Pitfall 2: URL-keyed side_effect)

**Network Calls:**
- Use `unittest.mock.patch('requests.get')` for HTTP mocking (standard library, already used in repo)
- Mock all external APIs:
  - `providers.optimade.org/v1/links` (registry)
  - `optimade.materialsproject.org/v1/structures` (OPTIMADE)
  - `pubchem.ncbi.nlm.nih.gov/rest/pug/...` (PubChem)
  - `api.materialsproject.org/...` (MP native)

**CRITICAL (Pitfall 2: URL-keyed side_effect for parallel tests):**
- **FORBIDDEN:** Do NOT use `side_effect = [response1, response2, ...]` (list ordering is non-deterministic with ThreadPoolExecutor)
- **REQUIRED:** Use URL-keyed side_effect function for all parallel OPTIMADE search tests:
  ```python
  def url_keyed_side_effect(url, **kwargs):
      response_map = {
          "https://optimade.materialsproject.org/v1/structures?filter=...": mock_mp_response,
          "https://www.crystallography.net/cod/optimade/v1/v1/structures?filter=...": mock_cod_response,
          # Add all provider URLs to map
      }
      # Handle partial URL matches (query params may vary)
      for key_url, response in response_map.items():
          if key_url in url or url.startswith(key_url.split('?')[0]):
              return response
      raise requests.exceptions.RequestException(f"Unexpected URL: {url}")
  
  mock_get.side_effect = url_keyed_side_effect
  ```
- This ensures tests are stable regardless of ThreadPoolExecutor execution order

**Timeout Testing:**
- Mock timeout using URL-keyed function: Raise `requests.exceptions.Timeout()` for specific URLs
- Verify timeout handling (don't fail entire search)
- Verify `requests.get(..., timeout=8.0)` called with correct timeout parameter

**Provider Registry:**
- Mock registry response with sample JSON (create fixture file `tests/data/optimade/registry_sample.json`)
- Mock registry unavailable (timeout/404) using URL-keyed function: `if "providers.optimade.org" in url: raise requests.exceptions.HTTPError(...)`

**Concurrency Testing (R5: Non-Flaky):**
- Assert concurrency by counting `ThreadPoolExecutor.submit()` calls (NOT timing)
- Verify all providers submitted before any result returned (use `unittest.mock.call_args_list`)
- No timing-based assertions (no `time.time()` comparisons, no `assert elapsed < X`)

**Time-Dependent Behavior (R5: Mock Clock):**
- Mock `time.time()` for cache TTL tests: `unittest.mock.patch('time.time', return_value=fixed_timestamp)`
- Mock `time.sleep()` for rate limiting tests: `unittest.mock.patch('time.sleep')` and count calls

**Deterministic Tests:**
- All tests must be deterministic (no network calls, no timing assertions)
- Use fixed sample data from `tests/data/optimade/` (existing) or create new fixtures
- Mock all time-dependent behavior (cache TTL, timeouts, rate limiting delays)

---

## 11. PR Breakdown (R2: Fixed Sequencing)

**Critical Change (R2):** API capability port + daemon/CLI migration must come FIRST (PR0/PR1) to stop layering violations early. Provider registry/concurrency/dedup/pubchem come AFTER migration.

### PR0: API Capability Port + DTOs + Daemon/CLI Migration + Remove Utils Re-exports

**Goal:** Create minimal API capability port and migrate daemon/CLI to use it (stop layering violations early).

**Files to Create:**
- `src/quantumvitas/api/types/online_search.py` (DTOs: SearchRequestDTO, CandidateDTO, etc.)

**Files to Modify:**
- `src/quantumvitas/api/service.py` (add `QVService.OnlineSearch` nested class with 4 methods: search, fetch, list_providers, update_online_sources)
- `src/quantumvitas/api/utils.py` (remove `search_online_structures`, `fetch_structure_from_optimade` re-exports)
- `src/quantumvitas/daemon/server.py` (update `_handle_structure_search_online` to call `QVService.OnlineSearch.search()`)
- `src/quantumvitas/io/online_cache.py` (migrate cache location to global: `~/.qmatsuite/cache/online_structures/`)
- `tests/integration/test_online_search_api.py` (add API integration tests)
- `tests/gates/test_api_utils_online_search_removed.py` (new gate test)

**Changes:**
1. Create DTOs: `SearchRequestDTO`, `SearchResultDTO`, `CandidateDTO`, `ProviderListDTO`, `OnlineSourcesPatchDTO`, etc.
2. Implement `QVService.OnlineSearch.search_structures()` → calls existing `search_online_structures()` (temporary passthrough)
3. Implement `QVService.OnlineSearch.fetch_structure()` → calls existing `fetch_structure_from_optimade()` (temporary passthrough, no project_root)
4. Implement `QVService.OnlineSearch.list_providers()` → returns minimal provider list (temporary stub)
5. Implement `QVService.OnlineSearch.update_online_sources()` → calls `set_settings()` from `api.utils` (R1)
6. Remove `search_online_structures` from `api.utils` (Law H3)
7. Remove `fetch_structure_from_optimade` from `api.utils` (Law H3)
8. Update daemon to call `QVService.OnlineSearch.*` (not kernel directly)
9. Migrate cache to global location: `~/.qmatsuite/cache/online_structures/` (R3)
10. Add integration tests for API methods (mocked)
11. Add gate test to enforce no utils re-exports

**Acceptance Criteria:**
- API methods work (return DTOs, call through to existing implementation)
- Utils re-exports removed
- Daemon calls API (not kernel)
- CLI can call API (not kernel)
- Cache location migrated to global (not project-specific)
- All tests pass
- Gate tests pass (no kernel imports in CLI/daemon)

**Verification Commands:**
```bash
source .venv/bin/activate
python -m pytest tests/integration/test_online_search_api.py -v --tb=short
python -m pytest tests/integration/test_online_search_daemon.py -v --tb=short
python -m pytest tests/gates/test_api_utils_online_search_removed.py -v --tb=short
python -m pytest tests/gates/test_import_gate.py -v --tb=short
python -m pytest tests/gates/test_daemon_kernel_ban.py -v --tb=short
# F3: Run live network tests directly to prove they execute (not skipped)
pytest tests/integration/test_optimade_online.py -v
```

---

### PR1: Provider Registry + Curated Defaults + Caching + Tests

**Goal:** Implement OPTIMADE provider registry fetching with curated defaults and caching.

**Files to Create:**
- `src/quantumvitas/io/providers/__init__.py` (provider registry module)
- `src/quantumvitas/io/providers/optimade.py` (registry fetching, curated defaults)
- `tests/unit/test_optimade_provider_registry.py`

**Files to Modify:**
- `src/quantumvitas/core/settings.py` (add `OnlineStructuresConfig` to `QMatSuiteSettings`)
- `src/quantumvitas/io/online_cache.py` (extend cache key to include registry version, migrate to global cache location)

**Changes:**
1. Create `ProviderConfig` dataclass (local model, not API DTO)
2. Create `CURATED_DEFAULT_PROVIDERS` list (MP, COD, Alexandria, OQMD, JARVIS, Materials Cloud) with `enabled=True` (R6)
3. Implement `fetch_optimade_registry()` with caching (24h TTL, global cache location)
4. Implement fallback to curated defaults on registry failure
5. Registry providers default to `enabled=False` (R6: user must opt-in)
6. Extend settings schema for provider configuration
7. Store registry providers in settings with `enabled=false` by default
8. Add unit tests for registry fetching, caching, fallback (R5: use unittest.mock)

**Acceptance Criteria:**
- Registry fetch works (mocked in tests)
- Fallback to curated defaults on error
- Cache TTL respected (24h)
- Settings schema extended
- All tests pass

**Verification Commands:**
```bash
source .venv/bin/activate
python -m pytest tests/unit/test_optimade_provider_registry.py -v --tb=short
python -m pytest tests/gates/test_import_gate.py -v --tb=short
python -m pytest tests/gates/test_daemon_kernel_ban.py -v --tb=short
# F3: Run live network tests directly to prove they execute (not skipped)
pytest tests/integration/test_optimade_online.py -v
```

---

### PR2: OPTIMADE Parallel Search + Dedup + Ranking + Tests

**Goal:** Implement parallel OPTIMADE search with deduplication and ranking.

**Files to Create:**
- `src/quantumvitas/io/providers/optimade.py` (parallel search, dedup, ranking)
- `tests/unit/test_optimade_parallel_search.py`
- `tests/unit/test_deduplication.py`
- `tests/unit/test_ranking.py`

**Files to Modify:**
- `src/quantumvitas/io/online_search.py` (refactor to use new provider system, remove old sequential search)

**Changes:**
1. Implement `OPTIMADEProvider.search_parallel()` with `ThreadPoolExecutor`
2. Implement per-provider timeout (8s default)
3. Implement deduplication: `(reduced_formula, space_group_number, nsites)`
4. Implement aggregation: merge same structure from multiple providers
5. Implement ranking: provider trust weights + formula match + size + partial occupancy
6. Remove old sequential search code
7. Add unit tests for parallel search, dedup, ranking

**Acceptance Criteria:**
- Parallel search works (all providers queried simultaneously)
- Timeout handling works (slow providers don't block)
- Deduplication works (same structure from multiple providers → one candidate)
- Ranking correct (experimental > computed > ML)
- All tests pass

**Verification Commands:**
```bash
source .venv/bin/activate
python -m pytest tests/unit/test_optimade_parallel_search.py -v --tb=short
python -m pytest tests/unit/test_deduplication.py -v --tb=short
python -m pytest tests/unit/test_ranking.py -v --tb=short
python -m pytest tests/gates/test_import_gate.py -v --tb=short
```

---

### PR3: COD OPTIMADE + Remove COD MySQL Fallback + Tests

**Goal:** Replace broken COD MySQL fallback with COD OPTIMADE HTTP endpoint.

**Files to Modify:**
- `src/quantumvitas/io/online_search.py` (remove `search_cod()` that uses MySQL)
- `src/quantumvitas/io/providers/optimade.py` (ensure COD OPTIMADE in curated defaults)
- `tests/integration/test_optimade_online.py` (update to mock COD OPTIMADE, not MySQL)

**Changes:**
1. Remove `search_cod()` function (MySQL-based)
2. Remove `pymatgen.ext.cod` import
3. Remove `COD_AVAILABLE` check
4. Ensure COD OPTIMADE in curated defaults (already in PR1)
5. Update all references to use COD OPTIMADE provider
6. Update tests to mock COD OPTIMADE endpoint (not MySQL)

**Acceptance Criteria:**
- COD MySQL code removed
- COD OPTIMADE works (mocked in tests)
- No `pymatgen.ext.cod` imports
- All tests pass

**Verification Commands:**
```bash
source .venv/bin/activate
python -m pytest tests/integration/test_optimade_online.py -v --tb=short
python -m pytest tests/unit/test_optimade_parallel_search.py -v --tb=short
grep -r "pymatgen.ext.cod" src/  # Should return nothing
# F3: Run live network tests directly to prove they execute (not skipped)
pytest tests/integration/test_optimade_online.py -v
```

---

### PR4: PubChem Molecules + Structure Schema Support + Tests

**Goal:** Add PubChem molecule search and support molecular structures (no lattice).

**Files to Create:**
- `src/quantumvitas/io/providers/pubchem.py` (PubChem search, SDF parsing)
- `tests/unit/test_pubchem_provider.py`

**Files to Modify:**
- `src/quantumvitas/io/providers/__init__.py` (add PubChem to unified search)
- `src/quantumvitas/core/models.py` (ensure StructureModel supports molecules: `lattice=None`, `pbc=[False,False,False]`)
- `src/quantumvitas/demo_store/translator.py` (verify molecule support)

**Changes:**
1. Implement `PubChemProvider.search_by_name()` and `search_by_formula()`
2. Implement `PubChemProvider.fetch_3d_sdf()` with rate limiting (200ms delay)
3. Implement `PubChemProvider.parse_sdf_to_structure()` (SDF → pymatgen Molecule)
4. Add auto-detection heuristic (`detect_search_mode()`)
5. Ensure structure schema supports molecules (`lattice=None`, `pbc=[False,False,False]`)
6. Add unit tests for PubChem search, SDF parsing, rate limiting

**Acceptance Criteria:**
- PubChem name/formula search works
- SDF parsing works (SDF → Molecule)
- Rate limiting respected (200ms delay)
- Molecules have `lattice=None` and `pbc=[False,False,False]`
- All tests pass

**Verification Commands:**
```bash
source .venv/bin/activate
python -m pytest tests/unit/test_pubchem_provider.py -v --tb=short
python -m pytest tests/integration/test_online_search_api.py::test_search_structures_molecule_mode -v --tb=short
python -m pytest tests/gates/test_import_gate.py -v --tb=short
```

---

### PR5: MP Native API Optional + Settings + Tests

**Goal:** Add Materials Project native API support (optional, requires API key).

**Files to Create:**
- `src/quantumvitas/io/providers/materials_project.py` (MP native API client)
- `tests/unit/test_materials_project_provider.py`

**Files to Modify:**
- `src/quantumvitas/core/settings.py` (add `MaterialsProjectConfig` with API key)
- `src/quantumvitas/io/providers/__init__.py` (add MP native to unified search)
- `pyproject.toml` (add `mp-api` as optional dependency)

**Changes:**
1. Implement `MaterialsProjectProvider.search_native()` using `mp-api` MPRester
2. Add API key storage in settings (`.qmatsuite/config/settings.json`)
3. Add API key validation (test on first use)
4. Integrate MP native into unified search (if enabled and key present)
5. Add unit tests for MP native search, key validation

**Acceptance Criteria:**
- MP native search works (mocked in tests)
- API key stored in settings (not committed to git)
- API key validation works
- MP native optional (not required by default)
- All tests pass

**Verification Commands:**
```bash
source .venv/bin/activate
python -m pytest tests/unit/test_materials_project_provider.py -v --tb=short
python -m pytest tests/integration/test_online_search_api.py -v --tb=short
python -m pytest tests/gates/test_import_gate.py -v --tb=short
```

---

### PR6: Replace API Passthrough with Provider System Integration

**Goal:** Replace temporary API passthrough (PR0) with actual provider system calls.

**Files to Modify:**
- `src/quantumvitas/api/service.py` (update `QVService.OnlineSearch.*` methods to call provider system instead of passthrough)
- `src/quantumvitas/io/providers/__init__.py` (ensure unified search interface returns local models)
- `src/quantumvitas/api/service.py` (add conversion: provider models → DTOs)

**Changes:**
1. Update `QVService.OnlineSearch.search_structures()` → calls `UnifiedSearch.search()` from providers
2. Update `QVService.OnlineSearch.fetch_structure()` → calls provider fetch methods
3. Update `QVService.OnlineSearch.list_providers()` → calls provider registry
4. Add model-to-DTO conversion layer (provider Candidate → CandidateDTO)
5. Remove old `search_online_structures()` passthrough code

**Acceptance Criteria:**
- API methods call provider system (not passthrough)
- Model-to-DTO conversion works
- All tests pass

**Verification Commands:**
```bash
source .venv/bin/activate
python -m pytest tests/integration/test_online_search_api.py -v --tb=short
python -m pytest tests/integration/test_online_search_daemon.py -v --tb=short
python -m pytest tests/gates/test_import_gate.py -v --tb=short
```

---

### PR7: GUI Wiring + RPC Types + E2E Smoke Tests

**Goal:** Wire GUI to new API and add RPC type definitions.

**Step 0: Repo Audit - Find Settings Panel (Pitfall 4: Mandatory audit step)**

**Before making any changes, run these grep commands to locate existing settings infrastructure:**

```bash
# Find Settings/Preferences panel component
grep -r "SettingsPanel\|PreferencesPanel\|Settings.*Panel" gui/src --include="*.tsx" --include="*.ts"

# Find settings routing/entrypoint
grep -r "settings\|preferences\|configure" gui/src --include="*.tsx" --include="*.ts" -i | grep -i "route\|path\|link"

# Find App.tsx or main routing file
find gui/src -name "App.tsx" -o -name "routes.tsx" -o -name "router.tsx" -o -name "main.tsx"

# Check for existing settings state management
grep -r "useState.*settings\|useSettings\|SettingsContext" gui/src --include="*.tsx" --include="*.ts"
```

**Document findings:**
- If `SettingsPanel.tsx` exists: Note its exact path and how it's mounted (route, tab, modal, etc.)
- If no SettingsPanel exists: Note the main app entrypoint file (App.tsx, routes.tsx, etc.) and how other panels are mounted
- Note the routing mechanism (React Router, tabs, modals, etc.)

**Files to Modify:**
- `gui/src/types/qv.ts` (add RPC type definitions: `structure_search_online`, `structure_fetch_online`, `structure_list_providers`)
- `gui/src/components/panels/OnlineImportPanel.tsx` (add mode selection, provider badges, structure type indicators)
- **Settings Panel (Pitfall 4: Exact mounting location):**
  - **If `gui/src/components/panels/SettingsPanel.tsx` exists:** Add online structures settings section to this file
  - **If SettingsPanel does NOT exist:** Create `gui/src/components/panels/SettingsPanel.tsx` and mount it in the main app entrypoint (App.tsx or routes file identified in audit)
- `gui/src/App.tsx` (or main routing file identified in audit) - verify molecule import support: `lattice=None`, `pbc=[False,False,False]`

**Files to Create (if SettingsPanel doesn't exist):**
- `gui/src/components/panels/SettingsPanel.tsx` (new component with online structures settings section)

**Changes:**
1. **Repo audit:** Run grep commands above, document findings
2. Add RPC type definitions to `qv.ts`
3. Add mode selection UI (Crystals/Molecules/All tabs) to `OnlineImportPanel.tsx`
4. Add provider badges to candidate list in `OnlineImportPanel.tsx`
5. Add structure type indicators (crystal vs molecule icons) to `OnlineImportPanel.tsx`
6. **Add settings UI (Pitfall 4: Exact mounting):**
   - If SettingsPanel exists: Add online structures settings section (provider toggles, MP API key) to existing SettingsPanel
   - If SettingsPanel doesn't exist: Create new SettingsPanel.tsx with online structures section, then mount it in main app entrypoint (add route/tab/modal as appropriate based on audit findings)
7. Verify molecule import works (no lattice)
8. Add E2E smoke tests (optional, can be manual)

**Acceptance Criteria:**
- GUI can search crystals (OPTIMADE)
- GUI can search molecules (PubChem)
- GUI shows provider badges
- GUI shows structure type (crystal vs molecule)
- Settings UI works (provider toggles, MP API key)
- Molecule import works (no lattice)
- E2E tests pass (if added)

**Verification Commands:**
```bash
# Manual GUI testing (no automated E2E yet, or add if time permits)
# Verify:
# 1. Search "Si" → shows crystals from OPTIMADE
# 2. Search "caffeine" → shows molecules from PubChem
# 3. Search "H2O" → shows both crystals and molecules
# 4. Provider badges visible
# 5. Settings panel shows provider toggles
# 6. Import molecule → no lattice in structure file
```

---

## 12. Risks & Mitigations

### 12.1 Provider Flakiness

**Risk:** OPTIMADE providers may be slow, timeout, or return errors.

**Mitigation:**
- Per-provider timeout (8s default, don't block on slow providers)
- Parallel queries (don't wait for one to fail before trying next)
- Fallback to curated defaults if registry unavailable
- Partial results flag: `partial: true` if some providers timed out
- **Note (F4):** Circuit breaker (disable provider after 3 failures) is marked as optional/out of scope for v1. Keep simple: timeout handling and partial results flag are sufficient.

**Test Strategy:**
- Mock timeout scenarios in tests
- Mock HTTP errors (4xx, 5xx)
- Verify search doesn't fail if one provider fails

---

### 12.2 Rate Limiting

**Risk:** PubChem rate limit (5 req/sec) may be exceeded.

**Mitigation:**
- Add 200ms delay between PubChem requests
- Sequential requests (not parallel) for PubChem
- Log warning if rate limit exceeded (don't fail silently)

**Test Strategy:**
- Mock rate limit response (429 status)
- Verify delay between requests (timing test)

---

### 12.3 Schema Mismatch

**Risk:** OPTIMADE providers may return non-standard fields or formats.

**Mitigation:**
- Use only standard OPTIMADE v1 fields in v1 ranking (avoid provider-specific fields)
- Parse response defensively (handle missing fields)
- Log warnings for unexpected fields (don't fail)

**Test Strategy:**
- Mock responses with missing fields
- Mock responses with extra fields
- Verify parsing doesn't fail

---

### 12.4 Registry Changes

**Risk:** OPTIMADE registry URL or format may change.

**Mitigation:**
- Hardcoded curated defaults as fallback
- Cache registry with TTL (24h) to reduce dependency
- Version stamp in cache keys (invalidate on registry update)
- Log warning if registry unavailable (don't fail)

**Test Strategy:**
- Mock registry unavailable (404, timeout)
- Verify fallback to curated defaults

---

### 12.5 SDF Parsing

**Risk:** PubChem SDF format may vary or be invalid.

**Mitigation:**
- Use pymatgen `Molecule.from_str()` if available (robust parser)
- Fallback to manual parsing if pymatgen doesn't support SDF well
- Validate parsed structure (check atom count, coordinates)
- Skip candidate if SDF parsing fails (don't fail entire search)

**Test Strategy:**
- Mock invalid SDF content
- Mock SDF with missing atoms
- Verify parsing doesn't fail entire search

---

### 12.6 API Key Security

**Risk:** MP API keys may be exposed or misused.

**Mitigation:**
- Store in `.qmatsuite/config/settings.json` (not committed to git, already in .gitignore)
- Never log API keys
- Validate key on first use (test request)
- Disable MP native if key invalid (fallback to OPTIMADE)

**Test Strategy:**
- Verify API key not in logs
- Verify key validation works
- Verify fallback to OPTIMADE if key invalid

---

### 12.7 Cache Key Collisions

**Risk:** Cache keys may collide if registry version not included.

**Mitigation:**
- Include registry version in cache keys: `f"{provider_id}:{query}:{filters}:{registry_version}"`
- Include provider ID in cache keys (different providers may have same entry_id)
- Include query and filters in cache keys

**Test Strategy:**
- Verify cache keys unique for different queries
- Verify cache keys include registry version

---

### 12.8 Import Gate Violations

**Risk:** New code may violate import gates (CLI/daemon importing kernel).

**Mitigation:**
- All provider logic in I/O layer (`quantumvitas.io.providers.*`) - providers are network I/O, not kernel-core
- API facade only (`QVService.OnlineSearch.*`)
- Run gate tests after each PR
- Code review: check imports

**Test Strategy:**
- Gate tests run in CI (already enforced)
- Verify no kernel imports in CLI/daemon after implementation

---

## 13. No-Code-Changes Verification Checklist

After each PR, run this checklist to verify no code changes were made during planning:

**Checklist:**
- [ ] No files created (only plan document exists)
- [ ] No files modified (existing code unchanged)
- [ ] No test files created
- [ ] No imports added/removed
- [ ] No function signatures changed
- [ ] Git status shows only plan document (`docs/worklog/STRUCTURE_FETCH_V2_PLAN.md`)

**Verification Command:**
```bash
git status
# Should show only: docs/worklog/STRUCTURE_FETCH_V2_PLAN.md (new file)
```

## 14. Implementation Verification Checklist (F3: Network Tests Policy)

**After Implementation, Verify Network Tests:**

**Checklist:**
- [ ] All live network tests are in `tests/integration/test_optimade_online.py` (single file)
- [ ] All network tests marked with `@pytest.mark.network` (and marker registered if needed)
- [ ] Network tests can be skipped via pytest selection:
  - `pytest -m "not network"` (excludes network tests)
  - `pytest --ignore=tests/integration/test_optimade_online.py` (excludes entire file)
- [ ] **CRITICAL:** Run `pytest tests/integration/test_optimade_online.py -v` (WITHOUT `-m "not network"` or `--ignore`) to prove tests execute locally and are NOT skipped by default
- [ ] No env vars or CI conditions for skipping (pytest selection only)

**Verification Commands (F3: Must run directly to prove not skipped):**
```bash
source .venv/bin/activate
# Must run WITHOUT -m "not network" or --ignore to prove tests execute
pytest tests/integration/test_optimade_online.py -v
# Expected: All network tests execute (may fail if network unavailable, but must NOT be skipped)
```

---

## 15. Summary

This plan provides a detailed, step-by-step implementation guide for Structure Fetch v2 that:

1. **Expands OPTIMADE federation** from 4 endpoints to curated default set (6+ providers) with dynamic registry discovery
2. **Adds PubChem molecule search** for molecular codes (ORCA, Gaussian, etc.)
3. **Adds optional MP native API** for power users with API keys
4. **Maintains layering** (CLI/daemon → API → kernel, no violations)
5. **Removes COD MySQL fallback** (replaced with COD OPTIMADE HTTP)
6. **Implements parallel search** with deduplication and ranking
7. **Extends GUI** with mode selection, provider badges, settings UI
8. **Includes comprehensive tests** (unit, integration, gate tests)

The plan is broken into 7 PRs, each independently mergeable with clear acceptance criteria and verification commands. All risks are identified with mitigations and test strategies.

**Next Steps:**
1. Review this plan with stakeholders
2. Get approval to proceed with implementation
3. Begin PR0: API Capability Port + DTOs + Daemon/CLI Migration (stop layering violations early)

---

**End of Plan**

