# RELAX 三引擎研究报告

**Version**: 1.0.0
**Date**: 2026-01-18
**Author**: Opus (Senior Architect)

---

## 1. 目标与背景

本文档为"GEN step 统一为 relax（一条）并真实跑通 QE/ORCA/PySCF 的 relax"功能提供三引擎的详细技术研究。

### 1.1 核心目标

- 统一 GEN step 为单一的 `relax` public type
- 真实调用三引擎执行几何优化
- 解析输出并生成 `current.json`
- 验证 canonicalize + SHA 流程

### 1.2 GEN Step 语义

| Engine | Public Type | 实际实现 | Option/配置 |
|--------|-------------|----------|-------------|
| QE | `relax` | `pw.x` with `calculation='relax'` or `'vc-relax'` | `relax.vc=true` → vc-relax |
| ORCA | `relax` | `! Opt` keyword in input | 分子级优化 |
| PySCF | `relax` | `pyscf.geomopt` module | berny_solver / geometric_solver |

---

## 2. Quantum ESPRESSO (QE) 几何优化

### 2.1 输入控制

**权威来源**: [QE pw.x input description](https://www.quantum-espresso.org/Doc/INPUT_PW.html)

QE 几何优化由 `&CONTROL` 中的 `calculation` 参数控制：

```fortran
&CONTROL
  calculation = 'relax'    ! 优化原子位置，固定晶胞
  ! 或
  calculation = 'vc-relax' ! 同时优化原子位置和晶胞
  
  etot_conv_thr = 1.0e-5   ! 能量收敛阈值 (Ry)
  forc_conv_thr = 1.0e-4   ! 力收敛阈值 (Ry/Bohr)
/

&IONS
  ion_dynamics = 'bfgs'    ! 优化算法
/

&CELL                      ! 仅 vc-relax 需要
  cell_dynamics = 'bfgs'
  press = 0.0              ! 目标压力 (kbar)
  press_conv_thr = 0.5     ! 压力收敛阈值 (kbar)
/
```

### 2.2 输出文件与解析策略

**输出位置**: stdout (`*.out` 文件)

**解析策略**: 使用现有 `read_final_geometry_from_output_text()` 函数

**输出格式示例** (在 stdout 中):
```
     Begin final coordinates
         new unit-cell volume =    123.456 a.u.^3 (    18.289 Ang^3 )
         density =      2.329 g/cm^3

CELL_PARAMETERS (alat=  7.26553535)
   0.707106781  -0.000000000   0.000000000
   0.353553391   0.612372435   0.000000000
   0.353553391   0.204124145   0.577350269

ATOMIC_POSITIONS (alat)
Si   0.000000000   0.000000000   0.000000000
Si   0.250000000   0.144337567   0.204124145
     End final coordinates
```

### 2.3 现有代码落点

**已实现的解析器**: `src/qmatsuite/calculation/geometry.py`

```python
# 已有函数
def read_final_geometry_from_output_text(text: str) -> Tuple[QEGeometrySnapshot, List[str]]
def structure_from_qe_geometry_snapshot(snapshot, species) -> PMGStructure
```

**关键调用点**:
1. `read_final_geometry_from_output_text()` - 解析 stdout
2. `structure_from_qe_geometry_snapshot()` - 转换为 pymatgen Structure
3. 内部调用 `canonicalize_structure_in_place()` - 统一的 canonicalize 入口

### 2.4 最小可运行示例

```fortran
&CONTROL
  calculation = 'relax'
  prefix = 'si'
  pseudo_dir = './pseudo/'
  outdir = './outdir/'
  etot_conv_thr = 1.0e-4
  forc_conv_thr = 1.0e-3
/
&SYSTEM
  ibrav = 2
  celldm(1) = 10.2
  nat = 2
  ntyp = 1
  ecutwfc = 30.0
/
&ELECTRONS
  conv_thr = 1.0e-6
/
&IONS
  ion_dynamics = 'bfgs'
/
ATOMIC_SPECIES
Si  28.086  Si.pbe-n-rrkjus_psl.1.0.0.UPF

ATOMIC_POSITIONS (crystal)
Si  0.00  0.00  0.00
Si  0.25  0.25  0.25

K_POINTS automatic
4 4 4 0 0 0
```

### 2.5 Writer/Parser 需要做的事

**Writer** (`QE input generation`):
- 根据 `relax.vc` option 设置 `calculation = 'relax'` 或 `'vc-relax'`
- 添加 `&IONS` block with `ion_dynamics = 'bfgs'`
- 若 vc-relax，添加 `&CELL` block

**Parser** (`execution/handlers.py` 或类似):
- 调用 `read_final_geometry_from_output_text(output_text)`
- 调用 `structure_from_qe_geometry_snapshot(snapshot, species)`
- 调用 `write_generated_structure()` 写入 `current.json`

---

## 3. ORCA 几何优化

### 3.1 输入控制

**权威来源**: [ORCA Manual 6.0 - Geometry Optimizations](https://www.faccts.de/docs/orca/6.0/manual/contents/detailed/geomopt.html)

ORCA 几何优化使用 `! Opt` 关键词：

```
! B3LYP def2-SVP Opt
! 或 TightOpt / VeryTightOpt 用于更严格收敛

%geom
  MaxIter 100
  coordsys redundant   # 或 cartesian
  # 约束
  Constraints
    { C 0 C }          # 固定原子 0
  end
end

* xyz 0 1
O   0.000000   0.000000   0.000000
H   0.757160   0.000000   0.586260
H  -0.757160   0.000000   0.586260
*
```

### 3.2 输出文件与解析策略

**权威来源**: ORCA 教程确认输出文件命名

**输出文件**:
- `basename.xyz` - 最终优化后的结构（XYZ 格式）
- `basename_trj.xyz` - 优化轨迹（每步的结构）
- `basename.out` - 完整输出日志
- `basename.property.txt` - 属性摘要

**解析策略**:
1. **首选**: 读取 `basename.xyz`（最终结构）
2. **备选**: 从 `basename.out` 解析 "FINAL SINGLE POINT ENERGY" 后的坐标块

**basename.xyz 格式**:
```
3
Coordinates from ORCA-job basename E -76.123456
O     0.000000     0.000000     0.117000
H     0.757160     0.000000    -0.468000
H    -0.757160     0.000000    -0.468000
```

### 3.3 现有代码落点

**ORCA Engine**: `src/qmatsuite/engine/orca_engine.py`
- `ORCAEngine.run_chain()` - 执行 ORCA 作业
- `ORCAInputCompiler.compile()` - 生成输入文件

**需新增**:
- `parse_orca_xyz()` - 解析 `basename.xyz` 文件
- 在 `orca_opt` 支持 step type

### 3.4 最小可运行示例

```
! HF def2-SVP Opt
%maxcore 2000

%geom
  MaxIter 50
end

* xyz 0 1
H   0.000000   0.000000   0.000000
H   0.740000   0.000000   0.000000
*
```

### 3.5 Writer/Parser 需要做的事

**Writer** (`engines/orca/input_compiler.py`):
- 检测 relax step，添加 `Opt` 关键词
- 设置 `%geom` block 的优化参数

**Parser** (新增):
```python
# execution/orca_relax_parser.py (新增)
def parse_orca_optimized_xyz(xyz_path: Path) -> PMGMolecule:
    """Parse ORCA's basename.xyz output file."""
    from pymatgen.core import Molecule
    return Molecule.from_file(xyz_path)
```

---

## 4. PySCF 几何优化

### 4.1 输入控制

**权威来源**: [PySCF Geometry Optimization](https://pyscf.org/user/geomopt.html)

PySCF 通过 `pyscf.geomopt` 模块提供几何优化：

```python
from pyscf import gto, scf
from pyscf.geomopt.geometric_solver import optimize

mol = gto.M(
    atom = '''
    O  0.000000  0.000000  0.117000
    H  0.757160  0.000000 -0.468000
    H -0.757160  0.000000 -0.468000
    ''',
    basis = 'cc-pvdz',
)

mf = scf.RHF(mol)
mol_eq = optimize(mf, maxsteps=100)

# 提取优化后的坐标
final_coords = mol_eq.atom_coords()  # numpy array, Bohr
final_symbols = [mol_eq.atom_symbol(i) for i in range(mol_eq.natm)]
```

### 4.2 Solver 选择与依赖

**两种 solver**:

1. **geometric_solver** (推荐):
   - 依赖: `pip install geometric`
   - 更稳定，支持多种坐标系
   - 默认选择

2. **berny_solver**:
   - 依赖: `pip install pyberny`
   - 纯 Python
   - 备选方案

**测试环境策略**:
1. 首选 `geometric` (已被 PySCF 官方推荐)
2. 若不可用，尝试 `berny`
3. 两者都不可用，测试标记 `xfail` 或 `skip`

```python
# 检测可用 solver
def get_available_solver():
    try:
        from pyscf.geomopt.geometric_solver import optimize
        return "geometric"
    except ImportError:
        pass
    try:
        from pyscf.geomopt.berny_solver import optimize
        return "berny"
    except ImportError:
        pass
    return None
```

### 4.3 从 mol_eq 提取几何

```python
from pymatgen.core import Molecule

def mol_eq_to_pmg_molecule(mol_eq) -> Molecule:
    """Convert PySCF Mole to pymatgen Molecule."""
    coords_bohr = mol_eq.atom_coords()  # in Bohr
    coords_ang = coords_bohr * 0.52917721092  # Bohr to Angstrom
    
    symbols = [mol_eq.atom_symbol(i) for i in range(mol_eq.natm)]
    
    return Molecule(
        species=symbols,
        coords=coords_ang,
        charge=mol_eq.charge,
        spin_multiplicity=mol_eq.spin + 1,
    )
```

### 4.4 现有代码落点

**PySCF Engine**: `src/qmatsuite/engine/pyscf_engine.py`
**PySCF Runner**: `src/qmatsuite/engines/pyscf/runner.py`

**需新增**:
- 在 runner 中添加 `pyscf_geomopt` step type 处理
- 或统一为 `pyscf_relax` machine type

### 4.5 最小可运行示例

```python
# engines/pyscf/relax_handler.py (新增)
def run_pyscf_relax(params: dict, mol: Molecule) -> Molecule:
    from pyscf import gto, scf
    
    # Build PySCF Mole
    atom_str = "\n".join(
        f"{site.species_string} {site.x:.6f} {site.y:.6f} {site.z:.6f}"
        for site in mol
    )
    pyscf_mol = gto.M(
        atom=atom_str,
        basis=params.get("basis", "sto-3g"),
        charge=mol.charge,
        spin=mol.spin_multiplicity - 1,
    )
    
    # Run SCF
    method = params.get("method", "rhf")
    if method.lower() in ("rhf", "hf"):
        mf = scf.RHF(pyscf_mol)
    else:
        mf = scf.RKS(pyscf_mol)
        mf.xc = params.get("xc", "pbe")
    
    # Geometry optimization
    try:
        from pyscf.geomopt.geometric_solver import optimize
    except ImportError:
        from pyscf.geomopt.berny_solver import optimize
    
    mol_eq = optimize(mf, maxsteps=params.get("maxsteps", 50))
    
    return mol_eq_to_pmg_molecule(mol_eq)
```

### 4.6 Writer/Parser 需要做的事

**Writer** (不适用 - PySCF 不需要输入文件):
- 在 `job_chain.json` 中传递参数

**Parser** (在 runner 中):
- 执行优化后调用 `mol_eq_to_pmg_molecule()`
- 结果写入 `results.json`

---

## 5. 统一 Canonicalize 入口

### 5.1 现有入口点

**唯一入口**: `src/qmatsuite/analysis/structure_viz.py`

```python
def canonicalize_structure_in_place(structure: Structure) -> None:
    """
    Canonicalize structure in-place.
    Wraps fractional coordinates to [0, 1) interval.
    """
```

**SHA 入口**: `src/qmatsuite/core/structure_fingerprint.py`

```python
def structure_fingerprint(structure: Structure, tol: float = 1e-5) -> str:
    """
    Generate stable fingerprint (SHA256) for a structure.
    
    Uses canonicalization with tolerance before hashing.
    """
```

### 5.2 在 RELAX 中的调用路径

```
QE:     read_final_geometry_from_output_text()
        ↓
        structure_from_qe_geometry_snapshot()  # 内部调用 canonicalize
        ↓
        write_generated_structure()

ORCA:   parse_orca_optimized_xyz()
        ↓
        canonicalize_structure_in_place(mol)   # 显式调用
        ↓
        write_generated_structure()

PySCF:  mol_eq_to_pmg_molecule()
        ↓
        canonicalize_structure_in_place(mol)   # 显式调用
        ↓
        write_generated_structure()
```

---

## 6. 依赖与测试环境

### 6.1 QE

- **依赖**: QE 安装 (`pw.x` 可执行)
- **CI 策略**: 使用内部 QE bundle 或 skip
- **测试**: 小体系 Si (2 atoms), low ecutwfc (~30 Ry), 限制 nstep

### 6.2 ORCA

- **依赖**: ORCA 安装 (`orca` 可执行)
- **CI 策略**: 需要 ORCA license，标记 `@pytest.mark.orca`
- **测试**: H2 分子, HF/STO-3G, MaxIter 10

### 6.3 PySCF

- **依赖**: 
  - `pyscf` (必需)
  - `geometric` 或 `pyberny` (至少一个)
- **CI 策略**: 
  - 检查 `geometric` 可用性
  - 若不可用，skip 或 xfail
- **测试**: H2 分子, HF/STO-3G, maxsteps 10

---

## 7. 参考文献

1. [Quantum ESPRESSO pw.x Input Description](https://www.quantum-espresso.org/Doc/INPUT_PW.html)
2. [ORCA 6.0 Manual - Geometry Optimizations](https://www.faccts.de/docs/orca/6.0/manual/contents/detailed/geomopt.html)
3. [PySCF Geometry Optimization User Guide](https://pyscf.org/user/geomopt.html)
4. [AiiDA Common Relax Workflows](https://aiida-common-workflows.readthedocs.io/en/latest/workflows/base/relax/)
5. QMatSuite 现有代码: `src/qmatsuite/calculation/geometry.py`

