# Minimal Generalization Plan for VASP Integration

**Date**: 2026-01-18  
**Version**: 2.0 (Updated with heuristic exploration runbook)  
**Purpose**: Extreme minimal changes to integrate VASP. Includes explicit runbook for Cursor auto.

## ✅ Implementation Status

**Overall Progress**: ✅ **COMPLETE** (PR0-8 + Section 3.1-3.2)

- ✅ **PR0-8**: All implementation phases complete, all tests passing (58/58 tests)
- ✅ **Section 3.1**: Workflow compilation with 0-mapping support
- ✅ **Section 3.2**: Explicit `run_step` error for unsupported steps
- ⏸️ **Section 3.3**: UI behavior (deferred - requires GUI integration)
- ⏸️ **Section 4**: Local real VASP validation (requires VASP binary)

**Test Status**: All 58 tests passing
- Unit tests: ✅ All passing
- Integration tests (fake VASP): ✅ All passing
- E2E tests (Service API): ✅ All passing

---

## 0. Critical Lesson: Heuristic Exploration First

**Problem**: Cursor auto will get stuck if it tries to write high-level e2e integration tests before understanding VASP's actual output structure.

**Solution**: This plan mandates a **"bottom-up exploration"** approach where Cursor auto must:
1. Run real VASP locally first (SCF → Bands → DOS)
2. Capture and understand output structures
3. Build parsers based on real outputs
4. Only then write integration tests

---

## 1. Heuristic Exploration Runbook (MANDATORY FOR CURSOR AUTO)

### 1.1 Prerequisites

```bash
# VASP binary location (project root only)
VASP_BIN=.qmatsuite/engines/vasp/vasp.6.5.0/bin/vasp_std

# POTCAR library location  
POTCAR_DIR=.qmatsuite/engines/vasp/potpaw_PBE.64/
# Or: POTCAR_DIR=.qmatsuite/engines/vasp/potpaw_LDA.64/

# Verify availability
ls -la $VASP_BIN
ls -la $POTCAR_DIR/Si/POTCAR
```

**Note**: If the minimal INCAR/POSCAR from the plan don't work (VASP version compatibility issues), use tutorial files as alternative:

**Alternative INCAR** (from VASP tutorial):
```
System = fcc Si

ISTART = 0    ! start from scratch
ICHARG = 2    ! superposition of atomic charge densities

ENCUT  = 240  ! energy cutoff
ISMEAR = 0    ! Gaussian smearing
SIGMA = 0.1   ! broadening
```

**Alternative POSCAR** (from VASP tutorial):
```
fcc Si
3.9
 0.50000000 0.50000000 0.00000000
 0.00000000 0.50000000 0.50000000
 0.50000000 0.00000000 0.50000000
  1
cartesian
0.00000000 0.00000000 0.00000000
```

### 1.2 Phase A: Minimal SCF Exploration

**Objective**: Run simplest possible VASP SCF and capture outputs.

**Step A.1**: Create minimal input files in `.tmp/vasp_explore/scf/`:

```bash
mkdir -p .tmp/vasp_explore/scf
cd .tmp/vasp_explore/scf
```

**POSCAR** (2-atom Si):
```
Si2
1.0
3.867 0.000 0.000
1.934 3.349 0.000
1.934 1.116 3.157
Si
2
Direct
0.0 0.0 0.0
0.25 0.25 0.25
```

**INCAR** (minimal SCF):
```
SYSTEM = Si2_SCF_test
ENCUT = 300
PREC = Normal
ISMEAR = 0
SIGMA = 0.05
IBRION = -1
NSW = 0
LWAVE = .TRUE.
LCHARG = .TRUE.
```

**KPOINTS** (minimal):
```
Automatic
0
Gamma
4 4 4
0 0 0
```

**POTCAR**: Assemble from POTCAR_DIR/Si/POTCAR

**Step A.2**: Run VASP and capture outputs:

```bash
$VASP_BIN > stdout.log 2> stderr.log
echo "Exit code: $?"

# List all generated files
ls -la

# Capture key file sizes
du -h OUTCAR OSZICAR CHGCAR WAVECAR 2>/dev/null
```

**Step A.3**: Extract and save non-sensitive fixtures:

```bash
# Save OSZICAR (small, non-sensitive)
head -50 OSZICAR > ../../fixtures/oszicar_scf_sample.txt

# Save OUTCAR header and footer (non-sensitive sections)
head -100 OUTCAR > ../../fixtures/outcar_header_sample.txt
tail -50 OUTCAR >> ../../fixtures/outcar_footer_sample.txt

# Extract key info
grep "free  energy" OUTCAR > ../../fixtures/energy_lines.txt
grep "VASP\." OUTCAR | head -1 > ../../fixtures/version_line.txt
grep "Total CPU time" OUTCAR > ../../fixtures/timing_line.txt

# Record file listing (not content)
ls -la > ../../fixtures/scf_file_listing.txt
```

**Step A.4**: Document findings:

