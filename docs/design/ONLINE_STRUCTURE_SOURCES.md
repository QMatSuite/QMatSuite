# Online Structure Sources — Design & Research Document

**Date:** 2026-02-11
**Status:** Proposal (pre-implementation)

---

## 1. Current State

QMatSuite currently fetches structures from **two sources**:

| Source | Protocol | Auth | Status |
|--------|----------|------|--------|
| OPTIMADE (Materials Project, Materials Cloud) | OPTIMADE v1 REST | None | Working |
| COD (Crystallography Open Database) | pymatgen.ext.cod (MySQL) | None | Unreliable — requires local MySQL file that most users don't have |

### How It Works Today

The implementation lives in `src/quantumvitas/io/online_search.py`:

1. **OPTIMADE search** — tries endpoints in order:
   - `https://optimade.materialsproject.org` (primary)
   - `https://optimade.materialscloud.org/main/mc3d-pbe-v1` (fallback)
   - `https://optimade.materialscloud.org/main/mc3d-pbesol-v2` (fallback)
   - `https://optimade.materialscloud.org/main/mc3d-pbesol-v1` (fallback)
2. **COD fallback** — only if OPTIMADE returns zero results. Uses `pymatgen.ext.cod.COD()` which needs a local MySQL database file. Silently fails for most users.
3. **2-step fetch** — OPTIMADE search returns metadata only; full structure is fetched on demand when the user clicks a candidate.
4. **Cache** — SQLite with msgpack-serialized structures, 30-day TTL (`online_cache.py`).

### Problems

- **Only 1 working source in practice** — COD's pymatgen integration is broken for most users (MySQL dependency). Users effectively only get Materials Project OPTIMADE results.
- **Only 4 OPTIMADE endpoints** — The OPTIMADE ecosystem has 19+ live providers with ~27 million structures. We query at most 4.
- **No molecular structures** — ORCA, Gaussian, Psi4, PySCF, and xTB users need molecules, not crystals. No source for that today.
- **No 2D materials** — No dedicated 2D sources despite engine support.
- **No user configuration** — Cannot add/remove providers, set API keys, or configure preferences.

---

## 2. Landscape of Online Structure Sources

### 2.1 Zero-Friction Sources (No API Key Required)

These databases provide fully open REST APIs. No registration, no API key, no friction.

#### A. OPTIMADE Federation (Crystals — Computed + Experimental)

OPTIMADE is a standardized REST API protocol. One client queries all providers with the same code. **19 live providers** serve **~27 million structures**.

| Provider | ID | Base URL | Structures | Type | Notes |
|----------|-----|----------|------------|------|-------|
| **COD** | `cod` | `https://www.crystallography.net/cod/optimade/v1` | ~530K | Experimental | Largest experimental DB. NO MySQL needed via OPTIMADE! |
| **Alexandria** | `alexandria` | via index meta-DB | ~5.8M | Computed (DFT) | Largest free computed DB. 3D+2D+1D. PBE/PBEsol/SCAN. |
| **AFLOW** | `aflow` | via index meta-DB | ~4M | Computed (DFT) | Alloys, intermetallics, prototypes. |
| **OQMD** | `oqmd` | `http://oqmd.org/optimade/v1` | ~1.3M | Computed (DFT) | Thermodynamic stability focus. |
| **JARVIS** | `jarvis` | `https://jarvis.nist.gov/optimade/jarvisdft/v1` | ~80K | Computed (multi) | DFT-3D, DFT-2D, ML, classical. NIST-hosted. |
| **NOMAD** | `nmd` | via index meta-DB | ~13M calcs | Computed | Heterogeneous community uploads. |
| **Materials Cloud** | `mcloud` | `https://www.materialscloud.org/optimade/main` | varies | Computed | MC3D databases, SSSP, community datasets. |
| **Materials Project** | `mp` | `https://optimade.materialsproject.org` | ~154K | Computed (DFT) | Gold standard computed. OPTIMADE endpoint is free. |
| **2DMatPedia** | `twodmatpedia` | via index meta-DB | ~6K | Computed (2D) | Monolayer structures. |
| **Matterverse** | `matterverse` | via index meta-DB | ~31M | ML-predicted | Hypothetical materials. Use with caution. |
| **Theoretical COD** | `tcod` | via index meta-DB | varies | Computed | Complement to experimental COD. |
| **CMR (C2DB)** | `cmr` | via index meta-DB | ~15K | Computed (2D) | Best 2D materials database. DTU Denmark. |
| **Open Materials DB** | `omdb` | `https://optimade-index.openmaterialsdb.se` | varies | Computed | Electronic structure focus. |
| **odbx** | `odbx` | `https://optimade-index.odbx.science` | varies | Computed | Ab initio structure prediction. |
| **MatCloud** | `matcloud` | via index meta-DB | varies | Computed | Chinese materials database. |
| **MPDD** | `mpdd` | via index meta-DB | varies | Computed | Material-Property-Descriptor DB. |

