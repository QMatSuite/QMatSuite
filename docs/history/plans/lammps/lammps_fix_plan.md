# LAMMPS 集成修复计划

## 执行纪律

**每个 PR 都必须运行全量并行回归**：
```bash
source .venv/bin/activate
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

**如果 LAMMPS integration tests 报"缺二进制"**，必须提供证据：
```bash
brew --prefix lammps
ls -l /opt/homebrew/opt/lammps/bin
/opt/homebrew/opt/lammps/bin/lmp_serial -h | head -n 5
python -c "from qmatsuite.core.engines.lammps_resolver import resolve_lammps_bin; print(resolve_lammps_bin())"
```
并修复 discovery/marker，**不许改 tests 去 skip**。

---

## PR 1: 回滚污染代码 + 实现 LAMMPSRecipe

### 1.1 改动清单

#### A) 移除 structure_steps.py 污染

**文件**：`src/qmatsuite/calculation/structure_steps.py`

**删除 #1**（第785-787行，`is_lammps_step` 定义）：
```python
# 删除这三行
    # LAMMPS step types - LAMMPS engine builds input dynamically (not QE input)
    LAMMPS_STEP_TYPES = {"lammps_relax", "lammps_md"}
    is_lammps_step = step_type_lower in LAMMPS_STEP_TYPES or calculation_engine_family == "lammps"
```

**删除 #2**（第1099-1118行，`if is_lammps_step:` 块）：
```python
# 删除整个块（约20行）
    # LAMMPS steps - no QE input file generation (LAMMPS engine builds input dynamically)
    if is_lammps_step:
        logger.info(
            f"[MATERIALIZE_STEP_SPEC] LAMMPS step detected: step_type={step_type_lower}, "
            f"engine_family={calculation_engine_family}, skipping QE input generation. "
            f"LAMMPS engine will build input dynamically from structure + parameters."
        )
        # Generate a dummy input file path (LAMMPS engine doesn't use it, but Step.input_file requires a path)
        from qmatsuite.calculation.naming import CalculationFileNaming
        if input_name:
            filename = input_name
        else:
            ext = CalculationFileNaming.input_extension(step_type_lower)
            filename = f"{step_type_lower}{ext}"

        generated_input = Path(output_dir) / filename
        generated_input = generated_input.resolve()
        generated_input.parent.mkdir(parents=True, exist_ok=True)
        # Don't write a file - LAMMPS engine builds input dynamically
        return generated_input, spec_obj
```

#### B) 回滚 VASPRecipe 映射 + 实现 LAMMPSRecipe

**文件**：`src/qmatsuite/execution/recipes.py`

**修改 #1**（第577行，删除 VASPRecipe 映射）：
```python
# 修改前
    recipes = {
        "qe": QERecipe,
        "orca": ORCARecipe,
        "pyscf": PySCFRecipe,
        "vasp": VASPRecipe,
        "lammps": VASPRecipe,  # LAMMPS uses same recipe pattern as VASP (isolated workdirs)
    }

# 修改后
    recipes = {
        "qe": QERecipe,
        "orca": ORCARecipe,
        "pyscf": PySCFRecipe,
        "vasp": VASPRecipe,
        "lammps": LAMMPSRecipe,
    }
