# Demo Postmortem Fixes — Worklog

## Context

An agent ran a fresh Al band structure calculation. Issues surfaced:
1. bandspw crashed due to `occupations=fixed` on a metal
2. Knowledge base didn't help agent diagnose the crash
3. PNG plot missing Fermi level, high-symmetry labels, energy shift
4. ASCII chart for bands unreadable (12 overlaid series, same marker)

---

## Phase 0: Investigation

### 0.1 Demo Directory
- Demo at `~/qmatsuite-demo/calculations/al_bands/`
- Raw outputs in `raw/`: scf.out, bands.out, bands.bands.dat.gnu
- PNG at `bands_step1.png`

### 0.2 bands.dat.gnu File
- 3624 lines, 12 blank-line-separated blocks = 12 bands
- Each block: ~300 (k-distance, energy) pairs
- Energy range: ~-3.6 to ~22.5 eV (absolute, not Fermi-shifted)

### 0.3 PNG Examination
Confirmed all three rendering defects:
- No Fermi level reference line
- No high-symmetry k-point labels (Gamma, X, W, etc.)
- Y-axis shows absolute energy, not E - E_F

### 0.4 render_meta Trace
- `BandStructure.to_primitives()` correctly populates:
  - `render_meta.reference_energy` = fermi_energy (7.9206 eV for Al)
  - `render_meta.markers` = high-symmetry k-points with `axis="x"`
- The data is available; renderers just weren't using it

### 0.5 Matplotlib Renderer
- `_plot_bands()` only checked markers for "fermi" in label
- Never used `reference_energy` for energy shifting
- Never used `axis="x"` markers for k-point labels

---

## Phase 1: Matplotlib Renderer Fixes

**File:** `src/quantumvitas/mcp/renderers/matplotlib_renderer.py`

Rewrote `_plot_bands()`:
- Energy shift: `y_data = s.y - e_fermi` when reference_energy available
- Fermi line: `ax.axhline(0.0, color="red", linestyle="--")` at shifted zero
- K-point labels: filter markers with `axis="x"`, use `ax.set_xticks()` + `ax.set_xticklabels()`
- Vertical lines at each high-symmetry point
- Y-axis label: "E - E_F (eV)" when shifted

Updated `_plot_dos()`:
- Checks `reference_energy` first for Fermi line, falls back to markers

## Phase 2: plotext Integration

**New file:** `src/quantumvitas/mcp/renderers/plotext_renderer.py` (~130 lines)
- `render_bundle_with_plotext()` — primary ASCII renderer
- `_render_bands_plotext()` — specialized: E-shift, Fermi line, k-point xticks
- `_render_generic_plotext()` — convergence, DOS, trajectory
- ANSI stripping via `re.sub(r"\x1b\[[0-9;]*m", "", result)`

**Modified:** `ascii_renderer.py`
- `render_bundle_to_ascii()` now tries plotext first, falls back to TerminalChart

**Dependency:**
- Added `"plotext>=5.2"` to `pyproject.toml` base dependencies (always installed)

**Tests:** 7 new tests in `TestPlotextRenderer` class (test_terminal_chart.py):
- plotext available, convergence/DOS/bands render, Fermi shift, no ANSI codes, box-drawing chars

## Phase 3: Occupation Defaults

**File:** `src/quantumvitas/calculation/step_defaults.py`

Added to SYSTEM namelist for qe_scf, qe_nscf, qe_bandspw, qe_relax, qe_md:
```python
"occupations": "smearing",
"smearing": "gaussian",
"degauss": 0.01,
```

**Knowledge entries** (3 new in `builtin_entries.py`):
1. Metal occupation crash recovery (principle grade) — occupations=fixed causes IEEE crashes on metals
2. bandspw IEEE crash debugging (finding grade) — bands step inherits occupations from SCF
3. degauss guidance (observation grade) — degauss=0.01 Ry universally safe

## Phase 4: Test Suite + Validation

### Test fixes
- `tests/unit/test_api_service_steps.py::test_add_step_to_calculation_with_defaults`:
  Updated assertion from "occupations NOT in defaults" to "occupations == smearing, smearing == gaussian, degauss == 0.01" to match intentional default change.

### Final results
```
6259 passed, 4 skipped, 0 failed
```

### Files modified (summary)
| File | Change |
|------|--------|
| `renderers/matplotlib_renderer.py` | Rewrote _plot_bands (E-shift, Fermi, k-labels), updated _plot_dos |
| `renderers/plotext_renderer.py` | NEW — primary ASCII renderer using plotext |
| `renderers/ascii_renderer.py` | plotext-first dispatch in render_bundle_to_ascii |
| `renderers/__init__.py` | Added plotext_renderer exports |
| `calculation/step_defaults.py` | occupations/smearing/degauss defaults for 5 QE steps |
| `mcp/knowledge/builtin_entries.py` | 3 new knowledge entries |
| `pyproject.toml` | plotext>=5.2 base dependency |
| `tests/mcp/test_terminal_chart.py` | 7 new plotext tests |
| `tests/unit/test_api_service_steps.py` | Updated assertion for new defaults |
