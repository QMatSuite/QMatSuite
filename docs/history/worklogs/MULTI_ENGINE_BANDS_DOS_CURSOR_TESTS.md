# Multi-Engine Bands/DOS Test Files — Cursor Auto Instructions

This document contains **mechanical test creation tasks (M1–M5)** for the multi-engine bands/DOS analysis expansion. Every provider listed below is already implemented and smoke-tested. Your job is to write the test files.

## Rules

1. **Follow the VASP test template EXACTLY.** The patterns are in:
   - `tests/drivers/vasp/test_vasp_bands_parser.py` — bands test template
   - `tests/drivers/vasp/test_vasp_dos_parser.py` — DOS test template
2. **Every test imports from the provider module directly** (e.g., `from quantumvitas.drivers.gpaw.parsers.bands import GPAWBandsProvider`)
3. **FIXTURE_DIR** uses `Path(__file__).resolve().parents[2] / "data" / "<fixture_dir>"`
4. **EvidenceBundle** pattern:
   ```python
   evidence = EvidenceBundle(
       primary_raw_dir=FIXTURE_DIR,
       calc_dir=FIXTURE_DIR.parent,
       run_ulid="01TESTRUN",
       calc_ulid="01CALC",
       step_ulids=["01STEP"],
       gen_steps=["<gen_step>"],
       engine_name="<engine>",
       evidence_steps=[],
   )
   ```
5. **`to_primitives()` test** always verifies:
   - Returns `CanonicalPrimitiveBundle`
   - Correct `object_type`
   - Correct axis labels ("k-path"/"Energy" for bands, "Energy"/"DOS" for dos)
   - Correct `provenance_meta.engine_name`
   - Correct arrays keys
   - SHA determinism via `compute_canonical_sha()`
6. **Import pattern at top of every test file:**
   ```python
   from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
   from quantumvitas.core.analysis.evidence import EvidenceBundle
   ```
7. **No sensitive paths** — never use absolute paths, only relative via `Path(__file__)`
8. **Run verification** after writing all tests:
   ```bash
   source .venv/bin/activate && python -m pytest tests/drivers/ -v --tb=short -n auto --dist=loadfile -q
   ```

---

## M1: QE DOS Tests

**File:** `tests/drivers/qe/test_qe_dos_parser.py`
**Fixture dir:** `tests/data/analysis_qe_dos/`
**Fixture files:** `si.dos.dat` (82KB, 2501 data lines, QE dos.x output)
**Provider:** `quantumvitas.drivers.qe.parsers.dos.QEDOSProvider`
**Model:** `quantumvitas.core.analysis.dos.DOS`

### Known fixture values (from smoke test):
- energies: 2501 points
- fermi_energy: 6.133 eV
- No PDOS (no projwfc.x files in fixture)

### Tests to write:

```python
"""Tests for QE DOS parser/provider using real QE fixture output."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.dos import DOS
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.qe.parsers.dos import QEDOSProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_qe_dos"
```

1. `test_can_parse_true_when_dos_dat_exists` — `QEDOSProvider().can_parse(FIXTURE_DIR)` is True
2. `test_can_parse_false_when_no_dos_dat` — `QEDOSProvider().can_parse(tmp_path)` is False
3. `test_parse_returns_dos` — parse() returns `DOS`, meta.object_type == "dos", meta.engine_name == "qe"
4. `test_parse_nedos` — `len(dos.energies) == 2501`
5. `test_parse_energy_range_spans_fermi` — `dos.energies.min() <= dos.fermi_energy <= dos.energies.max()`
6. `test_fermi_energy_value` — `dos.fermi_energy == pytest.approx(6.133, abs=0.01)`
7. `test_total_dos_nonnegative` — `np.all(dos.total_dos >= 0)`
8. `test_to_primitives_valid` — full to_primitives + SHA determinism check
   - `canonical.object_type == "dos"`
   - `canonical.render_meta.axis_labels["x"] == "Energy"`
   - `canonical.render_meta.axis_labels["y"] == "DOS"`
   - `canonical.provenance_meta.engine_name == "qe"`
   - `"energies" in canonical.arrays`
   - `"total_dos" in canonical.arrays`
   - SHA determinism: `compute_canonical_sha(dos.to_primitives()) == compute_canonical_sha(dos.to_primitives())`

---

## M2: ABINIT Bands + DOS Tests

### M2a: ABINIT Bands

**File:** `tests/drivers/abinit/test_abinit_bands_parser.py`
**Fixture dir:** `tests/data/analysis_abinit_bands/`
**Fixture files:** `si_bands_fixedo_DS2_EIG` (41 kpts, 8 bands, Hartree eigenvalues), `si_bands.abo`
**Provider:** `quantumvitas.drivers.abinit.parsers.bands.ABINITBandsProvider`
**Model:** `quantumvitas.core.analysis.band_structure.BandStructure`

### Known fixture values:
- eigenvalues shape: (41, 8) — 41 k-points, 8 bands
- fermi_energy: ~5.812 eV (from .abo)
- Eigenvalues in eV (converted from Hartree)
- k_distances: 41 points, monotonically non-decreasing

### Tests to write:

```python
"""Tests for ABINIT bands parser/provider using real ABINIT fixture output."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.band_structure import BandStructure
from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.abinit.parsers.bands import ABINITBandsProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_abinit_bands"
```

1. `test_can_parse_true_when_eig_exists` — `ABINITBandsProvider().can_parse(FIXTURE_DIR)` is True
2. `test_can_parse_false_when_no_eig` — `ABINITBandsProvider().can_parse(tmp_path)` is False
3. `test_parse_returns_band_structure` — returns BandStructure, meta.object_type == "bands", meta.engine_name == "abinit"
4. `test_eigenvalues_shape` — `bs.eigenvalues.shape == (41, 8)`
5. `test_eigenvalues_in_eV` — eigenvalues should be in eV range (e.g., -20 to +40), NOT Hartree (-0.5 to +1.5). Assert `bs.eigenvalues.max() > 5.0` (would be ~0.5 if still in Hartree)
6. `test_k_distances_monotonic` — `np.all(np.diff(bs.k_distances) >= -1e-10)`
7. `test_k_distances_length` — `len(bs.k_distances) == 41`
8. `test_fermi_energy_from_abo` — `bs.fermi_energy is not None` and `bs.fermi_energy == pytest.approx(5.812, abs=0.1)`
9. `test_to_primitives_valid` — full bundle + SHA check (use "bands" patterns from VASP template)
   - `canonical.object_type == "bands"`
   - `canonical.render_meta.axis_labels["x"] == "k-path"`
   - `canonical.provenance_meta.engine_name == "abinit"`
   - `"k_distances" in canonical.arrays`
   - `"eigenvalues" in canonical.arrays`

### M2b: ABINIT DOS

**File:** `tests/drivers/abinit/test_abinit_dos_parser.py`
**Fixture dir:** `tests/data/analysis_abinit_dos/`
**Fixture files:** `si_doso_DS2_DOS` (1201 pts, Ha energies, Fermi in header), `si_dos.abo`
**Provider:** `quantumvitas.drivers.abinit.parsers.dos.ABINITDOSProvider`
**Model:** `quantumvitas.core.analysis.dos.DOS`

### Known fixture values:
- energies: 1201 points
- fermi_energy: ~5.964 eV (from DOS header, converted from Ha)
- Energies in eV (converted from Hartree)

### Tests to write:

```python
"""Tests for ABINIT DOS parser/provider using real ABINIT fixture output."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.dos import DOS
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.abinit.parsers.dos import ABINITDOSProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_abinit_dos"
```

1. `test_can_parse_true_when_dos_exists` — True for FIXTURE_DIR
2. `test_can_parse_false_when_no_dos` — False for tmp_path
3. `test_parse_returns_dos` — returns DOS, correct meta
4. `test_energies_count` — `len(dos.energies) == 1201`
5. `test_energies_in_eV` — energies span eV range, not Hartree. Assert `dos.energies.max() > 10.0`
6. `test_fermi_energy_present` — `dos.fermi_energy is not None` and `dos.fermi_energy == pytest.approx(5.964, abs=0.1)`
7. `test_energy_range_spans_fermi` — Fermi within energy range
8. `test_to_primitives_valid` — bundle + SHA check (DOS pattern)

---

## M3: Siesta Bands + DOS Tests

### M3a: Siesta Bands

