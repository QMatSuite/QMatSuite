# MASTER PROMPT FOR CURSOR AUTO

**RELAX 三引擎真实 E2E 实现**

---

## 项目背景

你正在实现 QMatSuite 的 RELAX 功能：将 GEN step 统一为单一的 `relax` public type，并真正调用 QE/ORCA/PySCF 执行几何优化。

**必读文档** (按顺序):
1. `docs/specs/RELAX_SPEC.md` - 核心规范
2. `docs/research/RELAX_ENGINE_RESEARCH.md` - 三引擎研究
3. `docs/reviews/RELAX_CURSOR_IMPLEMENTATION_REVIEW.md` - 现状审查
4. `docs/plans/RELAX_UNIFY_GENSTEP_PATCH_PLAN.md` - 统一计划
5. `docs/plans/RELAX_3ENGINES_REAL_E2E_PLAN.md` - E2E 实现计划
6. `docs/checklists/RELAX_PR_REVIEW_CHECKLIST.md` - 每 PR 自检

---

## PR 执行顺序

### PR-1: Registry 统一 + 删除 qe_vc_relax

**目标**: 将 `qe_vc_relax` 合并到 `qe_relax`

**文件修改**:
1. `src/quantumvitas/workflow/registry.py`
   - 删除 `"qe_vc_relax": StepTypeSpec(...)` 条目
   - 更新 `"qe_relax"` 的 description: "Structure relaxation (positions and optionally cell)"

2. `src/quantumvitas/engine/qc_engine_base.py`
   - 修改 `RELAX_STEP_TYPES = {"relax"}` (删除 vc-relax, opt, geomopt)

3. `tests/unit/test_step_type_mapping.py`
   - 删除或更新 `vc-relax` 相关测试
   - 添加: 验证只有 `relax` 是 GEN public type

**验收**:
```bash
pytest tests/unit/test_step_type_mapping.py -v
# 确认: 无 vc-relax 测试失败
grep "vc-relax" src/quantumvitas/workflow/registry.py
# 确认: 无输出
```

---

### PR-2: 添加 ORCA/PySCF Relax Step Types

**目标**: 添加 `orca_relax` 和 `pyscf_relax`

**文件修改**:
1. `src/quantumvitas/workflow/registry.py`
   - 添加:
     ```python
     "orca_relax": StepTypeSpec(
         id="relax",
         machine_type="orca_relax",
         public_type="relax",
         engine="orca",
         executable="orca",
         description="ORCA geometry optimization",
         requires_structure=True,
         requires_charge_density=False,
         produces_charge_density=False,
         is_structure_transform=True,
     ),
     "pyscf_relax": StepTypeSpec(
         id="relax",
         machine_type="pyscf_relax",
         public_type="relax",
         engine="pyscf",
         executable="python",
         description="PySCF geometry optimization (geomopt)",
         requires_structure=True,
         requires_charge_density=False,
         produces_charge_density=False,
         is_structure_transform=True,
     ),
     ```

2. `src/quantumvitas/engine/orca_engine.py`
   - 在 `supported_step_types()` 添加 `"orca_relax"`

**验收**:
```bash
pytest tests/unit/test_step_type_mapping.py -v
# 确认: orca_relax, pyscf_relax 可以通过 registry.get() 获取
```

---

### PR-3: Compat Shim for Legacy Types

**目标**: 向后兼容 `vc-relax`, `opt`, `geomopt`

**文件修改**:
1. `src/quantumvitas/workflow/registry.py`
   - 添加:
     ```python
     STEP_TYPE_ALIASES = {
         "vc-relax": "relax",
         "qe_vc_relax": "qe_relax",
         "opt": "relax",
         "geomopt": "relax",
     }
     
     def normalize_step_type(step_type: str) -> str:
         if step_type in STEP_TYPE_ALIASES:
             import warnings
             warnings.warn(
                 f"Step type '{step_type}' is deprecated. Use 'relax' instead.",
                 DeprecationWarning,
             )
             return STEP_TYPE_ALIASES[step_type]
         return step_type
     ```

