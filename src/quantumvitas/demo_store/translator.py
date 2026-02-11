"""
Core translator: converts corpus cases (Layer A) to demo snapshots (Layer B).

Pipeline per S4.3:
1. Validate case.yaml vs corpus_index entry
2. Parse engine inputs via inputformat pipeline
3. Map to QMatSuite domain objects
4. Assemble ProjectSnapshot with deterministic ULIDs
5. Return snapshot dict for serialization

For Python-script engines (GPAW, Psi4, PySCF), delegates to direct_snapshot.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from quantumvitas.demo_store.ulid_seed import deterministic_ulid
from quantumvitas.demo_store.corpus import load_case_yaml, validate_case_yaml


# Structure conversion helpers

def _structure_doc_to_pymatgen_dict(
    structure_doc: Dict[str, Any],
    engine: str,
) -> Dict[str, Any]:
    """
    Convert a StructureDoc dict from the parser into pymatgen-compatible dict.

    StructureDoc format: {lattice, species, frac_coords|cart_coords, comment}
    Pymatgen format: {@module, @class, charge, lattice: {matrix, pbc, ...}, sites: [...]}
    """
    if not structure_doc:
        return {}

    lattice = structure_doc.get("lattice")
    species = structure_doc.get("species", [])
    frac_coords = structure_doc.get("frac_coords")
    cart_coords = structure_doc.get("cart_coords")

    # Determine if this is a molecule (cart_coords, no lattice) or periodic structure
    is_molecule = cart_coords is not None and lattice is None

    if is_molecule:
        return _build_molecule_dict(species, cart_coords)
    elif lattice is not None and frac_coords is not None:
        return _build_structure_dict(lattice, species, frac_coords)
    elif lattice is not None and cart_coords is not None:
        # Periodic with Cartesian coords - convert to fractional
        return _build_structure_dict_cartesian(lattice, species, cart_coords)
    else:
        return {}


def _build_structure_dict(
    lattice: List[List[float]],
    species: List[str],
    frac_coords: List[List[float]],
) -> Dict[str, Any]:
    """Build pymatgen Structure dict from lattice + fractional coordinates."""
    import numpy as np

    matrix = [list(row) for row in lattice]
    mat = np.array(matrix, dtype=float)

    # Compute lattice parameters
    a_len = float(np.linalg.norm(mat[0]))
    b_len = float(np.linalg.norm(mat[1]))
    c_len = float(np.linalg.norm(mat[2]))

    alpha = float(np.degrees(np.arccos(
        np.clip(np.dot(mat[1], mat[2]) / (b_len * c_len), -1, 1)
    )))
    beta = float(np.degrees(np.arccos(
        np.clip(np.dot(mat[0], mat[2]) / (a_len * c_len), -1, 1)
    )))
    gamma = float(np.degrees(np.arccos(
        np.clip(np.dot(mat[0], mat[1]) / (a_len * b_len), -1, 1)
    )))
    volume = float(abs(np.linalg.det(mat)))

    sites = []
    for sp, fc in zip(species, frac_coords):
        cart = list(np.dot(fc, mat))
        sites.append({
            "species": [{"element": sp, "occu": 1}],
            "abc": [float(x) for x in fc],
            "properties": {},
            "label": sp,
            "xyz": [float(x) for x in cart],
        })

    return {
        "@module": "pymatgen.core.structure",
        "@class": "Structure",
        "charge": 0,
        "lattice": {
            "matrix": matrix,
            "pbc": [True, True, True],
            "a": a_len,
            "b": b_len,
            "c": c_len,
            "alpha": alpha,
            "beta": beta,
            "gamma": gamma,
            "volume": volume,
        },
        "properties": {},
        "sites": sites,
    }


def _build_structure_dict_cartesian(
    lattice: List[List[float]],
    species: List[str],
    cart_coords: List[List[float]],
) -> Dict[str, Any]:
    """Build pymatgen Structure dict from lattice + Cartesian coordinates."""
    import numpy as np

    mat = np.array(lattice, dtype=float)
    inv_mat = np.linalg.inv(mat)

    frac_coords = []
    for cc in cart_coords:
        fc = list(np.dot(cc, inv_mat))
        frac_coords.append([float(x) for x in fc])

    return _build_structure_dict(lattice, species, frac_coords)


def _build_molecule_dict(
    species: List[str],
    cart_coords: List[List[float]],
) -> Dict[str, Any]:
    """Build pymatgen Molecule dict from Cartesian coordinates."""
    sites = []
    for sp, cc in zip(species, cart_coords):
        sites.append({
            "name": sp,
            "species": [{"element": sp, "occu": 1}],
            "xyz": [float(x) for x in cc],
            "properties": {},
            "label": sp,
        })

    return {
        "@module": "pymatgen.core.structure",
        "@class": "Molecule",
        "charge": 0,
        "spin_multiplicity": 1,
        "sites": sites,
        "properties": {},
    }


# Pseudo/asset handling

def _resolve_pseudo_info(
    engine: str,
    species: List[str],
    case_data: Dict[str, Any],
    repo_root: Path,
) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Resolve pseudopotential info for the snapshot.

    Returns:
        (pseudo_section, species_map) — both may be None if no pseudos needed.
    """
    asset_policy = case_data.get("asset_policy", "none")
    asset_reqs = case_data.get("asset_requirements", {})
    pseudo_reqs = asset_reqs.get("pseudopotentials", [])

    if not pseudo_reqs:
        return None, None

    pseudo_dir = repo_root / "resources" / "pseudo"
    pseudo_files = []
    species_map = {}

    for req in pseudo_reqs:
        filename = req.get("file", "")
        element = req.get("element", "")
        if not filename:
            continue

        pseudo_files.append(filename)
        entry: Dict[str, Any] = {"pseudopot": filename, "pseudo_basename": filename}

        # Compute checksums for redistributable assets
        if asset_policy == "redistributable":
            pseudo_path = pseudo_dir / filename
            if pseudo_path.exists():
                sha256 = hashlib.sha256(pseudo_path.read_bytes()).hexdigest()
                entry["pseudo_sha256"] = sha256
                # Compute sha_family (content-normalized hash)
                try:
                    from quantumvitas.core.pseudo_libinfo import compute_sha_family_file
                    entry["pseudo_sha_family"] = compute_sha_family_file(pseudo_path)
                except (ImportError, Exception):
                    pass

        if element:
            species_map[element] = entry

    # Build pseudo section
    pseudo_section = {
        "directory": "pseudo",
        "files": sorted(pseudo_files),
    }

    return pseudo_section, species_map


