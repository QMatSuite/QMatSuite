# Structure Fingerprint Specification

**Version**: 2.1.0  
**Date**: 2026-01-18  
**Status**: RATIFIED (v2.1 - Knife-Edge Fix)

---

## CHANGELOG

| Version | Date | Summary |
|---------|------|---------|
| 2.2.0 | 2026-01-XX | **FIX**: Fingerprint quantization uses deterministic rounding (floor(x/tol+0.5+eps)), removing banker's rounding instability. |
| 2.1.0 | 2026-01-18 | **BREAKING**: Fingerprint no longer wraps/mods coords. Canonicalization is import-time only. Molecule COG shift moved to canonicalization phase. |
| 2.0.0 | 2026-01-18 | Initial unified fingerprint for Structure + Molecule |

---

## 1. Purpose

This specification defines the fingerprinting algorithm for both PBC structures (pymatgen `Structure`) and molecular systems (pymatgen `Molecule`). The fingerprint is used for:

1. **Stale/change detection**: Determine if a relax-produced structure has changed
2. **Content-based deduplication**: Optional dedup during `import_structure()`
3. **Manifest skip logic**: Compare `effective_structure_sha` in incremental runs

**What fingerprint is NOT**:
- A full geometric equivalence test
- Rotationally invariant
- Symmetry-aware

---

## 2. Core Design Principles

### 2.1 Two-Phase Architecture

**CRITICAL**: The system is split into two distinct phases:

| Phase | Responsibility | When | Geometry Transforms |
|-------|---------------|------|---------------------|
| **Canonicalization** | Normalize coordinates to stable representation | Import/read/parse time | YES (wrap, fold, COG shift) |
| **Fingerprint** | Hash the already-canonicalized geometry | On-demand (comparison) | **NO** (quantize + hash only) |

### 2.2 Single Entrypoint Rule

**INVARIANT**: All fingerprint computation MUST go through a single function:

```python
def structure_like_fingerprint(obj: Union[Structure, Molecule], tol_ang: float = 1e-3) -> str
```

This function:
- Dispatches to PBC or Molecule strategies based on object type
- **NEVER** performs any coordinate transformation (wrap, mod, fold, shift)
- Assumes the input is already canonicalized

**FORBIDDEN in fingerprint**:
- `np.mod(frac, 1.0)` or any wrapping
- `coords - cog` or any translation
- Any geometry-altering operation

### 2.3 Knife-Edge Rationale

**Why fingerprint must NOT wrap coordinates:**

The existing PBC canonicalization wraps fractional coordinates to `[-WRAP_TOL, 1-WRAP_TOL)` where `WRAP_TOL = 1e-4`. This deliberately avoids the "knife-edge" at exactly 0 and 1 where tiny numerical noise can flip coordinates between ~0 and ~1.

If fingerprint re-wraps to `[0, 1)` via `mod 1.0`, it resurrects this knife-edge:
- A coordinate at `-1e-6` (valid in the canonical interval) becomes `0.999999` after mod
- This changes the quantized value dramatically and breaks fingerprint stability

**Solution**: Fingerprint trusts that canonicalization already happened. It hashes the coordinates as-is.

---

## 3. Canonicalization Phase

Canonicalization happens **once** at import/read/parse time. It is the only phase that may transform geometry.

### 3.1 PBC Structure Canonicalization (existing, unchanged)

The existing `canonicalize_structure_in_place()` in `structure_viz.py` remains the canonical entry point:

```
PBC Structure Canonicalization:
1. Wrap fractional coordinates to canonical interval [-WRAP_TOL, 1-WRAP_TOL)
2. Uses integer lattice translations only (geometry-preserving)
3. Applied ONCE at import/visualization entry points
```

**Location**: `src/quantumvitas/analysis/structure_viz.py:208-253`

**No changes required** to PBC canonicalization logic.

### 3.2 Molecule Canonicalization (NEW)

Molecules receive a light canonicalization: **translation normalization only**.

```
Molecule Canonicalization:
1. Compute center-of-geometry (COG) = mean of all atomic positions
2. Subtract COG from all positions (center molecule at origin)
3. Do NOT apply rotation normalization
4. Do NOT apply any periodic wrapping
```

**When applied**: At import/read time, same phase as PBC canonicalization.

**Implementation location**: A new helper `canonicalize_molecule_in_place(molecule)` or integrated into a unified `canonicalize_structure_like_in_place(obj)`.

### 3.3 Unified Canonicalization Entrypoint

To ensure consistency, define a single dispatch function:

```python
def canonicalize_structure_like_in_place(obj: Union[Structure, Molecule]) -> None:
    """
    Canonicalize a structure-like object in place.
    
    For Structure: wraps frac coords to [-WRAP_TOL, 1-WRAP_TOL)
    For Molecule: centers at origin (COG shift)
    
    This is the ONLY place geometry transforms happen.
    Must be called at import/read/parse time.
    """
    if isinstance(obj, Molecule):
        _canonicalize_molecule_in_place(obj)
    elif isinstance(obj, Structure):
        canonicalize_structure_in_place(obj)  # existing function
```

