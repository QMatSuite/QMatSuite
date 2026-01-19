# Cursor Auto 执行 Prompt：测试体系清理与下一阶段推进

**Date**: 2026-01-19  
**For**: Cursor Auto  
**Purpose**: 可直接复制执行的操作步骤

---

## ⚠️ 执行前必读

1. **你是 Cursor auto**，严格按本文档步骤执行
2. 每个 Phase 执行完后，运行验收命令，确认全绿再进入下一阶段
3. 如果遇到任何卡点，**立即停止**，输出 Stuck Report（模板见文末）
4. **不要自作主张**改动架构或添加不必要的抽象
5. 测试必须使用 `.venv`：`source .venv/bin/activate`

---

## Phase T1: 修复 Resolver 单测（去掉 @skipif，改用 fake 文件系统）

### 目标
`tests/unit/test_vasp_registry.py` 中的 `TestVASPResolver` 测试必须 CI 必跑，不可 skip

### 步骤

#### Step T1.1: 检查 vasp_resolver.py 是否有可 mock 的 repo root 函数

```bash
cd <HOME>/QMatSuite && source .venv/bin/activate
grep -n "_repo_root\|_get_repo_root\|repo_root" src/quantumvitas/core/engines/vasp_resolver.py
```

如果没有独立的 repo root 获取函数，需要添加一个：

**修改 `src/quantumvitas/core/engines/vasp_resolver.py`**:

在文件开头添加：
```python
def _get_repo_root() -> Path:
    """Get repository root directory. Can be mocked for testing."""
    import quantumvitas
    _pkg_path = Path(quantumvitas.__file__).parent
    return _pkg_path.parent.parent
```

然后将函数中直接使用 `_repo_root` 的地方改为调用 `_get_repo_root()`。

#### Step T1.2: 重写 TestVASPResolver 测试类

**修改 `tests/unit/test_vasp_registry.py`**:

1. **删除** `is_vasp_available()` 和 `is_potcar_available()` 函数
2. **删除** 所有 `@pytest.mark.skipif` 装饰器
3. **重写** `TestVASPResolver` 类如下：

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
        
        from quantumvitas.core.engines.vasp_resolver import resolve_vasp_bin
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
        
        # Clear env var and mock repo root
        monkeypatch.delenv("QMATS_VASP_STD_BIN", raising=False)
        
        import quantumvitas.core.engines.vasp_resolver as resolver_mod
        monkeypatch.setattr(resolver_mod, '_get_repo_root', lambda: tmp_path)
        
        from quantumvitas.core.engines.vasp_resolver import resolve_vasp_bin
        result = resolve_vasp_bin("std")
        assert result == fake_bin
    
    def test_resolve_vasp_bin_raises_when_not_found(self, monkeypatch, tmp_path):
        """Test resolver raises RuntimeError when VASP not found."""
        monkeypatch.delenv("QMATS_VASP_STD_BIN", raising=False)
        
        import quantumvitas.core.engines.vasp_resolver as resolver_mod
        monkeypatch.setattr(resolver_mod, '_get_repo_root', lambda: tmp_path)
        
        from quantumvitas.core.engines.vasp_resolver import resolve_vasp_bin
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
        
        import quantumvitas.core.engines.vasp_resolver as resolver_mod
        monkeypatch.setattr(resolver_mod, '_get_repo_root', lambda: tmp_path)
        
        from quantumvitas.core.engines.vasp_resolver import get_potcar_dir
        result = get_potcar_dir("PBE")
        assert result == potcar_dir
        assert (result / "Si" / "POTCAR").exists()
    
    def test_get_potcar_dir_raises_when_not_found(self, monkeypatch, tmp_path):
        """Test get_potcar_dir raises RuntimeError when not found."""
        import quantumvitas.core.engines.vasp_resolver as resolver_mod
        monkeypatch.setattr(resolver_mod, '_get_repo_root', lambda: tmp_path)
        
        from quantumvitas.core.engines.vasp_resolver import get_potcar_dir
        with pytest.raises(RuntimeError, match="POTCAR directory not found"):
            get_potcar_dir("PBE")
