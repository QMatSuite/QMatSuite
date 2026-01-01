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
    MagnetismOption,
    OccupationsSchemeOption,
    CUSTOM,
    detect_magnetism,
    detect_occupations_scheme,
    detect_all_presets,
    compile_magnetism,
    compile_occupations_scheme,
    compile_presets,
    PresetCompilationError,
)
from quantumvitas.presets.detector import detect_dimension_from_steps


class TestMagnetismDetection:
    """Tests for magnetism dimension detection (merged spin + SOC)."""
    
    def test_explicit_nonmagnetic(self):
        """nspin=1 should detect as NONMAGNETIC."""
        params = {"SYSTEM": {"nspin": 1}}
        assert detect_magnetism(params) == MagnetismOption.NONMAGNETIC
    
    def test_explicit_collinear_lsda(self):
        """nspin=2 should detect as COLLINEAR_LSDA."""
        params = {"SYSTEM": {"nspin": 2}}
        assert detect_magnetism(params) == MagnetismOption.COLLINEAR_LSDA
    
    def test_explicit_noncollinear_via_noncolin(self):
        """noncolin=.true. should detect as NONCOLLINEAR."""
        params = {"SYSTEM": {"noncolin": ".true."}}
        assert detect_magnetism(params) == MagnetismOption.NONCOLLINEAR
    
    def test_explicit_noncollinear_via_noncolin_bool(self):
        """noncolin=True should detect as NONCOLLINEAR."""
        params = {"SYSTEM": {"noncolin": True}}
        assert detect_magnetism(params) == MagnetismOption.NONCOLLINEAR
    
    def test_explicit_nspin_4_implies_noncollinear(self):
        """nspin=4 with noncolin=true should detect as NONCOLLINEAR."""
        params = {"SYSTEM": {"nspin": 4, "noncolin": ".true."}}
        assert detect_magnetism(params) == MagnetismOption.NONCOLLINEAR
    
    def test_implicit_default_nonmagnetic(self):
        """Missing nspin should default to NONMAGNETIC per QE defaults."""
        params = {"SYSTEM": {"ecutwfc": 50}}
        assert detect_magnetism(params) == MagnetismOption.NONMAGNETIC
    
    def test_empty_params_defaults_nonmagnetic(self):
        """Empty params should default to NONMAGNETIC."""
        assert detect_magnetism({}) == MagnetismOption.NONMAGNETIC
    
    def test_noncolin_false_is_not_noncollinear(self):
        """noncolin=.false. with nspin=1 should detect as NONMAGNETIC.
        
        Note: Per ParamSpace framework, explicit false values are tolerated.
        """
        params = {"SYSTEM": {"noncolin": ".false.", "nspin": 1}}
        assert detect_magnetism(params) == MagnetismOption.NONMAGNETIC
    
    def test_noncolin_true_nspin2_contradiction(self):
        """noncolin=.true. with nspin=2 is a contradiction → CUSTOM."""
        params = {"SYSTEM": {"noncolin": ".true.", "nspin": 2}}
        assert detect_magnetism(params) == CUSTOM
    
    def test_noncollinear_soc(self):
        """noncolin=true, lspinorb=true should detect as NONCOLLINEAR_SOC."""
        params = {"SYSTEM": {"noncolin": ".true.", "lspinorb": ".true."}}
        assert detect_magnetism(params) == MagnetismOption.NONCOLLINEAR_SOC
    
    def test_case_insensitive_section(self):
        """Section names should be case-insensitive."""
        params = {"system": {"nspin": 2}}
        assert detect_magnetism(params) == MagnetismOption.COLLINEAR_LSDA


