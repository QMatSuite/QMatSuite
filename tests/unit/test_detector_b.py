"""
Unit tests for Detector B and Compiler: Preset detection and compilation.

This module tests the preset system per Constitution Chapter 10:
- Detector B: sole legitimate source for preset/option state (10.4.1)
- Compiler: canonical encoding, explicit all key parameters (10.3.4)
- Equivalence: detect(compile(options)) == options (10.6.2)
- No "Unknown" state - either single value or Custom (10.5.1)

Test categories:
1. Single-step detection for each dimension
2. Implicit defaults (missing parameters)
3. Multi-step aggregation (homogeneous and heterogeneous)
4. Real QE inputs from tests/data
5. Compiler canonical encoding
6. Compiler-Detector equivalence
"""

import pytest
from pathlib import Path

from quantumvitas.presets import (
    SpinOption,
    SOCOption,
    MaterialOption,
    CUSTOM,
    detect_spin,
    detect_soc,
    detect_material,
    detect_all_presets,
    compile_spin,
    compile_soc,
    compile_material,
    compile_presets,
    PresetCompilationError,
)
from quantumvitas.presets.detector import detect_dimension_from_steps


class TestSpinDetection:
    """Tests for spin dimension detection."""
    
    def test_explicit_nonspin(self):
        """nspin=1 should detect as NONSPIN."""
        params = {"SYSTEM": {"nspin": 1}}
        assert detect_spin(params) == SpinOption.NONSPIN
    
    def test_explicit_collinear(self):
        """nspin=2 should detect as COLLINEAR."""
        params = {"SYSTEM": {"nspin": 2}}
        assert detect_spin(params) == SpinOption.COLLINEAR
    
    def test_explicit_noncollinear_via_noncolin(self):
        """noncolin=.true. should detect as NONCOLLINEAR."""
        params = {"SYSTEM": {"noncolin": ".true."}}
        assert detect_spin(params) == SpinOption.NONCOLLINEAR
    
    def test_explicit_noncollinear_via_noncolin_bool(self):
        """noncolin=True should detect as NONCOLLINEAR."""
        params = {"SYSTEM": {"noncolin": True}}
        assert detect_spin(params) == SpinOption.NONCOLLINEAR
    
    def test_explicit_nspin_4_implies_noncollinear(self):
        """nspin=4 should detect as NONCOLLINEAR (edge case)."""
        params = {"SYSTEM": {"nspin": 4}}
        assert detect_spin(params) == SpinOption.NONCOLLINEAR
    
    def test_implicit_default_nonspin(self):
        """Missing nspin should default to NONSPIN per QE defaults."""
        params = {"SYSTEM": {"ecutwfc": 50}}
        assert detect_spin(params) == SpinOption.NONSPIN
    
    def test_empty_params_defaults_nonspin(self):
        """Empty params should default to NONSPIN."""
        assert detect_spin({}) == SpinOption.NONSPIN
    
    def test_noncolin_false_is_not_noncollinear(self):
        """noncolin=.false. should not trigger NONCOLLINEAR."""
        params = {"SYSTEM": {"noncolin": ".false.", "nspin": 1}}
        assert detect_spin(params) == SpinOption.NONSPIN
    
    def test_noncolin_takes_precedence_over_nspin(self):
        """noncolin=.true. takes precedence over nspin=2."""
        params = {"SYSTEM": {"noncolin": ".true.", "nspin": 2}}
        assert detect_spin(params) == SpinOption.NONCOLLINEAR
    
    def test_case_insensitive_section(self):
        """Section names should be case-insensitive."""
        params = {"system": {"nspin": 2}}
        assert detect_spin(params) == SpinOption.COLLINEAR


