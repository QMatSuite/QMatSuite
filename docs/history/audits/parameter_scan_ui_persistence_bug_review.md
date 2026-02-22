# Parameter Scan UI 保存数组值丢失 - 深度审查报告

**审查日期**: 2026-01-17  
**审查类型**: READ-ONLY (无代码修改)  
**目标**: 找出为什么 UI 输入 `[330,340,350]` / `[40,50,60]` 最终落盘变成 `scan003.values=[]`、`scan004.values=[40]`，以及为何旧 scan 定义不被删除。

---

## 1) 复现步骤与落盘事实

### 复现步骤
1. 在同一个 step (scf) 上：
   - `ecutrho` 开 scan，输入 `[330,340,350]`
   - `ecutwfc` 开 scan，输入 `[40,50,60]`
2. 点击 Apply
3. 打开落盘文件检查

### 预期 vs 实际
**预期**:
```yaml
parameters:
  SYSTEM:
    ecutrho: "@scan:scan003"
    ecutwfc: "@scan:scan004"
parameter_scan:
  scan003:
    values: [330, 340, 350]
  scan004:
    values: [40, 50, 60]
```

**实际** (根据用户报告):
```yaml
parameters:
  SYSTEM:
    ecutrho: "@scan:scan003"
    ecutwfc: "@scan:scan004"
parameter_scan:
  scan001:  # 旧定义残留
    values: [...]
  scan002:  # 旧定义残留
    values: [...]
  scan003:
    values: []  # ❌ 丢失
  scan004:
    values: [40]  # ❌ 只保留第一个值
```

---

## 2) 端到端链路：UI state → RPC payload → backend apply → response → UI reset

### A. ScanValuesEditor 在输入框变化时的行为

**文件**: `gui/src/components/step_parameters/ScanValuesEditor.tsx`

**关键代码** (line 26-36):
```typescript
useEffect(() => {
  try {
    const jsonStr = JSON.stringify(values);
    setInputValue(jsonStr);
    setError(null);
  } catch (e) {
    setInputValue('');
    setError('Invalid values');
  }
}, [values]);
```

**分析**:
- ✅ **正常行为**: 当用户输入 `[330,340,350]` 时，`handleChange` (line 38-86) 会调用 `onChange(parsed)` (line 80)，其中 `parsed = [330, 340, 350]`
- ⚠️ **潜在问题**: `useEffect` 会在 `values` prop 变化时重置 `inputValue`。如果父组件在用户输入过程中更新了 `values` prop，会导致输入被覆盖

**证据链**:
- `handleChange` (line 38) 接收用户输入字符串
- 解析 JSON (line 49): `parsed = JSON.parse(newInput)`
- 验证数组 (line 60-80): 检查是否为有效数组
- 调用 `onChange(parsed)` (line 80): **这里应该传递完整数组**

**结论**: `ScanValuesEditor` 本身逻辑正确，问题不在这个组件。

---

### B. StepDetailPanel.handleScanValuesChange 收到的 values

**文件**: `gui/src/components/panels/StepDetailPanel.tsx`

**关键代码** (line 920-927):
```typescript
const handleScanValuesChange = useCallback((scanId: string, values: unknown[]) => {
  setEditedParameterScan(prev => {
    const updated = JSON.parse(JSON.stringify(prev));
    updated[scanId] = { values };
    return updated;
  });
  setHasChanges(true);
}, []);
```

**调用路径** (line 347):
```typescript
<ScanValuesEditor
  values={scanValues}
  onChange={(values) => onScanValuesChange(scanId, values)}
  disabled={false}
/>
```

**分析**:
- ✅ **逻辑正确**: `handleScanValuesChange` 直接使用传入的 `values` 数组，没有截断
- ✅ **状态更新**: 使用 `setEditedParameterScan` 更新状态，应该能正确保存数组

**证据链**:
- `ScanValuesEditor.onChange` → `onScanValuesChange(scanId, values)` (line 347)
- `onScanValuesChange` = `handleScanValuesChange` (从 props 传入，line 1433)
- `handleScanValuesChange` 更新 `editedParameterScan[scanId].values = values` (line 923)

**结论**: 如果 `ScanValuesEditor` 传递了完整数组，`handleScanValuesChange` 应该能正确接收并保存。

---

### C. Apply 时的 payload 结构