class TestOccupationsSchemeDetection:
    """Tests for occupations_scheme detection."""
    
    def test_smearing_gaussian_canonical(self):
        """occupations='smearing' + smearing='gaussian' + degauss=0.02 → SMEARING_GAUSSIAN."""
        params = {"SYSTEM": {"occupations": "smearing", "smearing": "gaussian", "degauss": 0.02}}
        assert detect_occupations_scheme(params) == OccupationsSchemeOption.SMEARING_GAUSSIAN
    
    def test_smearing_gauss_synonym(self):
        """occupations='smearing' + smearing='gauss' + degauss=0.02 → SMEARING_GAUSSIAN."""
        params = {"SYSTEM": {"occupations": "smearing", "smearing": "gauss", "degauss": 0.02}}
        assert detect_occupations_scheme(params) == OccupationsSchemeOption.SMEARING_GAUSSIAN
    
    def test_smearing_wrong_degauss(self):
        """occupations='smearing' + degauss != 0.02 → CUSTOM."""
        params = {"SYSTEM": {"occupations": "smearing", "smearing": "gaussian", "degauss": 0.01}}
        assert detect_occupations_scheme(params) == CUSTOM
    
    def test_smearing_non_gaussian(self):
        """occupations='smearing' + smearing != gaussian/gauss → CUSTOM."""
        params = {"SYSTEM": {"occupations": "smearing", "smearing": "mv", "degauss": 0.02}}
        assert detect_occupations_scheme(params) == CUSTOM
    
    def test_fixed_explicit(self):
        """occupations='fixed' → FIXED."""
        params = {"SYSTEM": {"occupations": "fixed"}}
        assert detect_occupations_scheme(params) == OccupationsSchemeOption.FIXED
    
    def test_fixed_missing_occupations(self):
        """Missing occupations → FIXED (QE default)."""
        params = {"SYSTEM": {"ecutwfc": 50}}
        assert detect_occupations_scheme(params) == OccupationsSchemeOption.FIXED
    
    def test_tetrahedra(self):
        """occupations='tetrahedra' → TETRAHEDRA."""
        params = {"SYSTEM": {"occupations": "tetrahedra"}}
        assert detect_occupations_scheme(params) == OccupationsSchemeOption.TETRAHEDRA
    
    def test_tetrahedra_opt_custom(self):
        """occupations='tetrahedra_opt' → CUSTOM."""
        params = {"SYSTEM": {"occupations": "tetrahedra_opt"}}
        assert detect_occupations_scheme(params) == CUSTOM
    
    def test_from_input_custom(self):
        """occupations='from_input' → CUSTOM."""
        params = {"SYSTEM": {"occupations": "from_input"}}
        assert detect_occupations_scheme(params) == CUSTOM


class TestMultiStepAggregation:
    """Tests for multi-step preset aggregation per Constitution 10.5.1."""
    
    def test_single_step_returns_value(self):
        """Single step should return its value (not Custom)."""
        steps = [{"SYSTEM": {"nspin": 2}}]
        result = detect_dimension_from_steps(steps, "magnetism")
        assert result == MagnetismOption.COLLINEAR_LSDA
    
    def test_homogeneous_steps_return_value(self):
        """Multiple steps with same value should return that value."""
        steps = [
            {"SYSTEM": {"nspin": 2}},
            {"SYSTEM": {"nspin": 2}},
            {"SYSTEM": {"nspin": 2}},
        ]
        result = detect_dimension_from_steps(steps, "magnetism")
        assert result == MagnetismOption.COLLINEAR_LSDA
    
    def test_heterogeneous_steps_return_custom(self):
        """Multiple steps with different values should return CUSTOM."""
        steps = [
            {"SYSTEM": {"nspin": 1}},
            {"SYSTEM": {"nspin": 2}},
        ]
        result = detect_dimension_from_steps(steps, "magnetism")
        assert result is CUSTOM
    
    def test_empty_steps_returns_default(self):
        """Empty step list should return the dimension's default."""
        result = detect_dimension_from_steps([], "magnetism")
        assert result == MagnetismOption.NONMAGNETIC
    
    def test_implicit_and_explicit_same_value_homogeneous(self):
        """Implicit default and explicit same value should be homogeneous."""
        steps = [
            {},  # Implicit nspin=1 (NONSPIN)
            {"SYSTEM": {"nspin": 1}},  # Explicit nspin=1 (NONSPIN)
        ]
        result = detect_dimension_from_steps(steps, "magnetism")
        assert result == MagnetismOption.NONMAGNETIC