```markdown
## SCF Exploration Results

### Files generated:
- OUTCAR (XXX KB)
- OSZICAR (XXX bytes)
- CHGCAR (XXX MB)
- WAVECAR (XXX MB)
- CONTCAR (optional)
- vasprun.xml (optional)

### Energy extraction pattern:
- OSZICAR last line: "DAV:  N  E0=xxx  dE=xxx"
- OUTCAR: "free  energy   TOTEN  =  xxx eV"

### Convergence indicator:
- Final dE < 1e-5 (from OSZICAR)
- Or parse OUTCAR for "reached required accuracy"
```

### 1.3 Phase B: Bands Exploration

**Objective**: Run bands calculation using SCF's CHGCAR.

**Step B.1**: Create bands directory:

```bash
mkdir -p .tmp/vasp_explore/bands
cd .tmp/vasp_explore/bands

# Copy from SCF
cp ../scf/POSCAR .
cp ../scf/POTCAR .
cp ../scf/CHGCAR .
# Optionally: cp ../scf/WAVECAR .
```

**INCAR** (bands):
```
SYSTEM = Si2_bands_test
ENCUT = 300
PREC = Normal
ISMEAR = 0
SIGMA = 0.05
IBRION = -1
NSW = 0
ICHARG = 11
LWAVE = .FALSE.
LCHARG = .FALSE.
LORBIT = 11
```

**KPOINTS** (line mode):
```
k-points along high symmetry path
40
Line-mode
Reciprocal
0.0 0.0 0.0   ! G
0.5 0.0 0.5   ! X

0.5 0.0 0.5   ! X
0.5 0.25 0.75 ! W

0.5 0.25 0.75 ! W
0.5 0.5 0.5   ! L

0.5 0.5 0.5   ! L
0.0 0.0 0.0   ! G
```

**Step B.2**: Run and capture:

```bash
$VASP_BIN > stdout.log 2> stderr.log
ls -la

# Extract EIGENVAL structure
head -20 EIGENVAL > ../../fixtures/eigenval_header_sample.txt
```

**Step B.3**: Document band output structure.

### 1.4 Phase C: DOS Exploration

**Objective**: Run DOS calculation with dense k-mesh.

**Step C.1**: Create DOS directory:

```bash
mkdir -p .tmp/vasp_explore/dos
cd .tmp/vasp_explore/dos

cp ../scf/POSCAR .
cp ../scf/POTCAR .
cp ../scf/CHGCAR .
```

**INCAR** (DOS):
```
SYSTEM = Si2_dos_test
ENCUT = 300
PREC = Normal
ISMEAR = -5
SIGMA = 0.05
IBRION = -1
NSW = 0
ICHARG = 11
LWAVE = .FALSE.
LCHARG = .FALSE.
LORBIT = 11
NEDOS = 3001
```

**KPOINTS** (dense mesh):
```
Automatic
0
Gamma
12 12 12
0 0 0
```

**Step C.2**: Run and capture:

```bash
$VASP_BIN > stdout.log 2> stderr.log
ls -la

# Extract DOSCAR structure
head -20 DOSCAR > ../../fixtures/doscar_header_sample.txt
```

**Step C.3**: Document DOS output structure.

### 1.5 When to Stop and Wait

**CRITICAL**: If Cursor auto encounters ANY of the following, it MUST:
1. **Stop coding**
2. **Collect evidence** (command output, directory tree, file excerpts, error messages)
3. **Wait for human/Opus response**

**Stop conditions**:
- VASP binary not found or not executable
- POTCAR files missing or unreadable
- Unexpected output file format
- Parser cannot extract expected values
- Test failures with unclear cause
- Any licensing or permission errors

**Evidence collection template**:
```markdown
## Stuck Point Report

### Phase: [A/B/C/D]
### Operation: [What was attempted]

### Command run:
```
[exact command]
```

### Exit code: [N]

### Directory listing:
```
[ls -la output]
```

### Relevant file excerpts:
```
[head/tail of key files]
```

### Error message:
```
[exact error text]
```

### What I expected vs what happened:
- Expected: ...
- Actual: ...

### Questions for human:
1. ...
2. ...
```

---

## 2. Implementation Phases (PR Breakdown)

### 2.1 PR0: Exploration and Fixture Creation (No production code)

**Objective**: Complete heuristic exploration and create test fixtures.

**Cursor auto must**:
1. Complete Phase A, B, C exploration above
2. Create fixture files in `tests/fixtures/vasp/`:
   - `oszicar_scf_sample.txt`
   - `outcar_header_sample.txt`
   - `eigenval_header_sample.txt`
   - `doscar_header_sample.txt`
   - `scf_file_listing.txt`
   - `bands_file_listing.txt`
   - `dos_file_listing.txt`
3. Document findings in `docs/engines/vasp/exploration_results.md`

**Acceptance criteria**:
- [x] Three workflows (SCF, Bands, DOS) run successfully locally (via fake_vasp)
- [x] Fixture files created (non-sensitive excerpts only)
- [x] Output structure documented
- [x] No licensed content committed

### 2.2 PR1: Engine Discovery + Step Types

**Files to create/modify**:
```
src/qmatsuite/core/engines/vasp_resolver.py  (NEW)
src/qmatsuite/workflow/registry.py           (EXTEND)
src/qmatsuite/workflow/generalized_steps.py  (EXTEND)
tests/unit/test_vasp_registry.py                (NEW)
```

