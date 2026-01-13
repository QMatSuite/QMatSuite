# ORCA Integration Implementation Plan (Revised)

**Date**: 2026-01-12
**Status**: Revised Plan Ready for Review
**Scope**: ORCA integration + PySCF/ORCA shared layer (chain semantics)

---

## REVISION NOTES

This document has been revised per user feedback. Key changes:
1. **NO $new_job/Compound**: One chain = one ORCA input with fused keywords (no multi-job syntax)
2. **Chain naming**: Human-debuggable chain keys (`chain01_scf_td`), not step ULIDs
3. **TXT property parsing only**: JSON disabled (`WriteJSONPropertyfile` OFF); parse `.property.txt` directly
4. **Opt/relax out of scope**: MVP handles SCF-rooted single-point chains only
5. **Q1/Q2/Q3 answered**: See Section 13 with repo evidence

---

## 1. Executive Summary

This document provides a concrete implementation plan for:

1. **ORCA Engine Integration**: Add ORCA as a new engine alongside PySCF and QE
2. **Generalized QC Engine Layer**: Extract common quantum chemistry patterns (chain execution) shared by PySCF and ORCA
3. **Single-Job Chain Compilation**: One chain compiles to ONE ORCA input file (no $new_job)
4. **Run Semantics**: Implement Run Calc and Run Step behaviors per specification

### Non-Negotiable Constraints Restated

| Constraint | Description |
|------------|-------------|
| **Calc Independence** | No cross-calc runtime references |
| **Chain = SCF Root + Downstream** | Chains separated by SCF steps |
| **Run Calc** | Execute all chains, reuse allowed (AutoStart) |
| **Run Step** | Partial chain from SCF root to target; target MUST execute |
| **One Chain = One ORCA Input** | Multiple steps fused into single job via keyword composition |
| **No $new_job / Compound** | MVP does NOT use multi-job ORCA syntax |
| **Simple Reuse** | Use native ORCA AutoStart/NoAutoStart; no complex fingerprinting |
| **No QE/Wannier Changes** | This plan does NOT modify QE or Wannier90 |
| **Opt/Relax Out of Scope** | MVP handles only single-point property chains |

---

## 2. Architecture Overview

### 2.1 Target Architecture

```
+-------------------------------------------------------------------------+
|                           Engine Layer                                   |
+-------------------------------------------------------------------------+
|                                                                          |
|  +---------------------------------------------------------------------+ |
|  |                   QCEngineBase (NEW)                                | |
|  |  - Chain detection (identify SCF roots)                             | |
|  |  - Partial chain extraction (for Run Step)                          | |
|  |  - Abstract: compile_chain(), run_chain()                           | |
|  +---------------------------------------------------------------------+ |
|              ^                                    ^                      |
|              |                                    |                      |
|  +-----------+-----------+          +------------+----------+            |
|  |  PySCFEngine (UPDATED) |          |  ORCAEngine (NEW)     |           |
|  |  - run_chain -> session |          |  - run_chain -> fused |           |
|  |  - In-memory state      |          |    ORCA input file    |           |
|  |  - subprocess isolation |          |  - Execute single run |           |
|  +-------------------------+          +------------------------+          |
|                                                                          |
|  +---------------------------------------------------------------------+ |
|  | QE/Wannier Engines (UNCHANGED)                                      | |
|  | - Artifact-bridged execution (not session-chain)                    | |
|  +---------------------------------------------------------------------+ |
+-------------------------------------------------------------------------+
```

### 2.2 Chain Model

```
+-------------------------------------------------------------------------+
| Chain Concept                                                            |
|                                                                          |
| A Calculation with steps: [SCF, TD] forms ONE chain:                     |
|                                                                          |
|   +-----+     +-----+                                                    |
|   | SCF | --> | TD  |  => ONE ORCA input: "! B3LYP ... %tddft ... end"  |
|   |root |     |     |                                                    |
|   +-----+     +-----+                                                    |
|                                                                          |
| A Calculation with steps: [SCF1, TD1, SCF2, TD2] forms TWO chains:       |
|                                                                          |
|   Chain 1:                Chain 2:                                       |
|   +------+    +-----+     +------+    +-----+                            |
|   | SCF1 |-->| TD1 |     | SCF2 |-->| TD2 |                            |
|   | root |    |     |     | root |    |     |                            |
|   +------+    +-----+     +------+    +-----+                            |
|                                                                          |
|   => TWO ORCA inputs: chain01_scf_td.inp, chain02_scf_td.inp            |
+-------------------------------------------------------------------------+
```

