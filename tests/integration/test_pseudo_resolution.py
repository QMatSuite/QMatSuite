"""Integration tests for deterministic pseudo resolution.

Tests are grouped:
    - TestIndexLookup: unit-level, no network (index loading, element lookup, C vs Cu)
    - TestArchiveInstallRelpath: unit-level (path computation from ArchiveInfo)
    - TestResolutionChain: integration (uses installed libraries, head.json scan)
    - TestBandspwDefaults: unit-level (diago_full_acc in qe_bandspw)
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Class A: Index lookup tests — no network
# ---------------------------------------------------------------------------


class TestIndexLookup:
    """Test resolve_element_from_index() from vendored PSEUDO_FILE_INDEX.json."""

    def test_resolve_si_sssp_precision(self):
        from quantumvitas.pseudo.registry import resolve_element_from_index

        filename = resolve_element_from_index("sssp", "precision", "1.3.0", "Si")
        assert filename is not None, "Si should be in SSSP precision"
        assert "Si" in filename
        assert filename.lower().endswith(".upf")

    def test_resolve_c_sssp_precision(self):
        """C must return Carbon pseudo, NOT Copper — the core bug fix."""
        from quantumvitas.pseudo.registry import resolve_element_from_index

        filename = resolve_element_from_index("sssp", "precision", "1.3.0", "C")
        assert filename is not None, "C should be in SSSP precision"
        # Must be a Carbon pseudo, not Copper
        assert not filename.startswith("Cu"), (
            f"C resolved to Copper pseudo {filename!r} — the C/Cu bug is NOT fixed"
        )
        # Filename should start with C followed by a separator (not Cu, Ca, etc.)
        basename = Path(filename).stem
        assert basename[0] == "C"
        # Second char should NOT be an uppercase letter (that would be another element)
        if len(basename) > 1:
            assert not basename[1].isupper() or basename[1] == ".", (
                f"C resolved to wrong element pseudo: {filename!r}"
            )

    def test_resolve_cu_sssp_precision(self):
        """Cu must return Copper pseudo."""
        from quantumvitas.pseudo.registry import resolve_element_from_index

        filename = resolve_element_from_index("sssp", "precision", "1.3.0", "Cu")
        assert filename is not None, "Cu should be in SSSP precision"
        assert "Cu" in filename

    def test_resolve_nonexistent_element(self):
        from quantumvitas.pseudo.registry import resolve_element_from_index

        filename = resolve_element_from_index("sssp", "precision", "1.3.0", "Xx")
        assert filename is None

    def test_resolve_nonexistent_library(self):
        from quantumvitas.pseudo.registry import resolve_element_from_index

        filename = resolve_element_from_index("nonexistent", "default", "1.0", "Si")
        assert filename is None

    def test_all_common_elements_have_entries(self):
        """SSSP precision should have entries for all common elements."""
        from quantumvitas.pseudo.registry import resolve_element_from_index

        common_elements = [
            "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
            "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar",
            "K", "Ca", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
            "Ga", "Ge", "As", "Se", "Br", "Kr",
            "Ag", "Ba", "Pb", "Bi",
        ]
        missing = []
        for elem in common_elements:
            if resolve_element_from_index("sssp", "precision", "1.3.0", elem) is None:
                missing.append(elem)
        assert not missing, f"Missing elements in SSSP precision index: {missing}"

    def test_deterministic(self):
        """Same call twice must return same result."""
        from quantumvitas.pseudo.registry import resolve_element_from_index

        r1 = resolve_element_from_index("sssp", "precision", "1.3.0", "Si")
        r2 = resolve_element_from_index("sssp", "precision", "1.3.0", "Si")
        assert r1 == r2

    def test_c_and_cu_are_different(self):
        """C and Cu must resolve to different filenames."""
        from quantumvitas.pseudo.registry import resolve_element_from_index

        c_file = resolve_element_from_index("sssp", "precision", "1.3.0", "C")
        cu_file = resolve_element_from_index("sssp", "precision", "1.3.0", "Cu")
        assert c_file is not None
        assert cu_file is not None
        assert c_file != cu_file, f"C and Cu resolved to same file: {c_file}"

    def test_resolve_si_sssp_efficiency(self):
        from quantumvitas.pseudo.registry import resolve_element_from_index

        filename = resolve_element_from_index("sssp", "efficiency", "1.3.0", "Si")
        assert filename is not None
        assert "Si" in filename

    def test_resolve_from_sg15(self):
        """SG15 library should also have elements."""
        from quantumvitas.pseudo.registry import resolve_element_from_index

        filename = resolve_element_from_index("sg15", "oncv", "2020-02-06", "Si")
        assert filename is not None
        assert filename.lower().endswith(".upf")

    def test_resolve_from_gbrv(self):
        """GBRV PBE library should have elements."""
        from quantumvitas.pseudo.registry import resolve_element_from_index

        filename = resolve_element_from_index("gbrv", "pbe", "1.5", "Si")
        assert filename is not None


# ---------------------------------------------------------------------------
# Class B: archive_install_relpath tests
# ---------------------------------------------------------------------------


class TestArchiveInstallRelpath:
    """Test archive_install_relpath() path computation."""

    def test_sssp_precision_path(self):
        from quantumvitas.pseudo.registry import ArchiveInfo, archive_install_relpath

        info = ArchiveInfo(
            filename="SSSP_1.3.0_PBE_precision.tar.gz",
            sha256="abc123",
            size_bytes=1000,
            library_key="sssp",
            dir_name="SSSP",
            variant="precision",
            version="1.3.0",
        )
        assert archive_install_relpath(info) == "SSSP/precision/1.3.0"

    def test_pseudodojo_path(self):
        from quantumvitas.pseudo.registry import ArchiveInfo, archive_install_relpath

        info = ArchiveInfo(
            filename="nc-sr_pbe_standard.tgz",
            sha256="def456",
            size_bytes=2000,
            library_key="pseudodojo",
            dir_name="PseudoDojo",
            variant="nc-sr_pbe_standard",
            version="0.4",
        )
        assert archive_install_relpath(info) == "PseudoDojo/nc-sr_pbe_standard/0.4"

    def test_gbrv_path(self):
        from quantumvitas.pseudo.registry import ArchiveInfo, archive_install_relpath

        info = ArchiveInfo(
            filename="GBRV_pbe_UPF_v1.5.tar.gz",
            sha256="ghi789",
            size_bytes=3000,
            library_key="gbrv",
            dir_name="GBRV",
            variant="pbe",
            version="1.5",
        )
        assert archive_install_relpath(info) == "GBRV/pbe/1.5"

    def test_sg15_path(self):
        from quantumvitas.pseudo.registry import ArchiveInfo, archive_install_relpath

        info = ArchiveInfo(
            filename="sg15_oncv.tar.gz",
            sha256="jkl012",
            size_bytes=4000,
            library_key="sg15",
            dir_name="SG15",
            variant="oncv",
            version="2020-02-06",
        )
        assert archive_install_relpath(info) == "SG15/oncv/2020-02-06"

    def test_pipeline_uses_archive_install_relpath(self):
        """Verify pipeline.py imports and uses archive_install_relpath."""
        import quantumvitas.pseudo.pipeline as pipeline_mod

        assert hasattr(pipeline_mod, "archive_install_relpath")


# ---------------------------------------------------------------------------
# Class C: Resolution chain tests — integration with installed libraries
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("QMATSUITE_SKIP_DOWNLOAD") == "1",
    reason="QMATSUITE_SKIP_DOWNLOAD=1",
)
class TestResolutionChain:
    """Integration tests using installed libraries."""

    def test_resolve_si_from_installed_library(self, tmp_path):
        """With SSSP installed, Si should resolve deterministically."""
        from quantumvitas.core.paths import home_pseudo_libraries_dir
        from quantumvitas.core.pseudo_config import (
            PseudoConfig,
            PseudoResolutionRequest,
            resolve_project_pseudos,
        )
        from quantumvitas.pseudo.pipeline import download_and_install

        # Ensure SSSP is installed
        install_result = download_and_install(
            library="sssp", variant="precision", version="1.3.0"
        )
        assert install_result["success"]

        project_dir = tmp_path / "test_si_project"
        project_dir.mkdir()

        config = PseudoConfig(
            store_dir=str(home_pseudo_libraries_dir()),
            seed_dir="",
        )
        request = PseudoResolutionRequest(
            project_root=project_dir,
            elements=["Si"],
            library="sssp",
            version="1.3.0",
            flavor="precision",
        )
        result = resolve_project_pseudos(config, request)
        assert "Si" in result.mapping, (
            f"Si not resolved. Errors: {result.errors}, Messages: {result.messages}"
        )
        assert result.mapping["Si"].lower().endswith(".upf")

    def test_resolve_c_not_cu(self, tmp_path):
        """C must resolve to Carbon pseudo — the core bug fix test."""
        from quantumvitas.core.paths import home_pseudo_libraries_dir
        from quantumvitas.core.pseudo_config import (
            PseudoConfig,
            PseudoResolutionRequest,
            resolve_project_pseudos,
        )
        from quantumvitas.pseudo.pipeline import download_and_install

        install_result = download_and_install(
            library="sssp", variant="precision", version="1.3.0"
        )
        assert install_result["success"]

        project_dir = tmp_path / "test_c_cu_project"
        project_dir.mkdir()

        config = PseudoConfig(
            store_dir=str(home_pseudo_libraries_dir()),
            seed_dir="",
        )
        request = PseudoResolutionRequest(
            project_root=project_dir,
            elements=["C", "Cu"],
            library="sssp",
            version="1.3.0",
            flavor="precision",
        )
        result = resolve_project_pseudos(config, request)
        assert result.success, f"Resolution failed: {result.errors}"
        assert "C" in result.mapping
        assert "Cu" in result.mapping
        # C and Cu must be different files
        assert result.mapping["C"] != result.mapping["Cu"], (
            f"C and Cu resolved to same file: {result.mapping['C']}"
        )
        # C file should not start with Cu
        assert not result.mapping["C"].startswith("Cu"), (
            f"C resolved to Copper pseudo: {result.mapping['C']}"
        )

    def test_resolve_5_elements_from_sg15(self, tmp_path):
        """Ag, Ba, Ga, Ti, Zn from SG15 library."""
        from quantumvitas.core.paths import home_pseudo_libraries_dir
        from quantumvitas.core.pseudo_config import (
            PseudoConfig,
            PseudoResolutionRequest,
            resolve_project_pseudos,
        )
        from quantumvitas.pseudo.pipeline import download_and_install

        install_result = download_and_install(library="sg15")
        assert install_result["success"]

        project_dir = tmp_path / "test_sg15_project"
        project_dir.mkdir()

        config = PseudoConfig(
            store_dir=str(home_pseudo_libraries_dir()),
            seed_dir="",
        )
        elements = ["Ag", "Ba", "Ga", "Ti", "Zn"]
        request = PseudoResolutionRequest(
            project_root=project_dir,
            elements=elements,
            library="sg15",
            version="2020-02-06",
            flavor="oncv",
        )
        result = resolve_project_pseudos(config, request)
        for elem in elements:
            assert elem in result.mapping, (
                f"{elem} not resolved. Errors: {result.errors}, Messages: {result.messages}"
            )

    def test_project_pseudo_dir_populated(self, tmp_path):
        """After resolution, files should exist in project/pseudo/."""
        from quantumvitas.core.paths import home_pseudo_libraries_dir
        from quantumvitas.core.pseudo_config import (
            PseudoConfig,
            PseudoResolutionRequest,
            resolve_project_pseudos,
        )
        from quantumvitas.pseudo.pipeline import download_and_install

        install_result = download_and_install(
            library="sssp", variant="precision", version="1.3.0"
        )
        assert install_result["success"]

        project_dir = tmp_path / "test_populate_project"
        project_dir.mkdir()

        config = PseudoConfig(
            store_dir=str(home_pseudo_libraries_dir()),
            seed_dir="",
        )
        request = PseudoResolutionRequest(
            project_root=project_dir,
            elements=["Si", "O"],
            library="sssp",
            version="1.3.0",
            flavor="precision",
        )
        result = resolve_project_pseudos(config, request)
        assert result.success

        pseudo_dir = project_dir / "pseudo"
        for elem, filename in result.mapping.items():
            assert (pseudo_dir / filename).exists(), (
                f"{filename} not found in project pseudo dir"
            )

    def test_resolution_prefers_project_local(self, tmp_path):
        """If pseudo already in project dir, don't re-copy from library."""
        from quantumvitas.core.paths import home_pseudo_libraries_dir
        from quantumvitas.core.pseudo_config import (
            PseudoConfig,
            PseudoResolutionRequest,
            resolve_project_pseudos,
        )
        from quantumvitas.pseudo.pipeline import download_and_install

        install_result = download_and_install(
            library="sssp", variant="precision", version="1.3.0"
        )
        assert install_result["success"]

        project_dir = tmp_path / "test_local_pref"
        project_dir.mkdir()

        config = PseudoConfig(
            store_dir=str(home_pseudo_libraries_dir()),
            seed_dir="",
        )
        request = PseudoResolutionRequest(
            project_root=project_dir,
            elements=["Si"],
            library="sssp",
            version="1.3.0",
            flavor="precision",
        )

        # First resolution — copies from library
        r1 = resolve_project_pseudos(config, request)
        assert r1.success
        first_msg = r1.messages[0] if r1.messages else ""

        # Second resolution — should find in project dir
        r2 = resolve_project_pseudos(config, request)
        assert r2.success
        assert any("Found in project" in m for m in r2.messages), (
            f"Expected 'Found in project' message, got: {r2.messages}"
        )