**文件**: `gui/src/components/panels/StepDetailPanel.tsx`

**关键代码** (line 755-761):
```typescript
const response = await window.qms.request<StepDetail>('update_step_params', {
  project_root: normalizedProjectRoot,
  calculation: calculationSelector,
  step: stepSelector,
  parameters: paramUpdates,
  parameter_scan: Object.keys(editedParameterScan).length > 0 ? editedParameterScan : undefined,
});
```

**分析**:
- ✅ **发送完整对象**: `parameter_scan` 字段发送的是完整的 `editedParameterScan` 对象
- ⚠️ **条件发送**: 只有当 `Object.keys(editedParameterScan).length > 0` 时才发送，否则为 `undefined`

**关键问题**: 
- 如果 `editedParameterScan` 在 Apply 时被重置或覆盖，payload 会发送错误的数据
- **需要验证**: Apply 时 `editedParameterScan` 的实际内容

**证据链**:
- `handleSaveParams` 构建 payload (line 755-761)
- `parameter_scan: editedParameterScan` (如果非空)
- 发送到 backend: `window.qms.request('update_step_params', payload)`

**预期 payload 结构** (如果 `editedParameterScan` 正确):
```json
{
  "project_root": "...",
  "calculation": "...",
  "step": "...",
  "parameters": {
    "SYSTEM": {
      "ecutrho": "@scan:scan003",
      "ecutwfc": "@scan:scan004"
    }
  },
  "parameter_scan": {
    "scan003": {
      "values": [330, 340, 350]
    },
    "scan004": {
      "values": [40, 50, 60]
    }
  }
}
```

---

### D. Backend 收到后的处理与返回

**文件**: `src/qmatsuite/api.py`

**关键代码** (line 4599-4601):
```python
# Update parameter_scan if provided
if parameter_scan is not None:
    step_doc.apply_patch({"parameter_scan": parameter_scan})
```

**关键代码** (line 4608-4614):
```python
# Return the updated step detail (pass cached index/config to avoid rebuilding)
result = QMSService.get_step_detail(
    project_root=project_root,
    calculation_ulid=calculation_ulid,
    step_selector=step_selector,
    index=index,
    config=config,
)
```

**分析**:
- ⚠️ **Patch Merge 语义**: `apply_patch` 是 **merge** 操作，不是 full replace
  - 如果 `parameter_scan` 包含 `{"scan003": {"values": [330, 340, 350]}}`
  - 只会更新/添加 `scan003`，**不会删除** `scan001` 和 `scan002`
- ✅ **返回完整数据**: `get_step_detail` 会读取整个 `step.yaml`，包括所有 `parameter_scan` 定义 (line 4484-4485)

**apply_patch 行为** (参考 `src/qmatsuite/core/yamldoc.py` line 383-396):
```python
def _apply_patch_recursive(self, patch: dict, current_path: list[str]) -> None:
    for key, value in patch.items():
        path = current_path + [key]
        if value is None:
            self.delete(path)
        elif isinstance(value, dict):
            # Recurse into nested dict
            self._apply_patch_recursive(value, path)
        else:
            # Set leaf value
            self.set(path, value)
```

**关键发现**:
- `apply_patch({"parameter_scan": {"scan003": {"values": [330, 340, 350]}}})` 会：
  1. 递归到 `parameter_scan.scan003`
  2. 设置 `parameter_scan.scan003.values = [330, 340, 350]`
  3. **不会删除** `parameter_scan.scan001` 和 `parameter_scan.scan002`

**证据链**:
- Backend 接收 `parameter_scan` payload
- 调用 `step_doc.apply_patch({"parameter_scan": parameter_scan})` (line 4601)
- `apply_patch` 是 merge 语义，只更新/添加，不删除未提及的键
- 保存后返回 `get_step_detail()`，包含所有 `parameter_scan` 定义

**结论**: Backend 的 merge 语义导致旧 scan 定义不会被删除（这是设计，不是 bug）。但数组值丢失的问题不在 backend。

---

### E. Apply 成功后的 reset 逻辑

**文件**: `gui/src/components/panels/StepDetailPanel.tsx`

