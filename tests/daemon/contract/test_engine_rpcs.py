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


class TestEngineRegistryRPCs:
    """Contract tests for registry-backed generic engine RPC endpoints."""

    def test_engine_list_happy_path(self, daemon: QVDaemon, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            "quantumvitas.api.engines.list_engines",
            lambda installed_only=False: [
                {"engine": "qe", "installed": True, "active_source": "bundled", "installations": []},
                {"engine": "xtb", "installed": False, "active_source": None, "installations": []},
            ],
        )

        response = send_request(daemon, "engine.list", {"installed_only": False})
        assert response["count"] == 2
        assert response["engines"][0]["engine"] == "qe"
        assert response["installed_only"] is False

    def test_engine_verify_happy_path(self, daemon: QVDaemon, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("quantumvitas.api.engines.verify_engine", lambda family: (True, f"{family}:OK"))

        response = send_request(daemon, "engine.verify", {"engine_family": "qe"})
        assert response["engine"] == "qe"
        assert response["ok"] is True
        assert response["message"] == "qe:OK"

    def test_engine_set_active_happy_path(self, daemon: QVDaemon, monkeypatch: pytest.MonkeyPatch):
        captured: dict[str, str] = {}

        def fake_set_active(engine_family: str, installation_id: str) -> bool:
            captured["engine_family"] = engine_family
            captured["installation_id"] = installation_id
            return True

        monkeypatch.setattr("quantumvitas.api.engines.set_active_engine", fake_set_active)

        response = send_request(
            daemon,
            "engine.set_active",
            {"engine_family": "qe", "installation_id": "bundled-7.5"},
        )
        assert response["active"] is True
        assert captured == {"engine_family": "qe", "installation_id": "bundled-7.5"}

    def test_engine_set_active_missing_id_returns_false(self, daemon: QVDaemon):
        response = send_request(
            daemon,
            "engine.set_active",
            {"engine_family": "qe"},
        )
        assert response["active"] is False
        assert "required" in response["message"]

    def test_engine_register_path_happy_path(self, daemon: QVDaemon, monkeypatch: pytest.MonkeyPatch):
        captured: dict[str, object] = {}

        def fake_register(engine_family: str, path: str, source: str, env_vars=None):
            captured["engine_family"] = engine_family
            captured["path"] = path
            captured["source"] = source
            captured["env_vars"] = env_vars
            return {"id": "user-test", "source": source, "path": path}

        monkeypatch.setattr("quantumvitas.api.engines.register_engine", fake_register)

        response = send_request(
            daemon,
            "engine.register_path",
            {
                "engine_family": "vasp",
                "path": "/opt/vasp/bin",
                "source": "user_path",
                "env_vars": {"VASP_PP_PATH": "/opt/vasp/potpaw"},
            },
        )
        assert response["engine"] == "vasp"
        assert response["installation"]["source"] == "user_path"
        assert response["installation"]["path"] == "/opt/vasp/bin"
        assert captured["engine_family"] == "vasp"
        assert captured["path"] == "/opt/vasp/bin"
        assert captured["source"] == "user_path"

    def test_engine_unregister_happy_path(self, daemon: QVDaemon, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("quantumvitas.api.engines.unregister_engine", lambda family, inst: True)

        response = send_request(
            daemon,
            "engine.unregister",
            {"engine_family": "qe", "installation_id": "bundled-7.5"},
        )
        assert response["removed"] is True

    def test_engine_unregister_missing_id_returns_false(self, daemon: QVDaemon):
        response = send_request(
            daemon,
            "engine.unregister",
            {"engine_family": "qe"},
        )
        assert response["removed"] is False
        assert "required" in response["message"]
