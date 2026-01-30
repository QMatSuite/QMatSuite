"""Unit tests for VASP step type registry and GEN→SPEC mapping."""

import pytest
from quantumvitas.workflow.registry import get_registry
from quantumvitas.workflow.generalized_steps import (
    materialize_step,
    materialize_workflow,
    materialize_public_step_key,
)


class TestVASPStepTypeRegistry:
    """Test VASP step types are registered correctly."""
    
    def test_vasp_step_types_registered(self):
        """Test that VASP step types exist in registry."""
        registry = get_registry()
        
        assert registry.has("vasp_scf")
        assert registry.has("vasp_nscf")
        assert registry.has("vasp_bands")
        assert registry.has("vasp_relax")
    
    def test_vasp_scf_spec(self):
        """Test vasp_scf StepTypeSpec details."""
        registry = get_registry()
        spec = registry.get("vasp_scf")
        
        assert spec is not None
        assert spec.step_type_gen == "scf"
        assert spec.step_type_spec == "vasp_scf"
        assert spec.step_type_gen == "scf"
        assert spec.engine == "vasp"
        assert spec.executable == "vasp_std"
        assert spec.requires_structure is True
        assert spec.requires_charge_density is False
        assert spec.produces_charge_density is True
    
    def test_vasp_nscf_spec(self):
        """Test vasp_nscf StepTypeSpec details."""
        registry = get_registry()
        spec = registry.get("vasp_nscf")
        
        assert spec is not None
        assert spec.engine == "vasp"
        assert spec.requires_charge_density is True
        assert spec.produces_charge_density is False
    
    def test_vasp_bands_spec(self):
        """Test vasp_bands StepTypeSpec details."""
        registry = get_registry()
        spec = registry.get("vasp_bands")
        
        assert spec is not None
        assert spec.engine == "vasp"
        assert spec.requires_charge_density is True
    
    def test_vasp_relax_spec(self):
        """Test vasp_relax StepTypeSpec details."""
        registry = get_registry()
        spec = registry.get("vasp_relax")
        
        assert spec is not None
        assert spec.engine == "vasp"
        assert spec.is_structure_transform is True


class TestVASPGenToSpecMapping:
    """Test GEN→SPEC mapping for VASP."""
    
    def test_vasp_scf_mapping(self):
        """Test SCF maps to vasp_scf."""
        result = materialize_step("SCF", "vasp")
        assert result == "vasp_scf"
    
    def test_vasp_nscf_mapping(self):
        """Test NSCF maps to vasp_nscf."""
        result = materialize_step("NSCF", "vasp")
        assert result == "vasp_nscf"
    
    def test_vasp_bands_mapping(self):
        """Test BANDS maps to vasp_bands."""
        result = materialize_step("BANDS", "vasp")
        assert result == "vasp_bands"
    
    def test_vasp_relax_mapping(self):
        """Test RELAX maps to vasp_relax."""
        result = materialize_step("RELAX", "vasp")
        assert result == "vasp_relax"
    
    def test_vasp_bands_post_zero_mapping(self):
        """Test BANDS_POST maps to None (0-mapping)."""
        result = materialize_step("BANDS_POST", "vasp")
        assert result is None
    
    def test_vasp_dos_zero_mapping(self):
        """Test DOS maps to None (0-mapping)."""
        result = materialize_step("DOS", "vasp")
        assert result is None
    
    def test_vasp_workflow_materialize_omits_zero_mappings(self):
        """Test that workflow materialization silently omits 0-mapped steps."""
        # DOS workflow: scf → nscf → dospp
        result = materialize_workflow(["scf", "nscf", "dospp"], "vasp")
        assert result == ["vasp_scf", "vasp_nscf"]  # dospp omitted
        
        # Bands workflow: scf → bands → bandspp
        result = materialize_workflow(["scf", "bands", "bandspp"], "vasp")
        assert result == ["vasp_scf", "vasp_bands"]  # bandspp omitted
    
    def test_vasp_public_step_key_mapping(self):
        """Test materialize_public_step_key for VASP."""
        assert materialize_public_step_key("scf", "vasp") == "vasp_scf"
        assert materialize_public_step_key("nscf", "vasp") == "vasp_nscf"
        assert materialize_public_step_key("bands", "vasp") == "vasp_bands"
        assert materialize_public_step_key("relax", "vasp") == "vasp_relax"
        assert materialize_public_step_key("dospp", "vasp") is None  # 0-mapping