class TestSOCDetection:
    """Tests for spin-orbit coupling detection."""
    
    def test_explicit_with_soc(self):
        """lspinorb=.true. should detect as WITH_SOC."""
        params = {"SYSTEM": {"lspinorb": ".true."}}
        assert detect_soc(params) == SOCOption.WITH_SOC
    
    def test_explicit_with_soc_bool(self):
        """lspinorb=True should detect as WITH_SOC."""
        params = {"SYSTEM": {"lspinorb": True}}
        assert detect_soc(params) == SOCOption.WITH_SOC
    
    def test_explicit_no_soc(self):
        """lspinorb=.false. should detect as NO_SOC."""
        params = {"SYSTEM": {"lspinorb": ".false."}}
        assert detect_soc(params) == SOCOption.NO_SOC
    
    def test_implicit_default_no_soc(self):
        """Missing lspinorb should default to NO_SOC per QE defaults."""
        params = {"SYSTEM": {"ecutwfc": 50}}
        assert detect_soc(params) == SOCOption.NO_SOC
    
    def test_empty_params_defaults_no_soc(self):
        """Empty params should default to NO_SOC."""
        assert detect_soc({}) == SOCOption.NO_SOC


class TestMaterialDetection:
    """Tests for material type detection."""
    
    def test_smearing_is_metal(self):
        """occupations='smearing' should detect as METAL."""
        params = {"SYSTEM": {"occupations": "'smearing'"}}
        assert detect_material(params) == MaterialOption.METAL
    
    def test_smearing_unquoted_is_metal(self):
        """occupations=smearing (unquoted) should detect as METAL."""
        params = {"SYSTEM": {"occupations": "smearing"}}
        assert detect_material(params) == MaterialOption.METAL
    
    def test_fixed_is_insulator(self):
        """occupations='fixed' should detect as INSULATOR."""
        params = {"SYSTEM": {"occupations": "'fixed'"}}
        assert detect_material(params) == MaterialOption.INSULATOR
    
    def test_tetrahedra_is_insulator(self):
        """occupations='tetrahedra' should detect as INSULATOR."""
        params = {"SYSTEM": {"occupations": "'tetrahedra'"}}
        assert detect_material(params) == MaterialOption.INSULATOR
    
    def test_tetrahedra_opt_is_insulator(self):
        """occupations='tetrahedra_opt' should detect as INSULATOR."""
        params = {"SYSTEM": {"occupations": "'tetrahedra_opt'"}}
        assert detect_material(params) == MaterialOption.INSULATOR
    
    def test_implicit_default_insulator(self):
        """Missing occupations should default to INSULATOR."""
        params = {"SYSTEM": {"ecutwfc": 50}}
        assert detect_material(params) == MaterialOption.INSULATOR
    
    def test_empty_params_defaults_insulator(self):
        """Empty params should default to INSULATOR."""
        assert detect_material({}) == MaterialOption.INSULATOR
    
    def test_from_input_is_insulator(self):
        """occupations='from_input' should detect as INSULATOR."""
        params = {"SYSTEM": {"occupations": "'from_input'"}}
        assert detect_material(params) == MaterialOption.INSULATOR


class TestMultiStepAggregation:
    """Tests for multi-step preset aggregation per Constitution 10.5.1."""
    
    def test_single_step_returns_value(self):
        """Single step should return its value (not Custom)."""
        steps = [{"SYSTEM": {"nspin": 2}}]
        result = detect_dimension_from_steps(steps, "spin")
        assert result == SpinOption.COLLINEAR
    
    def test_homogeneous_steps_return_value(self):
        """Multiple steps with same value should return that value."""
        steps = [
            {"SYSTEM": {"nspin": 2}},
            {"SYSTEM": {"nspin": 2}},
            {"SYSTEM": {"nspin": 2}},
        ]
        result = detect_dimension_from_steps(steps, "spin")
        assert result == SpinOption.COLLINEAR
    
    def test_heterogeneous_steps_return_custom(self):
        """Multiple steps with different values should return CUSTOM."""
        steps = [
            {"SYSTEM": {"nspin": 1}},
            {"SYSTEM": {"nspin": 2}},
        ]
        result = detect_dimension_from_steps(steps, "spin")
        assert result is CUSTOM
    
    def test_empty_steps_returns_default(self):
        """Empty step list should return the dimension's default."""
        result = detect_dimension_from_steps([], "spin")
        assert result == SpinOption.NONSPIN
    
    def test_implicit_and_explicit_same_value_homogeneous(self):
        """Implicit default and explicit same value should be homogeneous."""
        steps = [
            {},  # Implicit nspin=1 (NONSPIN)
            {"SYSTEM": {"nspin": 1}},  # Explicit nspin=1 (NONSPIN)
        ]
        result = detect_dimension_from_steps(steps, "spin")
        assert result == SpinOption.NONSPIN


