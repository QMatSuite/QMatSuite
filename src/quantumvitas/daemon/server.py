"""
QuantumVITAS JSON-RPC Daemon Server.

Provides a stdio-based JSON-RPC interface for GUI integration.
- Reads JSON requests from stdin (one per line)
- Writes JSON responses to stdout (one per line)
- Calls QVService for all operations (never CLI)
- Uses JobManager for long-running QE operations

Protocol:
    Request:  {"id": "req1", "type": "command_name", "payload": {...}}
    Response: {"id": "req1", "ok": true, "data": {...}}
              {"id": "req1", "ok": false, "error": {"code": "...", "message": "..."}}

The daemon itself never touches cwd; all paths come from request payloads.
"""

from __future__ import annotations

import json
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TextIO

from quantumvitas.api import QVService, QVServiceError
from quantumvitas.daemon.jobs import JobManager, JobStatus


@dataclass
class RPCRequest:
    """Parsed JSON-RPC request."""
    id: str
    type: str
    payload: Dict[str, Any]


@dataclass
class RPCResponse:
    """JSON-RPC response."""
    id: str
    ok: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        result = {"id": self.id, "ok": self.ok}
        if self.ok:
            result["data"] = self.data or {}
        else:
            result["error"] = self.error or {"code": "unknown", "message": "Unknown error"}
        return json.dumps(result)