class TestVASPResolver:
    """Test VASP binary and POTCAR resolution - MOCK TESTS (CI 必跑)."""
    
    def test_resolve_vasp_bin_finds_binary_from_env(self, monkeypatch, tmp_path):
        """Test resolver finds VASP via environment variable."""
        # Create fake binary
        fake_bin = tmp_path / "fake_vasp_std"
        fake_bin.write_text("#!/bin/bash\necho fake")
        fake_bin.chmod(0o755)
        
        monkeypatch.setenv("QMATS_VASP_STD_BIN", str(fake_bin))
        
        from quantumvitas.core.engines.vasp_resolver import resolve_vasp_bin
        result = resolve_vasp_bin("std")
        assert result == fake_bin
    
    def test_resolve_vasp_bin_finds_binary_from_repo_root(self, monkeypatch, tmp_path):
        """Test resolver finds VASP in .qmatsuite/ directory."""
        # Create fake repo structure
        vasp_dir = tmp_path / ".qmatsuite" / "engines" / "vasp" / "vasp.6.5.0" / "bin"
        vasp_dir.mkdir(parents=True)
        fake_bin = vasp_dir / "vasp_std"
        fake_bin.write_text("#!/bin/bash\necho fake")
        fake_bin.chmod(0o755)
        
        # Clear env var and mock repo root
        monkeypatch.delenv("QMATS_VASP_STD_BIN", raising=False)
        
        import quantumvitas.core.engines.vasp_resolver as resolver_mod
        monkeypatch.setattr(resolver_mod, '_get_repo_root', lambda: tmp_path)
        
        from quantumvitas.core.engines.vasp_resolver import resolve_vasp_bin
        result = resolve_vasp_bin("std")
        assert result == fake_bin
    
    def test_resolve_vasp_bin_raises_when_not_found(self, monkeypatch, tmp_path):
        """Test resolver raises RuntimeError when VASP not found."""
        monkeypatch.delenv("QMATS_VASP_STD_BIN", raising=False)
        
        import quantumvitas.core.engines.vasp_resolver as resolver_mod
        monkeypatch.setattr(resolver_mod, '_get_repo_root', lambda: tmp_path)
        
        from quantumvitas.core.engines.vasp_resolver import resolve_vasp_bin
        with pytest.raises(RuntimeError, match="VASP.*not found"):
            resolve_vasp_bin("std")
    
    def test_get_potcar_dir_finds_directory(self, monkeypatch, tmp_path):
        """Test get_potcar_dir finds POTCAR library."""
        # Create fake POTCAR structure
        potcar_dir = tmp_path / ".qmatsuite" / "engines" / "vasp" / "potpaw_PBE.64"
        potcar_dir.mkdir(parents=True)
        si_dir = potcar_dir / "Si"
        si_dir.mkdir()
        (si_dir / "POTCAR").write_text("FAKE POTCAR")
        
        import quantumvitas.core.engines.vasp_resolver as resolver_mod
        monkeypatch.setattr(resolver_mod, '_get_repo_root', lambda: tmp_path)
        
        from quantumvitas.core.engines.vasp_resolver import get_potcar_dir
        result = get_potcar_dir("PBE")
        assert result == potcar_dir
        assert (result / "Si" / "POTCAR").exists()
    
    def test_get_potcar_dir_raises_when_not_found(self, monkeypatch, tmp_path):
        """Test get_potcar_dir raises RuntimeError when not found."""
        import quantumvitas.core.engines.vasp_resolver as resolver_mod
        monkeypatch.setattr(resolver_mod, '_get_repo_root', lambda: tmp_path)
        
        from quantumvitas.core.engines.vasp_resolver import get_potcar_dir
        with pytest.raises(RuntimeError, match="POTCAR directory not found"):
            get_potcar_dir("PBE")

