"""
Facade API for materializing a project from a folder of QE input files.

This module provides a reusable facade function to create a full project snapshot
from an input folder containing .in files, enabling migration from raw QE
folders to QMatSuite projects.

This is a facade-level orchestration function that depends on QVService,
so it belongs in the api/ layer (not kernel).
"""

from __future__ import annotations

import inspect
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from quantumvitas.api import QVService
from quantumvitas.calculation.folder_import import (
    extract_species_map_from_qe_input,
    merge_species_maps,
    sort_input_files_by_execution_order,
)
from quantumvitas.project.snapshot import ProjectSnapshot, export_project_to_snapshot


def materialize_project_from_qe_input_folder(
    folder: Path,
    project_name: str,
    calculation_name: Optional[str] = None,
    *,
    service: Optional[QVService] = None,
    temp_dir: Optional[Path] = None,
) -> ProjectSnapshot:
    """
    Materialize a full project snapshot from a folder containing QE input files.

    This is a global, reusable API for creating projects from raw QE input folders.
    It can be used for demo import, user migration, or any scenario where you have
    a folder of .in files and want to create a QMatSuite project.

    Behavior:
    - Discovers all `.in` files under folder
    - Determines execution order using robust filename heuristics
    - For each `.in` in order:
      - Imports step via QVService.import_step_from_qe_input() (dedups structures by fingerprint)
    - Exports to snapshot using existing export_project_to_snapshot()

    Args:
        folder: Folder containing .in files
        project_name: Name for the project
        calculation_name: Optional name for the calculation (defaults to folder name)
        service: Optional QVService instance (creates new if not provided)
        temp_dir: Optional temporary directory for project (defaults to system temp)

    Returns:
        ProjectSnapshot containing the materialized project

    Raises:
        ValueError: If no input files found or project creation fails
    """
    from quantumvitas.core.resolution import build_resource_index

    folder = Path(folder).resolve()
    if not folder.exists():
        raise ValueError(f"Input folder does not exist: {folder}")

    # Find all .in files
    input_files = sorted(folder.glob("*.in"))
    if not input_files:
        raise ValueError(f"No .in files found in {folder}")

    # Sort by execution order
    input_files = sort_input_files_by_execution_order(input_files)

    # Preprocess input files: fix missing CELL_PARAMETERS for ibrav=0
    # Find the first file with explicit structure information for reference
    from quantumvitas.io import QEInputParser, QEInputGenerator
    from quantumvitas.io.structure_io import qe_input_has_explicit_structure
    from quantumvitas.io.model import QECardType

    temp_fix_dir = Path(tempfile.mkdtemp(prefix="qv_fix_"))
    processed_input_files = []

    try:
        # Find reference structure file (first file with explicit structure)
        reference_structure_file = None
        reference_qe_input = None
        for input_file in input_files:
            try:
                qe_input = QEInputParser.parse_file(input_file)
                if qe_input_has_explicit_structure(qe_input):
                    reference_structure_file = input_file
                    reference_qe_input = qe_input
                    break
            except Exception:
                continue

        # If no file has explicit structure, fail gracefully
        if not reference_structure_file:
            shutil.rmtree(temp_fix_dir, ignore_errors=True)
            raise ValueError(
                f"No input file in {folder} contains explicit structure information. "
                f"At least one file must have ATOMIC_POSITIONS and a resolvable lattice representation."
            )

        # Process each input file
        for input_file in input_files:
            try:
                qe_input = QEInputParser.parse_file(input_file)
                system = qe_input.get_namelist("SYSTEM") or qe_input.get_namelist("system")
                # Files without SYSTEM namelist (e.g., LR/TDDFT) are structure-less and should be processed as-is
                if not system:
                    processed_input_files.append(input_file)
                    continue

                ibrav = int(system.get("ibrav", 0) or 0)

                # Apply ibrav=12 cosab/cosbc workaround if needed
                if ibrav in [12, -12]:
                    has_cosab = any(str(k).lower() in ["cosab", "cos(ab)"] for k in system.parameters.keys())
                    has_cosbc = any(str(k).lower() == "cosbc" for k in system.parameters.keys())
                    if has_cosab and not has_cosbc:
                        cosab_val = None
                        for k, v in system.parameters.items():
                            if str(k).lower() in ["cosab", "cos(ab)"]:
                                cosab_val = v
                                break
                        if cosab_val is not None:
                            system.parameters["cosbc"] = cosab_val

                # Inject missing structure cards for ibrav=0 if a reference is available
                cell_card = qe_input.get_card(QECardType.CELL_PARAMETERS)
                if ibrav == 0 and not cell_card and reference_qe_input:
                    ref_cell_card = reference_qe_input.get_card(QECardType.CELL_PARAMETERS)
                    if ref_cell_card:
                        # Reference has CELL_PARAMETERS, use it
                        qe_input.cards.append(ref_cell_card)
                    else:
                        # Reference has ibrav != 0, extract structure and generate CELL_PARAMETERS
                        try:
                            from quantumvitas.io import structure_from_qe_input
                            from quantumvitas.calculation.structure_steps import generate_qe_input_from_structure
                            ref_structure = structure_from_qe_input(reference_qe_input)
                            # Generate a temporary QE input with ibrav=0 to get CELL_PARAMETERS
                            from quantumvitas.calculation.structure_steps import StructureStepSpec
                            temp_spec = StructureStepSpec(step_type_spec="qe_scf", structure_ulid="temp")
                            temp_qe, _ = generate_qe_input_from_structure(ref_structure, temp_spec)
                            gen_cell_card = temp_qe.get_card(QECardType.CELL_PARAMETERS)
                            if gen_cell_card:
                                qe_input.cards.append(gen_cell_card)
                            else:
                                # Can't generate, skip this file
                                processed_input_files.append(input_file)
                                continue
                        except Exception:
                            # Extraction failed, skip this file
                            processed_input_files.append(input_file)
                            continue

                    # Add other structure cards if missing
                    if reference_qe_input.get_card(QECardType.ATOMIC_SPECIES) and not qe_input.get_card(QECardType.ATOMIC_SPECIES):
                        qe_input.cards.append(reference_qe_input.get_card(QECardType.ATOMIC_SPECIES))
                    if reference_qe_input.get_card(QECardType.ATOMIC_POSITIONS) and not qe_input.get_card(QECardType.ATOMIC_POSITIONS):
                        qe_input.cards.append(reference_qe_input.get_card(QECardType.ATOMIC_POSITIONS))
                    system.parameters["ibrav"] = 0  # Ensure ibrav is 0

                    # Write fixed file to temp location
                    temp_fixed = temp_fix_dir / f"fixed_{input_file.name}"
                    QEInputGenerator.write_file(qe_input, temp_fixed)
                    processed_input_files.append(temp_fixed)
                else:
                    processed_input_files.append(input_file)
            except Exception as e:
                # Use original if preprocessing fails
                processed_input_files.append(input_file)

        if not processed_input_files:
            shutil.rmtree(temp_fix_dir, ignore_errors=True)
            raise ValueError("No valid input files found after preprocessing")

        input_files = processed_input_files
    except Exception:
        shutil.rmtree(temp_fix_dir, ignore_errors=True)
        raise

    # Create temporary project directory
    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="qv_import_"))
    else:
        temp_dir = Path(temp_dir).resolve()
        temp_dir.mkdir(parents=True, exist_ok=True)

    # Use provided service or create new
    if service is None:
        service = QVService

    try:
        # Initialize project
        project_root = temp_dir / project_name
        service.init_project(target_dir=project_root, name=project_name)

        # Build resource index
        index = build_resource_index(project_root)

        # Determine calculation structure_ulid from first file with explicit structure
        # This structure will be used for all steps (calc-level structure semantics)
        calculation_structure_ulid = None
        if reference_structure_file:
            # Import structure from reference file to get its ID
            from quantumvitas.io.structure_io import structure_from_qe_input
            from quantumvitas.io import write_structure
            from quantumvitas.core.resources import generate_resource_id, meta_from_name, ensure_relative_path

            ref_structure = structure_from_qe_input(reference_qe_input)
            structures_dir = project_root / "structures"
            structures_dir.mkdir(parents=True, exist_ok=True)

            # Generate ULID for structure
            calculation_structure_ulid = generate_resource_id()
            structure_filename = reference_structure_file.stem
            structure_path = structures_dir / f"{structure_filename}.json"

            # Create structure file with proper meta
            try:
                structure_meta_path = ensure_relative_path(structure_path, base=project_root)
            except ValueError:
                structure_meta_path = f"structures/{structure_filename}.json"

            structure_meta = meta_from_name(
                "structure",
                name=structure_filename,
                path=structure_meta_path,
            )
            structure_meta.ulid = calculation_structure_ulid

            # Write structure with meta
            write_structure(ref_structure, structure_path, format="json", metadata=structure_meta)

            # Register structure in project
            from quantumvitas.core.resolution import build_resource_index
        index = build_resource_index(project_root)

        # Create calculation
        calc_name = calculation_name or folder.name
        calc_resolved = service.init_calculation(
            project_root=project_root,
            name=calc_name,
            index=index,
        )
        calculation_selector = calc_resolved.meta.ulid  # Use ID as selector

        # Set calculation structure_ulid if we determined it
        if calculation_structure_ulid:
            from quantumvitas.core.models import load_calculation, save_calculation
            calculation_yaml = calc_resolved.absolute_path / "calculation.yaml"
            calc_model = load_calculation(calculation_yaml, project_root)
            calc_model.structure_ulid = calculation_structure_ulid
            save_calculation(calc_model, calculation_yaml)
            index = build_resource_index(project_root)  # Rebuild index after setting structure_ulid

        # Build species_map from all input files BEFORE importing steps
        # This allows us to fail fast if there are conflicting pseudopotential mappings
        calc_species_map: Dict[str, Dict[str, Any]] = {}
        for input_file in input_files:
            try:
                qe_input = QEInputParser.parse_file(input_file)
                file_species_map = extract_species_map_from_qe_input(qe_input)
                if file_species_map:
                    calc_species_map = merge_species_maps(
                        calc_species_map,
                        file_species_map,
                        source_file=input_file.name,
                    )
            except ValueError:
                # Re-raise conflict errors (from merge_species_maps)
                raise
            except Exception:
                # Ignore parse errors for files that can't be read
                continue

        # Import each step in order
        # Use adaptive call to handle API signature differences
        import_step_sig = inspect.signature(service.import_step_from_qe_input)

        for input_file in input_files:
            # Build kwargs based on actual API signature
            call_kwargs = {
                "project_root": project_root,
                "input_file": input_file,
                "index": index,
            }

            # Adapt parameter name: API uses calculation_ulid, but we have calculation_selector (which is a ULID)
            if "calculation_ulid" in import_step_sig.parameters:
                call_kwargs["calculation_ulid"] = calculation_selector
            elif "calculation_selector" in import_step_sig.parameters:
                call_kwargs["calculation_selector"] = calculation_selector
            # If neither exists, skip (shouldn't happen, but be defensive)

            service.import_step_from_qe_input(**call_kwargs)
            # Rebuild index after each step to pick up new structures
            index = build_resource_index(project_root)

        # Set calc-level species_map if we collected any pseudo mappings
        if calc_species_map:
            from quantumvitas.core.models import load_calculation, save_calculation
            calculation_yaml = calc_resolved.absolute_path / "calculation.yaml"
            calc_model = load_calculation(calculation_yaml, project_root)
            calc_model.species_map = calc_species_map
            save_calculation(calc_model, calculation_yaml)

        # Export to snapshot
        snapshot = export_project_to_snapshot(project_root)

        # Clean up temporary fixed files
        shutil.rmtree(temp_fix_dir, ignore_errors=True)

        return snapshot

    except Exception as e:
        # Clean up temp directory on error
        if temp_fix_dir.exists():
            shutil.rmtree(temp_fix_dir, ignore_errors=True)
        if temp_dir.exists() and str(temp_dir).startswith(str(Path(tempfile.gettempdir()))):
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise
