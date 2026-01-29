"""Auto-crawl tests for stateless RPC methods."""

import pytest
from pathlib import Path

from tests.contract_crawler.crawler import crawl_all_methods, crawl_method
from tests.contract_crawler.payloads import get_minimal_payload
from quantumvitas.daemon.server import QVDaemon
from quantumvitas.api import QVService
from io import StringIO


class TestStatelessMethodsCrawl:
    """Test auto-crawling of stateless methods."""

    def test_crawl_ping(self):
        """Ping method returns expected shape."""
        daemon = QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())
        result = crawl_method(daemon, "ping", {})

        assert result.success
        assert result.json_serializable
        assert result.response_data is not None

    def test_crawl_get_env_info(self):
        """get_env_info returns JSON-serializable data."""
        daemon = QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())
        result = crawl_method(daemon, "get_env_info", {})

        assert result.success
        assert result.json_serializable

    def test_crawl_all_stateless_methods(self):
        """All stateless methods return JSON-serializable data."""
        report = crawl_all_methods(project_root=None)

        # Check no serialization failures
        not_serializable = report.not_json_serializable
        assert not not_serializable, f"Methods not JSON-serializable: {[r.method_name for r in not_serializable]}"

        # Expect some coverage of stateless methods
        assert report.total > 0
        assert len(report.covered) > 10, f"Expected >10 stateless methods covered, got {len(report.covered)}"


class TestProjectScopedMethodsCrawl:
    """Test auto-crawling of project-scoped methods."""

    @pytest.fixture
    def temp_project(self, tmp_path: Path):
        """Create minimal project for testing."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        QVService.init_project(project_root, name="test_project")
        return project_root

    def test_crawl_list_structures(self, temp_project):
        """list_structures returns expected shape."""
        daemon = QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())
        payload = {"project_root": str(temp_project)}
        result = crawl_method(daemon, "list_structures", payload)

        assert result.success
        assert result.json_serializable
        assert "structures" in result.response_data
        assert "count" in result.response_data

    def test_crawl_list_calculations(self, temp_project):
        """list_calculations returns expected shape."""
        daemon = QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())
        payload = {"project_root": str(temp_project)}
        result = crawl_method(daemon, "list_calculations", payload)

        assert result.success
        assert result.json_serializable
        assert "calculations" in result.response_data
        assert "count" in result.response_data

    def test_crawl_get_project_summary(self, temp_project):
        """get_project_summary returns expected shape."""
        daemon = QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())
        payload = {"project_root": str(temp_project)}
        result = crawl_method(daemon, "get_project_summary", payload)

        assert result.success
        assert result.json_serializable
        assert "name" in result.response_data or "project" in result.response_data


class TestCrawlReport:
    """Test crawl report generation."""

    def test_report_has_all_methods(self):
        """Report includes all registered methods."""
        from tests.contract_crawler.introspection import get_all_rpc_methods

        all_methods = get_all_rpc_methods()
        report = crawl_all_methods()

        report_methods = {r.method_name for r in report.results}
        all_method_names = {m.name for m in all_methods}

        missing = all_method_names - report_methods
        assert not missing, f"Methods missing from report: {missing}"

    def test_report_json_serializable(self):
        """Report itself is JSON-serializable."""
        import json

        report = crawl_all_methods()
        report_dict = report.to_dict()

        # Should not raise
        json_str = json.dumps(report_dict)
        assert json_str