**关键代码** (line 763-768):
```typescript
if (response.ok && response.data) {
  setStepDetail(response.data);
  // Initialize edited params from current values (include ALL parameters, not just editable ones)
  setEditedParams(JSON.parse(JSON.stringify(response.data.parameters)));
  // Initialize edited parameter_scan
  setEditedParameterScan(JSON.parse(JSON.stringify(response.data.parameter_scan || {})));
  setHasChanges(false);
  setIsEditing(false);
  onParametersUpdated?.();
}
```

**分析**:
- ⚠️ **潜在覆盖**: 如果 `response.data.parameter_scan` 不完整或错误，会覆盖本地正确的 `editedParameterScan`
- ✅ **逻辑正确**: 如果 backend 返回正确的数据，reset 是合理的

**关键问题**: 
- Backend 返回的 `response.data.parameter_scan` 是什么？
- 如果 backend 正确返回了完整数组，但 UI 在某个时刻又重置了，会导致丢失

**证据链**:
- Apply 成功后，`response.data` 来自 `get_step_detail()` (line 4608)
- `get_step_detail()` 从 YAML 读取 `parameter_scan` (line 4484-4485)
- 如果 YAML 中 `parameter_scan.scan003.values = []`，返回的就是 `[]`
- UI reset 会用这个空数组覆盖本地状态

**结论**: 如果 backend 返回的数据是正确的，reset 不会导致丢失。但如果 backend 返回的数据已经是错误的（空数组或单值），reset 会"确认"这个错误。

---

## 3) 高优先级怀疑点：handleScanToggle 二次触发覆盖

### 关键代码分析

**文件**: `gui/src/components/panels/StepDetailPanel.tsx`

**handleScanToggle** (line 829-917):
```typescript
const handleScanToggle = useCallback((namelist: string, paramName: string, enabled: boolean) => {
  if (!stepDetail) return;
  
  const currentValue = (isEditing ? editedParams : stepDetail.parameters)[namelist]?.[paramName];
  const currentScanId = isScanRef(currentValue) ? getScanId(currentValue) : null;
  
  if (enabled) {
    // ... 生成 scanId ...
    
    // Create or update scan definition
    setEditedParameterScan(prev => {
      const updated = JSON.parse(JSON.stringify(prev));
      if (!updated[scanId]) {  // ⚠️ 关键条件
        // Initialize with current value if it exists and is a leaf value
        const initialValue = currentValue;
        const initialValues = (initialValue !== null && initialValue !== undefined && 
          (typeof initialValue === 'string' || typeof initialValue === 'number' || typeof initialValue === 'boolean' || 
           (Array.isArray(initialValue) && initialValue.every(item => 
             item === null || typeof item === 'string' || typeof item === 'number' || typeof item === 'boolean'
           ))))
          ? [initialValue]
          : [];
        updated[scanId] = { values: initialValues };
      }
      return updated;
    });
  }
  // ...
}, [stepDetail, editedParams, editedParameterScan, isEditing]);
```

**关键发现**:
- ✅ **保护机制**: `if (!updated[scanId])` 确保只在 scan 定义不存在时才初始化
- ⚠️ **初始化逻辑**: 如果 `currentValue` 是标量，初始化为 `[currentValue]`；否则初始化为 `[]`

**isScanned 判断** (ActiveParametersPanel.tsx line 291):
```typescript
const isScanned = isScanRef(param.value);
```

**param.value 来源** (ActiveParametersPanel.tsx line 250-260):
```typescript
const params = useMemo(() => {
  // ...
  const paramValue = isEditing 
    ? editedParams[namelist]?.[param.name]
    : stepDetail.parameters[namelist]?.[param.name];
  // ...
}, [isEditing, editedParams, stepDetail.parameters, ...]);
```

**关键问题**: 
- `isScanned` 的判断基于 `param.value`，而 `param.value` 来自 `editedParams` 或 `stepDetail.parameters`
- 如果 `editedParams` 中参数值是 `"@scan:scan003"`，`isScanned = true`
- 但如果 `editedParams` 和 `stepDetail.parameters` 不同步，可能导致误判

**调用路径** (ActiveParametersPanel.tsx line 320-325):
```typescript
<ParameterModeSelector
  mode={currentMode}
  onChange={(mode) => {
    if (mode === 'scan' && !isScanned) {
      onScanToggle(namelist, param.name, true);  // ⚠️ 可能被多次调用
    } else if (mode === 'value' && isScanned) {
      onScanToggle(namelist, param.name, false);
    }
  }}
/>
```