class TestDetectAllPresets:
    """Tests for detect_all_presets function."""
    
    def test_returns_all_v0_dimensions(self):
        """detect_all_presets should return all v0 dimensions."""
        steps = [{"SYSTEM": {"nspin": 2, "occupations": "'smearing'"}}]
        result = detect_all_presets(steps)
        
        assert "magnetism" in result
        assert "occupations_scheme" in result
    
    def test_empty_steps_returns_defaults(self):
        """Empty steps should return defaults for all dimensions."""
        result = detect_all_presets([])
        
        assert result["magnetism"] == MagnetismOption.NONMAGNETIC
        assert result["occupations_scheme"] == OccupationsSchemeOption.FIXED
    
    def test_mixed_presets(self):
        """Should correctly detect mixed preset values."""
        steps = [{"SYSTEM": {
            "nspin": 2,
            "lspinorb": ".false.",
            "occupations": "'smearing'",
            "smearing": "'gaussian'",
            "degauss": 0.02,
        }}]
        result = detect_all_presets(steps)
        
        assert result["magnetism"] == MagnetismOption.COLLINEAR_LSDA
        assert result["occupations_scheme"] == OccupationsSchemeOption.SMEARING_GAUSSIAN


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
        
        assert detect_magnetism(params) == MagnetismOption.NONMAGNETIC
        # Si SCF has no occupations -> implicit insulator
        assert detect_occupations_scheme(params) == OccupationsSchemeOption.FIXED
    
    def test_fe_collinear_is_collinear_metal(self, test_data_dir: Path):
        """tests/data/8_Fe_DOS/1_collinear/fe.2_scf.in should be collinear metal."""
        input_file = test_data_dir / "8_Fe_DOS" / "1_collinear" / "fe.2_scf.in"
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")
        
        params = self._params_from_qe_file(input_file)
        
        # nspin=2 -> COLLINEAR_LSDA
        assert detect_magnetism(params) == MagnetismOption.COLLINEAR_LSDA
        # occupations='smearing' → check if SMEARING_GAUSSIAN or CUSTOM
        # (depends on smearing type and degauss value)
        occ_result = detect_occupations_scheme(params)
        assert occ_result in (OccupationsSchemeOption.SMEARING_GAUSSIAN, CUSTOM)
    
    def test_fe_noncollinear_is_noncollinear_metal(self, test_data_dir: Path):
        """tests/data/8_Fe_DOS/2_noncolinear/fe.scf_noncollin.in should be noncollinear metal."""
        input_file = test_data_dir / "8_Fe_DOS" / "2_noncolinear" / "fe.scf_noncollin.in"
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")
        
        params = self._params_from_qe_file(input_file)
        
        # noncolin=.true. -> NONCOLLINEAR
        assert detect_magnetism(params) == MagnetismOption.NONCOLLINEAR
        # occupations='smearing' → check if SMEARING_GAUSSIAN or CUSTOM
        # (depends on smearing type and degauss value)
        occ_result = detect_occupations_scheme(params)
        assert occ_result in (OccupationsSchemeOption.SMEARING_GAUSSIAN, CUSTOM)
    
    def test_al_dos_is_nonspin_metal(self, test_data_dir: Path):
        """tests/data/6_Al_DOS/al.2_scf.in should be nonspin metal."""
        input_file = test_data_dir / "6_Al_DOS" / "al.2_scf.in"
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")
        
        params = self._params_from_qe_file(input_file)
        
        # no nspin -> NONMAGNETIC (implicit)
        assert detect_magnetism(params) == MagnetismOption.NONMAGNETIC
        # occupations='smearing' → check if SMEARING_GAUSSIAN or CUSTOM
        # (depends on smearing type and degauss value)
        occ_result = detect_occupations_scheme(params)
        assert occ_result in (OccupationsSchemeOption.SMEARING_GAUSSIAN, CUSTOM)
    
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
        
        # All Si DOS steps should be nonmagnetic
        assert result["magnetism"] == MagnetismOption.NONMAGNETIC
        # Si DOS: scf has no occupations (FIXED), nscf has tetrahedra (TETRAHEDRA)
        # Steps disagree → CUSTOM
        assert result["occupations_scheme"] == CUSTOM


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
    
    def test_magnetism_roundtrip_nonmagnetic(self):
        """compile(nonmagnetic) -> detect should equal nonmagnetic."""
        compiled = compile_magnetism(MagnetismOption.NONMAGNETIC)
        # compiled is now {"SYSTEM": {...}}
        params = compiled
        detected = detect_magnetism(params, step_type="scf")
        
        assert detected == MagnetismOption.NONMAGNETIC
    
    def test_magnetism_roundtrip_collinear_lsda(self):
        """compile(collinear_lsda) -> detect should equal collinear_lsda."""
        compiled = compile_magnetism(MagnetismOption.COLLINEAR_LSDA)
        # compiled is now {"SYSTEM": {...}}
        params = compiled
        detected = detect_magnetism(params, step_type="scf")
        
        assert detected == MagnetismOption.COLLINEAR_LSDA
    
    def test_magnetism_roundtrip_noncollinear(self):
        """compile(noncollinear) -> detect should equal noncollinear."""
        compiled = compile_magnetism(MagnetismOption.NONCOLLINEAR)
        # compiled is now {"SYSTEM": {...}}
        params = compiled
        detected = detect_magnetism(params, step_type="scf")
        
        assert detected == MagnetismOption.NONCOLLINEAR
    
    def test_magnetism_roundtrip_noncollinear_soc(self):
        """compile(noncollinear_soc) -> detect should equal noncollinear_soc."""
        compiled = compile_magnetism(MagnetismOption.NONCOLLINEAR_SOC)
        # compiled is now {"SYSTEM": {...}}
        params = compiled
        detected = detect_magnetism(params, step_type="scf")
        
        assert detected == MagnetismOption.NONCOLLINEAR_SOC
    
    
    def test_occupations_scheme_roundtrip_fixed(self):
        """compile(fixed) -> detect should equal fixed."""
        from quantumvitas.presets import compile_occupations_scheme
        
        compiled = compile_occupations_scheme(OccupationsSchemeOption.FIXED)
        # compiled is now {"SYSTEM": {...}}
        params = compiled
        detected = detect_occupations_scheme(params, step_type="scf")
        
        assert detected == OccupationsSchemeOption.FIXED
    
    def test_occupations_scheme_roundtrip_smearing_gaussian(self):
        """compile(smearing_gaussian) -> detect should equal smearing_gaussian."""
        from quantumvitas.presets import compile_occupations_scheme
        
        compiled = compile_occupations_scheme(OccupationsSchemeOption.SMEARING_GAUSSIAN)
        # compiled is now {"SYSTEM": {...}}
        params = compiled
        detected = detect_occupations_scheme(params, step_type="scf")
        
        assert detected == OccupationsSchemeOption.SMEARING_GAUSSIAN
    
    def test_occupations_scheme_roundtrip_tetrahedra(self):
        """compile(tetrahedra) -> detect should equal tetrahedra."""
        from quantumvitas.presets import compile_occupations_scheme
        
        compiled = compile_occupations_scheme(OccupationsSchemeOption.TETRAHEDRA)
        # compiled is now {"SYSTEM": {...}}
        params = compiled
        detected = detect_occupations_scheme(params, step_type="scf")
        
        assert detected == OccupationsSchemeOption.TETRAHEDRA
    
    def test_full_preset_roundtrip_defaults(self):
        """compile_presets with defaults should roundtrip through detect_all_presets."""
        from quantumvitas.presets import compile_presets
        
        options = {
            "magnetism": MagnetismOption.NONMAGNETIC,
            "occupations_scheme": OccupationsSchemeOption.FIXED,
        }
        compiled = compile_presets(options)
        detected = detect_all_presets([compiled])
        
        assert detected["magnetism"] == MagnetismOption.NONMAGNETIC
        assert detected["occupations_scheme"] == OccupationsSchemeOption.FIXED
    
    def test_full_preset_roundtrip_collinear_metal(self):
        """compile_presets for collinear metal should roundtrip correctly."""
        from quantumvitas.presets import compile_presets
        
        options = {
            "magnetism": MagnetismOption.COLLINEAR_LSDA,
            "occupations_scheme": OccupationsSchemeOption.SMEARING_GAUSSIAN,
        }
        compiled = compile_presets(options)
        detected = detect_all_presets([compiled])
        
        assert detected["magnetism"] == MagnetismOption.COLLINEAR_LSDA
        assert detected["occupations_scheme"] == OccupationsSchemeOption.SMEARING_GAUSSIAN
    
    def test_full_preset_roundtrip_noncollinear_soc(self):
        """compile_presets for noncollinear with SOC should roundtrip correctly."""
        from quantumvitas.presets import compile_presets
        
        options = {
            "magnetism": MagnetismOption.NONCOLLINEAR_SOC,
            "occupations_scheme": OccupationsSchemeOption.SMEARING_GAUSSIAN,
        }
        compiled = compile_presets(options)
        detected = detect_all_presets([compiled])
        
        assert detected["magnetism"] == MagnetismOption.NONCOLLINEAR_SOC
        assert detected["occupations_scheme"] == OccupationsSchemeOption.SMEARING_GAUSSIAN


