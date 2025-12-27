# Demo Importer Review Checklist

请按以下问题在代码库中定位相关代码/数据结构，并报告结论（文件路径 + 关键函数名 + 简短说明即可）。

## 1. Structure 提取逻辑

**问题：** 当前 importer 是否只从第一个 .in 文件建立 structure？

**需要定位：**
- 哪个函数负责从 QE input 提取 structure？
- 例如：`importers.py` 里是否有 `build_structure_from_qe_input()` / `parse_structure_from_qe_input()` 之类？
- `build_calculation_from_qe_inputs()` 现在怎么拿 `structure_id/selector` 传给每个 step？
- 是固定一个 `structure_id` 传给所有 steps，还是 step 可以各自指定？

**请报告：**
- 文件路径 + 函数名 + 简短说明

## 2. 多 Structure 支持

**问题：** 数据模型是否支持一个 project/calc 多个 structure？

**需要定位：**
- snapshot（`demo.qv.yml` / `demo_projects/*.yml`）里 `structures` 是 list/map 吗？
- step spec 里 `structure_id` / `structure_selector` 是单值字段吗？
- QVService / project API 是否有"新增 structure 并返回 id"的接口？在哪？

**请报告：**
- 文件路径 + 数据结构/函数名 + 简短说明

## 3. Structure 等价/去重逻辑

**问题：** 有无现成的"structure 等价/去重"逻辑可以复用？

**需要定位：**
- 是否已经有 canonicalization / wrap 的统一入口（之前讨论过的那套）
- 是否有结构 fingerprint（composition + lattice + frac coords）之类工具
- 如果没有，最合适放在哪里（`core/structure_utils`？）

**请报告：**
- 文件路径 + 函数名 + 简短说明（如果没有，说明"未找到"）

## 4. Exporter 的 ATOMIC_SPECIES 来源

**问题：** Exporter 在生成 .in 时，ATOMIC_SPECIES 来自哪里？

**需要定位：**
- 现在 exporter 是从 `species_overrides` 拼 ATOMIC_SPECIES，还是依赖 `step.cards`？
- 如果来自 overrides：当 step 没 overrides 时，用什么默认？（calc-level pseudo map？project pseudo config？）

**请报告：**
- 文件路径 + 函数名 + 简短说明

## 5. Verify 流程实现位置

**问题：** verify 流程目前在哪里实现？

**需要定位：**
- `--verify` flag 入口在哪个脚本/CLI？
- materialize 后 exporter 的调用点在哪？（准备插 round-trip 的位置）

**请报告：**
- 文件路径 + 函数名 + 简短说明

---

**格式要求：**
每个问题请按以下格式回复：

```
## 问题 X: [问题标题]

### 定位结果：

1. **文件路径**: `path/to/file.py`
   - **函数/类名**: `FunctionName` / `ClassName`
   - **说明**: 简短说明这个函数/类的作用

2. **文件路径**: `path/to/another_file.py`
   - **函数/类名**: `AnotherFunction`
   - **说明**: 简短说明
```

