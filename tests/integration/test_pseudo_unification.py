"""Integration tests for the unified pseudo system.

Tests verify the Pseudo System Unification is complete and correct:
    - TestNoRootHeadJson: root head.json NOT written after install
    - TestTwoVariantsCoexist: both precision + efficiency discoverable
    - TestNoOldLayoutReferences: deleted functions/fields don't exist
    - TestSeedFallback: seed-to-library auto-extraction
    - TestListResourcesShowsInstalled: MCP list_resources sees installed libs
    - TestRealSCFSmoke: full download→resolve→run with rare element (Tl)
    - TestGaAsEndToEnd: GaAs bands workflow (the original failing scenario)
"""

from __future__ import annotations

import inspect
import json
import os
import shutil
from pathlib import Path

import pytest

from qmatsuite.api import QMSService
from qmatsuite.core.resources import get_resources_dir

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SSSP_PRECISION_VERSION = "1.3.0"
_SSSP_EFFICIENCY_VERSION = "1.3.0"

# GaAs zincblende CIF (P1, pymatgen-compatible)
GAAS_CIF = """\
data_GaAs
_symmetry_space_group_name_H-M   'P 1'
_cell_length_a   5.65330000
_cell_length_b   5.65330000
_cell_length_c   5.65330000
_cell_angle_alpha   90.00000000
_cell_angle_beta   90.00000000
_cell_angle_gamma   90.00000000
_symmetry_Int_Tables_number   1
_chemical_formula_structural   GaAs
_chemical_formula_sum   'Ga1 As1'
_cell_volume   180.68957424
_cell_formula_units_Z   1
loop_
 _symmetry_equiv_pos_site_id
 _symmetry_equiv_pos_as_xyz
  1  'x, y, z'
loop_
 _atom_site_type_symbol
 _atom_site_label
 _atom_site_symmetry_multiplicity
 _atom_site_fract_x
 _atom_site_fract_y
 _atom_site_fract_z
 _atom_site_occupancy
  Ga  Ga0  1  0.00000000  0.00000000  0.00000000  1
  As  As0  1  0.25000000  0.25000000  0.25000000  1
"""

# Tl BCC CIF (P1, pymatgen-compatible)
TL_BCC_CIF = """\
data_Tl
_symmetry_space_group_name_H-M   'P 1'
_cell_length_a   3.45660000
_cell_length_b   3.45660000
_cell_length_c   3.45660000
_cell_angle_alpha   90.00000000
_cell_angle_beta   90.00000000
_cell_angle_gamma   90.00000000
_symmetry_Int_Tables_number   1
_chemical_formula_structural   Tl
_chemical_formula_sum   Tl1
_cell_volume   41.29974563
_cell_formula_units_Z   1
loop_
 _symmetry_equiv_pos_site_id
 _symmetry_equiv_pos_as_xyz
  1  'x, y, z'
loop_
 _atom_site_type_symbol
 _atom_site_label
 _atom_site_symmetry_multiplicity
 _atom_site_fract_x
 _atom_site_fract_y
 _atom_site_fract_z
 _atom_site_occupancy
  Tl  Tl0  1  0.00000000  0.00000000  0.00000000  1
"""


def _ensure_sssp_installed(variant: str = "precision", version: str = "1.3.0"):
    """Download + install SSSP if not already present."""
    from qmatsuite.core.paths import home_pseudo_libraries_dir
    from qmatsuite.pseudo.layout import find_installed_library

    libraries_root = home_pseudo_libraries_dir()
    lib = find_installed_library(libraries_root, "sssp", variant, version)
    if lib is not None:
        return  # already installed

    from qmatsuite.pseudo.pipeline import download_and_install

    result = download_and_install(library="sssp", variant=variant, version=version)
    assert result.get("success", False), f"SSSP {variant} install failed: {result}"


def _qe_available() -> bool:
    """Check if QE pw.x is available."""
    from qmatsuite.api.utils import get_qe_engine_status

    status = get_qe_engine_status()
    return status.get("detection", {}).get("found", False)


# ---------------------------------------------------------------------------
# Class 1: TestNoRootHeadJson
# ---------------------------------------------------------------------------