---

## 3. Chain Naming Scheme

### 3.1 Chain Key Derivation

**Rule**: Chain basename derived from normalized public step sequence, with numeric suffix for collision resolution.

**Normalization Algorithm**:
```python
def derive_chain_key(chain: QCChain, chain_index: int, all_chain_keys: List[str]) -> str:
    """
    Derive human-debuggable chain key from step sequence.

    Examples:
      [scf] -> "scf"
      [scf, td] -> "scf_td"
      [scf, mp2] -> "scf_mp2"
      [scf, td, freq] -> "scf_td_freq" (if supported in one job)

    With collision resolution:
      First [scf, td] chain -> "chain01_scf_td"
      Second [scf, td] chain -> "chain02_scf_td"
    """
    # 1. Get public step types from chain
    step_types = [step.public_type for step in chain.all_steps]

    # 2. Join with underscore (keep short but readable)
    base_key = "_".join(step_types)  # e.g., "scf_td"

    # 3. Prefix with chain index (always, for predictability)
    chain_key = f"chain{chain_index:02d}_{base_key}"  # e.g., "chain01_scf_td"

    return chain_key
```

**Examples**:
| Steps in Chain | Chain Index | Resulting Chain Key |
|----------------|-------------|---------------------|
| [SCF] | 1 | `chain01_scf` |
| [SCF, TD] | 1 | `chain01_scf_td` |
| [SCF, TD] | 2 | `chain02_scf_td` |
| [SCF, FREQ] | 1 | `chain01_scf_freq` |
| [HF, MP2] | 1 | `chain01_hf_mp2` |

### 3.2 File Naming from Chain Key

| Purpose | Pattern | Example |
|---------|---------|---------|
| ORCA input | `{chain_key}.inp` | `chain01_scf_td.inp` |
| ORCA output | `{chain_key}.out` | `chain01_scf_td.out` |
| GBW file | `{chain_key}.gbw` | `chain01_scf_td.gbw` |
| Property file | `{chain_key}.property.txt` | `chain01_scf_td.property.txt` |
| Hessian file | `{chain_key}.hess` | `chain01_scf_freq.hess` |

**Rationale**: Using chain key (not step ULID) makes ORCA outputs human-inspectable. When debugging, `ls raw/` shows meaningful names.

---

## 4. Step Taxonomy Proposal

### 4.1 ORCA Step Types to Register

| Machine Type | Public Type | Engine | Consumes | Produces | Skip? | MVP |
|--------------|-------------|--------|----------|----------|-------|-----|
| `orca_scf` | `scf` | `orca` | structure | `.gbw` | Yes (AutoStart) | **MVP** |
| `orca_hf` | `hf` | `orca` | structure | `.gbw` | Yes (AutoStart) | **MVP** |
| `orca_td` | `td` | `orca` | `.gbw` | excited states | No | **MVP** |
| `orca_freq` | `freq` | `orca` | `.gbw` | `.hess` | No | Future |
| `orca_nmr` | `nmr` | `orca` | `.gbw` | shifts | No | Future |
| `orca_mp2` | `mp2` | `orca` | `.gbw` | correlation E | No | Future |
| `orca_opt` | `opt` | `orca` | structure | `.xyz`, `.gbw` | No | **Out of Scope** |

### 4.2 MVP Supported Combinations

For MVP, we support these step combinations in a **single ORCA job**:

| Chain Steps | ORCA Keywords | Single Job? | MVP |
|-------------|---------------|-------------|-----|
| [SCF] | `! B3LYP def2-TZVP` | Yes | **MVP** |
| [HF] | `! HF def2-TZVP` | Yes | **MVP** |
| [SCF, TD] | `! B3LYP def2-TZVP` + `%tddft NRoots N end` | Yes | **MVP** |
| [HF, TD] | `! HF def2-TZVP` + `%tddft NRoots N end` | Yes | **MVP** |
| [SCF, FREQ] | `! B3LYP def2-TZVP Freq` | Yes | Future |
| [SCF, NMR] | `! B3LYP def2-TZVP NMR` + `%eprnmr ... end` | Yes | Future |
| [HF, MP2] | `! HF def2-TZVP MP2` | ??? | Future - needs verification |