**潜在触发场景**:
1. **组件重新渲染**: 如果 `editedParams` 或 `stepDetail` 变化，`ActiveParametersPanel` 会重新渲染
2. **currentMode 计算**: `currentMode = isScanned ? 'scan' : 'value'` (line 294)
3. **Mode 不匹配**: 如果 `isScanned` 判断错误（例如 `editedParams` 中已经是 token，但 `isScanned` 判断为 false），`onChange('scan')` 会被调用
4. **重复初始化**: `handleScanToggle(..., true)` 被调用，如果 `!updated[scanId]` 为 true，会初始化 `values = [currentValue]`

**证据链**:
- `ScanValuesEditor` 的 `useEffect` (line 27-36) 会在 `values` prop 变化时重置输入框
- 如果 `handleScanToggle` 在用户输入数组后又被调用，会重置 `editedParameterScan[scanId].values = [currentValue]`
- `ScanValuesEditor` 的 `useEffect` 检测到 `values` 变化，会重置 `inputValue`，导致用户输入丢失

**结论**: **这是最可能的根因**。`handleScanToggle` 可能在用户输入数组后被二次触发，导致 `values` 被重置为 `[currentValue]`。

---

## 4) Orphan scans 为何不删除：语义 vs Bug

### 当前实现：Patch Merge 语义

**文件**: `src/qmatsuite/api.py` (line 4600-4601)

```python
if parameter_scan is not None:
    step_doc.apply_patch({"parameter_scan": parameter_scan})
```

**行为**:
- `apply_patch` 是 **merge** 操作
- 只更新/添加 payload 中提到的 scan 定义
- **不会删除** payload 中未提及的 scan 定义

**证据**:
- `_apply_patch_recursive` (yamldoc.py line 383-396) 只处理 patch 中存在的键
- 如果 `parameter_scan` payload 是 `{"scan003": {...}, "scan004": {...}}`，只会更新这两个，不会删除 `scan001` 和 `scan002`

### 对比：K_POINTS 的处理方式

**文件**: `src/qmatsuite/api.py` (line 4767)

```python
step_doc.set(["cards", "K_POINTS"], card_data)
```

**行为**:
- `set()` 是 **full replace** 操作
- 直接替换整个 `cards.K_POINTS` 值
- 如果 `card_data` 是新的完整数据，旧数据会被完全替换

**关键差异**:
- K_POINTS 使用 `set()` → full replace
- parameter_scan 使用 `apply_patch()` → merge

### 建议

**如果目标是"做对就行、完全不要兼容"**:

1. **Option 1: Full Replace** (推荐)
   - 修改 backend 使用 `set()` 而不是 `apply_patch()`
   - UI 必须发送完整的 `parameter_scan` 对象（包含所有需要保留的 scan 定义）
   - 优点: 语义清晰，orphan scans 会被自动删除
   - 缺点: UI 必须维护完整的 `parameter_scan` 状态

2. **Option 2: Explicit Delete** (当前 merge + 显式删除)
   - 保持 `apply_patch()`，但 UI 发送 `null` 来标记删除
   - 例如: `{"scan001": null, "scan003": {...}}` 会删除 `scan001`
   - 优点: 保持增量更新语义
   - 缺点: UI 需要跟踪哪些 scan 需要删除

3. **Option 3: Allow Orphan + Warning** (当前行为)
   - 保持当前 merge 语义
   - Backend 验证时发出警告（已实现）
   - UI 显示警告，但不阻止保存
   - 优点: 最简单，不需要修改
   - 缺点: 用户需要手动清理 orphan scans

**推荐**: Option 1 (Full Replace)，因为：
- 语义最清晰
- 与 K_POINTS 的处理方式一致
- 自动处理 orphan scans
- UI 已经维护了完整的 `editedParameterScan` 状态

---

## 5) 参考 K_POINTS：成功的复杂结构更新

### K_POINTS 的更新流程

**UI 组件**: `CommonCardKPoints.tsx`

**关键代码** (line 295-334):
```typescript
const handleApply = useCallback(async () => {
  // Build view model from canonical source (rawBodyText)
  const newViewModel: KPointsViewModel = {
    raw: fullRawText,
    mode: localMode,
    canonical_raw: fullRawText,
  };
  
  // ... 构建完整 viewModel ...
  
  await onUpdate(newViewModel);
}, [fullRawText, localMode, localAutomatic, localPoints, useRawEdit, onUpdate]);
```