# ---------------------------------------------------------------------------
# Class D: Bandspw defaults
# ---------------------------------------------------------------------------


class TestBandspwDefaults:
    """Test that diago_full_acc is set in qe_bandspw defaults."""

    def test_diago_full_acc_in_bandspw_defaults(self):
        from quantumvitas.calculation.step_defaults import get_default_step_params

        params = get_default_step_params("qe_bandspw")
        electrons = params["parameters"].get("ELECTRONS", {})
        assert electrons.get("diago_full_acc") is True, (
            f"diago_full_acc not True in qe_bandspw ELECTRONS: {electrons}"
        )

    def test_diago_full_acc_not_in_scf(self):
        """diago_full_acc should NOT be in regular SCF defaults."""
        from quantumvitas.calculation.step_defaults import get_default_step_params

        params = get_default_step_params("qe_scf")
        electrons = params["parameters"].get("ELECTRONS", {})
        assert "diago_full_acc" not in electrons

    def test_diago_full_acc_not_in_bands_postprocess(self):
        """diago_full_acc should NOT be in bands.x post-processing defaults."""
        from quantumvitas.calculation.step_defaults import get_default_step_params

        params = get_default_step_params("qe_bands")
        electrons = params["parameters"].get("ELECTRONS", {})
        assert electrons.get("diago_full_acc") is not True