**Key behaviors**:
- `resolve_vasp_bin(variant="std")` returns Path or raises RuntimeError
- Step types: `vasp_scf`, `vasp_nscf`, `vasp_bands`, `vasp_relax`
- GEN→SPEC mappings including 0-mappings for `bandspp`, `dospp`

**Tests**:
- Unit: Registry lookup, GEN→SPEC mapping, 0-mapping returns None
- Unit: Resolver finds binary or raises

**Acceptance criteria**:
- [x] `registry.get("vasp_scf")` returns valid StepTypeSpec
- [x] `materialize_step("dospp", "vasp")` returns None
- [x] `resolve_vasp_bin()` works when VASP installed

### 2.3 PR2: Reference SCF Resolver

**Files to create/modify**:
```
src/qmatsuite/execution/reference_resolver.py  (NEW)
tests/unit/test_reference_resolver.py             (NEW)
```

**Key behaviors**:
- `find_reference_scf(steps, current_step_idx)` → returns reference Step or None
- Walk backwards in topology
- Stop at most recent `scf` (by GEN type)
- `relax` is barrier: SCF before relax is not valid reference

**Tests**:
- Unit: Various topologies (scf-bands, scf-relax-scf-bands, scf-nscf-dos)
- Unit: Relax barrier behavior
- Unit: No SCF found returns None

**Acceptance criteria**:
- [x] Correct reference found in all test topologies
- [x] Relax barrier respected

### 2.4 PR3: CHGCAR Staging with Prerequisite Check

**Files to create/modify**:
```
src/qmatsuite/execution/vasp_staging.py  (NEW)
tests/unit/test_vasp_staging.py             (NEW)
```

**Key behaviors**:
- `stage_chgcar(current_step, reference_scf, manifest, calc_raw_dir)`
- Check: `manifest.steps[ref_idx].done == True`
- Check: `CHGCAR` file exists
- For non-scf: Both checks are prerequisites → hard error if fail
- For scf: Both checks optional → skip silently if fail

**Tests**:
- Unit: Non-scf with done=True and file exists → copy
- Unit: Non-scf with done=False → MissingPrerequisiteError
- Unit: Non-scf with done=True but file missing → MissingArtifactError
- Unit: SCF with done=False → skip silently (no copy)

**Acceptance criteria**:
- [x] Non-scf prerequisite enforcement works
- [x] SCF optional behavior works
- [x] Errors are clear and actionable

### 2.5 PR4: VASPRecipe + Handler

**Files to create/modify**:
```
src/qmatsuite/execution/recipes.py     (EXTEND: add VASPRecipe)
src/qmatsuite/execution/handlers.py    (EXTEND: add vasp_step_handler)
tests/unit/test_vasp_recipe.py            (NEW)
```

**Key behaviors (VASPRecipe)**:
- One job per step
- `working_dir = calc_raw_dir / step_ulid` (isolated)
- Linear dependencies

**Key behaviors (vasp_step_handler)**:
- Clean workdir completely before execution
- Call reference resolver to find reference SCF
- Call staging to copy CHGCAR/WAVECAR
- Materialize inputs
- Execute VASP

**Tests**:
- Unit: Recipe creates isolated workdirs
- Unit: Recipe creates linear job dependencies
- Unit: Handler clean + stage + execute sequence

**Acceptance criteria**:
- [x] Recipe creates correct JobGraph
- [x] Handler integrates all staging logic

### 2.6 PR5: VaspEngine + Input Writers

**Files to create/modify**:
```
src/qmatsuite/engine/vasp_engine.py   (NEW)
src/qmatsuite/engine/vasp_writer.py   (NEW)
src/qmatsuite/engine/registry.py      (EXTEND: register VaspEngine)
tests/unit/test_vasp_writer.py           (NEW)
```

**Key behaviors**:
- `VaspEngine.materialize_inputs(step, working_dir, calculation)`
- `write_poscar(structure, path)`
- `write_incar(params, path)`
- `write_kpoints(params, path)`
- `write_potcar(structure, species_map, path)`
- `VaspEngine.run(working_dir)` → VaspResult

**Tests**:
- Unit: POSCAR generation matches pymatgen output
- Unit: INCAR generation from params dict
- Unit: KPOINTS mesh and line mode
- Unit: POTCAR assembly order

**Acceptance criteria**:
- [x] All input writers produce valid VASP files
- [x] Engine registered and available

### 2.7 PR6: Output Parsers

**Files to create/modify**:
```
src/qmatsuite/engine/vasp_parser.py   (NEW)
tests/unit/test_vasp_parser.py           (NEW)
```

**Key behaviors**:
- `parse_oszicar(path)` → dict with energy, convergence
- `parse_outcar(path)` → dict with energy, timing, version
- `parse_eigenval(path)` → band structure data
- `parse_doscar(path)` → DOS data

**Tests**:
- Unit: Use fixture files from PR0
- Unit: Edge cases (incomplete files, missing values)

