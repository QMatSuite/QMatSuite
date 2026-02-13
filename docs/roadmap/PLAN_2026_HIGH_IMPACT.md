# QMatSuite 2026 High-Impact Evolution Plan

**Version**: 1.0  
**Date**: 2026-01-02  
**Author**: Architecture Team  
**Status**: Implementation Ready

---

## Table of Contents

1. [Vision & Non-Goals](#1-vision--non-goals)
2. [Architectural Invariants](#2-architectural-invariants)
3. [Current State Assessment](#3-current-state-assessment)
4. [Proposed Target Architecture](#4-proposed-target-architecture)
5. [Milestones & Phases](#5-milestones--phases)
6. [PR Sequence Plan](#6-pr-sequence-plan)
7. [Test Strategy & CI Gates](#7-test-strategy--ci-gates)
8. [Wannier90 Integration Plan](#8-wannier90-integration-plan)
9. [PySCF Integration Plan](#9-pyscf-integration-plan)
10. [Packaging & Distribution](#10-packaging--distribution)
11. [UI Bug-Bash & E2E Strategy](#11-ui-bug-bash--e2e-strategy)
12. [Release & Marketing Plan](#12-release--marketing-plan)
13. [Risk Register](#13-risk-register)

---

## 1. Vision & Non-Goals

### 1.1 Vision

QMatSuite evolves into a **multi-engine computational materials science platform** that:
- Supports periodic systems (QE, Wannier90) and molecular systems (PySCF)
- Provides a "golden path" demo experience for new users
- Enables reproducible calculation sharing via standardized bundles
- Maintains strict architectural invariants for data integrity

### 1.2 Goals for 2026

| Goal | Priority | Target Date |
|------|----------|-------------|
| Role-based preset applicability | High | Q1 2026 |
| Project bundle export (3 levels) | High | Q1 2026 |
| Calc type / system_kind enforcement | High | Q1 2026 |
| Wannier90 integration (MVP) | High | Q2 2026 |
| PySCF integration (proof of concept) | Medium | Q2 2026 |
| Packaging & distribution strategy | Medium | Q3 2026 |
| UI bug-bash & E2E testing | Medium | Q3 2026 |
| v1.0 release with marketing | High | Q4 2026 |

### 1.3 Non-Goals

- **VASP integration** - Proprietary, licensing complexity
- **Gaussian integration** - Proprietary, not a priority
- **Full QM/MM support** - Future roadmap item
- **Cloud execution backend** - Desktop-first for v1.0
- **Workflow persistence** - Constitution explicitly forbids this

---

## 2. Architectural Invariants

These invariants are extracted from `CONSTITUTION_ZH.md` and MUST be respected:

### 2.1 Truth Layer Invariants

| ID | Invariant | Constitution Ref |
|----|-----------|-----------------|
| T1 | `step.yml` is the only executable truth | §10.1.1 |
| T2 | `step.yml` must not contain workflow/preset metadata | §10.1.2 |
| T3 | Workflow and preset are runtime interpretations only | §10.2.1 |
| T4 | Preset apply writes only declared ParamSpace keys | §10.3.3 |
| T5 | No "Selected vs Detected" dual-track model | §10.4.2 |

### 2.2 Identity Invariants

| ID | Invariant | Constitution Ref |
|----|-----------|-----------------|
| I1 | ULID-only cross-resource references | §2.1 |
| I2 | Pseudo identity triple: filename + sha256 + sha_family | §7.6 |
| I3 | UI never writes pseudo files; only Step0 does | §7.3 |
| I4 | Step0 must refresh pseudo triplet after materialization | §7.6 |

### 2.3 Engine Invariants

| ID | Invariant | Constitution Ref |
|----|-----------|-----------------|
| E1 | Two-state QE model: external (bin_dir) or internal | §9.4.2 |
| E2 | No PATH fallback for engine discovery | §9.4.3 |
| E3 | Internal engines under `.qmatsuite/engines/` | §9.1.1 |

### 2.4 New Invariants (This Plan)

| ID | Invariant | Source |
|----|-----------|--------|
| N1 | StepRole is inferred at runtime, never persisted | Decision A |
| N2 | Bundle manifest must include pseudo identity triples | Decision B |
| N3 | Calc system_kind is immutable after creation | Decision C |
| N4 | Same calculation cannot mix incompatible engine groups | Decision C |

---

## 3. Current State Assessment

### 3.1 What Exists (✅)

| Module | Status | Notes |
|--------|--------|-------|
| ParamSpace framework | Complete | §10.7 fully implemented |
| Preset compiler/detector | Complete | Thin wrappers work correctly |
| Variants registry | Complete | applies_to_step_types working |
| Workflow templates | Complete | Runtime-only, not persisted |
| StepTypeRegistry | Complete | Centralized step knowledge |
| Pseudo management | Complete | Triplet, materialization |
| Two-state QE engine | Complete | bin_dir or internal |
| Project snapshot | Partial | Needs bundle levels |

### 3.2 What's Missing (❌)

| Feature | Gap Description | Spec Reference |
|---------|-----------------|----------------|
| Role inference | No topology-based role system | `ROLE_INFERENCE_SPEC.md` |
| Bundle levels | Single export format only | `PROJECT_BUNDLE_SPEC.md` |
| Calc type constraints | No system_kind enforcement | `CALC_TYPE_SYSTEM_KIND_SPEC.md` |
| Wannier90 integration | Step types declared, not implemented | This document §8 |
| PySCF integration | Not started | This document §9 |
| E2E UI testing | Only basic Playwright tests | This document §11 |

### 3.3 Code Inventory Summary

See `CODE_REVIEW_ARCH_AUDIT.md` for detailed file-by-file inventory.

Key statistics:
- **Presets module**: 6 files, ~3000 LOC, complete
- **Workflow module**: 3 files, ~1500 LOC, complete
- **Pseudo module**: 8 files, ~2500 LOC, complete
- **Snapshot module**: 1 file, ~800 LOC, needs enhancement

---

## 4. Proposed Target Architecture

### 4.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         QMatSuite v1.0                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │    GUI    │  │    CLI    │  │   Daemon  │  │   API     │    │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘    │
│        └──────────────┴──────────────┴──────────────┘           │
│                              │                                   │
│  ┌───────────────────────────┴───────────────────────────┐      │
│  │                   QVService (Core API)                 │      │
│  ├────────────────────────────────────────────────────────┤      │
│  │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │      │
│  │ │  Preset  │ │ Workflow │ │  Bundle  │ │ Calc Type  │ │      │
│  │ │ Compiler │ │ Service  │ │ Exporter │ │ Enforcer   │ │      │
│  │ │ Detector │ │ Registry │ │ Importer │ │            │ │      │
│  │ └──────────┘ └──────────┘ └──────────┘ └────────────┘ │      │
│  ├────────────────────────────────────────────────────────┤      │
│  │ ┌──────────────────┐  ┌─────────────────────────────┐ │      │
│  │ │   Role Inference │  │     Engine Manager          │ │      │
│  │ │   (NEW)          │  │  ┌─────┐ ┌──────┐ ┌──────┐  │ │      │
│  │ └──────────────────┘  │  │ QE  │ │ W90  │ │PySCF │  │ │      │
│  │                       │  └─────┘ └──────┘ └──────┘  │ │      │
│  │                       └─────────────────────────────┘ │      │
│  └────────────────────────────────────────────────────────┘      │
│                              │                                   │
│  ┌───────────────────────────┴───────────────────────────┐      │
│  │               Project / Calculation / Step             │      │
│  │    ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │      │
│  │    │ YamlDoc     │  │ Pseudo Mgmt  │  │ Structure  │  │      │
│  │    │ Journal     │  │ Triplet      │  │ Geometry   │  │      │
│  │    └─────────────┘  └──────────────┘  └────────────┘  │      │
│  └────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 New Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Role Inference | `workflow/role_inference.py` | Topology → StepRole |
| Bundle Export | `project/bundle.py` | 3-level project export |
| Calc Type Enforcer | `calculation/type_enforcer.py` | system_kind enforcement |
| Wannier90 Engine | `engine/wannier90_engine.py` | W90 adapter |
| PySCF Engine | `engine/pyscf_engine.py` | PySCF adapter |

---

## 5. Milestones & Phases

### Phase 1: Foundation (Q1 2026)

**Milestone 1.1: Role Inference** (2 weeks)
- [ ] Implement `StepRole` enum
- [ ] Implement `infer_step_roles()` pure function
- [ ] Extend `ParamSpaceVariant` with `applies_to_roles`
- [ ] Update `variants_registry.py` matching logic
- [ ] Add unit tests for role inference
- [ ] Add contract tests for role-variant matching

**Milestone 1.2: Project Bundles** (2 weeks)
- [ ] Define `BundleLevel` enum
- [ ] Implement `export_bundle()` API
- [ ] Implement `import_bundle()` API
- [ ] Implement manifest schema with file hashes
- [ ] Implement staleness detection for analysis
- [ ] Add bundle roundtrip tests

**Milestone 1.3: Calc Type System** (2 weeks)
- [ ] Add `SystemKind` enum
- [ ] Add `EngineGroup` enum
- [ ] Extend `CalculationModel` with new fields
- [ ] Add immutability enforcement
- [ ] Add engine compatibility validation
- [ ] Update UI to filter workflows by system_kind

**Acceptance Criteria**:
- All unit tests pass
- No constitution violations
- Existing tests unbroken

### Phase 2: Integration Proof (Q2 2026)

**Milestone 2.1: Wannier90 MVP** (4 weeks)
- [ ] Add step types: `w90_preproc`, `pw2wannier90`, `w90_main`
- [ ] Implement Wannier90 engine adapter
- [ ] Implement `.win` file generator
- [ ] Implement `.win` file parser
- [ ] Define cross-engine data dependencies
- [ ] Create "Silicon Wannier Bands" demo project
- [ ] Add E2E test for Wannier90 workflow

**Milestone 2.2: PySCF Proof of Concept** (4 weeks)
- [ ] Add step types: `pyscf_rhf`, `pyscf_dft`
- [ ] Implement PySCF engine adapter (python-native)
- [ ] Implement molecular structure handling
- [ ] Create "Water Single Point" demo project
- [ ] Validate system_kind enforcement works
- [ ] Add E2E test for PySCF workflow

**Acceptance Criteria**:
- Demo projects run end-to-end
- Cross-engine data flow works (W90)
- Molecular calculations work (PySCF)

### Phase 3: Production Readiness (Q3 2026)

**Milestone 3.1: Packaging & Distribution** (4 weeks)
- [ ] Define packaging strategy (pyinstaller/electron-builder)
- [ ] Implement managed engine bundling
- [ ] Implement seed/asset distribution
- [ ] Implement rollback mechanism
- [ ] Create update check mechanism
- [ ] Document installation procedures

**Milestone 3.2: UI Bug-Bash** (4 weeks)
- [ ] Create structured UI test checklist
- [ ] Implement record/replay E2E harness
- [ ] Fix identified bugs
- [ ] Performance profiling and optimization
- [ ] Accessibility audit

**Acceptance Criteria**:
- App packages for macOS/Linux/Windows
- No P0/P1 bugs
- E2E tests cover golden paths

### Phase 4: Release (Q4 2026)

**Milestone 4.1: Documentation** (2 weeks)
- [ ] User guide for each workflow type
- [ ] Developer documentation
- [ ] API reference documentation
- [ ] Video tutorials for demo projects

**Milestone 4.2: v1.0 Release** (2 weeks)
- [ ] Final QA pass
- [ ] Release candidate testing
- [ ] Marketing materials
- [ ] Launch announcement

---

## 6. PR Sequence Plan

### Phase 1 PRs

| PR # | Title | Files Touched | Tests | Risk |
|------|-------|---------------|-------|------|
| 1.1.1 | Add StepRole enum | `workflow/role_inference.py` | Unit | Low |
| 1.1.2 | Implement role inference algorithm | `workflow/role_inference.py` | Unit | Low |
| 1.1.3 | Extend ParamSpaceVariant with roles | `presets/space_variant.py`, `presets/variants_registry.py` | Contract | Medium |
| 1.2.1 | Add BundleLevel and manifest schema | `project/bundle_manifest.py` | Unit | Low |
| 1.2.2 | Implement export_bundle | `project/bundle.py` | Integration | Medium |
| 1.2.3 | Implement import_bundle | `project/bundle.py` | Integration | Medium |
| 1.2.4 | Add staleness detection | `project/bundle.py` | Unit | Low |
| 1.3.1 | Add SystemKind and EngineGroup enums | `core/models.py`, `workflow/registry.py` | Unit | Low |
| 1.3.2 | Add calc type to CalculationModel | `core/models.py` | Unit | Low |
| 1.3.3 | Implement immutability enforcement | `calculation/calculation.py` | Contract | Medium |
| 1.3.4 | Implement engine compatibility checks | `calculation/type_enforcer.py` | Contract | Medium |

### Phase 2 PRs

| PR # | Title | Files Touched | Tests | Risk |
|------|-------|---------------|-------|------|
| 2.1.1 | Add Wannier90 step types | `workflow/registry.py`, `calculation/step_defaults.py` | Unit | Low |
| 2.1.2 | Implement Wannier90 engine adapter | `engine/wannier90_engine.py` | Unit | Medium |
| 2.1.3 | Implement .win file generator | `io/generator/wannier90_generator.py` | Unit | Medium |
| 2.1.4 | Implement .win file parser | `io/parser/wannier90_parser.py` | Unit | Medium |
| 2.1.5 | Add cross-engine dependencies | `workflow/data_dependencies.py` | Contract | Medium |
| 2.1.6 | Add Silicon Wannier demo | `resources/demo_projects/` | E2E | Low |
| 2.2.1 | Add PySCF step types | `workflow/registry.py` | Unit | Low |
| 2.2.2 | Implement PySCF engine adapter | `engine/pyscf_engine.py` | Unit | Medium |
| 2.2.3 | Add Water single point demo | `resources/demo_projects/` | E2E | Low |

### PR Guidelines

1. **Each PR < 500 LOC** - Easier review
2. **Tests in same PR** - No test debt
3. **No breaking changes without migration** - Backward compatible
4. **Constitution compliance verified** - Mandatory review checklist item

---

## 7. Test Strategy & CI Gates

### 7.1 Test Pyramid

```
           ┌─────────────┐
           │   E2E (5%)  │  UI automation, demo workflows
           ├─────────────┤
           │Integration  │  Cross-module, file I/O
           │   (15%)     │
           ├─────────────┤
           │Contract(20%)│  Roundtrip, compatibility
           ├─────────────┤
           │ Unit (60%)  │  Pure functions, isolated logic
           └─────────────┘
```

### 7.2 New Test Categories

| Category | Purpose | Location |
|----------|---------|----------|
| Role Inference | Topology → role mapping | `tests/unit/test_role_inference.py` |
| Bundle Export | Manifest, hashes, levels | `tests/unit/test_bundle.py` |
| Calc Type | Immutability, compatibility | `tests/unit/test_calc_type.py` |
| W90 Integration | E2E workflow | `tests/integration/test_wannier90.py` |
| PySCF Integration | E2E workflow | `tests/integration/test_pyscf.py` |

### 7.3 CI Pipeline Extensions

```yaml
# .github/workflows/tests.yml additions

- name: Role Inference Tests
  run: pytest tests/unit/test_role_inference.py -v

- name: Bundle Tests
  run: pytest tests/unit/test_bundle.py -v

- name: Calc Type Tests  
  run: pytest tests/unit/test_calc_type.py -v

- name: Wannier90 Integration
  run: pytest tests/integration/test_wannier90.py -v
  env:
    QE_BIN_DIR: ${{ github.workspace }}/.qmatsuite/engines/qe/bin

- name: Constitution Compliance Check
  run: python tools/check_constitution_compliance.py
```

### 7.4 Contract Test Requirements

Per Constitution §10.7.7, all preset dimensions must have:
1. **Roundtrip test**: `apply → detect == original`
2. **NOT_APPLICABLE test**: If key present, detect returns CUSTOM
3. **Alias test**: Synonyms detect to same profile

---

## 8. Wannier90 Integration Plan

### 8.1 Overview

Wannier90 is the first non-QE engine integration. It demonstrates:
- Cross-engine data dependencies
- Multi-executable workflows
- Different input file format (`.win` vs QE namelists)

### 8.2 Step Types

| Step Type | Executable | Purpose |
|-----------|------------|---------|
| `w90_preproc` | `wannier90.x -pp` | Generate .nnkp |
| `pw2wannier90` | `pw2wannier90.x` | Generate .mmn/.amn/.eig |
| `w90_main` | `wannier90.x` | MLWF construction |
| `postw90` | `postw90.x` | Berry/transport (v2) |

### 8.3 Workflow Templates

```python
# Wannier90 workflow templates
_WORKFLOWS["wannier_mlwf"] = WorkflowTemplate(
    id="wannier_mlwf",
    name="Wannier90 MLWFs",
    description="Construct maximally localized Wannier functions",
    step_sequence=("scf", "nscf", "w90_preproc", "pw2wannier90", "w90_main"),
)

_WORKFLOWS["wannier_bands"] = WorkflowTemplate(
    id="wannier_bands",
    name="Wannier90 Band Interpolation",
    description="Interpolate bands from Wannier functions",
    step_sequence=("scf", "nscf", "w90_preproc", "pw2wannier90", "w90_main"),
    # w90_main configured with kpoint_path
)
```

### 8.4 Data Dependencies

```python
DATA_DEPENDENCIES = {
    "w90_preproc": {
        "produces": ["seedname.nnkp"],
    },
    "pw2wannier90": {
        "requires": ["seedname.nnkp", "QE wavefunctions"],
        "produces": ["seedname.mmn", "seedname.amn", "seedname.eig"],
    },
    "w90_main": {
        "requires": ["seedname.mmn", "seedname.amn", "seedname.eig"],
        "produces": ["seedname.chk", "seedname_hr.dat"],
    },
}
```

### 8.5 Demo Project

**Silicon Wannier90 Band Interpolation**:
- Structure: Bulk silicon
- Workflow: SCF → NSCF → W90 → pw2wannier90 → W90 main
- Output: Interpolated bands, _hr.dat file
- Analysis: Compare DFT bands vs Wannier bands

### 8.6 References

- [Wannier90 User Guide](http://www.wannier.org/support/)
- [pw2wannier90 QE documentation](https://www.quantum-espresso.org/Doc/INPUT_pw2wannier90.html)
- QE test-suite: `wannier90/` examples

---

## 9. PySCF Integration Plan

### 9.1 Overview

PySCF integration is an architectural stress test:
- **Molecular system_kind**: Uses `gto.Mole` (no lattice) for molecular calculations
- **Periodic PySCF**: Uses `pbc.gto.Cell` (with lattice) and is classified as PERIODIC
- Python-native execution (no external binary)
- Different quantum chemistry paradigm

### 9.2 Step Types

| Step Type | Method | Purpose |
|-----------|--------|---------|
| `pyscf_rhf` | RHF | Restricted Hartree-Fock |
| `pyscf_uhf` | UHF | Unrestricted Hartree-Fock |
| `pyscf_dft` | DFT | Kohn-Sham DFT (various functionals) |
| `pyscf_opt` | Geom Opt | Geometry optimization (v2) |

### 9.3 Engine Adapter

```python
class PySCFEngine(Engine):
    """PySCF engine adapter."""
    
    def __init__(self, config: EngineConfig):
        super().__init__(config)
        self.name = "pyscf"
    
    def detect_executable(self) -> bool:
        """Check if PySCF is importable."""
        try:
            import pyscf
            return True
        except ImportError:
            return False
    
    def generate_input(self, step_type, input_data, working_dir, input_filename=None):
        """Generate PySCF input script."""
        # Generate Python script that runs PySCF
        script = self._generate_pyscf_script(step_type, input_data)
        path = working_dir / (input_filename or "pyscf_input.py")
        path.write_text(script)
        return path
    
    def build_command(self, step_type, input_file, working_dir):
        """Build command to run PySCF script."""
        return ["python", str(input_file)]
```

### 9.4 Demo Project

**Water Molecule Single Point**:
- Structure: H2O molecule (no lattice)
- Workflow: RHF single point
- Output: Energy, HOMO/LUMO
- Analysis: Orbital energies

### 9.5 System Kind Enforcement

```python
# PySCF steps only work with molecular system_kind
_STEP_TYPES["pyscf_rhf"] = StepTypeSpec(
    id="pyscf_rhf",
    engine="pyscf",
    engine_group=EngineGroup.MOLECULAR_QC,
    allowed_system_kinds=frozenset({SystemKind.MOLECULAR}),
    ...
)
```

### 9.6 References

- [PySCF Documentation](https://pyscf.org/user.html)
- [PySCF GitHub Examples](https://github.com/pyscf/pyscf/tree/master/examples)

---

## 10. Packaging & Distribution

### 10.1 Current State

- Python package: `pip install quantumvitas`
- Electron GUI: Development build only
- No managed engines bundled

### 10.2 Target Distribution

| Component | macOS | Linux | Windows |
|-----------|-------|-------|---------|
| GUI App | `.dmg` | `.AppImage` | `.exe` installer |
| QE Engine | Bundled | Bundled | oneAPI build |
| Wannier90 | Bundled | Bundled | Bundled |
| PySCF | pip install | pip install | pip install |
| Pseudos | SSSP seed | SSSP seed | SSSP seed |

### 10.3 Packaging Strategy

**macOS/Linux**:
```
QMatSuite.app/
├── Contents/
│   ├── MacOS/
│   │   └── QMatSuite
│   ├── Resources/
│   │   ├── python/           # Bundled Python
│   │   ├── quantumvitas/     # Python package
│   │   └── engines/
│   │       ├── qe/           # Pre-built QE
│   │       └── wannier90/    # Pre-built W90
│   └── Info.plist
```

**Windows**:
- Use electron-builder with NSIS installer
- QE built with oneAPI + MKL
- Include VS redistributables

### 10.4 Update Mechanism

**Staged approach**:
1. **v1.0**: Manual download + reinstall
2. **v1.1**: Update check notification
3. **v2.0**: In-app update with rollback

### 10.5 Seed/Asset Management

```
~/.qmatsuite/
├── seeds/
│   ├── qe/
│   │   └── qe-7.3-darwin-arm64.tar.gz
│   └── pseudo/
│       └── sssp-1.3.0-precision.tar.gz
├── engines/
│   └── qe/
│       └── qe-7.3/
│           └── bin/
└── libraries/
    └── pseudo/
        └── sssp/
            └── 1.3.0/
                └── precision/
```

---

## 11. UI Bug-Bash & E2E Strategy

### 11.1 Structured UI Test Checklist

**Project Management**:
- [ ] Create new project
- [ ] Open existing project
- [ ] Close project
- [ ] Delete project (with confirmation)

**Structure Management**:
- [ ] Import structure from CIF
- [ ] Import structure from XYZ
- [ ] View structure in 3D viewer
- [ ] Edit structure properties

**Calculation Workflows**:
- [ ] Create DOS workflow
- [ ] Create Bands workflow
- [ ] Create Relaxation workflow
- [ ] Run calculation
- [ ] View calculation progress
- [ ] View calculation results

**Presets**:
- [ ] Change magnetism preset
- [ ] Change precision preset
- [ ] Verify preset detection
- [ ] Verify preset persistence

**Settings**:
- [ ] Configure QE engine path
- [ ] Install pseudo library
- [ ] View installed pseudos

### 11.2 E2E Test Harness

**Technology**: Playwright + custom QMatSuite helpers

```typescript
// Example E2E test
test('silicon bands workflow', async ({ page }) => {
  // Open demo project
  await page.click('[data-testid="open-demo"]');
  await page.click('[data-testid="demo-si-bands"]');
  
  // Verify workflow detected
  await expect(page.locator('[data-testid="workflow-badge"]'))
    .toHaveText('Band Structure');
  
  // Run calculation
  await page.click('[data-testid="run-button"]');
  
  // Wait for completion
  await page.waitForSelector('[data-testid="status-completed"]', { timeout: 60000 });
  
  // Verify bands plot
  await expect(page.locator('[data-testid="bands-plot"]')).toBeVisible();
});
```

### 11.3 Record/Replay Strategy

1. **Record**: Use Playwright codegen to record user sessions
2. **Sanitize**: Remove timing-dependent assertions
3. **Parameterize**: Use data-testid attributes
4. **Run**: Nightly CI with full E2E suite

---

## 12. Release & Marketing Plan

### 12.1 Golden Path Demo Experience

**Primary Demo**: Silicon Band Structure
- Time to first result: < 5 minutes
- No installation beyond app
- Clear visual result (band diagram)

**User Journey**:
1. Download and install QMatSuite
2. Open "Silicon Bands" demo from gallery
3. Click "Run" (QE engine auto-detected)
4. View band structure plot
5. Export publication-ready figure

### 12.2 Marketing Materials

| Material | Purpose | Format |
|----------|---------|--------|
| Landing page | First impression | Web |
| Demo video | 2-minute walkthrough | YouTube |
| Tutorial series | Learning path | Web + Video |
| Comparison chart | vs competitors | PDF |
| Academic paper | Citation | arXiv |

### 12.3 Launch Timeline

| Date | Activity |
|------|----------|
| T-4 weeks | Release candidate |
| T-2 weeks | Documentation freeze |
| T-1 week | Marketing materials ready |
| T-0 | v1.0 release |
| T+1 week | Academic paper submission |
| T+2 weeks | Workshop/webinar |

---

## 13. Risk Register

### 13.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Wannier90 cross-engine complexity | Medium | High | Start with simple Si example |
| PySCF Python version conflicts | Medium | Medium | Pin Python version in package |
| Windows QE build issues | High | Medium | Use prebuilt binaries from QE |
| UI performance degradation | Medium | Medium | Profile early, optimize late |

### 13.2 Schedule Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Underestimated Wannier90 scope | Medium | High | MVP first, iterate |
| E2E test flakiness | High | Medium | Robust selectors, retries |
| Documentation debt | High | Medium | Write docs with features |

### 13.3 Adoption Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Users expect VASP support | High | Medium | Clear messaging on scope |
| Installation friction | Medium | High | One-click installer |
| Compute cluster integration | Medium | Medium | Document manual setup |

---

## Appendix A: Reference Documents

| Document | Location |
|----------|----------|
| Constitution | `CONSTITUTION_ZH.md` |
| Workflow/Preset Design | `docs/WORKFLOW_PRESET_DESIGN_V0.md` |
| Code Review Audit | `docs/roadmap/CODE_REVIEW_ARCH_AUDIT.md` |
| Role Inference Spec | `docs/design/ROLE_INFERENCE_SPEC.md` |
| Project Bundle Spec | `docs/design/PROJECT_BUNDLE_SPEC.md` |
| Calc Type Spec | `docs/laws/L2/CALC_TYPE_SYSTEM_KIND_SPEC.md` |

---

## Appendix B: Key Decisions Summary

| ID | Decision | Rationale |
|----|----------|-----------|
| A | StepRole as compile-time concept | Enables context-aware presets without persisting workflow |
| B | 3-level export bundles | Balances reproducibility vs file size |
| C | Calc type immutability | Prevents silent data corruption |
| D | Workflow as topology fingerprint | Avoids workflow as persisted entity |
| E | W90 + PySCF as integration proof | Tests engine abstraction |
| F | Desktop-first packaging | Simpler UX for v1.0 |

---

---

## 12. Pre-Milestone Paving Tasks

Before starting major milestone work, complete these small, low-risk improvements:

### 12.1 Demo Generator Hygiene

- [x] Demo generator writes pseudo identity triple (pseudo_basename, pseudo_sha256, pseudo_sha_family)
- [x] Demo generators skip demos with missing pseudos (no broken demos)
- [x] Demo verification tool added (`tools/verify_demos.py`)
- [ ] Demo regeneration completed (with skip list documented)
- [ ] All existing demos verified and regenerated

**Commands**:
```bash
# Regenerate main demos
python tools/generate_demo_snapshots.py

# Regenerate tutorial demos
python tools/import_tutorial_datasets.py

# Verify all demos
python tools/verify_demos.py
```

### 12.2 Documentation Fixes

- [x] PySCF system_kind doc fix applied (molecular = no lattice, periodic = with lattice)
- [x] Removed vacuum heuristics from system_kind inference spec
- [x] Updated PLAN and CALC_TYPE_SYSTEM_KIND_SPEC with correct PySCF distinction

### 12.3 Other Low-Risk Improvements

- [ ] Verify all demo YAML files have complete pseudo triplets
- [ ] Document demo generation workflow in `docs/DEMO_GENERATION.md` (if not already done)
- [ ] Add CI check to run `tools/verify_demos.py` on PRs

---

## 13. Wannier90 Integration (MVP)

**Goal**: Enable end-to-end Wannier90 workflows (SCF → NSCF → Wannier90) using the bundled QE engine.

**Status**: ✅ MVP Implemented

### 13.1 Architecture

**New Step Types**:
| Step Type | Executable | Description |
|-----------|------------|-------------|
| `w90_preproc` | `wannier90.x -pp` | Generate `.nnkp` file |
| `pw2wannier90` | `pw2wannier90.x` | Compute overlaps (`.mmn`, `.amn`, `.eig`) |
| `w90_run` | `wannier90.x` | Main MLWF optimization |

**Dependency Graph** (Diamond Workflow):
```
SCF (pw.x)
    ↓
NSCF (pw.x, uniform k-grid)
    ↓
w90_preproc (wannier90.x -pp) ← requires .win file
    ↓
pw2wannier90 (pw2wannier90.x) ← requires .nnkp + QE save files
    ↓
w90_run (wannier90.x) ← requires .win + .mmn + .amn + .eig
```

### 13.2 Implementation Checklist

- [x] Create `docs/design/engine_integration/WANNIER90_INTEGRATION_SPEC.md`
- [x] Add `W90_PREPROC`, `PW2WANNIER90`, `W90_RUN` to `StepType` enum
- [x] Register W90 step types in `workflow/registry.py`
- [x] Add W90 executables to `EXECUTABLE_MAP` in `core/engines/qe.py`
- [x] Add W90 to `KNOWN_STEP_TYPES` in `cli/main.py`
- [x] Implement `.win` file parser/generator (`io/wannier90_input.py`)
- [x] Implement `.pw2wan` file generator (`io/wannier90_input.py`)
- [x] Add W90-specific command building in `build_command()`
- [x] Add W90-specific execution logic in `run_step()` (no stdin for W90)
- [x] Create Diamond demo generator (`tools/generate_wannier90_demo.py`)
- [x] Copy `C.pz-vbc.UPF` pseudo to `resources/pseudo/`
- [x] Generate `diamond_wannier90_demo.yml` demo project

### 13.3 Demo Project

**File**: `resources/demo_projects/diamond_wannier90_demo.yml`

**Contents**:
- 1 structure: Diamond (2 C atoms, FCC)
- 1 calculation with 5 steps:
  1. `scf` (pw.x)
  2. `nscf` (pw.x, 4×4×4 k-grid)
  3. `w90_preproc` (wannier90.x -pp diamond)
  4. `pw2wannier90` (pw2wannier90.x)
  5. `w90_run` (wannier90.x diamond)

**Species Map** includes complete pseudo identity triple:
```yaml
C:
  mass: 12.0
  pseudopot: C.pz-vbc.UPF
  pseudo_basename: C.pz-vbc.UPF
  pseudo_sha256: 62d92a1d77af114f...
  pseudo_sha_family: 013161d04858e342...
```

### 13.4 Commands

```bash
# Generate the Wannier90 demo
python tools/generate_wannier90_demo.py

# Verify demo was created correctly
python tools/verify_demos.py

# Run Wannier90 unit tests
python -m pytest tests/unit/test_wannier90_integration.py -v

# Run Wannier90 project-based integration tests (runs real QE + Wannier90)
python -m pytest tests/integration/test_wannier90_project_execution.py -v -s

# Run all Wannier90 tests
python -m pytest tests/unit/test_wannier90_integration.py tests/integration/test_wannier90_project_execution.py -v
```

### 13.5 Test Results (2026-01-02)

**All tests pass across two test suites:**

#### Unit + Roundtrip Tests (34 tests)

| Test Suite | Tests | Status |
|------------|-------|--------|
| Unit: StepType Registration | 6 | ✅ |
| Unit: .win Parsing/Generation | 7 | ✅ |
| Unit: .pw2wan Parsing/Generation | 3 | ✅ |
| Unit: K-point Generation | 2 | ✅ |
| Unit: Demo Validation | 3 | ✅ |
| Integration: Example05 Diamond | 1 | ✅ |
| Integration: Example06 Copper | 1 | ✅ |
| Integration: Example16 Silicon | 1 | ✅ |
| Integration: QE Input Roundtrip | 2 | ✅ |
| Integration: .win Roundtrip | 7 | ✅ |

#### Project-Based Integration Tests (6 tests) ✅ NEW

These tests run through proper QMatSuite project structure in `.tmp/runs/`:

| Test | Description | Status |
|------|-------------|--------|
| TestDiamondWannier90::test_executables_from_managed_engine | Verify executables from `.qmatsuite/engines/` | ✅ |
| TestDiamondWannier90::test_project_structure | Verify project/pseudo/raw/ structure | ✅ |
| TestDiamondWannier90::test_full_workflow_and_results | Run workflow, validate spread values | ✅ |
| TestCopperWannier90::test_full_workflow_and_results | 7 WFs with disentanglement | ✅ |
| TestSiliconWannier90::test_full_workflow_and_results | 8 WFs with disentanglement | ✅ |
| TestProjectFilesAfterRun::test_diamond_files_in_raw | All outputs in raw/ | ✅ |

**Test Directories (persist after run for inspection):**
- `.tmp/runs/wannier90_diamond/`
- `.tmp/runs/wannier90_copper/`
- `.tmp/runs/wannier90_silicon/`

**Verified Assertions:**
- Executables come from managed engine path (NOT PATH lookup)
- pw2wannier90.x correctly uses stdin redirection
- All input/output files organized in `raw/` directory
- Pseudos in `project/pseudo/` (copied from resources)
- outdir/prefix paths correctly modified

**Example05 (Diamond) Results:**
- 4 MLWFs created with sp³ bonding character
- Final Spread: 2.3255 Ang² (expected: ~2.32 ✅)
- Each WF spread: 0.5814 Ang² (expected: ~0.58 ✅)

**Example06 (Copper) Results:**
- 7 MLWFs created (5d + 2s)
- Disentanglement converged successfully
- Fermi surface computable via interpolation

**Example16 (Silicon) Results:**
- 8 MLWFs created (sp³ × 2 atoms)
- Disentanglement converged successfully
- BoltzWann integration ready

### 13.6 Expected Outputs

After running the demo:
- `diamond.nnkp` (from w90_preproc)
- `diamond.mmn`, `diamond.amn`, `diamond.eig` (from pw2wannier90)
- `diamond.wout`, `diamond.chk` (from w90_run)

### 13.7 Future Work (Post-MVP)

- [ ] postw90.x integration (Berry phase, transport, DOS)
- [ ] wannier_plot.x integration (cube files for visualization)
- [ ] Disentanglement parameters (dis_win_min/max, dis_froz_min/max)
- [ ] Band structure interpolation (kpoint_path, bands_plot)
- [ ] Spinor/SOC support
- [ ] Fermi surface plotting
- [ ] Additional examples (Silicon, Copper, Iron)
- [ ] UI visualization of Wannier spread convergence
- [ ] Parse .wout for spread/center extraction

---

## 14. PySCF Integration (MVP)

**Goal**: Enable molecular quantum chemistry calculations using PySCF.

**Status**: ✅ MVP Implemented (2026-01-02)

### 14.1 Architecture

**Key Design Decisions**:
- **Molecular vs Periodic Detection**: A system is MOLECULAR if and only if it has no lattice vectors
- **Python-Native Execution**: No subprocess, direct PySCF API calls
- **Parallel Path**: PySCF code paths are completely separate from QE/PBC code

**New Step Types**:
| Step Type | Engine | Description |
|-----------|--------|-------------|
| `pyscf_scf` | pyscf | Single-point HF/DFT (RHF, UHF, RKS, UKS) |

### 14.2 Implementation Checklist

- [x] Create `docs/design/engine_integration/PYSCF_INTEGRATION_SPEC.md`
- [x] Add `PYSCF_SCF` to `StepType` enum in `calculation/types.py`
- [x] Register `pyscf_scf` in `workflow/registry.py`
- [x] Add `pyscf_scf` to CLI `KNOWN_STEP_TYPES`
- [x] Implement `PySCFEngine` adapter in `engine/pyscf_engine.py`
  - [x] Molecule building from parameters
  - [x] RHF/UHF/RKS/UKS method support
  - [x] Result extraction (energy, MO energies, HOMO/LUMO gap)
  - [x] Graceful error when PySCF not installed
- [x] Create demo generator `tools/generate_pyscf_demo.py`
- [x] Generate `resources/demo_projects/water_pyscf_scf.yml`
- [x] Add unit tests `tests/unit/test_pyscf_integration.py`
- [x] Add integration tests `tests/integration/test_pyscf_execution.py`
- [x] Add `pyscf` optional dependency in `pyproject.toml`

### 14.3 Demo Project

**File**: `resources/demo_projects/water_pyscf_scf.yml`

**Contents**:
- 1 structure: H2O molecule (no lattice = MOLECULAR)
- 1 calculation with 1 step:
  - `pyscf_scf` (RHF/6-31G)

**Expected Results**:
| Property | Value | Unit |
|----------|-------|------|
| Energy | ~-75.98 | Hartree |
| HOMO | ~-0.50 | Hartree |
| LUMO | ~0.21 | Hartree |
| Gap | ~19.3 | eV |

### 14.4 Commands

```bash
# Generate the PySCF demo
python tools/generate_pyscf_demo.py

# Run PySCF unit tests
python -m pytest tests/unit/test_pyscf_integration.py -v

# Run PySCF integration tests (requires pyscf installed)
python -m pytest tests/integration/test_pyscf_execution.py -v

# Install pyscf (optional dependency)
pip install pyscf
# OR
pip install quantumvitas[pyscf]
```

### 14.5 Test Results (2026-01-02)

**Unit Tests (always run)**:
| Test Suite | Tests | Status |
|------------|-------|--------|
| StepType Registration | 4 | ✅ |
| Engine Availability | 4 | ✅ |
| Demo Project Structure | 2 | ✅ |

**Integration Tests (skip if pyscf not installed)**:
| Test Suite | Tests | Status |
|------------|-------|--------|
| H2O Calculations | 3 | ✅ |
| Results File | 2 | ✅ |
| Unrestricted Methods | 2 | ✅ |
| Demo Execution | 1 | ✅ |
| Edge Cases | 3 | ✅ |

### 14.6 Future Work (Post-MVP)

- [ ] Geometry optimization (`pyscf_geomopt`)
- [ ] MP2 single-point (`pyscf_mp2`)
- [ ] CCSD/CCSD(T) (`pyscf_ccsd`)
- [ ] TD-DFT excited states (`pyscf_tddft`)
- [ ] Preset dimensions for method/basis selection
- [ ] UI visualization of molecular orbitals
- [ ] Additional demo molecules (CH4, NH3, benzene)
- [ ] Integration with pymatgen Molecule class

---

*This plan is implementation-ready. Execute PRs in sequence per Phase plan.*

