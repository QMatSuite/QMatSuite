"""
Unit tests for the QVDaemon and JobManager.
"""

import json
import pytest
import time
from io import StringIO
from pathlib import Path
from threading import Event
from unittest.mock import MagicMock, patch

from quantumvitas.daemon.server import QVDaemon, RPCRequest, RPCResponse
from quantumvitas.daemon.jobs import JobManager, JobStatus, Job


# =============================================================================
# JobManager Tests
# =============================================================================

class TestJobManager:
    """Tests for JobManager."""
    
    def test_submit_returns_job_id(self):
        """Test that submit returns a job ID."""
        manager = JobManager()
        
        job_id = manager.submit(
            job_type="test",
            func=lambda: {"result": "ok"},
            params={"key": "value"},
        )
        
        assert job_id is not None
        assert isinstance(job_id, str)
        assert len(job_id) > 0
        
        manager.shutdown()
    
    def test_job_completes_successfully(self):
        """Test that a job completes with result."""
        manager = JobManager()
        completed = Event()
        
        def work():
            return {"status": "done", "value": 42}
        
        job_id = manager.submit(
            job_type="test",
            func=work,
            params={},
        )
        
        # Wait for completion
        for _ in range(50):  # 5 seconds max
            status = manager.get_job_status(job_id)
            if status["status"] == "completed":
                break
            time.sleep(0.1)
        
        status = manager.get_job_status(job_id)
        assert status["status"] == "completed"
        assert status["result"]["status"] == "done"
        assert status["result"]["value"] == 42
        
        manager.shutdown()
    
    def test_job_failure_captured(self):
        """Test that job failures are captured."""
        manager = JobManager()
        
        def failing_work():
            raise ValueError("Test error")
        
        job_id = manager.submit(
            job_type="test",
            func=failing_work,
            params={},
        )
        
        # Wait for completion
        for _ in range(50):
            status = manager.get_job_status(job_id)
            if status["status"] in ("completed", "failed"):
                break
            time.sleep(0.1)
        
        status = manager.get_job_status(job_id)
        assert status["status"] == "failed"
        assert "Test error" in status["error"]
        
        manager.shutdown()
    
    def test_sequential_execution(self):
        """Test that jobs execute sequentially (max_workers=1)."""
        manager = JobManager(max_workers=1)
        execution_order = []
        
        def work(n):
            execution_order.append(n)
            time.sleep(0.1)
            return {"n": n}
        
        # Submit multiple jobs
        job_ids = []
        for i in range(3):
            job_id = manager.submit(
                job_type="test",
                func=work,
                params={"n": i},
                n=i,
            )
            job_ids.append(job_id)
        
        # Wait for all to complete
        for _ in range(100):
            all_done = all(
                manager.get_job_status(jid)["status"] in ("completed", "failed")
                for jid in job_ids
            )
            if all_done:
                break
            time.sleep(0.1)
        
        # Should execute in order
        assert execution_order == [0, 1, 2]
        
        manager.shutdown()
    
    def test_list_jobs_filtering(self):
        """Test listing jobs with filters."""
        manager = JobManager()
        
        # Submit some jobs
        manager.submit("type_a", lambda: {}, {})
        manager.submit("type_b", lambda: {}, {})
        manager.submit("type_a", lambda: {}, {})
        
        # Wait a bit
        time.sleep(0.3)
        
        all_jobs = manager.list_jobs()
        assert len(all_jobs) == 3
        
        type_a_jobs = manager.list_jobs(job_type="type_a")
        assert len(type_a_jobs) == 2
        
        manager.shutdown()
    
    def test_job_to_dict_schema(self):
        """Test that job.to_dict() returns expected schema."""
        manager = JobManager()
        
        job_id = manager.submit(
            job_type="test_type",
            func=lambda: {"result": "ok"},
            params={"param1": "value1"},
        )
        
        # Wait for completion
        time.sleep(0.2)
        
        job_dict = manager.get_job_status(job_id)
        
        assert "ulid" in job_dict
        assert "job_type" in job_dict
        assert "status" in job_dict
        assert "created_at" in job_dict
        assert "params" in job_dict
        
        assert job_dict["job_type"] == "test_type"
        assert job_dict["params"]["param1"] == "value1"
        
        manager.shutdown()