class TestDetectAllPresets:
    """Tests for detect_all_presets function."""
    
    def test_returns_all_v0_dimensions(self):
        """detect_all_presets should return all v0 dimensions."""
        steps = [{"SYSTEM": {"nspin": 2, "occupations": "'smearing'"}}]
        result = detect_all_presets(steps)
        
        assert "spin" in result
        assert "soc" in result
        assert "material" in result
    
    def test_empty_steps_returns_defaults(self):
        """Empty steps should return defaults for all dimensions."""
        result = detect_all_presets([])
        
        assert result["spin"] == SpinOption.NONSPIN
        assert result["soc"] == SOCOption.NO_SOC
        assert result["material"] == MaterialOption.INSULATOR
    
    def test_mixed_presets(self):
        """Should correctly detect mixed preset values."""
        steps = [{"SYSTEM": {
            "nspin": 2,
            "lspinorb": ".false.",
            "occupations": "'smearing'",
        }}]
        result = detect_all_presets(steps)
        
        assert result["spin"] == SpinOption.COLLINEAR
        assert result["soc"] == SOCOption.NO_SOC
        assert result["material"] == MaterialOption.METAL


class TestRealQEInputs:
    """Tests using real QE inputs from tests/data directory."""
    
    @pytest.fixture
    def test_data_dir(self) -> Path:
        """Get the tests/data directory path."""
        return Path(__file__).parent.parent / "data"
    
    def _params_from_qe_file(self, path: Path) -> dict:
        """Parse QE input file and return parameters dict."""
        from quantumvitas.io import QEInputParser
        qe_input = QEInputParser.parse_file(path)
        
        params = {}
        for namelist in qe_input.namelists:
            section_name = namelist.name.upper()
            if not section_name.startswith("&"):
                section_name = f"&{section_name}"
            # Remove & prefix for our params dict
            section_key = section_name.lstrip("&")
            params[section_key] = dict(namelist.parameters)
        
        return params
    
    def test_si_scf_is_nonspin_insulator(self, test_data_dir: Path):
        """tests/data/0_Si_scf/si.scf.in should be nonspin insulator."""
        input_file = test_data_dir / "0_Si_scf" / "si.scf.in"
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")
        
        params = self._params_from_qe_file(input_file)
        
        assert detect_spin(params) == SpinOption.NONSPIN
        assert detect_soc(params) == SOCOption.NO_SOC
        # Si SCF has no occupations -> implicit insulator
        assert detect_material(params) == MaterialOption.INSULATOR
    
    def test_fe_collinear_is_collinear_metal(self, test_data_dir: Path):
        """tests/data/8_Fe_DOS/1_collinear/fe.2_scf.in should be collinear metal."""
        input_file = test_data_dir / "8_Fe_DOS" / "1_collinear" / "fe.2_scf.in"
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")
        
        params = self._params_from_qe_file(input_file)
        
        # nspin=2 -> COLLINEAR
        assert detect_spin(params) == SpinOption.COLLINEAR
        # no lspinorb -> NO_SOC
        assert detect_soc(params) == SOCOption.NO_SOC
        # occupations='smearing' -> METAL
        assert detect_material(params) == MaterialOption.METAL
    
    def test_fe_noncollinear_is_noncollinear_metal(self, test_data_dir: Path):
        """tests/data/8_Fe_DOS/2_noncolinear/fe.scf_noncollin.in should be noncollinear metal."""
        input_file = test_data_dir / "8_Fe_DOS" / "2_noncolinear" / "fe.scf_noncollin.in"
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")
        
        params = self._params_from_qe_file(input_file)
        
        # noncolin=.true. -> NONCOLLINEAR
        assert detect_spin(params) == SpinOption.NONCOLLINEAR
        # no lspinorb -> NO_SOC
        assert detect_soc(params) == SOCOption.NO_SOC
        # occupations='smearing' -> METAL
        assert detect_material(params) == MaterialOption.METAL
    
    def test_al_dos_is_nonspin_metal(self, test_data_dir: Path):
        """tests/data/6_Al_DOS/al.2_scf.in should be nonspin metal."""
        input_file = test_data_dir / "6_Al_DOS" / "al.2_scf.in"
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")
        
        params = self._params_from_qe_file(input_file)
        
        # no nspin -> NONSPIN (implicit)
        assert detect_spin(params) == SpinOption.NONSPIN
        # no lspinorb -> NO_SOC
        assert detect_soc(params) == SOCOption.NO_SOC
        # occupations='smearing' -> METAL
        assert detect_material(params) == MaterialOption.METAL
    
    def test_si_dos_workflow_is_nonspin_insulator(self, test_data_dir: Path):
        """tests/data/4_Si_DOS workflow should aggregate to nonspin insulator."""
        si_dos_dir = test_data_dir / "4_Si_DOS"
        if not si_dos_dir.exists():
            pytest.skip(f"Test directory not found: {si_dos_dir}")
        
        # Collect all .in files (excluding dos.x input)
        input_files = list(si_dos_dir.glob("si.*.in"))
        pw_inputs = [f for f in input_files if "dos" not in f.stem.lower() or "scf" in f.stem.lower()]
        
        if not pw_inputs:
            pytest.skip(f"No PW input files found in {si_dos_dir}")
        
        steps = []
        for input_file in pw_inputs:
            params = self._params_from_qe_file(input_file)
            steps.append(params)
        
        result = detect_all_presets(steps)
        
        # All Si DOS steps should be nonspin insulator
        assert result["spin"] == SpinOption.NONSPIN
        assert result["soc"] == SOCOption.NO_SOC
        # Si is insulator (no smearing or tetrahedra)
        assert result["material"] == MaterialOption.INSULATOR


