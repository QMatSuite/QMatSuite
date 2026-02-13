# Quantum ESPRESSO Module Documentation Links

This document lists all QE modules and their official documentation links following the pattern:
`https://www.quantum-espresso.org/Doc/INPUT_{MODULE_NAME}.html`

## Runtime Metadata

**At runtime, QE parameter/namelist membership is driven by `qe_module_parameters.json` via `quantumvitas.data.qe_metadata`.**

### Runtime Access Rules

**`safe_load_metadata()` is the only runtime entry point for QE parameter metadata.**

- **CLI/daemon code must never read `qe_module_parameters.json` directly.**
- All runtime access must go through `quantumvitas.data.qe_metadata` helper functions:
  - `safe_load_metadata()` - Main entry point (raises `RuntimeError` for better error handling)
  - `get_module_param_sections(module)` - Get parameter sections for a module
  - `list_supported_modules()` - List all supported QE modules
  - `get_module_doc_url(module)` - Get documentation URL for a module
  - `get_module_namelists(module)` - Get namelist names for a module
  - Other helper functions in `qe_metadata` module

This ensures:
- Schema version compatibility (v1 or v2)
- Consistent error handling (`RuntimeError` instead of `FileNotFoundError`)
- No direct file I/O in application code
- Future-proofing against schema changes

### QE metadata schema and legacy snapshot

**Runtime uses:**
- `src/quantumvitas/data/qe_module_parameters.json` (schema v2, loaded via `qe_metadata`)
  - This is the active metadata file used by all runtime code.
  - Uses schema v2: `modules → parameters` map where each parameter has:
    - `namelist`: Section name (e.g., "&CONTROL")
    - `name`: Parameter name (e.g., "calculation")
    - `type`: Parameter type (e.g., "CHARACTER", "INTEGER", "REAL", "LOGICAL")
    - `default`: Default value if documented (e.g., "'scf'", "1.0D-6", "REQUIRED")
    - `enum`: List of allowed values where applicable (e.g., ["'scf'", "'nscf'", "'bands'"])
    - `description`: Free-text description from QE documentation
  - Each parameter key is `"&SECTION.param_name"` format.
  - The `qe_metadata` module is schema-aware and provides a stable API regardless of schema version.

**Legacy snapshot:**
- `src/quantumvitas/data/qe_module_parameters.legacy.json`
  - Frozen v1 snapshot, kept for historical reference.
  - Only used by `tools/compare_qe_parameter_maps.py` to compare schemas.
  - Not used by runtime code or tests.

**Tools:**
- `tools/extract_qe_parameters_v1.py` (deprecated, for legacy schema v1)
  - Used to generate the old v1 schema JSON (parameter names only).
  - Kept for historical reference only.
- `tools/extract_qe_parameters_v2.py` (current generator with rich metadata)
  - Scrapes QE HTML documentation directly to extract rich parameter metadata.
  - Extracts: parameter name, type, default value, allowed values (enum), description.
  - Usage: `python tools/extract_qe_parameters_v2.py [--modules pw ph ...] [--cache-dir ...] [--use-cache]`
  - Generates schema v2 JSON with full metadata.
  - Supports caching HTML files locally for offline regeneration.
  
  **Current metadata coverage (as of latest extraction):**
  - Total parameters: 954 across 22 modules (93% of legacy v1 snapshot)
  - Type information: 83% (791/954 parameters with types; card sections have type=None)
  - Default values: 65% (623/954 parameters)
  - Enum/allowed values: 20% (192/954 parameters)
  - Descriptions: 81% (774/954 parameters)
  
  **Note**: Card section parameters (extracted from ToC) have minimal metadata (names only), while namelist parameters (extracted from tables) have rich metadata (type, default, enum, description).
  
  The extractor parses QE HTML documentation structure (parameter tables with type, default, description blocks) to populate these fields. Some parameters may not have defaults (e.g., required parameters), enums (e.g., numeric ranges), or descriptions (edge cases in HTML structure).
- `tools/compare_qe_parameter_maps.py` (schema diff tool)
  - Compares legacy v1 snapshot against current JSON (supports both v1 and v2).
  - Derives sections from current JSON regardless of schema version.
  - Useful for verifying schema migrations and parameter coverage.

**Important:** All new code should access QE metadata only through `quantumvitas.data.qe_metadata` helper functions. Do not open `qe_module_parameters.json` directly. This ensures compatibility when the schema migrates from v1 to v2.

**Runtime entry point:** Use `safe_load_metadata()` for all QE metadata access. CLI/daemon code must never read the JSON file directly.

The JSON file is the source of truth for:
- Module → namelist/section mappings
- Namelist → parameter name lists
- Documentation URLs
- Parameter types, defaults, allowed values, and descriptions (schema v2)