class QVDaemon:
    """
    QuantumVITAS JSON-RPC Daemon.
    
    Handles stdio communication with a GUI client (e.g., Electron).
    All operations go through QVService, never CLI commands.
    Long-running QE operations are handled via JobManager.
    
    Usage:
        daemon = QVDaemon()
        daemon.run()  # Blocks, reading from stdin
    
    Or for testing:
        daemon = QVDaemon(stdin=my_input, stdout=my_output)
        daemon.handle_request({"id": "1", "type": "ping", "payload": {}})
    """
    
    def __init__(
        self,
        stdin: TextIO = sys.stdin,
        stdout: TextIO = sys.stdout,
        stderr: TextIO = sys.stderr,
    ):
        """
        Initialize the daemon.
        
        Args:
            stdin: Input stream (default sys.stdin)
            stdout: Output stream (default sys.stdout)
            stderr: Error stream for logging (default sys.stderr)
        """
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.job_manager = JobManager(max_workers=1)
        self._running = False
        
        # Command dispatcher
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            # System commands
            "ping": self._handle_ping,
            "shutdown": self._handle_shutdown,
            
            # Project/resource listing
            "get_project_summary": self._handle_get_project_summary,
            "list_structures": self._handle_list_structures,
            "list_workflows": self._handle_list_workflows,
            
            # Visualization data (pure data, no matplotlib)
            "get_structure_vis": self._handle_get_structure_vis,
            "get_scf_convergence": self._handle_get_scf_convergence,
            "get_dos_data": self._handle_get_dos_data,
            "get_band_structure_data": self._handle_get_band_structure_data,
            
            # Job management
            "run_workflow": self._handle_run_workflow,
            "run_step": self._handle_run_step,
            "get_job_status": self._handle_get_job_status,
            "list_jobs": self._handle_list_jobs,
            "cancel_job": self._handle_cancel_job,
        }
    
    def log(self, message: str):
        """Write log message to stderr."""
        self.stderr.write(f"[qv-daemon] {message}\n")
        self.stderr.flush()
    
    def run(self):
        """
        Run the daemon main loop.
        
        Reads JSON requests from stdin, processes them, and writes responses to stdout.
        Each line is a separate request/response.
        
        Blocks until stdin is closed or 'shutdown' command is received.
        """
        self._running = True
        self.log("Daemon started, waiting for requests...")
        
        try:
            while self._running:
                try:
                    line = self.stdin.readline()
                    if not line:
                        # EOF - stdin closed
                        break
                    
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Parse and handle request
                    response = self.handle_line(line)
                    
                    # Write response
                    self.stdout.write(response.to_json() + "\n")
                    self.stdout.flush()
                    
                except KeyboardInterrupt:
                    self.log("Interrupted, shutting down...")
                    break
                    
        finally:
            self._running = False
            self.job_manager.shutdown(wait=True)
            self.log("Daemon stopped")
    
    def handle_line(self, line: str) -> RPCResponse:
        """
        Handle a single JSON request line.
        
        Args:
            line: JSON request string
            
        Returns:
            RPCResponse object
        """
        request_id = "unknown"
        
        try:
            # Parse JSON
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                return RPCResponse(
                    id=request_id,
                    ok=False,
                    error={"code": "parse_error", "message": f"Invalid JSON: {e}"},
                )
            
            # Extract request fields
            request_id = data.get("id", "unknown")
            request_type = data.get("type")
            payload = data.get("payload", {})
            
            if not request_type:
                return RPCResponse(
                    id=request_id,
                    ok=False,
                    error={"code": "invalid_request", "message": "Missing 'type' field"},
                )
            
            # Create request object
            request = RPCRequest(id=request_id, type=request_type, payload=payload)
            
            # Handle request
            return self.handle_request(request)
            
        except Exception as e:
            self.log(f"Unexpected error: {e}\n{traceback.format_exc()}")
            return RPCResponse(
                id=request_id,
                ok=False,
                error={"code": "internal_error", "message": str(e)},
            )
    
    def handle_request(self, request: RPCRequest) -> RPCResponse:
        """
        Handle a parsed request.
        
        Args:
            request: Parsed RPCRequest
            
        Returns:
            RPCResponse object
        """
        handler = self._handlers.get(request.type)
        
        if handler is None:
            return RPCResponse(
                id=request.id,
                ok=False,
                error={
                    "code": "unknown_command",
                    "message": f"Unknown command: {request.type}",
                    "available_commands": list(self._handlers.keys()),
                },
            )
        
        try:
            result = handler(request.payload)
            return RPCResponse(id=request.id, ok=True, data=result)
            
        except QVServiceError as e:
            return RPCResponse(
                id=request.id,
                ok=False,
                error={"code": "service_error", "message": str(e)},
            )
        except FileNotFoundError as e:
            return RPCResponse(
                id=request.id,
                ok=False,
                error={"code": "not_found", "message": str(e)},
            )
        except ValueError as e:
            return RPCResponse(
                id=request.id,
                ok=False,
                error={"code": "invalid_argument", "message": str(e)},
            )
        except Exception as e:
            self.log(f"Handler error for {request.type}: {e}\n{traceback.format_exc()}")
            return RPCResponse(
                id=request.id,
                ok=False,
                error={"code": "handler_error", "message": str(e)},
            )
    
    # -------------------------------------------------------------------------
    # System handlers
    # -------------------------------------------------------------------------
    
    def _handle_ping(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping command."""
        return {"pong": True, "version": "2.0.0"}
    
    def _handle_shutdown(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle shutdown command."""
        self._running = False
        return {"shutdown": True}
    
    # -------------------------------------------------------------------------
    # Project/resource handlers
    # -------------------------------------------------------------------------
    
    def _handle_get_project_summary(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get project summary.
        
        Payload:
            project_root: str - Path to project root
        """
        project_root = self._require_path(payload, "project_root")
        return QVService.get_project_summary(project_root)
    
    def _handle_list_structures(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List structures in project.
        
        Payload:
            project_root: str - Path to project root
        """
        project_root = self._require_path(payload, "project_root")
        structures = QVService.list_structures_data(project_root)
        return {"structures": structures, "count": len(structures)}
    
    def _handle_list_workflows(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List workflows in project.
        
        Payload:
            project_root: str - Path to project root
        """
        project_root = self._require_path(payload, "project_root")
        workflows = QVService.list_workflows_data(project_root)
        return {"workflows": workflows, "count": len(workflows)}
    
    # -------------------------------------------------------------------------
    # Visualization data handlers
    # -------------------------------------------------------------------------
    
    def _handle_get_structure_vis(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get structure visualization data.
        
        Payload:
            project_root: str - Path to project root
            selector: str - Structure selector
            supercell: [int, int, int] - Optional supercell (default [1,1,1])
            repeat_boundary: bool - Optional (default false)
        """
        project_root = self._require_path(payload, "project_root")
        selector = self._require_str(payload, "selector")
        supercell = tuple(payload.get("supercell", [1, 1, 1]))
        repeat_boundary = payload.get("repeat_boundary", False)
        
        return QVService.get_structure_vis_data(
            project_root=project_root,
            selector=selector,
            supercell=supercell,
            repeat_boundary=repeat_boundary,
        )
    
    def _handle_get_scf_convergence(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get SCF convergence data.
        
        Payload:
            project_root: str - Path to project root
            workflow: str - Workflow selector
            step: str - Step selector
        """
        project_root = self._require_path(payload, "project_root")
        workflow = self._require_str(payload, "workflow")
        step = self._require_str(payload, "step")
        
        return QVService.get_scf_convergence_data(
            project_root=project_root,
            workflow_selector=workflow,
            step_selector=step,
        )
    
    def _handle_get_dos_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get DOS data for plotting.
        
        Payload:
            project_root: str - Path to project root
            workflow: str - Workflow selector
            step: str - Optional step selector
        """
        project_root = self._require_path(payload, "project_root")
        workflow = self._require_str(payload, "workflow")
        step = payload.get("step")
        
        return QVService.get_dos_data(
            project_root=project_root,
            workflow_selector=workflow,
            step_selector=step,
        )
    
    def _handle_get_band_structure_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get band structure data for plotting.
        
        Payload:
            project_root: str - Path to project root
            workflow: str - Workflow selector
            step: str - Optional step selector
        """
        project_root = self._require_path(payload, "project_root")
        workflow = self._require_str(payload, "workflow")
        step = payload.get("step")
        
        return QVService.get_band_structure_data(
            project_root=project_root,
            workflow_selector=workflow,
            step_selector=step,
        )
    
    # -------------------------------------------------------------------------
    # Job management handlers
    # -------------------------------------------------------------------------
    
    def _handle_run_workflow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit a workflow run job.
        
        Payload:
            project_root: str - Path to project root
            workflow: str - Workflow selector
            strict: bool - Optional strict mode (default false)
            verbose: bool - Optional verbose mode (default false)
            
        Returns:
            job_id: str - ID of submitted job
        """
        project_root = self._require_path(payload, "project_root")
        workflow = self._require_str(payload, "workflow")
        strict = payload.get("strict", False)
        verbose = payload.get("verbose", False)
        
        # Submit job
        job_id = self.job_manager.submit(
            job_type="run_workflow",
            func=QVService.run_workflow,
            params={
                "project_root": str(project_root),
                "workflow": workflow,
                "strict": strict,
            },
            project_root=project_root,
            workflow_selector=workflow,
            strict=strict,
            verbose=verbose,
        )
        
        return {"job_id": job_id, "status": "pending"}
    
    def _handle_run_step(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit a step run job.
        
        Payload:
            project_root: str - Path to project root
            workflow: str - Workflow selector
            step: str - Step selector
            verbose: bool - Optional verbose mode (default false)
            
        Returns:
            job_id: str - ID of submitted job
        """
        project_root = self._require_path(payload, "project_root")
        workflow = self._require_str(payload, "workflow")
        step = self._require_str(payload, "step")
        verbose = payload.get("verbose", False)
        
        # Submit job
        job_id = self.job_manager.submit(
            job_type="run_step",
            func=QVService.run_step,
            params={
                "project_root": str(project_root),
                "workflow": workflow,
                "step": step,
            },
            project_root=project_root,
            workflow_selector=workflow,
            step_selector=step,
            verbose=verbose,
        )
        
        return {"job_id": job_id, "status": "pending"}
    
    def _handle_get_job_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get status of a job.
        
        Payload:
            job_id: str - Job ID
        """
        job_id = self._require_str(payload, "job_id")
        
        status = self.job_manager.get_job_status(job_id)
        if status is None:
            raise ValueError(f"Job not found: {job_id}")
        
        return status
    
    def _handle_list_jobs(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List jobs.
        
        Payload:
            status: str - Optional status filter
            job_type: str - Optional job type filter
        """
        status_str = payload.get("status")
        status = JobStatus(status_str) if status_str else None
        job_type = payload.get("job_type")
        
        jobs = self.job_manager.list_jobs(status=status, job_type=job_type)
        return {"jobs": jobs, "count": len(jobs)}
    
    def _handle_cancel_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cancel a pending job.
        
        Payload:
            job_id: str - Job ID
        """
        job_id = self._require_str(payload, "job_id")
        
        cancelled = self.job_manager.cancel_job(job_id)
        return {"job_id": job_id, "cancelled": cancelled}
    
    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    
    def _require_path(self, payload: Dict[str, Any], key: str) -> Path:
        """Extract and validate a required path from payload."""
        value = payload.get(key)
        if value is None:
            raise ValueError(f"Missing required field: {key}")
        path = Path(value).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        return path
    
    def _require_str(self, payload: Dict[str, Any], key: str) -> str:
        """Extract a required string from payload."""
        value = payload.get(key)
        if value is None:
            raise ValueError(f"Missing required field: {key}")
        return str(value)


def main():
    """Entry point for qv-daemon command."""
    daemon = QVDaemon()
    daemon.run()


if __name__ == "__main__":
    main()