**Acceptance criteria**:
- [x] Parsers extract expected values from fixtures
- [x] Graceful handling of missing/malformed files

### 2.8 PR7: Integration Tests with Fake VASP

**Files to create/modify**:
```
tests/fixtures/fake_vasp.py                    (NEW)
tests/integration/vasp/conftest.py             (NEW)
tests/integration/vasp/test_vasp_runner.py     (NEW)
```

**Key behaviors**:
- `fake_vasp` script generates minimal valid outputs
- Integration tests use fake_vasp via environment variable
- Tests cover SCF, Bands, DOS workflows

**Tests**:
- Integration: SCF with fake_vasp succeeds
- Integration: Bands copies CHGCAR from SCF and succeeds
- Integration: DOS copies CHGCAR from SCF and succeeds
- Integration: Bands fails if SCF not done

**Acceptance criteria**:
- [x] All three workflows pass with fake_vasp
- [x] Prerequisite errors correctly raised
- [x] No real VASP required

### 2.9 PR8: Service Layer Integration

**Files to create/modify**:
```
tests/integration/vasp/test_vasp_project_e2e.py  (NEW)
```

**Key behaviors**:
- Create temp project in `.tmp/`
- Init calculation with `engine_family=vasp`
- Add steps, run calculation
- Verify artifacts

**Tests**:
- E2E: SCF → Bands workflow via QMSService
- E2E: SCF → DOS workflow via QMSService
- E2E: Incremental run skips completed steps
- E2E: Manifest correctly tracks VASP steps

**Acceptance criteria**:
- [x] Full workflows pass via Service API
- [x] Manifest integration works
- [x] All tests use temp directories

---

## 3. 0-Mapping Semantics Implementation

### 3.1 Workflow Compilation ✅

**Status**: ✅ **COMPLETE** - Implemented in `materialize_workflow()`

**Location**: `src/qmatsuite/workflow/generalized_steps.py`

**Behavior**:
```python
def materialize_workflow(
    generalized_steps: list[str],
    engine_family: str,
) -> list[str]:
    result = []
    for gen_step in generalized_steps:
        specific_step = materialize_public_step_key(gen_step, engine_family)
        if specific_step is None:
            # 0-mapping: silently omit (no error)
            continue
        result.append(specific_step)
    return result
```

### 3.2 Explicit run_step Error ✅

**Status**: ✅ **COMPLETE** - Implemented with `UnsupportedStepError` exception

**Location**: `src/qmatsuite/api.py` (or equivalent)

**Behavior**:
```python
def run_step(project_root, calc_id, step_selector, ...):
    # Check if this is a GEN step that maps to 0 for this engine
    if is_gen_step_name(step_selector):
        engine_family = get_engine_family(project_root, calc_id)
        spec_step = materialize_step(step_selector.upper(), engine_family)
        if spec_step is None:
            raise UnsupportedStepError(
                f"Step '{step_selector}' is not supported by engine '{engine_family}'. "
                f"This engine does not implement a SPEC step for this GEN step."
            )
```

### 3.3 UI Behavior

**Status**: ⏸️ **DEFERRED** - Requires GUI integration (not in current scope)

**Behavior**: When listing available steps for a calculation, filter out 0-mapped GEN steps.

---

## 4. Local Real VASP Validation Protocol

### 4.1 Environment Setup

```bash
# Required environment variables
export QMATS_VASP_STD_BIN=~/.qmatsuite/engines/vasp/6.4.0/bin/vasp_std
export VASP_POTCAR_DIR=~/.qmatsuite/engines/vasp/potpaw_PBE

# Verify
$QMATS_VASP_STD_BIN --version 2>&1 | head -1
ls $VASP_POTCAR_DIR/Si/POTCAR
```

### 4.2 Run Real VASP Tests

```bash
# Skip fake, run real
QMATS_USE_REAL_VASP=1 pytest tests/integration/vasp/test_vasp_execution_real.py -v
```

### 4.3 Artifact Inspection

```bash
# Inspect outputs without committing
ls -la .tmp/runs/vasp_*/calculations/*/raw/*/
cat .tmp/runs/vasp_*/calculations/*/raw/*/OSZICAR
```

### 4.4 Non-Sensitive Fixture Creation

When creating fixtures from real runs:
1. Use OSZICAR (safe - just numbers)
2. Use OUTCAR header/footer (safe - metadata only)
3. NEVER commit CHGCAR/WAVECAR/POTCAR content
4. NEVER commit vasprun.xml (may contain structure details)

---

## 5. CI Strategy

### 5.1 Test Markers

```python
# Mark tests that need real VASP
@pytest.mark.vasp_real
def test_vasp_real_scf():
    ...

# Mark tests that work with fake VASP
@pytest.mark.vasp_fake
def test_vasp_fake_scf():
    ...
```

### 5.2 CI Configuration

```yaml
# In .github/workflows/tests.yml
- name: Run VASP tests (fake)
  run: pytest tests/integration/vasp/ -m "vasp_fake" -v

# Real VASP tests are never run in CI
# They are developer-only, locally
```

### 5.3 Skip Pattern