def _build_species_map_from_params(
    engine: str,
    params: Dict[str, Any],
    species: List[str],
) -> Dict[str, Any]:
    """
    Build species_map from parsed parameters (mass, pseudo info).

    For engines like VASP where pseudo info comes from parameters.
    """
    species_map = {}

    if engine == "vasp":
        # VASP: species_map from POTCAR info
        for sp in species:
            species_map[sp] = {
                "mass": _element_mass(sp),
                "pseudo": sp,
                "pseudopot": sp,
                "pseudo_basename": sp,
            }
    elif engine == "qe":
        # QE: species from ATOMIC_SPECIES card
        atomic_species = params.get("ATOMIC_SPECIES", {})
        if isinstance(atomic_species, dict):
            for element, info in atomic_species.items():
                if isinstance(info, dict):
                    species_map[element] = {
                        "mass": info.get("mass", _element_mass(element)),
                        "pseudopot": info.get("pseudo_file", ""),
                        "pseudo_basename": info.get("pseudo_file", ""),
                    }
        if not species_map:
            for sp in species:
                species_map[sp] = {"mass": _element_mass(sp)}

    return species_map


# Common element masses (subset for demo purposes)
_ELEMENT_MASSES = {
    "H": 1.008, "He": 4.003, "Li": 6.941, "Be": 9.012, "B": 10.81,
    "C": 12.011, "N": 14.007, "O": 15.999, "F": 18.998, "Ne": 20.180,
    "Na": 22.990, "Mg": 24.305, "Al": 26.982, "Si": 28.086, "P": 30.974,
    "S": 32.06, "Cl": 35.45, "Ar": 39.948, "K": 39.098, "Ca": 40.078,
    "Ti": 47.867, "V": 50.942, "Cr": 51.996, "Mn": 54.938, "Fe": 55.845,
    "Co": 58.933, "Ni": 58.693, "Cu": 63.546, "Zn": 65.38, "Ga": 69.723,
    "Ge": 72.63, "As": 74.922, "Se": 78.971, "Br": 79.904, "Sr": 87.62,
    "Zr": 91.224, "Mo": 95.95, "Ru": 101.07, "Rh": 102.91, "Pd": 106.42,
    "Ag": 107.87, "Cd": 112.41, "In": 114.82, "Sn": 118.71, "Te": 127.60,
    "I": 126.90, "Ba": 137.33, "La": 138.91, "Pt": 195.08, "Au": 196.97,
}