class TestCustomSingleton:
    """Tests for CUSTOM singleton behavior."""
    
    def test_custom_equality(self):
        """CUSTOM should equal itself."""
        assert CUSTOM == CUSTOM
    
    def test_custom_repr(self):
        """CUSTOM repr should be 'Custom'."""
        assert repr(CUSTOM) == "Custom"
    
    def test_custom_str(self):
        """CUSTOM str should be 'Custom'."""
        assert str(CUSTOM) == "Custom"
    
    def test_custom_is_singleton(self):
        """CUSTOM should be a singleton."""
        from quantumvitas.presets.dimensions import _CustomType
        another = _CustomType()
        assert another is CUSTOM


class TestCompilerDetectorEquivalence:
    """
    Tests for Compiler-Detector mathematical equivalence.
    
    Per Constitution 10.6.2:
    detect(compile_one(step_type, options)) == options in that dimension
    
    This is the critical invariant that ensures the system is self-consistent.
    """
    
    def test_spin_roundtrip_nonspin(self):
        """compile(nonspin) -> detect should equal nonspin."""
        from quantumvitas.presets import compile_spin
        
        compiled = compile_spin(SpinOption.NONSPIN)
        params = {"SYSTEM": compiled}
        detected = detect_spin(params)
        
        assert detected == SpinOption.NONSPIN
    
    def test_spin_roundtrip_collinear(self):
        """compile(collinear) -> detect should equal collinear."""
        from quantumvitas.presets import compile_spin
        
        compiled = compile_spin(SpinOption.COLLINEAR)
        params = {"SYSTEM": compiled}
        detected = detect_spin(params)
        
        assert detected == SpinOption.COLLINEAR
    
    def test_spin_roundtrip_noncollinear(self):
        """compile(noncollinear) -> detect should equal noncollinear."""
        from quantumvitas.presets import compile_spin
        
        compiled = compile_spin(SpinOption.NONCOLLINEAR)
        params = {"SYSTEM": compiled}
        detected = detect_spin(params)
        
        assert detected == SpinOption.NONCOLLINEAR
    
    def test_soc_roundtrip_no_soc(self):
        """compile(no_soc) -> detect should equal no_soc."""
        from quantumvitas.presets import compile_soc
        
        compiled = compile_soc(SOCOption.NO_SOC)
        params = {"SYSTEM": compiled}
        detected = detect_soc(params)
        
        assert detected == SOCOption.NO_SOC
    
    def test_soc_roundtrip_with_soc(self):
        """compile(with_soc) -> detect should equal with_soc."""
        from quantumvitas.presets import compile_soc
        
        # with_soc requires noncollinear for physics validity
        compiled = compile_soc(SOCOption.WITH_SOC, spin=SpinOption.NONCOLLINEAR)
        params = {"SYSTEM": compiled}
        detected = detect_soc(params)
        
        assert detected == SOCOption.WITH_SOC
    
    def test_material_roundtrip_insulator(self):
        """compile(insulator) -> detect should equal insulator."""
        from quantumvitas.presets import compile_material
        
        compiled = compile_material(MaterialOption.INSULATOR)
        params = {"SYSTEM": compiled}
        detected = detect_material(params)
        
        assert detected == MaterialOption.INSULATOR
    
    def test_material_roundtrip_metal(self):
        """compile(metal) -> detect should equal metal."""
        from quantumvitas.presets import compile_material
        
        compiled = compile_material(MaterialOption.METAL)
        params = {"SYSTEM": compiled}
        detected = detect_material(params)
        
        assert detected == MaterialOption.METAL
    
    def test_full_preset_roundtrip_defaults(self):
        """compile_presets with defaults should roundtrip through detect_all_presets."""
        from quantumvitas.presets import compile_presets
        
        options = {
            "spin": SpinOption.NONSPIN,
            "soc": SOCOption.NO_SOC,
            "material": MaterialOption.INSULATOR,
        }
        compiled = compile_presets(options)
        detected = detect_all_presets([compiled])
        
        assert detected["spin"] == SpinOption.NONSPIN
        assert detected["soc"] == SOCOption.NO_SOC
        assert detected["material"] == MaterialOption.INSULATOR
    
    def test_full_preset_roundtrip_collinear_metal(self):
        """compile_presets for collinear metal should roundtrip correctly."""
        from quantumvitas.presets import compile_presets
        
        options = {
            "spin": SpinOption.COLLINEAR,
            "soc": SOCOption.NO_SOC,
            "material": MaterialOption.METAL,
        }
        compiled = compile_presets(options)
        detected = detect_all_presets([compiled])
        
        assert detected["spin"] == SpinOption.COLLINEAR
        assert detected["soc"] == SOCOption.NO_SOC
        assert detected["material"] == MaterialOption.METAL
    
    def test_full_preset_roundtrip_noncollinear_soc(self):
        """compile_presets for noncollinear with SOC should roundtrip correctly."""
        from quantumvitas.presets import compile_presets
        
        options = {
            "spin": SpinOption.NONCOLLINEAR,
            "soc": SOCOption.WITH_SOC,
            "material": MaterialOption.METAL,
        }
        compiled = compile_presets(options)
        detected = detect_all_presets([compiled])
        
        assert detected["spin"] == SpinOption.NONCOLLINEAR
        assert detected["soc"] == SOCOption.WITH_SOC
        assert detected["material"] == MaterialOption.METAL