# =============================================================================
# QVDaemon Tests
# =============================================================================

class TestQVDaemonProtocol:
    """Tests for QVDaemon JSON-RPC protocol."""
    
    def test_ping_command(self):
        """Test ping command returns pong."""
        stdin = StringIO("")
        stdout = StringIO()
        
        daemon = QVDaemon(stdin=stdin, stdout=stdout)
        
        response = daemon.handle_request(RPCRequest(
            id="test-1",
            type="ping",
            payload={},
        ))
        
        assert response.ok
        assert response.data["pong"] is True
        assert "version" in response.data
    
    def test_unknown_command_error(self):
        """Test that unknown command returns error."""
        stdin = StringIO("")
        stdout = StringIO()
        
        daemon = QVDaemon(stdin=stdin, stdout=stdout)
        
        response = daemon.handle_request(RPCRequest(
            id="test-1",
            type="nonexistent_command",
            payload={},
        ))
        
        assert not response.ok
        assert response.error["code"] == "unknown_command"
        assert "available_commands" in response.error
    
    def test_invalid_json_error(self):
        """Test that invalid JSON returns parse error."""
        stdin = StringIO("")
        stdout = StringIO()
        
        daemon = QVDaemon(stdin=stdin, stdout=stdout)
        
        response = daemon.handle_line("not valid json")
        
        assert not response.ok
        assert response.error["code"] == "parse_error"
    
    def test_missing_type_error(self):
        """Test that missing type field returns error."""
        stdin = StringIO("")
        stdout = StringIO()
        
        daemon = QVDaemon(stdin=stdin, stdout=stdout)
        
        response = daemon.handle_line('{"ulid": "1", "payload": {}}')
        
        assert not response.ok
        assert response.error["code"] == "invalid_request"
    
    def test_response_serialization(self):
        """Test that responses serialize to valid JSON."""
        response = RPCResponse(
            id="test-1",
            ok=True,
            data={"key": "value", "number": 42},
        )
        
        json_str = response.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["ulid"] == "test-1"
        assert parsed["ok"] is True
        assert parsed["data"]["key"] == "value"
    
    def test_error_response_serialization(self):
        """Test that error responses serialize correctly."""
        response = RPCResponse(
            id="test-1",
            ok=False,
            error={"code": "test_error", "message": "Something went wrong"},
        )
        
        json_str = response.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["ulid"] == "test-1"
        assert parsed["ok"] is False
        assert parsed["error"]["code"] == "test_error"


