"""
RPC contract tests for system endpoints.

Tests:
- ping: System health check
- shutdown: Daemon shutdown
"""

from qmatsuite.daemon.server import QMSDaemon

from .conftest import send_request


class TestPingRPC:
    """Contract tests for ping RPC."""

    def test_ping_happy_path(self, daemon: QMSDaemon):
        """ping returns pong and version."""
        response = send_request(daemon, "ping", {})

        assert response["pong"] is True
        assert "version" in response
        assert isinstance(response["version"], str)
        assert len(response["version"]) > 0

    def test_ping_ignores_extra_params(self, daemon: QMSDaemon):
        """ping ignores unexpected parameters."""
        response = send_request(daemon, "ping", {"foo": "bar", "baz": 123})

        assert response["pong"] is True
        assert "version" in response


class TestShutdownRPC:
    """Contract tests for shutdown RPC."""

    def test_shutdown_happy_path(self, daemon: QMSDaemon):
        """shutdown returns success."""
        response = send_request(daemon, "shutdown", {})

        assert response["shutdown"] is True
        assert daemon._running is False  # Daemon should be stopped

    def test_shutdown_ignores_extra_params(self, daemon: QMSDaemon):
        """shutdown ignores unexpected parameters."""
        response = send_request(daemon, "shutdown", {"foo": "bar"})

        assert response["shutdown"] is True
