# Online/Project Pipeline Unification - Final Report

## 一、已知事实与硬证据

### 共享 Pipeline 已正确生成 display_atoms + bonds

**证据日志：**
```
[qmatsuite.api] [PIPELINE] display_atoms: count=31
[PIPELINE] bonds_len=30 maxBondIndex=30
```

**结论：** project / online 的 canonical → display → bonds 逻辑在 `qmatsuite.api._build_structure_vis_payload` 中完全一致。

### 旧问题根源（已修复）

**问题 1：Online 存在第二套 pipeline**
- **位置：** `src/qmatsuite/daemon/server.py:1756`（已删除）
- **证据：** `[__main__] [viewer] kind=online ... inAtoms=12 outAtoms=12 supercell=(5,5,5)`
- **根因：** 旧 viewer 日志显示错误的 outAtoms 和 supercell
- **修复：** 删除旧日志，只使用共享 pipeline 的日志

**问题 2：Payload Contract 歧义**
- **旧 contract：** `atoms` 只包含 canonical atoms (12)，`boundary_atoms` 单独列出 (19)
- **问题：** bonds 的 index 指向 display_atoms (31)，但 `atoms` 只有 12 个
- **修复：** 新 contract 要求 `atoms` 包含 ALL display atoms (31)

**问题 3：Bond Schema 不一致**
- **Online：** 使用 `atom1`/`atom2`
- **Project：** 使用 `idx1`/`idx2`
- **修复：** 统一使用 `idx1`/`idx2`

## 二、新的 Payload Contract（强制）

### Contract 定义

```python
payload = {
    "atoms": [...],           # ALL display atoms (canonical + supercell + boundary)
    "boundary_atoms": [...],  # UI metadata only (subset of atoms with is_boundary=True)
    "bonds": [                # idx1/idx2 reference atoms[0..len(atoms)-1]
        {"idx1": int, "idx2": int, "distance": float, ...}
    ],
    ...
}
```

### 硬断言（后端 + 前端）

**后端断言位置：** `src/qmatsuite/api.py:2038-2045, 2137-2147`
```python
# HARD ASSERT: bonds must only reference atoms array
if bonds and max_bond_idx >= atoms_len:
    raise ValueError(f"INVALID PAYLOAD: maxBondIndex={max_bond_idx} >= atoms_len={atoms_len}")
```

**前端断言位置：** `gui/src/App.tsx:959-973`
```typescript
// HARD ASSERT: Frontend payload contract validation
if (bondsLen > 0) {
  const maxBondIndex = Math.max(...model.bonds.map(b => Math.max(b.i, b.j)));
  if (maxBondIndex >= atomsLen) {
    throw new Error(`INVALID FRONTEND PAYLOAD: maxBondIndex=${maxBondIndex} >= atoms_len=${atomsLen}`);
  }
}
```

## 三、彻底消灭 Online 第二套 Pipeline

### 删除的旧代码

**文件：** `src/qmatsuite/daemon/server.py`
- **行 1756：** 删除旧 viewer 日志 `[viewer] kind=online ... inAtoms=... outAtoms=...`
- **原因：** 共享 pipeline 已提供正确的 `[viz]` 日志

### Online Handler 清理

**文件：** `src/qmatsuite/daemon/server.py:1649-1750`
- **唯一调用：** `QMSService._build_structure_vis_payload(...)`
- **禁止：** 自己 build_display_atoms / build_bonds
- **参数来源：** 完全从 GUI payload 获取（`supercell`, `repeat_boundary`, `display_mode`）
- **默认值：** `supercell=[1,1,1]`（不允许 server-side magic default）

## 四、Reload 语义（Refresh）

### 行为定义

**策略 C：** 点击同一结构 = 显式 refresh = 必须重新触发 RPC

### 实现

**文件：** `gui/src/App.tsx:1505-1564, 1584-1670`
- **移除：** `needsLoad` 检查（不再跳过相同选择）
- **机制：** Load token 确保只有最新响应生效
- **超时：** 10 秒超时，显示错误面板
- **清理：** finally 确保 loading 状态被清除

### 为什么不再出现无限转圈

1. **Load token 机制：** 新请求会 supersede 旧请求
2. **超时保护：** 10 秒后强制显示错误
3. **Finally 清理：** 所有路径都清除 loading 状态
4. **无 skip 逻辑：** 每次点击都触发 RPC

## 五、Supercell 参数来源

**唯一来源：** GUI state (`viewerSettings.supercell`)
- **默认值：** `[1, 1, 1]`
- **传递路径：** GUI → RPC payload → `DisplayModeParams`
- **禁止：** Server-side magic default（例如 5×5×5）

**验证：** `src/qmatsuite/daemon/server.py:1427`
```python
supercell = tuple(payload.get("supercell", [1, 1, 1]))  # 从 payload 获取，默认 [1,1,1]
```

## 六、测试体系

### D1. 在线集成测试

**文件：** `tests/integration/test_optimade_online.py`
- **标记：** `@pytest.mark.integration`, `@pytest.mark.network`
- **目的：** 验证 OPTIMADE 生态健康
- **特点：** 真实网络请求，失败 = CI 红（这是好事）

### D2. 离线确定性测试

**文件：** `tests/unit/test_optimade_offline.py`
- **数据：** `tests/data/optimade/*.json`（保存的 OPTIMADE raw data）
- **目的：** 验证 pipeline 逻辑，不依赖网络
- **特点：** 必须稳定通过

### Payload Contract 测试

**文件：** `tests/unit/test_online_project_payload_contract.py`
- **验证：** Online vs Project payload 完全一致
- **断言：** `atoms_len`, `bonds_len`, `maxBondIndex`, bond schema

## 七、Payload 示例

### 修复后的 Payload（repeat_boundary=True）

```json
{
  "atoms": [
    // 12 canonical atoms
    {"index": 0, "element": "Nb", "cart_coords": [...], ...},
    ...
    {"index": 11, "element": "Se", ...},
    // 19 boundary atoms (is_boundary=true)
    {"index": 12, "element": "Nb", "is_boundary": true, ...},
    ...
    {"index": 30, "element": "Se", "is_boundary": true, ...}
  ],
  "boundary_atoms": [
    // UI metadata (subset of atoms with is_boundary=true)
    {"index": 12, "element": "Nb", "is_boundary": true, ...},
    ...
  ],
  "bonds": [
    {"idx1": 0, "idx2": 1, "distance": 2.5, ...},  // 引用 atoms[0..30]
    ...
    {"idx1": 28, "idx2": 30, "distance": 2.6, ...}  // maxBondIndex=30 < atoms_len=31 ✓
  ],
  "n_atoms": 31,  // ALL display atoms
  "n_boundary_atoms": 19,  // UI metadata count
  "n_bonds": 30
}
```

### 为什么现在逻辑上不可能再出现

1. **Online 第二次转圈：**
   - ❌ 旧：`needsLoad` 跳过相同选择，但进入 loading 状态
   - ✅ 新：每次点击都触发 RPC，load token 处理并发，超时保护

2. **Online bonds 消失：**
   - ❌ 旧：`atoms` 只有 12 个，bonds 引用 0-30，越界被丢弃
   - ✅ 新：`atoms` 包含 31 个，bonds 引用 0-30，硬断言确保有效

3. **参数漂移（5×5×5）：**
   - ❌ 旧：Server-side magic default
   - ✅ 新：唯一来源是 GUI state，默认 [1,1,1]

## 八、文件变更清单

### 后端

1. **`src/qmatsuite/api.py`**
   - 行 1980-1996：修复 `atoms` 包含所有 display atoms
   - 行 2038-2045：添加 bond index 硬断言
   - 行 2137-2147：添加最终 payload contract 验证
   - 行 2043-2063：添加证据日志

2. **`src/qmatsuite/daemon/server.py`**
   - 行 1679-1713：修复 bond schema（idx1/idx2），添加硬断言
   - 行 1756：删除旧 viewer 日志
   - 行 1658-1678：确保 atoms_data 包含所有 display atoms

### 前端

3. **`gui/src/App.tsx`**
   - 行 1505-1564：修复 project reload 语义（移除 needsLoad）
   - 行 1584-1670：修复 online reload 语义（移除 needsLoad）
   - 行 959-973：添加前端 payload contract 硬断言
   - 行 974-996：添加前端证据日志

4. **`gui/src/components/panels/DebugPanel.tsx`**
   - 行 20-46：改进日志过滤，保留关键 pipeline 日志

### 测试

5. **`tests/unit/test_online_project_payload_contract.py`**（新建）
   - Payload contract 一致性测试

6. **`tests/integration/test_optimade_online.py`**（新建）
   - OPTIMADE 在线集成测试

7. **`tests/unit/test_optimade_offline.py`**（新建）
   - OPTIMADE 离线确定性测试

8. **`tests/data/optimade/README.md`**（新建）
   - 测试数据目录说明

## 九、验收标准

✅ **Payload Contract：**
- `atoms` 包含所有 display atoms（31）
- `bonds.idx1/idx2` 只引用 `atoms[0..30]`
- 硬断言在前后端都生效

✅ **Pipeline 统一：**
- Online 只调用共享 `_build_structure_vis_payload`
- 无第二套 pipeline
- 无旧 viewer 日志

✅ **Reload 语义：**
- 点击同一结构 = refresh = 触发 RPC
- Load token 处理并发
- 超时保护（10s）

✅ **测试：**
- `pytest tests/unit/test_online_project_payload_contract.py` 全绿
- `pytest tests/unit/test_optimade_offline.py` 全绿
- `pytest tests/integration/test_optimade_online.py` 在网络可用时通过

## 十、预期日志输出

修复后，日志应显示：

```
[PIPELINE] PAYLOAD_EVIDENCE kind=online atoms_len=31 boundary_atoms_len=19 bonds_len=30 maxBondIndex=30 maxBondIndex_valid=True
[PIPELINE] PAYLOAD_EVIDENCE firstBondKeys=['idx1', 'idx2', 'coord1', 'coord2', 'distance']
[ONLINE] PAYLOAD_EVIDENCE candidate_id=xxx atoms_len=31 boundary_atoms_len=19 bonds_len=30 maxBondIndex=30 maxBondIndex_valid=True
[viz] kind=online mode=primitive supercell=1x1x1 repeat=1 atoms=31 bonds=30 ...
[FRONTEND] PAYLOAD_EVIDENCE selectionKey=online:session:candidate atoms.length=31 bonds.length=30 maxBondIndex=30 maxBondIndex_valid=true
```

**关键点：**
- `atoms_len=31`（不是 12）
- `maxBondIndex=30 < atoms_len=31` ✓
- `supercell=1x1x1`（不是 5×5×5）
- Bond schema 使用 `idx1`/`idx2`