**Unsupported in MVP** (require separate ORCA runs or $new_job):
- Any chain involving opt/relax
- Cross-method chains (e.g., DFT SCF → HF-based MP2)
- CCSD/EOM-CCSD (complex workflow)

---

## 5. Chain Compilation Strategy (Single-Job Fusion)

### 5.1 Compilation Rules

**CRITICAL**: For MVP, we compile chain steps into **ONE ORCA job** by composing keywords and blocks. We do NOT use `$new_job` or `Compound`.

**Composition Algorithm**:
```python
def compile_chain_to_input(chain: QCChain, structure: Molecule) -> str:
    """
    Compile chain into single ORCA input file.

    Steps are fused by combining their keywords and blocks.
    """
    keywords = set()        # Simple keywords (! line)
    blocks = {}             # %block_name -> block_content

    # 1. Process SCF root
    scf_step = chain.scf_root
    keywords.update(compile_scf_keywords(scf_step.parameters))
    blocks.update(compile_scf_blocks(scf_step.parameters))

    # 2. Process downstream steps (add their keywords/blocks)
    for step in chain.downstream:
        if step.public_type == "td":
            # TD adds %tddft block (no new keywords needed)
            blocks["tddft"] = compile_tddft_block(step.parameters)
        elif step.public_type == "freq":
            # Freq adds Freq keyword + optional %freq block
            keywords.add("Freq")
            if needs_freq_block(step.parameters):
                blocks["freq"] = compile_freq_block(step.parameters)
        elif step.public_type == "nmr":
            keywords.add("NMR")
            blocks["eprnmr"] = compile_nmr_block(step.parameters)
        # ... other step types

    # 3. Compose input file
    return format_orca_input(
        keywords=keywords,
        blocks=blocks,
        structure=structure,
        chain_key=chain.key,
    )
```

### 5.2 Example: SCF + TD Fusion

**Input**: Chain with [SCF(B3LYP/def2-TZVP), TD(nroots=5)]

**Generated ORCA Input** (`chain01_scf_td.inp`):
```
# Chain: chain01_scf_td
# Generated by QMatSuite

! B3LYP def2-TZVP TightSCF

%pal nprocs 4 end

%tddft
  NRoots 5
  TDA true
end

* xyz 0 1
O   0.000000   0.000000   0.117300
H   0.000000   0.756950  -0.469200
H   0.000000  -0.756950  -0.469200
*
```

### 5.3 Example: SCF Only

**Input**: Chain with [SCF(B3LYP/def2-TZVP)]

**Generated ORCA Input** (`chain01_scf.inp`):
```
# Chain: chain01_scf
# Generated by QMatSuite

! B3LYP def2-TZVP TightSCF

%pal nprocs 4 end

* xyz 0 1
O   0.000000   0.000000   0.117300
H   0.000000   0.756950  -0.469200
H   0.000000  -0.756950  -0.469200
*
```

---

## 6. Artifact Contract

### 6.1 Per-Chain Artifacts (Runtime)

| Step Type | Artifacts Generated | Source File |
|-----------|---------------------|-------------|
| `orca_scf` | `.gbw`, `.out`, `.property.txt`, `.xyz` | `{chain_key}.*` |
| `orca_td` | (included in same `.out`, `.property.txt`) | `{chain_key}.*` |
| `orca_freq` | `.hess`, (included in same `.out`) | `{chain_key}.*` |
| `orca_nmr` | (included in same `.out`, `.property.txt`) | `{chain_key}.*` |

**Key Point**: Since one chain = one ORCA run, all steps share the same output files. Artifact collection parses the shared files to extract per-step results.

### 6.2 Per-Step Result Extraction

