"""Integration tests for the pseudo download pipeline.

Tests are grouped:
    - TestRegistry: unit-level, no network (manifest loading, resolve, defaults, errors)
    - TestSSPPrecisionDownload: SSSP precision full pipeline (real download)
    - TestRepresentativeLibraries: parametrized small libraries (real download)
    - TestResolutionIntegration: after download, resolution finds pseudos
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Registry unit tests — no network
# ---------------------------------------------------------------------------


class TestRegistry:
    """Test PseudoRegistry from vendored manifest (no network)."""

    def test_load_manifest(self):
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        assert len(registry._archives) > 0, "Manifest should have archives"
        assert len(registry._by_key) > 0, "Should have keyed entries"

    def test_list_libraries(self):
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        libs = registry.list_libraries()
        lib_keys = {lib["library_key"] for lib in libs}
        # Verify all 8 categories are present
        assert "sssp" in lib_keys
        assert "pseudodojo" in lib_keys
        assert "gbrv" in lib_keys
        assert "sg15" in lib_keys
        assert "hgh" in lib_keys
        assert "ps-library" in lib_keys
        assert "gipaw" in lib_keys
        assert "scan_tm" in lib_keys

    def test_resolve_sssp_precision(self):
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        info = registry.resolve("sssp", variant="precision", version="1.3.0")
        assert info.library_key == "sssp"
        assert info.variant == "precision"
        assert info.version == "1.3.0"
        assert info.filename.endswith(".tar.gz")
        assert info.sha256 == "d91db6b4b3788501d535a5b84ebabf3859ea3e3ac6ea154c4be3718da50f0c85"
        assert len(info.companions) == 1  # cutoffs JSON

    def test_resolve_sssp_efficiency(self):
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        info = registry.resolve("sssp", variant="efficiency", version="1.3.0")
        assert info.library_key == "sssp"
        assert info.variant == "efficiency"
        assert info.sha256 == "7a85b71fa3d68df1b5ed33c55c7057681fbf10377ae3b3eac9392924d9189f12"

    def test_resolve_default_variant(self):
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        info = registry.resolve("sssp")
        assert info.variant == "precision"  # default for sssp

    def test_resolve_latest_version(self):
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        info = registry.resolve("sssp", variant="precision", version="latest")
        assert info.version == "1.3.0"

    def test_resolve_pseudodojo(self):
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        info = registry.resolve("pseudodojo", variant="nc-sr_pbe_standard")
        assert info.library_key == "pseudodojo"
        assert info.dir_name == "PseudoDojo"
        assert "nc-sr" in info.variant

    def test_resolve_gbrv(self):
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        info = registry.resolve("gbrv", variant="pbe")
        assert info.library_key == "gbrv"
        assert info.version == "1.5"

    def test_resolve_sg15(self):
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        info = registry.resolve("sg15")
        assert info.library_key == "sg15"
        assert info.variant == "oncv"

    def test_resolve_hgh(self):
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        info = registry.resolve("hgh")
        assert info.library_key == "hgh"
        assert info.variant == "default"

    def test_resolve_gipaw(self):
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        info = registry.resolve("gipaw")
        assert info.library_key == "gipaw"

    def test_resolve_scan_tm(self):
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        info = registry.resolve("scan_tm")
        assert info.library_key == "scan_tm"

    def test_resolve_pslibrary(self):
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        info = registry.resolve("ps-library")
        assert info.library_key == "ps-library"

    def test_resolve_unknown_library_raises(self):
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        with pytest.raises(ValueError, match="Unknown library"):
            registry.resolve("nonexistent_library")

    def test_resolve_unknown_variant_raises(self):
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        with pytest.raises(ValueError, match="No archive found"):
            registry.resolve("sssp", variant="nonexistent_variant")

    def test_list_variants(self):
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        variants = registry.list_variants("sssp")
        assert "precision" in variants
        assert "efficiency" in variants

    def test_list_variants_pseudodojo(self):
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        variants = registry.list_variants("pseudodojo")
        assert len(variants) > 5  # Many PseudoDojo variants

    def test_get_default_variant(self):
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        assert registry.get_default_variant("sssp") == "precision"
        assert registry.get_default_variant("gbrv") == "pbe"
        assert registry.get_default_variant("sg15") == "oncv"

    def test_archive_info_companions(self):
        """SSSP archives should have companion cutoffs JSON."""
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        info = registry.resolve("sssp", variant="precision")
        assert len(info.companions) >= 1
        assert any(".json" in c for c in info.companions)

    def test_archive_info_no_companions_for_non_sssp(self):
        """Non-SSSP archives should have no companions."""
        from quantumvitas.pseudo.registry import PseudoRegistry

        registry = PseudoRegistry()
        info = registry.resolve("sg15")
        assert len(info.companions) == 0


# ---------------------------------------------------------------------------
# Pipeline tests — real network downloads
# ---------------------------------------------------------------------------

# Use a shared tmp dir for downloads so tests don't re-download
_PIPELINE_TEST_DIR = None


def _get_test_dir() -> Path:
    global _PIPELINE_TEST_DIR
    if _PIPELINE_TEST_DIR is None:
        from quantumvitas.core.paths import get_qmatsuite_tmp_root

        _PIPELINE_TEST_DIR = get_qmatsuite_tmp_root() / "test_pseudo_pipeline"
        _PIPELINE_TEST_DIR.mkdir(parents=True, exist_ok=True)
    return _PIPELINE_TEST_DIR


@pytest.mark.skipif(
    os.environ.get("QMATSUITE_SKIP_DOWNLOAD") == "1",
    reason="QMATSUITE_SKIP_DOWNLOAD=1",
)
class TestSSPPrecisionDownload:
    """Full pipeline test for SSSP precision (mandatory, ~60MB)."""

    def test_download_sssp_precision(self):
        from quantumvitas.pseudo.pipeline import download_and_install

        result = download_and_install(
            library="sssp", variant="precision", version="1.3.0"
        )
        assert result["success"], f"Pipeline failed: {result.get('errors')}"
        assert result["upf_count"] > 50, f"Expected >50 UPFs, got {result['upf_count']}"
        assert result["library_key"] == "sssp"
        assert result["variant"] == "precision"
        assert result["version"] == "1.3.0"

    def test_head_json_exists(self):
        """After download, head.json should exist at library root."""
        from quantumvitas.core.paths import home_pseudo_libraries_dir

        lib_root = home_pseudo_libraries_dir() / "SSSP"
        head = lib_root / "head.json"
        assert head.exists(), f"head.json not found at {head}"
        data = json.loads(head.read_text())
        assert data["variant"] == "precision"
        assert data["version"] == "1.3.0"

    def test_upfs_in_install_dir(self):
        """UPF files should be in the variant/version subdirectory."""
        from quantumvitas.core.paths import home_pseudo_libraries_dir

        upf_dir = home_pseudo_libraries_dir() / "SSSP" / "precision" / "1.3.0"
        assert upf_dir.is_dir()
        upfs = [f for f in upf_dir.iterdir() if f.suffix.lower() == ".upf"]
        assert len(upfs) > 50

    def test_idempotent_rerun(self):
        """Second run should detect already installed and skip."""
        from quantumvitas.pseudo.pipeline import download_and_install

        result = download_and_install(
            library="sssp", variant="precision", version="1.3.0"
        )
        assert result["success"]
        assert any("Already installed" in m for m in result["messages"])

    def test_no_orphan_temp_dirs(self):
        """No pseudo_dl_ or pseudo_ext_ temp dirs should remain."""
        from quantumvitas.core.paths import tmp_downloads_dir

        dl_dir = tmp_downloads_dir()
        orphans = [
            d
            for d in dl_dir.iterdir()
            if d.is_dir() and (d.name.startswith("pseudo_dl_") or d.name.startswith("pseudo_ext_"))
        ]
        assert len(orphans) == 0, f"Orphan temp dirs: {[d.name for d in orphans]}"


@pytest.mark.skipif(
    os.environ.get("QMATSUITE_SKIP_DOWNLOAD") == "1",
    reason="QMATSUITE_SKIP_DOWNLOAD=1",
)
class TestRepresentativeLibraries:
    """Test downloading representative small libraries."""

    @pytest.mark.parametrize(
        "library,variant,version,min_upfs",
        [
            ("pseudodojo", "nc-sr_pbe_standard", "0.4", 10),
            ("gbrv", "pbe", "1.5", 10),
            ("sg15", "oncv", "latest", 10),
            ("scan_tm", "default", "latest", 5),
        ],
        ids=["pseudodojo-5MB", "gbrv-13MB", "sg15-6MB", "scan_tm-1MB"],
    )
    def test_download_library(self, library, variant, version, min_upfs):
        from quantumvitas.pseudo.pipeline import download_and_install

        result = download_and_install(
            library=library, variant=variant, version=version
        )
        assert result["success"], f"Pipeline failed for {library}: {result.get('errors')}"
        assert result["upf_count"] >= min_upfs, (
            f"Expected >={min_upfs} UPFs for {library}, got {result['upf_count']}"
        )

    def test_download_gipaw(self):
        """GIPAW is a zip, not tar.gz — tests zip extraction path."""
        from quantumvitas.pseudo.pipeline import download_and_install

        result = download_and_install(library="gipaw")
        assert result["success"], f"GIPAW failed: {result.get('errors')}"
        assert result["upf_count"] >= 5

    @pytest.mark.skipif(
        os.environ.get("QMATSUITE_SKIP_LARGE_DOWNLOAD") != "0",
        reason="HGH is 30MB, set QMATSUITE_SKIP_LARGE_DOWNLOAD=0 to run",
    )
    def test_download_hgh(self):
        from quantumvitas.pseudo.pipeline import download_and_install

        result = download_and_install(library="hgh")
        assert result["success"], f"HGH failed: {result.get('errors')}"
        assert result["upf_count"] >= 10


@pytest.mark.skipif(
    os.environ.get("QMATSUITE_SKIP_DOWNLOAD") == "1",
    reason="QMATSUITE_SKIP_DOWNLOAD=1",
)
class TestResolutionIntegration:
    """After download, resolution should find installed pseudos."""

    def test_resolution_finds_sssp(self, tmp_path):
        """resolve_project_pseudos should find SSSP UPFs via head.json."""
        from quantumvitas.core.pseudo_config import (
            PseudoConfig,
            PseudoResolutionRequest,
            resolve_project_pseudos,
        )
        from quantumvitas.core.paths import home_pseudo_libraries_dir

        # Make sure SSSP is installed
        from quantumvitas.pseudo.pipeline import download_and_install

        install_result = download_and_install(
            library="sssp", variant="precision", version="1.3.0"
        )
        assert install_result["success"]

        # Now resolve Si from a fresh project dir
        project_dir = tmp_path / "test_project"
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
            f"Si not found in resolution mapping. "
            f"Errors: {result.errors}, Messages: {result.messages}"
        )
        assert result.mapping["Si"].endswith(".UPF") or result.mapping["Si"].endswith(".upf")