**Key insight:** COD via OPTIMADE is the fix for our broken COD fallback — same database, no MySQL dependency, just HTTP.

**OPTIMADE filter syntax** (works on all providers):
```
chemical_formula_reduced="Si2O"
elements HAS ALL "Si","O"
elements HAS ANY "Fe","Co","Ni"
nelements=2
nsites<100
```

**Provider-specific properties** (non-standard but useful):
- Alexandria: `_alexandria_band_gap`, `_alexandria_hull_distance`, `_alexandria_formation_energy`
- JARVIS: formation energy, band gap via their properties
- Materials Project: `_mp_band_gap`

#### B. COD REST API (Crystals — Experimental)

In addition to OPTIMADE, COD has a native REST API that requires no MySQL:

```
https://www.crystallography.net/cod/result?formula=SiO2&format=json
```

Supports filtering by formula, elements, space group, lattice parameters, volume, journal, year, DOI. Direct CIF download: `https://www.crystallography.net/cod/{ID}.cif`

This is a **better replacement** for our current broken `pymatgen.ext.cod` integration.

#### C. PubChem (Molecules — For Molecular Codes)

| Field | Detail |
|-------|--------|
| **API** | `https://pubchem.ncbi.nlm.nih.gov/rest/pug/` |
| **Auth** | None |
| **Structures** | ~116M compounds |
| **Type** | Molecules only (no crystals) |
| **Rate limit** | 5 req/sec |
| **Python lib** | `pubchempy` |
| **3D coords** | Yes, computed conformers |
| **Relevance** | ORCA, Gaussian, Psi4, PySCF, xTB users |

```python
# Search by name
GET https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/caffeine/record/SDF?record_type=3d
# Search by formula
GET https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/formula/C8H10N4O2/cids/JSON
# Get 3D SDF by CID
GET https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/2519/record/SDF?record_type=3d
```

PubChem fills a critical gap: **molecular structures for molecular codes**. A user running ORCA on caffeine shouldn't need to build the molecule by hand. PubChem provides 3D conformers for most small molecules.

#### D. AFLOW REST API (Crystals — Computed)

Native REST API in addition to OPTIMADE:
```
https://aflowlib.org/API/aflux/?species(Si),nspecies(1),paging(0,10)
```
AFLUX query language. No auth. ~4M structures. Good for alloys and prototypes.

#### E. RCSB PDB (Biomolecular Structures)

| Field | Detail |
|-------|--------|
| **API** | `https://data.rcsb.org/rest/v1/` + search at `https://search.rcsb.org/` |
| **Auth** | None |
| **Structures** | ~220K experimental biomolecular structures |
| **Type** | Proteins, nucleic acids, ligands |
| **Relevance** | QM/MM with ORCA, Gaussian; LAMMPS peptide simulations |

Lower priority — niche use case. But worth noting for completeness.

### 2.2 Free-API-Key Sources

These require a free registration + API key. Worth supporting for power users.

#### A. Materials Project (mp-api)

| Field | Detail |
|-------|--------|
| **API** | `https://api.materialsproject.org/` |
| **Auth** | Free API key (register at materialsproject.org) |
| **Python lib** | `mp-api` (MPRester) |
| **Structures** | ~154K + ~380K GNoME |
| **Advantage over OPTIMADE** | Richer metadata: band gap, formation energy, magnetic ordering, elasticity, phase diagrams |

The OPTIMADE endpoint gives structure + basic metadata. The native API gives everything. Worth supporting for users who have a key.

### 2.3 Paid/Institutional Sources (Out of Scope)

| Source | Cost | Notes |
|--------|------|-------|
| ICSD | $5K-20K/year institutional | Gold standard experimental inorganic. No public API. |
| MPDS (Pauling File) | Subscription | Curated experimental. Limited free OPTIMADE. |
| CCDC (Cambridge Structural DB) | Subscription | Organic/metalorganic experimental. |

Not recommended for integration — too much friction.

---

## 3. Recommended Architecture

### 3.1 Three-Tier Strategy