```

**新增 #1**（在 VASPRecipe 类之后，约第334行后）：
```python
class LAMMPSRecipe(BaseRecipe):
    """
    LAMMPS-Recipe: Isolated workdir per step, classical MD model.
    
    Creates one job per step. Each step runs in its own isolated workdir:
    `calc/raw/<step_ulid>/`
    
    File layout:
    - Input: in.lammps, structure.data, *.eam/*.tersoff (potentials)
    - Output: log.lammps, *.lammpstrj, final.data (for relax)
    
    Used by: LAMMPS
    """
    
    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """
        Materialize jobs for LAMMPS steps.
        
        Each step gets its own isolated workdir: calc_raw_dir / step_ulid
        
        Args:
            steps: List of LAMMPS steps
            calc_raw_dir: Path to calc/raw/
            step_shas: Optional dict for fingerprinting
        
        Returns:
            JobGraph with one job per step
        """
        if not steps:
            return JobGraph(jobs=[])
        
        registry = get_registry()
        jobs: List[Job] = []
        
        for step in steps:
            # Get step type info
            step_type = step.step_type
            spec = registry.get(step_type) if step_type else None
            public_type = spec.public_type if spec else "unknown"
            
            # Job ID = step ULID
            job_id = step.meta.id
            
            # Working directory: isolated per step
            working_dir = calc_raw_dir / step.meta.id
            
            # LAMMPS executable (from resolver, not spec)
            # Executable resolution happens at runtime in handler
            executable = "lmp"  # Placeholder; actual path resolved by LammpsEngine
            
            # Command: lmp -in in.lammps -log log.lammps
            command = [executable, "-in", "in.lammps", "-log", "log.lammps"]
            
            # Input files (will be materialized into working_dir by LammpsEngine)
            input_files = [
                working_dir / "in.lammps",
                working_dir / "structure.data",
            ]
            
            # Expected outputs
            expected_outputs = [
                working_dir / "log.lammps",
            ]
            # Add final.data for relax steps
            if public_type == "relax":
                expected_outputs.append(working_dir / "final.data")
            
            # Fingerprint
            step_sha = self._get_step_sha(step, step_shas)
            fingerprint = step_sha if step_sha else None
            
            # Dependencies: linear (each step depends on previous)
            deps = []
            if len(jobs) > 0:
                deps = [jobs[-1].id]
            
            # Create job
            job = Job(
                id=job_id,
                step_ids=[step.meta.id],
                working_dir=working_dir,
                command=command,
                input_files=input_files,
                expected_outputs=expected_outputs,
                deps=deps,
                fingerprint=fingerprint,
                metadata={
                    "engine": "lammps",
                    "spec_step_type": spec.machine_type if spec else None,
                    "public_type": public_type,
                },
            )
            jobs.append(job)
        
        return JobGraph(jobs=jobs)
```

### 1.2 预期行为

- `get_recipe_for_engine("lammps")` 返回 `LAMMPSRecipe` 实例
- `LAMMPSRecipe.materialize()` 生成正确的 LAMMPS 文件布局
- `structure_steps.py` 不再有 LAMMPS 特殊处理
- LAMMPS step 不会进入 QE PATH（由 LammpsEngine 处理 materialize）

### 1.3 验收测试

```bash
# 单元测试：确保 recipe 正确
python -m pytest tests/unit/test_lammps_engine.py -v --tb=short

# 确保 structure_steps.py 无回归
python -m pytest tests/unit/test_step_type_mapping.py -v --tb=short

# 全量回归
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### 1.4 回滚点

如果 PR 1 导致其他引擎（QE/VASP/ORCA/PySCF）回归：
1. `git revert` PR 1 commit
2. 分析调用链，确保 LAMMPS 逻辑完全隔离

---

## PR 2: 修复 LAMMPS Integration Tests

### 2.1 问题诊断

**首先验证 LAMMPS 二进制可用性**（Auto 必须执行）：
```bash
# 验证 brew 安装
brew --prefix lammps

# 验证二进制存在
ls -l /opt/homebrew/opt/lammps/bin

# 验证二进制可执行
/opt/homebrew/opt/lammps/bin/lmp_serial -h | head -n 5

# 验证 Python resolver 能找到
python -c "from qmatsuite.core.engines.lammps_resolver import resolve_lammps_bin; print(resolve_lammps_bin())"
```

### 2.2 可能的修复

#### A) 如果 resolver 返回正确路径但 tests 仍 skip

**检查 fixture 中的 skip 逻辑**：
```python
# tests/integration/test_lammps_lj_minimize.py:29-32
try:
    resolve_lammps_bin()
except FileNotFoundError:
    pytest.skip("LAMMPS not installed")
```

**可能问题**：fixture 在 collection 阶段执行，PATH 环境可能不同

**修复方案**：在 `conftest.py` 中添加 pytest fixture 自动设置 PATH