class TestCompilerCanonicalEncoding:
    """
    Tests for Compiler canonical encoding per Constitution 10.3.4.
    
    Compiler must explicitly write all key parameters - no reliance on defaults.
    """
    
    def test_compile_magnetism_nonmagnetic_explicit_nspin(self):
        """compile_magnetism(NONMAGNETIC) must explicitly write nspin=1."""
        result = compile_magnetism(MagnetismOption.NONMAGNETIC)
        
        assert "SYSTEM" in result
        system = result["SYSTEM"]
        assert "nspin" in system
        assert system["nspin"] == 1
    
    def test_compile_magnetism_collinear_lsda_explicit_nspin(self):
        """compile_magnetism(COLLINEAR_LSDA) must explicitly write nspin=2."""
        result = compile_magnetism(MagnetismOption.COLLINEAR_LSDA)
        
        assert "SYSTEM" in result
        system = result["SYSTEM"]
        assert "nspin" in system
        assert system["nspin"] == 2
    
    def test_compile_magnetism_noncollinear_explicit_noncolin(self):
        """compile_magnetism(NONCOLLINEAR) must explicitly write noncolin=.true."""
        result = compile_magnetism(MagnetismOption.NONCOLLINEAR)
        
        assert "SYSTEM" in result
        system = result["SYSTEM"]
        assert "noncolin" in system
        assert system["noncolin"] == ".true."
        # Should NOT write nspin per QE docs (NOT_APPLICABLE)
        assert "nspin" not in system
    
    def test_compile_magnetism_noncollinear_soc_explicit(self):
        """compile_magnetism(NONCOLLINEAR_SOC) must explicitly write noncolin and lspinorb."""
        result = compile_magnetism(MagnetismOption.NONCOLLINEAR_SOC)
        
        assert "SYSTEM" in result
        system = result["SYSTEM"]
        assert "noncolin" in system
        assert system["noncolin"] == ".true."
        assert "lspinorb" in system
        assert system["lspinorb"] == ".true."
        # Should NOT write nspin per QE docs (NOT_APPLICABLE)
        assert "nspin" not in system
    
    def test_compile_occupations_scheme_fixed_explicit(self):
        """compile_occupations_scheme(FIXED) must explicitly write occupations='fixed'."""
        result = compile_occupations_scheme(OccupationsSchemeOption.FIXED)
        
        assert "SYSTEM" in result
        system = result["SYSTEM"]
        assert "occupations" in system
        assert system["occupations"] == "fixed"
        # smearing and degauss should NOT be in result (will be removed by integration layer)
    
    def test_compile_occupations_scheme_smearing_gaussian_explicit(self):
        """compile_occupations_scheme(SMEARING_GAUSSIAN) must explicitly write all params."""
        result = compile_occupations_scheme(OccupationsSchemeOption.SMEARING_GAUSSIAN)
        
        assert "SYSTEM" in result
        system = result["SYSTEM"]
        assert "occupations" in system
        assert system["occupations"] == "smearing"
        assert "smearing" in system
        assert system["smearing"] == "gaussian"
        assert "degauss" in system
        assert system["degauss"] == 0.02
    
    def test_compile_occupations_scheme_tetrahedra_explicit(self):
        """compile_occupations_scheme(TETRAHEDRA) must explicitly write occupations='tetrahedra'."""
        result = compile_occupations_scheme(OccupationsSchemeOption.TETRAHEDRA)
        
        assert "SYSTEM" in result
        system = result["SYSTEM"]
        assert "occupations" in system
        assert system["occupations"] == "tetrahedra"
        # smearing and degauss should NOT be in result (will be removed by integration layer)
    
    def test_compile_presets_structure(self):
        """compile_presets should return section -> params structure."""
        options = {
            "magnetism": MagnetismOption.NONMAGNETIC,
            "occupations_scheme": OccupationsSchemeOption.FIXED,
        }
        result = compile_presets(options)
        
        assert "SYSTEM" in result
        assert isinstance(result["SYSTEM"], dict)


