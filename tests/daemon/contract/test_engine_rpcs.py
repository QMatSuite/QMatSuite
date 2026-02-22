"""RPC contract tests for engine management endpoints."""

import pytest
from quantumvitas.daemon.server import QVDaemon
from .conftest import send_request


class TestListEngineFamilies:
    """Contract tests for list_engine_families RPC."""

    def test_list_engine_families_happy_path(self, daemon: QVDaemon):
        """list_engine_families returns all 15 engines."""
        response = send_request(daemon, "list_engine_families", {})

        assert "engines" in response
        engines = response["engines"]
        assert isinstance(engines, list)
        assert len(engines) >= 15  # QE, VASP, ORCA, LAMMPS, etc.

        # Validate schema matches TypeScript EngineFamilyInfo
        for engine in engines:
            assert "engine_family" in engine
            assert "display_name" in engine
            assert "supported_gen_steps" in engine

    def test_list_engine_families_includes_qe(self, daemon: QVDaemon):
        """list_engine_families includes qe engine."""
        response = send_request(daemon, "list_engine_families", {})
        engine_names = [e["engine_family"] for e in response["engines"]]
        assert "qe" in engine_names


class TestSetEngineFamily:
    """Contract tests for set_engine_family RPC."""

    def test_set_engine_family_immutable(self, demo_project_with_calculation, daemon: QVDaemon):
        """set_engine_family errors when trying to change immutable engine."""
        project_root, _, calc_ulid = demo_project_with_calculation

        # Engine family is immutable after creation - should error
        with pytest.raises(RuntimeError) as exc_info:
            send_request(daemon, "set_engine_family", {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "engine_family": "vasp"
            })
        
        assert "immutable" in str(exc_info.value).lower()

    def test_set_engine_family_invalid_engine(self, demo_project_with_calculation, daemon: QVDaemon):
        """set_engine_family errors on unknown engine."""
        project_root, _, calc_ulid = demo_project_with_calculation

        with pytest.raises(RuntimeError):
            send_request(daemon, "set_engine_family", {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "engine_family": "nonexistent_engine"
            })


class TestEngineInstallManagement:
    """Contract tests for Step 3 engine installation RPC endpoints."""

    def test_engine_list_installable_happy_path(self, daemon: QVDaemon, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            "quantumvitas.api.engines.list_installable_engines",
            lambda: [
                {"engine": "xtb", "manual_only": False},
                {"engine": "vasp", "manual_only": True},
            ],
        )

        response = send_request(daemon, "engine.list_installable", {})
        assert response["count"] == 2
        assert response["engines"][0]["engine"] == "xtb"

    def test_engine_install_returns_job_id(self, daemon: QVDaemon, monkeypatch: pytest.MonkeyPatch):
        captured: dict[str, object] = {}

        def fake_submit(job_type, func, params, target_name=None, project_root_display=None, **kwargs):
            captured["job_type"] = job_type
            captured["params"] = params
            captured["target_name"] = target_name
            return "job-install-1"

        monkeypatch.setattr(daemon.job_manager, "submit", fake_submit)

        response = send_request(
            daemon,
            "engine.install",
            {"engine_family": "xtb", "version": "6.7.1", "source": "conda"},
        )
        assert response["job_id"] == "job-install-1"
        assert response["status"] == "pending"
        assert captured["job_type"] == "engine_install"
        assert captured["params"] == {
            "engine_family": "xtb",
            "version": "6.7.1",
            "source": "conda",
        }

    def test_engine_uninstall_returns_job_id(self, daemon: QVDaemon, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(daemon.job_manager, "submit", lambda *args, **kwargs: "job-uninstall-1")

        response = send_request(
            daemon,
            "engine.uninstall",
            {"engine_family": "xtb", "installation_id": "conda-6.7.1"},
        )
        assert response["job_id"] == "job-uninstall-1"
        assert response["status"] == "pending"