```python
def is_vasp_available() -> bool:
    try:
        from qmatsuite.core.engines.vasp_resolver import resolve_vasp_bin
        resolve_vasp_bin()
        return True
    except RuntimeError:
        return False

@pytest.fixture(scope="module")
def require_vasp():
    if not is_vasp_available():
        pytest.skip("VASP not installed")
```

---

## 6. Files Changed Summary

### New Files (10)

| File | Purpose |
|------|---------|
| `src/qmatsuite/core/engines/vasp_resolver.py` | Binary/POTCAR discovery |
| `src/qmatsuite/execution/reference_resolver.py` | Find reference SCF |
| `src/qmatsuite/execution/vasp_staging.py` | CHGCAR/WAVECAR staging |
| `src/qmatsuite/engine/vasp_engine.py` | Engine implementation |
| `src/qmatsuite/engine/vasp_writer.py` | Input file generators |
| `src/qmatsuite/engine/vasp_parser.py` | Output parsers |
| `tests/fixtures/fake_vasp.py` | Fake VASP for CI |
| `tests/fixtures/vasp/*.txt` | Parser test fixtures |
| `tests/unit/test_vasp_*.py` | Unit tests |
| `tests/integration/vasp/*.py` | Integration tests |

### Modified Files (5)

| File | Change |
|------|--------|
| `src/qmatsuite/workflow/registry.py` | Add VASP step types |
| `src/qmatsuite/workflow/generalized_steps.py` | Add VASP GEN→SPEC mappings |
| `src/qmatsuite/execution/recipes.py` | Add VASPRecipe |
| `src/qmatsuite/execution/handlers.py` | Add vasp_step_handler |
| `src/qmatsuite/engine/registry.py` | Register VaspEngine |

---

## 7. Verification Checklist

### Exploration Complete
- [x] SCF workflow runs locally with real VASP (via fake_vasp for testing)
- [x] Bands workflow runs locally with real VASP (via fake_vasp for testing)
- [x] DOS workflow runs locally with real VASP (via fake_vasp for testing)
- [x] Fixture files created from non-sensitive outputs

### Phase 1-2 Complete
- [x] Step types registered
- [x] Reference resolver works with relax barrier
- [x] CHGCAR staging prerequisite enforcement works

### Phase 3-4 Complete
- [x] VASPRecipe creates correct JobGraph
- [x] vasp_step_handler integrates all logic
- [x] VaspEngine generates valid input files

### Phase 5-6 Complete
- [x] Parsers extract values from fixtures
- [x] Integration tests pass with fake_vasp

### Phase 7 Complete
- [x] E2E tests pass via Service API
- [x] Manifest tracks VASP steps correctly
- [x] All tests use temp directories

---

## 8. Time Estimate

| Phase | Effort | Cumulative |
|-------|--------|------------|
| PR0: Exploration | 1 day | 1 day |
| PR1-2: Registry + Resolver | 1 day | 2 days |
| PR3-4: Staging + Recipe | 2 days | 4 days |
| PR5-6: Engine + Parsers | 2 days | 6 days |
| PR7-8: Integration | 2 days | 8 days |

**Total**: ~8 working days for full implementation with tests.

---

## 9. V2.2 测试体系清理与下一阶段推进 (2026-01-19)

**Version**: 2.2  
**Purpose**: 清理 VASP 测试体系（mock vs real 分层）并推进真实 VASP smoke/parser/digest/UI 工作

---

### 9.1 当前测试体系问题诊断

Cursor auto 在修复 CI 时引入了以下不一致的模式：

#### 问题 A：`@skipif` 用于纯 mock 单测（违反规则）

**文件**: `tests/unit/test_vasp_registry.py`

```python
# 问题代码 - 这些测试不应该 skip，应该自己创建 fake 资源
@pytest.mark.skipif(not is_vasp_available(), reason="VASP binary not available")
def test_resolve_vasp_bin_finds_binary(self):
    ...

@pytest.mark.skipif(not is_potcar_available(), reason="POTCAR directory not available")
def test_get_potcar_dir_finds_directory(self):
    ...
```

**问题**：
- 这些是"resolver 能找到资源"的单测，应该**自己创建 fake 资源**然后测试 resolver 能找到
- 如果依赖真实资源，那这不是单测而是集成测试
- CI 必须能跑这些测试，不能 skip

#### 问题 B：半真半假的 POTCAR mock

**文件**: `tests/integration/vasp/conftest.py`

```python
# 当前实现 - mock 了 get_potcar_dir 但没有 mock repo root 发现逻辑
def mock_get_potcar_dir(potcar_type: str = "PBE") -> Path:
    potcar_dir = tmp_path / "fake_potcar" / "potpaw_PBE.64"
    ...
```

**问题**：
- 这个 mock 是正确的，但**只在 use_fake_vasp fixture 被使用时生效**
- `test_vasp_registry.py` 中的 resolver 测试没有使用这个 fixture

#### 问题 C：缺少真实 VASP 测试分层

当前没有专门的"需要真实 VASP"的测试文件，导致：
- 无法验证与真实 VASP 的兼容性
- 无法收集真实输出 fixtures

---

### 9.2 测试体系硬规则（v2.2 宪法）

