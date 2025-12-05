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
        
        assert "id" in job_dict
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
        
        response = daemon.handle_line('{"id": "1", "payload": {}}')
        
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
        
        assert parsed["id"] == "test-1"
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
        
        assert parsed["id"] == "test-1"
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
    
    def test_list_workflows_handler(self, tmp_path):
        """Test list_workflows handler."""
        from quantumvitas.api import QVService
        
        project_root = QVService.init_project(tmp_path / "test_proj")
        QVService.init_workflow(project_root, "wf1")
        
        stdin = StringIO("")
        stdout = StringIO()
        daemon = QVDaemon(stdin=stdin, stdout=stdout)
        
        response = daemon.handle_request(RPCRequest(
            id="1",
            type="list_workflows",
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
    
    def test_run_workflow_returns_job_id(self, tmp_path):
        """Test that run_workflow returns a job ID."""
        from quantumvitas.api import QVService
        
        project_root = QVService.init_project(tmp_path / "test_proj")
        QVService.init_workflow(project_root, "test-wf")
        
        stdin = StringIO("")
        stdout = StringIO()
        daemon = QVDaemon(stdin=stdin, stdout=stdout)
        
        response = daemon.handle_request(RPCRequest(
            id="1",
            type="run_workflow",
            payload={
                "project_root": str(project_root),
                "workflow": "test-wf",
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
        QVService.init_workflow(project_root, "test-wf")
        
        stdin = StringIO("")
        stdout = StringIO()
        daemon = QVDaemon(stdin=stdin, stdout=stdout)
        
        # Submit a job
        submit_response = daemon.handle_request(RPCRequest(
            id="1",
            type="run_workflow",
            payload={
                "project_root": str(project_root),
                "workflow": "test-wf",
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
        assert status_response.data["id"] == job_id
        assert status_response.data["job_type"] == "run_workflow"
        
        daemon.job_manager.shutdown()


class TestQVDaemonMainLoop:
    """Tests for QVDaemon main loop behavior."""
    
    def test_processes_multiple_requests(self):
        """Test that daemon processes multiple requests."""
        requests = [
            '{"id": "1", "type": "ping", "payload": {}}',
            '{"id": "2", "type": "ping", "payload": {}}',
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
            '{"id": "1", "type": "ping", "payload": {}}',
            '{"id": "2", "type": "shutdown", "payload": {}}',
            '{"id": "3", "type": "ping", "payload": {}}',  # Should not be processed
        ]
        stdin = StringIO("\n".join(requests) + "\n")
        stdout = StringIO()
        
        daemon = QVDaemon(stdin=stdin, stdout=stdout, stderr=StringIO())
        daemon.run()
        
        stdout.seek(0)
        lines = stdout.read().strip().split("\n")
        
        # Should have processed ping and shutdown, but not the third ping
        assert len(lines) == 2

