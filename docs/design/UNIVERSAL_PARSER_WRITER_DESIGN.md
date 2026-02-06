# Universal Engine Input Parser/Writer & Metadata System

**Status**: DRAFT
**Version**: 0.3
**Date**: 2026-02-05
**Author**: Design proposal
**Scope**: Cross-engine input parsing, writing, and parameter catalogs
**Parent Laws**: `CONSTITUTION.md` §17, `ENGINE_INTEGRATION_CONSTITUTION.md`, `ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md`

---

## Table of Contents

1. [Goals](#1-goals)
2. [Governing Laws](#2-governing-laws)
3. [Engine Inventory & Syntax Families](#3-engine-inventory--syntax-families)
4. [Key Architectural Decisions](#4-key-architectural-decisions)
5. [Data Model / Schema (v0)](#5-data-model--schema-v0)
6. [Integration Points in QMatSuite](#6-integration-points-in-qmatsuite)
7. [Validation & Roundtrip Testing](#7-validation--roundtrip-testing)
8. [Corpus Workflow & Demo Gallery](#8-corpus-workflow--demo-gallery)
9. [Extensibility & Future Engines](#9-extensibility--future-engines)
10. [Module Layout](#10-module-layout)
11. [Phased Implementation Plan](#11-phased-implementation-plan)
12. [Open Questions](#12-open-questions)

---

## 1. Goals

### 1.1 Metadata Goal — QE-Depth for Every Engine

From official engine documentation, obtain **near-complete** parameter catalogs for every supported engine — the same level of depth as the existing QE metadata (`qe_module_parameters.json`). Every engine gets:

- Complete list of valid parameters per module/program
- Type, default, allowed values, units, doc string per parameter
- Deep links to official documentation per parameter
- Version tracking (which engine version the catalog targets)
- UI-ready parameter browsing/editing support
- Pre-submission validation against the catalog

**Non-black-box requirement**: Every metadata entry must be traceable to an official doc section, tutorial, or example file. No heuristics, no guessing, no "we think this parameter exists." If a parameter cannot be verified against docs, it is flagged `unverified` in the catalog.

For Python-script engines (GPAW, PySCF, Psi4), metadata is extracted via Python introspection (docstrings, type hints, constructor signatures) rather than documentation scraping. These catalogs are still QE-depth — just sourced differently.

### 1.2 Parser/Writer Goal — Semantic, No-Fidelity

For all file-based engines (12 of 15):

- **Writer**: Serialize structured parameters (from SSOT docs) into engine-native input files. This is the primary direction and the first-class citizen.
- **Parser**: Read engine-native input files into a structured representation. Used for import, validation, and inspection.
- **No fidelity goal**: Comments are stripped. Whitespace is not preserved. The parser extracts semantic content only. The writer produces clean, canonical output.
- **Primary validation loop**: `YAML → write → parse → YAML` must preserve all semantic content. This is the only roundtrip that must be perfect.
- **Import validation**: `file → parse → write → file` produces canonicalized output that is semantically equivalent. Formatting WILL differ — this is expected and correct.
- **Explicitness**: All parsing/writing rules are traceable to engine documentation. Each rule cites a doc section or grammar specification.
- **Unknown content**: Content the parser does not recognize is reported as a diagnostic and dropped. No "raw text" preservation — if the parser can't understand it, it says so and moves on.

**Scope boundary**: This system handles *input* files. Output parsing (energies, forces, convergence) remains a separate concern in existing `parser.py` modules per driver.

### 1.3 Validation Goal — Corpus-Driven Confidence

Download large corpora of official docs, tutorials, and example inputs into:

```
.tmp/engine_research/<engine_name>/
  docs/          # Official documentation (HTML, PDF, RST)
  examples/      # Official example inputs from engine repos
  tutorials/     # Tutorial inputs from docs/workshops
  tests/         # Test suite inputs from engine source trees
  corpora.json   # Manifest: source URL, download date, file count, license
```

Do NOT clean these `.tmp` corpora during development. They will be archived/moved later.

**Purpose**: Drive parser/writer/metadata improvements by measuring coverage against real-world inputs from authoritative sources. Every parser improvement should be motivated by a corpus file that exercises the new capability.

### 1.4 Demo Goal — Golden Calcs Gallery

From corpora, extract a small "golden calcs" set (3–5 per engine) representing common calculation types. Selection criteria:

- Covers the engine's most common step types (SCF, relax, bands, etc.)
- Uses standard/simple structures (Si, NaCl, graphene, benzene, etc.)
- Runs quickly (small systems, coarse grids)
- Input is well-commented and pedagogically clear

**Extraction workflow** (later phase):
1. Identify candidate corpus files by step type coverage
2. Simplify (reduce system size, coarsen grids) to ensure fast execution
3. Validate by running engine on golden calc, recording output signature (total energy, structure digest)
4. Package as demo gallery item with: input files, expected output signature, pedagogical README

---

## 2. Governing Laws

### Law 1: Two Kinds of Things — Input Files and Resource References

**There are exactly two kinds of things an engine needs at runtime:**

| Kind | Definition | Parser/Writer handles? | Examples |
|------|-----------|----------------------|----------|
| **Engine input file** | A file that encodes calculation parameters. The parser reads it; the writer produces it. | **Yes** — first-class parsed/written content. | QE: `pw.in`. VASP: `INCAR`, `POSCAR`, `KPOINTS`. ABINIT: `*.abi`. CP2K: `*.inp`. |
| **Resource reference** | An external binary or data file staged (copied/symlinked) from a library. Not parsed by the input parser. | **No** — staged by the recipe/handler. | Pseudopotentials (`.UPF`, `POTCAR`, `.psf`). Basis set files. Continuation artifacts (`CHGCAR`, `WAVECAR`, charge density). |

**There is no "generated asset" concept.** Structure data and k-point specifications are part of the SSOT mapping — they flow from SSOT docs into engine input files via the writer. For engines where structure is in a separate file (VASP's `POSCAR`, xTB's `.xyz`), that file is an **engine input file** — it is parsed and written by the parser/writer system, not "generated" by some separate mechanism.

**Implications**:

- **VASP**: `INCAR`, `POSCAR`, `KPOINTS` are all engine input files — the parser/writer system handles all three. `POTCAR` is a resource reference (staged from library). Multi-file is normal, not special.
- **QE**: `pw.in` is the single engine input file (structure, k-points, parameters all embedded). `.UPF` files are resource references.
- **ABINIT**: `*.abi` is the engine input file. Pseudopotentials listed via `pp_dirpath`/`pseudos` are resource references.
- **xTB**: `.xcontrol` and the coordinate file (`.xyz`) are both engine input files. No resource references.
- **LAMMPS**: `in.*` script and `.data` file are engine input files. Potential files (`.tersoff`, etc.) are resource references.

**SSOT mapping for structure/k-points**: The writer maps structure data from `structure.json` (SSOT) into the appropriate engine input file — whether that's embedded cards in QE's `pw.in`, VASP's separate `POSCAR`, or positional data in ORCA's geometry block. The parser extracts structure data from engine input files back into SSOT-compatible format. This mapping is part of the per-engine `EngineInputSpec`.

### Law 2: Engine-Centered Declarations

**All engine-specific definitions must be centralized in exactly one place per engine.** This is the `EngineInputSpec` — a single, self-contained, declarative data structure that lives in the driver bundle and fully describes the engine's input format:

```python
@dataclass(frozen=True)
class EngineInputSpec:
    """Complete input format specification for one engine.

    This is the SSOT for everything the parser/writer system
    needs to know about this engine. Lives in drivers/<engine>/inputspec.py.
    """

    # === Identity ===
    engine_family: str                    # "qe", "vasp", "abinit"
    syntax_family: str                    # "fortran-namelist", "flat-keyval", etc.

    # === Dialect configuration ===
    dialect: DialectSpec                  # Declarative grammar config (see §4.2)

    # === Hooks ===
    hooks: dict[str, Callable]            # Named hook functions (see §4.3)

    # === File layout ===
    input_files: tuple[InputFileSpec, ...]  # Engine input files (parsed/written)
    resource_refs: tuple[ResourceRefSpec, ...]  # Staged external files (not parsed)

    # === SSOT mapping ===
    ssot_mapping: SSOTMappingSpec         # Which SSOT fields map to which input files

    # === Metadata ===
    metadata_source: MetadataSourceSpec   # How to obtain/load parameter catalog

    # === Corpus ===
    corpus_config: CorpusConfig | None    # Where to find corpus, file patterns, etc.
```

**Registration model — no import-time side effects**: The `EngineInputSpec` is returned by a method on the driver, not registered at import time. The framework collects specs explicitly when needed:

```python
# In the driver protocol (extends existing EngineDriver):
class EngineDriver(Protocol):
    # ... existing 7-item MUST interface ...

    def get_input_spec(self) -> EngineInputSpec | None:
        """Return input format specification, or None if not yet implemented."""
        ...
```

The framework collects specs by iterating registered drivers — the same pattern used for step types and materialization maps. No global mutable registry for input specs. No module-level side effects.

### Law 3: Engine-Agnostic Kernel

The `inputformat` package is engine-agnostic. It contains:
- Semantic AST data model (Node, Value, InputDocument)
- Family parsers (one per syntax family)
- Family writers (one per syntax family)
- Value coercion utilities
- Metadata schema definitions
- Corpus harness

It does NOT contain:
- Engine names, engine-specific constants, or engine-specific logic
- Import of any driver module
- Knowledge of QMatSuite's domain IR, step types, or recipes

All engine-specific behavior flows through `EngineInputSpec` (dialect config + hooks), which the driver provides to the framework at call time.

### Law 4: Parser/Writer Are Kernel-Internal

**The parser and writer are pure mapping functions internal to the kernel.** They are NOT callable from the API facade, CLI, or daemon. Their signatures are:

```python
# Kernel-internal pure functions (in inputformat package):

def parse_engine_inputs(
    workdir: Path,
    spec: EngineInputSpec,
) -> dict:
    """Parse engine input files from a workdir into an SSOT-compatible dict.

    Reads all files declared in spec.input_files from workdir.
    Returns a dict fragment compatible with step.yaml engine_params structure.
    Comments are stripped. Whitespace is normalized. Only semantic content is extracted.
    Unknown/unrecognized content produces diagnostics and is dropped.
    """

def write_engine_inputs(
    params: dict,
    spec: EngineInputSpec,
    workdir: Path,
) -> list[Path]:
    """Write engine input files to workdir from an SSOT-compatible dict.

    Writes all files declared in spec.input_files to workdir.
    params is a dict fragment from step.yaml engine_params structure.
    Returns list of written file paths.
    Output is clean, canonical — no comment preservation, no formatting fidelity.
    """
```

**Who calls these functions**:
- The **recipe/materialize** flow calls `write_engine_inputs` during materialization.
- The **import** flow (kernel-level) calls `parse_engine_inputs` to extract parameters from existing engine input files.
- The **validation** flow (kernel-level) calls both to verify roundtrip consistency.

**Who does NOT call these functions**:
- API facade endpoints — they call higher-level kernel functions that may internally use parse/write.
- CLI commands — they call API facade or kernel entry points.
- Daemon — it calls runner/executor which calls recipes.

The higher-level import wrapper (kernel-level, not in `inputformat`) handles business logic: creating step.yaml, populating calculation.yaml, resolving structure references, etc.

### Law 5: SSOT Four Documents

The parser/writer system maps between engine input files and the **four SSOT documents**:

| SSOT Document | Content | Parser extracts from | Writer consumes from |
|---------------|---------|---------------------|---------------------|
| `project.yaml` | Project-level settings | (not used by parser/writer) | (not used) |
| `calculation.yaml` | Calculation identity, engine family, step sequence | Engine family hint | Engine family |
| `step.yaml` | Step parameters (`engine_params.*`) | All engine parameters | All engine parameters |
| `structure.json` | Atomic structure (cell, positions, species) | Structure data from input files | Structure data for input files |

The parser's output is a dict fragment that can populate `step.yaml`'s `engine_params` section plus a structure dict for `structure.json`. The writer's input is the same dict fragment plus structure data.

---

## 3. Engine Inventory & Syntax Families

### 3.1 All 15 Supported Engines

| # | Engine | Family | Prefix | Engine Input Files | Syntax Family | Resource References |
|---|--------|--------|--------|-------------------|---------------|---------------------|
| 1 | Quantum ESPRESSO | `qe` | `qe` | `pw.in` (params + structure + k-points embedded) | fortran-namelist | `.UPF` pseudopotentials |
| 2 | ABINIT | `abinit` | `abinit` | `*.abi` (params + structure embedded) | flat-keyval | pseudopotentials (referenced by `pp_dirpath`/`pseudos`) |
| 3 | CP2K | `cp2k` | `cp2k` | `*.inp` (params + structure embedded) | nested-section | basis set files, potential files |
| 4 | VASP | `vasp` | `vasp` | `INCAR` (params), `POSCAR` (structure), `KPOINTS` (k-mesh) | flat-keyval | `POTCAR` (staged from library) |
| 5 | ORCA | `orca` | `orca` | `*.inp` (keywords + geometry embedded) | keyword-block | none |
| 6 | Gaussian | `gaussian` | `gaussian` | `*.gjf`/`.com` (route + geometry embedded) | keyword-block | checkpoint files (`.chk`, staged) |
| 7 | LAMMPS | `lammps` | `lammps` | `in.*` script, `.data` file | command-stream | potential files (`.tersoff`, etc.) |
| 8 | Siesta | `siesta` | `siesta` | `*.fdf` (params + structure embedded) | flat-keyval | `.psf`/`.psml` pseudopotentials |
| 9 | Wannier90 | `w90` | `w90` | `*.win` (params + structure embedded) | flat-keyval | `.amn`, `.mmn`, `.eig` (from DFT) |
| 10 | GPAW | `gpaw` | `gpaw` | `*.py` | python-script | — (writer-only) |
| 11 | Psi4 | `psi4` | `psi4` | `*.dat`/`.py` | python-script | — (writer-only) |
| 12 | PySCF | `pyscf` | `pyscf` | `*.py` | python-script | — (writer-only) |
| 13 | xTB | `xtb` | `xtb` | `.xcontrol`, coordinate file (`.xyz`) | dollar-flag | none |
| 14 | QMCPACK | `qmcpack` | `qmcpack` | `*.xml` | xml | wavefunction `.h5`, pseudopotentials |
| 15 | Yambo | `yambo` | `yambo` | `yambo.in` | flat-keyval | SAVE directory (from DFT) |

### 3.2 Syntax Family Classification (8 Families)

| ID | Family Name | Current Engines | Grammar Traits |
|----|------------|-----------------|----------------|
| **F1** | **fortran-namelist** | QE | `&NAME ... /` sections with `key = value`, free-format cards after namelists |
| **F2** | **flat-keyval** | ABINIT, Siesta, Wannier90, VASP, Yambo | `key value` or `key = value`, optional block directives (`%block`/`begin...end`/`%...%`) |
| **F3** | **nested-section** | CP2K | `&SECTION ... &END SECTION`, deeply nested, positional `keyword value` |
| **F4** | **keyword-block** | ORCA, Gaussian | Keyword lines (`!`/`#`) + structured blocks (`%...end` or blank-line delimited) |
| **F5** | **command-stream** | LAMMPS | Imperative line-oriented commands with positional args |
| **F6** | **xml** | QMCPACK | Standard XML with `<parameter name="key">value</parameter>` convention |
| **F7** | **python-script** | GPAW, Psi4, PySCF | Python API calls; **writer-only** (no parser needed) |
| **F8** | **dollar-flag** | xTB | `$instruction ... $end` blocks with `:` (append) and `=` (set-once) |

**Key design property**: The flat-keyval family (F2) is the most common pattern across computational science codes. It accommodates significant dialect variation through declarative configuration:

| Dialect | Block Syntax | Assignment | Special Features |
|---------|-------------|------------|------------------|
| ABINIT | (none — flat) | whitespace or `=` | Dataset suffixes (`ecut1`), repeat (`3*10.25`), `sqrt()` |
| Siesta | `%block` / `%endblock` | whitespace | Label normalization (`-_. ` ignored), first-occurrence wins |
| Wannier90 | `begin` / `end` | `=`, `:`, or whitespace | Three assignment operators, unit on first block data line |
| VASP (INCAR) | (none — flat) | `=` | `;` multi-tag lines, `\` continuation |
| Yambo | `%` / `%` | `=` with units | `\|` array separators, auto-generated category comments |

### 3.3 Per-Family Grammar Reference

#### F1: fortran-namelist (QE)

```
&CONTROL                          ← namelist open
    calculation = 'scf'           ← key = value (strings in quotes)
    pseudo_dir = './pseudo/'
/                                 ← namelist close
ATOMIC_SPECIES                    ← card keyword
Si 28.086 Si.pbe-n-kjpaw_psl.1.0.0.UPF   ← positional data
ATOMIC_POSITIONS (crystal)        ← card with option in parens
Si 0.0 0.0 0.0
K_POINTS (automatic)
4 4 4 0 0 0                      ← grid specification
```

- Assignment: `=` (commas optional as value separators)
- Values: Fortran booleans (`.true.`/`.false.`), `d` exponents (`1.0d-5`), quoted strings
- Structure data embedded in cards (ATOMIC_SPECIES, ATOMIC_POSITIONS, CELL_PARAMETERS, K_POINTS)

#### F2: flat-keyval (ABINIT / Siesta / Wannier90 / VASP / Yambo)

**ABINIT**:
```
# Comment
ecut 30.0         ← key value (= is treated as whitespace)
ngkpt 4 4 4       ← multi-value
acell 3*10.25     ← repeat multiplier (3 copies of 10.25)
xred              ← multi-line array follows
  0.0 0.0 0.0
  0.25 0.25 0.25
```

**Siesta (FDF)**:
```
SystemLabel       Si
LatticeConstant   5.43 Ang        ← value with unit
%block LatticeVectors
  1.0 0.0 0.0
  0.0 1.0 0.0
  0.0 0.0 1.0
%endblock LatticeVectors
```

**Wannier90**:
```
num_bands = 12
begin unit_cell_cart
bohr
  5.0 0.0 0.0
  0.0 5.0 0.0
  0.0 0.0 5.0
end unit_cell_cart
```

**VASP (INCAR)**:
```
SYSTEM = Si bulk SCF
ENCUT = 520
ISMEAR = 0 ; SIGMA = 0.1    ← semicolon-separated
LWAVE = .TRUE.
```

**Yambo**:
```
EXXRLvcs= 100      RL    # [XX] Exchange RL components
BndsRnXp= 1 | 300 |      # [Xp] Polarization function bands
%QPkrange                  ← %-delimited array block
  1| 37| 1| 38|
%
```

#### F3: nested-section (CP2K)

```
&GLOBAL
  PROJECT Si_scf
  RUN_TYPE ENERGY
&END GLOBAL
&FORCE_EVAL
  METHOD Quickstep
  &DFT
    BASIS_SET_FILE_NAME BASIS_MOLOPT
    &SCF
      MAX_SCF 50
      &OT
        MINIMIZER DIIS
      &END OT
    &END SCF
  &END DFT
&END FORCE_EVAL
```

- Deeply nested (4–5 levels typical)
- Positional: `KEYWORD VALUE` (no `=`)
- Section "default keyword" (value after section name on same line)
- Preprocessor: `@SET`, `@IF`/`@ENDIF`, `@INCLUDE`, `${VAR}`
- Units: `[unit]` token before values

#### F4: keyword-block (ORCA / Gaussian)

**ORCA**:
```
! B3LYP def2-SVP Opt         ← simple input keyword line
%maxcore 4000
%scf
  MaxIter 200
end
* xyz 0 1                    ← geometry block
C 0.0 0.0 0.0
H 1.0 0.0 0.0
*
```

**Gaussian**:
```
%mem=4GB                      ← Link0 (% prefix)
%nproc=8
#p B3LYP/6-31G(d) Opt Freq   ← Route (# prefix)

Title line                    ← blank-line delimited sections
                              ← blank line (structural!)
0 1                           ← charge multiplicity
C  0.0  0.0  0.0
H  1.0  0.0  0.0
                              ← blank line terminates geometry
```

- Gaussian: blank lines are structural terminators (extra blanks break the file)
- ORCA: three paradigms (`!`-line, `%...end` blocks, `*...*` geometry)

#### F5: command-stream (LAMMPS)

```
# Comment
units           metal
atom_style      atomic
read_data       Si.data          ← references external data file
pair_style      tersoff
pair_coeff      * * Si.tersoff Si
fix             1 all npt temp 300 300 0.1 iso 0.0 0.0 1.0
run             10000
```

- Imperative (order matters, commands execute on read)
- Positional args (command + args, no `=`)
- Variables: `$x`, `${name}`, `$((expr))`
- Control flow: `if/then/else`, `loop`, `jump`

#### F6: xml (QMCPACK)

```xml
<simulation>
  <project id="Si" series="0"/>
  <qmcsystem>
    <simulationcell>
      <parameter name="lattice" units="bohr">
        5.1 5.1 0.0  5.1 0.0 5.1  0.0 5.1 5.1
      </parameter>
    </simulationcell>
  </qmcsystem>
  <qmc method="vmc" move="pbyp">
    <parameter name="blocks">100</parameter>
  </qmc>
</simulation>
```

#### F8: dollar-flag (xTB)

```
$constrain
  atoms: 1-10
  force constant=1.0
$fix
  atoms: 11,12
$end
```

- `$instruction`: opens block
- `:` for appendable values, `=` for set-once values
- `$end` optional (EOF or next `$` terminates)

---

## 4. Key Architectural Decisions

### 4.1 Shared Parsing Kernel with Family Parsers

A single parsing framework provides common infrastructure (AST types, value coercion, diagnostics), but each syntax family has its own parser and writer module. Engine-specific behavior is isolated in the `EngineInputSpec` (declarative dialect + thin hooks).

```
                     ┌──────────────────────────┐
                     │    inputformat kernel     │
                     │  (AST, values,            │
                     │   diagnostics, harness)   │
                     └────────┬─────────────────┘
              ┌───────────────┼───────────────────┐
              ▼               ▼                   ▼
    ┌─────────────┐  ┌──────────────┐   ┌──────────────┐
    │ F1 Parser   │  │ F2 Parser    │   │ F3 Parser    │  ...
    │ + Writer    │  │ + Writer     │   │ + Writer     │
    │ (namelist)  │  │ (flat-kv)    │   │ (nested-sec) │
    └─────────────┘  └──────────────┘   └──────────────┘
           ▲                ▲                   ▲
           │                │                   │
    ┌──────┴──────┐  ┌──────┴───────┐   ┌──────┴───────┐
    │ QE          │  │ ABINIT       │   │ CP2K         │
    │ InputSpec   │  │ Siesta       │   │ InputSpec    │
    │ (dialect    │  │ W90, VASP    │   │ (dialect     │
    │  + hooks)   │  │ Yambo        │   │  + hooks)    │
    │             │  │ InputSpecs   │   │              │
    └─────────────┘  └──────────────┘   └──────────────┘
    lives in            lives in            lives in
    drivers/qe/         drivers/*/          drivers/cp2k/
```

**Rationale**: Syntax families share enough structure to warrant common infrastructure, but their grammars are different enough that a single "configurable" parser would be a leaky abstraction. Family parsers are small (200–500 lines each) and self-contained.

### 4.2 DialectSpec (Declarative Configuration)

The DialectSpec captures all grammar rules for a specific engine dialect within its syntax family. It is a frozen dataclass — pure data, no behavior:

```python
@dataclass(frozen=True)
class DialectSpec:
    """Declarative grammar configuration for one engine dialect."""

    # === Lexical rules ===
    comment_chars: tuple[str, ...]        # ("!", "#") or ("<!--",)
    line_continuation: str | None         # "\\", "&", None
    case_sensitive: bool                  # False for most
    max_line_length: int | None           # 132 for ABINIT, None for most
    blank_lines_structural: bool          # True for Gaussian (blank = section end)

    # === Section rules (family-specific) ===
    section_config: SectionConfig         # Family-specific frozen dataclass

    # === Value parsing ===
    assignment_operators: tuple[str, ...]  # ("=",) or ("=", ":", " ")
    value_separators: tuple[str, ...]      # (",", " ", ";", "|")
    boolean_literals: dict[str, bool]      # {".true.": True, "T": True, ...}
    string_delimiters: tuple[str, ...]     # ("'", '"')

    # === Documentation ===
    doc_url: str                          # Official input reference URL
    grammar_version: str                  # Engine version this spec targets
```

**Section config variants** (one per family):

```python
@dataclass(frozen=True)
class NamelistSectionConfig(SectionConfig):
    """F1: fortran-namelist"""
    open_pattern: str                     # "&{name}"
    close_pattern: str                    # "/"
    card_keywords: tuple[str, ...]        # ("ATOMIC_SPECIES", "K_POINTS", ...)
    card_option_delimiters: tuple[str, str]  # ("(", ")")

@dataclass(frozen=True)
class FlatKeyvalSectionConfig(SectionConfig):
    """F2: flat-keyval"""
    block_open: str | None                # "%block", "begin", "%", None
    block_close: str | None               # "%endblock", "end", "%", None
    block_name_on_delimiter: bool         # True for %block NAME, False for % alone
    multi_tag_separator: str | None       # ";" for VASP, None for others
    dataset_suffix_pattern: str | None    # r"(\w+?)(\d+)$" for ABINIT, None for others
    label_normalization: str | None       # "strip_-_." for Siesta, None for others

@dataclass(frozen=True)
class NestedSectionConfig(SectionConfig):
    """F3: nested-section"""
    open_pattern: str                     # "&{name}"
    close_pattern: str                    # "&END {name}" or "&END"
    default_keyword_on_open: bool         # True (value after section name)
    preprocessor_prefix: str | None       # "@" for CP2K
    unit_bracket: tuple[str, str] | None  # ("[", "]") for CP2K

@dataclass(frozen=True)
class KeywordBlockSectionConfig(SectionConfig):
    """F4: keyword-block"""
    keyword_line_prefix: str              # "!" for ORCA, "#" for Gaussian
    block_open: str                       # "%" for ORCA, (special for Gaussian)
    block_close: str                      # "end" for ORCA
    geometry_open: str | None             # "*" for ORCA, None for Gaussian
    geometry_close: str | None            # "*" for ORCA, None for Gaussian

@dataclass(frozen=True)
class CommandStreamSectionConfig(SectionConfig):
    """F5: command-stream"""
    variable_prefix: str                  # "$"
    include_command: str | None           # "include" for LAMMPS
    continuation_char: str | None         # "&" for LAMMPS

@dataclass(frozen=True)
class DollarFlagSectionConfig(SectionConfig):
    """F8: dollar-flag"""
    flag_prefix: str                      # "$"
    end_marker: str                       # "$end"
    append_operator: str                  # ":"
    set_operator: str                     # "="
```

### 4.3 Minimal Hook Mechanism

Hooks handle truly engine-specific behaviors that cannot be captured in a dialect spec. Constraints:

- Each hook is a single function with a well-defined signature
- Hooks are declared in the `EngineInputSpec`, not registered globally
- Called by the family parser at specific extension points
- Must be thin (< 50 lines); complex logic belongs in the family parser or dialect spec
- A hook that is `None` means "use default family behavior"

**Extension points** (hooks a family parser MAY call):

| Hook | Signature | Purpose |
|------|-----------|---------|
| `pre_tokenize` | `(text: str) -> str` | Preprocess raw text (e.g., ABINIT `include` expansion, CP2K `@SET` preprocessing) |
| `classify_section` | `(header: str) -> str \| None` | Determine section type/module when ambiguous (e.g., QE module detection from `&inputph`) |
| `parse_special_block` | `(block_name: str, lines: list[str], dialect: DialectSpec) -> list[ParameterNode]` | Handle non-standard block formats (e.g., QE K_POINTS variants, ORCA geometry `*...*`) |
| `coerce_value` | `(raw: str, context: str) -> Value \| None` | Engine-specific value transforms (e.g., ABINIT `3*10.25` repeat, `sqrt()`) |
| `post_parse` | `(doc: InputDocument) -> InputDocument` | Post-parse validation, cross-references, module detection |
| `pre_write` | `(doc: InputDocument) -> InputDocument` | Inject engine-specific content before serialization |
| `format_value` | `(value: Value, context: str) -> str \| None` | Engine-specific value formatting (e.g., Fortran `.true.`, VASP `.TRUE.`) |

**Example (QE hooks)**:
```python
def qe_classify_section(header: str) -> str | None:
    """Detect QE module from namelist names."""
    name = header.strip("&").lower()
    return {"inputph": "ph", "path": "neb", "inputpp": "pp"}.get(name)

def qe_parse_kpoints(block_name: str, lines: list[str], dialect: DialectSpec) -> list[ParameterNode]:
    """Handle K_POINTS variants: gamma, automatic, crystal, tpiba, etc."""
    # Returns structured parameter nodes from the K_POINTS card
    ...
```

### 4.4 Python-Script Engines: Writer-Only + Introspection

GPAW, PySCF, and Psi4 do not have parseable input files. For these engines:

- **Writer only**: A Python code generator that produces executable scripts from step.yaml parameters
- **No parser**: QMatSuite is the source of truth, not the generated script
- **Metadata via introspection**: Parameter catalogs extracted from Python docstrings, type hints, and constructor signatures
- **Roundtrip**: Not applicable in the traditional sense. The closed loop is `YAML → generate_script → (human inspection)`. Validation is by running the generated script.

These engines still get QE-depth metadata catalogs — the catalogs are just sourced from Python introspection rather than doc scraping.

### 4.5 InputDocument — Semantic AST, No Formatting

The parser/writer system defines its own **InputDocument** — a semantic-only representation of the input file content. Comments are stripped. Whitespace is not preserved. The AST captures parameter names, values, and structure — nothing else.

```
                  Write Path (primary)                Import Path (secondary)
                  ==================                  =====================

step.yaml params                                Engine input file(s)
      │                                               │
      ▼  [SSOT → InputDocument]                       ▼  [parse → strip comments/whitespace]
InputDocument                                   InputDocument
      │                                               │
      ▼  [family writer]                              ▼  [InputDocument → SSOT dict]
Engine input file(s)                            step.yaml params (dict)
```

The two directions share the same InputDocument type but have different priorities:
- **Write path** (YAML → file): First-class citizen. Must be robust and complete.
- **Import path** (file → YAML): Second-class citizen. Best-effort with coverage reporting.

---

## 5. Data Model / Schema (v0)

### 5.1 InputDocument (Semantic AST)

```python
@dataclass
class InputDocument:
    """Parsed/constructed engine input — semantic representation.

    Contains only semantic content. Comments are stripped during parsing.
    Whitespace and formatting are not preserved. The writer produces
    clean canonical output from this structure.
    """

    # Identity
    engine_family: str                    # "qe", "vasp", etc.
    syntax_family: str                    # "fortran-namelist", etc.
    dialect_version: str                  # Engine version this targets

    # Content — one InputDocument per engine input file
    file_name: str                        # "INCAR", "pw.in", "POSCAR", etc.
    nodes: list[Node]                     # Ordered AST nodes (semantic only)

    # Provenance
    source: str                           # "parsed:<path>", "constructed:materialize", etc.
    diagnostics: list[Diagnostic]         # Warnings, errors, info (including unrecognized content)


# --- AST Node Hierarchy ---

@dataclass
class Node:
    """Base AST node — semantic content only."""
    pass


@dataclass
class SectionNode(Node):
    """A named section/namelist/block containing children."""
    kind: str                             # "namelist", "block", "section", "card"
    name: str                             # Section name (canonical lowercase form)
    option: str | None                    # e.g., "crystal" for ATOMIC_POSITIONS
    children: list[Node]                  # Parameters, sub-sections, data lines


@dataclass
class ParameterNode(Node):
    """A key-value parameter."""
    key: str                              # Parameter name (canonical form)
    value: Value                          # Parsed value


@dataclass
class Value:
    """A parsed value with type information."""
    python_value: Any                     # Python-native value
    kind: str                             # "int", "float", "bool", "string",
                                          # "list", "array", "enum"
    unit: str | None                      # Physical unit if present


@dataclass
class DataLineNode(Node):
    """Positional data line in a card/block (not key-value)."""
    fields: list[Value]                   # Parsed fields
    role: str | None                      # "structure", "kpoints", "species", etc.


@dataclass
class CommandNode(Node):
    """A command in a command-stream format (LAMMPS)."""
    command: str                          # Command name
    args: list[Value]                     # Positional arguments


@dataclass
class Diagnostic:
    """Parser/writer diagnostic message."""
    level: str                            # "error", "warning", "info"
    message: str
    line: int | None                      # Source line number (1-based), if from parsing
    code: str                             # Machine-readable code, e.g. "W001"
```

**What is NOT in the AST** (by design):

- No `Comment` node — comments are stripped during parsing.
- No `raw_text`, `raw_value`, or `raw` fields — no formatting preservation.
- No `Span` for roundtrip fidelity — only `Diagnostic.line` for error reporting.
- No `RawNode` — unrecognized content produces a diagnostic and is dropped.
- No `separator` field on `ParameterNode` — the writer always uses canonical formatting.

### 5.2 File Specification Types

```python
@dataclass(frozen=True)
class InputFileSpec:
    """Specification for one engine input file (parsed/written)."""
    filename: str                         # "INCAR", "POSCAR", "pw.in"
    description: str                      # Human-readable
    content_role: str                     # "parameters", "structure", "kpoints",
                                          # "combined" (for QE/ABINIT/CP2K where all-in-one)
    optional: bool = False                # True if file may not exist (e.g., KPOINTS when using auto)

    # === Per-file dispatch (optional) ===
    # When set, these override the family parser/writer for this specific file.
    # Used when an engine has mixed-format input files (e.g., VASP INCAR is
    # flat-keyval but POSCAR/KPOINTS are engine-specific formats).
    # When None, the family parser/writer from EngineInputSpec.syntax_family is used.
    custom_parser: Callable[[str], dict] | None = None    # text -> SSOT dict fragment
    custom_writer: Callable[[dict], str] | None = None    # SSOT dict fragment -> text


@dataclass(frozen=True)
class ResourceRefSpec:
    """Specification for a resource reference (staged, not parsed)."""
    name: str                             # "pseudopotential", "basis_set", "continuation"
    description: str                      # Human-readable
    staging_policy: str                   # "copy", "symlink", "concatenate" (POTCAR)
    source: str                           # "library", "previous_step", "user"


@dataclass(frozen=True)
class SSOTMappingSpec:
    """Declares how SSOT fields map to engine input files."""
    structure_in: str                     # Which input file contains structure data
                                          # "pw.in" (embedded), "POSCAR" (separate), etc.
    kpoints_in: str | None                # Which file contains k-points
                                          # "pw.in" (embedded), "KPOINTS" (separate), None
    params_in: str                        # Which file contains calculation parameters
                                          # "pw.in" (embedded), "INCAR" (separate), etc.
```

### 5.3 Metadata Schema (Parameter Catalogs)

Every engine gets a catalog at this depth:

```python
@dataclass
class EngineMetadata:
    """Near-complete parameter catalog for one engine."""

    engine_family: str                    # "qe", "abinit", etc.
    engine_version: str                   # "7.5", "10.0", etc.
    schema_version: int                   # Start at 1
    generated_at: str                     # ISO 8601
    source: str                           # "scraped:docs.abinit.org", "introspection:pyscf"
    doc_url: str                          # Root documentation URL

    modules: dict[str, ModuleMetadata]    # "pw" → ModuleMetadata


@dataclass
class ModuleMetadata:
    """One program/executable within an engine."""

    name: str                             # "pw", "ph", "FORCE_EVAL"
    display_name: str                     # "pw.x", "ph.x"
    doc_url: str | None                   # Deep link to module docs
    sections: list[SectionMetadata]       # Ordered sections/namelists/blocks


@dataclass
class SectionMetadata:
    """Section/namelist/block definition."""

    name: str                             # "&CONTROL", "%block LatticeVectors"
    kind: str                             # "namelist", "card", "section", "block"
    description: str | None
    optionality: str                      # "required", "conditional", "optional"
    optionality_condition: str | None     # Human-readable condition text
    options: list[str] | None             # Card options: ["crystal", "alat", "bohr"]
    parent_path: str | None               # Nested: "FORCE_EVAL/DFT/SCF"
    parameters: list[ParameterMetadata]


@dataclass
class ParameterMetadata:
    """Single parameter definition — QE-depth for all engines."""

    # Identity
    key: str                              # "ecutwfc", "ENCUT", "CUTOFF"
    aliases: list[str]                    # Alternative names for same param

    # Type
    kind: str                             # "integer", "real", "string", "logical",
                                          # "integer_array", "real_array", "enum"
    enum_values: list[str] | None         # For enum kind
    array_shape: str | None               # "3", "3x3", "natom", "ntyp"

    # Values
    default: str | None                   # Default value (as string)
    unit: str | None                      # Physical unit
    allowed_range: str | None             # "[0, inf)" or "positive integer"

    # Documentation — traceable to source
    description: str | None               # Short description
    long_description: str | None          # Extended docs (from engine manual)
    doc_url: str | None                   # Deep link to parameter in official docs
    doc_section: str | None               # Section in engine manual where documented
    version_added: str | None             # Engine version when added
    version_deprecated: str | None        # Engine version when deprecated
    verified: bool                        # True if confirmed against official docs

    # Classification
    importance: str                       # "core", "advanced", "expert", "deprecated"
    category: str | None                  # "convergence", "symmetry", "io", etc.
    section_path: str                     # "CONTROL", "SYSTEM", "FORCE_EVAL/DFT/SCF"

    # Corpus references (populated by validation harness)
    corpus_frequency: int | None          # How many corpus files use this param
```

### 5.4 Serialization

- **Metadata catalogs**: JSON files in `src/quantumvitas/data/`, one per engine. Human-editable, version-controlled. Schema: `<engine>_parameters.json`.
- **InputDocument**: In-memory only during parsing/writing. Not persisted (no need — the source files and SSOT docs are the persistent representations).
- **DialectSpec / EngineInputSpec**: Python code in driver bundles. Not serialized.

### 5.5 Stability Contract

The InputDocument and ParameterMetadata schemas are versioned. Breaking changes require:

1. Schema version bump
2. Migration path (script or documented manual steps)
3. Governance review if affecting driver protocol

Non-breaking additions (no version bump needed):
- New optional fields with defaults on existing types
- New Node subtypes
- New diagnostic codes

---

## 6. Integration Points in QMatSuite

### 6.1 Where Code Lives

```
src/quantumvitas/
├── inputformat/                       # NEW: Engine-agnostic parsing framework
│   ├── __init__.py                    #   Internal API (NOT public facade)
│   ├── core.py                        #   InputDocument, Node hierarchy,
│   │                                  #   Value, Diagnostic, InputFileSpec,
│   │                                  #   ResourceRefSpec, SSOTMappingSpec
│   ├── dialect.py                     #   DialectSpec, SectionConfig variants
│   ├── metadata.py                    #   EngineMetadata, ParameterMetadata,
│   │                                  #   load/query/validate functions
│   ├── values.py                      #   Value coercion: parse_bool, parse_float,
│   │                                  #   parse_array, format_bool, format_float
│   ├── families/                      #   Family parsers + writers
│   │   ├── __init__.py                #     FamilyParser / FamilyWriter protocols
│   │   ├── base.py                    #     Shared utilities (line iteration,
│   │   │                              #       indentation, line wrapping)
│   │   ├── fortran_namelist.py        #     F1: parse + write
│   │   ├── flat_keyval.py             #     F2: parse + write
│   │   ├── nested_section.py          #     F3: parse + write
│   │   ├── keyword_block.py           #     F4: parse + write
│   │   ├── command_stream.py          #     F5: parse + write
│   │   ├── xml_format.py              #     F6: parse + write
│   │   ├── dollar_flag.py             #     F8: parse + write
│   │   └── python_script.py           #     F7: write only
│   └── harness.py                     #   Corpus validation harness
│
├── data/                              # Metadata catalogs (JSON)
│   ├── qe_module_parameters.json      #   EXISTING (evolve schema)
│   ├── qe_ui_parameters.json          #   EXISTING
│   ├── abinit_parameters.json         #   NEW
│   ├── cp2k_parameters.json           #   NEW
│   ├── vasp_parameters.json           #   NEW
│   ├── orca_parameters.json           #   NEW
│   ├── gaussian_parameters.json       #   NEW
│   ├── lammps_parameters.json         #   NEW
│   ├── siesta_parameters.json         #   NEW
│   ├── w90_parameters.json            #   NEW
│   ├── qmcpack_parameters.json        #   NEW
│   ├── xtb_parameters.json            #   NEW
│   └── yambo_parameters.json          #   NEW
│
├── drivers/                           # EXISTING: Per-engine driver bundles
│   └── <engine>/
│       ├── __init__.py                #   EXISTING (driver registration)
│       ├── driver.py                  #   EXISTING (add get_input_spec method)
│       ├── inputspec.py               #   NEW: EngineInputSpec (dialect + hooks + files)
│       ├── handler.py                 #   EXISTING (unchanged)
│       ├── recipe.py                  #   EXISTING (unchanged)
│       ├── io/                        #   EXISTING (QE only; thin wrappers over inputformat)
│       └── ir/
│           └── mapping.py             #   EXISTING (InputDocument ↔ SSOT dict)
```

### 6.2 Engine Declaration (EngineInputSpec)

Each driver bundle contains an `inputspec.py` that centralizes ALL input format knowledge for that engine:

```python
# src/quantumvitas/drivers/vasp/inputspec.py

from quantumvitas.inputformat.core import InputFileSpec, ResourceRefSpec, SSOTMappingSpec
from quantumvitas.inputformat.dialect import DialectSpec, FlatKeyvalSectionConfig

VASP_DIALECT = DialectSpec(
    comment_chars=("#", "!"),
    line_continuation="\\",
    case_sensitive=False,
    max_line_length=None,
    blank_lines_structural=False,
    section_config=FlatKeyvalSectionConfig(
        block_open=None,
        block_close=None,
        block_name_on_delimiter=False,
        multi_tag_separator=";",
        dataset_suffix_pattern=None,
        label_normalization=None,
    ),
    assignment_operators=("=",),
    value_separators=(",", " "),
    boolean_literals={".TRUE.": True, ".FALSE.": False, "T": True, "F": False},
    string_delimiters=("'", '"'),
    doc_url="https://www.vasp.at/wiki/index.php/Category:INCAR_tag",
    grammar_version="6.4",
)

from quantumvitas.drivers.vasp.io.poscar import parse_poscar_text, write_poscar_text
from quantumvitas.drivers.vasp.io.kpoints import parse_kpoints_text, write_kpoints_text

VASP_INPUT_SPEC = EngineInputSpec(
    engine_family="vasp",
    syntax_family="flat-keyval",
    dialect=VASP_DIALECT,
    hooks={},                             # VASP INCAR has no special grammar quirks
    input_files=(
        InputFileSpec(
            filename="INCAR",
            description="VASP parameter file (TAG = value)",
            content_role="parameters",
            # No custom_parser/writer — uses family flat-keyval parser
        ),
        InputFileSpec(
            filename="POSCAR",
            description="Crystal structure in VASP format",
            content_role="structure",
            custom_parser=parse_poscar_text,   # VASP-specific format
            custom_writer=write_poscar_text,   # not flat-keyval
        ),
        InputFileSpec(
            filename="KPOINTS",
            description="K-point mesh specification",
            content_role="kpoints",
            optional=True,                # Auto k-mesh via KSPACING in INCAR
            custom_parser=parse_kpoints_text,  # VASP-specific format
            custom_writer=write_kpoints_text,  # not flat-keyval
        ),
    ),
    resource_refs=(
        ResourceRefSpec(
            name="pseudopotential",
            description="Pseudopotential data (concatenated per species)",
            staging_policy="concatenate",
            source="library",
        ),
    ),
    ssot_mapping=SSOTMappingSpec(
        structure_in="POSCAR",
        kpoints_in="KPOINTS",
        params_in="INCAR",
    ),
    metadata_source=MetadataSourceSpec(
        kind="json",
        path="data/vasp_parameters.json",
        scrape_url="https://www.vasp.at/wiki/index.php/Category:INCAR_tag",
    ),
    corpus_config=None,                   # Added when corpus is downloaded
)
```

**Driver integration** — the driver returns the spec on request:

```python
# src/quantumvitas/drivers/vasp/driver.py

class VASPDriver(BaseEngineDriver):
    # ... existing 7-item MUST interface ...

    def get_input_spec(self) -> EngineInputSpec:
        from .inputspec import VASP_INPUT_SPEC
        return VASP_INPUT_SPEC
```

### 6.3 Kernel-Internal Parse/Write Functions

The parse/write functions are kernel-internal. They are NOT exposed as a public API facade. The `inputformat/__init__.py` provides internal helper functions used by other kernel code:

```python
# src/quantumvitas/inputformat/__init__.py
# NOTE: This is an internal module. NOT part of the public API facade.

def parse_engine_inputs(
    workdir: Path,
    spec: EngineInputSpec,
) -> tuple[dict, list[Diagnostic]]:
    """Parse all engine input files from workdir into SSOT-compatible dict.

    For each InputFileSpec in spec.input_files:
      1. Read the file from workdir
      2. Select the family parser based on spec.syntax_family
      3. Parse text → InputDocument (comments stripped, semantic only)
      4. Map InputDocument → SSOT dict fragment

    Returns:
        (params_dict, diagnostics) where params_dict is compatible with
        step.yaml engine_params structure, and diagnostics lists any
        warnings/errors encountered.
    """
    ...

def write_engine_inputs(
    params: dict,
    structure: dict | None,
    spec: EngineInputSpec,
    workdir: Path,
) -> list[Path]:
    """Write engine input files to workdir from SSOT dict.

    For each InputFileSpec in spec.input_files:
      1. Map SSOT dict fragment → InputDocument
      2. Select the family writer based on spec.syntax_family
      3. Write InputDocument → canonical text
      4. Write text to file in workdir

    Args:
        params: Dict from step.yaml engine_params section
        structure: Dict from structure.json (cell, positions, species)
        spec: Engine input format specification
        workdir: Directory to write files into

    Returns:
        List of written file paths.
    """
    ...

def get_metadata(engine: str) -> EngineMetadata:
    """Load parameter catalog for an engine."""
    ...
```

**Who calls these functions**:

| Caller | Function | Purpose |
|--------|----------|---------|
| Recipe `.materialize()` | `write_engine_inputs` | Produce engine input files during materialization |
| Kernel import flow | `parse_engine_inputs` | Extract parameters from existing engine inputs |
| Validation harness | Both | Roundtrip testing |
| Metadata queries (kernel) | `get_metadata` | Parameter catalog lookups |

**Who does NOT call these functions**:

| Non-caller | Why |
|-----------|-----|
| API facade | Calls kernel-level import/export functions that internally use parse/write |
| CLI | Calls API facade or kernel entry points |
| Daemon/runner | Calls recipes which internally call `write_engine_inputs` |

### 6.4 Recipe/Materialize Integration

The existing materialize flow (step.yaml → engine input files) is the primary consumer of `write_engine_inputs`. Materialization continues to be a clean rewrite from YAML, as required by the Engine Recipe & Runner Constitution (§1.2).

The parser/writer system adds two capabilities on top:

1. **Import**: Parse external engine input files → extract parameters → produce SSOT-compatible dicts for `step.yaml` and `structure.json`. For importing existing calculations into QMatSuite.
2. **Validation**: After materialization, optionally parse the generated input files back and validate the SSOT roundtrip. For debugging and confidence.

### 6.5 Relationship to Existing QE I/O Code

The existing QE I/O code (`drivers/qe/io/`) is the most mature implementation and serves as the reference model. Migration path:

1. Build `inputformat` framework with `fortran-namelist` family parser
2. QE's `inputspec.py` defines dialect + hooks that encode the same rules as the existing parser
3. Existing `QEInput`/`QEInputParser`/`QEInputGenerator` become thin wrappers that delegate to `inputformat`
4. Eventually remove QE-specific parser code; only `inputspec.py` (dialect + hooks) remains

---

## 7. Validation & Roundtrip Testing

### 7.1 Primary Validation Loop: YAML → Input → YAML

The easiest, most scalable validation is the **writer+parser closed loop**:

```
step.yaml params ──► [writer] ──► engine input file(s) ──► [parser] ──► recovered params
       │                                                                       │
       └──────────────────── semantic equality check ──────────────────────────┘
```

This loop exercises both the writer and parser simultaneously. It can be massively exercised because we control the input (YAML params) and can generate thousands of test cases programmatically.

**Implementation**:

```python
def test_yaml_roundtrip(engine: str, params: dict, structure: dict | None = None):
    """YAML → write → parse → YAML roundtrip test."""
    spec = get_input_spec(engine)

    # 1. Write engine input files to a temp workdir
    written = write_engine_inputs(params, structure, spec, tmp_workdir)

    # 2. Parse back
    recovered_params, diagnostics = parse_engine_inputs(tmp_workdir, spec)

    # 3. Compare (semantic equality — values match, formatting irrelevant)
    assert semantic_equal(params, recovered_params), semantic_diff(params, recovered_params)
    assert not any(d.level == "error" for d in diagnostics)
```

**Test case generation strategies**:
- Enumerate all parameters in metadata catalog, test each individually
- Test combinations of parameters (per section/namelist)
- Test edge cases: empty values, extreme numbers, special characters, long lines
- Fuzz: random valid parameter combinations

### 7.2 Secondary Validation Loop: Input → YAML → Input (Import)

The import direction is harder because external inputs may use features we don't fully support. Since there is no fidelity goal, the comparison uses canonicalized output:

**A. Coverage reports**:
```python
@dataclass
class ImportCoverageReport:
    total_lines: int
    recognized_lines: int                 # Lines that produced semantic nodes
    skipped_lines: int                    # Comment lines, blank lines (stripped)
    unrecognized_lines: int               # Lines that produced diagnostics
    line_coverage: float                  # recognized / (recognized + unrecognized)
    recognized_params: int                # Params found in metadata catalog
    unrecognized_params: int              # Params NOT in catalog
    catalog_hit_rate: float               # recognized / (recognized + unrecognized)
```

**B. Canonicalized semantic diffs**:
```python
def canonicalized_roundtrip(text: str, engine: str) -> tuple[bool, str]:
    """Parse → write → compare semantically."""
    spec = get_input_spec(engine)

    # Parse → InputDocument (comments stripped, semantic only)
    doc = family_parse(text, spec)

    # Write → canonical text
    regenerated = family_write(doc, spec)

    # Parse both into param dicts and compare semantically
    original_params = extract_params(doc)
    regenerated_doc = family_parse(regenerated, spec)
    regenerated_params = extract_params(regenerated_doc)

    match = semantic_equal(original_params, regenerated_params)
    diff = semantic_diff(original_params, regenerated_params) if not match else ""
    return match, diff
```

Note: We compare the extracted parameter dicts, NOT the text. Formatting differences are expected and correct.

**C. Output-signature comparison for golden cases**:
For a small set of golden calc files per engine, validate the import roundtrip by actually running the engine on both the original and regenerated inputs, then comparing output signatures:

```python
@dataclass
class OutputSignature:
    """Lightweight fingerprint of engine output for comparison."""
    total_energy: float | None            # eV, to within tolerance
    n_atoms: int
    n_scf_steps: int | None
    forces_norm: float | None             # |F| in eV/Ang
    structure_digest: str | None          # Hash of final atomic positions
```

This is the strongest validation — it proves that the regenerated input produces the same physics. But it requires engine availability and is slow, so it's reserved for a small golden set (3–5 per engine) run manually or in nightly CI.

### 7.3 Gate Tests (CI)

Small curated samples committed to the repo. Located in `tests/inputformat/`:

```
tests/inputformat/
├── conftest.py
├── samples/                          # Curated inputs (3-5 per engine)
│   ├── qe/
│   │   ├── si_scf.in
│   │   ├── si_relax.in
│   │   └── al_bands.in
│   ├── vasp/
│   │   ├── si_scf_INCAR
│   │   ├── si_scf_POSCAR
│   │   └── si_scf_KPOINTS
│   ├── abinit/
│   │   └── si_scf.abi
│   ├── cp2k/
│   │   └── si_scf.inp
│   ├── orca/
│   │   └── benzene_opt.inp
│   ├── gaussian/
│   │   └── h2o_opt.gjf
│   ├── lammps/
│   │   └── si_minimize.lmp
│   ├── siesta/
│   │   └── si_scf.fdf
│   ├── w90/
│   │   └── si.win
│   ├── qmcpack/
│   │   └── si_vmc.xml
│   ├── xtb/
│   │   └── opt.xcontrol
│   └── yambo/
│       └── gw.in
├── test_yaml_roundtrip.py            # YAML → write → parse → YAML per engine
├── test_import_roundtrip.py          # file → parse → write → semantic compare
├── test_metadata.py                  # Catalog validity (schema, completeness)
├── test_dialect_specs.py             # Dialect spec consistency
└── test_value_coercion.py            # Value parsing/formatting
```

**Gate test assertions**:
1. All curated samples parse without errors (warnings OK)
2. All curated samples pass canonicalized semantic comparison on import roundtrip
3. Zero unrecognized lines in curated samples (100% parse coverage)
4. YAML roundtrip preserves all parameters for curated samples
5. Metadata catalogs are valid JSON, schema-conformant
6. Every parameter in curated samples appears in the metadata catalog

**Note on VASP samples**: VASP samples include all three engine input files (`INCAR`, `POSCAR`, `KPOINTS`) — they are all parsed by the parser, not just `INCAR`.

### 7.4 Corpus Runs (Nightly/Manual)

Not in CI. Run against `.tmp/engine_research/` corpora:

```bash
python -m quantumvitas.inputformat.harness \
    --corpus .tmp/engine_research/qe/examples \
    --engine qe \
    --output .tmp/corpus_reports/qe/
```

**Acceptance targets** (per engine):

| Metric | Target |
|--------|--------|
| YAML roundtrip success | 100% (for all supported params) |
| Import parse success | >= 95% of corpus files |
| Import line coverage | >= 95% |
| Catalog completeness | >= 80% (corpus params found in catalog) |

---

## 8. Corpus Workflow & Demo Gallery

### 8.1 Corpus Directory Structure

```
.tmp/engine_research/
├── qe/
│   ├── docs/                         # Downloaded QE documentation
│   ├── examples/                     # Official QE examples (from source tree)
│   ├── tutorials/                    # QE tutorial inputs
│   ├── tests/                        # QE test suite inputs
│   └── corpora.json                  # Manifest
├── vasp/
│   ├── docs/
│   ├── examples/
│   └── corpora.json
├── abinit/
│   └── ...
└── ... (one directory per engine)
```

**Manifest format** (`corpora.json`):
```json
{
  "engine": "qe",
  "downloaded_at": "2026-02-05T12:00:00Z",
  "sources": [
    {
      "url": "https://github.com/QEF/q-e/tree/master/PW/examples",
      "type": "examples",
      "file_count": 47,
      "license": "GPL-2.0"
    },
    {
      "url": "https://www.quantum-espresso.org/Doc/INPUT_PW.html",
      "type": "docs",
      "file_count": 1,
      "license": "CC-BY-4.0"
    }
  ]
}
```

### 8.2 Corpus Harness

```python
# src/quantumvitas/inputformat/harness.py

@dataclass
class CorpusResult:
    """Result of validating one corpus file."""
    file_path: Path
    engine: str
    parse_success: bool
    write_success: bool
    yaml_roundtrip_match: bool            # construct → write → parse → extract matches
    import_semantic_match: bool           # parse → write → parse → compare params
    unrecognized_line_count: int
    total_line_count: int
    recognized_params: int
    unrecognized_params: int
    diagnostics: list[Diagnostic]


@dataclass
class CoverageReport:
    """Aggregate report for one engine across all corpus files."""
    engine: str
    total_files: int
    parse_success_rate: float
    yaml_roundtrip_rate: float
    import_semantic_match_rate: float
    line_coverage: float
    catalog_completeness: float           # % of corpus params in catalog
    param_catalog_coverage: float         # % of catalog params seen in corpus
    missing_from_catalog: list[str]       # Params in corpus not in catalog
    unused_in_catalog: list[str]          # Params in catalog never seen in corpus
    worst_files: list[CorpusResult]       # Bottom 10 by coverage


def run_corpus_harness(
    corpus_dir: Path,
    engine: str,
    output_dir: Path | None = None,
) -> CoverageReport:
    """Run full validation on all corpus files for an engine."""
```

### 8.3 Demo Gallery Extraction

**Phase** (later, after parsers are stable):

1. **Select candidates**: For each engine, identify corpus files that cover its most common step types using simple structures
2. **Simplify**: Reduce system size (e.g., 2-atom Si instead of 64-atom supercell), coarsen grids (2x2x2 instead of 12x12x12)
3. **Validate**: Run engine on simplified input, record output signature
4. **Package**: Each golden calc becomes:

```
tests/golden_calcs/<engine>/<calc_name>/
├── input/                            # Engine input files
├── expected_output.json              # Output signature (energy, structure digest)
├── step_params.yaml                  # Equivalent step.yaml parameters
└── README.md                         # Pedagogical description
```

Golden calcs serve dual purposes:
- **Demo gallery items** for users
- **End-to-end validation** that the full pipeline (YAML → materialize → run → parse output) works correctly

---

## 9. Extensibility & Future Engines

### 9.1 Adding a New Engine (Existing Syntax Family)

If the new engine uses a syntax family that already has a parser:

1. **Create `inputspec.py`** in `drivers/<engine>/`:
   - Define `DialectSpec` with the engine's grammar rules (~50-100 lines)
   - Define hooks if needed (0–2 hooks typical, < 50 lines each)
   - Define `EngineInputSpec` with file layout, resource refs, SSOT mapping, metadata source

2. **Generate metadata catalog**:
   - Scrape official docs or use machine-readable schema
   - Produce `data/<engine>_parameters.json`
   - Mark each parameter `verified: true/false`

3. **Add to driver**:
   - Add `get_input_spec()` method to driver class
   - No changes to framework code, no changes to kernel

4. **Add gate tests**:
   - 3–5 curated samples in `tests/inputformat/samples/<engine>/`
   - Must pass YAML roundtrip and import semantic comparison

5. **Download corpus**:
   - Populate `.tmp/engine_research/<engine>/`
   - Run harness, fix parser issues until acceptance targets met

**Estimated effort**: 2–4 days for an engine with well-documented input format.

### 9.2 Adding a New Syntax Family

If the new engine uses a grammar not covered by existing families:

1. **Write family module** in `inputformat/families/<family>.py`:
   - `parse(text, dialect, hooks) -> InputDocument`
   - `write(doc, dialect, hooks) -> str`
   - 200–500 lines typical

2. **Define SectionConfig** variant for the family

3. Steps 1–5 from §9.1

**Estimated effort**: 4–7 days.

### 9.3 Future Engine Candidates — Comprehensive Survey

The following 20 engines have been researched for input format compatibility. All engines likely to be added in the next few years fit into existing families:

#### Fit Existing Families (14 of 20)

| Engine | Family | Notes |
|--------|--------|-------|
| **GAMESS** | F1 (fortran-namelist) | `$GROUP ... $END` with `key=value` — exact match |
| **FHI-aims** | F2 (flat-keyval) | `keyword value` in `control.in` — close to ABINIT style |
| **CASTEP** | F2 (flat-keyval) | `.cell`/`.param` with `%block/%endblock` — archetype of flat-keyval |
| **ONETEP** | F2 (flat-keyval) | `%block/%endblock` — identical to CASTEP (same Cambridge origin) |
| **CONQUEST** | F2 (flat-keyval) | `%block/%endblock` with `Key.Name value` — flat-keyval |
| **ABACUS** | F2 (flat-keyval) | `INPUT` file is flat `key value`; `STRU`/`KPT` are engine input files |
| **NWChem** | F4 (keyword-block) | `directive...end` blocks + `task` commands |
| **TURBOMOLE** | F8 (dollar-flag) | `$keyword` data groups — identical to xTB family |
| **FLEUR** | F6 (xml) | Standard XML (`inp.xml`) with XSD schema |
| **Exciting** | F6 (xml) | Standard XML (`input.xml`) with XSD schema |
| **JDFTx** | F5 (command-stream) | `command arg1 arg2` per line — identical to LAMMPS style |
| **GPUMD** | F5 (command-stream) | `keyword param1 param2` per line — sequential commands |
| **DeePMD-kit** | (json/yaml) | Standard JSON/YAML — trivial to parse (use stdlib) |
| **BigDFT** | (yaml) | Standard YAML — trivial to parse (use stdlib) |

#### May Need New Families (6 of 20)

| Engine | Proposed Family | Grammar | Difficulty |
|--------|----------------|---------|-----------|
| **DFTB+** | `hsd` (curly-brace tree) | `Node = value` or `Node { children }`, `[unit]` attributes | Medium — recursive descent parser needed |
| **Elk** | `block-positional` | Named blocks with positional data, implicit block boundaries | Medium — unique format |
| **CRYSTAL** | `sequential-positional` | Three ordered blocks terminated by `END`, context-dependent keywords | High — rigid structure, no key=value |
| **OpenMX** | Could fit F2 with custom block delimiters | `key value` + `<Name...Name>` blocks | Low — flat-keyval variant |
| **WIEN2k** | `fixed-column-fortran` | Column-position-dependent data, Fortran FORMAT layouts | High — completely unique |
| **MOPAC** | Could fit F4 (keyword-block) | Keyword line 1, title lines 2-3, geometry rest | Medium — rigid line-number structure |

**Design impact**: The 8 current families (F1–F8) cover all 15 supported engines and 14 of 20 surveyed future candidates. The remaining 6 candidates either fit with minor dialect extensions (OpenMX, MOPAC) or would need truly new families (DFTB+, Elk, CRYSTAL, WIEN2k). Even in the worst case, only 3–4 new families would be needed to cover the entire landscape of computational science input formats.

**Note on ABACUS**: Like VASP, ABACUS uses multiple engine input files (`INPUT`, `STRU`, `KPT`). This is handled the same way — all three are declared as engine input files in the `EngineInputSpec`, each with its own `content_role`. No special treatment needed.

---

## 10. Module Layout

### 10.1 Complete File Tree

```
src/quantumvitas/inputformat/
├── __init__.py                        # Internal API: parse_engine_inputs,
│                                      #   write_engine_inputs, get_metadata
│                                      #   NOT a public API facade
├── core.py                            # InputDocument, Node hierarchy, Value,
│                                      #   Diagnostic, InputFileSpec, ResourceRefSpec,
│                                      #   SSOTMappingSpec, MetadataSourceSpec
├── dialect.py                         # DialectSpec, SectionConfig variants
├── metadata.py                        # EngineMetadata, ParameterMetadata,
│                                      #   load/query/validate functions
├── values.py                          # Value coercion: parse_bool, parse_float,
│                                      #   parse_array, format_bool, format_float
├── families/
│   ├── __init__.py                    # FamilyParser / FamilyWriter protocols
│   ├── base.py                        # Shared: line iteration, indentation,
│   │                                  #   line wrapping, value formatting
│   ├── fortran_namelist.py            # F1: QE (parse + write)
│   ├── flat_keyval.py                 # F2: ABINIT, Siesta, W90, VASP, Yambo
│   ├── nested_section.py             # F3: CP2K
│   ├── keyword_block.py              # F4: ORCA, Gaussian
│   ├── command_stream.py             # F5: LAMMPS
│   ├── xml_format.py                 # F6: QMCPACK
│   ├── dollar_flag.py                # F8: xTB
│   └── python_script.py              # F7: GPAW, Psi4, PySCF (write only)
└── harness.py                         # Corpus validation harness

# Per-engine declarations (in driver bundles):
src/quantumvitas/drivers/<engine>/inputspec.py

# Metadata catalogs:
src/quantumvitas/data/<engine>_parameters.json
```

### 10.2 Dependency Rules

```
inputformat/               ← LEAF PACKAGE: no imports from drivers/, core/,
                              execution/, api/, or any other qmatsuite package
  core.py                  ← stdlib + dataclasses only
  dialect.py               ← imports core.py only
  metadata.py              ← imports core.py only; reads JSON via pathlib
  values.py                ← stdlib only
  families/*.py            ← imports core.py, dialect.py, values.py
  harness.py               ← imports core.py, metadata.py, families
  __init__.py              ← imports all above (NO DriverRegistry import here)

drivers/<engine>/
  inputspec.py             ← imports inputformat.core, inputformat.dialect
  driver.py                ← imports inputspec.py (lazy, in get_input_spec())
```

**No reverse dependency**: Unlike v0.2, `inputformat/__init__.py` does NOT import `DriverRegistry`. The `inputformat` package is a pure leaf — it takes `EngineInputSpec` as a parameter, never looks up engines itself. The kernel code that calls `parse_engine_inputs` / `write_engine_inputs` is responsible for obtaining the spec from the driver registry.

**Key property**: The entire `inputformat` package is independently testable with zero qmatsuite dependencies. Family parsers/writers take `DialectSpec` and hooks as arguments — they never look up engines themselves.

---

## 11. Phased Implementation Plan

All phases target QE-depth for every engine touched. No maturity tiers — each engine is either "not started" or "complete."

### Phase 0: Framework + QE (reference implementation)

**Scope**: Build the `inputformat` framework and port QE as the first engine.

**Deliverables**:
- `inputformat/core.py` — all data model classes (semantic AST, no formatting)
- `inputformat/dialect.py` — DialectSpec, SectionConfig variants
- `inputformat/values.py` — common value coercion
- `inputformat/families/base.py` — shared parsing/writing utilities
- `inputformat/families/fortran_namelist.py` — F1 parser + writer (ported from QE I/O)
- `drivers/qe/inputspec.py` — QE dialect spec + hooks
- Existing QE tests continue to pass
- QE metadata catalog (`qe_module_parameters.json`) validated against new schema

**Acceptance criteria**:
- 3 curated QE samples pass YAML roundtrip (semantic equality)
- 3 curated QE samples pass import semantic comparison
- Zero unrecognized lines in curated samples
- `inputformat` has zero imports from qmatsuite packages (leaf package)

### Phase 1: Flat-keyval engines (ABINIT, Siesta, VASP, Wannier90, Yambo)

**Scope**: Build the flat-keyval family parser/writer and deploy for 5 engines.

**Deliverables**:
- `inputformat/families/flat_keyval.py` — F2 parser + writer
- `drivers/{abinit,siesta,vasp,w90,yambo}/inputspec.py` — dialect specs + hooks
- `data/{abinit,siesta,vasp,w90,yambo}_parameters.json` — QE-depth metadata catalogs
- Corpus download for all 5 engines
- Corpus harness (`harness.py`) implemented

**Acceptance criteria**:
- 3–5 curated samples per engine pass both roundtrip tests
- Zero unrecognized lines in curated samples
- Metadata catalogs have >= 80% of known parameters (verified against docs)
- Corpus harness produces coverage reports

**Note on VASP**: VASP curated samples include `INCAR` + `POSCAR` + `KPOINTS`. The flat-keyval parser handles `INCAR`. `POSCAR` and `KPOINTS` have their own sub-parsers (registered as hooks or as separate parse functions in the inputspec), since their formats differ from flat-keyval. The `EngineInputSpec` declares all three as engine input files.

### Phase 2: Remaining file-based engines (CP2K, ORCA, Gaussian, LAMMPS, QMCPACK, xTB)

**Scope**: Build remaining family parsers and complete all file-based engines.

**Deliverables**:
- `inputformat/families/{nested_section,keyword_block,command_stream,xml_format,dollar_flag}.py`
- `drivers/{cp2k,orca,gaussian,lammps,qmcpack,xtb}/inputspec.py`
- `data/{cp2k,orca,gaussian,lammps,qmcpack,xtb}_parameters.json`
- Corpus download for all 6 engines

**Acceptance criteria**:
- All 12 file-based engines have complete inputspec + metadata + gate tests
- Corpus harness targets met for all 12 engines
- All 12 engines pass both roundtrip tests on curated samples

### Phase 3: Python-script engines + golden calcs + integration

**Scope**: Complete python-script writers, extract golden calcs, integrate with kernel.

**Deliverables**:
- `inputformat/families/python_script.py` — F7 writer for GPAW, Psi4, PySCF
- Metadata catalogs for GPAW, Psi4, PySCF (via introspection)
- Golden calcs extracted (3–5 per engine, 15 engines)
- Kernel-level import function that uses `parse_engine_inputs` internally
- Kernel-level validation function for post-materialize checking
- QE I/O fully migrated to `inputformat` (old code removed)

**Acceptance criteria**:
- All 15 engines have metadata catalogs at QE-depth
- Golden calcs validated by output signature comparison
- Import and validation flows tested end-to-end via kernel entry points
- Documentation updated

---

## 12. Open Questions

### 12.1 Resolved by This Revision

| Question | Resolution |
|----------|-----------|
| Should VASP be a separate syntax family? | **No.** VASP uses multiple engine input files (INCAR, POSCAR, KPOINTS) — all parsed/written. Multi-file is normal, not special. |
| Should engines have maturity tiers? | **No.** Every engine gets QE-depth or is "not started." |
| How to avoid import-time side effects? | Driver returns `EngineInputSpec` via `get_input_spec()` method — called lazily, not at import. |
| Primary roundtrip direction? | **YAML → write → parse → YAML** is the primary loop. Import roundtrip is secondary. |
| How much whitespace/comment fidelity? | **None.** Comments are stripped. Whitespace is not preserved. Parser extracts semantic content only. Writer produces clean canonical output. Comparison is always semantic (parameter values match). |
| Are POSCAR/KPOINTS "generated assets"? | **No.** There is no "generated asset" concept. POSCAR and KPOINTS are engine input files — parsed and written by the parser/writer system. Structure/k-point data flows from SSOT docs into these files via the writer's SSOT mapping. |
| Should parse/write be API-callable? | **No.** Parser/writer are kernel-internal pure mapping functions. API facade calls higher-level kernel functions that internally use parse/write. |
| What are the SSOT documents? | **Four**: `project.yaml`, `calculation.yaml`, `step.yaml`, `structure.json`. Parser output maps to `step.yaml` engine_params + `structure.json`. |
| Should `inputformat` import DriverRegistry? | **No.** `inputformat` is a pure leaf package. Callers obtain the `EngineInputSpec` from the driver registry and pass it to `inputformat` functions. |
| VASP POSCAR/KPOINTS: which family parser handles them? | **Per-file dispatch via `InputFileSpec.custom_parser/custom_writer`.** POSCAR and KPOINTS are engine-specific formats (not flat-keyval). Each gets its own pure parse/write functions in `drivers/vasp/io/{poscar,kpoints}.py`, registered on the `InputFileSpec` via `custom_parser`/`custom_writer` fields. INCAR continues to use the F2 flat-keyval family parser. `parse_engine_inputs` checks each `InputFileSpec`: if `custom_parser` is set, use it; otherwise, use the family parser. No new syntax family needed. See §5.2 and §6.2 for the updated `InputFileSpec` and VASP example. **Implemented**: `drivers/vasp/io/poscar.py` and `drivers/vasp/io/kpoints.py` with 21 passing roundtrip tests. |

### 12.2 Still Open

1. **Should `inputformat` be extractable as a standalone PyPI package?**
   Build as internal leaf package first. The dependency rules (§10.2) are designed to make extraction possible later.

2. **Metadata catalog auto-generation vs. hand-curation?**
   Auto-generate from engine docs/schemas as a starting point. Human review and `verified: true/false` flag per parameter. Final catalogs are committed and version-controlled.

3. **CP2K: regex or recursive descent?**
   CP2K's deeply nested format (4–5 levels) may benefit from a recursive descent parser rather than regex-based line tokenization. Decide during Phase 2 implementation.

4. **Gaussian: how to handle missing comment syntax?**
   Gaussian has no comment character. Blank lines are structural terminators (`blank_lines_structural: True` in DialectSpec). The writer must be careful never to emit stray blank lines.

5. **LAMMPS: how deep to parse command arguments?**
   LAMMPS has ~500+ commands with different argument schemas. Option A: parse commands generically (command + string args). Option B: parse known commands with typed args. **Recommendation**: Start with A (generic), add typed parsing for high-value commands (fix, pair_style, etc.) incrementally.

---

*End of design document.*