```
Tier 1: OPTIMADE Federation     (zero friction, crystals, ~27M structures)
Tier 2: PubChem                  (zero friction, molecules, ~116M compounds)
Tier 3: Materials Project API    (free key, richer metadata for crystals)
```

### 3.2 OPTIMADE: From 4 Endpoints to Full Federation

**Current:** Hardcoded list of 4 OPTIMADE base URLs, tried sequentially.

**Proposed:** Query multiple OPTIMADE providers in parallel, with a curated default set and user-configurable additions.

#### Default Provider Set (Recommended)

These providers are reliable, high-quality, and cover diverse structure types:

| Provider | Why Include | Structure Count |
|----------|-------------|-----------------|
| Materials Project | Most-used, computed inorganic | ~154K |
| COD (OPTIMADE) | Largest experimental DB, replaces broken MySQL COD | ~530K |
| Alexandria | Largest free computed, includes 2D | ~5.8M |
| OQMD | Good thermodynamic data | ~1.3M |
| JARVIS | NIST-quality, multi-method | ~80K |
| Materials Cloud (mc3d) | Diverse computed datasets | ~80K |

**Optional providers** (user can enable):
- AFLOW (~4M, alloys/prototypes)
- NOMAD (~13M, heterogeneous quality)
- 2DMatPedia (~6K, 2D specialist)
- CMR/C2DB (~15K, 2D specialist)
- Matterverse (~31M, ML-predicted — caveat needed)
- TCOD (theoretical structures)

#### Parallel Query Strategy

```python
# Pseudo-code for parallel OPTIMADE search
async def search_optimade_federation(query, providers, max_per_provider=10):
    """Query multiple OPTIMADE providers in parallel."""
    tasks = [
        fetch_optimade(provider.base_url, query, max_per_provider)
        for provider in providers
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Merge, deduplicate by reduced formula + space group, score, rank
    merged = merge_and_deduplicate(results)
    return sorted(merged, key=lambda c: c.score, reverse=True)
```

Key design decisions:
- **Parallel, not sequential** — Don't wait for one provider to fail before trying the next. Query all enabled providers simultaneously.
- **Timeout per provider** — 8-second timeout per provider. Slow providers just get skipped.
- **Deduplication** — Same structure in COD and Materials Project? Show once, note both sources.
- **Source badge** — Each result shows which provider it came from.

### 3.3 PubChem: Molecular Structures

New capability — fetch molecules by name or formula for molecular codes.

```python
def search_pubchem(query: str, max_results: int = 10) -> list[MoleculeCandidate]:
    """
    Search PubChem for molecular structures.

    Tries name search first (more specific), then formula search.
    Returns 3D conformers as Cartesian coordinates.
    """
    # Step 1: Try name search (e.g., "caffeine", "aspirin")
    cids = pubchem_name_search(query)

    # Step 2: If no name match, try formula (e.g., "H2O", "C6H6")
    if not cids:
        cids = pubchem_formula_search(query)

    # Step 3: Fetch 3D SDF for each CID
    molecules = []
    for cid in cids[:max_results]:
        sdf = fetch_3d_sdf(cid)
        if sdf:
            molecules.append(parse_sdf_to_candidate(sdf, cid))

    return molecules
```

**GUI integration:** The search bar already exists. When the user types "caffeine" or "H2O" and selects "Molecules" tab (or we auto-detect), we search PubChem instead of OPTIMADE.

**Auto-detection heuristic:**
- If query matches an element or common crystal formula (Si, MoS2, Fe2O3) → crystal search
- If query looks like an organic formula (C6H6, C8H10N4O2) or is a common name (caffeine, aspirin, ethanol) → molecule search
- If ambiguous (H2O) → search both, merge results

### 3.4 Materials Project Native API (Optional, Key Required)

For users who set an API key:

```python
def search_materials_project(query: str, api_key: str, max_results: int = 10):
    """Rich search via mp-api when user has a key."""
    from mp_api.client import MPRester
    with MPRester(api_key) as mpr:
        docs = mpr.summary.search(
            formula=query,
            num_results=max_results,
            fields=["material_id", "structure", "band_gap", "formation_energy_per_atom",
                     "energy_above_hull", "is_stable", "symmetry"]
        )
    return [mp_doc_to_candidate(doc) for doc in docs]
```

Richer metadata vs OPTIMADE: band gap, formation energy, hull distance, stability, magnetic ordering.

### 3.5 Configuration

Add to the user's project or global settings:

```yaml
# ~/.qmatsuite/config.yaml or project settings
online_structures:
  # OPTIMADE providers (enabled by default, user can toggle)
  optimade_providers:
    - id: mp
      enabled: true
    - id: cod
      enabled: true
    - id: alexandria
      enabled: true
    - id: oqmd
      enabled: true
    - id: jarvis
      enabled: true
    - id: mcloud
      enabled: true
    # Disabled by default (user can enable)
    - id: aflow
      enabled: false
    - id: nomad
      enabled: false
    - id: matterverse
      enabled: false

  # PubChem (molecules)
  pubchem:
    enabled: true

  # Materials Project native API (optional, needs key)
  materials_project:
    enabled: false
    api_key: ""  # User fills in

  # Timeouts and limits
  timeout_seconds: 8
  max_results_per_provider: 10
  max_total_results: 50
```

---

## 4. GUI Changes

### 4.1 Search Bar Enhancement

Current: Single text input + search button.

Proposed:
```
┌─────────────────────────────────────────────────┐
│  Search: [_caffeine______________] [Search]     │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ Crystals │  │Molecules │  │   All    │      │
│  │ (active) │  │          │  │          │      │
│  └──────────┘  └──────────┘  └──────────┘      │
│                                                  │
│  Sources: MP  COD  Alexandria  OQMD  JARVIS     │
│           ✓    ✓      ✓        ✓      ✓         │
└─────────────────────────────────────────────────┘
```

- **Category tabs**: Crystals / Molecules / All
- **Source indicators**: Show which providers are being queried
- **Auto-detect**: Smart routing based on query text

### 4.2 Results List Enhancement

Current: Label + source badge + flags.

Add:
- **Provider badge** — "COD", "MP", "Alexandria", "OQMD", "PubChem" etc.
- **Structure type indicator** — crystal icon vs molecule icon
- **Quick metadata** — space group for crystals, molecular weight for molecules
- **Data quality indicator** — experimental vs computed vs ML-predicted

### 4.3 Settings Panel

New section in settings for online structure sources:
- Toggle individual OPTIMADE providers on/off
- Toggle PubChem on/off
- Materials Project API key input field
- Test connection button

---

## 5. Implementation Priority

### Phase 1: Fix & Expand OPTIMADE (Highest Impact, Lowest Effort)

1. **Replace broken COD MySQL with COD OPTIMADE** — Same database, HTTP-only, no MySQL dependency
2. **Add Alexandria, OQMD, JARVIS** to the OPTIMADE provider list
3. **Parallel queries** — Query all enabled providers simultaneously (use `concurrent.futures.ThreadPoolExecutor`)
4. **Deduplication** — Merge results across providers by formula + space group hash
5. **Source attribution** — Show which provider each result came from

**Estimated scope:** ~200 lines changed in `online_search.py`, minor GUI updates for provider badges.

### Phase 2: PubChem for Molecules (High Impact)

1. **Add `search_pubchem()`** function — name search + formula search + 3D SDF fetch
2. **SDF parser** — Parse SDF/MOL format to extract 3D Cartesian coordinates (or use pymatgen/openbabel)
3. **GUI category tabs** — Crystals vs Molecules
4. **Auto-detection** — Route queries to crystal vs molecule sources intelligently

**Estimated scope:** ~300 lines new code, new GUI tab component.

### Phase 3: Materials Project Native API (Medium Impact)

1. **Add settings for API key** — GUI + config file
2. **`search_materials_project()`** — Uses `mp-api` MPRester when key is configured
3. **Rich metadata display** — Band gap, formation energy, stability in the detail panel

**Estimated scope:** ~150 lines new code, settings UI work.

### Phase 4: User Configuration (Polish)

1. **Provider settings panel** — Toggle providers on/off
2. **Custom OPTIMADE endpoints** — Users can add their own OPTIMADE-compatible servers
3. **Connection testing** — "Test" button to verify each provider is reachable

---

## 6. OPTIMADE Provider Discovery

The OPTIMADE ecosystem maintains a central provider registry at:
```
https://providers.optimade.org/v1/links
```

Each provider with a live base URL also has an index meta-database that lists its sub-databases:
```
GET https://providers.optimade.org/index-metadbs/{provider_id}/v1/links
```

This can be used for **dynamic provider discovery** — rather than hardcoding base URLs, we can fetch the live registry at startup (with caching). This makes the system self-updating as new providers come online.

**Recommended approach:**
1. Ship with a hardcoded fallback list of known-good base URLs
2. On first search (or periodically), fetch the live registry and cache it
3. Merge with user's enabled/disabled preferences
4. If registry fetch fails, use the hardcoded fallback

---

## 7. Deduplication Strategy

When querying multiple OPTIMADE providers, the same structure may appear in several databases. For example, silicon (diamond cubic) exists in MP, COD, Alexandria, OQMD, JARVIS, AFLOW, and more.

**Deduplication key:** `(reduced_formula, space_group_number, nsites)`

**Merge strategy:**
- Keep the highest-scored entry as primary
- Attach cross-references: "Also available from: COD, OQMD, JARVIS"
- Prefer experimental (COD) for known structures, computed for hypothetical ones

---

## 8. Molecular Structure Handling

Molecules (for ORCA, Gaussian, Psi4, PySCF, xTB) use Cartesian coordinates, not fractional coordinates in a periodic cell. The existing StructureDoc format needs a molecular variant:

```python
# Current crystal format
StructureDoc = {
    "lattice": [[a1], [a2], [a3]],
    "species": ["Si", "Si"],
    "frac_coords": [[0, 0, 0], [0.25, 0.25, 0.25]],
    "comment": "Silicon diamond"
}

# Molecular format (no lattice)
MoleculeDoc = {
    "species": ["O", "H", "H"],
    "cart_coords": [[0.0, 0.0, 0.117], [-0.757, 0.0, -0.469], [0.757, 0.0, -0.469]],
    "charge": 0,
    "multiplicity": 1,
    "comment": "Water"
}
```

Note: ORCA's parser already returns `cart_coords` (not `frac_coords`). This is consistent.

---

## 9. Rate Limiting & Robustness

| Source | Rate Limit | Our Strategy |
|--------|-----------|--------------|
| OPTIMADE (most providers) | Not specified | 1 concurrent request per provider, 8s timeout |
| PubChem | 5 req/sec | Respect with 200ms delay between requests |
| Materials Project | Throttled | Respect (mp-api handles this internally) |

**Retry policy:** No retries on timeout. If a provider is slow, skip it. Users shouldn't wait.

**Circuit breaker:** If a provider fails 3 times in a session, disable it for the rest of the session and log a warning.

---

## 10. Coverage Matrix

After full implementation, structure source coverage by engine type:

| Engine Type | Current Sources | Phase 1 | Phase 2 | Phase 3 |
|-------------|----------------|---------|---------|---------|
| Periodic DFT (QE, VASP, ABINIT, Siesta, CP2K, GPAW) | MP OPTIMADE | +COD, Alexandria, OQMD, JARVIS | — | +MP native |
| Molecular QC (ORCA, Gaussian, Psi4, PySCF) | None | — | +PubChem | — |
| Semi-empirical (xTB) | None | — | +PubChem | — |
| Classical MD (LAMMPS) | MP OPTIMADE | +COD, Alexandria, OQMD, JARVIS | — | — |
| QMC (QMCPACK) | MP OPTIMADE | +COD, Alexandria, OQMD, JARVIS | — | — |
| Many-body (Yambo, W90) | MP OPTIMADE | +COD, Alexandria, OQMD, JARVIS | — | — |

**Key wins:**
- Phase 1: 6x more crystal sources, COD actually works
- Phase 2: Molecular codes go from zero to 116M compounds
- Phase 3: Richer metadata for power users

---

## 11. Dependencies

| Dependency | Phase | Already in project? | Notes |
|-----------|-------|---------------------|-------|
| `requests` | 1, 2 | Yes | HTTP client |
| `pymatgen` | 1, 3 | Yes | Structure objects, MP integration |
| `pubchempy` | 2 | No | Lightweight PubChem client. Alternative: raw REST with `requests` |
| `mp-api` | 3 | No | Materials Project client. Optional — only for users with API key |

**Note on `pubchempy`:** It's a thin wrapper around PubChem's REST API. We could skip it and use `requests` directly (fewer dependencies). The raw REST API is simple enough.

**Note on `mp-api`:** Only needed if user configures an API key. Can be an optional dependency (`extras_require`).

---

## 12. Summary

| What | Current | After |
|------|---------|-------|
| Crystal sources | 1 working (MP OPTIMADE) | 6+ OPTIMADE providers in parallel |
| Experimental structures | 0 (COD broken) | ~530K via COD OPTIMADE |
| Molecular structures | 0 | ~116M via PubChem |
| 2D materials | 0 | ~21K via Alexandria + 2DMatPedia + C2DB |
| ML-predicted | 0 | ~31M via Matterverse (opt-in) |
| Total reachable | ~154K | **~35M+** |
| User friction | None (already zero for OPTIMADE) | Zero for Tier 1+2; free API key for Tier 3 |
| Config | None | Provider toggles, optional API keys |