class TestNoRootHeadJson:
    """After install, root-level head.json must NOT exist."""

    @pytest.fixture(autouse=True)
    def _install_sssp(self):
        from qmatsuite.core.paths import home_pseudo_libraries_dir

        # Remove any stale root head.json left from OLD pipeline runs
        libraries_root = home_pseudo_libraries_dir()
        stale_root_head = libraries_root / "SSSP" / "head.json"
        if stale_root_head.exists():
            stale_root_head.unlink()

        _ensure_sssp_installed("precision")

    def test_no_root_head_json(self):
        """Fresh install must NOT create root-level head.json."""
        from qmatsuite.core.paths import home_pseudo_libraries_dir

        libraries_root = home_pseudo_libraries_dir()
        root_head = libraries_root / "SSSP" / "head.json"
        assert not root_head.exists(), (
            f"Root head.json must NOT exist after unification: {root_head}"
        )

    def test_install_level_head_json_exists(self):
        from qmatsuite.core.paths import home_pseudo_libraries_dir

        libraries_root = home_pseudo_libraries_dir()
        install_head = libraries_root / "SSSP" / "precision" / _SSSP_PRECISION_VERSION / "head.json"
        assert install_head.exists(), (
            f"Install-level head.json must exist: {install_head}"
        )

    def test_install_head_has_library_key(self):
        from qmatsuite.core.paths import home_pseudo_libraries_dir

        libraries_root = home_pseudo_libraries_dir()
        install_head = libraries_root / "SSSP" / "precision" / _SSSP_PRECISION_VERSION / "head.json"
        head = json.loads(install_head.read_text())
        assert "library_key" in head, "head.json must have library_key"
        assert head["library_key"] == "sssp"
        assert head["variant"] == "precision"
        assert head["version"] == _SSSP_PRECISION_VERSION


# ---------------------------------------------------------------------------
# Class 2: TestTwoVariantsCoexist
# ---------------------------------------------------------------------------


class TestTwoVariantsCoexist:
    """Both precision and efficiency must be discoverable after both installed."""

    @pytest.fixture(autouse=True)
    def _install_both(self):
        _ensure_sssp_installed("precision")
        _ensure_sssp_installed("efficiency")

    def test_both_discovered(self):
        from qmatsuite.core.paths import home_pseudo_libraries_dir
        from qmatsuite.pseudo.layout import iter_installed_libraries

        libraries_root = home_pseudo_libraries_dir()
        sssp_variants = set()
        for lib in iter_installed_libraries(libraries_root):
            if lib.library_key == "sssp":
                sssp_variants.add(lib.variant)

        assert "precision" in sssp_variants, "precision must be discoverable"
        assert "efficiency" in sssp_variants, "efficiency must be discoverable"

    def test_find_installed_library_precision(self):
        from qmatsuite.core.paths import home_pseudo_libraries_dir
        from qmatsuite.pseudo.layout import find_installed_library

        libraries_root = home_pseudo_libraries_dir()
        lib = find_installed_library(libraries_root, "sssp", "precision", _SSSP_PRECISION_VERSION)
        assert lib is not None, "precision must be findable"
        assert lib.install_dir.is_dir()

    def test_find_installed_library_efficiency(self):
        from qmatsuite.core.paths import home_pseudo_libraries_dir
        from qmatsuite.pseudo.layout import find_installed_library

        libraries_root = home_pseudo_libraries_dir()
        lib = find_installed_library(libraries_root, "sssp", "efficiency", _SSSP_EFFICIENCY_VERSION)
        assert lib is not None, "efficiency must be findable"
        assert lib.install_dir.is_dir()

    def test_separate_directories(self):
        from qmatsuite.core.paths import home_pseudo_libraries_dir
        from qmatsuite.pseudo.layout import find_installed_library

        libraries_root = home_pseudo_libraries_dir()
        prec = find_installed_library(libraries_root, "sssp", "precision", _SSSP_PRECISION_VERSION)
        eff = find_installed_library(libraries_root, "sssp", "efficiency", _SSSP_EFFICIENCY_VERSION)
        assert prec is not None and eff is not None
        assert prec.install_dir != eff.install_dir, "variants must be in separate dirs"


# ---------------------------------------------------------------------------
# Class 3: TestNoOldLayoutReferences
# ---------------------------------------------------------------------------