class TestCompilerCanonicalEncoding:
    """
    Tests for Compiler canonical encoding per Constitution 10.3.4.
    
    Compiler must explicitly write all key parameters - no reliance on defaults.
    """
    
    def test_compile_spin_nonspin_explicit_nspin(self):
        """compile_spin(NONSPIN) must explicitly write nspin=1."""
        result = compile_spin(SpinOption.NONSPIN)
        
        assert "nspin" in result
        assert result["nspin"] == 1
    
    def test_compile_spin_collinear_explicit_nspin(self):
        """compile_spin(COLLINEAR) must explicitly write nspin=2."""
        result = compile_spin(SpinOption.COLLINEAR)
        
        assert "nspin" in result
        assert result["nspin"] == 2
    
    def test_compile_spin_noncollinear_explicit_noncolin(self):
        """compile_spin(NONCOLLINEAR) must explicitly write noncolin=.true."""
        result = compile_spin(SpinOption.NONCOLLINEAR)
        
        assert "noncolin" in result
        assert result["noncolin"] == ".true."
        # Should NOT write nspin per QE docs
        assert "nspin" not in result
    
    def test_compile_soc_no_soc_explicit_lspinorb(self):
        """compile_soc(NO_SOC) must explicitly write lspinorb=.false."""
        result = compile_soc(SOCOption.NO_SOC)
        
        assert "lspinorb" in result
        assert result["lspinorb"] == ".false."
    
    def test_compile_soc_with_soc_explicit_lspinorb(self):
        """compile_soc(WITH_SOC) must explicitly write lspinorb=.true."""
        result = compile_soc(SOCOption.WITH_SOC, spin=SpinOption.NONCOLLINEAR)
        
        assert "lspinorb" in result
        assert result["lspinorb"] == ".true."
    
    def test_compile_material_insulator_explicit_occupations(self):
        """compile_material(INSULATOR) must explicitly write occupations='fixed'."""
        result = compile_material(MaterialOption.INSULATOR)
        
        assert "occupations" in result
        assert result["occupations"] == "'fixed'"
    
    def test_compile_material_metal_explicit_smearing_params(self):
        """compile_material(METAL) must explicitly write all smearing params."""
        result = compile_material(MaterialOption.METAL)
        
        assert "occupations" in result
        assert result["occupations"] == "'smearing'"
        assert "smearing" in result
        assert "degauss" in result
    
    def test_compile_presets_structure(self):
        """compile_presets should return section -> params structure."""
        options = {
            "spin": SpinOption.NONSPIN,
            "soc": SOCOption.NO_SOC,
            "material": MaterialOption.INSULATOR,
        }
        result = compile_presets(options)
        
        assert "SYSTEM" in result
        assert isinstance(result["SYSTEM"], dict)


