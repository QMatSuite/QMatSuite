# RELAX PR Review Checklist

**Version**: 1.0.0
**Date**: 2026-01-18

---

## 使用说明

Cursor Auto 每完成一个 PR，必须对照本清单逐项自检。
标记 ✅ 表示通过，❌ 表示不通过（需修复）。

---

## 1. GEN Step 唯一性

- [ ] **CHECK-1.1**: Public type 只有 `relax`
  - `grep -r "public_type.*=.*relax" src/` 只应返回 `"relax"`
  - 不应存在 `"vc-relax"`, `"opt"`, `"geomopt"` 作为独立 public type

- [ ] **CHECK-1.2**: `RELAX_STEP_TYPES` 只包含 `"relax"`
  - 检查 `src/quantumvitas/engine/qc_engine_base.py`
  - `RELAX_STEP_TYPES = {"relax"}`

- [ ] **CHECK-1.3**: VC-relax 通过 option 控制
  - QE: `parameters.CONTROL.calculation = "vc-relax"` 而非独立 step type
  - 或 `parameters.relax.vc = true`

---

## 2. QC Topology 严格验证

- [ ] **CHECK-2.1**: `verify_qc_topology()` 在 ORCA/PySCF Recipe 中调用
  - 检查 `src/quantumvitas/execution/recipes.py`
  - `ORCARecipe.materialize()` 开头调用
  - `PySCFRecipe.materialize()` 开头调用

- [ ] **CHECK-2.2**: Relax 阻断 SCF 链
  - 测试: `test_qc_topo_verify_scf_relax_tddft_invalid` 必须通过
  - `scf → relax → tddft` 应抛出 `TopologyError`

- [ ] **CHECK-2.3**: QE 不被 QC verify 误伤
  - `QERecipe.materialize()` 不调用 `verify_qc_topology()`

---

## 3. Scoped Cleanup

- [ ] **CHECK-3.1**: Job 开始前清理覆盖的 relax steps
  - 检查 `src/quantumvitas/execution/executor.py`
  - 在 job 执行前调用 `clean_generated_structure()` for each relax step in job

- [ ] **CHECK-3.2**: 不全清
  - 只清理当前 job 覆盖的 relax steps 的 `current.json`
  - 不清理其他 jobs 的 relax artifacts

---

## 4. Missing Artifact Hard Error

- [ ] **CHECK-4.1**: `MissingArtifactError` 定义存在
  - 检查 `src/quantumvitas/core/exceptions.py`

- [ ] **CHECK-4.2**: 需要 effective structure 时检查 `current.json` 存在
  - 若依赖 relax step 的结构，必须检查 `get_generated_structure_path().exists()`
  - 不存在时抛出 `MissingArtifactError`

- [ ] **CHECK-4.3**: 错误信息清晰
  - 包含: step name, relax step ULID, 预期路径
  - 包含: 可能原因和修复建议

---

## 5. Canonicalize 入口唯一

- [ ] **CHECK-5.1**: QE parser 使用 `canonicalize_structure_in_place()`
  - 检查 `src/quantumvitas/calculation/geometry.py`
  - `structure_from_qe_geometry_snapshot()` 内部调用

- [ ] **CHECK-5.2**: ORCA parser 使用相同入口
  - 新增代码必须调用 `canonicalize_structure_in_place()`

- [ ] **CHECK-5.3**: PySCF parser 使用相同入口
  - 分子不需要 fractional coord 处理，但如需 canonicalize 必须用相同入口

- [ ] **CHECK-5.4**: 无第二套 JSON hash
  - SHA 只通过 `structure_fingerprint()` 计算
  - 不存在自定义的 structure hashing 逻辑

---

## 6. Relax 不产出电子态

- [ ] **CHECK-6.1**: Registry 中 relax types 的 `produces_charge_density=False`
  - `qe_relax`, `orca_relax`, `pyscf_relax` 都设置为 False

- [ ] **CHECK-6.2**: Registry 中 relax types 的 `is_structure_transform=True`
  - 必须标记为结构变换 step

---

## 7. Promote Dropdown/Selector 语义

- [ ] **CHECK-7.1**: `promote_relax_structure()` 要求 `step_selector` 参数
  - 不是 "promote latest"，必须明确指定 step

- [ ] **CHECK-7.2**: 验证 step 是 relax 类型
  - 检查 `is_structure_transform` 或 `step_type in relax_types`

- [ ] **CHECK-7.3**: 验证 `current.json` 存在
  - 不存在时返回清晰错误

---

## 8. 测试覆盖

- [ ] **CHECK-8.1**: Unit tests 全部通过
  ```bash
  pytest tests/unit/test_step_type_mapping.py -v
  pytest tests/unit/execution/test_qc_topology.py -v
  pytest tests/unit/execution/test_relax_artifacts.py -v
  ```

- [ ] **CHECK-8.2**: 新增功能有对应测试
  - 每个新函数至少一个 happy path 测试
  - 每个错误路径有对应测试

- [ ] **CHECK-8.3**: 真实引擎测试 (若本 PR 涉及)
  ```bash
  pytest tests/integration/test_qe_relax_real.py -v -m qe
  pytest tests/integration/test_orca_relax_real.py -v -m orca
  pytest tests/integration/test_pyscf_relax_real.py -v
  ```

---

## 9. 文件格式

- [ ] **CHECK-9.1**: `current.json` 格式正确
  - 包含 `__qv_meta__` 字段
  - 包含 `source_step_ulid`, `provenance`
  - pymatgen 可读取

- [ ] **CHECK-9.2**: 路径格式正确
  - `generated_structures/step_<ULID>/current.json`

---

## 10. 代码风格

- [ ] **CHECK-10.1**: 无 linter 错误
  ```bash
  ruff check src/
  ```

- [ ] **CHECK-10.2**: Import 正确
  - TYPE_CHECKING 用于类型提示的 circular import

- [ ] **CHECK-10.3**: Logging 使用 `logger.info()` 格式
  - 格式: `[MODULE_NAME] message`

---

## Quick Grep Commands

```bash
# 检查 GEN step 唯一性
grep -n "RELAX_STEP_TYPES" src/quantumvitas/engine/qc_engine_base.py

# 检查 canonicalize 调用
grep -rn "canonicalize_structure_in_place" src/

# 检查 produces_charge_density
grep -n "produces_charge_density" src/quantumvitas/workflow/registry.py

# 检查 is_structure_transform
grep -n "is_structure_transform" src/quantumvitas/workflow/registry.py

# 检查 verify_qc_topology 调用
grep -n "verify_qc_topology" src/quantumvitas/execution/recipes.py
```

---

## Sign-off

每个 PR 完成后，需要在 PR description 中添加:

```
## RELAX Checklist
- [x] CHECK-1.x: GEN Step 唯一性 ✅
- [x] CHECK-2.x: QC Topology ✅
- [x] CHECK-3.x: Scoped Cleanup ✅
- [x] CHECK-4.x: Missing Artifact ✅
- [x] CHECK-5.x: Canonicalize 唯一 ✅
- [x] CHECK-6.x: No Electronic State ✅
- [x] CHECK-7.x: Promote Selector ✅
- [x] CHECK-8.x: Test Coverage ✅
- [x] CHECK-9.x: File Format ✅
- [x] CHECK-10.x: Code Style ✅
```