class TestCompilerPhysicsConstraints:
    """Tests for Compiler physics constraint validation.
    
    Note: With magnetism merge, all magnetism options are valid.
    Physics constraints are now enforced at the option level (e.g., SOC requires noncollinear).
    """
    
    def test_magnetism_all_options_valid(self):
        """All magnetism options should compile successfully."""
        # All magnetism options are valid (physics constraints built into options)
        for option in MagnetismOption:
            result = compile_magnetism(option)
            assert "SYSTEM" in result or result == {}  # Some may return empty if using defaults


class TestCompilerStringOptions:
    """Tests for Compiler string option normalization."""
    
    def test_compile_presets_string_magnetism(self):
        """compile_presets should accept string magnetism values."""
        options = {
            "magnetism": "collinear_lsda",
            "occupations_scheme": "smearing_gaussian",
        }
        result = compile_presets(options)
        
        assert result["SYSTEM"]["nspin"] == 2
    
    def test_compile_presets_string_noncollinear_soc(self):
        """compile_presets should accept 'noncollinear_soc' string."""
        options = {
            "magnetism": "noncollinear_soc",
            "occupations_scheme": "smearing_gaussian",
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
            "magnetism": MagnetismOption.COLLINEAR_LSDA,
            "occupations_scheme": OccupationsSchemeOption.SMEARING_GAUSSIAN,
        }
        result = compile_presets_for_step("dos", options)
        
        # Post-processing steps don't get preset params
        assert result == {}
    
    def test_compile_presets_for_bands_step(self):
        """BANDS step should return empty params."""
        from quantumvitas.presets import compile_presets_for_step
        
        options = {"magnetism": MagnetismOption.NONMAGNETIC}
        result = compile_presets_for_step("bands", options)
        
        assert result == {}
    
    def test_compile_presets_for_scf_step(self):
        """SCF step should return full preset params."""
        from quantumvitas.presets import compile_presets_for_step
        
        options = {
            "magnetism": MagnetismOption.COLLINEAR_LSDA,
            "occupations_scheme": OccupationsSchemeOption.SMEARING_GAUSSIAN,
        }
        result = compile_presets_for_step("scf", options)
        
        assert "SYSTEM" in result
        assert result["SYSTEM"]["nspin"] == 2


