# IR SSOT迁移计划：移除QE↔IR往返Shim

**日期**: 2025-01-XX  
**目标**: 将ParamSpace从"QE↔IR往返shim"改为"IR SSOT"，ParamSpace直接操作IR，QE writer从IR生成QE input。

---

## Phase B 定位

### Shim往返的唯一路径

**搜索命令**:
```bash
rg -n "qe_yaml_to_ir_yaml|ir_patch_to_qe_patch" -S src/qmatsuite/presets
```

**发现的Shim路径**:

#### 1. variants_registry.py

**compile_dimension_patch_for_step()** (行260-346):
- **位置**: `src/qmatsuite/presets/variants_registry.py:328-340`
- **Shim代码**:
  ```python
  from qmatsuite.ir.backends.qe.mapping import qe_yaml_to_ir_yaml, ir_patch_to_qe_patch
  ir_yaml = qe_yaml_to_ir_yaml(step_yaml, qe_module="pw")
  # ... ParamSpace操作 ...
  patch = ir_patch_to_qe_patch(ir_patch)
  ```
- **往返**: QE YAML → IR YAML → ParamSpace → IR patch → QE patch

**detect_dimension_for_step()** (行499-529):
- **位置**: `src/qmatsuite/presets/variants_registry.py:536-539`
- **Shim代码**:
  ```python
  from qmatsuite.ir.backends.qe.mapping import qe_yaml_to_ir_yaml
  ir_yaml = qe_yaml_to_ir_yaml(step_yaml, qe_module="pw")
  ```
- **往返**: QE YAML → IR YAML → ParamSpace match

**_compile_precision_patch_for_step()** (行366-496):
- **位置**: `src/qmatsuite/presets/variants_registry.py:481-484`
- **Shim代码**:
  ```python
  from qmatsuite.ir.backends.qe.mapping import ir_patch_to_qe_patch
  patch = ir_patch_to_qe_patch(patch)
  ```
- **往返**: IR patch → QE patch

**_detect_precision_for_step()** (行556-648):
- **位置**: `src/qmatsuite/presets/variants_registry.py:630-631`
- **Shim代码**:
  ```python
  from qmatsuite.ir.backends.qe.mapping import qe_yaml_to_ir_yaml
  ir_yaml = qe_yaml_to_ir_yaml(step_yaml, qe_module="pw")
  ```
- **往返**: QE YAML → IR YAML

#### 2. spaces_registry.py

**detect_dimension()** (行143-231):
- **位置**: `src/qmatsuite/presets/spaces_registry.py:190-193, 220-221`
- **Shim代码**: `qe_yaml_to_ir_yaml(step_yaml, qe_module="pw")`

**compile_dimension_patch()** (行238-385):
- **位置**: `src/qmatsuite/presets/spaces_registry.py:315-337, 354-362`
- **Shim代码**: `qe_yaml_to_ir_yaml()` → `ir_patch_to_qe_patch()`

### ParamSpace被调用的唯一入口函数

**编译入口**:
- **文件**: `src/qmatsuite/presets/variants_registry.py`
- **函数**: `compile_dimension_patch_for_step()`
- **调用链**: `apply_presets_to_step()` → `compile_dimension_patch_for_step()` → `compile_profile_patch()`

**检测入口**:
- **文件**: `src/qmatsuite/presets/variants_registry.py`
- **函数**: `detect_dimension_for_step()`
- **调用链**: `detect_all_presets()` → `detect_dimension_for_step()` → `match_profile()`

### Shim往返发生的函数

**主要Shim函数**:
1. `compile_dimension_patch_for_step()` - 编译时的QE→IR→QE往返
2. `detect_dimension_for_step()` - 检测时的QE→IR往返
3. `_compile_precision_patch_for_step()` - 精度编译时的IR→QE转换
4. `_detect_precision_for_step()` - 精度检测时的QE→IR转换

**辅助Shim函数**:
- `spaces_registry.py`中的`detect_dimension()`和`compile_dimension_patch()`也有类似转换

---

## Phase B: ParamSpace内核输入输出改为IR

### 改动清单

1. **移除variants_registry.py中的shim**:
   - `compile_dimension_patch_for_step()`: 移除`qe_yaml_to_ir_yaml()`和`ir_patch_to_qe_patch()`调用
   - `detect_dimension_for_step()`: 移除`qe_yaml_to_ir_yaml()`调用
   - `_compile_precision_patch_for_step()`: 移除`ir_patch_to_qe_patch()`调用
   - `_detect_precision_for_step()`: 移除`qe_yaml_to_ir_yaml()`调用

2. **修改integration.py**:
   - `apply_presets_to_step()`: 从step.yaml读取时，直接视为IR YAML（因为v0中IR==QE结构）
   - 写入时，直接写入IR patch（不再转换为QE patch）

3. **更新ParamSpace注释/类型**:
   - `paramspace.py`: 更新注释，明确key是IR key（虽然v0中与QE key同名）
   - `oracle.py`: 更新注释，明确读取的是IR状态

4. **删除spaces_registry.py中的shim**（如果仍在使用）

### 验收结果

待Phase B完成后填写。

---

## Phase C: QE writer改为从IR落地到QE

### 改动清单

1. **修改QE writer**:
   - 输入改为IR参数容器
   - 内部使用IR→QE mapping生成QE input文本

2. **删除presets层残留的QE转换代码**

### 验收结果

待Phase C完成后填写。

---

## 最终静态断言

待完成后填写。

---

## 最终交付说明

待完成后填写。