---

## 4. Fingerprint Phase

Fingerprint is a **pure** function: it hashes the already-canonicalized geometry without any transformation.

### 4.1 Tolerance Unification

Use a **single tolerance in Angstrom**:

```python
tol_ang = 1e-3  # Angstrom (ratified)
```

For PBC structures, convert to fractional tolerance:

```python
frac_tol = tol_ang / min(|a|, |b|, |c|)  # where a,b,c are lattice vector lengths
```

### 4.2 PBC Structure Fingerprint

**Algorithm** (no geometry transforms):

```python
def _fingerprint_pbc_structure(structure: Structure, tol_ang: float) -> str:
    """Fingerprint for PBC Structure. NO wrapping or mod."""
    # 1. Compute fractional tolerance
    a, b, c = structure.lattice.abc
    frac_tol = tol_ang / min(a, b, c)
    
    # 2. Quantize lattice matrix (in Å) - NO transforms
    # Uses deterministic quantization: q = floor(x / tol + 0.5 + eps)
    lattice_q = quantize_array(structure.lattice.matrix / tol_ang).astype(np.int64)
    
    # 3. Quantize fractional coordinates AS-IS - NO mod, NO wrap
    frac_coords = structure.frac_coords  # Use directly, already canonicalized
    frac_q = quantize_array(frac_coords / frac_tol).astype(np.int64)
    
    # 4. Get species symbols
    species = [site.specie.symbol for site in structure]
    
    # 5. Sort sites deterministically: (element, fx_q, fy_q, fz_q)
    site_data = sorted(zip(species, frac_q), key=lambda x: (x[0], *x[1]))
    
    # 6. Build payload and hash
    payload = _build_pbc_payload(lattice_q, site_data)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()
```

**Quantization Rule** (CRITICAL):

Quantize each numeric scalar `x` as:
```
q = floor(x / tol + 0.5 + eps)
```
where `eps = 1e-12` (dimensionless).

**Rationale**: Banker's rounding (`round()` / `np.round()`) uses ties-to-even at half-integers, causing instability. For example, when `x / tol = N + 0.5` (exactly half-integer), tiny noise can flip between `N` and `N+1`. The deterministic rule `floor(x/tol + 0.5 + eps)` ensures ties always round up, eliminating this instability.

**Knife-edge regression case**: For `tol_ang=1e-3 Å` and lattice min length `Lmin=5.43 Å`, `frac_tol = tol_ang/Lmin`, and `frac=0.25`, we get `0.25/frac_tol = 250*Lmin = 1357.5` (half-integer). This is not rare because many tests use common lattice constants and symmetric fractional coordinates. Deterministic tie-breaking is required.

**Fields included**:
| Field | Format | Quantization |
|-------|--------|--------------|
| Lattice vectors | 3×3 matrix in Å | `quantize_scalar(value / tol_ang)` → int64 |
| Fractional coordinates | Nx3 matrix (as-is) | `quantize_scalar(frac / frac_tol)` → int64 |
| Species symbols | List of strings | Exact |

**Fields excluded**: `__qv_meta__`, provenance, ULIDs, charge, spin, properties.

### 4.3 Molecule Fingerprint

**Algorithm** (no geometry transforms):

```python
def _fingerprint_molecule(molecule: Molecule, tol_ang: float) -> str:
    """Fingerprint for Molecule. NO translation or COG shift."""
    # 1. Get Cartesian coordinates AS-IS - already canonicalized (centered)
    coords = np.array([site.coords for site in molecule])
    
    # 2. Quantize coordinates - NO COG shift here
    # Uses deterministic quantization: q = floor(x / tol + 0.5 + eps)
    coords_q = quantize_array(coords / tol_ang).astype(np.int64)
    
    # 3. Get species symbols
    species = [site.specie.symbol for site in molecule]
    
    # 4. Sort sites deterministically: (element, x_q, y_q, z_q)
    site_data = sorted(zip(species, coords_q), key=lambda x: (x[0], *x[1]))
    
    # 5. Build payload and hash
    payload = _build_molecule_payload(site_data)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()
```

**Quantization Rule**: Same as PBC - uses `quantize_scalar(x, tol)` = `floor(x / tol + 0.5 + eps)` where `eps = 1e-12`.

**Fields included**:
| Field | Format | Quantization |
|-------|--------|--------------|
| Cartesian coordinates | Nx3 matrix in Å (already centered) | `quantize_scalar(value / tol_ang)` → int64 |
| Species symbols | List of strings | Exact |

**Fields excluded**: `__qv_meta__`, provenance, charge, spin_multiplicity, properties.

---

## 5. Payload Format

### 5.1 PBC Payload Format

```
PBC|lat|{a11}|{a12}|...|{a33}|sites|{E1}:{fx1}:{fy1}:{fz1}|{E2}:...
```

Where:
- All numbers are quantized int64 values
- Sites are sorted by (element, fx, fy, fz)

### 5.2 Molecule Payload Format

```
MOL|sites|{E1}:{x1}:{y1}:{z1}|{E2}:{x2}:{y2}:{z2}|...
```

