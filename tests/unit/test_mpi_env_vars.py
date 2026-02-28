"""
Unit tests for MPI environment variable support in EngineConfig.

Tests QMS_MPI_COMMAND and QMS_MPI_CORES environment variable overrides.
"""

import pytest
import platform
import stat
from pathlib import Path

from qmatsuite.core.engines.base import EngineConfig, EngineConfigError


def _make_mock_qe(tmp_path):
    """Create a minimal mock QE installation for build_command tests."""
    qe_root = tmp_path / "qe"
    bin_dir = qe_root / "bin"
    bin_dir.mkdir(parents=True)
    exe_name = "pw.exe" if platform.system() == "Windows" else "pw.x"
    exe = bin_dir / exe_name
    exe.write_text("mock")
    if platform.system() != "Windows":
        exe.chmod(stat.S_IRWXU)
    return qe_root


class TestMPIEnvVarConfig:
    """Test QMS_MPI_COMMAND and QMS_MPI_CORES environment variable overrides."""

    def test_default_no_env_vars(self, monkeypatch):
        """Default (no env vars): serial mode, mpi_cores=1, mpi_command=None."""
        monkeypatch.delenv("QMS_MPI_COMMAND", raising=False)
        monkeypatch.delenv("QMS_MPI_CORES", raising=False)
        config = EngineConfig(name="qe")
        assert config.mpi_cores == 1
        assert config.mpi_command is None

    def test_cores_4_mpirun_exists(self, monkeypatch):
        """QMS_MPI_CORES=4 with mpirun in PATH: MPI mode with mpirun."""
        monkeypatch.delenv("QMS_MPI_COMMAND", raising=False)
        monkeypatch.setenv("QMS_MPI_CORES", "4")
        # Mock shutil.which to say mpirun exists
        monkeypatch.setattr("shutil.which", lambda cmd: f"/usr/bin/{cmd}")
        config = EngineConfig(name="qe")
        assert config.mpi_cores == 4
        assert config.mpi_command == "mpirun"  # auto-defaulted

    def test_cores_4_mpirun_not_found(self, monkeypatch):
        """QMS_MPI_CORES=4, mpirun NOT in PATH: raises EngineConfigError."""
        monkeypatch.delenv("QMS_MPI_COMMAND", raising=False)
        monkeypatch.setenv("QMS_MPI_CORES", "4")
        monkeypatch.setattr("shutil.which", lambda cmd: None)
        with pytest.raises(EngineConfigError, match="not found in PATH"):
            EngineConfig(name="qe")

    def test_cores_1_serial(self, monkeypatch):
        """QMS_MPI_CORES=1: serial mode (no MPI)."""
        monkeypatch.delenv("QMS_MPI_COMMAND", raising=False)
        monkeypatch.setenv("QMS_MPI_CORES", "1")
        config = EngineConfig(name="qe")
        assert config.mpi_cores == 1
        assert config.mpi_command is None

    def test_cores_0_serial(self, monkeypatch):
        """QMS_MPI_CORES=0: serial mode (no MPI)."""
        monkeypatch.delenv("QMS_MPI_COMMAND", raising=False)
        monkeypatch.setenv("QMS_MPI_CORES", "0")
        config = EngineConfig(name="qe")
        assert config.mpi_cores == 0
        assert config.mpi_command is None

    def test_custom_command_with_cores(self, monkeypatch):
        """QMS_MPI_COMMAND=mpiexec, QMS_MPI_CORES=4: uses mpiexec."""
        monkeypatch.setenv("QMS_MPI_COMMAND", "mpiexec")
        monkeypatch.setenv("QMS_MPI_CORES", "4")
        monkeypatch.setattr("shutil.which", lambda cmd: f"/usr/bin/{cmd}")
        config = EngineConfig(name="qe")
        assert config.mpi_cores == 4
        assert config.mpi_command == "mpiexec"

    def test_command_without_cores_serial(self, monkeypatch):
        """QMS_MPI_COMMAND=mpirun, QMS_MPI_CORES unset: serial (command ignored)."""
        monkeypatch.setenv("QMS_MPI_COMMAND", "mpirun")
        monkeypatch.delenv("QMS_MPI_CORES", raising=False)
        config = EngineConfig(name="qe")
        assert config.mpi_cores == 1
        # mpi_command is set but won't be used since cores <= 1
        assert config.mpi_command == "mpirun"

    def test_env_overrides_instance_config(self, monkeypatch):
        """Environment variables take priority over constructor arguments."""
        monkeypatch.setenv("QMS_MPI_COMMAND", "srun")
        monkeypatch.setenv("QMS_MPI_CORES", "8")
        monkeypatch.setattr("shutil.which", lambda cmd: f"/usr/bin/{cmd}")
        config = EngineConfig(name="qe", mpi_command="mpirun", mpi_cores=2)
        assert config.mpi_cores == 8
        assert config.mpi_command == "srun"

    def test_error_message_includes_guidance(self, monkeypatch):
        """Error message tells user how to fix the problem."""
        monkeypatch.setenv("QMS_MPI_CORES", "4")
        monkeypatch.setenv("QMS_MPI_COMMAND", "nonexistent_mpi")
        monkeypatch.setattr("shutil.which", lambda cmd: None)
        with pytest.raises(EngineConfigError) as exc_info:
            EngineConfig(name="qe")
        msg = str(exc_info.value)
        assert "nonexistent_mpi" in msg
        assert "not found in PATH" in msg
        assert "unset QMS_MPI_CORES" in msg

    def test_invalid_cores_string_ignored(self, monkeypatch):
        """Non-numeric QMS_MPI_CORES value is ignored (uses default)."""
        monkeypatch.setenv("QMS_MPI_CORES", "abc")
        monkeypatch.delenv("QMS_MPI_COMMAND", raising=False)
        config = EngineConfig(name="qe")
        assert config.mpi_cores == 1  # default preserved