2. `tests/unit/test_registry_compat.py` (新增)
   - 测试 alias 映射
   - 测试 deprecation warning

**验收**:
```bash
pytest tests/unit/test_registry_compat.py -v
```

---

### PR-4: QE Relax Output Handler

**目标**: 解析 QE relax 输出，写入 `current.json`

**文件修改**:
1. `src/quantumvitas/execution/handlers.py`
   - 添加 `handle_qe_relax_output()` 函数 (见 E2E Plan §4.3.1)

2. `src/quantumvitas/execution/executor.py`
   - 在 job 成功后调用 `_post_process_job()`
   - 检测 relax step，调用 handler

**验收**:
```bash
pytest tests/unit/execution/test_relax_artifacts.py -v
# 新增测试: test_handle_qe_relax_output
```

---

### PR-5: Job Scoped Cleanup

**目标**: Job 开始前清理覆盖的 relax steps 的 `current.json`

**文件修改**:
1. `src/quantumvitas/execution/executor.py`
   - 在 job 开始前:
     ```python
     for step_ulid in job.step_ids:
         if is_relax_step_type(self._get_step_type(step_ulid)):
             clean_generated_structure(calc_dir, step_ulid)
     ```

**验收**:
```bash
pytest tests/unit/execution/test_relax_artifacts.py -v
# 新增测试: test_scoped_cleanup
```

---

### PR-6: Missing Artifact Check

**目标**: 依赖 effective structure 时检查 `current.json` 存在

**文件修改**:
1. `src/quantumvitas/execution/executor.py`
   - 在需要 effective structure 时:
     ```python
     if needs_effective_structure and previous_relax_ulid:
         artifact_path = get_generated_structure_path(calc_dir, previous_relax_ulid)
         if not artifact_path.exists():
             raise MissingArtifactError(
                 f"Step '{step_name}' requires relaxed structure from step '{relax_step_name}' "
                 f"(ULID: {previous_relax_ulid}), but generated_structures/step_{previous_relax_ulid}/current.json "
                 "is missing.\n\n"
                 "This typically means:\n"
                 "- The relax step has not been executed yet\n"
                 "- The relax step failed before producing output\n"
                 "- The generated_structures directory was deleted\n\n"
                 "To fix: Run the calculation from the beginning, or run the relax step first."
             )
     ```

**验收**:
```bash
pytest tests/unit/test_manifest_effective_structure.py -v
# 确认 MissingArtifactError 测试通过
```

---

### PR-7: ORCA Relax Parser

**目标**: 解析 ORCA `basename.xyz` 输出

**文件新增**:
1. `src/quantumvitas/execution/orca_relax_parser.py` (见 E2E Plan §5.3.1)

2. `src/quantumvitas/engines/orca/input_compiler.py`
   - 在 `compile()` 中检测 relax step，添加 `Opt` 关键词

**验收**:
```bash
pytest tests/unit/execution/test_orca_relax_parser.py -v
```

---

### PR-8: PySCF Relax Handler

**目标**: 在 PySCF runner 中处理 relax step

**文件修改**:
1. `src/quantumvitas/engines/pyscf/runner.py`
   - 添加 `run_pyscf_relax()` 函数 (见 E2E Plan §6.3.1)

2. `src/quantumvitas/execution/pyscf_relax_handler.py` (新增)
   - `handle_pyscf_relax_output()` (见 E2E Plan §6.3.2)

**验收**:
```bash
pytest tests/unit/execution/test_pyscf_relax_handler.py -v
```

---

### PR-9: Real QE Relax Test

**目标**: 真实调用 QE pw.x 执行 relax

**文件新增**:
1. `tests/integration/test_qe_relax_real.py` (见 E2E Plan §4.4)

**验收**:
```bash
pytest tests/integration/test_qe_relax_real.py -v -m qe
# 需要 QE 可用
```