class TestCompilerPhysicsConstraints:
    """Tests for Compiler physics constraint validation."""
    
    def test_soc_with_nonspin_raises_error(self):
        """WITH_SOC with NONSPIN spin should raise PresetCompilationError."""
        with pytest.raises(PresetCompilationError) as exc_info:
            compile_soc(SOCOption.WITH_SOC, spin=SpinOption.NONSPIN)
        
        assert "noncollinear" in str(exc_info.value).lower()
    
    def test_soc_with_collinear_raises_error(self):
        """WITH_SOC with COLLINEAR spin should raise PresetCompilationError."""
        with pytest.raises(PresetCompilationError) as exc_info:
            compile_soc(SOCOption.WITH_SOC, spin=SpinOption.COLLINEAR)
        
        assert "noncollinear" in str(exc_info.value).lower()
    
    def test_soc_with_noncollinear_succeeds(self):
        """WITH_SOC with NONCOLLINEAR spin should succeed."""
        result = compile_soc(SOCOption.WITH_SOC, spin=SpinOption.NONCOLLINEAR)
        assert result["lspinorb"] == ".true."
    
    def test_compile_presets_soc_nonspin_raises(self):
        """compile_presets with WITH_SOC and NONSPIN should raise error."""
        options = {
            "spin": SpinOption.NONSPIN,
            "soc": SOCOption.WITH_SOC,
            "material": MaterialOption.INSULATOR,
        }
        with pytest.raises(PresetCompilationError):
            compile_presets(options, validate_physics=True)
    
    def test_compile_presets_skip_physics_validation(self):
        """compile_presets with validate_physics=False should not raise."""
        options = {
            "spin": SpinOption.NONSPIN,
            "soc": SOCOption.WITH_SOC,  # Invalid combo
            "material": MaterialOption.INSULATOR,
        }
        # Should not raise when validation is disabled
        result = compile_presets(options, validate_physics=False)
        assert "SYSTEM" in result