class TestMPIBuildCommand:
    """Test that build_command correctly uses MPI config from env vars."""

    def test_serial_command(self, monkeypatch, tmp_path):
        """Serial mode: command is just the executable."""
        monkeypatch.delenv("QMS_MPI_COMMAND", raising=False)
        monkeypatch.delenv("QMS_MPI_CORES", raising=False)
        qe_root = _make_mock_qe(tmp_path)
        from qmatsuite.core.engines.qe import QuantumEspressoEngine
        config = EngineConfig(name="qe", qe_home=qe_root)
        engine = QuantumEspressoEngine(config)
        input_file = tmp_path / "scf.in"
        input_file.write_text("&control\n/\n")
        cmd = engine.build_command("qe_scf", input_file, tmp_path)
        # Should NOT have mpirun prefix
        assert "mpirun" not in cmd[0]
        assert cmd[0].endswith("pw.x") or cmd[0].endswith("pw.exe")

    def test_mpi_command_from_env(self, monkeypatch, tmp_path):
        """MPI env vars produce mpirun prefix in build_command."""
        monkeypatch.setenv("QMS_MPI_CORES", "4")
        monkeypatch.setenv("QMS_MPI_COMMAND", "mpirun")
        monkeypatch.setattr("shutil.which", lambda cmd: f"/usr/bin/{cmd}")
        qe_root = _make_mock_qe(tmp_path)
        from qmatsuite.core.engines.qe import QuantumEspressoEngine
        config = EngineConfig(name="qe", qe_home=qe_root)
        engine = QuantumEspressoEngine(config)
        input_file = tmp_path / "scf.in"
        input_file.write_text("&control\n/\n")
        cmd = engine.build_command("qe_scf", input_file, tmp_path)
        assert cmd[0] == "mpirun"
        assert cmd[1] == "-np"
        assert cmd[2] == "4"
        assert cmd[3].endswith("pw.x") or cmd[3].endswith("pw.exe")
