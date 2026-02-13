# Wannier90 Execution Commands Reference

本文档详细说明 QMatSuite 中 Wannier90 工作流的每个步骤的具体执行命令。

## 执行流程和命令

### 步骤 1: SCF (Self-Consistent Field)

**输入文件**: `scf.in`  
**输出文件**: `scf.out`

**命令**:
```bash
cd <working_dir>
pw.x < scf.in > scf.out 2>&1
```

**说明**:
- 使用标准 QE 的 stdin 重定向
- 如果配置了 MPI：`mpirun -np <cores> pw.x < scf.in > scf.out 2>&1`

---

### 步骤 2: NSCF (Non-Self-Consistent Field)

**输入文件**: `nscf.in`  
**输出文件**: `nscf.out`

**命令**:
```bash
cd <working_dir>
pw.x < nscf.in > nscf.out 2>&1
```

**说明**:
- 使用标准 QE 的 stdin 重定向
- **重要**: NSCF 的 kpoints 列表会被提取并用于后续 Wannier90 步骤，保持完全相同的顺序

---

### 步骤 3: W90 Preprocessing (生成 .nnkp)

**输入文件**: `diamond.win` (seedname = "diamond")  
**输出文件**: `diamond.nnkp` (由 wannier90.x 生成)

**命令**:
```bash
cd <working_dir>
wannier90.x -pp diamond
```

**说明**:
- **不使用 stdin**，使用命令行参数
- 从输入文件名提取 seedname: `diamond.win` → seedname = "diamond"
- 命令格式: `wannier90.x -pp <seedname>`
- wannier90.x 读取 `<seedname>.win`，生成 `<seedname>.nnkp`
- 主要输出: `diamond.nnkp` (kpoints 和结构信息)
- 日志输出: `diamond.wout` (可能包含警告信息)

**如果配置了 MPI**:
```bash
mpirun -np <cores> wannier90.x -pp diamond
```

---

### 步骤 4: PW2Wannier90 (计算重叠矩阵)

**输入文件**: `pw2wan.in` (文件内容包含 `seedname = 'diamond'`)  
**输出文件**: 
- `pw2wan.out` (stdout)
- `pw2wan.stderr` (stderr)
- `diamond.mmn` (M 矩阵)
- `diamond.amn` (A 矩阵)
- `diamond.eig` (本征值)

**命令**:
```bash
cd <working_dir>
pw2wannier90.x < pw2wan.in > pw2wan.out 2> pw2wan.stderr
```

**说明**:
- **使用 stdin 重定向**（标准 QE 方式）
- 输入文件: `pw2wan.in` (标准 QE 命名)
- 输入文件内容中的 `seedname = 'diamond'` 控制输出文件名：
  - `diamond.mmn` - M 矩阵 (overlap matrices)
  - `diamond.amn` - A 矩阵 (projection matrices)
  - `diamond.eig` - 本征值文件
- stdout 写入: `pw2wan.out`
- stderr 写入: `pw2wan.stderr` (新增，用于调试)
- pw2wannier90.x 会读取 NSCF 的输出（通过 `prefix` 和 `outdir` 参数）和 `diamond.nnkp`（通过 `seedname`）

**如果配置了 MPI**:
```bash
mpirun -np <cores> pw2wannier90.x < pw2wan.in > pw2wan.out 2> pw2wan.stderr
```

**关键点**:
- `pw2wan.in` 中的 `seedname = 'diamond'` 必须与 `diamond.win` 中的 seedname 一致
- pw2wannier90 会验证 `.nnkp` 文件中的 kpoints 与 NSCF 的 kpoints 顺序一致
- 输出文件使用 seedname 作为前缀（`diamond.*`），但 stdout/stderr 使用输入文件名前缀（`pw2wan.*`）

---

### 步骤 5: W90 Run (生成 MLWFs)

**输入文件**: `diamond.win` (seedname = "diamond")  
**输出文件**: `diamond.wout` (主输出), `diamond.chk` (checkpoint)

**命令**:
```bash
cd <working_dir>
wannier90.x diamond
```

**说明**:
- **不使用 stdin**，使用命令行参数
- 从输入文件名提取 seedname: `diamond.win` → seedname = "diamond"
- 命令格式: `wannier90.x <seedname>`
- wannier90.x 读取:
  - `<seedname>.win` (输入参数)
  - `<seedname>.nnkp` (来自步骤 3)
  - `<seedname>.mmn`, `<seedname>.amn`, `<seedname>.eig` (来自步骤 4)
- 主输出: `diamond.wout` (包含收敛信息、Wannier 函数中心和展宽等)
- Checkpoint: `diamond.chk` (用于重启)
- 其他可能输出: `diamond.xsf`, `diamond_centres.xyz` 等（取决于 `.win` 中的设置）

**如果配置了 MPI**:
```bash
mpirun -np <cores> wannier90.x diamond
```

---

## 关键一致性要求

1. **Seedname 一致性**:
   - 步骤 3 和 5: `diamond.win` (文件名中的 seedname)
   - 步骤 4: `pw2wan.in` 文件内容中的 `seedname = 'diamond'`
   - 所有三个必须使用相同的 seedname ("diamond")

2. **Kpoints 顺序**:
   - 步骤 2 (NSCF) 的 kpoints 列表
   - 步骤 3 (W90 preproc) 生成的 `diamond.nnkp` 中的 kpoints
   - 必须完全相同的顺序（pw2wannier90 按 index 逐个比对）

3. **文件位置**:
   - 所有命令都在 `<working_dir>` 中执行
   - 输入文件必须在 `<working_dir>` 中
   - 输出文件写入 `<working_dir>`

4. **依赖关系**:
   - 步骤 3 需要: `diamond.win` (从步骤 1/2 的结构)
   - 步骤 4 需要: `pw2wan.in`, `diamond.nnkp` (步骤 3), NSCF 输出 (步骤 2)
   - 步骤 5 需要: `diamond.win`, `diamond.nnkp` (步骤 3), `diamond.mmn/amn/eig` (步骤 4)

---

## 实际示例 (Diamond Demo)

假设 `working_dir = /path/to/calc/raw`:

```bash
# Step 1: SCF
cd /path/to/calc/raw
pw.x < scf.in > scf.out 2>&1

# Step 2: NSCF
cd /path/to/calc/raw
pw.x < nscf.in > nscf.out 2>&1

# Step 3: W90 Preprocessing
cd /path/to/calc/raw
wannier90.x -pp diamond
# 生成: diamond.nnkp

# Step 4: PW2Wannier90
cd /path/to/calc/raw
pw2wannier90.x < pw2wan.in > pw2wan.out 2> pw2wan.stderr
# 生成: diamond.mmn, diamond.amn, diamond.eig

# Step 5: W90 Run
cd /path/to/calc/raw
wannier90.x diamond
# 生成: diamond.wout, diamond.chk
```

---

## 代码位置

- **命令构建**: `src/quantumvitas/core/engines/qe.py::build_command()`
- **stdin 判断**: `src/quantumvitas/core/engines/qe.py::uses_stdin()`
- **执行逻辑**: `src/quantumvitas/core/engines/qe_calculation.py::run_step()`
- **文件命名**: `src/quantumvitas/calculation/naming.py`