**Backend 处理** (api.py line 4767):
```python
step_doc.set(["cards", "K_POINTS"], card_data)
```

**关键差异**:
- ✅ **K_POINTS**: 使用 `set()` → full replace，发送完整数据
- ⚠️ **parameter_scan**: 使用 `apply_patch()` → merge，可能只发送部分数据

**K_POINTS 成功的原因**:
1. **单一真实来源**: `rawBodyText` 是 canonical source
2. **Full Replace**: `set()` 确保旧数据被完全替换
3. **完整数据**: UI 总是发送完整的 `viewModel`，不是增量

**parameter_scan 失败的原因**:
1. **Merge 语义**: `apply_patch()` 只更新部分数据
2. **状态不同步**: `editedParameterScan` 可能在某个时刻被重置
3. **初始化覆盖**: `handleScanToggle` 可能在用户输入后重置 `values`

---

## 6) 最终根因分析

### 主根因：handleScanToggle 二次触发覆盖 (高置信度)

**证据链**:
1. **初始化逻辑** (StepDetailPanel.tsx line 855-870):
   - `if (!updated[scanId])` 时，初始化 `values = [currentValue]` 或 `[]`
   - 如果 `currentValue` 是标量（如 `40`），初始化为 `[40]`
   - 如果 `currentValue` 是 `undefined` 或 token，初始化为 `[]`

2. **触发场景**:
   - 用户开启 scan → `handleScanToggle(..., true)` → 初始化 `values = [currentValue]`
   - 用户输入数组 `[40, 50, 60]` → `handleScanValuesChange(scanId, [40, 50, 60])` → 更新 `editedParameterScan[scanId].values = [40, 50, 60]`
   - **某个时刻** `handleScanToggle(..., true)` 又被调用 → 如果 `!updated[scanId]` 为 false，不会覆盖；但如果状态被重置，`updated[scanId]` 可能不存在，导致重新初始化

3. **状态判断问题**:
   - `isScanned` 基于 `param.value`，而 `param.value` 来自 `editedParams` 或 `stepDetail.parameters`
   - 如果 `editedParams` 和 `stepDetail.parameters` 不同步，`isScanned` 可能误判
   - 如果 `isScanned = false` 但 `editedParams` 中已经是 token，`onChange('scan')` 会被调用，触发 `handleScanToggle(..., true)`

4. **ScanValuesEditor 的 useEffect**:
   - 当 `values` prop 从 `[40, 50, 60]` 变为 `[40]` 时，`useEffect` 会重置 `inputValue`
   - 用户输入丢失

**最可能的场景**:
1. 用户开启 `ecutwfc` scan → `handleScanToggle` 初始化 `values = [40]` (假设 `currentValue = 40`)
2. 用户输入 `[40, 50, 60]` → `handleScanValuesChange` 更新为 `[40, 50, 60]`
3. **某个 rerender** 导致以下情况之一：
   - `isScanned` 误判为 `false`（例如 `editedParams` 被重置或不同步）
   - `editedParameterScan` 被重置（例如 `stepDetail` 变化触发 useEffect）
   - `ScanValuesEditor` 的 `values` prop 从 `editedParameterScan` 变为 `stepDetail.parameter_scan`（如果 `effectiveParameterScan` 计算错误）
4. `ParameterModeSelector` 检测到 `currentMode !== 'scan'`，调用 `onChange('scan')`
5. `handleScanToggle(..., true)` 被调用
6. 如果此时 `editedParameterScan[scanId]` 不存在（例如状态被重置），会重新初始化 `values = [40]` 或 `[]`
7. `ScanValuesEditor` 的 `useEffect` 检测到 `values` 变化，重置 `inputValue = "[40]"` 或 `"[]"`
8. 用户输入丢失

**关键发现 - effectiveParameterScan 计算** (ActiveParametersPanel.tsx line 336-338):
```typescript
const effectiveParameterScan = isEditing && editedParameterScan 
  ? editedParameterScan 
  : stepDetail.parameter_scan;
```