```

### 验收命令

```bash
cd <HOME>/QMatSuite && source .venv/bin/activate

# 确认无 skipif
grep -n "skipif" tests/unit/test_vasp_registry.py
# 应该返回空

# 运行 Resolver 测试
pytest tests/unit/test_vasp_registry.py::TestVASPResolver -v --tb=short

# 确认 CI 环境也能跑
CI=true pytest tests/unit/test_vasp_registry.py::TestVASPResolver -v --tb=short
```

### 卡点处理

如果 `_get_repo_root` mock 不生效，尝试以下替代方案：

```python
# 替代方案：直接 mock 模块级变量
import quantumvitas.core.engines.vasp_resolver as resolver_mod

# 在 resolve_vasp_bin 函数内部，替换对 _repo_root 的引用
original_file = resolver_mod.__file__
# ... 具体策略取决于代码结构
```

---

## Phase T2: 确认 E2E Mock 测试完全自给

### 目标
确认 `tests/integration/vasp/` 中所有测试使用 `use_fake_vasp` fixture 后无任何真实依赖

### 步骤

#### Step T2.1: 检查所有测试都依赖 use_fake_vasp

```bash
cd <HOME>/QMatSuite && source .venv/bin/activate

# 列出所有测试函数
grep -n "def test_" tests/integration/vasp/test_vasp_*.py

# 检查 fixture 依赖
grep -n "use_fake_vasp\|vasp_project\|vasp_calculation" tests/integration/vasp/test_vasp_*.py
```

确认：每个 `test_` 函数的参数中都有 `use_fake_vasp` 或依赖它的 fixture。

#### Step T2.2: 在 CI 模式下运行测试

```bash
# 模拟 CI 环境
CI=true pytest tests/integration/vasp/ -v --tb=short

# 如果全绿，则 Phase T2 完成
```

### 验收命令

```bash
cd <HOME>/QMatSuite && source .venv/bin/activate

# 子集验证
pytest tests/integration/vasp/ -v --tb=short