def _element_mass(symbol: str) -> float:
    return _ELEMENT_MASSES.get(symbol, 1.0)


def _slugify(name: str) -> str:
    """Simple slugification: lowercase, replace spaces/underscores with hyphens."""
    import re
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "unnamed"


# Input spec adaptation for corpus

def _adapt_input_spec_to_corpus(
    spec: Any,
    case_dir: Path,
) -> Any:
    """
    Adapt an EngineInputSpec so its filenames match the actual files in the corpus dir.

    The input spec from get_input_spec() uses default filenames (e.g., run.abi, orca_calc.inp)
    but corpus directories may use different names (e.g., si_scf.abi, input.inp).
    This function finds the actual file in the corpus and rewrites the spec filename.
    """
    from quantumvitas.inputformat.core import EngineInputSpec, InputFileSpec

    # Map file extensions to find actual files
    ext_map = {}
    for f in case_dir.iterdir():
        if f.is_file() and f.name != "case.yaml":
            ext = f.suffix.lower()
            ext_map.setdefault(ext, []).append(f.name)

    new_files = []
    for file_spec in spec.input_files:
        target = case_dir / file_spec.filename
        if target.exists():
            # File exists with the expected name
            new_files.append(file_spec)
        else:
            # Try to find a file with the same extension
            ext = Path(file_spec.filename).suffix.lower()
            candidates = ext_map.get(ext, [])
            if len(candidates) == 1:
                # Single candidate: use it
                new_files.append(InputFileSpec(
                    filename=candidates[0],
                    content_role=file_spec.content_role,
                    description=file_spec.description,
                    optional=file_spec.optional,
                    custom_writer=file_spec.custom_writer,
                    custom_parser=file_spec.custom_parser,
                ))
            elif candidates:
                # Multiple candidates: try the first one
                new_files.append(InputFileSpec(
                    filename=candidates[0],
                    content_role=file_spec.content_role,
                    description=file_spec.description,
                    optional=file_spec.optional,
                    custom_writer=file_spec.custom_writer,
                    custom_parser=file_spec.custom_parser,
                ))
            elif file_spec.optional:
                new_files.append(file_spec)
            else:
                # Required file not found and no candidates - keep original (will fail at parse)
                new_files.append(file_spec)

    return EngineInputSpec(
        engine_family=spec.engine_family,
        syntax_family=spec.syntax_family,
        input_files=tuple(new_files),
        resource_refs=spec.resource_refs,
        ssot_mapping=spec.ssot_mapping,
    )


# Main translator