## Schema v2 Rich Metadata Extraction

The v2 extractor (`tools/extract_qe_parameters_v2.py`) directly scrapes Quantum ESPRESSO HTML documentation to extract rich parameter metadata. This replaces the previous v1→v2 converter approach.

### Extraction Process

1. **HTML Download & Caching**: Downloads QE documentation HTML files (e.g., `INPUT_PW.html`) from quantum-espresso.org, with optional local caching for offline regeneration.

2. **Table of Contents Parsing**: Extracts parameter names from the ToC section (similar to v1 extractor) as a reference for validation.

3. **Parameter Table Parsing**: For each parameter, parses HTML table structure:
   - Parameter name and type from table header row
   - Default value from "Default:" row
   - Description from blockquote content
   - Enum values from definition lists (`<dl><dt><tt>value</tt></dt>`) or quoted strings in descriptions

4. **Section Detection**: Handles both namelist sections (e.g., "Namelist: &CONTROL") and card sections (e.g., "Card: K_POINTS").

5. **Schema Assembly**: Builds v2 JSON structure with `schema_version: 2`, `generated_at` timestamp, and `modules` containing `parameters` maps.

### Metadata Coverage Statistics

As of the latest extraction run:

- **Total parameters**: 954 across 22 modules (93% of legacy v1 snapshot)
- **Type information**: 83% coverage (791/954 parameters have types)
  - All namelist parameters (table-based) have type extracted (CHARACTER, INTEGER, REAL, LOGICAL, etc.)
  - Card section parameters (ToC-based) have type=None (they don't have explicit types in HTML)
- **Default values**: 65% coverage (623/954 parameters)
  - Missing defaults typically indicate required parameters or parameters without documented defaults
  - Card section parameters typically don't have documented defaults
- **Enum/allowed values**: 20% coverage (192/954 parameters)
  - Extracted from definition lists in HTML or quoted strings in descriptions
  - Only parameters with discrete allowed values have enums
  - Card section parameters don't have enum information
- **Descriptions**: 81% coverage (774/954 parameters)
  - Most namelist parameters have free-text descriptions from QE documentation
  - Missing descriptions are typically edge cases with unusual HTML structure
  - Card section parameters (extracted from ToC) don't have descriptions

### Validation

The extractor includes optional validation against the legacy v1 snapshot:
- `--validate-against-legacy`: Runs `tools/compare_qe_parameter_maps.py` to compare parameter names
- Helps ensure no parameters were missed during extraction
- Parameter name coverage: V2 has 1069 parameters vs V1's 1024 parameters (104% coverage)
  - **V2 finds more parameters**: All ToC parameters included (v1-style extraction)
  - **All previously missing parameters found**: `celldm`, `cosAB`, `fixed_magnetization`, etc.
  - **Case-sensitive names**: Parameter names preserve original case (X != x)
  - **New in V2**: Some newer parameters and normalized section names
  - See `docs/QE_PARAMETER_VALIDATION_REPORT.md` for detailed analysis
  - Generate fresh report data: `python tools/generate_qe_parameter_validation_report.py`

**Note**: The v2 extractor now follows the exact same strategy as v1: extract ALL parameters from ToC first, then enrich with metadata from HTML tables. This ensures complete coverage with all parameters included.

## Offline Documentation Snapshots

For future work, QE HTML docs can be snapshotted into `resources/qe_docs_raw/` using `tools/snapshot_qe_docs.py`. Those snapshots are not required at runtime; they are only for offline regeneration of parameter metadata.

## Currently Supported Modules (with Documentation)

### Core Modules

1. **PW (pw.x)** - Main DFT code
   - Documentation: https://www.quantum-espresso.org/Doc/INPUT_PW.html
   - Namelists: `&CONTROL`, `&SYSTEM`, `&ELECTRONS`, `&IONS`, `&CELL`

2. **PH (ph.x)** - Phonon calculations
   - Documentation: https://www.quantum-espresso.org/Doc/INPUT_PH.html
   - Namelist: `&inputph`

3. **Q2R (q2r.x)** - q-point to real space conversion
   - Documentation: https://www.quantum-espresso.org/Doc/INPUT_Q2R.html
   - Namelist: `&input`

4. **MATDYN (matdyn.x)** - Phonon frequency calculation
   - Documentation: https://www.quantum-espresso.org/Doc/INPUT_MATDYN.html
   - Namelist: `&input`

### Post-Processing Modules

5. **PP (pp.x)** - Post-processing
   - Documentation: https://www.quantum-espresso.org/Doc/INPUT_PP.html
   - Namelist: `&inputpp`

6. **BANDS (bands.x)** - Band structure calculations
   - Documentation: https://www.quantum-espresso.org/Doc/INPUT_BANDS.html
   - Namelist: `&BANDS`

7. **DOS (dos.x)** - Density of states calculations
   - Documentation: https://www.quantum-espresso.org/Doc/INPUT_DOS.html
   - Namelist: `&DOS`

8. **PROJWFC (projwfc.x)** - Projected wavefunction calculations
   - Documentation: https://www.quantum-espresso.org/Doc/INPUT_PROJWFC.html
   - Namelist: `&PROJWFC`

### Advanced Modules

9. **NEB (neb.x)** - Nudged Elastic Band method
   - Documentation: https://www.quantum-espresso.org/Doc/INPUT_NEB.html
   - Namelist: `&PATH` (plus embedded pw.x input)

10. **CP (cp.x)** - Car-Parrinello molecular dynamics
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_CP.html
    - Namelists: `&CONTROL`, `&SYSTEM`, `&ELECTRONS`, `&IONS`, `&CELL`

11. **LD1 (ld1.x)** - Atomic calculations
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_LD1.html
    - Namelist: `&input`

12. **HP (hp.x)** - Hubbard U parameter calculations
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_HP.html
    - Namelist: `&inputhp`

13. **PWCOND (pwcond.x)** - Conductance calculations
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_PWCOND.html
    - Namelist: `&cond`

## Documentation URL Pattern

All QE module documentation follows a consistent pattern:
```
https://www.quantum-espresso.org/Doc/INPUT_{MODULE_NAME}.html
```

Where `{MODULE_NAME}` is the uppercase version of the executable name (with `.x` removed), with special characters converted:
- Hyphens (`-`) → Underscores (`_`)
- Example: `pwcond.x` → `INPUT_PWCOND.html`
- Example: `band-interpolation.x` → `INPUT_BAND_INTERPOLATION.html`

## Adding New Modules

To add support for a new QE module:

1. **Check if documentation exists**:
   - Convert executable name to uppercase
   - Replace hyphens with underscores
   - Check: `https://www.quantum-espresso.org/Doc/INPUT_{MODULE_NAME}.html`

2. **Add to QEModule enum** in `src/quantumvitas/core/engines/qe_input.py`:
   ```python
   MODULE_NAME = "module"  # module.x - description
   ```

3. **Update detect_module()** method with detection logic

4. **Add to MODULE_NAMELISTS** in `src/quantumvitas/core/engines/qe.py`

5. **Add documentation link** to enum docstring and comments

## Additional Supported Modules (with Documentation)

14. **POSTAHC (postahc.x)** - Post-processing for AHC
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_POSTAHC.html
    - Namelist: `&input`

15. **DYNMAT (dynmat.x)** - Dynamical matrix diagonalization
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_DYNMAT.html
    - Namelist: `&input`

16. **OSCDFT_ET (oscdft_et.x)** - OSCDFT eigenvalue tracking
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_OSCDFT_ET.html
    - Namelist: `&oscdft_et_namelist`

17. **OSCDFT_PP (oscdft_pp.x)** - OSCDFT post-processing
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_OSCDFT_PP.html
    - Namelist: `&oscdft_pp_namelist`

18. **BAND_INTERPOLATION (band_interpolation.x)** - Band interpolation
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_BAND_INTERPOLATION.html
    - Namelist: `&interpolation`

19. **CPPP (cppp.x)** - CP post-processing
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_CPPP.html
    - Namelist: `&inputpp`

20. **D3HESS (d3hess.x)** - Third-order force constants
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_D3HESS.html
    - Namelist: `&input`

21. **PPACF (ppacf.x)** - Post-processing ACF
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_PPACF.html
    - Namelist: `&plot`

22. **PPRISM (pprism.x)** - Post-processing RISM
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_PPRISM.html
    - Namelists: `&inputpp`, `&plot`

## Other QE Modules (No Input Documentation)

The following modules exist in QE but do not have input file documentation or are utility programs without structured input files:

**Note**: These modules either:
- Are utility programs that don't use structured input files
- Have documentation but without input file format specifications
- Are external tools (e.g., Wannier90)

Examples include:
- Utility tools: `alpha2f.x`, `average.x`, `cell2ibrav.x`, `ibrav2cell.x`, `kpoints.x`, `dist.x`
- Plotting tools: `plotband.x`, `plotproj.x`, `plotrho.x`
- Conversion tools: `pw2gw.x`, `pw2bgw.x`, `pw2wannier90.x`, `pwi2xsf.x`
- External interfaces: `wannier90.x` (external tool)
- And many others...

For a complete list of all QE executables, check the `bin` directory of your QE installation.

## Notes

- Not all modules have input files (some are utilities)
- Some modules may use the same input format as other modules
- Documentation availability should be verified before adding support
- When adding new modules, follow the detection logic in `detect_module()` method