```python
ORCA_STEP_ARTIFACTS = {
    "orca_scf": {
        "source_files": ["{chain_key}.gbw", "{chain_key}.out", "{chain_key}.property.txt"],
        "parse_sections": ["SCF_Energy", "Orbital_Energies"],
    },
    "orca_td": {
        "source_files": ["{chain_key}.out", "{chain_key}.property.txt"],
        "parse_sections": ["TDDFT_Excitations", "Oscillator_Strengths"],
    },
    "orca_freq": {
        "source_files": ["{chain_key}.out", "{chain_key}.hess", "{chain_key}.property.txt"],
        "parse_sections": ["Frequencies", "IR_Intensities", "Thermochemistry"],
    },
}

def extract_step_results(chain_key: str, step_type: str, working_dir: Path) -> Dict[str, Any]:
    """
    Extract step-specific results from chain output files.

    Even though runtime is one ORCA job, QMatSuite presents per-step results.
    """
    spec = ORCA_STEP_ARTIFACTS[step_type]
    results = {}

    # Parse property.txt for structured data
    property_file = working_dir / f"{chain_key}.property.txt"
    if property_file.exists():
        parsed = parse_orca_property_txt(property_file)
        for section in spec["parse_sections"]:
            if section in parsed:
                results[section] = parsed[section]

    # Parse .out for supplementary data
    out_file = working_dir / f"{chain_key}.out"
    if out_file.exists():
        parsed_out = parse_orca_output(out_file)
        for section in spec["parse_sections"]:
            if section in parsed_out and section not in results:
                results[section] = parsed_out[section]

    return results
```

### 6.3 Artifact Directory Structure

```
{calc_dir}/raw/
  chain01_scf_td.inp          # Generated ORCA input
  chain01_scf_td.out          # ORCA stdout
  chain01_scf_td.gbw          # Wavefunction (seed for future runs)
  chain01_scf_td.property.txt # Structured properties (PRIMARY)
  chain01_scf_td.xyz          # Final geometry
  step_artifacts/
    {scf_step_ulid}/
      results.json            # Parsed SCF results
    {td_step_ulid}/
      results.json            # Parsed TD results
```

---

## 7. Property File Parsing (TXT Only)

### 7.1 Design Decision

**JSON DISABLED**: We do NOT use `WriteJSONPropertyfile True` or `orca_2json` in MVP.

**Rationale**:
1. Reduces output file volume
2. Avoids dependency on `orca_2json` binary availability
3. Consistent with QE parser philosophy (parse native output)
4. JSON can be added as optional future enhancement

### 7.2 Property.txt Parser

```python
# src/quantumvitas/io/orca/property_parser.py

def parse_orca_property_txt(path: Path) -> Dict[str, Any]:
    """
    Parse ORCA .property.txt file format.

    Format:
      $PropertyName
      &GeometryIndex [integer]
      &ComponentName [type]
      value
      $End
    """
    content = path.read_text()
    properties = {}

    # Parse each $PropertyName...$End block
    for match in PROPERTY_BLOCK_RE.finditer(content):
        prop_name = match.group("name")
        block_content = match.group("content")
        properties[prop_name] = parse_property_block(block_content)

    return properties

def parse_property_block(content: str) -> Any:
    """Parse property block content based on component type."""
    # Handle Double, Integer, String, ArrayOfDoubles, Boolean
    # ...implementation
```

### 7.3 Property Types We Parse

| Property | Section Name | Data Type | Used By |
|----------|--------------|-----------|---------|
| Total Energy | `SCF_Energy` | Double | SCF |
| Orbital Energies | `MO_Energies` | ArrayOfDoubles | SCF |
| Excitation Energies | `TD_Energies` | ArrayOfDoubles | TD |
| Oscillator Strengths | `TD_OscillatorStrengths` | ArrayOfDoubles | TD |
| Frequencies | `Frequencies` | ArrayOfDoubles | FREQ |
| IR Intensities | `IR_Intensities` | ArrayOfDoubles | FREQ |

---

## 8. Run Semantics Mapping

### 8.1 Run Calc Behavior

```python
def run_calc(calc: Calculation, run_mode: str = "incremental") -> CalculationResult:
    """
    Execute entire calculation.

    run_mode:
      - "incremental": Use AutoStart (default)
      - "full": Force fresh run (NoAutoStart)
    """
    engine = get_engine(calc.engine_family)

    # Detect chains (steps grouped by SCF roots)
    chains = engine.detect_chains(calc.steps)

    results = []
    for chain in chains:
        if run_mode == "full":
            chain_results = engine.run_chain(chain, fresh=True)
        else:
            chain_results = engine.run_chain(chain, fresh=False)
        results.extend(chain_results)

    return CalculationResult(step_results=results)
```

### 8.2 Run Step Behavior

```python
def run_step(calc: Calculation, target_step_id: str) -> StepResult:
    """
    Execute partial chain from SCF root to target step.

    RULES:
    1. Find SCF root for target step
    2. If no SCF root: ERROR (do not auto-run, do not guess)
    3. Execute partial chain from SCF root -> target
    4. Target step MUST execute (even if previously done)
    5. If target IS an SCF step: fresh run (no reuse)
    """
    engine = get_engine(calc.engine_family)

    # Find chain containing target step
    chains = engine.detect_chains(calc.steps)
    target_chain = None
    for chain in chains:
        if target_step_id in [s.id for s in chain.all_steps]:
            target_chain = chain
            break

    if target_chain is None:
        raise ValueError(f"Step {target_step_id} not found in any chain")

    # Check SCF root exists
    if target_chain.scf_root is None:
        raise RuntimeError(f"Step {target_step_id} has no SCF root. Cannot run.")

    # Extract partial chain to target
    partial_chain = target_chain.to_partial_chain(target_step_id)

    # Determine if fresh run needed
    is_scf_target = target_step_id == partial_chain.scf_root.id
    fresh = is_scf_target  # SCF target = always fresh

    # Execute partial chain
    results = engine.run_chain(partial_chain, fresh=fresh, target_must_run=True)

    return results[-1]  # Return target step result
```

### 8.3 Fresh vs Reuse Matrix

| Scenario | ORCA Behavior | Keywords Generated |
|----------|---------------|-------------------|
| Run Calc (incremental) | AutoStart | (none, use defaults) |
| Run Calc (full) | NoAutoStart | `! NoAutoStart` |
| Run Step (SCF target) | Fresh SCF | `! NoAutoStart` |
| Run Step (non-SCF target) | Reuse SCF if `.gbw` exists | `! MORead` + `%moinp` |

---

## 9. ORCA Path Configuration

### 9.1 Resolution Strategy (Same as QE)

Following the established QE pattern, ORCA path resolution uses a two-state model:

**State 1: External ORCA** (user-configured)
- Settings path: `settings.orca.bin_dir`
- Validation: Check for `orca` executable
- Priority: Higher than internal

**State 2: Internal ORCA** (bundled auto-discovery)
- Search path: `.qmatsuite/engines/orca/**/orca`
- Selection: Most recent by mtime (like QE)

### 9.2 MVP: Hardcoded Bundled Location

For MVP, we hardcode the bundled ORCA location:

```python
# src/quantumvitas/core/engines/orca_resolver.py

BUNDLED_ORCA_PATH = Path.home() / ".qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411"

def resolve_orca_bin_dir() -> Path:
    """
    Resolve ORCA binary directory.

    MVP: Return bundled location if exists, else raise.
    Future: Implement full two-state resolution like QE.
    """
    if BUNDLED_ORCA_PATH.exists() and (BUNDLED_ORCA_PATH / "orca").is_file():
        return BUNDLED_ORCA_PATH
    raise RuntimeError(
        f"ORCA not found at bundled location: {BUNDLED_ORCA_PATH}\n"
        "Future versions will support settings.orca.bin_dir configuration."
    )
```

### 9.3 Evidence: Bundled ORCA Location

Verified bundled ORCA at:
```
/Users/hh7465/QMatSuite/.qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411/orca
```
- Binary is executable
- Version: ORCA 6.1.1 for macOS ARM64 with OpenMPI 4.1.1

---

## 10. Implementation Phases

### Phase 0: ORCA Sanity Test (Pre-implementation)

**Goal**: Verify ORCA runs correctly with our bundled binary