def translate_corpus_case(
    case_dir: Path,
    case_data: Dict[str, Any],
    index_entry: Dict[str, Any],
    repo_root: Path,
) -> Dict[str, Any]:
    """
    Translate a single corpus case to a demo project snapshot dict.

    This is the core translation pipeline per S4.3.

    Args:
        case_dir: Path to the corpus case directory.
        case_data: Parsed case.yaml.
        index_entry: Corresponding corpus_index entry.
        repo_root: Repository root path.

    Returns:
        Snapshot dict ready for YAML serialization.

    Raises:
        ValueError: On validation failure.
    """
    # 1. Validate
    errors = validate_case_yaml(case_data, index_entry)
    if errors:
        raise ValueError(
            f"Validation failed for {case_data.get('case_id', '?')}: "
            + "; ".join(errors)
        )

    demo_slug = case_data["demo_slug"]
    engine = case_data["engine"]
    species = case_data.get("species", [])
    multi_step = case_data.get("multi_step", False)

    # Check for direct_snapshot mode (Python-script engines)
    parser_mode = case_data.get("parser_mode")
    if parser_mode == "direct_snapshot":
        from quantumvitas.demo_store.direct_snapshot import build_direct_snapshot
        return build_direct_snapshot(case_data, index_entry, repo_root)

    # 2. Parse - for multi-step, parse each step's files separately
    if multi_step:
        return _translate_multi_step(case_dir, case_data, index_entry, repo_root)

    # Single-step: parse all input files together
    return _translate_single_step(case_dir, case_data, index_entry, repo_root)


def _translate_single_step(
    case_dir: Path,
    case_data: Dict[str, Any],
    index_entry: Dict[str, Any],
    repo_root: Path,
) -> Dict[str, Any]:
    """Translate a single-step corpus case."""
    demo_slug = case_data["demo_slug"]
    engine = case_data["engine"]
    species = case_data.get("species", [])
    step_type_gen = case_data["step_type_gen"]
    step_type_spec = case_data["step_type_spec"]

    # Get engine input spec via DriverRegistry
    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers  # noqa: F401 — trigger registration

    driver = DriverRegistry.get_driver(engine)
    input_spec = driver.get_input_spec()

    if input_spec is None:
        raise ValueError(f"Engine {engine} returned None input_spec")

    # Adapt input_spec filenames to match actual files in the corpus dir
    input_spec = _adapt_input_spec_to_corpus(input_spec, case_dir)

    # Parse engine input files
    from quantumvitas.inputformat.parser import parse_engine_inputs
    parse_result = parse_engine_inputs(input_spec, case_dir)

    params = parse_result.params
    structure_doc = parse_result.structure

    # 3. Map to pymatgen structure
    structure_data = None
    if structure_doc:
        structure_data = _structure_doc_to_pymatgen_dict(structure_doc, engine)

    # Build structure name from species
    struct_name = _make_structure_name(species)
    struct_slug = _slugify(struct_name)

    # Build calculation name
    calc_name = case_data.get("title", f"{engine} {step_type_gen}")
    calc_slug = _slugify(calc_name)

    # 4. Assemble snapshot with deterministic ULIDs
    project_ulid = deterministic_ulid(demo_slug, "project")
    struct_ulid = deterministic_ulid(demo_slug, f"structure:{struct_slug}")
    calc_ulid = deterministic_ulid(demo_slug, f"calculation:{calc_slug}")
    step_ulid = deterministic_ulid(demo_slug, f"step:{calc_slug}:{_slugify(step_type_gen)}")

    # Resolve pseudo info
    pseudo_section, pseudo_species_map = _resolve_pseudo_info(
        engine, species, case_data, repo_root
    )

    # Build species_map from params or pseudo info
    species_map = pseudo_species_map or _build_species_map_from_params(engine, params, species)

    # Build step dict
    step_dict = {
        "meta": {
            "name": step_type_gen,
            "slug": _slugify(step_type_gen),
            "path": f"calculations/{calc_slug}/steps/{_slugify(step_type_gen)}.step.yaml",
            "kind": "step",
            "ulid": step_ulid,
        },
        "parameters": params,
        "step_type_spec": step_type_spec,
    }

    # Build calculation dict
    calc_dict = {
        "meta": {
            "ulid": calc_ulid,
            "name": calc_name,
            "slug": calc_slug,
            "path": f"calculations/{calc_slug}",
            "kind": "calculation",
        },
        "mode": "normal",
        "working_dir": "raw",
        "engine_family": engine,
        "steps": [step_dict],
    }

    if structure_data:
        calc_dict["structure_ulid"] = struct_ulid

    if species_map:
        calc_dict["species_map"] = species_map

    # Build structures list
    structures = []
    if structure_data:
        structures.append({
            "meta": {
                "ulid": struct_ulid,
                "name": struct_name,
                "slug": struct_slug,
                "path": f"structures/{struct_slug}.json",
                "kind": "structure",
            },
            "data": structure_data,
        })

    # Build project
    project_name = case_data.get("title", demo_slug)

    snapshot = {
        "version": 1,
        "project": {
            "meta": {
                "ulid": project_ulid,
                "name": project_name,
                "slug": _slugify(project_name),
                "path": ".",
                "kind": "project",
            },
            "settings": {},
        },
        "structures": structures,
        "calculations": [calc_dict],
    }

    if pseudo_section:
        snapshot["pseudo"] = pseudo_section

    # Add demo gallery metadata
    snapshot["meta"] = _build_gallery_meta(case_data, index_entry, case_dir)

    return snapshot