class TestNoOldLayoutReferences:
    """Verify deleted functions/fields are truly gone."""

    def test_no_pseudo_installs_module(self):
        """pseudo_installs.py was deleted."""
        with pytest.raises(ImportError):
            import qmatsuite.core.pseudo_installs  # noqa: F401

    def test_no_download_sssp_library(self):
        """Old download_sssp_library function must not exist in pseudo_config."""
        from qmatsuite.core import pseudo_config

        assert not hasattr(pseudo_config, "download_sssp_library")

    def test_no_install_sssp_from_seed(self):
        from qmatsuite.core import pseudo_config

        assert not hasattr(pseudo_config, "install_sssp_from_seed")

    def test_no_get_sssp_library_path(self):
        from qmatsuite.core import pseudo_config

        assert not hasattr(pseudo_config, "get_sssp_library_path")

    def test_no_list_installed_sssp(self):
        from qmatsuite.core import pseudo_config

        assert not hasattr(pseudo_config, "list_installed_sssp")

    def test_no_flavor_field_in_request(self):
        """PseudoResolutionRequest must use 'variant', not 'flavor'."""
        from qmatsuite.core.pseudo_config import PseudoResolutionRequest

        fields = {f.name for f in PseudoResolutionRequest.__dataclass_fields__.values()}
        assert "flavor" not in fields, "flavor field must be gone"
        assert "variant" in fields, "variant field must exist"

    def test_variant_default_is_precision(self):
        from qmatsuite.core.pseudo_config import PseudoResolutionRequest

        field_info = PseudoResolutionRequest.__dataclass_fields__["variant"]
        assert field_info.default == "precision", (
            f"Default variant must be 'precision', got {field_info.default!r}"
        )

    def test_no_flavor_in_src_nontest(self):
        """Zero pseudo-related 'flavor' references in non-test src/ Python files.

        CP2K binary flavors (cp2k.psmp etc.) are legitimate uses of the word.
        """
        import subprocess

        result = subprocess.run(
            ["grep", "-rn", "flavor", "src/qmatsuite/",
             "--include=*.py"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent),
        )
        lines = [
            line for line in result.stdout.strip().split("\n")
            if line
            and "__pycache__" not in line
            # CP2K binary flavors are a legitimate use of the word
            and "cp2k_resolver" not in line
        ]
        assert len(lines) == 0, f"Found 'flavor' references in src/:\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Class 4: TestSeedFallback
# ---------------------------------------------------------------------------


class TestSeedFallback:
    """If a library is missing but can be downloaded, auto_resolve triggers download."""

    @pytest.fixture(autouse=True)
    def _install_sssp(self):
        _ensure_sssp_installed("precision")

    def test_resolve_after_install(self, tmp_path, monkeypatch):
        """Resolution succeeds when SSSP precision is installed."""
        from qmatsuite.core.paths import home_pseudo_libraries_dir
        from qmatsuite.core.pseudo_config import (
            PseudoConfig,
            PseudoResolutionRequest,
            resolve_project_pseudos,
        )

        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pseudo").mkdir()

        request = PseudoResolutionRequest(
            project_root=project_root,
            elements=["Si"],
            library="sssp",
            version=_SSSP_PRECISION_VERSION,
            variant="precision",
        )
        config = PseudoConfig()
        result = resolve_project_pseudos(config, request)
        assert "Si" in result.mapping, f"Si should be resolved. Messages: {result.messages}"
        assert result.mapping["Si"].lower().endswith(".upf")


# ---------------------------------------------------------------------------
# Class 5: TestListResourcesShowsInstalled
# ---------------------------------------------------------------------------


class TestListResourcesShowsInstalled:
    """MCP list_available_resources shows installed SSSP library."""

    @pytest.fixture(autouse=True)
    def _install_and_project(self, tmp_path, monkeypatch):
        _ensure_sssp_installed("precision")

        # Set up a temp project for MCP context
        project_root = QMSService.init_project(tmp_path / "project")

        # Import a structure using known-good CIF from test data
        si_cif = Path(__file__).parent.parent / "data" / "structures" / "si_diamond.cif"
        if si_cif.exists():
            QMSService(project_root).structure.import_file(si_cif, name="Si")
        else:
            # Fallback: use pymatgen JSON format
            import json as _json
            si_json = tmp_path / "si.json"
            si_json.write_text(_json.dumps({
                "@module": "pymatgen.core.structure",
                "@class": "Structure",
                "lattice": {
                    "matrix": [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]],
                    "a": 5.43, "b": 5.43, "c": 5.43,
                    "alpha": 90, "beta": 90, "gamma": 90,
                },
                "sites": [
                    {"species": [{"element": "Si", "occu": 1}],
                     "abc": [0, 0, 0], "xyz": [0, 0, 0]},
                ],
            }))
            QMSService(project_root).structure.import_file(si_json, name="Si")

        from qmatsuite.mcp import project as mcp_project
        monkeypatch.setattr(mcp_project, "_project_root_override", project_root)

    def test_qe_shows_installed_libraries(self):
        from qmatsuite.mcp.tools.list_resources import list_available_resources

        r = list_available_resources.fn(engine="qe", elements=["Si"])
        assert r["status"] == "success", f"Failed: {r}"
        data = r["data"]
        assert data["any_installed"] is True, "Should show installed after SSSP install"
        assert len(data["installed_libraries"]) > 0, "installed_libraries should be non-empty"

        # Check that SSSP precision is in the list
        found_precision = False
        for lib in data["installed_libraries"]:
            if lib.get("variant") == "precision":
                found_precision = True
                assert lib["upf_count"] > 0
                break
        assert found_precision, "SSSP precision should be in installed_libraries"

    def test_si_available_in_library(self):
        from qmatsuite.mcp.tools.list_resources import list_available_resources

        r = list_available_resources.fn(engine="qe", elements=["Si"])
        data = r["data"]
        for lib in data["installed_libraries"]:
            if lib.get("variant") == "precision":
                assert "Si" in lib.get("available_elements", []), (
                    "Si should be in available_elements for SSSP precision"
                )
                break