class TestQVDaemonHandlers:
    """Tests for QVDaemon handler methods."""
    
    def test_get_project_summary_handler(self, tmp_path):
        """Test get_project_summary handler."""
        from quantumvitas.api import QVService
        
        # Create project
        project_root = QVService.init_project(tmp_path / "test_proj", name="Test")
        
        stdin = StringIO("")
        stdout = StringIO()
        daemon = QVDaemon(stdin=stdin, stdout=stdout)
        
        response = daemon.handle_request(RPCRequest(
            id="1",
            type="get_project_summary",
            payload={"project_root": str(project_root)},
        ))
        
        assert response.ok
        assert response.data["name"] == "Test"
        assert response.data["n_structures"] == 0
    
    def test_list_structures_handler(self, tmp_path):
        """Test list_structures handler."""
        from quantumvitas.api import QVService
        
        project_root = QVService.init_project(tmp_path / "test_proj")
        
        stdin = StringIO("")
        stdout = StringIO()
        daemon = QVDaemon(stdin=stdin, stdout=stdout)
        
        response = daemon.handle_request(RPCRequest(
            id="1",
            type="list_structures",
            payload={"project_root": str(project_root)},
        ))
        
        assert response.ok
        assert "structures" in response.data
        assert "count" in response.data
        assert response.data["count"] == 0
    
    def test_list_calculations_handler(self, tmp_path):
        """Test list_calculations handler."""
        from quantumvitas.api import QVService
        
        project_root = QVService.init_project(tmp_path / "test_proj")
        QVService.init_calculation(project_root, "wf1")
        
        stdin = StringIO("")
        stdout = StringIO()
        daemon = QVDaemon(stdin=stdin, stdout=stdout)
        
        response = daemon.handle_request(RPCRequest(
            id="1",
            type="list_calculations",
            payload={"project_root": str(project_root)},
        ))
        
        assert response.ok
        assert response.data["count"] == 1
    
    def test_missing_required_field_error(self, tmp_path):
        """Test that missing required fields return error."""
        from quantumvitas.api import QVService
        
        project_root = QVService.init_project(tmp_path / "test_proj")
        
        stdin = StringIO("")
        stdout = StringIO()
        daemon = QVDaemon(stdin=stdin, stdout=stdout)
        
        response = daemon.handle_request(RPCRequest(
            id="1",
            type="get_structure_vis",
            payload={"project_root": str(project_root)},  # Missing 'selector'
        ))
        
        assert not response.ok
        assert "selector" in response.error["message"]
    
    def test_run_calculation_returns_job_id(self, tmp_path):
        """Test that run_calculation returns a job ID."""
        from quantumvitas.api import QVService
        
        project_root = QVService.init_project(tmp_path / "test_proj")
        QVService.init_calculation(project_root, "test-wf")
        
        stdin = StringIO("")
        stdout = StringIO()
        daemon = QVDaemon(stdin=stdin, stdout=stdout)
        
        response = daemon.handle_request(RPCRequest(
            id="1",
            type="run_calculation",
            payload={
                "project_root": str(project_root),
                "calculation": "test-wf",
            },
        ))
        
        assert response.ok
        assert "job_id" in response.data
        assert response.data["status"] == "pending"
        
        daemon.job_manager.shutdown()
    
    def test_get_job_status_handler(self, tmp_path):
        """Test get_job_status handler."""
        from quantumvitas.api import QVService
        
        project_root = QVService.init_project(tmp_path / "test_proj")
        QVService.init_calculation(project_root, "test-wf")
        
        stdin = StringIO("")
        stdout = StringIO()
        daemon = QVDaemon(stdin=stdin, stdout=stdout)
        
        # Submit a job
        submit_response = daemon.handle_request(RPCRequest(
            id="1",
            type="run_calculation",
            payload={
                "project_root": str(project_root),
                "calculation": "test-wf",
            },
        ))
        job_id = submit_response.data["job_id"]
        
        # Check status
        status_response = daemon.handle_request(RPCRequest(
            id="2",
            type="get_job_status",
            payload={"job_id": job_id},
        ))
        
        assert status_response.ok
        assert status_response.data["ulid"] == job_id
        assert status_response.data["job_type"] == "run_calculation"
        
        daemon.job_manager.shutdown()
    
    def test_list_workflow_templates_schema(self):
        """Test list_workflow_templates handler returns correct schema (no widening)."""
        stdin = StringIO("")
        stdout = StringIO()
        daemon = QVDaemon(stdin=stdin, stdout=stdout)
        
        response = daemon.handle_request(RPCRequest(
            id="1",
            type="list_workflow_templates",
            payload={},
        ))
        
        assert response.ok
        assert "templates" in response.data
        templates = response.data["templates"]
        
        # Must be a list
        assert isinstance(templates, list)
        assert len(templates) > 0  # Should have at least one template
        
        # Schema validation for each template
        expected_keys = {"id", "ulid", "name", "description", "step_sequence"}  # ulid is backwards compat alias
        for template in templates:
            # Must be a dict
            assert isinstance(template, dict)

            # Keys must be exactly the expected set (no extras, no missing)
            actual_keys = set(template.keys())
            assert actual_keys == expected_keys, f"Template keys mismatch: got {actual_keys}, expected {expected_keys}"

            # Type checks
            assert isinstance(template["id"], str)  # Template identifier (not a ULID)
            assert isinstance(template["ulid"], str)  # Backwards compat alias for id
            assert isinstance(template["name"], str)
            assert template["description"] is None or isinstance(template["description"], str)
            
            # step_sequence must be a list (not tuple), and all elements must be strings
            step_seq = template["step_sequence"]
            assert isinstance(step_seq, list), f"step_sequence must be list, got {type(step_seq)}"
            assert all(isinstance(step, str) for step in step_seq), "All step_sequence elements must be strings"
    
    def test_detect_workflow_schema(self, tmp_path):
        """Test detect_workflow handler returns correct schema (JSON-serializable, no unexpected keys)."""
        stdin = StringIO("")
        stdout = StringIO()
        daemon = QVDaemon(stdin=stdin, stdout=stdout)
        
        # Create a minimal calculation directory structure
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir()
        (calc_dir / "calculation.yaml").write_text("steps: []\n")
        
        response = daemon.handle_request(RPCRequest(
            id="1",
            type="detect_workflow",
            payload={"calculation_path": str(calc_dir)},
        ))
        
        assert response.ok
        assert "match" in response.data
        
        # Verify response is JSON-serializable
        json_str = json.dumps(response.data)
        assert isinstance(json_str, str)
        
        # Verify expected structure (match dict with known keys)
        match = response.data["match"]
        assert isinstance(match, dict)
        
        # Expected keys from handler (no extras from asdict() if used)
        expected_match_keys = {
            "workflow_id", "workflow_name", "coverage", "present_steps",
            "missing_steps", "extra_steps", "ordering_valid"
        }
        actual_match_keys = set(match.keys())
        assert actual_match_keys == expected_match_keys, \
            f"Match keys mismatch: got {actual_match_keys}, expected {expected_match_keys}"
    
    def test_detect_workflow_for_calculation_schema(self, tmp_path):
        """Test detect_workflow_for_calculation handler returns correct schema (JSON-serializable, no unexpected keys)."""
        stdin = StringIO("")
        stdout = StringIO()
        daemon = QVDaemon(stdin=stdin, stdout=stdout)
        
        # Create minimal project structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "project.qv.yml").write_text("name: test\n")
        
        # This handler may return error if calculation not found, but schema should still be valid
        response = daemon.handle_request(RPCRequest(
            id="1",
            type="detect_workflow_for_calculation",
            payload={
                "project_root": str(project_dir),
                "calculation_ulid": "01ARZ3NDEKTSV4RRFFQ69G5FAV",  # Valid ULID format
            },
        ))
        
        # Response may be ok or error, but must be JSON-serializable
        json_str = json.dumps(response.data)
        assert isinstance(json_str, str)
        
        # If ok, verify expected structure
        if response.ok:
            # Expected top-level keys from handler
            expected_keys = {
                "workflow_id", "workflow_name", "coverage", "missing_step_types", "issues"
            }
            actual_keys = set(response.data.keys())
            # Allow extra keys only if they're explicitly documented (none expected)
            unexpected = actual_keys - expected_keys
            assert not unexpected, \
                f"Unexpected keys in response: {unexpected}. Response: {response.data}"
    
    def test_instantiate_workflow_schema(self, tmp_path):
        """Test instantiate_workflow handler returns correct schema (JSON-serializable, no unexpected keys)."""
        stdin = StringIO("")
        stdout = StringIO()
        daemon = QVDaemon(stdin=stdin, stdout=stdout)
        
        # Create minimal calculation directory
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir()
        (calc_dir / "calculation.yaml").write_text("steps: []\n")
        
        # This handler may fail if workflow_id is invalid, but schema should still be valid
        response = daemon.handle_request(RPCRequest(
            id="1",
            type="instantiate_workflow",
            payload={
                "workflow_id": "scf",  # Valid workflow ID
                "calculation_path": str(calc_dir),
                "structure_ulid": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "calculation_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
            },
        ))
        
        # Response must be JSON-serializable
        json_str = json.dumps(response.data)
        assert isinstance(json_str, str)
        
        # If ok, verify expected structure
        if response.ok:
            # Expected top-level keys from handler
            expected_keys = {"step_paths"}
            actual_keys = set(response.data.keys())
            unexpected = actual_keys - expected_keys
            assert not unexpected, \
                f"Unexpected keys in response: {unexpected}. Response: {response.data}"
            
            # Verify step_paths is a list of strings
            step_paths = response.data["step_paths"]
            assert isinstance(step_paths, list)
            assert all(isinstance(p, str) for p in step_paths)