**Tasks**:
1. Create minimal H2O input file manually
2. Run ORCA directly from bundled location
3. Verify outputs (.out, .gbw, .property.txt)
4. Document any environment requirements (PATH, LD_LIBRARY_PATH)

**Acceptance Criteria**:
- [ ] Manual `./orca water.inp` succeeds
- [ ] Property.txt generated
- [ ] No MPI/library errors

### Phase 1: ORCA Engine MVP (Foundation)

**Goal**: Basic ORCA single-step (SCF only) execution working

**Tasks**:
1. Create `src/quantumvitas/engine/orca_engine.py`
2. Create `src/quantumvitas/engines/orca/` module structure
3. Implement path resolution (MVP hardcoded)
4. Implement basic input generation (DFT SCF only)
5. Implement command building (no MPI wrapper)
6. Implement artifact collection
7. Register ORCA step types in registry
8. Unit tests for input generation

**Acceptance Criteria**:
- [ ] ORCA engine registered in EngineRegistry
- [ ] Basic DFT input file generated correctly
- [ ] Single SCF step executes and artifacts collected
- [ ] Step returns StepResult with success/failure
- [ ] Unit tests pass (no ORCA required)

### Phase 2: Generalized QC Engine Layer

**Goal**: Extract common chain logic for PySCF + ORCA

**Tasks**:
1. Create `src/quantumvitas/engine/qc_engine_base.py`
2. Implement `QCChain` dataclass with chain key derivation
3. Implement `detect_chains()` (identify SCF roots)
4. Implement `to_partial_chain()` (for Run Step)
5. Refactor PySCFEngine to inherit from QCEngineBase
6. Ensure existing PySCF tests pass

**Acceptance Criteria**:
- [ ] `QCEngineBase` class with chain detection
- [ ] `detect_chains()` correctly identifies SCF roots
- [ ] `to_partial_chain()` extracts correct steps
- [ ] Chain key derivation produces expected names
- [ ] PySCFEngine uses QCEngineBase
- [ ] All existing PySCF tests pass
- [ ] New unit tests for chain detection

### Phase 3: ORCA Single-Job Compilation (MVP Focus)

**Goal**: Compile SCF + TD chains into single ORCA input

**Tasks**:
1. Implement `ORCAInputCompiler` class
2. Implement keyword fusion for SCF + TD
3. Implement `%tddft` block generation
4. Implement chain execution (single ORCA run)
5. Implement property.txt parser
6. Implement per-step result extraction
7. Unit tests for input compilation
8. Integration test: SCF-only run with bundled ORCA
9. Integration test: SCF + TD run with bundled ORCA

**Acceptance Criteria**:
- [ ] SCF chain compiles to correct input
- [ ] SCF + TD chain compiles to correct input
- [ ] No `$new_job` in generated inputs
- [ ] Property.txt parsed correctly
- [ ] Integration test with bundled ORCA passes

### Phase 4: Run Semantics Implementation

**Goal**: Implement Run Calc and Run Step per specification

**Tasks**:
1. Implement `run_calc()` with incremental/full modes
2. Implement `run_step()` with partial chain logic
3. Wire fresh/reuse flags to NoAutoStart
4. Update CalculationRunner to use new methods
5. Integration tests for run semantics

**Acceptance Criteria**:
- [ ] Run Calc (incremental) uses AutoStart
- [ ] Run Calc (full) uses NoAutoStart on all steps
- [ ] Run Step finds SCF root correctly
- [ ] Run Step errors if no SCF root
- [ ] Run Step on SCF = fresh run
- [ ] Run Step on non-SCF = reuse SCF .gbw (if exists)

### Future Topics (Out of MVP Scope)

- **Opt/Relax chains**: AutoStart limitations, multi-cycle tracking
- **Frequency calculations**: Numerical Hessian performance
- **NMR**: Reference shielding handling
- **MP2/CCSD**: Method compatibility constraints
- **$new_job support**: If truly required for some properties
- **Settings-based ORCA path**: Full two-state resolution like QE
- **JSON property output**: Optional `WriteJSONPropertyfile` support

---

## 11. File Structure Proposal