#### B) 如果 resolver 无法找到二进制

**检查 resolver 逻辑**：
- 确认 `/opt/homebrew/opt/lammps` 目录存在检测正确
- 确认 `lmp_serial` 二进制名匹配

**修复方案**：在 resolver 中添加 debug logging

### 2.3 改动清单

#### 如果需要修复 marker/discovery

**文件**：`tests/conftest.py`

**新增 fixture**（确保 LAMMPS PATH 可用）：
```python
@pytest.fixture(autouse=True)
def ensure_lammps_path():
    """Ensure LAMMPS binary path is in environment."""
    import os
    brew_prefix = "/opt/homebrew/opt/lammps/bin"
    if os.path.exists(brew_prefix):
        if brew_prefix not in os.environ.get("PATH", ""):
            os.environ["PATH"] = f"{brew_prefix}:{os.environ.get('PATH', '')}"
```

#### 如果需要改进 resolver 诊断

**文件**：`src/qmatsuite/core/engines/lammps_resolver.py`

**添加 debug logging**（在 FileNotFoundError 前）：
```python
import logging
logger = logging.getLogger(__name__)
logger.warning(f"LAMMPS not found. Searched: ENV={env_bin}, brew={brew_prefixes}, apt={apt_paths}")
```

### 2.4 预期行为

- 本机 brew 安装 LAMMPS 后，integration tests 能真实运行
- 不再出现"缺二进制"的 skip
- tests 真实验证 LAMMPS 工作流

### 2.5 验收测试

```bash
# 验证 LAMMPS tests 能找到二进制并运行
python -m pytest tests/integration/test_lammps_lj_minimize.py -v --tb=short

# 验证所有 LAMMPS integration tests
python -m pytest tests/integration/test_lammps_*.py -v --tb=short

# 全量回归
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### 2.6 回滚点

如果 PR 2 导致其他测试回归：
1. `git revert` PR 2 commit
2. 分析 conftest.py 变更的副作用

---

## PR 3: 验证 species_map Gate 正确性（可选）

### 3.1 目的

确认 species_map gate 在 runner 层面已正确条件化，不再需要 structure_steps.py 绕路。

### 3.2 验证项

1. **runner.py:154**：`if calculation.species_map:` 已正确条件化 Step0
2. **runner.py:376**：`if engine_family == "lammps":` 正确分流 potential_assets_sha
3. **LAMMPS tests**：无 species_map 时不触发 pseudo validation error

### 3.3 测试用例

```python
# 新增测试：LAMMPS 无 species_map 不应报错
def test_lammps_no_species_map_required():
    """LAMMPS calculations should not require species_map."""
    # ... 创建 LAMMPS calculation without species_map
    # ... 验证不抛出 "Pseudopotential not configured" 错误
```

### 3.4 验收测试

```bash
# 运行 LAMMPS 特定测试
python -m pytest tests/integration/test_lammps_*.py -v --tb=short

# 运行 QE pseudo 相关测试（确保不削弱）
python -m pytest tests/unit/test_pseudo_*.py -v --tb=short

# 全量回归
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

## 最终交付标准

1. **全量并行 pytest 绿**：0 failed, 0 errors
2. **LAMMPS integration tests 真实运行**：不依赖 skip，本机 brew 可执行
3. **无架构污染**：
   - `structure_steps.py` 无 `is_lammps_step`
   - `recipes.py` 使用独立的 `LAMMPSRecipe`
   - species_map gate 在 runner 层面条件化
4. **不削弱 QE/VASP 强制逻辑**：pseudo 相关测试全部通过

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| LAMMPSRecipe 实现不正确 | 中 | 高 | 参考 VASPRecipe 模式，单元测试覆盖 |
| structure_steps 移除导致回归 | 低 | 高 | 全量回归验证，LAMMPS 应完全隔离 |
| integration tests PATH 问题 | 中 | 中 | 诊断优先，添加 debug logging |
| species_map gate 位置影响 QE | 低 | 高 | 保持 runner.py 逻辑不变 |