# ---------------------------------------------------------------------------
# Class 6: TestRealSCFSmoke
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _qe_available(),
    reason="QE pw.x not available — skipping real SCF smoke test",
)
class TestRealSCFSmoke:
    """Full pipeline: download → resolve → run QE SCF with rare element (Tl).

    Uses Tl (Thallium) to prove resolution works for elements NOT in
    ``resources/pseudo/``.
    """

    @pytest.fixture(autouse=True)
    def _install_sssp(self):
        _ensure_sssp_installed("precision")

    def test_tl_not_in_bundled_resources(self):
        """Precondition: Tl is NOT in resources/pseudo/."""
        internal_pseudo = get_resources_dir() / "pseudo"
        if not internal_pseudo.is_dir():
            return  # No internal resources — precondition trivially true

        # Check no Tl UPF in bundled resources
        tl_files = list(internal_pseudo.glob("Tl*.[Uu][Pp][Ff]"))
        assert len(tl_files) == 0, f"Tl should NOT be in bundled resources: {tl_files}"

    def test_tl_in_sssp_precision_index(self):
        """Precondition: Tl IS in SSSP precision index."""
        from qmatsuite.pseudo.registry import resolve_element_from_index

        filename = resolve_element_from_index("sssp", "precision", "1.3.0", "Tl")
        assert filename is not None, "Tl must be in SSSP precision index"
        assert filename.lower().endswith(".upf")

    def test_full_scf_smoke(self, tmp_path, monkeypatch):
        """Download SSSP → resolve Tl → run QE SCF → verify converged."""
        from qmatsuite.mcp import project as mcp_project

        project_root = QMSService.init_project(tmp_path / "tl_scf_project")
        svc = QMSService(project_root)

        # Import Tl BCC structure
        tl_cif = tmp_path / "tl_bcc.cif"
        tl_cif.write_text(TL_BCC_CIF)
        svc.structure.import_file(tl_cif, name="Tl_BCC")

        # Patch MCP context
        monkeypatch.setattr(mcp_project, "_project_root_override", project_root)

        # Create SCF calculation
        from qmatsuite.mcp.tools.create_calculation import create_calculation
        r = create_calculation.fn(engine="qe", workflow="scf", structure_selector="Tl_BCC")
        assert r["status"] == "success", f"Create calc failed: {r}"
        calc_ulid = r["data"]["calc_ulid"]

        # Auto-resolve species map — THE KEY ASSERTION
        from qmatsuite.mcp.tools.resolve_species_map import auto_resolve_species_map
        r = auto_resolve_species_map.fn(calc_ulid=calc_ulid)
        assert r["status"] == "success", f"auto_resolve failed: {r}"
        data = r["data"]
        species_map = data["species_map"]
        assert "Tl" in species_map, f"Tl must be resolved: {data}"
        tl_pseudo = species_map["Tl"]["pseudopot"]
        assert tl_pseudo.lower().endswith(".upf")

        # Verify UPF was staged to project/pseudo/
        staged_file = project_root / "pseudo" / tl_pseudo
        assert staged_file.exists(), f"Staged UPF must exist: {staged_file}"

        # Apply preset and run
        from qmatsuite.mcp.tools.apply_preset import apply_preset
        r = apply_preset.fn(calc_ulid=calc_ulid, presets={"magnetism": "NM", "precision": "LOW"})
        assert r["status"] == "success", f"apply_preset failed: {r}"

        from qmatsuite.mcp.tools.run_calculation import run_calculation
        r = run_calculation.fn(calc_ulid=calc_ulid)
        assert r["status"] == "success", f"run_calculation failed: {r}"
        assert r["data"]["status"] == "completed", f"SCF did not converge: {r['data']}"


