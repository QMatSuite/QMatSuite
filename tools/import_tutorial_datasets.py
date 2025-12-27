#!/usr/bin/env python3
"""
Import tutorial datasets from tests/data/ into demo project snapshots.

This script:
1. Scans tests/data/ for folders 0_* through 19_*
2. For each dataset, finds .in files in execution order
3. Extracts structure and parameters from inputs
4. Maps pseudopotentials from project/pseudo or repo pseudo/
5. Creates calculation structure using existing QMatSuite APIs
6. Validates by round-tripping (parse -> export -> compare)
7. Generates demo snapshots in demos/qe_tutorials/
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Add src to path for imports
import sys
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from quantumvitas.io import QEInputParser, QEInputGenerator, read_structure, write_structure
from quantumvitas.io.model import QECardType, QEInput
from quantumvitas.calculation.importers import build_calculation_from_qe_inputs
from quantumvitas.project.snapshot import ProjectSnapshot, export_project_to_snapshot
from quantumvitas.calculation.structure_steps import StructureStepSpec, generate_qe_input_from_spec
from quantumvitas.core.resources import generate_resource_id, meta_from_name


@dataclass
class DatasetInfo:
    """Information about a tutorial dataset."""
    folder_name: str
    folder_path: Path
    input_files: List[Path] = field(default_factory=list)
    subcases: List[Tuple[str, Path]] = field(default_factory=list)  # (subcase_name, subcase_path)
    reference_out_dir: Optional[Path] = None


@dataclass
class ValidationResult:
    """Result of round-trip validation."""
    success: bool
    differences: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class DemoResult:
    """Result of creating a demo from a dataset."""
    demo_name: str
    demo_path: Path
    success: bool
    validation: Optional[ValidationResult] = None
    missing_pseudos: List[str] = field(default_factory=list)
    error: Optional[str] = None
    step_count: int = 0


def find_repo_root() -> Path:
    """Find the repository root directory."""
    current = Path(__file__).parent.parent
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / "project.qv.yml").exists():
            return current
        current = current.parent
    return Path(__file__).parent.parent


def discover_datasets(tests_data_dir: Path) -> List[DatasetInfo]:
    """
    Discover all tutorial datasets in tests/data/.
    
    Looks for folders matching pattern 0_* through 19_*.
    Handles subcases (e.g., 14_DFT_plus_U_NiO/1_noU, 2_addU).
    """
    datasets = []
    
    # Find main dataset folders (0_* through 19_*)
    for folder in sorted(tests_data_dir.iterdir()):
        if not folder.is_dir():
            continue
        
        folder_name = folder.name
        # Match pattern: number_* (e.g., 0_Si_scf, 14_DFT_plus_U_NiO)
        match = re.match(r'^(\d+)_(.+)$', folder_name)
        if not match:
            continue
        
        dataset_num = int(match.group(1))
        if dataset_num < 0 or dataset_num > 19:
            continue
        
        # Check for subcases (e.g., 14_DFT_plus_U_NiO/1_noU)
        subcases = []
        input_files = []
        reference_out_dir = None
        
        # Look for subcase folders (numbered subdirectories)
        subcase_dirs = sorted([d for d in folder.iterdir() if d.is_dir() and re.match(r'^\d+_', d.name)])
        
        if subcase_dirs:
            # Has subcases - each subcase is a separate dataset
            for subcase_dir in subcase_dirs:
                subcase_name = subcase_dir.name
                subcase_inputs = sorted(subcase_dir.glob("*.in"))
                if subcase_inputs:
                    subcases.append((subcase_name, subcase_dir))
        else:
            # No subcases - main folder contains inputs
            input_files = sorted(folder.glob("*.in"))
            # Check for reference output directories
            for ref_dir_name in ["reference_out", "reference_output", "reference", "reference_outputs"]:
                ref_dir = folder / ref_dir_name
                if ref_dir.exists() and ref_dir.is_dir():
                    reference_out_dir = ref_dir
                    break
        
        if subcases:
            # Create separate dataset info for each subcase
            for subcase_name, subcase_path in subcases:
                subcase_inputs = sorted(subcase_path.glob("*.in"))
                if subcase_inputs:
                    # Create a combined name for the demo
                    # Extract descriptive part after the number prefix
                    desc_part = folder_name.split('_', 1)[1] if '_' in folder_name else folder_name
                    demo_name = f"{dataset_num}_{desc_part}__{subcase_name}"
                    datasets.append(DatasetInfo(
                        folder_name=demo_name,
                        folder_path=subcase_path,
                        input_files=subcase_inputs,
                        subcases=[],
                        reference_out_dir=subcase_path / "reference_out" if (subcase_path / "reference_out").exists() else None
                    ))
        elif input_files:
            # Single dataset without subcases
            datasets.append(DatasetInfo(
                folder_name=folder_name,
                folder_path=folder,
                input_files=input_files,
                subcases=[],
                reference_out_dir=reference_out_dir
            ))
    
    return datasets


def sort_input_files_by_execution_order(files: List[Path]) -> List[Path]:
    """
    Sort input files by execution order.
    
    Files are typically named like:
    - si.1_scf.in, si.2_nscf.in, si.3_dos.in
    - h2o.1_relax.in, h2o.2_ph.in
    
    We extract the numeric prefix and sort by it.
    """
    def extract_order(filepath: Path) -> Tuple[int, str]:
        stem = filepath.stem
        # Try to match pattern: name.number_step.in
        match = re.match(r'^(.+)\.(\d+)_(.+)$', stem)
        if match:
            return (int(match.group(2)), stem)
        # Try pattern: name.number.in
        match = re.match(r'^(.+)\.(\d+)$', stem)
        if match:
            return (int(match.group(2)), stem)
        # Fallback: use filename
        return (999, stem)
    
    return sorted(files, key=extract_order)


def extract_pseudopotential_names(qe_input: QEInput) -> List[str]:
    """Extract pseudopotential filenames from ATOMIC_SPECIES card."""
    species_card = qe_input.get_card(QECardType.ATOMIC_SPECIES)
    if not species_card:
        return []
    
    pseudo_names = []
    for line in species_card.data:
        if isinstance(line, list) and len(line) >= 3:
            # Format: element mass pseudo_filename
            pseudo_name = line[2].strip()
            pseudo_names.append(pseudo_name)
        elif isinstance(line, str):
            # Try to parse string format
            parts = line.split()
            if len(parts) >= 3:
                pseudo_names.append(parts[2].strip())
    
    return pseudo_names


def find_pseudopotential_file(pseudo_name: str, search_dirs: List[Path]) -> Optional[Path]:
    """
    Find a pseudopotential file in the search directories.
    
    Args:
        pseudo_name: Filename of the pseudopotential
        search_dirs: List of directories to search
        
    Returns:
        Path to the pseudopotential file, or None if not found
    """
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        # Try exact match
        pp_path = search_dir / pseudo_name
        if pp_path.exists():
            return pp_path
        # Try case-insensitive match
        for existing_file in search_dir.iterdir():
            if existing_file.name.lower() == pseudo_name.lower():
                return existing_file
    return None


def validate_roundtrip(original_input: Path, generated_input: Path) -> ValidationResult:
    """
    Validate round-trip conversion: parse -> export -> compare.
    
    This is a semantic comparison, not strict textual.
    """
    try:
        # Parse original
        original_qe = QEInputParser.parse_file(original_input)
        
        # Parse generated
        generated_qe = QEInputParser.parse_file(generated_input)
        
        differences = []
        
        # Compare modules
        if original_qe.module != generated_qe.module:
            differences.append(f"Module mismatch: {original_qe.module} != {generated_qe.module}")
        
        # Compare namelists
        original_nl_names = {nl.name.upper() for nl in original_qe.namelists}
        generated_nl_names = {nl.name.upper() for nl in generated_qe.namelists}
        
        if original_nl_names != generated_nl_names:
            differences.append(f"Namelist names differ: {original_nl_names} != {generated_nl_names}")
        
        # Compare parameters in each namelist
        for nl_name in original_nl_names | generated_nl_names:
            orig_nl = original_qe.get_namelist(nl_name)
            gen_nl = generated_qe.get_namelist(nl_name)
            
            if orig_nl is None or gen_nl is None:
                if orig_nl is None:
                    differences.append(f"Missing namelist {nl_name} in original")
                if gen_nl is None:
                    differences.append(f"Missing namelist {nl_name} in generated")
                continue
            
            # Compare parameters (ignore structure-related ones that may be removed)
            orig_params = {k: v for k, v in orig_nl.parameters.items() 
                          if str(k).lower() not in ['ibrav', 'nat', 'ntyp', 'celldm(1)', 'a', 'b', 'c']}
            gen_params = {k: v for k, v in gen_nl.parameters.items() 
                         if str(k).lower() not in ['ibrav', 'nat', 'ntyp', 'celldm(1)', 'a', 'b', 'c']}
            
            for key in orig_params.keys() | gen_params.keys():
                orig_val = orig_params.get(key)
                gen_val = gen_params.get(key)
                if orig_val != gen_val:
                    differences.append(f"{nl_name}.{key}: {orig_val} != {gen_val}")
        
        # Compare cards (excluding structure cards which are in structure JSON)
        original_card_types = {c.card_type for c in original_qe.cards 
                              if c.card_type not in [QECardType.ATOMIC_POSITIONS, QECardType.CELL_PARAMETERS]}
        generated_card_types = {c.card_type for c in generated_qe.cards 
                               if c.card_type not in [QECardType.ATOMIC_POSITIONS, QECardType.CELL_PARAMETERS]}
        
        if original_card_types != generated_card_types:
            differences.append(f"Card types differ: {original_card_types} != {generated_card_types}")
        
        # Compare K_POINTS if present
        orig_kpoints = original_qe.get_card(QECardType.K_POINTS)
        gen_kpoints = generated_qe.get_card(QECardType.K_POINTS)
        if orig_kpoints and gen_kpoints:
            if orig_kpoints.option != gen_kpoints.option:
                differences.append(f"K_POINTS option: {orig_kpoints.option} != {gen_kpoints.option}")
            if orig_kpoints.data != gen_kpoints.data:
                differences.append(f"K_POINTS data differs")
        
        # Compare ATOMIC_SPECIES (pseudopotential names)
        orig_species = original_qe.get_card(QECardType.ATOMIC_SPECIES)
        gen_species = generated_qe.get_card(QECardType.ATOMIC_SPECIES)
        if orig_species and gen_species:
            orig_pseudos = extract_pseudopotential_names(original_qe)
            gen_pseudos = extract_pseudopotential_names(generated_qe)
            if orig_pseudos != gen_pseudos:
                differences.append(f"Pseudopotential names differ: {orig_pseudos} != {gen_pseudos}")
        
        return ValidationResult(
            success=len(differences) == 0,
            differences=differences
        )
        
    except Exception as e:
        return ValidationResult(
            success=False,
            error=f"Validation error: {str(e)}"
        )


def create_demo_from_dataset(
    dataset: DatasetInfo,
    output_dir: Path,
    repo_root: Path,
    pseudo_search_dirs: List[Path]
) -> DemoResult:
    """
    Create a demo project snapshot from a dataset.
    
    Args:
        dataset: Dataset information
        output_dir: Directory to create demo in
        repo_root: Repository root path
        pseudo_search_dirs: Directories to search for pseudopotentials
        
    Returns:
        DemoResult with success status and details
    """
    demo_name = dataset.folder_name.replace("/", "__").replace(" ", "_")
    demo_path = output_dir / demo_name
    
    try:
        # Sort input files by execution order
        input_files = sort_input_files_by_execution_order(dataset.input_files)
        if not input_files:
            return DemoResult(
                demo_name=demo_name,
                demo_path=demo_path,
                success=False,
                error="No input files found"
            )
        
        # Check pseudopotentials for all inputs
        missing_pseudos = []
        all_pseudos_needed = set()
        
        for input_file in input_files:
            qe_input = QEInputParser.parse_file(input_file)
            pseudo_names = extract_pseudopotential_names(qe_input)
            all_pseudos_needed.update(pseudo_names)
        
        # Check if pseudos are available
        for pseudo_name in all_pseudos_needed:
            if not find_pseudopotential_file(pseudo_name, pseudo_search_dirs):
                missing_pseudos.append(pseudo_name)
        
        if missing_pseudos:
            return DemoResult(
                demo_name=demo_name,
                demo_path=demo_path,
                success=False,
                missing_pseudos=missing_pseudos,
                error=f"Missing pseudopotentials: {', '.join(missing_pseudos)}"
            )
        
        # Create temporary project structure
        temp_project_dir = output_dir / f".temp_{demo_name}"
        temp_project_dir.mkdir(parents=True, exist_ok=True)
        
        # Create project.qv.yml
        project_config = {
            "project": {"name": demo_name},
            "calculations": [],
            "structures": [],
            "settings": {}
        }
        (temp_project_dir / "project.qv.yml").write_text(yaml.safe_dump(project_config, sort_keys=False))
        
        # Create calculation from input files
        calculation_dir = temp_project_dir / "calculations" / "main"
        calc_result = build_calculation_from_qe_inputs(
            input_files=input_files,
            calculation_dir=calculation_dir,
            calculation_id="main",
            project_root=temp_project_dir,
            reference_structure_by="id"
        )
        
        # Copy pseudopotentials to project
        project_pseudo_dir = temp_project_dir / "pseudo"
        project_pseudo_dir.mkdir(parents=True, exist_ok=True)
        
        for pseudo_name in all_pseudos_needed:
            pseudo_file = find_pseudopotential_file(pseudo_name, pseudo_search_dirs)
            if pseudo_file:
                shutil.copy2(pseudo_file, project_pseudo_dir / pseudo_name)
        
        # Copy original input files as reference
        reference_dir = demo_path / "reference_inputs"
        reference_dir.mkdir(parents=True, exist_ok=True)
        for input_file in input_files:
            shutil.copy2(input_file, reference_dir / input_file.name)
        
        # Copy reference outputs if present
        if dataset.reference_out_dir and dataset.reference_out_dir.exists():
            ref_out_dest = demo_path / "reference_outputs"
            if ref_out_dest.exists():
                shutil.rmtree(ref_out_dest)
            shutil.copytree(dataset.reference_out_dir, ref_out_dest)
        
        # Create project snapshot
        snapshot = export_project_to_snapshot(temp_project_dir)
        
        # Add demo metadata
        snapshot.meta = {
            "id": demo_name,
            "title": dataset.folder_name.replace("_", " ").title(),
            "description": f"Tutorial dataset: {dataset.folder_name}",
            "tags": ["tutorial", "qe"],
            "source": f"tests/data/{dataset.folder_path.name}",
            "step_count": len(input_files)
        }
        
        # Write snapshot
        snapshot_file = demo_path / "demo.qv.yml"
        demo_path.mkdir(parents=True, exist_ok=True)
        snapshot_file.write_text(yaml.safe_dump(snapshot.to_dict(), sort_keys=False))
        
        # Validate round-trip for first input file
        validation = None
        if input_files and calc_result.step_results:
            first_input = input_files[0]
            
            try:
                # Load the step spec
                step_spec_file = calc_result.step_results[0].spec_path
                step_spec_data = yaml.safe_load(step_spec_file.read_text())
                step_spec = StructureStepSpec.from_dict(step_spec_data, source_path=step_spec_file)
                
                # Load structure
                structure = read_structure(calc_result.structure_path)
                
                # Generate QE input
                generated_qe_input, _ = generate_qe_input_from_spec(
                    structure=structure,
                    spec=step_spec
                )
                
                # Write to temp file for comparison
                temp_generated = temp_project_dir / "generated.in"
                QEInputGenerator.write_file(generated_qe_input, temp_generated)
                
                # Validate
                validation = validate_roundtrip(first_input, temp_generated)
                
            except Exception as e:
                import traceback
                validation = ValidationResult(
                    success=False,
                    error=f"Validation failed: {str(e)}\n{traceback.format_exc()}"
                )
        
        # Clean up temp project
        shutil.rmtree(temp_project_dir)
        
        # Create demo.json manifest
        demo_manifest = {
            "id": demo_name,
            "title": snapshot.meta.get("title", demo_name),
            "description": snapshot.meta.get("description", ""),
            "source": f"tests/data/{dataset.folder_path.relative_to(repo_root)}",
            "steps": [f.stem for f in input_files],
            "step_count": len(input_files),
            "validation": {
                "success": validation.success if validation else False,
                "differences": validation.differences if validation else [],
                "error": validation.error if validation else None
            } if validation else None,
            "pseudopotentials": list(all_pseudos_needed)
        }
        
        (demo_path / "demo.json").write_text(json.dumps(demo_manifest, indent=2))
        
        return DemoResult(
            demo_name=demo_name,
            demo_path=demo_path,
            success=True,
            validation=validation,
            step_count=len(input_files)
        )
        
    except Exception as e:
        return DemoResult(
            demo_name=demo_name,
            demo_path=demo_path,
            success=False,
            error=f"Error creating demo: {str(e)}"
        )


def main():
    """Main entry point."""
    repo_root = find_repo_root()
    tests_data_dir = repo_root / "tests" / "data"
    output_dir = repo_root / "demos" / "qe_tutorials"
    
    # Find pseudopotential directories
    repo_pseudo_dir = repo_root / "pseudo"
    pseudo_search_dirs = [repo_pseudo_dir] if repo_pseudo_dir.exists() else []
    
    print(f"Repository root: {repo_root}")
    print(f"Tests data directory: {tests_data_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Pseudopotential search directories: {pseudo_search_dirs}")
    print()
    
    # Discover datasets
    print("Discovering datasets...")
    datasets = discover_datasets(tests_data_dir)
    print(f"Found {len(datasets)} datasets")
    print()
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process each dataset
    results: List[DemoResult] = []
    for i, dataset in enumerate(datasets, 1):
        print(f"[{i}/{len(datasets)}] Processing {dataset.folder_name}...")
        result = create_demo_from_dataset(dataset, output_dir, repo_root, pseudo_search_dirs)
        results.append(result)
        
        if result.success:
            print(f"  ✓ Created demo: {result.demo_path.name}")
            if result.validation:
                if result.validation.success:
                    print(f"  ✓ Round-trip validation passed")
                else:
                    print(f"  ⚠ Round-trip validation failed: {len(result.validation.differences)} differences")
                    if result.validation.error:
                        print(f"    Error: {result.validation.error}")
        else:
            print(f"  ✗ Failed: {result.error}")
            if result.missing_pseudos:
                print(f"    Missing pseudos: {', '.join(result.missing_pseudos)}")
        print()
    
    # Generate summary report
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    
    summary = {
        "total_datasets": len(datasets),
        "successful": len(successful),
        "failed": len(failed),
        "results": [
            {
                "demo_name": r.demo_name,
                "success": r.success,
                "error": r.error,
                "missing_pseudos": r.missing_pseudos,
                "step_count": r.step_count,
                "validation": {
                    "success": r.validation.success if r.validation else None,
                    "differences_count": len(r.validation.differences) if r.validation else None,
                    "error": r.validation.error if r.validation else None
                } if r.validation else None
            }
            for r in results
        ]
    }
    
    # Write JSON report
    report_json = output_dir / "import_report.json"
    report_json.write_text(json.dumps(summary, indent=2))
    
    # Write Markdown report
    report_md = output_dir / "import_report.md"
    with report_md.open("w") as f:
        f.write("# Tutorial Dataset Import Report\n\n")
        f.write(f"**Total datasets discovered:** {len(datasets)}\n")
        f.write(f"**Successfully imported:** {len(successful)}\n")
        f.write(f"**Failed:** {len(failed)}\n\n")
        
        f.write("## Successful Imports\n\n")
        for r in successful:
            f.write(f"### {r.demo_name}\n")
            f.write(f"- Steps: {r.step_count}\n")
            if r.validation:
                if r.validation.success:
                    f.write("- Round-trip validation: ✓ Passed\n")
                else:
                    f.write(f"- Round-trip validation: ✗ Failed ({len(r.validation.differences)} differences)\n")
            f.write("\n")
        
        f.write("## Failed Imports\n\n")
        for r in failed:
            f.write(f"### {r.demo_name}\n")
            f.write(f"- Error: {r.error}\n")
            if r.missing_pseudos:
                f.write(f"- Missing pseudopotentials: {', '.join(r.missing_pseudos)}\n")
            f.write("\n")
    
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total datasets: {len(datasets)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    print()
    print(f"Reports written to:")
    print(f"  - {report_json}")
    print(f"  - {report_md}")
    print()


if __name__ == "__main__":
    main()