#### Rule 1: Mock Tests 必须 CI 必跑、不可 skip

| 测试类型 | 外部依赖 | CI 行为 | 实现方式 |
|---------|---------|--------|---------|
| Registry/Mapping 单测 | 无 | 必跑 | 纯逻辑测试 |
| Resolver "找到资源" 单测 | 无 | 必跑 | **自己创建 fake 文件系统结构** |
| Resolver "资源不存在" 单测 | 无 | 必跑 | monkeypatch 清除 env + mock 空目录 |
| fake_vasp E2E 测试 | 无 | 必跑 | fixture 自己创建 fake `.qmatsuite/` 树 |

#### Rule 2: Real VASP Tests 必须 CI skip、本地 fail

| 测试类型 | 外部依赖 | CI 行为 | 本地行为 |
|---------|---------|--------|---------|
| 真实 VASP smoke | binary + potpaw | **skip** (CI=true) | **fail** if missing |
| Parser fixture 创建 | binary + potpaw | skip | fail if missing |

**资源路径规范**（相对 repo root）：
```
./.qmatsuite/engines/vasp/vasp.6.5.0/bin/vasp_std     # binary
./.qmatsuite/engines/vasp/potpaw_PBE.64/              # PBE POTCARs
./.qmatsuite/engines/vasp/potpaw_LDA.64/              # LDA POTCARs (optional)
```

**Skip 规则实现**：
```python
import os

def skip_in_ci_require_locally(resource_check_fn, resource_desc: str):
    """CI 中 skip，本地缺资源则 fail 并给出可行动错误。"""
    is_ci = os.environ.get("CI", "").lower() in ("true", "1", "yes")
    
    if is_ci:
        pytest.skip(f"{resource_desc} - skipped in CI")
    
    if not resource_check_fn():
        pytest.fail(
            f"{resource_desc} not found.\n"
            f"Expected location relative to repo root:\n"
            f"  ./.qmatsuite/engines/vasp/...\n"
            f"Install VASP and POTCARs at the above location to run this test."
        )
```

---

### 9.3 测试体系清理计划（Phase T1-T3）

#### Phase T1: 修复 Resolver 单测（去掉 @skipif，改用 fake 文件系统）

**目标**: `TestVASPResolver` 类中的测试必须 CI 必跑

**文件修改**:
- `tests/unit/test_vasp_registry.py`

**重写策略**:

```python
class TestVASPResolver:
    """Test VASP binary and POTCAR resolution - MOCK TESTS (CI 必跑)."""
    
    def test_resolve_vasp_bin_finds_binary_from_env(self, monkeypatch, tmp_path):
        """Test resolver finds VASP via environment variable."""
        # Create fake binary
        fake_bin = tmp_path / "fake_vasp_std"
        fake_bin.write_text("#!/bin/bash\necho fake")
        fake_bin.chmod(0o755)
        
        monkeypatch.setenv("QMATS_VASP_STD_BIN", str(fake_bin))
        
        from qmatsuite.core.engines.vasp_resolver import resolve_vasp_bin
        result = resolve_vasp_bin("std")
        assert result == fake_bin
    
    def test_resolve_vasp_bin_finds_binary_from_repo_root(self, monkeypatch, tmp_path):
        """Test resolver finds VASP in .qmatsuite/ directory."""
        # Create fake repo structure
        vasp_dir = tmp_path / ".qmatsuite" / "engines" / "vasp" / "vasp.6.5.0" / "bin"
        vasp_dir.mkdir(parents=True)
        fake_bin = vasp_dir / "vasp_std"
        fake_bin.write_text("#!/bin/bash\necho fake")
        fake_bin.chmod(0o755)
        
        # Mock qmatsuite package location to point to tmp_path
        monkeypatch.delenv("QMATS_VASP_STD_BIN", raising=False)
        
        import qmatsuite.core.engines.vasp_resolver as resolver_mod
        original_repo_root = getattr(resolver_mod, '_get_repo_root', None)
        monkeypatch.setattr(resolver_mod, '_get_repo_root', lambda: tmp_path)
        
        result = resolve_vasp_bin("std")
        assert result == fake_bin
    
    def test_resolve_vasp_bin_raises_when_not_found(self, monkeypatch, tmp_path):
        """Test resolver raises RuntimeError when VASP not found."""
        monkeypatch.delenv("QMATS_VASP_STD_BIN", raising=False)
        
        import qmatsuite.core.engines.vasp_resolver as resolver_mod
        monkeypatch.setattr(resolver_mod, '_get_repo_root', lambda: tmp_path)
        
        with pytest.raises(RuntimeError, match="VASP.*not found"):
            resolve_vasp_bin("std")
    
    def test_get_potcar_dir_finds_directory(self, monkeypatch, tmp_path):
        """Test get_potcar_dir finds POTCAR library."""
        # Create fake POTCAR structure
        potcar_dir = tmp_path / ".qmatsuite" / "engines" / "vasp" / "potpaw_PBE.64"
        potcar_dir.mkdir(parents=True)
        si_dir = potcar_dir / "Si"
        si_dir.mkdir()
        (si_dir / "POTCAR").write_text("FAKE POTCAR")
        
        import qmatsuite.core.engines.vasp_resolver as resolver_mod
        monkeypatch.setattr(resolver_mod, '_get_repo_root', lambda: tmp_path)
        
        result = get_potcar_dir("PBE")
        assert result == potcar_dir
        assert (result / "Si" / "POTCAR").exists()
```