class TestQVDaemonMainLoop:
    """Tests for QVDaemon main loop behavior."""
    
    def test_processes_multiple_requests(self):
        """Test that daemon processes multiple requests."""
        requests = [
            '{"ulid": "1", "type": "ping", "payload": {}}',
            '{"ulid": "2", "type": "ping", "payload": {}}',
        ]
        stdin = StringIO("\n".join(requests) + "\n")
        stdout = StringIO()
        
        daemon = QVDaemon(stdin=stdin, stdout=stdout, stderr=StringIO())
        daemon.run()
        
        # Check output
        stdout.seek(0)
        lines = stdout.read().strip().split("\n")
        
        assert len(lines) == 2
        
        for line in lines:
            response = json.loads(line)
            assert response["ok"] is True
            assert response["data"]["pong"] is True
    
    def test_shutdown_command_stops_loop(self):
        """Test that shutdown command stops the main loop."""
        requests = [
            '{"ulid": "1", "type": "ping", "payload": {}}',
            '{"ulid": "2", "type": "shutdown", "payload": {}}',
            '{"ulid": "3", "type": "ping", "payload": {}}',  # Should not be processed
        ]
        stdin = StringIO("\n".join(requests) + "\n")
        stdout = StringIO()
        
        daemon = QVDaemon(stdin=stdin, stdout=stdout, stderr=StringIO())
        daemon.run()
        
        stdout.seek(0)
        lines = stdout.read().strip().split("\n")
        
        # Should have processed ping and shutdown, but not the third ping
        assert len(lines) == 2


