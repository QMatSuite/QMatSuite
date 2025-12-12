# JSON 文件与 Python 提取器对应关系

## 完整对应表

| JSON 文件 | 旧编号 | 新编号 | Schema Version | 生成器脚本 | 说明 |
|-----------|--------|--------|----------------|------------|------|
| `qe_module_parameters.legacy.v0.json` | v1 | v0 | **无** | `extract_qe_parameters_v1.py` | 最初版本，无 schema_version 字段 |
| `qe_module_parameters.legacy.v1.json` | v2 | v1 | **1** | `extract_qe_parameters_v2.py` (旧版本) | 引入 parameters map 结构 |
| `qe_module_parameters.legacy.v2.json` | v3 | v2 | **2** | `extract_qe_parameters_v2.py` (当前版本) | 添加 status/see_also 字段 |
| `qe_module_parameters.json` (生产) | v4 | v3 | **3** | `extract_qe_parameters_v3.py` (当前版本) | 添加 sections tree, optionality, card fields |

## 详细说明

### 1. `legacy.v0.json` (旧 v1 → 新 v0)

**生成器**: `tools/extract_qe_parameters_v1.py`

**特点**:
- 最初的提取器，在引入 schema versioning 之前就存在
- **不设置** `schema_version` 字段
- 数据结构: `modules -> {module -> {sections: {section_name -> [param_names]}}}`
- 每个参数只有名称，没有 type/default/enum/description 等元数据

**生成命令**:
```bash
python3 tools/extract_qe_parameters_v1.py --use-cache
```

---

### 2. `legacy.v1.json` (旧 v2 → 新 v1)

**生成器**: `tools/extract_qe_parameters_v2.py` (旧版本，在重新编号之前)

**特点**:
- 旧编号 v2，新编号 v1
- Schema version: **1**
- 引入 `parameters` map 结构（替代 sections -> [names]）
- 每个参数包含: name, type, default, enum, description

**注意**: 
- 这个文件是在重新编号**之前**由旧版本的 `extract_qe_parameters_v2.py` 生成的
- 当时该脚本生成 `schema_version=1`（对应旧 v2）
- 重新编号后，该文件的 `schema_version` 被更新为 1（对应新 v1）

**生成命令** (历史):
```bash
# 旧版本的 extract_qe_parameters_v2.py 生成 schema_version=1
python3 tools/extract_qe_parameters_v2.py --use-cache
```

---

### 3. `legacy.v2.json` (旧 v3 → 新 v2)

**生成器**: `tools/extract_qe_parameters_v2.py` (当前版本，重新编号后)

**特点**:
- 旧编号 v3，新编号 v2
- Schema version: **2**
- 添加了 `status` 和 `see_also` 字段
- 改进了 Default/Status/See 解析（读取左单元格文本）
- 改进了 enum 提取（优先使用 `<span class="flag">`）
- 改进了索引支持（bounded, symbolic, multi-dimensional）

**生成命令**:
```bash
python3 tools/extract_qe_parameters_v2.py --use-cache
```

**当前状态**: 
- 该脚本现在生成 `schema_version=2`（对应新 v2，旧 v3）

---

### 4. `qe_module_parameters.json` (生产版本，旧 v4 → 新 v3)

**生成器**: `tools/extract_qe_parameters_v3.py` (当前版本，重新编号后)

**特点**:
- 旧编号 v4，新编号 v3
- Schema version: **3**
- 添加了 `module.sections` 层次结构（支持 NEB supercard）
- 添加了 section-level descriptions
- 添加了 optionality 分类（optional/required/conditional/none）
- 添加了 card 结构化字段（options, default_option, options_description, syntax, items）
- 保留了 v2 的所有参数提取逻辑

**生成命令**:
```bash
python3 tools/extract_qe_parameters_v3.py --use-cache --pretty
```

**当前状态**:
- 这是**当前生产版本**的提取器
- 生成 `schema_version=3`（对应新 v3，旧 v4）

---

## 版本演进历史

```
v0 (旧 v1) → extract_qe_parameters_v1.py
  ↓ 无 schema_version 字段
  ↓ sections -> [param_names]

v1 (旧 v2) → extract_qe_parameters_v2.py (旧版本)
  ↓ schema_version=1
  ↓ 引入 parameters map

v2 (旧 v3) → extract_qe_parameters_v2.py (当前版本)
  ↓ schema_version=2
  ↓ 添加 status/see_also

v3 (旧 v4) → extract_qe_parameters_v3.py (当前版本)
  ↓ schema_version=3
  ↓ 添加 sections tree, optionality, card fields
```

## 当前提取器脚本状态

| 脚本 | 生成的 Schema Version | 对应新编号 | 对应旧编号 |
|------|---------------------|-----------|-----------|
| `extract_qe_parameters_v1.py` | 无 | v0 | v1 |
| `extract_qe_parameters_v2.py` | 2 | v2 | v3 |
| `extract_qe_parameters_v3.py` | 3 | v3 | v4 |

## 注意事项

1. **legacy.v1.json** 是由**旧版本**的 `extract_qe_parameters_v2.py` 生成的（在重新编号之前）
   - 该旧版本生成 `schema_version=1`（对应旧 v2）
   - 重新编号后，该文件的 `schema_version` 值被更新为 1（对应新 v1）

2. **legacy.v2.json** 是由**当前版本**的 `extract_qe_parameters_v2.py` 生成的
   - 该脚本在重新编号后生成 `schema_version=2`（对应新 v2，旧 v3）

3. 所有提取器都使用 `json.dump(..., sort_keys=False)` 来保持文档顺序

4. 生产 JSON 路径始终是: `src/quantumvitas/data/qe_module_parameters.json`
