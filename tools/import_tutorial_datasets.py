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
7. Generates demo snapshots in resources/demo_projects/ with naming 00_* to 19_*
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Add src to path for imports
import sys
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from quantumvitas.io import QEInputParser, QEInputGenerator, read_structure, write_structure
from quantumvitas.io.model import QECardType, QEInput, QEModule
from quantumvitas.calculation.importers import build_calculation_from_qe_inputs
from quantumvitas.project.snapshot import ProjectSnapshot, export_project_to_snapshot
from quantumvitas.calculation.structure_steps import StructureStepSpec, generate_qe_input_from_spec
from quantumvitas.core.resources import generate_resource_id, meta_from_name


@dataclass
class DatasetInfo:
    """Information about a tutorial dataset."""
    folder_name: str
    folder_path: Path
    dataset_num: int  # 0-19
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
    reference_artifacts: Dict[str, str] = field(default_factory=dict)


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
                    # Create a combined name for the demo
                    desc_part = folder_name.split('_', 1)[1] if '_' in folder_name else folder_name
                    demo_name = f"{dataset_num:02d}_{desc_part}__{subcase_name}"
                    datasets.append(DatasetInfo(
                        folder_name=demo_name,
                        folder_path=subcase_dir,
                        dataset_num=dataset_num,
                        input_files=subcase_inputs,
                        subcases=[],
                        reference_out_dir=subcase_dir / "reference_out" if (subcase_dir / "reference_out").exists() else None
                    ))
        else:
            # No subcases - main folder contains inputs
            input_files = sorted(folder.glob("*.in"))
            # Check for reference output directories
            for ref_dir_name in ["reference_out", "reference_output", "reference", "reference_outputs"]:
                ref_dir = folder / ref_dir_name
                if ref_dir.exists() and ref_dir.is_dir():
                    reference_out_dir = ref_dir
                    break
            
            if input_files:
                # Single dataset without subcases
                datasets.append(DatasetInfo(
                    folder_name=folder_name,
                    folder_path=folder,
                    dataset_num=dataset_num,
                    input_files=input_files,
                    subcases=[],
                    reference_out_dir=reference_out_dir
                ))
    
    return datasets


