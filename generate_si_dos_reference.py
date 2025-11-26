#!/usr/bin/env python3
"""
一次性生成 4_Si_DOS 的 reference 输出文件。
这个脚本应该只在本机运行一次，生成 reference 文件供测试使用。
"""

import sys
from pathlib import Path
import subprocess
import shutil

project_root = Path(__file__).parent

from quantumvitas.core.engines.qe import QuantumEspressoEngine, EngineConfig
from quantumvitas.io import QEInputParser, QEInputGenerator
# Import from new locations
from quantumvitas.core.engines import ensure_pseudopotentials
from tests.core.qe_step_runner import set_outdir_to_temp, set_pseudo_dir_to_temp
from tests.core import run_and_verify_step_with_assert

def generate_reference_outputs():
    """生成所有 reference 输出文件。"""
    
    # 设置路径
    si_dos_dir = project_root / "tests" / "integration" / "ci_test_data" / "4_Si_DOS"
    reference_out_dir = si_dos_dir / "reference_out"
    reference_out_dir.mkdir(exist_ok=True)
    
    # 创建临时工作目录
    work_dir = project_root / "temp" / "generate_reference"
    work_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("生成 4_Si_DOS Reference 输出文件")
    print("=" * 80)
    print(f"工作目录: {work_dir}")
    print(f"Reference 输出目录: {reference_out_dir}")
    print()
    
    # 初始化 QE Engine
    try:
        config = EngineConfig(name="qe")
        qe_engine = QuantumEspressoEngine(config)
        if not qe_engine.detect_executable("pw.x"):
            print("❌ pw.x 未找到。请确保 Quantum ESPRESSO 已正确安装")
            return False
        if not qe_engine.detect_executable("dos.x"):
            print("❌ dos.x 未找到。请确保 Quantum ESPRESSO 已正确安装")
            return False
        print(f"✓ QE Engine 初始化成功")
        print(f"  QE Home: {qe_engine.config.qe_home or 'auto-detected'}")
    except Exception as e:
        print(f"❌ QE Engine 初始化失败: {e}")
        print("请确保 Quantum ESPRESSO 已正确安装")
        return False
    
    # 确保 pseudopotentials 存在（从第一个输入文件）
    print("\n检查 pseudopotentials...")
    scf_file = si_dos_dir / "si.1_scf.in"
    ensure_pseudopotentials(scf_file, work_dir)
    print("✓ Pseudopotentials 准备完成")
    
    # Step 1: 运行 SCF 计算
    print("\n" + "=" * 80)
    print("Step 1: 运行 SCF 计算")
    print("=" * 80)
    
    scf_file = si_dos_dir / "si.1_scf.in"
    scf_input = QEInputParser.parse_file(scf_file)
    
    # 设置 pseudo_dir 和 outdir（统一使用 temp/pseudo 和 temp/outdir）
    set_outdir_to_temp(scf_input, project_root)
    set_pseudo_dir_to_temp(scf_input, project_root)
    
    # 确保 SCF 有 prefix（QE 需要它）
    scf_control = scf_input.get_namelist("control")
    if scf_control and not scf_control.get("prefix"):
        scf_control.parameters["prefix"] = "si"
    
    # 保存修改后的输入文件
    modified_scf = work_dir / "si.1_scf.in"
    QEInputGenerator.write_file(scf_input, modified_scf)
    
    # Run SCF using standardized step execution
    scf_reference = None  # No reference for generation
    try:
        scf_result = run_and_verify_step_with_assert(
            input_file=modified_scf,
            qe_engine=qe_engine,
            working_dir=work_dir,
            reference_file=scf_reference,
            category="4_Si_DOS",
            timeout=300,
            project_root=project_root
        )
    except AssertionError as e:
        print(f"❌ SCF 计算失败: {e}")
        return False
    
    if not scf_result.success:
        print(f"❌ SCF 计算失败: {scf_result.error}")
        return False
    
    # 复制输出文件到 reference_out
    scf_output = scf_result.output_file
    if scf_output.exists():
        reference_scf = reference_out_dir / "si.1_scf.out"
        shutil.copy2(scf_output, reference_scf)
        print(f"✓ SCF 输出已保存: {reference_scf}")
        
        # 显示能量信息
        content = reference_scf.read_text()
        import re
        energy_match = re.search(r"!\s+total energy\s+=\s+([-\d.]+)\s+Ry", content, re.IGNORECASE)
        if energy_match:
            print(f"  Total energy: {energy_match.group(1)} Ry")
    else:
        print(f"❌ SCF 输出文件不存在: {scf_output}")
        return False
    
    # 等待文件系统同步
    import time
    time.sleep(0.5)
    
    # Step 2: 运行 NSCF 计算
    print("\n" + "=" * 80)
    print("Step 2: 运行 NSCF 计算")
    print("=" * 80)
    
    nscf_file = si_dos_dir / "si.2_nscf.in"
    nscf_input = QEInputParser.parse_file(nscf_file)
    
    # 设置 pseudo_dir 和 outdir（统一使用 temp/pseudo 和 temp/outdir，与 SCF 一致）
    set_outdir_to_temp(nscf_input, project_root)
    set_pseudo_dir_to_temp(nscf_input, project_root)
    
    # 确保 NSCF 有 prefix（与 SCF 一致）
    scf_control = scf_input.get_namelist("control")
    nscf_control = nscf_input.get_namelist("control")
    if scf_control and nscf_control:
        scf_prefix = scf_control.get("prefix", "si")
        nscf_control.parameters["prefix"] = scf_prefix
        # NSCF 需要 restart_mode='restart' 来读取 SCF 的输出
        if nscf_control.get("restart_mode") == "from_scratch":
            nscf_control.parameters["restart_mode"] = "restart"
    
    # 保存修改后的输入文件
    modified_nscf = work_dir / "si.2_nscf.in"
    QEInputGenerator.write_file(nscf_input, modified_nscf)
    
    # Run NSCF using standardized step execution
    nscf_reference = None  # No reference for generation
    try:
        nscf_result = run_and_verify_step_with_assert(
            input_file=modified_nscf,
            qe_engine=qe_engine,
            working_dir=work_dir,
            reference_file=nscf_reference,
            category="4_Si_DOS",
            timeout=300,
            project_root=project_root
        )
    except AssertionError as e:
        print(f"❌ NSCF 计算失败: {e}")
        return False
    
    if not nscf_result.success:
        print(f"❌ NSCF 计算失败: {nscf_result.error}")
        return False
    
    # 复制输出文件到 reference_out
    nscf_output = nscf_result.output_file
    if nscf_output.exists():
        reference_nscf = reference_out_dir / "si.2_nscf.out"
        shutil.copy2(nscf_output, reference_nscf)
        print(f"✓ NSCF 输出已保存: {reference_nscf}")
        
        # 显示 Fermi energy 信息
        content = reference_nscf.read_text()
        import re
        fermi_patterns = [
            r"the\s+Fermi\s+energy\s+is\s+([-\d.]+)\s+ev",
            r"Fermi\s+energy\s*=\s*([-\d.]+)\s+Ry",
            r"the\s+Fermi\s+energy\s+is\s+([-\d.]+)\s+Ry",
        ]
        for pattern in fermi_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                fermi = float(match.group(1))
                if "ev" in pattern.lower():
                    fermi = fermi / 13.6057
                print(f"  Fermi energy: {fermi:.8f} Ry")
                break
    else:
        print(f"❌ NSCF 输出文件不存在: {nscf_output}")
        return False
    
    # Step 3: 运行 DOS 计算
    print("\n" + "=" * 80)
    print("Step 3: 运行 DOS 计算")
    print("=" * 80)
    
    dos_file = si_dos_dir / "si.3_dos.in"
    dos_input = QEInputParser.parse_file(dos_file)
    dos_namelist = dos_input.get_namelist("dos")
    
    # 获取 outdir（使用 temp/outdir，与 SCF/NSCF 一致）
    temp_outdir = project_root / "temp" / "outdir"
    temp_outdir.mkdir(parents=True, exist_ok=True)
    
    # 手动创建 DOS 输入文件（dos.x 对输入格式敏感）
    prefix = dos_namelist.get("prefix", "si") if dos_namelist else "si"
    fildos = dos_namelist.get("fildos", "si.dos.dat") if dos_namelist else "si.dos.dat"
    emin = dos_namelist.get("emin", -9.0) if dos_namelist else -9.0
    emax = dos_namelist.get("emax", 16.0) if dos_namelist else 16.0
    
    dos_input_content = f"""&DOS
    prefix='{prefix}'
    outdir='{temp_outdir.absolute()}'
    fildos='{fildos}'
    emin={emin}
    emax={emax}
/
"""
    modified_dos = work_dir / "si.3_dos.in"
    modified_dos.write_text(dos_input_content)
    print(f"✓ DOS 输入文件已创建: {modified_dos}")
    
    # 构建 dos.x 命令
    dos_exe = qe_engine.get_executable_path("dos.x")
    dos_command = [str(dos_exe), "-inp", str(modified_dos)]
    
    # 运行 dos.x
    import os
    temp_pseudo_dir = project_root / "temp" / "pseudo"
    temp_pseudo_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['ESPRESSO_PSEUDO'] = str(temp_pseudo_dir.absolute())
    
    print(f"运行命令: {' '.join(dos_command)}")
    result = subprocess.run(
        dos_command,
        cwd=str(work_dir),
        capture_output=True,
        text=True,
        timeout=60,
        env=env
    )
    
    if result.returncode != 0:
        print(f"❌ DOS 计算失败 (return code: {result.returncode})")
        print(f"stdout: {result.stdout[:1000]}")
        print(f"stderr: {result.stderr[:500]}")
        return False
    
    # 保存 DOS 输出
    dos_output_file = work_dir / f"{prefix}.dos.out"
    dos_output_file.write_text(result.stdout)
    
    reference_dos = reference_out_dir / "si.3_dos.out"
    shutil.copy2(dos_output_file, reference_dos)
    print(f"✓ DOS 输出已保存: {reference_dos}")
    
    # 检查是否有 dos.dat 文件（在 outdir 或工作目录中）
    dos_dat_file = temp_outdir / fildos
    if not dos_dat_file.exists():
        dos_dat_file = work_dir / fildos
    if dos_dat_file.exists():
        reference_dos_dat = reference_out_dir / "si.dos.dat"
        shutil.copy2(dos_dat_file, reference_dos_dat)
        print(f"✓ DOS 数据文件已保存: {reference_dos_dat}")
    else:
        print(f"⚠️  DOS 数据文件未找到: {fildos}")
    
    print("\n" + "=" * 80)
    print("✅ 所有 Reference 文件生成完成！")
    print("=" * 80)
    print(f"\n生成的文件:")
    print(f"  - {reference_out_dir / 'si.1_scf.out'}")
    print(f"  - {reference_out_dir / 'si.2_nscf.out'}")
    print(f"  - {reference_out_dir / 'si.3_dos.out'}")
    if (reference_out_dir / "si.dos.dat").exists():
        print(f"  - {reference_out_dir / 'si.dos.dat'}")
    
    return True

if __name__ == "__main__":
    success = generate_reference_outputs()
    sys.exit(0 if success else 1)