---

### PR-10: Real ORCA Relax Test

**目标**: 真实调用 ORCA 执行 Opt

**文件新增**:
1. `tests/integration/test_orca_relax_real.py` (见 E2E Plan §5.4)

**验收**:
```bash
pytest tests/integration/test_orca_relax_real.py -v -m orca
# 需要 ORCA 可用
```

---

### PR-11: Real PySCF Relax Test

**目标**: 真实调用 PySCF geomopt

**文件新增**:
1. `tests/integration/test_pyscf_relax_real.py` (见 E2E Plan §6.4)

**验收**:
```bash
pytest tests/integration/test_pyscf_relax_real.py -v
# 需要 pyscf + geometric 可用
```

---

### PR-12: Promote E2E Test

**目标**: 验证 relax → promote → use 完整流程

**文件新增**:
1. `tests/integration/test_relax_promote_e2e.py` (见 E2E Plan §7.2)

**验收**:
```bash
pytest tests/integration/test_relax_promote_e2e.py -v
```

---

## 每 PR 完成后必做

1. **运行所有相关测试**
   ```bash
   pytest tests/unit/test_step_type_mapping.py tests/unit/execution/test_qc_topology.py tests/unit/execution/test_relax_artifacts.py -v
   ```

2. **对照 Checklist 自检**
   - 打开 `docs/checklists/RELAX_PR_REVIEW_CHECKLIST.md`
   - 逐项检查

3. **Grep 验证**
   ```bash
   grep "RELAX_STEP_TYPES" src/quantumvitas/engine/qc_engine_base.py
   # 应只包含 "relax"
   
   grep -c "vc-relax" src/quantumvitas/workflow/registry.py
   # 应为 0 (从 PR-1 开始)
   ```

---

## 关键约束 (不可违反)

1. **Canonicalize 唯一入口**: 只使用 `structure_from_qe_geometry_snapshot()` 或 `canonicalize_structure_in_place()`

2. **SHA 唯一入口**: 只使用 `structure_fingerprint(structure, tol=1e-5)`

3. **Artifact 路径**: `generated_structures/step_<ulid>/current.json`

4. **Missing Artifact**: Hard error，不自动重跑

5. **QC Topology**: Relax 是 standalone chain，不能穿越

6. **Promote**: 必须传 step_selector (dropdown 语义)

---

## 文件路径速查

| 功能 | 文件路径 |
|------|----------|
| Registry | `src/quantumvitas/workflow/registry.py` |
| Relax Artifacts | `src/quantumvitas/execution/relax_artifacts.py` |
| QC Topology | `src/quantumvitas/execution/recipes.py` |
| QE Geometry Parser | `src/quantumvitas/calculation/geometry.py` |
| Executor | `src/quantumvitas/execution/executor.py` |
| ORCA Engine | `src/quantumvitas/engine/orca_engine.py` |
| PySCF Engine | `src/quantumvitas/engine/pyscf_engine.py` |
| Promote API | `src/quantumvitas/api.py` |
| Exceptions | `src/quantumvitas/core/exceptions.py` |

---

## 开始执行

从 **PR-1** 开始，严格按顺序执行。每个 PR 完成后打勾:

- [ ] PR-1: Registry 统一 + 删除 qe_vc_relax
- [ ] PR-2: 添加 ORCA/PySCF Relax Step Types
- [ ] PR-3: Compat Shim for Legacy Types
- [ ] PR-4: QE Relax Output Handler
- [ ] PR-5: Job Scoped Cleanup
- [ ] PR-6: Missing Artifact Check
- [ ] PR-7: ORCA Relax Parser
- [ ] PR-8: PySCF Relax Handler
- [ ] PR-9: Real QE Relax Test
- [ ] PR-10: Real ORCA Relax Test
- [ ] PR-11: Real PySCF Relax Test
- [ ] PR-12: Promote E2E Test

---

**开始吧！**