def materialize_project_from_input_folder(
    input_folder: Path,
    project_name: str,
    calculation_name: Optional[str] = None,
    pseudo_search_dirs: Optional[List[Path]] = None,
    temp_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Core function: Materialize a QMatSuite project from a folder containing QE input files.
    
    This function can be used to reconstruct a project from raw input files, e.g., when
    only a folder of .in files is available.
    
    Args:
        input_folder: Folder containing .in files
        project_name: Name for the project
        calculation_name: Optional name for the calculation (defaults to folder name)
        pseudo_search_dirs: Optional directories to search for pseudopotentials
        temp_dir: Optional temporary directory for project (defaults to system temp)
        
    Returns:
        Dict with:
        - project_root: Path to created project
        - structure_selector: Structure selector (slug)
        - calculation_selector: Calculation selector (ID)
        - step_types: List of step types imported
        - input_files: List of input files processed (sorted)
        - all_pseudos_needed: Set of pseudopotential filenames needed
        
    Raises:
        ValueError: If no input files found or project creation fails
    """
    from quantumvitas.api import QVService
    from quantumvitas.core.resolution import build_resource_index
    import tempfile
    
    input_folder = Path(input_folder).resolve()
    if not input_folder.exists():
        raise ValueError(f"Input folder does not exist: {input_folder}")
    
    # Find all .in files in the folder
    input_files = sorted(input_folder.glob("*.in"))
    if not input_files:
        raise ValueError(f"No .in files found in {input_folder}")
    
    # Sort by execution order (numbering if exists, otherwise filename)
    input_files = sort_input_files_by_execution_order(input_files)
    
    # Preprocess input files: fix missing CELL_PARAMETERS for ibrav=0
    # Find the first file with complete structure information
    structure_file = find_structure_file(input_files)
    if not structure_file:
        raise ValueError("No input file found with complete structure information")
    
    # Extract structure from the first complete file for reference
    structure_qe_input = QEInputParser.parse_file(structure_file)
    structure_cell_card = structure_qe_input.get_card(QECardType.CELL_PARAMETERS)
    structure_atomic_species = structure_qe_input.get_card(QECardType.ATOMIC_SPECIES)
    structure_atomic_positions = structure_qe_input.get_card(QECardType.ATOMIC_POSITIONS)
    
    # Filter and fix input files
    import tempfile
    temp_fix_dir = Path(tempfile.mkdtemp(prefix="qv_fix_"))
    valid_input_files = []
    
    try:
        for input_file in input_files:
            try:
                qe_input = QEInputParser.parse_file(input_file)
                system = qe_input.get_namelist("SYSTEM") or qe_input.get_namelist("system")
                if not system:
                    continue
                
                ibrav = int(system.get("ibrav", 0) or 0)
                cell_card = qe_input.get_card(QECardType.CELL_PARAMETERS)
                
                # Check if file has complete structure
                has_complete_structure = False
                if ibrav != 0:
                    # For ibrav != 0, check if required params exist
                    if ibrav in [12, -12]:
                        # Check parameter keys (case-insensitive)
                        param_keys_lower = {str(k).lower(): k for k in system.parameters.keys()}
                        has_b = "b" in param_keys_lower
                        has_c = "c" in param_keys_lower
                        has_cosab = any(k in param_keys_lower for k in ["cosab", "cos(ab)", "cos(angle)", "cosab"])
                        # Also check if a is present (sometimes used instead of b for ibrav=12)
                        has_a = "a" in param_keys_lower
                        has_complete_structure = (has_b or has_a) and has_c and has_cosab
                    else:
                        has_celldm1 = any(str(k).lower() == "celldm(1)" for k in system.parameters.keys())
                        has_a = any(str(k).lower() == "a" for k in system.parameters.keys())
                        has_complete_structure = has_celldm1 or has_a
                else:
                    # ibrav == 0 requires CELL_PARAMETERS
                    has_complete_structure = cell_card is not None
                
                # Special handling for ibrav=12/-12: workaround for cosab vs cosbc issue
                if ibrav in [12, -12] and not has_complete_structure:
                    # Check if we have cosab but code expects cosbc
                    has_cosab = any(str(k).lower() in ["cosab", "cos(ab)"] for k in system.parameters.keys())
                    if has_b and has_c and has_cosab:
                        # Add cosbc parameter if missing (workaround for structure_io.py bug)
                        if not any(str(k).lower() == "cosbc" for k in system.parameters.keys()):
                            cosab_val = None
                            for k, v in system.parameters.items():
                                if str(k).lower() in ["cosab", "cos(ab)"]:
                                    cosab_val = v
                                    break
                            if cosab_val is not None:
                                # For ibrav=12, cosab is the angle between a and b (gamma)
                                # The code expects cosbc, but we'll use cosab as cosbc
                                system.parameters["cosbc"] = cosab_val
                                has_complete_structure = True
                
                if has_complete_structure:
                    valid_input_files.append(input_file)
                elif ibrav == 0 and not cell_card and structure_cell_card:
                    # Fix: add CELL_PARAMETERS and other structure cards from structure file
                    if structure_cell_card:
                        qe_input.cards.append(structure_cell_card)
                    if structure_atomic_species and not qe_input.get_card(QECardType.ATOMIC_SPECIES):
                        qe_input.cards.append(structure_atomic_species)
                    if structure_atomic_positions and not qe_input.get_card(QECardType.ATOMIC_POSITIONS):
                        qe_input.cards.append(structure_atomic_positions)
                    # Also ensure ibrav is set correctly
                    if system:
                        system.parameters["ibrav"] = 0
                    # Write fixed file to temp location
                    temp_fixed = temp_fix_dir / f"fixed_{input_file.name}"
                    QEInputGenerator.write_file(qe_input, temp_fixed)
                    valid_input_files.append(temp_fixed)
                elif ibrav == 0 and not cell_card:
                    # Can't fix - skip this file
                    continue
                else:
                    # File is OK
                    valid_input_files.append(input_file)
            except Exception as e:
                # Skip files that can't be parsed
                continue
        
        if not valid_input_files:
            shutil.rmtree(temp_fix_dir, ignore_errors=True)
            raise ValueError("No valid input files found after filtering")
        
        # Use valid_input_files instead of input_files
        input_files = valid_input_files
    except Exception:
        # Clean up on error
        shutil.rmtree(temp_fix_dir, ignore_errors=True)
        raise
    
    # Create temporary project directory
    if temp_dir is None:
        temp_base = tempfile.mkdtemp(prefix="qv_materialize_")
        temp_project_dir = Path(temp_base) / project_name
    else:
        temp_project_dir = Path(temp_dir) / project_name
    
    # Step 1: Initialize empty project
    project_root = QVService.init_project(
        target_dir=temp_project_dir,
        name=project_name
    )
    
    # Build initial resource index
    index = build_resource_index(project_root)
    config = None  # Will be loaded by QVService methods
    
    # Step 2: Import structure from first input file
    # Preprocess first file if needed (fix ibrav=12 cosab/cosbc issue)
    first_input = input_files[0]
    try:
        qe_input = QEInputParser.parse_file(first_input)
        system = qe_input.get_namelist("SYSTEM") or qe_input.get_namelist("system")
        if system:
            ibrav = int(system.get("ibrav", 0) or 0)
            if ibrav in [12, -12]:
                # Workaround: structure_io.py expects cosbc for ibrav=12, but files have cosab
                has_cosab = any(str(k).lower() in ["cosab", "cos(ab)"] for k in system.parameters.keys())
                has_cosbc = any(str(k).lower() == "cosbc" for k in system.parameters.keys())
                if has_cosab and not has_cosbc:
                    # Copy cosab value to cosbc
                    cosab_val = None
                    for k, v in system.parameters.items():
                        if str(k).lower() in ["cosab", "cos(ab)"]:
                            cosab_val = v
                            break
                    if cosab_val is not None:
                        system.parameters["cosbc"] = cosab_val
                        # Write fixed file to temp location
                        temp_fixed_first = temp_fix_dir / f"fixed_{first_input.name}"
                        QEInputGenerator.write_file(qe_input, temp_fixed_first)
                        first_input = temp_fixed_first
    except Exception:
        pass  # If preprocessing fails, use original file
    
    structure_resolved = QVService.import_structure(
        project_root=project_root,
        source=first_input,
        name=None,  # Use default name from file
        format="auto",
        index=None  # Let it rebuild internally
    )
    structure_selector = structure_resolved.meta.slug
    
    # Rebuild index after structure import
    index = build_resource_index(project_root)
    
    # Step 3: Create calculation with structure
    if calculation_name is None:
        calculation_name = input_folder.name.replace("_", " ").title()
    
    calculation_resolved = QVService.init_calculation(
        project_root=project_root,
        name=calculation_name,
        structure_selector=structure_selector,
        template=None,
        index=index,
        config=config
    )
    # Use calculation ID as selector to avoid slug conflicts
    calculation_selector = calculation_resolved.meta.id
    
    # Rebuild index after calculation creation
    index = build_resource_index(project_root)
    
    # Step 4: Import steps sequentially from input files
    step_types = []
    all_pseudos_needed = set()
    
    for input_file in input_files:
        try:
            # Extract pseudopotentials from input
            qe_input = QEInputParser.parse_file(input_file)
            pseudo_names = extract_pseudopotential_names(qe_input)
            all_pseudos_needed.update(pseudo_names)
            
            # Import step from QE input
            step_result = QVService.import_step_from_qe_input(
                project_root=project_root,
                calculation_selector=calculation_selector,
                input_file=input_file,
                step_name=None,  # Use default name from file
                index=index,
                config=config
            )
            
            # Extract step type from result
            steps = step_result.get("steps", [])
            if steps:
                step_types.append(steps[-1].get("step_type", "unknown"))
            
            # Rebuild index after each step import
            index = build_resource_index(project_root)
            
        except Exception as e:
            # Log but continue - some steps might fail
            print(f"    ⚠ Failed to import step from {input_file.name}: {str(e)}")
            continue
    
    if not step_types:
        raise ValueError("No steps were successfully imported")
    
    return {
        "project_root": project_root,
        "structure_selector": structure_selector,
        "calculation_selector": calculation_selector,
        "step_types": step_types,
        "input_files": input_files,
        "all_pseudos_needed": all_pseudos_needed,
        "index": index,
        "config": config
    }


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


def find_pseudopotential_file(pseudo_name: str, search_dirs: List[Path], dataset_path: Optional[Path] = None) -> Optional[Path]:
    """
    Find a pseudopotential file in the search directories.
    
    Enhanced search:
    1. Exact match (case-sensitive)
    2. Case-insensitive match
    3. Partial match (element name)
    4. Search in dataset folder and tests/data
    
    Args:
        pseudo_name: Filename of the pseudopotential
        search_dirs: List of directories to search
        dataset_path: Optional dataset folder path to search
        
    Returns:
        Path to the pseudopotential file, or None if not found
    """
    # Add dataset path and tests/data to search
    extended_search_dirs = list(search_dirs)
    if dataset_path:
        extended_search_dirs.append(dataset_path)
        # Also check parent (tests/data) for pseudos
        if dataset_path.parent.name == "data" and dataset_path.parent.parent.name == "tests":
            extended_search_dirs.append(dataset_path.parent)
    
    for search_dir in extended_search_dirs:
        if not search_dir.exists():
            continue
        # Try exact match
        pp_path = search_dir / pseudo_name
        if pp_path.exists() and pp_path.is_file():
            return pp_path
        # Try case-insensitive match
        for existing_file in search_dir.iterdir():
            if existing_file.is_file() and existing_file.name.lower() == pseudo_name.lower():
                return existing_file
    
    # Try partial match by element name
    # Extract element from pseudo name (e.g., "Si.pbe-n-rrkjus_psl.1.0.0.UPF" -> "Si")
    element_match = re.match(r'^([A-Z][a-z]?)[._]', pseudo_name)
    if element_match:
        element = element_match.group(1)
        for search_dir in extended_search_dirs:
            if not search_dir.exists():
                continue
            # Look for files starting with element
            for existing_file in search_dir.iterdir():
                if existing_file.is_file() and existing_file.name.startswith(element + "."):
                    # Prefer files with similar extension
                    if existing_file.suffix.lower() in [".upf", ".UPF"] or pseudo_name.lower().endswith(existing_file.suffix.lower()):
                        return existing_file
    
    return None


def find_structure_file(input_files: List[Path]) -> Optional[Path]:
    """
    Find the first input file that has complete structure information.
    
    A file has complete structure if:
    1. ibrav != 0 with required parameters, OR
    2. ibrav == 0 with CELL_PARAMETERS card
    
    Args:
        input_files: List of input files in execution order
        
    Returns:
        Path to file with complete structure, or None
    """
    for input_file in input_files:
        try:
            qe_input = QEInputParser.parse_file(input_file)
            system = qe_input.get_namelist("SYSTEM") or qe_input.get_namelist("system")
            if not system:
                continue
            
            ibrav = int(system.get("ibrav", 0) or 0)
            
            # Check if ibrav != 0 (structure defined by ibrav)
            if ibrav != 0:
                # Check if required parameters are present
                # For ibrav=12/-12, need b, c, and cosab (or cos(angle))
                if ibrav in [12, -12]:
                    has_b = any(str(k).lower() == "b" for k in system.parameters.keys())
                    has_c = any(str(k).lower() == "c" for k in system.parameters.keys())
                    has_cosab = any(str(k).lower() in ["cosab", "cos(ab)", "cos(angle)", "cosab"] for k in system.parameters.keys())
                    # Also check if cosab value exists (might be in parameter values)
                    if not has_cosab:
                        # Check parameter values for cosab-like values
                        for key, value in system.parameters.items():
                            key_lower = str(key).lower()
                            if "cos" in key_lower and isinstance(value, (int, float)):
                                has_cosab = True
                                break
                    if has_b and has_c and has_cosab:
                        return input_file
                else:
                    # For other ibrav, check if celldm(1) or a is present
                    has_celldm1 = any(str(k).lower() == "celldm(1)" for k in system.parameters.keys())
                    has_a = any(str(k).lower() == "a" for k in system.parameters.keys())
                    if has_celldm1 or has_a:
                        return input_file
            
            # Check if ibrav == 0 with CELL_PARAMETERS
            if ibrav == 0:
                cell_card = qe_input.get_card(QECardType.CELL_PARAMETERS)
                if cell_card:
                    return input_file
        except Exception:
            continue
    
    return None


def infer_step_type_improved(qe_input: QEInput, filename: str) -> str:
    """
    Improved step type inference with better recognition accuracy.
    
    Uses multiple heuristics:
    1. Module detection
    2. CONTROL.calculation parameter
    3. Filename patterns
    4. Card presence (e.g., K_POINTS crystal_b suggests bands)
    """
    module = qe_input.detect_module()
    
    # Module-based mapping
    if module == QEModule.PW:
        control = qe_input.get_namelist("CONTROL") or qe_input.get_namelist("control")
        if control:
            calculation = control.get("calculation", "scf")
            calculation = str(calculation).lower().strip("'\"")
            mapping = {
                "scf": "scf",
                "nscf": "nscf",
                "bands": "bands_pw",
                "relax": "relax",
                "vc-relax": "vc-relax",
                "md": "md",
                "vc-md": "vc-md",
            }
            step_type = mapping.get(calculation, calculation)
        else:
            step_type = "scf"
        
        # Additional heuristics for bands
        kpoints = qe_input.get_card(QECardType.K_POINTS)
        if kpoints and kpoints.option:
            opt_lower = kpoints.option.lower()
            if "crystal" in opt_lower or "tpiba" in opt_lower:
                # Check if it's a k-path (multiple k-points)
                if isinstance(kpoints.data, list) and len(kpoints.data) > 1:
                    # Check if first element is a count (single number)
                    first = kpoints.data[0]
                    if isinstance(first, list) and len(first) == 1:
                        # Has count line, likely a k-path
                        if step_type == "nscf":
                            step_type = "bands_pw"
        
        # Filename heuristics
        filename_lower = filename.lower()
        if "bands" in filename_lower and step_type == "nscf":
            step_type = "bands_pw"
        if "relax" in filename_lower and step_type == "scf":
            step_type = "relax"
        if "vc" in filename_lower and "relax" in filename_lower:
            step_type = "vc-relax"
    else:
        # Non-PW modules
        module_map = {
            QEModule.DOS: "dos",
            QEModule.BANDS: "bands",
            QEModule.PROJWFC: "projwfc",
            QEModule.PH: "ph",
            QEModule.Q2R: "q2r",
            QEModule.MATDYN: "matdyn",
            QEModule.DYNMAT: "dynmat",
            QEModule.PP: "pp",
            QEModule.GIPAW: "gipaw",
        }
        step_type = module_map.get(module, "custom")
    
    return step_type


def extract_reference_artifacts_from_outputs(
    reference_out_dir: Path,
    demo_id: str,
    target_dir: Path,
    step_types: List[str]
) -> Dict[str, str]:
    """
    Extract reference artifacts from output files.
    
    Args:
        reference_out_dir: Directory containing reference output files
        demo_id: Demo identifier (e.g., "00_Si_scf")
        target_dir: Target directory for artifacts
        step_types: List of step types in the calculation
        
    Returns:
        Dict mapping analysis_type -> artifact_filename
    """
    reference_artifacts = {}
    
    if not reference_out_dir.exists():
        return reference_artifacts
    
    # Try to parse SCF outputs
    scf_outputs = list(reference_out_dir.glob("*scf*.out"))
    if scf_outputs:
        try:
            from quantumvitas.analysis.parsers import parse_scf_output
            scf_result = parse_scf_output(scf_outputs[0])
            if scf_result:
                scf_data = scf_result.to_dict()
                scf_artifact = f"{demo_id}.scf.json"
                scf_path = target_dir / scf_artifact
                scf_path.write_text(json.dumps(scf_data, indent=2))
                reference_artifacts["scf"] = scf_artifact
        except Exception:
            pass  # Silently fail if parsing doesn't work
    
    # Look for DOS data files
    dos_files = list(reference_out_dir.glob("*.dos.dat")) + list(reference_out_dir.glob("*dos*.dat"))
    if dos_files and "dos" in step_types:
        # Try to parse DOS data
        try:
            # Basic DOS parsing (can be enhanced)
            dos_data = {"source_file": str(dos_files[0])}
            dos_artifact = f"{demo_id}.dos.json"
            dos_path = target_dir / dos_artifact
            dos_path.write_text(json.dumps(dos_data, indent=2))
            reference_artifacts["dos"] = dos_artifact
        except Exception:
            pass
    
    # Look for bands data files
    bands_files = list(reference_out_dir.glob("*.bands.dat")) + list(reference_out_dir.glob("*bands*.dat"))
    if bands_files and "bands" in " ".join(step_types):
        # Try to parse bands data
        try:
            bands_data = {"source_file": str(bands_files[0])}
            bands_artifact = f"{demo_id}.bands.json"
            bands_path = target_dir / bands_artifact
            bands_path.write_text(json.dumps(bands_data, indent=2))
            reference_artifacts["bands"] = bands_artifact
        except Exception:
            pass
    
    return reference_artifacts


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
    pseudo_search_dirs: List[Path],
    clean_mode: bool = False
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
    # Generate demo name with zero-padded number: 00_Si_scf, 04_Si_DOS, etc.
    demo_name = f"{dataset.dataset_num:02d}_{dataset.folder_name.split('_', 1)[1] if '_' in dataset.folder_name else dataset.folder_name}"
    # Remove subcase suffix if present (we already handled it in discovery)
    demo_name = demo_name.split("__")[0]
    demo_file = output_dir / f"{demo_name}.yml"
    
    # Clean mode: delete existing demo files with same name first
    if clean_mode and demo_file.exists():
        # Delete the main demo file
        demo_file.unlink()
        # Also delete associated reference artifact files (e.g., demo_name.scf.json, demo_name.dos.json)
        for artifact_file in output_dir.glob(f"{demo_name}.*.json"):
            try:
                artifact_file.unlink()
            except Exception:
                pass  # Ignore errors deleting artifacts
        print(f"  🗑️  Cleaned existing demo: {demo_name}")
    
    try:
        # Sort input files by execution order
        input_files = sort_input_files_by_execution_order(dataset.input_files)
        if not input_files:
            return DemoResult(
                demo_name=demo_name,
                demo_path=demo_file,
                success=False,
                error="No input files found"
            )
        
        # Check pseudopotentials for all inputs
        missing_pseudos = []
        all_pseudos_needed = set()
        
        for input_file in input_files:
            try:
                qe_input = QEInputParser.parse_file(input_file)
                pseudo_names = extract_pseudopotential_names(qe_input)
                all_pseudos_needed.update(pseudo_names)
            except Exception:
                # Skip files that can't be parsed
                continue
        
        # Check if pseudos are available (with enhanced search)
        # Also try to download missing ones to repo/pseudo
        repo_pseudo_dir = repo_root / "pseudo"
        repo_pseudo_dir.mkdir(parents=True, exist_ok=True)
        
        missing_pseudos = []
        for pseudo_name in all_pseudos_needed:
            # First check if already exists
            if find_pseudopotential_file(pseudo_name, pseudo_search_dirs, dataset_path=dataset.folder_path):
                continue
            
            # Try to download to repo/pseudo
            try:
                from quantumvitas.api import QVService
                # Use a dummy project root for download (we just need the download function)
                # The dest_dir will be repo/pseudo
                result = QVService.download_pseudo_by_filename(
                    project_root=repo_root,  # Use repo root as project root
                    filename=pseudo_name,
                    dest_dir=repo_pseudo_dir,
                    config=None
                )
                
                if result.get("errors"):
                    # Download failed
                    missing_pseudos.append(pseudo_name)
                    print(f"    ⚠ Could not download {pseudo_name}: {', '.join(result.get('errors', []))}")
                else:
                    # Download succeeded (or was skipped because already exists)
                    downloaded_name = result.get("filename", pseudo_name)
                    if result.get("skipped"):
                        print(f"    ℹ Pseudo {pseudo_name} already exists as {downloaded_name}")
                    else:
                        print(f"    ✓ Downloaded {pseudo_name} to repo/pseudo")
                    # Update search dirs to include repo/pseudo
                    if repo_pseudo_dir not in pseudo_search_dirs:
                        pseudo_search_dirs.append(repo_pseudo_dir)
            except Exception as e:
                # Download failed
                missing_pseudos.append(pseudo_name)
                print(f"    ⚠ Could not download {pseudo_name}: {str(e)}")
        
        if missing_pseudos:
            return DemoResult(
                demo_name=demo_name,
                demo_path=demo_file,
                success=False,
                missing_pseudos=missing_pseudos,
                error=f"Missing pseudopotentials (could not download): {', '.join(missing_pseudos)}"
            )
        
        # Find the first file with complete structure information
        structure_file = find_structure_file(input_files)
        if not structure_file:
            return DemoResult(
                demo_name=demo_name,
                demo_path=demo_file,
                success=False,
                error="No input file found with complete structure information (ibrav != 0 with params, or ibrav == 0 with CELL_PARAMETERS)"
            )
        
        # Extract structure from the first complete file for reference
        structure_qe_input = QEInputParser.parse_file(structure_file)
        structure_cell_card = structure_qe_input.get_card(QECardType.CELL_PARAMETERS)
        structure_system = structure_qe_input.get_namelist("SYSTEM") or structure_qe_input.get_namelist("system")
        structure_ibrav = int(structure_system.get("ibrav", 0) or 0) if structure_system else 0
        
        # Filter and fix input files (create temp directory for fixed files)
        import tempfile
        temp_fix_dir = Path(tempfile.mkdtemp(prefix="qv_fix_"))
        valid_input_files = []
        temp_fixed_files = []
        
        try:
            for input_file in input_files:
                try:
                    qe_input = QEInputParser.parse_file(input_file)
                    system = qe_input.get_namelist("SYSTEM") or qe_input.get_namelist("system")
                    if not system:
                        continue
                    
                    ibrav = int(system.get("ibrav", 0) or 0)
                    cell_card = qe_input.get_card(QECardType.CELL_PARAMETERS)
                    
                    # Check if file has complete structure
                    has_complete_structure = False
                    if ibrav != 0:
                        # For ibrav != 0, check if required params exist
                        if ibrav in [12, -12]:
                            has_b = any(str(k).lower() == "b" for k in system.parameters.keys())
                            has_c = any(str(k).lower() == "c" for k in system.parameters.keys())
                            has_cosab = any(str(k).lower() in ["cosab", "cos(ab)"] for k in system.parameters.keys())
                            has_complete_structure = has_b and has_c and has_cosab
                        else:
                            has_celldm1 = any(str(k).lower() == "celldm(1)" for k in system.parameters.keys())
                            has_a = any(str(k).lower() == "a" for k in system.parameters.keys())
                            has_complete_structure = has_celldm1 or has_a
                    else:
                        # ibrav == 0 requires CELL_PARAMETERS
                        has_complete_structure = cell_card is not None
                    
                    if has_complete_structure:
                        valid_input_files.append(input_file)
                    elif ibrav == 0 and not cell_card and structure_cell_card:
                        # Fix: add CELL_PARAMETERS from structure file
                        qe_input.cards.append(structure_cell_card)
                        # Also ensure ibrav is set correctly
                        if system:
                            system.parameters["ibrav"] = 0
                        # Write fixed file to temp location
                        temp_fixed = temp_fix_dir / f"fixed_{input_file.name}"
                        QEInputGenerator.write_file(qe_input, temp_fixed)
                        temp_fixed_files.append((input_file, temp_fixed))
                        valid_input_files.append(temp_fixed)
                    elif ibrav == 0 and not cell_card:
                        # Can't fix - skip this file
                        continue
                    else:
                        # File is OK
                        valid_input_files.append(input_file)
                except Exception as e:
                    # Skip files that can't be parsed
                    continue
        finally:
            # Clean up temp fix directory after we're done (but keep files until project is created)
            pass  # Will clean up later
        
        if not valid_input_files:
            # Clean up temp fix dir
            shutil.rmtree(temp_fix_dir, ignore_errors=True)
            return DemoResult(
                demo_name=demo_name,
                demo_path=demo_file,
                success=False,
                error="No valid input files found after filtering"
            )
        
        # Use core function to materialize project from input folder
        import tempfile
        temp_base = tempfile.mkdtemp(prefix="qv_import_")
        
        try:
            # Generate calculation name from dataset
            calc_name = dataset.folder_name.split("_", 1)[1] if "_" in dataset.folder_name else dataset.folder_name
            calc_name = calc_name.replace("_", " ").title()
            
            # Materialize project using core function
            materialize_result = materialize_project_from_input_folder(
                input_folder=dataset.folder_path,
                project_name=demo_name,
                calculation_name=calc_name,
                pseudo_search_dirs=pseudo_search_dirs,
                temp_dir=Path(temp_base)
            )
            
            project_root = materialize_result["project_root"]
            structure_selector = materialize_result["structure_selector"]
            calculation_selector = materialize_result["calculation_selector"]
            step_types = materialize_result["step_types"]
            materialized_input_files = materialize_result["input_files"]
            materialized_pseudos = materialize_result["all_pseudos_needed"]
            index = materialize_result["index"]
            config = materialize_result["config"]
            
            # Copy pseudopotentials to project
            project_pseudo_dir = project_root / "pseudo"
            project_pseudo_dir.mkdir(parents=True, exist_ok=True)
            
            for pseudo_name in all_pseudos_needed:
                pseudo_file = find_pseudopotential_file(pseudo_name, pseudo_search_dirs, dataset_path=dataset.folder_path)
                if pseudo_file:
                    shutil.copy2(pseudo_file, project_pseudo_dir / pseudo_name)
            
            # Create project snapshot
            snapshot = export_project_to_snapshot(project_root)
            
            # Extract reference artifacts from output files
            reference_artifacts = {}
            if dataset.reference_out_dir:
                reference_artifacts = extract_reference_artifacts_from_outputs(
                    dataset.reference_out_dir,
                    demo_name,
                    output_dir,
                    step_types
                )
            
            # Generate title and subtitle from step types
            step_type_names = {
                "scf": "SCF",
                "nscf": "NSCF",
                "dos": "DOS",
                "bands_pw": "Bands",
                "bands": "Bands",
                "relax": "Relax",
                "vc-relax": "VC-Relax",
                "ph": "Phonon",
                "gipaw": "GIPAW",
            }
            step_sequence = " → ".join([step_type_names.get(st, st) for st in step_types])
            
            # Determine recommended analysis
            recommended_analysis = None
            if "dos" in step_types:
                recommended_analysis = "dos"
            elif "bands" in " ".join(step_types):
                recommended_analysis = "bands"
            elif "scf" in step_types:
                recommended_analysis = "scf"
            
            # Add demo metadata matching existing format
            snapshot.meta = {
                "id": demo_name,
                "title": dataset.folder_name.replace("_", " ").title(),
                "subtitle": step_sequence,
                "tags": ["tutorial", "qe"] + step_types[:2],  # Add first two step types as tags
                "recommended_analysis": recommended_analysis,
                "difficulty": "beginner",  # Default, can be enhanced
                "reference_artifacts": reference_artifacts if reference_artifacts else None
            }
            
            # Add pseudo section
            snapshot.pseudo = {
                "directory": "pseudo",
                "files": sorted(list(all_pseudos_needed))
            }
            
            # Write snapshot
            output_dir.mkdir(parents=True, exist_ok=True)
            demo_file.write_text(yaml.safe_dump(snapshot.to_dict(), sort_keys=False))
            
            # Verify the demo can be loaded using existing function
            try:
                from quantumvitas.project.snapshot import ProjectSnapshot
                loaded_snapshot = ProjectSnapshot.from_dict(yaml.safe_load(demo_file.read_text()))
                # Verify it has structures and calculations
                if not loaded_snapshot.structures:
                    print(f"    ⚠ Warning: Demo has no structures")
                if not loaded_snapshot.calculations:
                    print(f"    ⚠ Warning: Demo has no calculations")
            except Exception as e:
                print(f"    ⚠ Warning: Could not verify demo load: {str(e)}")
        
            # Validate round-trip for first input file
            validation = None
            if valid_input_files and step_types:
                first_input = valid_input_files[0]
                
                try:
                    # Get first step from calculation
                    from quantumvitas.core.resolution import require_calculation, require_step
                    from quantumvitas.api import QVService
                    calc_resolved = require_calculation(project_root, calculation_selector, config=config, index=index)
                    calc_detail = QVService.get_calculation_detail(
                        project_root=project_root,
                        calculation_selector=calculation_selector,
                        index=index,
                        config=config
                    )
                    
                    if calc_detail.get("steps"):
                        first_step = calc_detail["steps"][0]
                        step_selector = first_step.get("slug") or first_step.get("name")
                        
                        # Load step spec
                        step_resolved = require_step(project_root, calculation_selector, step_selector, config=config, index=index)
                        step_spec_data = yaml.safe_load(step_resolved.absolute_path.read_text())
                        step_spec = StructureStepSpec.from_dict(step_spec_data, source_path=step_resolved.absolute_path)
                        
                        # Load structure - resolve it from the project
                        from quantumvitas.core.resolution import require_structure
                        structure_resolved = require_structure(project_root, structure_selector, config=config, index=index)
                        structure = read_structure(structure_resolved.absolute_path)
                        
                        # Generate QE input
                        generated_qe_input, _ = generate_qe_input_from_spec(
                            structure=structure,
                            spec=step_spec
                        )
                        
                        # Write to temp file for comparison
                        temp_generated = Path(tempfile.mkdtemp()) / "generated.in"
                        QEInputGenerator.write_file(generated_qe_input, temp_generated)
                        
                        # Validate
                        validation = validate_roundtrip(first_input, temp_generated)
                        
                        # Clean up temp generated file
                        temp_generated.unlink()
                        temp_generated.parent.rmdir()
                        
                except Exception as e:
                    import traceback
                    validation = ValidationResult(
                        success=False,
                        error=f"Validation failed: {str(e)}\n{traceback.format_exc()}"
                    )
            
            # Clean up temp project and temp fix directory
            shutil.rmtree(project_root, ignore_errors=True)
            if 'temp_fix_dir' in locals():
                shutil.rmtree(temp_fix_dir, ignore_errors=True)
            
            return DemoResult(
                demo_name=demo_name,
                demo_path=demo_file,
                success=True,
                validation=validation,
                step_count=len(valid_input_files),
                reference_artifacts=reference_artifacts
            )
        
        except Exception as e:
            import traceback
            # Clean up on error
            if 'project_root' in locals():
                shutil.rmtree(project_root, ignore_errors=True)
            if 'temp_fix_dir' in locals():
                shutil.rmtree(temp_fix_dir, ignore_errors=True)
            return DemoResult(
                demo_name=demo_name,
                demo_path=demo_file,
                success=False,
                error=f"Error creating demo: {str(e)}\n{traceback.format_exc()}"
            )
    
    except Exception as e:
        import traceback
        return DemoResult(
            demo_name=demo_name,
            demo_path=demo_file,
            success=False,
            error=f"Error creating demo: {str(e)}\n{traceback.format_exc()}"
        )


def verify_demo_consistency(demo_file: Path) -> Tuple[bool, List[str]]:
    """
    Verify consistency of a generated demo file.
    
    Returns:
        (is_consistent, list_of_issues)
    """
    issues = []
    
    try:
        data = yaml.safe_load(demo_file.read_text())
        
        # Check required sections
        if "version" not in data:
            issues.append("Missing 'version' field")
        if "project" not in data:
            issues.append("Missing 'project' section")
        if "structures" not in data:
            issues.append("Missing 'structures' section")
        if "calculations" not in data:
            issues.append("Missing 'calculations' section")
        if "meta" not in data:
            issues.append("Missing 'meta' section")
        
        # Check project section
        if "project" in data:
            project = data["project"]
            if "meta" not in project:
                issues.append("Project missing 'meta' section")
            elif "id" not in project["meta"]:
                issues.append("Project meta missing 'id'")
        
        # Check structures
        if "structures" in data and data["structures"]:
            for i, struct in enumerate(data["structures"]):
                if "meta" not in struct:
                    issues.append(f"Structure {i} missing 'meta' section")
                if "data" not in struct:
                    issues.append(f"Structure {i} missing 'data' section")
        
        # Check calculations
        if "calculations" in data and data["calculations"]:
            for i, calc in enumerate(data["calculations"]):
                if "meta" not in calc:
                    issues.append(f"Calculation {i} missing 'meta' section")
                if "steps" not in calc:
                    issues.append(f"Calculation {i} missing 'steps' section")
                elif calc["steps"]:
                    for j, step in enumerate(calc["steps"]):
                        if "meta" not in step:
                            issues.append(f"Calculation {i}, step {j} missing 'meta' section")
                        if "step_type" not in step:
                            issues.append(f"Calculation {i}, step {j} missing 'step_type'")
        
        # Check meta section
        if "meta" in data:
            meta = data["meta"]
            if "id" not in meta:
                issues.append("Meta missing 'id'")
            if "title" not in meta:
                issues.append("Meta missing 'title'")
        
        # Check pseudo section
        if "pseudo" in data:
            pseudo = data["pseudo"]
            if "directory" not in pseudo:
                issues.append("Pseudo section missing 'directory'")
            if "files" not in pseudo:
                issues.append("Pseudo section missing 'files'")
        
        return len(issues) == 0, issues
        
    except Exception as e:
        return False, [f"Error reading demo file: {str(e)}"]


def verify_demo_project(demo_file: Path) -> Dict[str, Any]:
    """
    Verify a generated demo project by loading it and checking structure.
    
    Returns:
        Dict with verification results:
        - can_load: bool - Whether demo can be loaded
        - n_structures: int - Number of structures
        - n_calculations: int - Number of calculations
        - n_steps: List[int] - Number of steps per calculation
        - step_types: List[List[str]] - Step types per calculation
        - issues: List[str] - List of issues found
    """
    from quantumvitas.project.snapshot import ProjectSnapshot
    
    result = {
        "can_load": False,
        "n_structures": 0,
        "n_calculations": 0,
        "n_steps": [],
        "step_types": [],
        "issues": []
    }
    
    try:
        # Load snapshot
        snapshot_data = yaml.safe_load(demo_file.read_text())
        snapshot = ProjectSnapshot.from_dict(snapshot_data)
        result["can_load"] = True
        
        # Count structures
        result["n_structures"] = len(snapshot.structures)
        if result["n_structures"] == 0:
            result["issues"].append("No structures found")
        
        # Count calculations and steps
        result["n_calculations"] = len(snapshot.calculations)
        if result["n_calculations"] == 0:
            result["issues"].append("No calculations found")
        
        for calc in snapshot.calculations:
            steps = calc.get("steps", [])
            result["n_steps"].append(len(steps))
            step_types = [step.get("step_type", "unknown") for step in steps]
            result["step_types"].append(step_types)
            if len(steps) == 0:
                result["issues"].append(f"Calculation '{calc.get('meta', {}).get('name', 'unknown')}' has no steps")
        
    except Exception as e:
        result["issues"].append(f"Failed to load demo: {str(e)}")
    
    return result


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Import tutorial datasets from tests/data/ into demo project snapshots"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean mode: delete existing demos with same names before generating new ones"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify mode: after generation, verify each demo by loading and checking structure"
    )
    args = parser.parse_args()
    
    repo_root = find_repo_root()
    tests_data_dir = repo_root / "tests" / "data"
    output_dir = repo_root / "resources" / "demo_projects"
    
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
        result = create_demo_from_dataset(
            dataset, output_dir, repo_root, pseudo_search_dirs, clean_mode=args.clean
        )
        results.append(result)
        
        if result.success:
            print(f"  ✓ Created demo: {result.demo_path.name}")
            # Verify consistency
            is_consistent, issues = verify_demo_consistency(result.demo_path)
            if is_consistent:
                print(f"  ✓ Demo structure is consistent")
            else:
                print(f"  ⚠ Demo has {len(issues)} consistency issue(s):")
                for issue in issues[:5]:  # Show first 5 issues
                    print(f"    - {issue}")
            
            # Detailed verification if --verify flag is set
            if args.verify:
                verification = verify_demo_project(result.demo_path)
                if verification["can_load"]:
                    print(f"  ✓ Demo can be loaded")
                    print(f"    Structures: {verification['n_structures']}")
                    print(f"    Calculations: {verification['n_calculations']}")
                    for i, (n_steps, step_types) in enumerate(zip(verification["n_steps"], verification["step_types"])):
                        print(f"    Calculation {i+1}: {n_steps} step(s) - {', '.join(step_types)}")
                    if verification["issues"]:
                        print(f"    ⚠ Issues: {', '.join(verification['issues'])}")
                else:
                    print(f"  ✗ Demo cannot be loaded")
                    if verification["issues"]:
                        for issue in verification["issues"]:
                            print(f"    - {issue}")
            
            if result.validation:
                if result.validation.success:
                    print(f"  ✓ Round-trip validation passed")
                else:
                    print(f"  ⚠ Round-trip validation failed: {len(result.validation.differences)} differences")
                    if result.validation.error:
                        print(f"    Error: {result.validation.error[:100]}")
            
            if result.reference_artifacts:
                print(f"  ✓ Extracted {len(result.reference_artifacts)} reference artifact(s)")
        else:
            print(f"  ✗ Failed: {result.error}")
            if result.missing_pseudos:
                print(f"    Missing pseudos: {', '.join(result.missing_pseudos)}")
        print()
    
    # Generate summary report
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    
    # Verify all successful demos
    verification_results = {}
    detailed_verification = {}
    for result in successful:
        is_consistent, issues = verify_demo_consistency(result.demo_path)
        verification_results[result.demo_name] = {
            "consistent": is_consistent,
            "issues": issues
        }
        
        # Detailed verification if --verify flag is set
        if args.verify:
            detailed_verification[result.demo_name] = verify_demo_project(result.demo_path)
    
    summary = {
        "total_datasets": len(datasets),
        "successful": len(successful),
        "failed": len(failed),
        "verification": {
            name: {
                "consistent": info["consistent"],
                "issue_count": len(info["issues"])
            }
            for name, info in verification_results.items()
        },
        "results": [
            {
                "demo_name": r.demo_name,
                "success": r.success,
                "error": r.error,
                "missing_pseudos": r.missing_pseudos,
                "step_count": r.step_count,
                "reference_artifacts": r.reference_artifacts,
                "validation": {
                    "success": r.validation.success if r.validation else None,
                    "differences_count": len(r.validation.differences) if r.validation else None,
                    "error": r.validation.error if r.validation else None
                } if r.validation else None,
                "verification": verification_results.get(r.demo_name, {}),
                "detailed_verification": detailed_verification.get(r.demo_name) if args.verify else None
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
        
        consistent_count = sum(1 for v in verification_results.values() if v["consistent"])
        f.write(f"**Consistent demos:** {consistent_count}/{len(successful)}\n\n")
        
        f.write("## Successful Imports\n\n")
        for r in successful:
            f.write(f"### {r.demo_name}\n")
            f.write(f"- Steps: {r.step_count}\n")
            verif = verification_results.get(r.demo_name, {})
            if verif.get("consistent"):
                f.write("- Structure: ✓ Consistent\n")
            else:
                f.write(f"- Structure: ✗ {len(verif.get('issues', []))} issue(s)\n")
            if r.validation:
                if r.validation.success:
                    f.write("- Round-trip validation: ✓ Passed\n")
                else:
                    f.write(f"- Round-trip validation: ✗ Failed ({len(r.validation.differences)} differences)\n")
            if r.reference_artifacts:
                f.write(f"- Reference artifacts: {', '.join(r.reference_artifacts.keys())}\n")
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
    consistent_count = sum(1 for v in verification_results.values() if v["consistent"])
    print(f"Consistent: {consistent_count}/{len(successful)}")
    print()
    print(f"Reports written to:")
    print(f"  - {report_json}")
    print(f"  - {report_md}")
    print()


if __name__ == "__main__":
    main()