class TestCompilerStringOptions:
    """Tests for Compiler string option normalization."""
    
    def test_compile_presets_string_spin(self):
        """compile_presets should accept string spin values."""
        options = {
            "spin": "collinear",
            "soc": "no_soc",
            "material": "metal",
        }
        result = compile_presets(options)
        
        assert result["SYSTEM"]["nspin"] == 2
    
    def test_compile_presets_string_noncollinear(self):
        """compile_presets should accept 'noncollinear' string."""
        options = {
            "spin": "noncollinear",
            "soc": "with_soc",
            "material": "metal",
        }
        result = compile_presets(options)
        
        assert result["SYSTEM"]["noncolin"] == ".true."
        assert result["SYSTEM"]["lspinorb"] == ".true."


class TestCompilerPostProcessing:
    """Tests for Compiler handling of post-processing steps."""
    
    def test_compile_presets_for_dos_step(self):
        """DOS step should return empty params (inherits from PW calc)."""
        from quantumvitas.presets import compile_presets_for_step
        
        options = {
            "spin": SpinOption.COLLINEAR,
            "soc": SOCOption.NO_SOC,
            "material": MaterialOption.METAL,
        }
        result = compile_presets_for_step("dos", options)
        
        # Post-processing steps don't get preset params
        assert result == {}
    
    def test_compile_presets_for_bands_step(self):
        """BANDS step should return empty params."""
        from quantumvitas.presets import compile_presets_for_step
        
        options = {"spin": SpinOption.NONSPIN}
        result = compile_presets_for_step("bands", options)
        
        assert result == {}
    
    def test_compile_presets_for_scf_step(self):
        """SCF step should return full preset params."""
        from quantumvitas.presets import compile_presets_for_step
        
        options = {
            "spin": SpinOption.COLLINEAR,
            "soc": SOCOption.NO_SOC,
            "material": MaterialOption.METAL,
        }
        result = compile_presets_for_step("scf", options)
        
        assert "SYSTEM" in result
        assert result["SYSTEM"]["nspin"] == 2


class TestMultiStepCompilerDetectorEquivalence:
    """Tests for multi-step equivalence scenarios."""
    
    def test_homogeneous_compiled_steps_detect_single_value(self):
        """Multiple steps compiled with same options should detect that value."""
        options = {
            "spin": SpinOption.COLLINEAR,
            "soc": SOCOption.NO_SOC,
            "material": MaterialOption.METAL,
        }
        
        # Compile the same options multiple times
        step1 = compile_presets(options)
        step2 = compile_presets(options)
        step3 = compile_presets(options)
        
        detected = detect_all_presets([step1, step2, step3])
        
        assert detected["spin"] == SpinOption.COLLINEAR
        assert detected["soc"] == SOCOption.NO_SOC
        assert detected["material"] == MaterialOption.METAL
    
    def test_heterogeneous_compiled_steps_detect_custom(self):
        """Steps compiled with different options should detect CUSTOM."""
        step1 = compile_presets({
            "spin": SpinOption.NONSPIN,
            "soc": SOCOption.NO_SOC,
            "material": MaterialOption.INSULATOR,
        })
        step2 = compile_presets({
            "spin": SpinOption.COLLINEAR,
            "soc": SOCOption.NO_SOC,
            "material": MaterialOption.METAL,
        })
        
        detected = detect_all_presets([step1, step2])
        
        # Different spin values -> CUSTOM
        assert detected["spin"] is CUSTOM
        # Same SOC values -> NO_SOC
        assert detected["soc"] == SOCOption.NO_SOC
        # Different material values -> CUSTOM
        assert detected["material"] is CUSTOM