class TestMultiStepCompilerDetectorEquivalence:
    """Tests for multi-step equivalence scenarios."""
    
    def test_homogeneous_compiled_steps_detect_single_value(self):
        """Multiple steps compiled with same options should detect that value."""
        options = {
            "magnetism": MagnetismOption.COLLINEAR_LSDA,
            "occupations_scheme": OccupationsSchemeOption.SMEARING_GAUSSIAN,
        }
        
        # Compile the same options multiple times
        step1 = compile_presets(options)
        step2 = compile_presets(options)
        step3 = compile_presets(options)
        
        detected = detect_all_presets([step1, step2, step3])
        
        assert detected["magnetism"] == MagnetismOption.COLLINEAR_LSDA
        assert detected["occupations_scheme"] == OccupationsSchemeOption.SMEARING_GAUSSIAN
    
    def test_heterogeneous_compiled_steps_detect_custom(self):
        """Steps compiled with different options should detect CUSTOM."""
        step1 = compile_presets({
            "magnetism": MagnetismOption.NONMAGNETIC,
            "occupations_scheme": OccupationsSchemeOption.FIXED,
        })
        step2 = compile_presets({
            "magnetism": MagnetismOption.COLLINEAR_LSDA,
            "occupations_scheme": OccupationsSchemeOption.SMEARING_GAUSSIAN,
        })
        
        detected = detect_all_presets([step1, step2])
        
        # Different magnetism values -> CUSTOM
        assert detected["magnetism"] is CUSTOM
        # Different occupations_scheme values -> CUSTOM
        assert detected["occupations_scheme"] is CUSTOM