**File:** `tests/drivers/siesta/test_siesta_bands_parser.py`
**Fixture dir:** `tests/data/analysis_siesta_bands/`
**Fixture files:** `si_bands.EIG` (32 kpts, 26 bands, eV eigenvalues), `si_bands.out` (Fermi, BandLines)
**Provider:** `quantumvitas.drivers.siesta.parsers.bands.SiestaBandsProvider`
**Model:** `quantumvitas.core.analysis.band_structure.BandStructure`

### Known fixture values:
- eigenvalues shape: (32, 26) — 32 k-points, 26 bands
- fermi_energy: -4.487 eV (from .out)
- 5 high-symmetry points (from BandLines in .out)

### Tests to write:

```python
"""Tests for Siesta bands parser/provider using real Siesta fixture output."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.band_structure import BandStructure
from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.siesta.parsers.bands import SiestaBandsProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_siesta_bands"
```

1. `test_can_parse_true_when_eig_exists` — True
2. `test_can_parse_false_when_no_eig` — False (tmp_path)
3. `test_parse_returns_band_structure` — returns BandStructure, correct meta (engine_name="siesta")
4. `test_eigenvalues_shape` — `bs.eigenvalues.shape == (32, 26)`
5. `test_k_distances_monotonic` — non-decreasing
6. `test_fermi_energy_present` — `bs.fermi_energy == pytest.approx(-4.487, abs=0.01)`
7. `test_high_symmetry_points` — `len(bs.high_symmetry_points) == 5`
8. `test_to_primitives_valid` — bundle + SHA check

### M3b: Siesta DOS

**File:** `tests/drivers/siesta/test_siesta_dos_parser.py`
**Fixture dir:** `tests/data/analysis_siesta_dos/`
**Fixture files:** `si_dos.DOS` (500 pts), `si_dos.PDOS.xml` (2 atoms, s/p/d orbitals), `si_dos.out` (Fermi)
**Provider:** `quantumvitas.drivers.siesta.parsers.dos.SiestaDOSProvider`
**Model:** `quantumvitas.core.analysis.dos.DOS`

### Known fixture values:
- energies: 500 points
- fermi_energy: -4.487 eV
- PDOS shape: (2, 500, 3) — 2 atoms, 500 energies, 3 orbital types (s, p, d)
- atom_labels: ["Si_1", "Si_2"]
- orbital_labels: ["s", "p", "d"]

### Tests to write:

```python
"""Tests for Siesta DOS parser/provider using real Siesta fixture output."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.dos import DOS
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.siesta.parsers.dos import SiestaDOSProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_siesta_dos"
```

1. `test_can_parse_true_when_dos_exists` — True
2. `test_can_parse_false_when_no_dos` — False (tmp_path)
3. `test_parse_returns_dos` — returns DOS, correct meta
4. `test_energies_count` — `len(dos.energies) == 500`
5. `test_fermi_energy_present` — `dos.fermi_energy == pytest.approx(-4.487, abs=0.01)`
6. `test_pdos_shape` — `dos.pdos.shape == (2, 500, 3)`
7. `test_pdos_atom_labels` — `dos.atom_labels == ["Si_1", "Si_2"]`
8. `test_pdos_orbital_labels` — `dos.orbital_labels == ["s", "p", "d"]`
9. `test_total_dos_nonnegative` — `np.all(dos.total_dos >= 0)`
10. `test_to_primitives_valid` — bundle + SHA check

---

## M4: CP2K Bands + DOS Tests

### M4a: CP2K Bands

**File:** `tests/drivers/cp2k/test_cp2k_bands_parser.py`
**Fixture dir:** `tests/data/analysis_cp2k_bands/`
**Fixture files:** `si_bands.bs` (5 sets, 80 total k-points, 4 bands, eV), `si_bands.out` (no Fermi)
**Provider:** `quantumvitas.drivers.cp2k.parsers.bands.CP2KBandsProvider`
**Model:** `quantumvitas.core.analysis.band_structure.BandStructure`

### Known fixture values:
- eigenvalues shape: (80, 4) — 80 k-points across 5 sets, 4 bands
- fermi_energy: None (not in .out file for this run)
- 6 high-symmetry points: Γ, X, W, L, Γ, K
- Energies already in eV (CP2K .bs uses eV natively)

### Tests to write:

```python
"""Tests for CP2K bands parser/provider using real CP2K fixture output."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.band_structure import BandStructure
from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.cp2k.parsers.bands import CP2KBandsProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_cp2k_bands"
```

1. `test_can_parse_true_when_bs_exists` — True
2. `test_can_parse_false_when_no_bs` — False (tmp_path)
3. `test_parse_returns_band_structure` — returns BandStructure, correct meta (engine_name="cp2k")
4. `test_eigenvalues_shape` — `bs.eigenvalues.shape == (80, 4)`
5. `test_k_distances_length` — `len(bs.k_distances) == 80`
6. `test_k_distances_monotonic` — non-decreasing
7. `test_high_symmetry_points` — `len(bs.high_symmetry_points) == 6`
8. `test_high_symmetry_labels` — labels are `["Γ", "X", "W", "L", "Γ", "K"]`
9. `test_energies_in_eV_range` — eigenvalues in reasonable eV range (-10 to +10)
10. `test_to_primitives_valid` — bundle + SHA check

### M4b: CP2K DOS

**File:** `tests/drivers/cp2k/test_cp2k_dos_parser.py`
**Fixture dir:** `tests/data/analysis_cp2k_dos/`
**Fixture files:** `si_dos-k1-1.pdos` (8 eigenvalues, Si kind, per-orbital projections), `si_dos.out` (Fermi)
**Provider:** `quantumvitas.drivers.cp2k.parsers.dos.CP2KDOSProvider`
**Model:** `quantumvitas.core.analysis.dos.DOS`

### Known fixture values:
- energies: 8 points (CP2K PDOS lists discrete eigenvalues, not a smoothed grid)
- fermi_energy: ~7.715 eV (from .out, converted from Ha)
- PDOS shape: (1, 8, 9) — 1 atomic kind, 8 eigenvalues, 9 orbital types (s, py, pz, px, d-2, d-1, d0, d+1, d+2)
- atom_labels: ["Si_1"]
- orbital_labels: ["s", "py", "pz", "px", "d-2", "d-1", "d0", "d+1", "d+2"]

### Tests to write:

```python
"""Tests for CP2K DOS parser/provider using real CP2K fixture output."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.dos import DOS
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.cp2k.parsers.dos import CP2KDOSProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_cp2k_dos"
```

1. `test_can_parse_true_when_pdos_exists` — True
2. `test_can_parse_false_when_no_pdos` — False (tmp_path)
3. `test_parse_returns_dos` — returns DOS, correct meta (engine_name="cp2k")
4. `test_energies_count` — `len(dos.energies) == 8`
5. `test_fermi_energy_from_out` — `dos.fermi_energy == pytest.approx(7.715, abs=0.1)`
6. `test_pdos_shape` — `dos.pdos.shape == (1, 8, 9)`
7. `test_pdos_atom_labels` — `dos.atom_labels == ["Si_1"]`
8. `test_pdos_orbital_labels` — `dos.orbital_labels == ["s", "py", "pz", "px", "d-2", "d-1", "d0", "d+1", "d+2"]`
9. `test_to_primitives_valid` — bundle + SHA check

---

## M5: GPAW Bands + DOS Tests

### M5a: GPAW Bands

**File:** `tests/drivers/gpaw/test_gpaw_bands_parser.py`
**Fixture dir:** `tests/data/analysis_gpaw_bands/`
**Fixture files:** `bandstructure.json` (ASE format, 60 kpts, 8 bands, eV)
**Provider:** `quantumvitas.drivers.gpaw.parsers.bands.GPAWBandsProvider`
**Model:** `quantumvitas.core.analysis.band_structure.BandStructure`

### Known fixture values:
- eigenvalues shape: (60, 8) — 60 k-points, 8 bands
- fermi_energy: ~5.433 eV (from "reference" in JSON)
- 10 high-symmetry points (from labelseq "GXWKGLUWLK": Γ, X, W, K, Γ, L, U, W, L, K)
- Energies in eV (ASE format stores in eV natively)

### Tests to write:

```python
"""Tests for GPAW bands parser/provider using real GPAW fixture output."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.band_structure import BandStructure
from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.gpaw.parsers.bands import GPAWBandsProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_gpaw_bands"
```

