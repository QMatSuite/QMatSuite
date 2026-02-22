#!/usr/bin/env python3
"""
Minimal reproduction script for precision apply breaking bands_pw K_POINTS.

This script demonstrates the bug where applying precision preset to bands_pw
steps clears or overwrites the K_POINTS (kpath) even though bands_pw should
preserve it (accepts_kmesh=False).

Run: python audit_precision_bands_kpoints.py
"""

import tempfile
import shutil
from pathlib import Path
import yaml

# Import the functions we need to test
from qmatsuite.presets.integration import apply_presets_to_step
from qmatsuite.presets.precision import PrecisionAdvisor, PrecisionOption
from qmatsuite.presets.receivers import get_precision_receiver_spec
from qmatsuite.presets.compiler import compile_precision_from_advice
from qmatsuite.presets.integration import DIMENSION_OWNED_KEYS, DIMENSION_PRECISION


def main():
    print("=" * 80)
    print("AUDIT: Precision Apply Breaking bands_pw K_POINTS")
    print("=" * 80)
    print()
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    try:
        project_root = Path(temp_dir) / "test_project"
        project_root.mkdir()
        calc_dir = project_root / "calculations" / "test_calc"
        calc_dir.mkdir(parents=True)
        steps_dir = calc_dir / "steps"
        steps_dir.mkdir()
        
        # Create project.qms.yml
        project_qms_yml = project_root / "project.qms.yml"
        project_qms_yml.write_text(yaml.safe_dump({
            "name": "Test Project",
            "version": "1.0",
        }))
        
        # Create calculation.yaml
        calc_yaml = calc_dir / "calculation.yaml"
        calc_yaml.write_text(yaml.safe_dump({
            "name": "Test Calculation",
            "species_map": {"Si": {"pseudo_sha256": "test_sha"}},
        }))
        
        # Create bands_pw step with kpath K_POINTS
        bands_step = calc_dir / "steps" / "bands.step.yaml"
        original_kpoints = {
            "option": "crystal_b",
            "data": [
                [0.0, 0.0, 0.0, 1.0],  # Gamma point
                [0.5, 0.5, 0.5, 1.0],  # L point
            ],
        }
        original_content = {
            "step_type": "bands_pw",
            "parameters": {},
            "cards": {
                "K_POINTS": original_kpoints,
            },
        }
        bands_step.write_text(yaml.safe_dump(original_content))
        
        print("Phase 1: Initial State")
        print("-" * 80)
        print(f"Step type: bands_pw")
        print(f"Original K_POINTS:")
        print(yaml.safe_dump(original_kpoints, default_flow_style=False))
        print()
        
        # Check receiver spec
        precision_spec = get_precision_receiver_spec("bands_pw")
        print("Precision Receiver Spec for bands_pw:")
        print(f"  accepts_kmesh: {precision_spec.accepts_kmesh}")
        print(f"  accepts_cutoffs: {precision_spec.accepts_cutoffs}")
        print(f"  accepts_conv_thr: {precision_spec.accepts_conv_thr}")
        print(f"  kmesh_strategy: {precision_spec.kmesh_strategy}")
        print()
        
        # Check ownership
        print("DIMENSION_OWNED_KEYS for precision:")
        precision_owned = DIMENSION_OWNED_KEYS[DIMENSION_PRECISION]
        print(f"  {precision_owned}")
        print(f"  cards.K_POINTS owned by precision: {'K_POINTS' in precision_owned.get('cards', set())}")
        print()
        
        # Create PrecisionAdvisor and get advice
        species_map = {"Si": {"pseudo_sha256": "test_sha"}}
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        advisor = PrecisionAdvisor(species_map, lattice_matrix=lattice, repo_root=project_root)
        precision_advice = advisor.advise_for_step(PrecisionOption.MED, "bands_pw")
        
        print("Phase 2: Compile Precision")
        print("-" * 80)
        precision_compiled = compile_precision_from_advice(precision_advice)
        print("compile_precision_from_advice output:")
        print(f"  SYSTEM keys: {list(precision_compiled.get('SYSTEM', {}).keys())}")
        print(f"  ELECTRONS keys: {list(precision_compiled.get('ELECTRONS', {}).keys())}")
        print(f"  K_POINTS_CARD present: {'K_POINTS_CARD' in precision_compiled}")
        if "K_POINTS_CARD" in precision_compiled:
            print(f"  K_POINTS_CARD content:")
            print(yaml.safe_dump(precision_compiled["K_POINTS_CARD"], default_flow_style=False))
        print()
        
        # Simulate what apply_presets_to_step does
        print("Phase 3: Apply Logic Simulation")
        print("-" * 80)
        print("Step 1: Check if kmesh should be applied")
        should_apply_kmesh = precision_spec.accepts_kmesh and precision_spec.kmesh_strategy != "none"
        print(f"  accepts_kmesh && kmesh_strategy != 'none': {should_apply_kmesh}")
        compiled_kpoints_card = None
        if should_apply_kmesh:
            compiled_kpoints_card = precision_compiled.get("K_POINTS_CARD")
            print(f"  → compiled_kpoints_card = {compiled_kpoints_card}")
        else:
            print(f"  → compiled_kpoints_card = None (NOT set)")
        print()
        
        print("Step 2: Deletion logic")
        print("  DIMENSION_PRECISION owns cards.K_POINTS")
        print("  Line 449 condition: section != 'cards' OR dimension == DIMENSION_PRECISION")
        print("  → K_POINTS will be added to keys_to_remove['cards']")
        print("  Line 457: existing_cards.pop('K_POINTS', None)")
        print("  → K_POINTS is DELETED from existing_cards")
        print()
        
        print("Step 3: Merge logic")
        print(f"  compiled_kpoints_card is None: {compiled_kpoints_card is None}")
        if compiled_kpoints_card is not None:
            print("  → existing_cards['K_POINTS'] = compiled_kpoints_card (OVERWRITE)")
        else:
            print("  → K_POINTS is NOT restored (CLEARED)")
        print()
        
        # Actually apply
        print("Phase 4: Actual Apply")
        print("-" * 80)
        apply_presets_to_step(
            bands_step,
            {"precision": "med"},
            precision_advice=precision_advice,
        )
        
        # Read result
        result_content = yaml.safe_load(bands_step.read_text())
        result_kpoints = result_content.get("cards", {}).get("K_POINTS")
        
        print("After apply_presets_to_step:")
        print(f"  K_POINTS present: {result_kpoints is not None}")
        if result_kpoints:
            print(f"  K_POINTS content:")
            print(yaml.safe_dump(result_kpoints, default_flow_style=False))
        else:
            print(f"  K_POINTS: MISSING (cleared)")
        print()
        
        print("Phase 5: Root Cause Summary")
        print("-" * 80)
        print("BUG IDENTIFIED:")
        print("  1. DIMENSION_OWNED_KEYS declares precision owns cards.K_POINTS")
        print("  2. Deletion logic (line 449) adds K_POINTS to removal list")
        print("  3. Line 457 removes K_POINTS from existing_cards")
        print("  4. For bands_pw, accepts_kmesh=False, so compiled_kpoints_card = None")
        print("  5. Line 463-464 only restores if compiled_kpoints_card is not None")
        print("  6. RESULT: K_POINTS is deleted but never restored → CLEARED")
        print()
        print("TWO SCENARIOS:")
        print("  A. CLEAR: compiled_kpoints_card = None → K_POINTS deleted, not restored")
        print("  B. OVERWRITE: If compiled_kpoints_card was set → K_POINTS replaced with mesh")
        print()
        
    finally:
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()

