"""Unit tests for ORCA engine (no binary required)."""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class MockStep:
    """Mock step for testing."""
    ulid: str
    # public_type removed - use step_type_gen
    step_type_spec: str  # SPEC type (e.g., "orca_scf")
    step_type_gen: str = ""  # GEN type (e.g., "scf") - derived from spec
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def meta(self):
        """Mock meta attribute for compatibility."""
        class MockMeta:
            def __init__(self, ulid):
                self.ulid = ulid
        return MockMeta(self.ulid)


@dataclass
class MockMolecule:
    """Mock molecule for testing."""
    atoms: str = """O   0.000000   0.000000   0.117300
H   0.000000   0.756950  -0.469200
H   0.000000  -0.756950  -0.469200"""
    charge: int = 0
    multiplicity: int = 1


class TestORCAEngine:
    """Tests for ORCA engine initialization and setup."""

    def test_engine_creation_with_path(self):
        """Engine can be created with explicit path."""
        from quantumvitas.engine.orca_engine import ORCAEngine

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'is_file', return_value=True):
                engine = ORCAEngine(orca_bin=Path("/fake/orca"))
                assert engine is not None
                assert engine.orca_binary == Path("/fake/orca")

    def test_engine_probe_success(self):
        """Engine probe returns True when binary exists and runs."""
        from quantumvitas.engine.orca_engine import ORCAEngine

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "ORCA 6.1.1"
        mock_result.stderr = ""

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'is_file', return_value=True):
                with patch('subprocess.run', return_value=mock_result):
                    engine = ORCAEngine(orca_bin=Path("/fake/orca"))
                    available, version = engine.probe()
                    assert available is True
                    assert "ORCA" in version

    def test_engine_probe_binary_not_found(self):
        """Engine probe returns False when binary doesn't exist."""
        from quantumvitas.engine.orca_engine import ORCAEngine

        with patch.object(Path, 'exists', return_value=False):
            with patch.object(Path, 'is_file', return_value=False):
                engine = ORCAEngine.__new__(ORCAEngine)
                # Set private attributes directly (bypassing property accessor)
                engine._orca_binary = Path("/nonexistent/orca")
                engine._orca_dir = Path("/nonexistent")
                engine.config = Mock()
                engine._defer_binary_resolution = False  # Already resolved

                available, msg = engine.probe()
                assert available is False

    def test_command_building(self):
        """Test ORCA command construction."""
        from quantumvitas.engine.orca_engine import ORCAEngine

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'is_file', return_value=True):
                engine = ORCAEngine(orca_bin=Path("/fake/orca"))
                cmd = engine._build_command(Path("/work/chain01_scf.inp"))

                assert cmd[0] == "/fake/orca"
                assert "chain01_scf.inp" in cmd[1]

    def test_engine_step_types(self):
        """Engine reports supported step types."""
        from quantumvitas.engine.orca_engine import ORCAEngine

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'is_file', return_value=True):
                engine = ORCAEngine(orca_bin=Path("/fake/orca"))
                step_types = engine.supported_step_types()

                assert "orca_scf" in step_types
                assert "orca_hf" in step_types
                assert "orca_td" in step_types


class TestORCAPathResolution:
    """Tests for ORCA path resolution."""

    def test_bundled_path_found(self):
        """Bundled ORCA path is resolved correctly when exists."""
        from quantumvitas.core.engines.orca_resolver import resolve_orca_bin

        # This tests actual bundled location
        try:
            path = resolve_orca_bin()
            assert path.exists()
            assert path.name == "orca"
        except RuntimeError:
            pytest.skip("Bundled ORCA not available")

    def test_env_var_resolution(self):
        """ORCA_BIN env var is used if set."""
        from quantumvitas.core.engines.orca_resolver import resolve_orca_bin
        import os

        old_val = os.environ.get("QMATSUITE_ORCA_BIN")
        try:
            os.environ["QMATSUITE_ORCA_BIN"] = "/custom/path/orca"
            with patch.object(Path, 'exists', return_value=True):
                with patch.object(Path, 'is_file', return_value=True):
                    path = resolve_orca_bin()
                    assert str(path) == "/custom/path/orca"
        finally:
            if old_val:
                os.environ["QMATSUITE_ORCA_BIN"] = old_val
            else:
                os.environ.pop("QMATSUITE_ORCA_BIN", None)

    def test_missing_orca_raises(self):
        """Missing ORCA raises RuntimeError when no fallback."""
        from quantumvitas.core.engines.orca_resolver import resolve_orca_bin
        import os

        old_val = os.environ.get("QMATSUITE_ORCA_BIN")
        try:
            os.environ.pop("QMATSUITE_ORCA_BIN", None)
            # If bundled ORCA doesn't exist, this should raise
            with patch.object(Path, 'exists', return_value=False):
                with pytest.raises(RuntimeError):
                    resolve_orca_bin()
        except RuntimeError:
            pass  # Expected when bundled ORCA not available
        finally:
            if old_val:
                os.environ["QMATSUITE_ORCA_BIN"] = old_val


class TestORCAEngineChainExecution:
    """Tests for ORCA chain execution (mocked)."""

    def test_run_chain_creates_input_file(self, tmp_path):
        """run_chain creates input file in working directory."""
        from quantumvitas.engine.orca_engine import ORCAEngine
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            ulid="s1",
            step_type_gen="scf",
            step_type_spec="orca_scf",
            
            parameters={"functional": "B3LYP", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")
        molecule = MockMolecule()

        # Mock subprocess to avoid actually running ORCA
        mock_result = Mock()
        mock_result.returncode = 0

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'is_file', return_value=True):
                with patch('subprocess.run', return_value=mock_result):
                    engine = ORCAEngine(orca_bin=Path("/fake/orca"))
                    # Create empty files to simulate ORCA output
                    (tmp_path / "chain01_scf.out").write_text("FINAL SINGLE POINT ENERGY -75.96")
                    (tmp_path / "chain01_scf.property.txt").write_text("")

                    results = engine.run_chain(chain, tmp_path, molecule)

                    # Input file should be created
                    assert (tmp_path / "chain01_scf.inp").exists()

    def test_run_chain_returns_step_results(self, tmp_path):
        """run_chain returns StepResult for each step in chain."""
        from quantumvitas.engine.orca_engine import ORCAEngine
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            ulid="s1",
            step_type_gen="scf",
            step_type_spec="orca_scf",
            
            parameters={"functional": "HF", "basis": "def2-SVP"},
        )
        td_step = MockStep(
            ulid="s2",
            step_type_gen="td",
            step_type_spec="orca_td",
            
            parameters={"nroots": 3, "tda": True},
        )
        chain = QCChain(scf_root=scf_step, downstream=[td_step], key="chain01_scf_td")
        molecule = MockMolecule()

        mock_result = Mock()
        mock_result.returncode = 0

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'is_file', return_value=True):
                with patch('subprocess.run', return_value=mock_result):
                    engine = ORCAEngine(orca_bin=Path("/fake/orca"))
                    # Create empty files
                    (tmp_path / "chain01_scf_td.out").write_text("")
                    (tmp_path / "chain01_scf_td.property.txt").write_text("")

                    results = engine.run_chain(chain, tmp_path, molecule)

                    assert len(results) == 2
                    assert results[0].step_ulid == "s1"
                    assert results[1].step_ulid == "s2"