1. `test_can_parse_true_when_bandstructure_json_exists` — True
2. `test_can_parse_false_when_no_bandstructure_json` — False (tmp_path)
3. `test_parse_returns_band_structure` — returns BandStructure, correct meta (engine_name="gpaw")
4. `test_eigenvalues_shape` — `bs.eigenvalues.shape == (60, 8)`
5. `test_k_distances_length` — `len(bs.k_distances) == 60`
6. `test_k_distances_monotonic` — non-decreasing
7. `test_fermi_energy_present` — `bs.fermi_energy == pytest.approx(5.433, abs=0.01)`
8. `test_high_symmetry_points` — `len(bs.high_symmetry_points) == 10`
9. `test_high_symmetry_first_is_gamma` — `bs.high_symmetry_points[0].label == "Γ"`
10. `test_to_primitives_valid` — bundle + SHA check

### M5b: GPAW DOS

**File:** `tests/drivers/gpaw/test_gpaw_dos_parser.py`
**Fixture dir:** `tests/data/analysis_gpaw_dos/`
**Fixture files:** `dos.json` (301 points, fermi_eV=5.358)
**Provider:** `quantumvitas.drivers.gpaw.parsers.dos.GPAWDOSProvider`
**Model:** `quantumvitas.core.analysis.dos.DOS`

### Known fixture values:
- energies: 301 points
- fermi_energy: ~5.358 eV
- No PDOS (total DOS only)

### Tests to write:

```python
"""Tests for GPAW DOS parser/provider using real GPAW fixture output."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.dos import DOS
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.gpaw.parsers.dos import GPAWDOSProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_gpaw_dos"
```

1. `test_can_parse_true_when_dos_json_exists` — True
2. `test_can_parse_false_when_no_dos_json` — False (tmp_path)
3. `test_parse_returns_dos` — returns DOS, correct meta (engine_name="gpaw")
4. `test_energies_count` — `len(dos.energies) == 301`
5. `test_fermi_energy_present` — `dos.fermi_energy == pytest.approx(5.358, abs=0.01)`
6. `test_energy_range_spans_fermi` — Fermi within energy range
7. `test_total_dos_nonnegative` — `np.all(dos.total_dos >= 0)`
8. `test_no_pdos` — `dos.pdos is None`
9. `test_to_primitives_valid` — bundle + SHA check

---

## Verification Checklist

After writing all test files, run:

```bash
# Run just the new test files
source .venv/bin/activate && python -m pytest \
    tests/drivers/qe/test_qe_dos_parser.py \
    tests/drivers/abinit/test_abinit_bands_parser.py \
    tests/drivers/abinit/test_abinit_dos_parser.py \
    tests/drivers/siesta/test_siesta_bands_parser.py \
    tests/drivers/siesta/test_siesta_dos_parser.py \
    tests/drivers/cp2k/test_cp2k_bands_parser.py \
    tests/drivers/cp2k/test_cp2k_dos_parser.py \
    tests/drivers/gpaw/test_gpaw_bands_parser.py \
    tests/drivers/gpaw/test_gpaw_dos_parser.py \
    -v --tb=short

# Then run full suite
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

**Expected new test count:** ~80 tests across 9 files
**Expected total test count:** ~4720+ passed (was 4647 before)

## File Listing

| File | Tests | Status |
|------|-------|--------|
| `tests/drivers/qe/test_qe_dos_parser.py` | 8 | TO CREATE |
| `tests/drivers/abinit/test_abinit_bands_parser.py` | 9 | TO CREATE |
| `tests/drivers/abinit/test_abinit_dos_parser.py` | 8 | TO CREATE |
| `tests/drivers/siesta/test_siesta_bands_parser.py` | 8 | TO CREATE |
| `tests/drivers/siesta/test_siesta_dos_parser.py` | 10 | TO CREATE |
| `tests/drivers/cp2k/test_cp2k_bands_parser.py` | 10 | TO CREATE |
| `tests/drivers/cp2k/test_cp2k_dos_parser.py` | 9 | TO CREATE |
| `tests/drivers/gpaw/test_gpaw_bands_parser.py` | 10 | TO CREATE |
| `tests/drivers/gpaw/test_gpaw_dos_parser.py` | 9 | TO CREATE |