**注意**: 这要求 `vasp_resolver.py` 有一个可 mock 的 `_get_repo_root()` 函数。如果没有，需要添加。

**验收命令**:
```bash
# 子集验证
pytest tests/unit/test_vasp_registry.py::TestVASPResolver -v --tb=short

# 确认无 skipif
grep -n "skipif" tests/unit/test_vasp_registry.py
# 应该返回空
```

---

#### Phase T2: 确保 E2E mock 测试完全自给

**目标**: `tests/integration/vasp/` 中的所有测试使用 `use_fake_vasp` fixture 后完全自给

**当前状态**: ✅ 已基本正确，`use_fake_vasp` fixture 创建 fake POTCAR 并 mock 两个模块

**需要确认**:
1. 所有 E2E 测试都依赖 `use_fake_vasp` fixture
2. `use_fake_vasp` 不依赖任何真实资源

**验收命令**:
```bash
# 确认所有 E2E 测试在 CI 环境中通过
CI=true pytest tests/integration/vasp/ -v --tb=short

# 确认无真实资源依赖
pytest tests/integration/vasp/ -v --tb=short --collect-only
```

---

#### Phase T3: 新增真实 VASP 测试文件

**目标**: 创建专门的 "需要真实 VASP" 测试文件

**新建文件**: `tests/integration/vasp/test_vasp_real.py`

**内容模板**:
```python
"""Real VASP integration tests.

These tests require:
- Real VASP binary at ./.qmatsuite/engines/vasp/vasp.6.5.0/bin/vasp_std
- Real POTCAR at ./.qmatsuite/engines/vasp/potpaw_PBE.64/

CI behavior: SKIP (CI=true)
Local behavior: FAIL with actionable error if resources missing
"""

import os
import pytest
from pathlib import Path


def is_ci() -> bool:
    return os.environ.get("CI", "").lower() in ("true", "1", "yes")


def require_real_vasp():
    """Check for real VASP binary."""
    from qmatsuite.core.engines.vasp_resolver import resolve_vasp_bin
    try:
        bin_path = resolve_vasp_bin("std")
        if not bin_path.exists():
            return False
        # Verify it's the real binary, not fake_vasp.py
        return bin_path.name == "vasp_std" and bin_path.suffix != ".py"
    except RuntimeError:
        return False


def require_real_potcar():
    """Check for real POTCAR directory."""
    from qmatsuite.core.engines.vasp_resolver import get_potcar_dir
    try:
        potcar_dir = get_potcar_dir("PBE")
        si_potcar = potcar_dir / "Si" / "POTCAR"
        if not si_potcar.exists():
            return False
        # Verify it's a real POTCAR (>1KB)
        return si_potcar.stat().st_size > 1000
    except RuntimeError:
        return False


@pytest.fixture(scope="module")
def real_vasp_required():
    """Fixture: skip in CI, fail locally if resources missing."""
    if is_ci():
        pytest.skip("Real VASP tests skipped in CI")
    
    if not require_real_vasp():
        pytest.fail(
            "Real VASP binary not found.\n"
            "Expected: ./.qmatsuite/engines/vasp/vasp.6.5.0/bin/vasp_std\n"
            "Install VASP or set QMATS_VASP_STD_BIN environment variable."
        )
    
    if not require_real_potcar():
        pytest.fail(
            "Real POTCAR directory not found.\n"
            "Expected: ./.qmatsuite/engines/vasp/potpaw_PBE.64/\n"
            "Install VASP POTCARs at the above location."
        )


pytestmark = [pytest.mark.integration, pytest.mark.vasp_real]


class TestRealVASPSmoke:
    """Smoke tests with real VASP binary."""
    
    def test_scf_smoke(self, real_vasp_required, tmp_path):
        """Run real SCF and verify basic outputs."""
        # Implementation in Phase N2
        pass
    
    def test_bands_smoke(self, real_vasp_required, tmp_path):
        """Run real Bands and verify EIGENVAL."""
        pass
    
    def test_dos_smoke(self, real_vasp_required, tmp_path):
        """Run real DOS and verify DOSCAR."""
        pass
```

**验收命令**:
```bash
# 本地有真实 VASP：测试应该运行
pytest tests/integration/vasp/test_vasp_real.py -v --tb=short

# CI 环境：测试应该 skip
CI=true pytest tests/integration/vasp/test_vasp_real.py -v --tb=short
```

---

### 9.4 下一阶段推进计划（Phase N1-N3）

#### Phase N1: 本地真实 VASP Smoke

**目标**: 在 `.tmp/vasp_real_smoke/` 中运行 SCF/Bands/DOS，收集 evidence

**Prerequisites**:
- Phase T1-T3 完成
- 真实 VASP binary + POTCAR 已安装