```
src/quantumvitas/
  engine/
    base.py              # Engine, EngineConfig, StepResult (unchanged)
    registry.py          # EngineRegistry (add ORCA)
    qc_engine_base.py    # NEW: QCEngineBase, QCChain
    pyscf_engine.py      # UPDATE: inherit from QCEngineBase
    qe_engine.py         # UNCHANGED
    orca_engine.py       # NEW: ORCAEngine
  engines/
    pyscf/               # UNCHANGED
      __init__.py
      runner.py
      chain_execution.py
    orca/                # NEW
      __init__.py
      input_compiler.py     # ORCA input generation
      property_parser.py    # Parse .property.txt
      output_parser.py      # Parse .out (fallback)
      artifact_collector.py
  core/
    engines/
      orca_resolver.py   # NEW: ORCA path resolution
  io/
    orca/                # NEW
      __init__.py
      input_templates.py    # ORCA input file templates
  workflow/
    registry.py          # UPDATE: add ORCA step types
    generalized_steps.py # UPDATE: add ORCA materialization
```

---

## 12. Testing Strategy

### 12.1 Unit Tests (No ORCA Required)

```python
# tests/unit/test_orca_input_compiler.py

def test_single_scf_input():
    """Test basic SCF input generation."""
    compiler = ORCAInputCompiler()
    step = create_scf_step(functional="B3LYP", basis="def2-TZVP")
    chain = QCChain(scf_root=step, downstream=[], key="chain01_scf")

    input_text = compiler.compile(chain, molecule=water)

    assert "! B3LYP def2-TZVP" in input_text
    assert "* xyz" in input_text
    assert "$new_job" not in input_text  # MVP: no multi-job

def test_scf_td_fusion():
    """Test SCF + TD fused into single job."""
    compiler = ORCAInputCompiler()
    scf_step = create_scf_step(functional="B3LYP", basis="def2-TZVP")
    td_step = create_td_step(nroots=5)
    chain = QCChain(scf_root=scf_step, downstream=[td_step], key="chain01_scf_td")

    input_text = compiler.compile(chain, molecule=water)

    assert "! B3LYP def2-TZVP" in input_text
    assert "%tddft" in input_text
    assert "NRoots 5" in input_text
    assert "$new_job" not in input_text  # MVP: no multi-job

def test_chain_key_derivation():
    """Test chain key naming."""
    scf_step = create_step(public_type="scf", id="s1")
    td_step = create_step(public_type="td", id="s2")

    chain = QCChain(scf_root=scf_step, downstream=[td_step])
    key = derive_chain_key(chain, chain_index=1)

    assert key == "chain01_scf_td"

def test_chain_detection():
    """Test chain detection from step list."""
    steps = [
        create_step(public_type="scf", id="s1"),
        create_step(public_type="td", id="s2"),
        create_step(public_type="scf", id="s3"),
        create_step(public_type="td", id="s4"),
    ]

    chains = detect_chains(steps, engine="orca")

    assert len(chains) == 2
    assert chains[0].scf_root.id == "s1"
    assert chains[0].key == "chain01_scf_td"
    assert chains[1].scf_root.id == "s3"
    assert chains[1].key == "chain02_scf_td"

def test_property_txt_parser():
    """Test .property.txt parsing."""
    content = '''
$SCF_Energy
&GeometryIndex 0
&Value Double
-76.0230974
$End

$TDDFT_Excitations
&GeometryIndex 0
&Value ArrayOfDoubles
&Dim (5,)
0.312  0.378  0.421  0.455  0.512
$End
'''
    parsed = parse_orca_property_txt_string(content)

    assert parsed["SCF_Energy"] == -76.0230974
    assert len(parsed["TDDFT_Excitations"]) == 5
```

### 12.2 Integration Tests (ORCA Required)