def _translate_multi_step(
    case_dir: Path,
    case_data: Dict[str, Any],
    index_entry: Dict[str, Any],
    repo_root: Path,
) -> Dict[str, Any]:
    """Translate a multi-step corpus case (e.g., QE SCF->NSCF->Bands)."""
    demo_slug = case_data["demo_slug"]
    engine = case_data["engine"]
    species = case_data.get("species", [])
    steps_def = case_data.get("steps", [])

    if len(steps_def) < 2:
        raise ValueError(f"multi_step is true but steps has {len(steps_def)} entries")

    # Get engine input spec
    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers  # noqa: F401

    driver = DriverRegistry.get_driver(engine)
    input_spec = driver.get_input_spec()

    # Parse each step's input files
    from quantumvitas.inputformat.parser import parse_engine_inputs

    parsed_steps = []
    first_structure = None

    for step_def in steps_def:
        step_gen = step_def["step_type_gen"]
        step_spec = step_def["step_type_spec"]
        input_files = step_def.get("input_files", [])

        # Parse each input file
        step_params: Dict[str, Any] = {}
        step_structure = None

        for input_file in input_files:
            file_path = case_dir / input_file
            if file_path.exists():
                # Find the matching file spec from input_spec
                for fs in input_spec.input_files:
                    if fs.filename == input_file and fs.custom_parser:
                        text = file_path.read_text()
                        parsed = fs.custom_parser(text)
                        if fs.content_role == "parameters":
                            step_params.update(parsed)
                        elif fs.content_role == "structure":
                            step_structure = parsed
                        elif fs.content_role == "combined":
                            if "params" in parsed:
                                step_params.update(parsed["params"])
                            if "structure" in parsed:
                                step_structure = parsed["structure"]
                        elif fs.content_role == "kpoints":
                            step_params["kpoints"] = parsed
                        break
                else:
                    # No matching spec - try reading as the primary input
                    # For QE, all .in files use the same parser
                    for fs in input_spec.input_files:
                        if fs.content_role == "combined" and fs.custom_parser:
                            text = file_path.read_text()
                            parsed = fs.custom_parser(text)
                            if "params" in parsed:
                                step_params.update(parsed["params"])
                            if "structure" in parsed:
                                step_structure = parsed["structure"]
                            break

        if step_structure and first_structure is None:
            first_structure = step_structure

        parsed_steps.append({
            "step_type_gen": step_gen,
            "step_type_spec": step_spec,
            "params": step_params,
        })

    # Build pymatgen structure from first step's structure
    structure_data = None
    if first_structure:
        structure_data = _structure_doc_to_pymatgen_dict(first_structure, engine)

    struct_name = _make_structure_name(species)
    struct_slug = _slugify(struct_name)
    calc_name = case_data.get("title", f"{engine} multi-step")
    calc_slug = _slugify(calc_name)

    # Deterministic ULIDs
    project_ulid = deterministic_ulid(demo_slug, "project")
    struct_ulid = deterministic_ulid(demo_slug, f"structure:{struct_slug}")
    calc_ulid = deterministic_ulid(demo_slug, f"calculation:{calc_slug}")

    # Resolve pseudo info
    pseudo_section, pseudo_species_map = _resolve_pseudo_info(
        engine, species, case_data, repo_root
    )
    species_map = pseudo_species_map or _build_species_map_from_params(
        engine, parsed_steps[0]["params"] if parsed_steps else {}, species
    )

    # Build step dicts
    step_dicts = []
    for ps in parsed_steps:
        step_slug = _slugify(ps["step_type_gen"])
        step_ulid = deterministic_ulid(
            demo_slug, f"step:{calc_slug}:{step_slug}"
        )
        step_dicts.append({
            "meta": {
                "name": ps["step_type_gen"],
                "slug": step_slug,
                "path": f"calculations/{calc_slug}/steps/{step_slug}.step.yaml",
                "kind": "step",
                "ulid": step_ulid,
            },
            "parameters": ps["params"],
            "step_type_spec": ps["step_type_spec"],
        })

    # Build calculation
    calc_dict = {
        "meta": {
            "ulid": calc_ulid,
            "name": calc_name,
            "slug": calc_slug,
            "path": f"calculations/{calc_slug}",
            "kind": "calculation",
        },
        "mode": "normal",
        "working_dir": "raw",
        "engine_family": engine,
        "steps": step_dicts,
    }

    if structure_data:
        calc_dict["structure_ulid"] = struct_ulid
    if species_map:
        calc_dict["species_map"] = species_map

    structures = []
    if structure_data:
        structures.append({
            "meta": {
                "ulid": struct_ulid,
                "name": struct_name,
                "slug": struct_slug,
                "path": f"structures/{struct_slug}.json",
                "kind": "structure",
            },
            "data": structure_data,
        })

    project_name = case_data.get("title", demo_slug)

    snapshot = {
        "version": 1,
        "project": {
            "meta": {
                "ulid": project_ulid,
                "name": project_name,
                "slug": _slugify(project_name),
                "path": ".",
                "kind": "project",
            },
            "settings": {},
        },
        "structures": structures,
        "calculations": [calc_dict],
    }

    if pseudo_section:
        snapshot["pseudo"] = pseudo_section

    snapshot["meta"] = _build_gallery_meta(case_data, index_entry, case_dir)

    return snapshot