Where:
- All numbers are quantized int64 values
- Sites are sorted by (element, x, y, z)

---

## 6. Call Site Contract

### 6.1 import_structure()

The `import_structure()` function MUST:

1. Load/parse the structure from file or object
2. Call `canonicalize_structure_like_in_place(obj)` to normalize geometry
3. Call `structure_like_fingerprint(obj)` to compute fingerprint
4. Store the canonicalized structure and fingerprint

**FORBIDDEN**:
```python
# OLD - separate hash fork - REMOVE
if isinstance(structure, Molecule):
    fingerprint = hashlib.sha256(json.dumps(structure.as_dict())).hexdigest()
```

**REQUIRED**:
```python
# NEW - unified path
canonicalize_structure_like_in_place(structure)
fingerprint = structure_like_fingerprint(structure, tol_ang=1e-3)
```

### 6.2 Executor effective_structure_sha

**Location**: `src/quantumvitas/execution/executor.py`

Must use the same entrypoint, assuming structure is already canonicalized:
```python
effective_structure_sha = structure_like_fingerprint(structure, tol_ang=1e-3)
```

### 6.3 Relax Artifact Writers

When writing `current.json` after relax:
1. Parse the relaxed geometry from engine output
2. Call `canonicalize_structure_like_in_place(obj)` on the parsed structure
3. Write to `current.json`

When reading `current.json` for promote:
1. Read structure from JSON (pymatgen handles this)
2. Structure is already canonicalized (was canonicalized before writing)
3. Call `structure_like_fingerprint(obj)` directly

---

## 7. Invariants

### 7.1 Fingerprint Stability Invariants

| Invariant | Description | Enforced By |
|-----------|-------------|-------------|
| **Roundtrip stable** | `fingerprint(read(write(obj))) == fingerprint(obj)` | Canonicalization at write/read |
| **Noise tolerance** | Perturbations < tol_ang do not change fingerprint | Quantization |
| **Deterministic** | Same input always produces same fingerprint | Sorted payload |
| **Translation invariant (Molecule)** | Different origins → same fingerprint | Canonicalization (COG shift at import) |
| **Wrap invariant (PBC)** | Coords shifted by integer lattice → same fingerprint | Canonicalization (wrap at import) |

### 7.2 NOT Enforced by Fingerprint

| Property | Status |
|----------|--------|
| Coordinate wrapping | Canonicalization phase only |
| COG centering | Canonicalization phase only |
| Rotational invariance | NOT implemented |
| Symmetry equivalence | NOT implemented |

---

## 8. File Layout

```
src/quantumvitas/core/structure_fingerprint.py
├── structure_like_fingerprint()      # Unified entry point (NO transforms)
├── _fingerprint_pbc_structure()      # PBC implementation (NO mod/wrap)
├── _fingerprint_molecule()           # Molecule implementation (NO COG shift)
├── _build_pbc_payload()              # Payload builder
├── _build_molecule_payload()         # Payload builder
├── structure_fingerprint()           # Backward compat wrapper
├── structures_semantically_equal()   # LEGACY: belt-and-suspenders verification only (uses np.mod)
└── canonicalize_structure_for_identity()  # LEGACY: only used by structures_semantically_equal (uses np.mod)

src/quantumvitas/core/structure_canonicalize.py  (NEW or extend existing)
├── canonicalize_structure_like_in_place()  # Unified canonicalization entry
├── _canonicalize_molecule_in_place()       # Molecule COG shift
└── (uses existing canonicalize_structure_in_place for PBC)
```

---

## 9. Implications for Implementation

Cursor Auto must implement:

1. **Remove `np.mod(frac, 1.0)` from `_fingerprint_pbc_structure()`** - use frac_coords directly
2. **Remove COG shift from `_fingerprint_molecule()`** - assume already centered
3. **Add `_canonicalize_molecule_in_place()`** - COG shift logic
4. **Add `canonicalize_structure_like_in_place()`** - dispatch to PBC or Molecule canonicalization
5. **Update `import_structure()`** to call canonicalization before fingerprint
6. **Update relax handlers** to canonicalize structures before writing `current.json`
7. **Update tests** per the test matrix

---

## Appendix A: Tolerance Rationale

**Why tol_ang = 1e-3 Å?**

- Typical relaxation convergence: ~1e-4 Å
- Parser float noise: ~1e-10 Å
- 1e-3 Å provides safe margin for stale detection without false positives from noise

**Why COG instead of principal axes for Molecule?**

- Simpler: no eigenvalue computation
- Stable: no sign ambiguity or axis ordering issues
- Sufficient: we only need translation invariance, not rotation invariance

---

## Appendix B: Migration Checklist

- [ ] Remove `np.mod()` from PBC fingerprint
- [ ] Remove COG shift from Molecule fingerprint  
- [ ] Add `_canonicalize_molecule_in_place()`
- [ ] Add `canonicalize_structure_like_in_place()` dispatch
- [ ] Update `import_structure()` to call canonicalization
- [ ] Update relax handlers to canonicalize before writing
- [ ] Update tests per test matrix
- [ ] Verify knife-edge regression test passes