**问题分析**:
- 如果 `isEditing = true` 且 `editedParameterScan = {}`（空对象），条件 `isEditing && editedParameterScan` 为 `true`（空对象是 truthy）
- 会使用 `editedParameterScan = {}`，导致 `scanDef = undefined`，`scanValues = []`
- `ScanValuesEditor` 收到 `values = []`，`useEffect` 重置 `inputValue = "[]"`
- **用户输入丢失**

**触发场景**:
- `editedParameterScan` 被重置为 `{}`（例如 `setEditedParameterScan({})`）
- 或 `editedParameterScan` 初始化时是 `{}`，但用户还没有添加任何 scan 定义
- `effectiveParameterScan` 使用空的 `editedParameterScan`，导致 `scanDef` 不存在

**关键发现 - editedParameterScan 初始化** (StepDetailPanel.tsx line 175):
```typescript
const [editedParameterScan, setEditedParameterScan] = useState<Record<string, { values: unknown[] }>>({});
```
- 初始状态是空对象 `{}`
- 当 `stepDetail` 加载时，会从 `response.data.parameter_scan` 初始化 (line 373)
- 但如果 `response.data.parameter_scan` 是 `undefined` 或 `{}`，`editedParameterScan` 会保持为空
- 如果用户在此时开启 scan，`effectiveParameterScan` 会使用空的 `editedParameterScan`，导致 `scanDef` 不存在

**验证方法** (需要断点/日志):
- 在 `handleScanToggle` 入口添加日志，记录调用次数、`enabled` 值、`currentValue`、`scanId`、`editedParameterScan[scanId]` 是否存在
- 在 `handleScanValuesChange` 入口添加日志，记录 `scanId`、`values` 数组长度和内容
- 在 `ParameterModeSelector.onChange` 添加日志，记录 `mode` 变化和 `isScanned` 值
- 在 Apply 时记录 `editedParameterScan` 的完整内容

---

### 备选根因 1：ScanValuesEditor useEffect 覆盖 (中置信度)

**证据**:
- `ScanValuesEditor` 的 `useEffect` (line 27-36) 会在 `values` prop 变化时重置 `inputValue`
- 如果父组件在用户输入过程中更新了 `values` prop，会导致输入被覆盖

**场景**:
- 用户正在输入 `[330, 340, 350]`（输入框显示 `"[330, 340, 350"`，还未完成）
- 父组件更新 `values` prop（例如从 `[]` 变为 `[330]`）
- `useEffect` 检测到变化，重置 `inputValue = "[330]"`
- 用户输入丢失

**验证方法**:
- 在 `ScanValuesEditor` 的 `useEffect` 添加日志，记录 `values` prop 的变化
- 检查是否有其他地方在用户输入时更新 `values` prop

---

### 备选根因 2：Backend apply_patch merge 导致部分更新 (低置信度)

**证据**:
- Backend 使用 `apply_patch()` 进行 merge
- 如果 UI 发送的 payload 中 `parameter_scan` 不完整，merge 后可能丢失数据

**场景**:
- UI 发送 `{"scan003": {"values": [330, 340, 350]}}`
- Backend merge 时，如果 `scan003.values` 已经是 `[]`，merge 可能不会正确更新
- 但实际上 `apply_patch` 应该能正确更新嵌套值

**验证方法**:
- 在 backend `apply_patch` 前后记录 `step_doc.parameter_scan` 的内容
- 检查 merge 是否正确更新了嵌套的 `values` 数组

**结论**: 这个可能性较低，因为 `apply_patch` 的 merge 逻辑应该能正确处理嵌套字典。

---

## 7) 建议的修复方向（不实现，只建议）

### 修复 1：防止 handleScanToggle 二次触发

**方案 A**: 在 `handleScanToggle` 中添加保护
```typescript
if (enabled) {
  // 检查 scan 是否已经存在且已有 values
  if (updated[scanId] && updated[scanId].values && updated[scanId].values.length > 0) {
    // 已经初始化过，不要覆盖
    return;
  }
  // ... 初始化逻辑
}
```

**方案 B**: 修复 `isScanned` 判断逻辑
- 确保 `isScanned` 的判断基于正确的数据源
- 如果 `isEditing`，使用 `editedParams`；否则使用 `stepDetail.parameters`
- 确保 `editedParams` 和 `stepDetail.parameters` 保持同步

### 修复 2：ScanValuesEditor 防覆盖

