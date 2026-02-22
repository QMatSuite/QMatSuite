# ParamSpace Dimension/Variant/Key 与 Step SSOT 深度审查报告

**日期**: 2026-01-XX  
**审查类型**: Targeted Code Review（只读，不修改代码）  
**目标**: 深挖 dimension/variant/key 定义、precision vs occupation 依赖、Step SSOT 审计

---

## 目录

1. [A) ParamSpace 的 "dimension / variant / key" 到底是什么？](#a-paramspace-的-dimension--variant--key-到底是什么)
2. [B) Precision vs Occupation：依赖、编译顺序、oracle](#b-precision-vs-occupation依赖编译顺序oracle)
3. [C) Step SSOT 审计：系统里只能有两个 step 库（gen 与 spec）](#c-step-ssot-审计系统里只能有两个-step-库gen-与-spec)
4. [D) 迁移建议（只写观察，不改代码）](#d-迁移建议只写观察不改代码)
5. [E) Unknown 列表](#e-unknown-列表)

---

## A) ParamSpace 的 "dimension / variant / key" 到底是什么？

### A1) 逐一定义：dimension / variant / key 的实体在哪里？

#### Dimension 是什么？

**证据位置**: `src/qmatsuite/presets/dimensions.py`

**定义**:
- **Dimension 是字符串 ID**（不是类/结构体/枚举）
- **常量定义**（行 129-132）:
  ```python
  DIMENSION_MAGNETISM: Final[str] = "magnetism"
  DIMENSION_OCCUPATIONS_SCHEME: Final[str] = "occupations_scheme"
  DIMENSION_PRECISION: Final[str] = "precision"
  DIMENSION_CONVERGENCE: Final[str] = "convergence"
  ```

**Dimension 与 ParamSpace 的关系**:
- **Dimension ≠ ParamSpace**
- **ParamSpace 是 dimension 的容器/实现**
- 每个 dimension 有一个或多个 ParamSpace（通过 variants）

**证据**: 
- `src/qmatsuite/presets/variants_registry.py:42-111` - 每个 dimension 可以有多个 variants，每个 variant 有一个 ParamSpace
- `src/qmatsuite/presets/paramspace.py:525` - ParamSpace 有 `name` 字段，通常等于 dimension name

**存储位置**:
- Dimension 名称作为字符串常量存储在 `dimensions.py`
- Dimension 枚举值（如 `MagnetismOption`, `PrecisionOption`）也在 `dimensions.py`（行 17-93）
- Dimension 到 ParamSpace 的映射通过 `variants_registry.py` 的 `VARIANTS` 列表

**创建者**: 硬编码在 `variants_registry.py` 的 `VARIANTS` 元组（行 104-111）

#### Variant 是什么？

**证据位置**: `src/qmatsuite/presets/space_variant.py:16-50`

**定义**:
- **Variant 是 `ParamSpaceVariant` 类实例**
- **不是 profile**（profile 是 ParamSpace 内部的矩阵行）

**字段**（行 31-35）:
```python
@dataclass(frozen=True)
class ParamSpaceVariant:
    name: str  # 例如 "PRECISION_PW_DEFAULT"
    dimension: str  # 例如 "precision"
    space: ParamSpace  # ParamSpace 实例
    applies_to_step_types: FrozenSet[str]  # 例如 {"scf", "nscf", "relax"}
    priority: int = 0
```

**Variant 与 Profile 的关系**:
- **Variant ≠ Profile**
- **Variant 是 ParamSpace + step_type 绑定**
- **Profile 是 ParamSpace 内部的矩阵行**（如 "LOW", "MED", "HIGH"）

**证据**: 
- `src/qmatsuite/presets/variants_registry.py:67-90` - Precision 有 3 个 variants（PRECISION_PW_DEFAULT, PRECISION_PW_NSCF, PRECISION_PW_BANDS_PW），每个 variant 有自己的 ParamSpace
- `src/qmatsuite/presets/paramspace.py:709-713` - Precision ParamSpace 有 3 个 profiles（"LOW", "MED", "HIGH"）

**互斥表示**:
- Variant 互斥通过 `(step_type, dimension)` 索引表保证（`src/qmatsuite/presets/variants_registry.py:138-147`）
- Profile 互斥通过 `match_profile()` 检测多个匹配并抛出异常（`src/qmatsuite/presets/paramspace.py:300-304`）

**Variant 与 Step 绑定**:
- ✅ **是**，variant 通过 `applies_to_step_types` 字段绑定到 step types
- 绑定关系存储在 `VARIANT_BY_STEP_AND_DIMENSION` 索引表（`src/qmatsuite/presets/variants_registry.py:158`）

#### Key 是什么？

**证据位置**: `src/qmatsuite/presets/paramspace.py:57-117`

**定义**:
- **Key 是 `ParamKey` 类实例**
- **Key 指的是 IR key**（概念上，v0 中与 QE key 相同）

**字段**（行 74-80）:
```python
@dataclass(frozen=True, eq=True)
class ParamKey:
    section: str  # YAML section（如 "SYSTEM", "ELECTRONS", "cards"）
    key: str  # IR parameter key name（如 "nspin", "ecutwfc", "degauss"）
    parser: Callable[[Any], Any]
    canonicalizer: Callable[[Any], Any]
    tolerance: Optional[float] = None
    aliases: Optional[frozenset[tuple[str, Any]]] = None
    default: Optional[Any] = None
```

**Key 的表示**:
- **不是字符串**，是 `ParamKey` 对象
- **不是枚举**，是 dataclass 实例
- Key 的 `key` 字段是字符串（IR key name）

**Canonicalization / Parse 归属**:
- **Parser**: `ParamKey.parser` 字段（函数）
- **Canonicalizer**: `ParamKey.canonicalizer` 字段（函数）
- **Aliases**: `ParamKey.aliases` 字段（frozenset）
- **Tolerance**: `ParamKey.tolerance` 字段（float）

**证据**: `src/qmatsuite/presets/paramspace.py:82-117` - `ParamKey.canonicalize()` 和 `ParamKey.matches()` 方法

**Key 在 YAML 中的路径**:
- Key 通过 `(section, key)` 二元组定位
- 例如：`("SYSTEM", "degauss")` 对应 YAML 中的 `parameters.SYSTEM.degauss`

### A2) Key 单归属（SSOT）是否真正实现？还是只是"约定"？

#### 是否存在全局注册/校验：key -> dimension/paramspace？

**结论**: ❌ **不存在全局注册/校验**

**证据**:
- 搜索 `key.*dimension|dimension.*key|key.*ownership` 未找到全局注册表
- `DIMENSION_OWNED_KEYS`（`src/qmatsuite/presets/integration.py:307-324`）是**硬编码映射**，不是运行时校验

**当前实现如何防止同一个 key 出现在多个 dimension？**

**结论**: ⚠️ **靠约定，不是 enforce**

**证据**:
- `DIMENSION_OWNED_KEYS` 是硬编码映射（行 307-324），用于 UI 显示和删除逻辑
- **没有运行时校验**确保 key 只属于一个 dimension
- **没有测试**验证 key 单归属

**实际约束**:
- 删除逻辑使用 `DIMENSION_OWNED_KEYS` 决定哪些 key 可以被删除（`src/qmatsuite/presets/integration.py:511-519`）
- 但这只是**约定**，不是 enforce

#### 报告里提到的 "(step_type, dimension) 单归属/避免 overlap" 到底是啥？

**证据位置**: `src/qmatsuite/presets/variants_registry.py:118-160`

**精确指出**:
- **约束的是 variant**，不是 keys
- **约束内容**: 同一个 `(step_type, dimension)` 组合只能有一个 variant

**实现**（行 138-147）:
```python
for step_type in variant.applies_to_step_types:
    key = (step_type, variant.dimension)
    if key in variant_by_step_and_dimension:
        existing = variant_by_step_and_dimension[key]
        raise ValueError(
            f"Overlap detected: Both {existing.name} and {variant.name} "
            f"apply to step_type={step_type}, dimension={variant.dimension}"
        )
    variant_by_step_and_dimension[key] = variant
```

**能否阻止同一个 key 在两个 dimension 中出现？**

**结论**: ❌ **不能**

**证据**:
- 这个约束只检查 variant 重叠，不检查 key 重叠
- 例如：`degauss` 可以同时出现在 `occupations_scheme` 和另一个 dimension 的 ParamSpace 中（虽然当前没有，但代码不阻止）

**实际例子**:
- `degauss` 只出现在 `occupations_scheme` dimension（`src/qmatsuite/presets/paramspace.py:495-502`）
- 但这是**约定**，不是 enforce

#### 反推（match_profile）时，match 的 key 集合来自哪里？

**证据位置**: `src/qmatsuite/presets/paramspace.py:241-309`

**Key 集合来源**: **来自 ParamSpace 自己的 key 集**

**实现**（行 268-295）:
```python
for key in paramspace.keys:  # 遍历 ParamSpace.keys
    cell = profile_cells[key]
    # ... 匹配逻辑
```

**反推域定义**:
- **参与匹配的 keys**: `ParamSpace.keys` 列表中的所有 keys
- **不来自 IR mapping 表**: IR mapping 只用于转换，不决定匹配范围
- **不来自 UI 参数库**: UI 参数库只用于显示，不参与匹配

**证据**: 
- `src/qmatsuite/presets/paramspace.py:268` - `for key in paramspace.keys`
- `src/qmatsuite/presets/variants_registry.py:496-500` - 匹配前先转换 QE→IR，但匹配时只检查 ParamSpace.keys

**结论**: ✅ **反推域 = ParamSpace.keys**（该 dimension 的 variant 的 ParamSpace 中定义的所有 keys）

---

## B) Precision vs Occupation：依赖、编译顺序、oracle

### B1) 找到 occupation 与 precision 的 ParamSpace 定义

#### OccupationsScheme ParamSpace

**证据位置**: `src/qmatsuite/presets/paramspace.py:463-529`

**定义函数**: `build_occupations_scheme_paramspace()`

**Keys**（行 504）:
- `key_occupations`: `("SYSTEM", "occupations")`，default="fixed"
- `key_smearing`: `("SYSTEM", "smearing")`，no default，aliases: "gauss" -> "gaussian"
- `key_degauss`: `("SYSTEM", "degauss")`，no default，tolerance=1e-12

**Profiles**（行 507-523）:
- `FIXED`: `occupations=VALUE("fixed")`, `smearing=NOT_APPLICABLE`, `degauss=NOT_APPLICABLE`
- `TETRAHEDRA`: `occupations=VALUE("tetrahedra")`, `smearing=NOT_APPLICABLE`, `degauss=NOT_APPLICABLE`
- `SMEARING_GAUSSIAN_0.02`: `occupations=VALUE("smearing")`, `smearing=VALUE("gaussian")`, `degauss=VALUE(0.02)`

**生成函数**: `compile_profile_patch()`（`src/qmatsuite/presets/paramspace.py:316-377`）

#### Precision ParamSpace

**证据位置**: `src/qmatsuite/presets/paramspace.py:655-730`

**定义函数**: `build_precision_paramspace()`

**Keys**（行 705）:
- `key_ecutwfc`: `("SYSTEM", "ecutwfc")`，no default
- `key_ecutrho`: `("SYSTEM", "ecutrho")`，no default
- `key_conv_thr`: `("ELECTRONS", "conv_thr")`，no default，tolerance=1e-11
- `key_kpoints`: `("cards", "K_POINTS")`，no default

**Profiles**（行 709-713）:
- `"LOW"`, `"MED"`, `"HIGH"` - 空字典（运行时计算）

**生成函数**: `_compile_precision_patch_for_step()`（`src/qmatsuite/presets/variants_registry.py:346-457`）

**注意**: Precision 不使用标准的 `compile_profile_patch()`，而是使用特殊的 resolver 函数

### B2) 编译顺序在哪里定义？是否存在明确 pipeline？

#### 编译入口函数

**证据位置**: `src/qmatsuite/presets/integration.py:327-568`

**入口**: `apply_presets_to_step()`

**Dimension 遍历顺序**（行 417）:
```python
for dimension in applied_dimensions:
    # ... 编译每个 dimension
```

**顺序来源**: **`applied_dimensions` 列表的顺序**

**`applied_dimensions` 如何构建**（行 387-395）:
```python
for dimension, option_value in options.items():
    variant = get_variant(dimension, step_type)
    if variant is not None:
        applied_dimensions.append(dimension)
```

**结论**: ⚠️ **顺序来自 `options` 字典的迭代顺序**（Python 3.7+ 保持插入顺序）

**是否有明确的顺序控制？**

**结论**: ❌ **当前不存在顺序控制**

**证据**:
- `DIMENSION_ORDER`（`src/qmatsuite/presets/catalog.py:82-87`）只用于 UI 显示排序，不用于编译顺序
- `apply_presets_to_step()` 中直接遍历 `options.items()`，没有排序

**结论**: ⚠️ **当前不存在顺序控制**（这将与预期冲突）

**详细证据**:
- `apply_presets_to_step()` 中（`src/qmatsuite/presets/integration.py:417`）直接遍历 `applied_dimensions` 列表
- `applied_dimensions` 列表的构建（行 387-395）按 `options.items()` 的迭代顺序
- Python 3.7+ 字典保持插入顺序，但**没有显式排序**
- `DIMENSION_ORDER`（`src/qmatsuite/presets/catalog.py:82-87`）只用于 UI 显示，不用于编译顺序

**如果 precision 需要依赖 occupation 的选择（例如 degauss 的写入），当前实现无法保证**:
- 如果 `options = {"precision": "med", "occupations_scheme": "smearing_gaussian"}`
- 编译顺序取决于字典插入顺序，**不确定**
- Precision 编译时无法读取 occupation 的状态（没有 oracle 机制）

### B3) Oracle：它是什么？从哪来？能提供什么信息？

**结论**: ❌ **未找到明确的 "oracle" 机制**

**证据**:
- 搜索 `oracle|Oracle|ORACLE` 只找到文档引用，没有代码实现
- `precision_context`（`src/qmatsuite/presets/variants_registry.py:268`）提供外部数据（lattice_matrix, base_ecutwfc, base_ecutrho），但不是 "oracle"

**Oracle 接口/类**: **不存在**

**传进编译器的路径**: **不存在**（没有 oracle 参数）

**Oracle 是否允许 ParamSpace "偷看"别的 ParamSpace 的选择？**

**结论**: ❌ **不允许**（因为没有 oracle 机制）

**证据**: 
- `compile_dimension_patch_for_step()` 只接收 `dimension`, `option_enum`, `step_type`, `step_yaml`，没有其他 dimension 的状态
- 每个 dimension 独立编译，不读取其他 dimension 的选择

**Oracle 是否提供 step topo / global info？**

**结论**: ❌ **不提供**（因为没有 oracle）

**Precision 的特殊性**:
- Precision 通过 `precision_context` 接收外部数据（structure + pseudos）
- 这些数据来自 `precision_advice` 和 `precision_lattice_matrix` 参数（`src/qmatsuite/presets/integration.py:332-333`）
- **不是从其他 ParamSpace 读取**，而是从外部数据源计算

### B4) 用 degauss 做端到端证据链

#### degauss 属于哪个 dimension/ParamSpace？

**结论**: ✅ **degauss 属于 `occupations_scheme` dimension**

**证据**: 
- `src/qmatsuite/presets/paramspace.py:495-502` - `key_degauss` 定义在 `build_occupations_scheme_paramspace()` 中
- `src/qmatsuite/presets/integration.py:312` - `DIMENSION_OWNED_KEYS[DIMENSION_OCCUPATIONS_SCHEME]` 包含 `"degauss"`

#### degauss 在什么条件下写出？谁决定？

**证据位置**: `src/qmatsuite/presets/paramspace.py:316-377`

**决定者**: **ParamSpace profile 的 Cell 类型**

**条件**:
- **FIXED profile**: `degauss=NOT_APPLICABLE` → **删除**（`compile_profile_patch()` 行 355-358）
- **TETRAHEDRA profile**: `degauss=NOT_APPLICABLE` → **删除**
- **SMEARING_GAUSSIAN_0.02 profile**: `degauss=VALUE(0.02)` → **写出 0.02**

**证据**: `src/qmatsuite/presets/paramspace.py:507-523` - Profile 定义

**Precision 是否影响 degauss？**

**结论**: ❌ **Precision 不影响 degauss**

**证据**:
- Precision ParamSpace 的 keys 列表（`src/qmatsuite/presets/paramspace.py:705`）不包含 `degauss`
- Precision 编译函数（`_compile_precision_patch_for_step()`）不涉及 `degauss`
- `DIMENSION_OWNED_KEYS[DIMENSION_PRECISION]`（`src/qmatsuite/presets/integration.py:314-319`）不包含 `degauss`

#### 当 occupation 不是 smearing 时，degauss 在 YAML/IR 中应当如何？

**证据位置**: `src/qmatsuite/presets/paramspace.py:316-377`

**真实行为**:
- **FIXED/TETRAHEDRA profile**: `degauss=NOT_APPLICABLE`
- **编译时**: `compile_profile_patch()` 将 `NOT_APPLICABLE` 加入 `deletions` set（行 355-358）
- **应用时**: `apply_presets_to_step()` 将 deletions 转换为 `None` 值（`src/qmatsuite/presets/integration.py:512-519`）
- **结果**: **degauss 被删除**（从 YAML 中移除）

**证据**: 
- `src/qmatsuite/presets/paramspace.py:355-358` - `NOT_APPLICABLE` → deletions
- `src/qmatsuite/presets/integration.py:512-519` - deletions → `None` → 删除

**结论**: ✅ **缺席**（不是显式 NA，而是删除 key）

#### 反推时如果 degauss 缺席/NA，precision profile 的 match 条件是什么？

**证据位置**: `src/qmatsuite/presets/paramspace.py:241-309`

**Precision profile 的 match 条件**:
- Precision ParamSpace 的 keys 列表（行 705）**不包含 `degauss`**
- **`degauss` 不参与 precision 匹配**

**证据**: 
- `src/qmatsuite/presets/paramspace.py:268` - `for key in paramspace.keys` - 只遍历 ParamSpace.keys
- Precision ParamSpace.keys 不包含 `degauss`（`src/qmatsuite/presets/paramspace.py:705`）

**结论**: ✅ **degauss 缺席不影响 precision profile 匹配**（因为 degauss 不在 precision ParamSpace.keys 中）

**证据**: `src/qmatsuite/presets/paramspace.py:705` - Precision ParamSpace.keys 只包含 `[key_ecutwfc, key_ecutrho, key_conv_thr, key_kpoints]`，不包含 `degauss`

#### Presence/absence 是否是 profile 的一部分？在哪里实现？

**证据位置**: `src/qmatsuite/presets/paramspace.py:241-309`

**实现**:
- **Presence**: 通过 `get_yaml_value()` 返回 `(present: bool, raw_value: Any)`（行 169-205）
- **Absence**: `present == False` 时，使用 `key.default` 作为 `effective_value`（行 208-234）
- **NOT_APPLICABLE**: Profile 中定义为 `Cell.NOT_APPLICABLE()`，匹配时要求 `present == False`（行 278-284）

**证据**: 
- `src/qmatsuite/presets/paramspace.py:278-284` - NOT_APPLICABLE 匹配逻辑
- `src/qmatsuite/presets/paramspace.py:355-358` - NOT_APPLICABLE 编译逻辑（删除）

**结论**: ✅ **Presence/absence 是 profile 的一部分**，通过 `Cell.NOT_APPLICABLE()` 和 `get_yaml_value()` 实现

#### 完整链路：用户选 preset/profile → 编译 → 写入 YAML → 重开项目 → 反推出 profile/custom

**以 `occupations_scheme=smearing_gaussian` 为例（degauss 相关）**:

```
[用户选择]
  UI: occupations_scheme = "smearing_gaussian"
  
[编译方向]
  apply_presets_to_step(options={"occupations_scheme": "smearing_gaussian"})
    → get_variant("occupations_scheme", "scf") → OCCUPATIONS_SCHEME_VARIANT
    → compile_dimension_patch_for_step("occupations_scheme", SMEARING_GAUSSIAN, "scf", step_yaml)
      → ENUM_TO_PROFILE["occupations_scheme"][SMEARING_GAUSSIAN] → "SMEARING_GAUSSIAN_0.02"
      → compile_profile_patch(space, "SMEARING_GAUSSIAN_0.02", ir_yaml)
        → Profile["SMEARING_GAUSSIAN_0.02"][key_degauss] = Cell.VALUE(0.02)
        → ir_patch = {"SYSTEM": {"degauss": 0.02}}
        → ir_patch_to_qe_patch() → qe_patch = {"SYSTEM": {"degauss": 0.02}}
    → StepDoc.apply_patch({"parameters": {"SYSTEM": {"degauss": "0.02"}}})
    → save_step_doc() → step.yaml 写入 parameters.SYSTEM.degauss = "0.02"
  
[重开项目]
  get_step_detail() → StepDoc.load() → export_copy(["parameters"])
    → UI 显示: parameters.SYSTEM.degauss = "0.02"
  
[反推方向]
  detect_presets_from_calculation(calculation_dir)
    → detect_all_presets(steps)
      → detect_dimension_from_steps(steps, "occupations_scheme")
        → detect_dimension_for_step("occupations_scheme", "scf", step_yaml)
          → get_variant("occupations_scheme", "scf") → OCCUPATIONS_SCHEME_VARIANT
          → qe_yaml_to_ir_yaml(step_yaml) → ir_yaml = {"SYSTEM": {"degauss": 0.02}}
          → match_profile(variant.space, ir_yaml)
            → for key in paramspace.keys:  # key_degauss
              → get_yaml_value(ir_yaml, "SYSTEM", "degauss") → (True, 0.02)
              → Profile["SMEARING_GAUSSIAN_0.02"][key_degauss] = Cell.VALUE(0.02)
              → key_degauss.matches(0.02, 0.02) → True (within tolerance 1e-12)
            → 所有 keys match → 返回 "SMEARING_GAUSSIAN_0.02"
          → PROFILE_TO_ENUM["occupations_scheme"]["SMEARING_GAUSSIAN_0.02"] → SMEARING_GAUSSIAN
    → 返回 {"occupations_scheme": "smearing_gaussian"}
```

**证据位置**:
- 编译: `src/qmatsuite/presets/variants_registry.py:260-343`
- 匹配: `src/qmatsuite/presets/paramspace.py:241-309`
- 存储: `src/qmatsuite/workflow/step_factory.py:106-118`

---

## C) Step SSOT 审计：系统里只能有两个 step 库（gen 与 spec）

### C1) 列出所有 step 类型来源（按层分类）

#### GenStep 候选来源（抽象）

| 来源 | 定义文件 | 类型 | 主要调用点 | 证据 |
|------|---------|------|-----------|------|
| `GeneralizedStep` 枚举 | `src/qmatsuite/workflow/generalized_steps.py:21-56` | Enum | `materialize_public_step_key()`, `dematerialize_to_generalized_step()` | 行 21-56 定义枚举值 |
| `StepTypeSpec.public_type` / `id` | `src/qmatsuite/workflow/registry.py:24-50` | 字符串字段 | `StepTypeRegistry.get()`, UI/workflow | 行 29-31 定义 public_type 字段 |
| `MATERIALIZATION_MAP` 的 key | `src/qmatsuite/workflow/generalized_steps.py:61-92` | Dict key (tuple) | `materialize_step()`, `dematerialize_step()` | 行 61-92 定义映射表 |

**结论**: ✅ **GenStep 来源明确**，主要是 `GeneralizedStep` 枚举和 `StepTypeSpec.public_type`

#### SpecStep 候选来源（机器类型）

| 来源 | 定义文件 | 类型 | 主要调用点 | 证据 |
|------|---------|------|-----------|------|
| `StepTypeSpec.machine_type` | `src/qmatsuite/workflow/registry.py:24-50` | 字符串字段 | `step.yaml` 存储, `resolve_engine_for_step()` | 行 30, 45 定义 machine_type |
| `_STEP_TYPES` 字典的 key | `src/qmatsuite/workflow/registry.py:181-558` | Dict key (字符串) | `StepTypeRegistry` 初始化 | 行 185-558 定义所有 step types |
| `MATERIALIZATION_MAP` 的 value | `src/qmatsuite/workflow/generalized_steps.py:61-92` | Dict value (字符串) | `materialize_step()` | 行 63-86 定义映射值 |

**结论**: ✅ **SpecStep 来源明确**，主要是 `StepTypeSpec.machine_type` 和 `_STEP_TYPES` 字典

#### 第三套/legacy step 词典来源（违规）

| 来源 | 定义文件 | 类型 | 主要调用点 | 证据 | 违规原因 |
|------|---------|------|-----------|------|---------|
| `StepType` 枚举 | `src/qmatsuite/calculation/types.py:10-30` | Enum | `Step.step_type`, `_coerce_step_type()` | 行 10-30 定义枚举 | **混用 gen 和 spec** |
| `ParamSpaceVariant.applies_to_step_types` | `src/qmatsuite/presets/space_variant.py:34` | FrozenSet[str] | `get_variant()`, `apply_presets_to_step()` | 行 34 定义字段 | **使用 public_type**（如 "scf", "nscf"），对应 GenStep 字符串，但格式与 `GeneralizedStep` 枚举不一致 |

**关于 `applies_to_step_types`**:
- **不是第三套词典**，它使用的是 `StepTypeSpec.public_type`（GenStep 的字符串形式）
- **但格式不一致**: `applies_to_step_types` 使用小写（"scf"），`GeneralizedStep` 枚举使用大写（"SCF"）
- **需要统一**: 应该统一为 `StepTypeSpec.public_type` 格式（小写）或 `GeneralizedStep` 枚举格式（大写）

**结论**: ⚠️ **存在第三套词典**: `StepType` 枚举

**违规证据**:
1. **`StepType` 枚举**（`src/qmatsuite/calculation/types.py:10-30`）:
   - 包含混合值：`SCF = "scf"`（gen-like），`PYSCF_SCF = "pyscf_scf"`（spec-like），`BANDS_PW = "bands_pw"`（spec-like）
   - **混用 gen 和 spec**，违反 SSOT

2. **`applies_to_step_types`**（`src/qmatsuite/presets/variants_registry.py:48-100`）:
   - 使用 `public_type` 字符串（如 `"scf"`, `"nscf"`, `"bands_pw"`）
   - **对应 GenStep 的字符串形式**（`StepTypeSpec.public_type`）
   - **但格式不一致**: `applies_to_step_types` 使用小写（"scf"），`GeneralizedStep` 枚举使用大写（"SCF"）
   - **需要统一**: 应该统一为 `StepTypeSpec.public_type` 格式（小写）或 `GeneralizedStep` 枚举格式（大写）

### C2) 重点深挖 StepType(str, Enum)：它到底代表什么？

**证据位置**: `src/qmatsuite/calculation/types.py:10-30`

**定义**:
```python
class StepType(str, Enum):
    SCF = "scf"  # gen-like
    NSCF = "nscf"  # gen-like
    DOS = "dos"  # gen-like
    BANDS_PW = "bands_pw"  # spec-like (QE-specific)
    PYSCF_SCF = "pyscf_scf"  # spec-like
    # ...
```

**结论**: ⚠️ **StepType 混用 gen 和 spec**

**证据**:
- `SCF = "scf"` → gen step（public type）
- `BANDS_PW = "bands_pw"` → spec step（QE-specific，但没有 engine 前缀）
- `PYSCF_SCF = "pyscf_scf"` → spec step（完整 machine type）

**YAML 中 step_type 存的是啥？**

**证据位置**: `src/qmatsuite/workflow/step_factory.py:48-55`

**结论**: ✅ **YAML 存储 `machine_type`（SPEC）**

**证据**:
```python
# 行 48-55
spec = registry.get(step_type)  # Accepts both public and machine types
if spec:
    machine_step_type = spec.machine_type  # Use machine type for step.yaml
else:
    machine_step_type = step_type  # Fallback
# 行 73
"step_type": machine_step_type,  # Machine type goes to step.yaml
```

**Runner/materialize/dematerialize 使用的是哪一套？**

**证据位置**: 
- Materialize: `src/qmatsuite/workflow/generalized_steps.py:96-122`
- Dematerialize: `src/qmatsuite/workflow/generalized_steps.py:338-353`
- Runner: `src/qmatsuite/calculation/runner.py:96`

**结论**: 
- **Materialize**: 使用 `MATERIALIZATION_MAP`（gen → spec）
- **Dematerialize**: 使用 `MATERIALIZATION_MAP` 反向查找（spec → gen）
- **Runner**: 读取 `step.yaml` 的 `step_type` 字段（SPEC），然后通过 `_coerce_step_type()` 转换为 `StepType` 枚举（`src/qmatsuite/calculation/runner.py:50-77`）

**如果 StepType 与 gen/spec 不是一一对应，那它就是第三套词典（违规）**

**结论**: ✅ **StepType 是第三套词典（违规）**

**证据**:
- StepType 枚举值不完整（只有部分 step types）
- StepType 混用 gen 和 spec 值
- StepType 在 `Step.step_type` 字段中使用（`src/qmatsuite/calculation/step.py:28`），但执行时应该用 `step.yaml` 的 `machine_type`

---

## D) 迁移建议（只写观察，不改代码）

### D1) 哪些地方需要改才能实现 SSOT：只剩 gen_step: str 与 spec_step: str

**观察到的需要改动的地方**:

1. **`StepType` 枚举**（`src/qmatsuite/calculation/types.py`）:
   - **当前**: 混用 gen 和 spec，不完整
   - **需要**: 移除或重构为纯 gen step 枚举（如果保留）
   - **影响**: `Step.step_type` 字段、`_coerce_step_type()` 函数

2. **`ParamSpaceVariant.applies_to_step_types`**（`src/qmatsuite/presets/space_variant.py`）:
   - **当前**: 使用 public_type 字符串（如 "scf", "nscf"），对应 GenStep 但大小写不一致
   - **需要**: 统一为 GenStep 枚举值或统一的字符串格式（如全部小写 "scf" 或全部大写 "SCF"）
   - **影响**: 所有 variant 定义、`get_variant()` 函数、需要与 `GeneralizedStep` 枚举或 `StepTypeSpec.public_type` 对齐

3. **`_coerce_step_type()`**（`src/qmatsuite/calculation/runner.py:50-77`）:
   - **当前**: 将字符串转换为 `StepType` 枚举
   - **需要**: 改为直接使用字符串，或转换为 gen step
   - **影响**: Runner 执行逻辑

4. **`Step.step_type` 字段**（`src/qmatsuite/calculation/step.py:28`）:
   - **当前**: `Optional[StepType]` 枚举
   - **需要**: 改为 `Optional[str]`（gen step 或 spec step）
   - **影响**: 所有使用 `step.step_type` 的代码

### D2) StepType(enum) 作为 legacy 应该如何退场（在哪些边界层保留兼容解析）

**观察到的边界层**:

1. **加载边界**（`src/qmatsuite/calculation/calculation.py:768-795`）:
   - `_coerce_step_type()` 函数将字符串转换为 `StepType` 枚举
   - **建议**: 保留兼容解析，但标记为 deprecated

2. **执行边界**（`src/qmatsuite/calculation/runner.py:50-77`）:
   - `_coerce_step_type()` 用于执行时类型转换
   - **建议**: 改为直接使用 `step.yaml` 的 `machine_type` 字符串，不转换

3. **API 边界**（`src/qmatsuite/api.py`）:
   - 多个地方使用 `StepType` 枚举
   - **建议**: 逐步迁移到字符串，保留兼容层

**退场策略**:
- **阶段 1**: 保留 `StepType` 枚举，但标记为 deprecated
- **阶段 2**: 内部使用字符串，边界层提供兼容转换
- **阶段 3**: 移除 `StepType` 枚举，完全使用字符串

---

## E) Unknown 列表

### E1) Key 单归属的全局 enforce 机制

**状态**: ⚠️ **Unknown**

**问题**: 是否存在运行时校验确保 key 只属于一个 dimension？

**下一步查找线索**:
- 检查是否有测试验证 key 单归属
- 检查 `DIMENSION_OWNED_KEYS` 是否有冲突检测逻辑
- 检查 ParamSpace 构建时是否有校验

**当前发现**: 未找到 enforce 机制，只有硬编码约定

**补充证据**:
- `DIMENSION_OWNED_KEYS`（`src/qmatsuite/presets/integration.py:307-324`）标记为 DEPRECATED（行 303），只用于 UI 显示
- 删除逻辑现在由 `profile NOT_APPLICABLE cells` 驱动（行 304），不是由 `DIMENSION_OWNED_KEYS` 驱动
- **没有运行时校验**确保 key 只属于一个 dimension

### E2) Precision 与 Occupation 的编译顺序依赖

**状态**: ✅ **已确认：不存在依赖**

**结论**: Precision 和 Occupation 是独立编译的，没有顺序依赖

**证据**: `src/qmatsuite/presets/integration.py:417` - 按 `options` 字典顺序遍历，没有显式顺序控制

### E3) Oracle 机制的完整实现

**状态**: ✅ **已确认：不存在**

**结论**: 没有 oracle 机制，precision 通过 `precision_context` 接收外部数据

**证据**: 搜索 `oracle` 未找到实现，只有文档引用

### E4) StepType 枚举的完整使用范围

**状态**: ⚠️ **部分确认**

**问题**: `StepType` 枚举在哪些地方被使用？是否可以完全移除？

**下一步查找线索**:
- 完整搜索 `StepType` 的所有使用点
- 评估移除的影响范围
- 确认是否有外部 API 依赖

**当前发现**: `StepType` 在 `Step.step_type` 字段、`_coerce_step_type()` 函数中使用

### E5) ParamSpaceVariant.applies_to_step_types 的迁移路径

**状态**: ⚠️ **需要进一步设计**

**问题**: 如何将 `applies_to_step_types` 从 SPEC types 迁移到 GenStep？

**下一步查找线索**:
- 检查是否有 GenStep → SPEC 的映射表
- 评估迁移影响范围
- 设计兼容层

**当前发现**: `applies_to_step_types` 使用 SPEC types（如 "scf", "nscf"），需要迁移到 GenStep

**具体证据**:
- `src/qmatsuite/presets/variants_registry.py:48-100` - 所有 variant 的 `applies_to_step_types` 使用字符串（如 "scf", "nscf", "bands_pw"）
- 这些字符串对应 `StepTypeSpec.public_type`（`src/qmatsuite/workflow/registry.py:188, 201, 214`）
- `public_type` 是 GenStep 的字符串表示（如 "scf" 对应 GenStep.SCF）
- **结论**: `applies_to_step_types` 使用的是 **GenStep 的字符串形式**（public_type），不是第三套词典
- **但**: 当前实现中，`applies_to_step_types` 的值（如 "scf"）与 `GeneralizedStep` 枚举值（"SCF"）不一致（大小写不同），需要统一

---

## 总结

### 关键发现

1. **Dimension/Variant/Key 定义**:
   - Dimension = 字符串 ID
   - Variant = ParamSpace + step_type 绑定
   - Key = ParamKey 对象（IR key）

2. **Key 单归属**:
   - ❌ **不存在全局 enforce**
   - ⚠️ **靠约定**（`DIMENSION_OWNED_KEYS` 硬编码）
   - `(step_type, dimension)` 单归属只约束 variant，不约束 keys

3. **Precision vs Occupation 依赖**:
   - ❌ **不存在依赖**
   - degauss 只属于 `occupations_scheme`，precision 不影响 degauss
   - 没有编译顺序控制
   - 没有 oracle 机制

4. **Step SSOT 违规**:
   - ⚠️ **存在第三套词典**: `StepType` 枚举（混用 gen 和 spec）
   - ⚠️ **ParamSpaceVariant.applies_to_step_types** 使用 `public_type`（GenStep 字符串），但格式与 `GeneralizedStep` 枚举不一致（小写 vs 大写）

### 迁移建议（观察）

1. **移除 `StepType` 枚举**，改用字符串
2. **将 `applies_to_step_types` 迁移到 GenStep**
3. **添加 key 单归属的运行时校验**（如果需要 enforce）