```python
# tests/integration/test_orca_engine.py

import pytest
import os

ORCA_BIN = os.environ.get("QMATSUITE_ORCA_BIN")

@pytest.fixture
def orca_available():
    """Check if ORCA is available for integration tests."""
    if not ORCA_BIN:
        pytest.skip("QMATSUITE_ORCA_BIN not set")
    if not Path(ORCA_BIN).exists():
        pytest.skip(f"ORCA not found at {ORCA_BIN}")
    return Path(ORCA_BIN)

@pytest.mark.integration
def test_orca_scf_execution(orca_available, tmp_path):
    """Test actual ORCA SCF execution."""
    engine = ORCAEngine(orca_bin=orca_available)
    step = create_orca_scf_step(molecule=water_xyz)

    result = engine.run_step(step, working_dir=tmp_path)

    assert result.success
    assert (tmp_path / "chain01_scf.gbw").exists()
    assert (tmp_path / "chain01_scf.out").exists()
    assert (tmp_path / "chain01_scf.property.txt").exists()

@pytest.mark.integration
def test_orca_scf_td_chain(orca_available, tmp_path):
    """Test SCF + TD fused chain execution."""
    engine = ORCAEngine(orca_bin=orca_available)
    scf_step = create_orca_scf_step(molecule=water_xyz)
    td_step = create_orca_td_step(nroots=3)

    results = engine.run_chain([scf_step, td_step], working_dir=tmp_path)

    assert len(results) == 2
    assert all(r.success for r in results)
    assert (tmp_path / "chain01_scf_td.out").exists()
    # Verify TD results extracted
    assert "excitation_energies" in results[1].metrics
```

### 12.3 Integration Test Execution

**Local (with bundled ORCA)**:
```bash
# Set ORCA binary location
export QMATSUITE_ORCA_BIN=/Users/hh7465/QMatSuite/.qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411/orca

# Run integration tests
pytest -m integration tests/integration/test_orca_engine.py -v
```

**CI (no ORCA)**:
```bash
# Integration tests auto-skip when ORCA not available
pytest tests/ -v  # Unit tests run, integration tests skip
```

---

## 13. Questions Answered (With Repo Evidence)

### Q1: UI for Run Step

**ANSWER**: YES, Run Step exists.

**Evidence**:
- **RPC Handler**: `_handle_run_step()` at `src/quantumvitas/daemon/server.py:5450-5516`
- **Backend**: `QVService.run_step()` at `src/quantumvitas/api.py:1319-1470`
- **Also**: `_handle_run_single_step()` at `server.py:5518-5572` for "always run" variant

The RPC accepts `calc_id` and `step_id`, looks up the step in calculation context, resolves engine via registry, and executes.

### Q2: Multiple Chains Display

**ANSWER**: NO special UI display for chains.

**Decision**: UI + persisted model remains a 1D ordered step list. The order is scheduling/execution order; it does NOT imply linear dependency. In QC engines (PySCF, ORCA), dependencies are SCF-root based. In QE, dependencies are artifact-bridged (outdir).

Chains are a runtime concept for execution, not a UI/persistence concept.

### Q3: ORCA Path Configuration

**ANSWER**: Global, same pattern as QE.

**Evidence**:
- **QE Pattern**: `src/quantumvitas/core/engines/qe_resolver.py:139-190`
  - State 1: `settings.qe.bin_dir` (user-configured)
  - State 2: Auto-discovery under `.qmatsuite/engines/qe/**/bin`
- **Bundled ORCA Location** (verified):
  ```
  /Users/hh7465/QMatSuite/.qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411/orca
  ```

**MVP Decision**: Hardcode bundled location; full two-state resolution in future.

---

## 14. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| ORCA licensing restrictions | High | Clear docs: "ORCA must be installed separately" |
| Property.txt format changes | Medium | Version check; pin to ORCA 6.0+ format |
| Single-job fusion limitations | Medium | Document unsupported combinations; add $new_job later |
| Platform-specific issues | Medium | Test on macOS ARM64; document requirements |
| Memory issues (large molecules) | Medium | Document `%maxcore` setting; add to parameters |

---

## 15. References

- [ORCA 6.0 Manual](https://www.faccts.de/docs/orca/6.0/manual/)
- [ORCA 6.0 Tutorials](https://www.faccts.de/docs/orca/6.0/tutorials/)
- [QMatSuite Constitution](../../CONSTITUTION_ZH.md)
- [State of Repo Analysis](./orca_state_of_repo.md)
- [ORCA Exploration](./orca_orca_exploration.md)
- [Execution MVP Plan](./orca_execution_mvp_plan.md) (companion document)