**方案**: 在 `useEffect` 中添加保护
```typescript
useEffect(() => {
  // 如果用户正在输入（inputValue 与 values 不同步），不要重置
  const currentParsed = tryParseInput(inputValue);
  if (currentParsed && JSON.stringify(currentParsed) !== JSON.stringify(values)) {
    // 用户正在输入，不要覆盖
    return;
  }
  // ... 正常重置逻辑
}, [values, inputValue]);
```

### 修复 3：Backend Full Replace

**方案**: 修改 backend 使用 `set()` 而不是 `apply_patch()`
```python
# 当前 (merge):
step_doc.apply_patch({"parameter_scan": parameter_scan})

# 改为 (full replace):
if parameter_scan is not None:
    step_doc.set(["parameter_scan"], parameter_scan)
```

**要求**: UI 必须发送完整的 `parameter_scan` 对象（包含所有需要保留的 scan 定义）

---

## 8) 验证清单（需要断点/日志）

### 必须验证的点

1. **handleScanToggle 调用次数**
   - 在 `handleScanToggle` 入口添加日志
   - 记录：调用时间、`enabled` 值、`currentValue`、`scanId`、`editedParameterScan[scanId]` 是否存在

2. **handleScanValuesChange 调用**
   - 在 `handleScanValuesChange` 入口添加日志
   - 记录：`scanId`、`values` 数组长度和内容

3. **Apply payload**
   - 在 `handleSaveParams` 中，发送前记录 `editedParameterScan` 的完整内容
   - 验证是否包含完整的数组值

4. **Backend 接收**
   - 在 `update_step_params` 入口记录 `parameter_scan` payload
   - 在 `apply_patch` 前后记录 `step_doc.parameter_scan` 的内容

5. **Backend 返回**
   - 在 `get_step_detail` 返回前记录 `result["parameter_scan"]` 的内容
   - 验证返回的数据是否正确

6. **UI reset**
   - 在 `setEditedParameterScan` 调用时记录新值
   - 验证 reset 时是否覆盖了正确的数据

7. **isScanned 判断**
   - 在 `ActiveParametersPanel` 中记录 `isScanned` 的计算过程
   - 记录 `param.value`、`editedParams`、`stepDetail.parameters` 的值

8. **ScanValuesEditor useEffect**
   - 在 `useEffect` 中记录 `values` prop 的变化
   - 记录 `inputValue` 的重置时机

---

## 9) 总结

### 最可能根因（主因）

**handleScanToggle 二次触发覆盖** (高置信度)

- `handleScanToggle` 在用户输入数组后被二次触发
- 如果 `editedParameterScan[scanId]` 不存在（例如状态被重置），会重新初始化 `values = [currentValue]`
- `ScanValuesEditor` 的 `useEffect` 检测到 `values` 变化，重置 `inputValue`，导致用户输入丢失

**证据**:
- `handleScanToggle` 的初始化逻辑 (line 855-870) 会在 `!updated[scanId]` 时重置 `values`
- `isScanned` 的判断可能不准确，导致 `onChange('scan')` 被错误调用
- `ScanValuesEditor` 的 `useEffect` 会在 `values` prop 变化时重置输入框

### 备选根因 1

**ScanValuesEditor useEffect 覆盖** (中置信度)

- `ScanValuesEditor` 的 `useEffect` 在用户输入过程中重置了 `inputValue`
- 可能由父组件更新 `values` prop 触发

### 备选根因 2

**Backend apply_patch merge 导致部分更新** (低置信度)

- Backend 的 merge 语义可能导致部分更新失败
- 但可能性较低，因为 `apply_patch` 应该能正确处理嵌套字典

### Orphan scans 残留

**这是设计，不是 bug**

- Backend 使用 `apply_patch()` 进行 merge，不会删除未提及的 scan 定义
- 如果要删除 orphan scans，需要改为 full replace 或显式删除

---

## 10) 下一步行动建议

1. **立即验证**: 添加断点/日志，验证 `handleScanToggle` 的调用次数和时机
2. **修复主因**: 如果确认是 `handleScanToggle` 二次触发，添加保护逻辑
3. **修复备选**: 如果主因不成立，检查 `ScanValuesEditor` 的 `useEffect` 行为
4. **修复 orphan**: 根据产品意图决定是否改为 full replace

---

**报告结束**