class TestQVDaemonLogging:
    """Tests for QVDaemon logging behavior."""
    
    def test_polling_rpc_logs_at_debug(self):
        """Test that polling RPC endpoints (job_counts, list_jobs) log at DEBUG level."""
        stdin = StringIO("")
        stdout = StringIO()
        stderr = StringIO()
        
        daemon = QVDaemon(stdin=stdin, stdout=stdout, stderr=stderr)
        
        # Test job_counts
        response = daemon.handle_request(RPCRequest(
            id="test-1",
            type="job_counts",
            payload={},
        ))
        
        assert response.ok
        
        # Check stderr output
        stderr.seek(0)
        stderr_content = stderr.read()
        
        # Should contain DEBUG level log for job_counts
        # Note: Now includes [polling] tag for filtering
        assert "[DEBUG]" in stderr_content
        assert "[RPC]" in stderr_content
        assert "[polling]" in stderr_content or "job_counts" in stderr_content
        assert "took" in stderr_content
    
    def test_non_polling_rpc_logs_at_info(self):
        """Test that non-polling RPC endpoints log at INFO level."""
        stdin = StringIO("")
        stdout = StringIO()
        stderr = StringIO()
        
        daemon = QVDaemon(stdin=stdin, stdout=stdout, stderr=stderr)
        
        # Test ping (non-polling endpoint)
        response = daemon.handle_request(RPCRequest(
            id="test-1",
            type="ping",
            payload={},
        ))
        
        assert response.ok
        
        # Check stderr output
        stderr.seek(0)
        stderr_content = stderr.read()
        
        # Should contain INFO level log for ping
        assert "[INFO]" in stderr_content
        assert "[RPC] ping" in stderr_content
        assert "took" in stderr_content
        # Should NOT contain DEBUG
        assert "[DEBUG]" not in stderr_content
    
    def test_list_jobs_logs_at_debug(self):
        """Test that list_jobs (polling endpoint) logs at DEBUG level."""
        stdin = StringIO("")
        stdout = StringIO()
        stderr = StringIO()
        
        daemon = QVDaemon(stdin=stdin, stdout=stdout, stderr=stderr)
        
        # Test list_jobs
        response = daemon.handle_request(RPCRequest(
            id="test-1",
            type="list_jobs",
            payload={},
        ))
        
        assert response.ok
        
        # Check stderr output
        stderr.seek(0)
        stderr_content = stderr.read()
        
        # Should contain DEBUG level log for list_jobs
        # Note: Now includes [polling] tag for filtering
        assert "[DEBUG]" in stderr_content
        assert "[RPC]" in stderr_content
        assert "[polling]" in stderr_content or "list_jobs" in stderr_content
        assert "took" in stderr_content
    
    def test_set_log_level_to_debug(self):
        """Test that set_log_level changes log level and affects subsequent RPC logs."""
        stdin = StringIO("")
        stdout = StringIO()
        stderr = StringIO()
        
        daemon = QVDaemon(stdin=stdin, stdout=stdout, stderr=stderr)
        
        # First, verify default behavior (non-polling RPC logs at INFO)
        response1 = daemon.handle_request(RPCRequest(
            id="test-1",
            type="ping",
            payload={},
        ))
        assert response1.ok
        
        stderr.seek(0)
        stderr_content_before = stderr.read()
        assert "[INFO]" in stderr_content_before
        assert "[DEBUG]" not in stderr_content_before
        
        # Set log level to DEBUG
        response2 = daemon.handle_request(RPCRequest(
            id="test-2",
            type="set_log_level",
            payload={"level": "DEBUG"},
        ))
        assert response2.ok
        assert response2.data["level"] == "DEBUG"
        
        # Clear stderr for next check
        stderr.seek(0)
        stderr.truncate(0)
        
        # Now non-polling RPC should also log at DEBUG
        response3 = daemon.handle_request(RPCRequest(
            id="test-3",
            type="ping",
            payload={},
        ))
        assert response3.ok
        
        stderr.seek(0)
        stderr_content_after = stderr.read()
        # Should now contain DEBUG
        assert "[DEBUG]" in stderr_content_after
        assert "[RPC] ping" in stderr_content_after
    
    def test_set_log_level_to_info(self):
        """Test that set_log_level can switch back to INFO."""
        stdin = StringIO("")
        stdout = StringIO()
        stderr = StringIO()
        
        daemon = QVDaemon(stdin=stdin, stdout=stdout, stderr=stderr)
        
        # Set to DEBUG first
        response1 = daemon.handle_request(RPCRequest(
            id="test-1",
            type="set_log_level",
            payload={"level": "DEBUG"},
        ))
        assert response1.ok
        
        # Clear stderr
        stderr.seek(0)
        stderr.truncate(0)
        
        # Set back to INFO
        response2 = daemon.handle_request(RPCRequest(
            id="test-2",
            type="set_log_level",
            payload={"level": "INFO"},
        ))
        assert response2.ok
        assert response2.data["level"] == "INFO"
        
        # Clear stderr
        stderr.seek(0)
        stderr.truncate(0)
        
        # Non-polling RPC should log at INFO again
        response3 = daemon.handle_request(RPCRequest(
            id="test-3",
            type="ping",
            payload={},
        ))
        assert response3.ok
        
        stderr.seek(0)
        stderr_content = stderr.read()
        # Should contain INFO, not DEBUG (for non-polling)
        assert "[INFO]" in stderr_content
        assert "[RPC] ping" in stderr_content
    
    def test_set_log_level_invalid_level(self):
        """Test that set_log_level rejects invalid levels."""
        stdin = StringIO("")
        stdout = StringIO()
        stderr = StringIO()
        
        daemon = QVDaemon(stdin=stdin, stdout=stdout, stderr=stderr)
        
        response = daemon.handle_request(RPCRequest(
            id="test-1",
            type="set_log_level",
            payload={"level": "INVALID"},
        ))
        
        assert not response.ok
        assert response.error["code"] == "invalid_argument"
        assert "Invalid log level" in response.error["message"]
    
    def test_rpc_log_level_for_helper(self):
        """Test the _rpc_log_level_for helper method."""
        stdin = StringIO("")
        stdout = StringIO()
        
        daemon = QVDaemon(stdin=stdin, stdout=stdout)
        
        # Default: polling endpoints return DEBUG, others return INFO
        assert daemon._rpc_log_level_for("job_counts") == "DEBUG"
        assert daemon._rpc_log_level_for("list_jobs") == "DEBUG"
        assert daemon._rpc_log_level_for("ping") == "INFO"
        assert daemon._rpc_log_level_for("get_env_info") == "INFO"
        
        # When global level is DEBUG, all return DEBUG
        daemon._rpc_log_level = "DEBUG"
        assert daemon._rpc_log_level_for("job_counts") == "DEBUG"
        assert daemon._rpc_log_level_for("list_jobs") == "DEBUG"
        assert daemon._rpc_log_level_for("ping") == "DEBUG"
        assert daemon._rpc_log_level_for("get_env_info") == "DEBUG"
        
        # When global level is INFO, polling returns DEBUG, others return INFO
        daemon._rpc_log_level = "INFO"
        assert daemon._rpc_log_level_for("job_counts") == "DEBUG"
        assert daemon._rpc_log_level_for("list_jobs") == "DEBUG"
        assert daemon._rpc_log_level_for("ping") == "INFO"
        assert daemon._rpc_log_level_for("get_env_info") == "INFO"