# CI 模式验证
CI=true pytest tests/integration/vasp/ -v --tb=short
```

---

## Phase T3: 新增真实 VASP 测试文件

### 目标
创建 `tests/integration/vasp/test_vasp_real.py`，实现 CI skip / 本地 fail 规则

### 步骤

#### Step T3.1: 创建测试文件

**创建 `tests/integration/vasp/test_vasp_real.py`**:

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
    """Check if running in CI environment."""
    return os.environ.get("CI", "").lower() in ("true", "1", "yes")


def check_real_vasp() -> tuple[bool, str]:
    """Check for real VASP binary. Returns (available, message)."""
    try:
        from quantumvitas.core.engines.vasp_resolver import resolve_vasp_bin
        bin_path = resolve_vasp_bin("std")
        if not bin_path.exists():
            return False, f"VASP binary does not exist: {bin_path}"
        # Verify it's the real binary, not fake_vasp.py
        if bin_path.suffix == ".py":
            return False, f"Found fake_vasp.py, not real binary: {bin_path}"
        return True, f"Found VASP at: {bin_path}"
    except RuntimeError as e:
        return False, str(e)


def check_real_potcar() -> tuple[bool, str]:
    """Check for real POTCAR directory. Returns (available, message)."""
    try:
        from quantumvitas.core.engines.vasp_resolver import get_potcar_dir
        potcar_dir = get_potcar_dir("PBE")
        si_potcar = potcar_dir / "Si" / "POTCAR"
        if not si_potcar.exists():
            return False, f"Si POTCAR does not exist: {si_potcar}"
        # Verify it's a real POTCAR (>1KB)
        size = si_potcar.stat().st_size
        if size < 1000:
            return False, f"Si POTCAR too small ({size} bytes), likely fake"
        return True, f"Found POTCAR at: {potcar_dir}"
    except RuntimeError as e:
        return False, str(e)


@pytest.fixture(scope="module")
def real_vasp_required():
    """Fixture: skip in CI, fail locally if resources missing."""
    if is_ci():
        pytest.skip("Real VASP tests skipped in CI environment")
    
    vasp_ok, vasp_msg = check_real_vasp()
    potcar_ok, potcar_msg = check_real_potcar()
    
    if not vasp_ok:
        pytest.fail(
            f"Real VASP binary not available.\n"
            f"Reason: {vasp_msg}\n\n"
            f"Expected location (relative to repo root):\n"
            f"  ./.qmatsuite/engines/vasp/vasp.6.5.0/bin/vasp_std\n\n"
            f"To fix:\n"
            f"  1. Install VASP at the above location, OR\n"
            f"  2. Set QMATS_VASP_STD_BIN environment variable"
        )
    
    if not potcar_ok:
        pytest.fail(
            f"Real POTCAR directory not available.\n"
            f"Reason: {potcar_msg}\n\n"
            f"Expected location (relative to repo root):\n"
            f"  ./.qmatsuite/engines/vasp/potpaw_PBE.64/\n\n"
            f"To fix:\n"
            f"  Install VASP POTCARs at the above location"
        )
    
    return {"vasp_msg": vasp_msg, "potcar_msg": potcar_msg}


pytestmark = [pytest.mark.integration, pytest.mark.vasp_real]


class TestRealVASPSmoke:
    """Smoke tests with real VASP binary.
    
    These tests verify that real VASP runs correctly and produces expected outputs.
    They are NOT run in CI (skipped when CI=true).
    """
    
    def test_real_vasp_available(self, real_vasp_required):
        """Verify real VASP is available (meta-test)."""
        assert real_vasp_required is not None
        print(f"VASP: {real_vasp_required['vasp_msg']}")
        print(f"POTCAR: {real_vasp_required['potcar_msg']}")
    
    def test_scf_smoke(self, real_vasp_required, tmp_path):
        """Run real SCF and verify basic outputs."""
        # TODO: Implement in Phase N1
        # This test should:
        # 1. Create minimal Si structure
        # 2. Run SCF via VaspEngine
        # 3. Verify OUTCAR, OSZICAR, CHGCAR exist
        # 4. Parse energy from OSZICAR
        pytest.skip("TODO: Implement in Phase N1")
    
    def test_bands_smoke(self, real_vasp_required, tmp_path):
        """Run real Bands and verify EIGENVAL."""
        # TODO: Implement in Phase N1
        pytest.skip("TODO: Implement in Phase N1")
    
    def test_dos_smoke(self, real_vasp_required, tmp_path):
        """Run real DOS and verify DOSCAR."""
        # TODO: Implement in Phase N1
        pytest.skip("TODO: Implement in Phase N1")
```

### 验收命令

```bash
cd <HOME>/QMatSuite && source .venv/bin/activate

# 语法检查
python -m py_compile tests/integration/vasp/test_vasp_real.py

# CI 模式：应该全部 skip
CI=true pytest tests/integration/vasp/test_vasp_real.py -v --tb=short
# 期望输出: X skipped

# 本地模式（有真实 VASP）：应该运行
pytest tests/integration/vasp/test_vasp_real.py -v --tb=short
# 期望: test_real_vasp_available PASSED, 其他 skipped (TODO)

# 本地模式（无真实 VASP）：应该 fail 并给出错误提示
# 需要先清除 env var
unset QMATS_VASP_STD_BIN
pytest tests/integration/vasp/test_vasp_real.py::TestRealVASPSmoke::test_real_vasp_available -v --tb=short
# 期望: FAILED with actionable error message
```

---

## Phase N1: 本地真实 VASP Smoke（需要真实 VASP）

### 目标
实现 `test_vasp_real.py` 中的 smoke 测试，验证真实 VASP 运行

### Prerequisites
- Phase T1-T3 完成
- 真实 VASP binary 和 POTCAR 已安装

### 步骤

#### Step N1.1: 实现 test_scf_smoke

**修改 `tests/integration/vasp/test_vasp_real.py`**:

```python
def test_scf_smoke(self, real_vasp_required, tmp_path):
    """Run real SCF and verify basic outputs."""
    from pymatgen.core import Structure, Lattice
    from quantumvitas.engine.vasp_engine import VaspEngine
    from quantumvitas.engine.vasp_writer import write_poscar, write_incar, write_kpoints, write_potcar
    from quantumvitas.engine.vasp_parser import parse_oszicar
    
    # Create minimal Si structure
    lattice = Lattice.cubic(5.43)
    structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
    
    # Setup working directory
    work_dir = tmp_path / "scf"
    work_dir.mkdir()
    
    # Write input files
    write_poscar(structure, work_dir / "POSCAR")
    write_incar({
        "SYSTEM": "Si2_SCF_smoke",
        "ENCUT": 300,
        "ISMEAR": 0,
        "SIGMA": 0.05,
        "IBRION": -1,
        "NSW": 0,
        "LWAVE": True,
        "LCHARG": True,
    }, work_dir / "INCAR")
    write_kpoints({"mode": "automatic", "mesh": [4, 4, 4], "shift": [0, 0, 0]}, work_dir / "KPOINTS")
    write_potcar(structure, {"Si": {}}, work_dir / "POTCAR", "PBE")
    
    # Run VASP
    from quantumvitas.core.engines.vasp_resolver import resolve_vasp_bin
    import subprocess
    vasp_bin = resolve_vasp_bin("std")
    result = subprocess.run(
        [str(vasp_bin)],
        cwd=work_dir,
        capture_output=True,
        text=True,
        timeout=300,  # 5 minutes timeout
    )
    
    # Verify outputs exist
    assert (work_dir / "OUTCAR").exists(), "OUTCAR not created"
    assert (work_dir / "OSZICAR").exists(), "OSZICAR not created"
    assert (work_dir / "CHGCAR").exists(), "CHGCAR not created"
    
    # Parse energy
    oszicar_data = parse_oszicar(work_dir / "OSZICAR")
    assert oszicar_data is not None, "Failed to parse OSZICAR"
    assert "energy" in oszicar_data, "No energy in parsed OSZICAR"
    
    # Print for evidence collection
    print(f"SCF Energy: {oszicar_data['energy']} eV")
    print(f"Exit code: {result.returncode}")
```

#### Step N1.2: 实现 test_bands_smoke 和 test_dos_smoke

类似模式，但需要先运行 SCF 获取 CHGCAR。

### 验收命令

```bash
cd <HOME>/QMatSuite && source .venv/bin/activate

# 运行 smoke 测试（需要真实 VASP）
pytest tests/integration/vasp/test_vasp_real.py -v --tb=short -k smoke

# 查看输出
ls -la /tmp/pytest-*/pytest-*/test_scf_smoke*/scf/
```

---

## Phase N2: Parser + Digest 落地

### 目标
完善 VASP 解析器并接入 digest/history 系统

### 步骤

#### Step N2.1: 检查现有 parser 实现

```bash
cd <HOME>/QMatSuite && source .venv/bin/activate

# 查看现有 parser
cat src/quantumvitas/engine/vasp_parser.py

# 查看现有测试
cat tests/unit/test_vasp_parser.py
```

#### Step N2.2: 扩展 parser 功能

根据 v2.0 spec 的 parser priority：

| Step | Primary | Fallback |
|------|---------|----------|
| SCF | `OSZICAR` | `OUTCAR` |
| Bands | `EIGENVAL` | `vasprun.xml` |
| DOS | `DOSCAR` | `vasprun.xml` |

**需要实现/完善的函数**:
- `parse_oszicar(path)` → `{"energy": float, "n_iterations": int, "converged": bool}`
- `parse_outcar(path)` → `{"energy": float, "timing": float, "version": str}`
- `parse_eigenval(path)` → `{"kpoints": [...], "bands": [...], "efermi": float}`
- `parse_doscar(path)` → `{"energies": [...], "dos": [...], "efermi": float}`

#### Step N2.3: 创建 fixture 文件

从真实 VASP 运行中收集非敏感输出片段：

