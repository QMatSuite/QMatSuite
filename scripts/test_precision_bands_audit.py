#!/usr/bin/env python3
"""最小复现: precision apply 对 bands_pw K_POINTS 的影响"""

import tempfile
import shutil
from pathlib import Path
import yaml

from quantumvitas.presets.integration import apply_presets_to_step
from quantumvitas.presets.precision import PrecisionAdvisor, PrecisionOption
from quantumvitas.presets.compiler import compile_precision_from_advice
from quantumvitas.presets.receivers import get_precision_receiver_spec

# 创建临时目录
temp_dir = tempfile.mkdtemp()
try:
    project_root = Path(temp_dir) / "test_project"
    project_root.mkdir()
    calc_dir = project_root / "calculations" / "test_calc"
    calc_dir.mkdir(parents=True)
    steps_dir = calc_dir / "steps"
    steps_dir.mkdir()
    
    # 创建 project.qv.yml
    (project_root / "project.qv.yml").write_text(yaml.safe_dump({
        "name": "Test Project",
        "version": "1.0",
    }))
    
    # 创建 calculation.yaml
    (calc_dir / "calculation.yaml").write_text(yaml.safe_dump({
        "name": "Test Calculation",
        "species_map": {"Si": {"pseudo_sha256": "test_sha"}},
    }))
    
    # 创建 bands_pw step with kpath
    bands_step = calc_dir / "steps" / "bands.step.yaml"
    original_kpoints = {
        "option": "crystal_b",
        "data": [
            [0.0, 0.0, 0.0, 1.0],
            [0.5, 0.5, 0.5, 1.0],
        ],
    }
    original_content = {
        "step_type": "bands_pw",
        "parameters": {},
        "cards": {"K_POINTS": original_kpoints},
    }
    bands_step.write_text(yaml.safe_dump(original_content))
    
    print("=" * 80)
    print("BEFORE APPLY")
    print("=" * 80)
    before_content = yaml.safe_load(bands_step.read_text())
    print("K_POINTS:", yaml.safe_dump(before_content["cards"]["K_POINTS"], default_flow_style=False))
    
    # 检查 receiver spec
    spec = get_precision_receiver_spec("bands_pw")
    print(f"\nReceiver spec: accepts_kmesh={spec.accepts_kmesh}, kmesh_strategy={spec.kmesh_strategy}")
    
    # 创建 advisor 和 advice
    species_map = {"Si": {"pseudo_sha256": "test_sha"}}
    lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
    advisor = PrecisionAdvisor(species_map, lattice_matrix=lattice, repo_root=project_root)
    precision_advice = advisor.advise_for_step(PrecisionOption.MED, "bands_pw")
    
    # 编译 precision patch
    precision_compiled = compile_precision_from_advice(precision_advice)
    print(f"\nCompiled patch K_POINTS_CARD present: {'K_POINTS_CARD' in precision_compiled}")
    if "K_POINTS_CARD" in precision_compiled:
        print("K_POINTS_CARD:", yaml.safe_dump(precision_compiled["K_POINTS_CARD"], default_flow_style=False))
    
    # 检查是否会设置 compiled_kpoints_card
    compiled_kpoints_card = None
    if spec.accepts_kmesh and spec.kmesh_strategy != "none":
        compiled_kpoints_card = precision_compiled.get("K_POINTS_CARD")
    print(f"\ncompiled_kpoints_card will be set: {compiled_kpoints_card is not None}")
    
    # Apply
    print("\n" + "=" * 80)
    print("APPLYING PRECISION")
    print("=" * 80)
    apply_presets_to_step(
        bands_step,
        {"precision": "med"},
        precision_advice=precision_advice,
    )
    
    # 读取结果
    print("\n" + "=" * 80)
    print("AFTER APPLY")
    print("=" * 80)
    after_content = yaml.safe_load(bands_step.read_text())
    after_kpoints = after_content.get("cards", {}).get("K_POINTS")
    print(f"K_POINTS present: {after_kpoints is not None}")
    if after_kpoints:
        print("K_POINTS:", yaml.safe_dump(after_kpoints, default_flow_style=False))
    else:
        print("K_POINTS: MISSING (cleared)")
    
    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    print("1. Receiver spec rejects kmesh → compiled_kpoints_card = None")
    print("2. Deletion logic removes K_POINTS (ownership)")
    print("3. Restore logic doesn't run (compiled_kpoints_card is None)")
    print("4. Result: K_POINTS cleared")
    
finally:
    shutil.rmtree(temp_dir)

