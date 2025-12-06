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
            
            # Environment and settings
            "detect_qe": self._handle_detect_qe,
            "get_env_info": self._handle_get_env_info,
            
            # Project/resource listing
            "get_project_summary": self._handle_get_project_summary,
            "list_structures": self._handle_list_structures,
            "list_workflows": self._handle_list_workflows,
            
            # Project creation and management
            "create_project": self._handle_create_project,
            "import_structure": self._handle_import_structure,
            
            # Structure management
            "rename_structure": self._handle_rename_structure,
            "delete_structure": self._handle_delete_structure,
            "can_delete_structure": self._handle_can_delete_structure,
            
            # Workflow creation and management
            "list_workflow_templates": self._handle_list_workflow_templates,
            "create_workflow": self._handle_create_workflow,
            "rename_workflow": self._handle_rename_workflow,
            "delete_workflow": self._handle_delete_workflow,
            "can_delete_workflow": self._handle_can_delete_workflow,
            
            # Step operations
            "get_step_detail": self._handle_get_step_detail,
            "update_step_params": self._handle_update_step_params,
            "reset_step_params": self._handle_reset_step_params,
            
            # Workflow configuration
            "get_workflow_detail": self._handle_get_workflow_detail,
            "reorder_workflow_steps": self._handle_reorder_workflow_steps,
            "change_workflow_structure": self._handle_change_workflow_structure,
            
            # Pre-flight checks
            "preflight_check": self._handle_preflight_check,
            
            # Demo project
            "create_demo_project": self._handle_create_demo_project,
            
            # Visualization data (pure data, no matplotlib)
            "get_structure_vis": self._handle_get_structure_vis,
            "get_scf_convergence": self._handle_get_scf_convergence,
            "get_dos_data": self._handle_get_dos_data,
            "get_band_structure_data": self._handle_get_band_structure_data,
            
            # Job management
            "run_workflow": self._handle_run_workflow,
            "run_step": self._handle_run_step,
            "get_job_status": self._handle_get_job_status,
            "get_job_logs": self._handle_get_job_logs,
            "list_jobs": self._handle_list_jobs,
            "job_counts": self._handle_job_counts,
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
    # Environment and settings handlers
    # -------------------------------------------------------------------------
    
    def _handle_detect_qe(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect QE installation.
        
        Payload: (none required)
        
        Returns detection status, qe_home, version, executables
        """
        return QVService.detect_qe()
    
    def _handle_get_env_info(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get environment info.
        
        Payload: (none required)
        
        Returns python_version, qv_version, qe_home, etc.
        """
        return QVService.get_environment_info()
    
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
    # Project creation handlers
    # -------------------------------------------------------------------------
    
    def _handle_create_project(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new project.
        
        Payload:
            target_dir: str - Directory to create project in
            name: str - Optional project name (defaults to dir name)
            template: str - Optional template name
        """
        target_dir = Path(payload.get("target_dir", "")).resolve()
        name = payload.get("name")
        template = payload.get("template")
        
        if not target_dir:
            raise ValueError("Missing required field: target_dir")
        
        project_root = QVService.init_project(
            target_dir=target_dir,
            name=name,
            template=template,
        )
        
        # Get summary of newly created project
        summary = QVService.get_project_summary(project_root)
        
        return {
            "project_root": str(project_root),
            "name": summary.get("name", name or target_dir.name),
            "id": summary.get("id"),
        }
    
    def _handle_import_structure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Import a structure file into a project.
        
        Payload:
            project_root: str - Path to project root
            source_file: str - Path to structure file
            name: str - Optional structure name
        """
        project_root = self._require_path(payload, "project_root")
        source_file = Path(payload.get("source_file", "")).resolve()
        name = payload.get("name")
        
        if not source_file or not source_file.exists():
            raise FileNotFoundError(f"Structure file not found: {source_file}")
        
        result = QVService.import_structure(
            project_root=project_root,
            source=source_file,
            name=name,
        )
        
        # Get structure metadata
        structures = QVService.list_structures_data(project_root)
        new_struct = next((s for s in structures if s.get("id") == result.meta.id), None)
        
        return {
            "structure_id": result.meta.id,
            "name": result.meta.name,
            "slug": result.meta.slug,
            "formula": new_struct.get("formula", "?") if new_struct else "?",
            "n_atoms": new_struct.get("n_atoms", 0) if new_struct else 0,
        }
    
    # -------------------------------------------------------------------------
    # Structure management handlers
    # -------------------------------------------------------------------------
    
    def _handle_rename_structure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rename a structure.
        
        Payload:
            project_root: str - Path to project root
            selector: str - Structure selector
            new_name: str - New name
        """
        project_root = self._require_path(payload, "project_root")
        selector = self._require_str(payload, "selector")
        new_name = self._require_str(payload, "new_name")
        
        return QVService.rename_structure(
            project_root=project_root,
            selector=selector,
            new_name=new_name,
        )
    
    def _handle_can_delete_structure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if structure can be deleted.
        
        Payload:
            project_root: str - Path to project root
            selector: str - Structure selector
        """
        project_root = self._require_path(payload, "project_root")
        selector = self._require_str(payload, "selector")
        
        return QVService.can_delete_structure(
            project_root=project_root,
            selector=selector,
        )
    
    def _handle_delete_structure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete a structure.
        
        Payload:
            project_root: str - Path to project root
            selector: str - Structure selector
            force: bool - Force delete even if used by workflows
        """
        project_root = self._require_path(payload, "project_root")
        selector = self._require_str(payload, "selector")
        force = payload.get("force", False)
        
        # Get structure name before deletion for response
        check = QVService.can_delete_structure(project_root, selector)
        structure_name = check.get("structure_name", selector)
        
        QVService.delete_structure(
            project_root=project_root,
            selector=selector,
            force=force,
        )
        
        return {
            "success": True,
            "name": structure_name,
        }
    
    # -------------------------------------------------------------------------
    # Workflow creation handlers
    # -------------------------------------------------------------------------
    
    def _handle_list_workflow_templates(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List available workflow templates.
        """
        from quantumvitas.core.templates import list_workflow_templates
        
        templates = list_workflow_templates()
        
        return {
            "templates": [
                {
                    "name": t.get("name"),
                    "path": t.get("path"),
                    "description": t.get("description"),
                    "n_steps": t.get("n_steps", 0),
                    "step_types": t.get("step_types", []),
                }
                for t in templates
            ],
            "count": len(templates),
        }
    
    def _handle_create_workflow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new workflow.
        
        Payload:
            project_root: str - Path to project root
            name: str - Workflow name
            structure: str - Optional structure selector
            template: str - Optional template name
        """
        project_root = self._require_path(payload, "project_root")
        name = self._require_str(payload, "name")
        structure = payload.get("structure")
        template = payload.get("template")
        
        result = QVService.init_workflow(
            project_root=project_root,
            name=name,
            structure_selector=structure,
            template=template,
        )
        
        # Get workflow details
        workflows = QVService.list_workflows_data(project_root)
        new_wf = next((w for w in workflows if w.get("id") == result.meta.id), None)
        
        return {
            "workflow_id": result.meta.id,
            "name": result.meta.name,
            "slug": result.meta.slug,
            "n_steps": new_wf.get("n_steps", 0) if new_wf else 0,
        }
    
    # -------------------------------------------------------------------------
    # Workflow management handlers
    # -------------------------------------------------------------------------
    
    def _handle_rename_workflow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rename a workflow.
        
        Payload:
            project_root: str - Path to project root
            selector: str - Workflow selector
            new_name: str - New name
        """
        project_root = self._require_path(payload, "project_root")
        selector = self._require_str(payload, "selector")
        new_name = self._require_str(payload, "new_name")
        
        return QVService.rename_workflow(
            project_root=project_root,
            selector=selector,
            new_name=new_name,
        )
    
    def _handle_can_delete_workflow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if workflow can be deleted.
        
        Payload:
            project_root: str - Path to project root
            selector: str - Workflow selector
        """
        project_root = self._require_path(payload, "project_root")
        selector = self._require_str(payload, "selector")
        
        return QVService.can_delete_workflow(
            project_root=project_root,
            selector=selector,
        )
    
    def _handle_delete_workflow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete a workflow.
        
        Payload:
            project_root: str - Path to project root
            selector: str - Workflow selector
            force: bool - Force delete
        """
        project_root = self._require_path(payload, "project_root")
        selector = self._require_str(payload, "selector")
        force = payload.get("force", False)
        
        # Get workflow name before deletion for response
        check = QVService.can_delete_workflow(project_root, selector)
        workflow_name = check.get("workflow_name", selector)
        
        QVService.delete_workflow(
            project_root=project_root,
            selector=selector,
            force=force,
        )
        
        return {
            "success": True,
            "name": workflow_name,
        }
    
    # -------------------------------------------------------------------------
    # Step handlers
    # -------------------------------------------------------------------------
    
    def _handle_get_step_detail(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get step detail.
        
        Payload:
            project_root: str - Path to project root
            workflow: str - Workflow selector
            step: str - Step selector
        """
        project_root = self._require_path(payload, "project_root")
        workflow = self._require_str(payload, "workflow")
        step = self._require_str(payload, "step")
        
        return QVService.get_step_detail(
            project_root=project_root,
            workflow_selector=workflow,
            step_selector=step,
        )
    
    def _handle_update_step_params(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update step parameters.
        
        Payload:
            project_root: str - Path to project root
            workflow: str - Workflow selector
            step: str - Step selector
            parameters: Dict[str, Dict[str, Any]] - Namelist parameters to update
            cards: Optional[Dict] - Card data to update
        """
        project_root = self._require_path(payload, "project_root")
        workflow = self._require_str(payload, "workflow")
        step = self._require_str(payload, "step")
        parameters = payload.get("parameters", {})
        cards = payload.get("cards")
        
        return QVService.update_step_params(
            project_root=project_root,
            workflow_selector=workflow,
            step_selector=step,
            parameters=parameters,
            cards=cards,
        )
    
    def _handle_reset_step_params(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reset step parameters to defaults.
        
        Payload:
            project_root: str - Path to project root
            workflow: str - Workflow selector
            step: str - Step selector
            template_name: Optional[str] - Template to reset from
        """
        project_root = self._require_path(payload, "project_root")
        workflow = self._require_str(payload, "workflow")
        step = self._require_str(payload, "step")
        template_name = payload.get("template_name")
        
        return QVService.reset_step_params(
            project_root=project_root,
            workflow_selector=workflow,
            step_selector=step,
            template_name=template_name,
        )
    
    # -------------------------------------------------------------------------
    # Workflow configuration handlers
    # -------------------------------------------------------------------------
    
    def _handle_get_workflow_detail(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get detailed workflow information.
        
        Payload:
            project_root: str - Path to project root
            workflow: str - Workflow selector
        """
        project_root = self._require_path(payload, "project_root")
        workflow = self._require_str(payload, "workflow")
        
        return QVService.get_workflow_detail(
            project_root=project_root,
            workflow_selector=workflow,
        )
    
    def _handle_reorder_workflow_steps(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reorder workflow steps.
        
        Payload:
            project_root: str - Path to project root
            workflow: str - Workflow selector
            new_order: List[str] - Step IDs/slugs in new order
        """
        project_root = self._require_path(payload, "project_root")
        workflow = self._require_str(payload, "workflow")
        new_order = payload.get("new_order", [])
        
        if not isinstance(new_order, list):
            raise ValueError("new_order must be a list of step selectors")
        
        return QVService.reorder_workflow_steps(
            project_root=project_root,
            workflow_selector=workflow,
            new_order=new_order,
        )
    
    def _handle_change_workflow_structure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Change workflow structure.
        
        Payload:
            project_root: str - Path to project root
            workflow: str - Workflow selector
            new_structure: str - New structure selector
            update_steps: bool - Whether to update step structure fields (default True)
        """
        project_root = self._require_path(payload, "project_root")
        workflow = self._require_str(payload, "workflow")
        new_structure = self._require_str(payload, "new_structure")
        update_steps = payload.get("update_steps", True)
        
        return QVService.change_workflow_structure(
            project_root=project_root,
            workflow_selector=workflow,
            new_structure=new_structure,
            update_steps=update_steps,
        )
    
    # -------------------------------------------------------------------------
    # Pre-flight check handlers
    # -------------------------------------------------------------------------
    
    def _handle_preflight_check(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform pre-flight checks before running.
        
        Payload:
            project_root: str - Path to project root
            workflow: Optional[str] - Workflow selector
            step: Optional[str] - Step selector
        """
        project_root = self._require_path(payload, "project_root")
        workflow = payload.get("workflow")
        step = payload.get("step")
        
        return QVService.preflight_check(
            project_root=project_root,
            workflow_selector=workflow,
            step_selector=step,
        )
    
    # -------------------------------------------------------------------------
    # Demo project handlers
    # -------------------------------------------------------------------------
    
    def _handle_create_demo_project(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a demo Si project.
        
        Payload:
            target_dir: str - Directory to create project in
            name: Optional[str] - Project name (default 'demo-si-project')
        """
        target_dir = self._require_path(payload, "target_dir")
        name = payload.get("name", "demo-si-project")
        
        return QVService.create_demo_project(
            target_dir=target_dir,
            name=name,
        )
    
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
            status: str - Initial status ("pending")
            target_name: str - Workflow name for display
        """
        project_root = self._require_path(payload, "project_root")
        workflow = self._require_str(payload, "workflow")
        strict = payload.get("strict", False)
        verbose = payload.get("verbose", False)
        
        # Submit job with target info for display
        job_id = self.job_manager.submit(
            job_type="run_workflow",
            func=QVService.run_workflow,
            params={
                "project_root": str(project_root),
                "workflow": workflow,
                "strict": strict,
            },
            target_name=workflow,
            project_root_display=str(project_root),
            # kwargs for QVService.run_workflow
            project_root=project_root,
            workflow_selector=workflow,
            strict=strict,
            verbose=verbose,
        )
        
        return {"job_id": job_id, "status": "pending", "target_name": workflow}
    
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
            status: str - Initial status ("pending")
            target_name: str - Step name for display
        """
        project_root = self._require_path(payload, "project_root")
        workflow = self._require_str(payload, "workflow")
        step = self._require_str(payload, "step")
        verbose = payload.get("verbose", False)
        
        target_name = f"{workflow}/{step}"
        
        # Submit job with target info for display
        job_id = self.job_manager.submit(
            job_type="run_step",
            func=QVService.run_step,
            params={
                "project_root": str(project_root),
                "workflow": workflow,
                "step": step,
            },
            target_name=target_name,
            project_root_display=str(project_root),
            # kwargs for QVService.run_step
            project_root=project_root,
            workflow_selector=workflow,
            step_selector=step,
            verbose=verbose,
        )
        
        return {"job_id": job_id, "status": "pending", "target_name": target_name}
    
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
    
    def _handle_get_job_logs(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get logs for a job.
        
        Payload:
            job_id: str - Job ID
            tail_lines: int - Number of lines to return (default 100)
            offset: int - Line offset (default 0, meaning tail from end)
        """
        job_id = self._require_str(payload, "job_id")
        tail_lines = payload.get("tail_lines", 100)
        offset = payload.get("offset", 0)
        
        result = self.job_manager.get_job_logs(job_id, tail_lines=tail_lines, offset=offset)
        if result is None:
            raise ValueError(f"Job not found: {job_id}")
        
        return result
    
    def _handle_list_jobs(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List jobs.
        
        Payload:
            status: str - Optional status filter
            job_type: str - Optional job type filter
            project_root: str - Optional project filter
            limit: int - Maximum jobs to return (default 50)
        """
        status_str = payload.get("status")
        status = JobStatus(status_str) if status_str else None
        job_type = payload.get("job_type")
        project_root = payload.get("project_root")
        limit = payload.get("limit", 50)
        
        jobs = self.job_manager.list_jobs(
            status=status,
            job_type=job_type,
            project_root=project_root,
            limit=limit,
        )
        return {"jobs": jobs, "count": len(jobs)}
    
    def _handle_job_counts(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get job counts by status.
        
        Payload: (none required)
        
        Returns:
            counts: dict - {status: count} for each status
            running: int - Number of running jobs
            pending: int - Number of pending jobs
        """
        counts = self.job_manager.count_by_status()
        return {
            "counts": counts,
            "running": counts.get("running", 0),
            "pending": counts.get("pending", 0),
        }
    
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