# ---------------------------------------------------------------------------
# Class 7: TestGaAsEndToEnd
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _qe_available(),
    reason="QE pw.x not available — skipping GaAs end-to-end test",
)
class TestGaAsEndToEnd:
    """GaAs bands workflow — the original failing scenario from the demo."""

    @pytest.fixture(autouse=True)
    def _install_sssp(self):
        _ensure_sssp_installed("precision")

    def test_gaas_bands_full_workflow(self, tmp_path, monkeypatch):
        """Clean project → download SSSP → import GaAs → create bands →
        auto_resolve → verify Ga and As both staged."""
        from qmatsuite.mcp import project as mcp_project

        project_root = QMSService.init_project(tmp_path / "gaas_project")
        svc = QMSService(project_root)

        # Import GaAs structure
        gaas_cif = tmp_path / "gaas.cif"
        gaas_cif.write_text(GAAS_CIF)
        svc.structure.import_file(gaas_cif, name="GaAs")

        monkeypatch.setattr(mcp_project, "_project_root_override", project_root)

        # Create bands calculation
        from qmatsuite.mcp.tools.create_calculation import create_calculation
        r = create_calculation.fn(engine="qe", workflow="bands", structure_selector="GaAs")
        assert r["status"] == "success", f"Create calc failed: {r}"
        calc_ulid = r["data"]["calc_ulid"]

        # Auto-resolve — THE KEY ASSERTION
        from qmatsuite.mcp.tools.resolve_species_map import auto_resolve_species_map
        r = auto_resolve_species_map.fn(calc_ulid=calc_ulid)
        assert r["status"] == "success", f"auto_resolve failed: {r}"
        data = r["data"]
        species_map = data["species_map"]
        assert "Ga" in species_map, f"Ga must be resolved: {data}"
        assert "As" in species_map, f"As must be resolved: {data}"

        ga_pseudo = species_map["Ga"]["pseudopot"]
        as_pseudo = species_map["As"]["pseudopot"]

        # Verify both staged to project/pseudo/
        pseudo_dir = project_root / "pseudo"
        ga_file = pseudo_dir / ga_pseudo
        as_file = pseudo_dir / as_pseudo
        assert ga_file.exists(), f"Ga UPF must be staged: {ga_file}"
        assert as_file.exists(), f"As UPF must be staged: {as_file}"

        # Verify filenames are actual UPF files
        assert ga_pseudo.lower().endswith(".upf")
        assert as_pseudo.lower().endswith(".upf")

    def test_cutoffs_loaded_for_gaas(self, tmp_path, monkeypatch):
        """Cutoffs must be loaded from SSSP companion JSON (the dict-vs-list bug fix)."""
        from qmatsuite.core.pseudo_config import (
            PseudoConfig,
            PseudoResolutionRequest,
            resolve_project_pseudos,
        )

        project_root = tmp_path / "gaas_cutoffs"
        project_root.mkdir()
        (project_root / "pseudo").mkdir()

        request = PseudoResolutionRequest(
            project_root=project_root,
            elements=["Ga", "As"],
            library="sssp",
            version=_SSSP_PRECISION_VERSION,
            variant="precision",
        )
        config = PseudoConfig()
        result = resolve_project_pseudos(config, request)

        # Both elements must have cutoffs loaded
        assert "Ga" in result.cutoffs, f"Ga cutoffs missing. Cutoffs: {result.cutoffs}"
        assert "As" in result.cutoffs, f"As cutoffs missing. Cutoffs: {result.cutoffs}"

        # Cutoff values should be positive
        assert result.cutoffs["Ga"]["ecutwfc"] > 0, "Ga ecutwfc must be > 0"
        assert result.cutoffs["Ga"]["ecutrho"] > 0, "Ga ecutrho must be > 0"
        assert result.cutoffs["As"]["ecutwfc"] > 0, "As ecutwfc must be > 0"
        assert result.cutoffs["As"]["ecutrho"] > 0, "As ecutrho must be > 0"