```bash
# 在 .tmp/vasp_real_smoke/ 运行后
head -50 .tmp/vasp_real_smoke/scf/OSZICAR > tests/fixtures/vasp/oszicar_scf_sample.txt
head -100 .tmp/vasp_real_smoke/scf/OUTCAR > tests/fixtures/vasp/outcar_header_sample.txt
head -20 .tmp/vasp_real_smoke/bands/EIGENVAL > tests/fixtures/vasp/eigenval_header_sample.txt
head -20 .tmp/vasp_real_smoke/dos/DOSCAR > tests/fixtures/vasp/doscar_header_sample.txt
```

### 验收命令

```bash
cd <HOME>/QMatSuite && source .venv/bin/activate

# Parser 单测
pytest tests/unit/test_vasp_parser.py -v --tb=short

# 全量测试确认无回归
pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

## Phase N3: UI 隐藏 0-Mapping GEN Steps

### 目标
在 step 列表 API 中过滤掉 0-mapped GEN steps

### 步骤

#### Step N3.1: 定位 step 列表 API

```bash
cd <HOME>/QMatSuite && source .venv/bin/activate

# 搜索可能的 listing 函数
grep -rn "list.*step\|available.*step" src/quantumvitas/api.py | head -20
```

#### Step N3.2: 添加过滤逻辑

在找到的 listing 函数中添加：

```python
from quantumvitas.workflow.generalized_steps import materialize_step

def list_available_gen_steps(engine_family: str) -> list[str]:
    """List GEN steps available for given engine family."""
    all_gen_steps = ["scf", "nscf", "bands", "bandspp", "dos", "dospp", "relax"]
    
    available = []
    for gen_step in all_gen_steps:
        spec_step = materialize_step(gen_step.upper(), engine_family)
        if spec_step is not None:  # Not 0-mapped
            available.append(gen_step)
    
    return available
```

### 验收命令

```bash
cd <HOME>/QMatSuite && source .venv/bin/activate

# 如果有相关测试
pytest tests/ -v --tb=short -k "list.*step" 

# 手动验证
python -c "
from quantumvitas.workflow.generalized_steps import materialize_step
for step in ['scf', 'nscf', 'bands', 'bandspp', 'dos', 'dospp', 'relax']:
    result = materialize_step(step.upper(), 'vasp')
    status = '0-mapped (hidden)' if result is None else f'-> {result}'
    print(f'{step}: {status}')
"
# 期望输出:
# scf: -> vasp_scf
# nscf: -> vasp_nscf
# bands: -> vasp_bands
# bandspp: 0-mapped (hidden)
# dos: 0-mapped (hidden)
# dospp: 0-mapped (hidden)
# relax: -> vasp_relax
```

---

## 全量回归测试

每个 Phase 完成后，以及所有 Phase 完成后，运行：

```bash
cd <HOME>/QMatSuite && source .venv/bin/activate

# 全量测试（并行）
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile

# 期望：全绿
```

---

## Stuck Report 模板

如果在任何步骤中遇到无法解决的问题，**立即停止**并输出以下报告：

```markdown
## Stuck Point Report

### Phase: [T1/T2/T3/N1/N2/N3]
### Step: [具体步骤编号]
### Operation: [正在尝试做什么]

### 命令:
```
[执行的具体命令]
```

### 退出码: [N]

### 目录结构:
```
[ls -la 相关目录的输出]
```

### 相关文件内容:
```
[head/tail 关键文件的输出]
```

### 错误信息:
```
[完整的错误文本]
```

### 期望 vs 实际:
- 期望: ...
- 实际: ...

### 已尝试的解决方案:
1. ...
2. ...

### 给 Opus 的问题:
1. ...
2. ...
```

---

## 执行顺序总结

```
T1 (Resolver 单测) ─┬─> T2 (E2E 确认) ─┬─> T3 (Real 新增) ─> N1 (Smoke) ─> N2 (Parser)
                   │                  │
                   └──────────────────┴─> N3 (UI 过滤) [可并行]
```

**先做 T1-T3（测试体系清理），再做 N1-N3（功能推进）。**