def _make_structure_name(species: List[str]) -> str:
    """Build a structure name from species list."""
    if not species:
        return "structure"
    if len(species) == 1:
        return species[0]
    # Chemical formula-like name
    from collections import Counter
    counts = Counter(species)
    parts = []
    for elem in sorted(counts.keys()):
        n = counts[elem]
        parts.append(f"{elem}{n}" if n > 1 else elem)
    return "".join(parts)


def _build_gallery_meta(
    case_data: Dict[str, Any],
    index_entry: Dict[str, Any],
    case_dir: Path,
) -> Dict[str, Any]:
    """Build the demo gallery metadata section."""
    from quantumvitas.demo_store.manifest import _compute_dir_checksum, GENERATOR_VERSION

    meta: Dict[str, Any] = {
        "ulid": case_data["demo_slug"],
        "title": case_data.get("title", case_data["demo_slug"]),
        "subtitle": case_data.get("subtitle", case_data.get("step_type_gen", "")),
        "tags": case_data.get("tags", case_data.get("workflow_tags", [])),
        "recommended_analysis": case_data.get("recommended_analysis", "scf"),
        "difficulty": case_data.get("difficulty", "beginner"),
    }

    # Asset policy info
    asset_policy = case_data.get("asset_policy", "none")
    if asset_policy != "none":
        meta["asset_policy"] = asset_policy
    if case_data.get("asset_requirements"):
        meta["asset_requirements"] = case_data["asset_requirements"]

    meta["required_engine"] = case_data.get("required_engine", case_data["engine"])
    meta["availability"] = case_data.get("availability", "open_source")

    # Generator provenance (Rule DP6)
    meta["generator_version"] = GENERATOR_VERSION
    meta["corpus_engine"] = case_data["engine"]
    meta["corpus_case_id"] = case_data["case_id"]
    meta["corpus_checksum"] = _compute_dir_checksum(case_dir)

    return meta