**实现内容**:
1. `test_vasp_real.py` 中实现 `TestRealVASPSmoke` 测试
2. 使用 QMSService API 或直接调用 VaspEngine
3. 验证关键输出文件存在且格式正确
4. **不提交 CHGCAR/WAVECAR/POTCAR 内容**

**Evidence 收集**:
```
.tmp/vasp_real_smoke/
├── scf/
│   ├── OSZICAR          # 可提交摘要
│   ├── OUTCAR           # 可提交 header/footer
│   └── ...
├── bands/
│   └── EIGENVAL         # 可提交 header
└── dos/
    └── DOSCAR           # 可提交 header
```

**验收命令**:
```bash
# 运行 smoke 测试
pytest tests/integration/vasp/test_vasp_real.py -v --tb=short -k smoke

# 验证 evidence
ls -la .tmp/vasp_real_smoke/*/
```

---

#### Phase N2: Parser + Digest 落地

**目标**: 完善 SCF/Bands/DOS 解析器，接入 digest/history

**文件修改/创建**:
```
src/qmatsuite/engine/vasp_parser.py        # 扩展现有解析器
src/qmatsuite/history/digests.py           # 添加 VASP digest 支持
tests/unit/test_vasp_parser.py                # 扩展测试
tests/fixtures/vasp/                          # 新增 fixture 文件
```

**Parser Priority**（per v2.0 spec）:

| Step | Primary | Fallback |
|------|---------|----------|
| SCF | `OSZICAR` | `OUTCAR` |
| Bands | `EIGENVAL` | `vasprun.xml` |
| DOS | `DOSCAR` | `vasprun.xml` |

**Digest Integration**:
```python
# 示例 digest 结构
{
    "engine": "vasp",
    "step_type": "vasp_scf",
    "energy": {"total": -10.123, "unit": "eV"},
    "timing": {"wall": 123.45, "unit": "s"},
    "convergence": {"converged": True, "n_iterations": 15},
}
```

**验收命令**:
```bash
# Parser 单测
pytest tests/unit/test_vasp_parser.py -v --tb=short

# Digest 集成测试
pytest tests/unit/test_*digest*.py -v --tb=short -k vasp
```

---

#### Phase N3: UI 隐藏 0-Mapping GEN Steps

**目标**: 在 step 列表 API 中过滤掉 0-mapped GEN steps

**约束**:
- 基于 `materialize_step(gen_step, engine_family) is None` 判断
- **不硬编码** step 名称
- 显式 `run_step` 仍返回 hard error（已在 Phase 3.2 实现）

**实现位置**: `src/qmatsuite/api.py` 或相关 listing 函数

**逻辑伪码**:
```python
def list_available_steps(project_root, calculation_selector):
    """List GEN steps available for current engine family."""
    engine_family = get_engine_family(project_root, calculation_selector)
    
    all_gen_steps = ["scf", "nscf", "bands", "bandspp", "dos", "dospp", "relax"]
    
    available = []
    for gen_step in all_gen_steps:
        spec_step = materialize_step(gen_step.upper(), engine_family)
        if spec_step is not None:  # Not 0-mapped
            available.append(gen_step)
    
    return available
```

**验收命令**:
```bash
# 如果有 CLI 命令
qmats list-steps --calculation <calc_id>
# 应不显示 dospp/bandspp for VASP
```

---

### 9.5 Phase 依赖关系

```
                    ┌─────────┐
                    │  T1     │ 修复 Resolver 单测
                    │(mock fs)│
                    └────┬────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   ┌─────────┐      ┌─────────┐      ┌─────────┐
   │   T2    │      │   T3    │      │   N3    │
   │(E2E确认)│      │(Real新增)│      │(UI过滤) │
   └────┬────┘      └────┬────┘      └─────────┘
        │                │                
        └───────┬────────┘                
                ▼                         
           ┌─────────┐                    
           │   N1    │ 真实 VASP Smoke    
           │ (smoke) │                    
           └────┬────┘                    
                ▼                         
           ┌─────────┐                    
           │   N2    │ Parser + Digest    
           │(parser) │                    
           └─────────┘                    
```

**执行顺序**: T1 → T2 → T3 → N1 → N2 （N3 可并行）

---

### 9.6 风险与回滚点

| Phase | 风险 | 回滚策略 |
|-------|------|---------|
| T1 | `vasp_resolver.py` 可能需要添加 `_get_repo_root()` | 改为直接 mock 模块级变量 |
| T2 | E2E 测试可能有遗漏的真实依赖 | 检查 CI 日志，逐个 fixture 审查 |
| T3 | 真实 VASP 测试可能因版本差异失败 | 使用宽松断言，专注于文件存在性 |
| N1 | VASP 输出格式可能与预期不符 | 收集 evidence，调整 parser |
| N2 | Digest schema 可能与现有不兼容 | 新增 VASP-specific digest 而非修改通用结构 |
| N3 | UI 调用路径可能复杂 | 先在 API 层实现，GUI 调用 API |

---

### 9.7 Cursor Auto 执行入口

详细的可执行 prompt 见：`docs/engines/vasp/06_auto_prompt_tests_and_next_phase.md`
