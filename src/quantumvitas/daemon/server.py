"""
QuantumVITAS JSON-RPC Daemon Server.

Provides a stdio-based JSON-RPC interface for GUI integration.
- Reads JSON requests from stdin (one per line)
- Writes JSON responses to stdout (one per line)
- Calls QVService for all operations (never CLI)
- Uses JobManager for long-running QE operations

Protocol:
    Request:  {"ulid": "req1", "type": "command_name", "payload": {...}}
    Response: {"ulid": "req1", "ok": true, "data": {...}}
              {"ulid": "req1", "ok": false, "error": {"code": "...", "message": "..."}}

The daemon itself never touches cwd; all paths come from request payloads.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import traceback
import yaml
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TextIO

from quantumvitas.api import QVService, APIError, get_service
from quantumvitas.api.utils import (
    is_ulid_like,
    validate_ulid,
    load_calculation,
    get_pseudo_status_bundle,
    set_pseudo_config,
    get_calculation_preset_bundle,
    download_pseudo_by_filename,
    get_qe_engine_status,
    set_qe_engine,
    resolve_pseudo_provenance,
    download_pseudo_from_url,
    get_journal,
    create_blob_store,
    compute_io_dir_from_calculation_model,
    parse_volume_artifact,
    apply_presets_to_step,
    get_preset_catalog,
    resolve_precision_context,
    generate_unique_name_and_slug,
    meta_from_name,
    list_calculation_templates,
    read_structure,
    find_path_context_from_pwd,
    canonicalize_structure,
    reduce_formula,
    extract_provenance,
    set_settings,
)
from quantumvitas.daemon.jobs import JobManager, JobStatus
from quantumvitas.daemon.compat import adapt_payload, shape_response
from quantumvitas.api.utils import (
    list_supported_modules,
    get_module_param_sections,
    get_module_card_sections,
    get_module_doc_url,
    get_metadata_file_info,
    safe_load_metadata,
    _iter_params,
)


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
        # Note: 'id' here is a request correlation ID, not a resource ULID
        result = {"id": self.id, "ok": self.ok}
        if self.ok:
            result["data"] = self.data or {}
        else:
            result["error"] = self.error or {"code": "unknown", "message": "Unknown error"}
        return json.dumps(result)


@dataclass
class ProjectCache:
    """
    Cache for a project's ResourceIndex and config.
    
    The daemon keeps a long-lived cache per project to avoid rebuilding
    the ResourceIndex on every request. The cache is invalidated when
    mutations occur (rename, delete, import, etc.).
    """
    project_root: Path
    index: Any  # ResourceIndex type - using Any to avoid importing kernel types
    config: dict
    svc: QVService  # QVService instance for this project


@dataclass
class DaemonState:
    """
    State management for the daemon.
    
    Maintains per-project caches of ResourceIndex to avoid rebuilding
    on every request. Caches are invalidated on mutations.
    """
    _caches: Dict[Path, ProjectCache] = field(default_factory=dict)
    
    def get_cache(self, project_root: Path) -> ProjectCache:
        """
        Get or create cache for a project.
        
        Args:
            project_root: Path to project root
            
        Returns:
            ProjectCache for the project
        """
        project_root = project_root.resolve()
        if project_root not in self._caches:
            # Build fresh cache using get_service() (canonical API pattern)
            svc = get_service(project_root)
            config = svc.project.get_config()
            index = svc.project.build_resource_index()
            self._caches[project_root] = ProjectCache(
                project_root=project_root,
                index=index,
                config=config,
                svc=svc,
            )
        return self._caches[project_root]
    
    def rebuild_cache(self, project_root: Path) -> ProjectCache:
        """
        Rebuild cache for a project (force refresh).
        
        Args:
            project_root: Path to project root
            
        Returns:
            Fresh ProjectCache for the project
        """
        project_root = project_root.resolve()
        svc = get_service(project_root)
        config = svc.project.get_config()
        index = svc.project.build_resource_index()
        self._caches[project_root] = ProjectCache(
            project_root=project_root,
            index=index,
            config=config,
            svc=svc,
        )
        return self._caches[project_root]
    
    def invalidate_cache(self, project_root: Path) -> None:
        """
        Invalidate cache for a project (will be rebuilt on next access).
        
        Args:
            project_root: Path to project root
        """
        project_root = project_root.resolve()
        self._caches.pop(project_root, None)


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
        daemon.handle_request({"ulid": "1", "type": "ping", "payload": {}})
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
        # Load max_workers from settings (default 2 for concurrent calc runs)
        settings = QVService.get_settings()
        max_workers = settings.get("max_concurrent_calcs", 2)
        self.job_manager = JobManager(max_workers=max_workers)
        self.state = DaemonState()
        self._running = False
        
        # Polling RPC endpoints that should log at DEBUG level by default
        # to avoid spamming the logs with high-frequency polling
        self.NOISY_POLLING_RPC = {"job_counts", "list_jobs"}
        
        # Current log level for daemon logs (can be changed at runtime)
        self._rpc_log_level = "INFO"
        
        # CRITICAL: Configure Python logging to output to stderr
        # This ensures all logging.getLogger(...).info(...) calls are visible in GUI
        self._configure_logging()
        
        # Command dispatcher
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            # System commands
            "ping": self._handle_ping,
            "shutdown": self._handle_shutdown,
            
            # Environment and settings
            "detect_qe": self._handle_detect_qe,  # Engine detection — no generic replacement yet (spec §5.5)
            "get_env_info": self._handle_get_env_info,
            "list_qe_engines": self._handle_list_qe_engines,  # Engine detection — no generic replacement yet
            "set_qe_engine": self._handle_set_qe_engine,  # Engine detection — no generic replacement yet
            "set_log_level": self._handle_set_log_level,
            "set_debug_resolution": self._handle_set_debug_resolution,
            "get_debug_resolution": self._handle_get_debug_resolution,
            
            # ─────────────────────────────────────────────────────────────
            # Generic engine RPCs (engine-agnostic, replaces QE-specific)
            # ─────────────────────────────────────────────────────────────
            "list_engine_families": self._handle_list_engine_families,
            "list_step_palette": self._handle_list_step_palette,
            "list_engine_ui_parameters": self._handle_list_engine_ui_parameters,
            "list_engine_parameter_metadata": self._handle_list_engine_parameter_metadata,
            "set_engine_family": self._handle_set_engine_family,
            
            # Pseudopotential configuration
            "get_pseudo_config": self._handle_get_pseudo_config,
            "set_pseudo_config": self._handle_set_pseudo_config,
            "validate_pseudo_config": self._handle_validate_pseudo_config,
            "init_pseudo_dirs": self._handle_init_pseudo_dirs,
            "install_seed_to_store": self._handle_install_seed_to_store,
            "list_installed_sssp": self._handle_list_installed_sssp,
            "list_seed_archives": self._handle_list_seed_archives,
            "download_sssp_library": self._handle_download_sssp_library,
            "download_all_sssp": self._handle_download_all_sssp,
            "resolve_project_pseudo_provenance": self._handle_resolve_project_pseudo_provenance,
            "import_seed_archives": self._handle_import_seed_archives,
            "list_pseudo_archives_status": self._handle_list_pseudo_archives_status,
            "install_pseudo_archive": self._handle_install_pseudo_archive,
            "analyze_project_pseudo_effects": self._handle_analyze_project_pseudo_effects,
            
            # Generic library manager RPCs
            "list_libraries": self._handle_list_libraries,
            "get_library_status": self._handle_get_library_status,
            "install_library": self._handle_install_library,
            "remove_library": self._handle_remove_library,
            "repair_library": self._handle_repair_library,
            "compute_store_size": self._handle_compute_store_size,
            
            # Project/resource listing
            "get_project_summary": self._handle_get_project_summary,
            "list_structures": self._handle_list_structures,
            "list_calculations": self._handle_list_calculations,
            "find_project_root": self._handle_find_project_root,
            "rebuild_project_registry": self._handle_rebuild_project_registry,
            
            # Project creation and management
            "create_project": self._handle_create_project,
            "import_structure": self._handle_import_structure,
            
            # Online structure search
            "structure_search_online": self._handle_structure_search_online,
            "structure_get_online_candidate": self._handle_structure_get_online_candidate,
            "structure_list_providers": self._handle_structure_list_providers,
            "structure_update_online_sources": self._handle_structure_update_online_sources,
            "structure_import_online_candidate": self._handle_structure_import_online_candidate,
            
            # Structure management
            "rename_structure": self._handle_rename_structure,
            "delete_structure": self._handle_delete_structure,
            "can_delete_structure": self._handle_can_delete_structure,
            
            # Calculation creation and management
            "list_calculation_templates": self._handle_list_calculation_templates,
            "create_calculation": self._handle_create_calculation,
            "rename_calculation": self._handle_rename_calculation,
            "delete_calculation": self._handle_delete_calculation,
            "can_delete_calculation": self._handle_can_delete_calculation,
            
            # Step operations
            "get_step_detail": self._handle_get_step_detail,
            "update_step_params": self._handle_update_step_params,
            "reset_step_params": self._handle_reset_step_params,
            "get_common_cards": self._handle_get_common_cards,
            "promote_relax_structure": self._handle_promote_relax_structure,
            "set_common_card": self._handle_set_common_card,
            "get_pseudo_mapping": self._handle_get_pseudo_mapping,
            "set_pseudo_mapping": self._handle_set_pseudo_mapping,
            "import_pseudo_files": self._handle_import_pseudo_files,
            "search_legacy_pseudos": self._handle_search_legacy_pseudos,
            "download_pseudo_by_filename": self._handle_download_pseudo_by_filename,
            "download_pseudo_candidate": self._handle_download_pseudo_candidate,
            "get_relax_final_structure_preview": self._handle_get_relax_final_structure_preview,
            "save_relax_final_structure": self._handle_save_relax_final_structure,
            
            # Calculation configuration
            "get_calculation_detail": self._handle_get_calculation_detail,
            "reorder_calculation_steps": self._handle_reorder_calculation_steps,
            "add_step_to_calculation": self._handle_add_step_to_calculation,
            # import_step_from_qe_input removed in M8
            "change_calculation_structure": self._handle_change_calculation_structure,
            "get_calculation_pseudo_mapping": self._handle_get_calculation_pseudo_mapping,
            "update_calculation_species_map": self._handle_update_calculation_species_map,
            "get_pseudo_options_for_calculation": self._handle_get_pseudo_options_for_calculation,
            "materialize_pseudo_file": self._handle_materialize_pseudo_file,
            "delete_step": self._handle_delete_step,
            
            # Preset detection (Constitution §10.4.1: Detector B is sole state source)
            "get_preset_catalog": self._handle_get_preset_catalog,
            "detect_presets": self._handle_detect_presets,
            "detect_workflow": self._handle_detect_workflow,
            "apply_presets_to_step": self._handle_apply_presets_to_step,
            "apply_presets_to_calculation": self._handle_apply_presets_to_calculation,
            "get_step_preset_footprints": self._handle_get_step_preset_footprints,
            
            # Pre-flight checks
            "preflight_check": self._handle_preflight_check,
            
            # Demo project
            "create_demo_project": self._handle_create_demo_project,
            "list_demo_projects": self._handle_list_demo_projects,
            
            # Visualization data (pure data, no matplotlib)
            "get_structure_vis": self._handle_get_structure_vis,
            "get_reference_analysis": self._handle_get_reference_analysis,
            "get_analysis": self._handle_get_analysis,
            "get_analysis_instances_for_step": self._handle_get_analysis_instances_for_step,
            "get_analysis_snapshot": self._handle_get_analysis_snapshot,
            "get_field3d_grid": self._handle_get_field3d_grid,
            "get_step_digest": self._handle_get_step_digest,
            "list_step_artifacts": self._handle_list_step_artifacts,
            "read_step_artifact_text": self._handle_read_step_artifact_text,
            "list_raw_files": self._handle_list_raw_files,
            "read_raw_file": self._handle_read_raw_file,
            
            # Volume visualization (dev sandbox)
            "list_wannier_3d_fixtures": self._handle_list_wannier_3d_fixtures,
            "compile_fixture_volume": self._handle_compile_fixture_volume,
            
            # Job management
            "run_calculation": self._handle_run_calculation,
            "run_step": self._handle_run_step,
            "run_single_step": self._handle_run_single_step,
            "get_job_status": self._handle_get_job_status,
            "get_job_logs": self._handle_get_job_logs,
            "list_jobs": self._handle_list_jobs,
            "job_counts": self._handle_job_counts,
            "cancel_job": self._handle_cancel_job,
            
            # Journal (change history)
            "list_journal_entries": self._handle_list_journal_entries,
            "get_journal_entry": self._handle_get_journal_entry,
            
            # Project History (notebook timeline)
            "get_project_history": self._handle_get_project_history,
            "get_run_revision": self._handle_get_run_revision,
            "list_project_runs": self._handle_list_project_runs,
            "pin_analysis_to_history": self._handle_pin_analysis_to_history,
            "can_pin_to_run": self._handle_can_pin_to_run,
            "get_pin_data": self._handle_get_pin_data,
            "get_latest_run_for_step": self._handle_get_latest_run_for_step,
            "delete_project_history": self._handle_delete_project_history,
            "get_storage_summary": self._handle_get_storage_summary,
            
            # Workflow operations
            "list_workflow_templates": self._handle_list_workflow_templates,
            "detect_workflow": self._handle_detect_workflow,
            "detect_workflow_for_calculation": self._handle_detect_workflow_for_calculation,
            "instantiate_workflow": self._handle_instantiate_workflow,
        }
    
    def log(self, message: str, level: str = "INFO"):
        """Write log message to stderr."""
        self.stderr.write(f"[qv-daemon] [{level}] {message}\n")
        self.stderr.flush()
    
    def _rpc_log_level_for(self, endpoint: str) -> str:
        """
        Determine the log level for an RPC endpoint.
        
        Polling endpoints (job_counts, list_jobs) log at DEBUG by default
        unless the global log level is set to DEBUG (then they log at DEBUG too).
        Non-polling endpoints log at INFO (or DEBUG if global level is DEBUG).
        
        Args:
            endpoint: RPC endpoint name
            
        Returns:
            "DEBUG" or "INFO"
        """
        # If global log level is DEBUG, all RPCs log at DEBUG
        if self._rpc_log_level == "DEBUG":
            return "DEBUG"
        
        # Otherwise, polling endpoints log at DEBUG, others at INFO
        if endpoint in self.NOISY_POLLING_RPC:
            return "DEBUG"
        return "INFO"
    
    @property
    def logger(self):
        """Logger-like interface for compatibility."""
        class Logger:
            def __init__(self, daemon):
                self.daemon = daemon
            
            def warning(self, message: str, *args, **kwargs):
                """Log warning message."""
                formatted = message.format(*args, **kwargs) if args or kwargs else message
                self.daemon.log(formatted, level="WARNING")
            
            def info(self, message: str, *args, **kwargs):
                """Log info message."""
                formatted = message.format(*args, **kwargs) if args or kwargs else message
                self.daemon.log(formatted, level="INFO")
            
            def error(self, message: str, *args, **kwargs):
                """Log error message."""
                formatted = message.format(*args, **kwargs) if args or kwargs else message
                self.daemon.log(formatted, level="ERROR")
        
        return Logger(self)
    
    def _configure_logging(self):
        """
        Configure Python logging to output all logs to stderr.
        
        This ensures that all logging.getLogger(...).info(...) calls throughout
        the codebase are visible in the GUI Daemon Logs panel.
        """
        # Create a handler that writes to stderr
        handler = logging.StreamHandler(self.stderr)
        
        # Use a formatter that matches the daemon log format
        formatter = logging.Formatter(
            '[qv-daemon] [%(levelname)s] [%(name)s] %(message)s',
            datefmt=None
        )
        handler.setFormatter(formatter)
        
        # Configure root logger to output to stderr at INFO level
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(handler)
        
        # Prevent duplicate logs (don't propagate to parent if already handled)
        root_logger.propagate = False
    
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
            
            # Log incoming request with req_id (dev-only, helps identify duplicate calls)
            if os.environ.get("QV_DEBUG_RPC", "").strip() == "1":
                self.log(f"[RPC-IN] {request_type} (req_id={request_id})")
            
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
        from quantumvitas.api.errors import NotFoundError
        # LegacyProjectError is a kernel exception that may still be raised by some code paths
        # We'll catch it via a generic Exception handler and check the type dynamically
        
        import time
        start_time = time.time()
        
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
        
        # Extract project_root from payload for logging (if present)
        project_root = None
        if isinstance(request.payload, dict):
            project_root_str = request.payload.get("project_root")
            if project_root_str:
                try:
                    project_root = Path(project_root_str).resolve()
                except Exception:
                    pass
        
        try:
            # Apply v0 compatibility: adapt payload before handler
            adapted_payload = adapt_payload(request.type, request.payload)

            result = handler(adapted_payload)

            # Apply v0 compatibility: shape response after handler
            shaped_result = shape_response(request.type, result)

            duration_ms = (time.time() - start_time) * 1000

            # Log request timing
            # Polling RPCs (job_counts, list_jobs) log at DEBUG to avoid spam
            # Other RPCs log at INFO
            log_level = self._rpc_log_level_for(request.type)
            # Tag polling RPCs for frontend filtering
            tag = " [polling]" if request.type in self.NOISY_POLLING_RPC else ""
            if project_root:
                self.log(f"[RPC]{tag} {request.type} (req_id={request.id}, project: {project_root.name}) took {duration_ms:.1f}ms", level=log_level)
            else:
                self.log(f"[RPC]{tag} {request.type} (req_id={request.id}) took {duration_ms:.1f}ms", level=log_level)

            return RPCResponse(id=request.id, ok=True, data=shaped_result)
            
        except ValueError as e:
            # ValueError from handler should be converted to structured error
            return RPCResponse(
                id=request.id,
                ok=False,
                error={"code": "invalid_argument", "message": str(e)},
            )
        except NotFoundError as e:
            # Convert NotFoundError (API error) to structured daemon error
            # API errors use context dict instead of direct attributes
            error_dict = {
                "code": "resource_not_found",
                "kind": e.context.get("resource_type", "resource"),
                "selector": e.context.get("selector", ""),
                "ulid": e.context.get("ulid", ""),
                "message": str(e),
            }
            # Include details from context if present
            if e.context:
                # Copy any additional context fields
                for key in ["suggestions", "calculation_path", "expected_step_path", "reason"]:
                    if key in e.context:
                        if "details" not in error_dict:
                            error_dict["details"] = {}
                        error_dict["details"][key] = e.context[key]
            return RPCResponse(
                id=request.id,
                ok=False,
                error=error_dict,
            )
        except APIError as e:
            return RPCResponse(
                id=request.id,
                ok=False,
                error={"code": "service_error", "message": str(e)},
            )
        except FileNotFoundError as e:
            # Check if this is a project-missing error
            error_str = str(e).lower()
            if "project.qv.yml" in error_str or "project" in error_str:
                return RPCResponse(
                    id=request.id,
                    ok=False,
                    error={"code": "project_missing", "message": str(e), "kind": "project_missing"},
                )
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
        return get_qe_engine_status()["detection"]

    def _handle_get_env_info(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get environment info.

        Payload: (none required)

        Returns python_version, qv_version, qe_home, etc.
        """
        return get_qe_engine_status()["environment"]

    def _handle_list_qe_engines(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List available QE engines (managed + external).

        Payload: (none required)

        Returns managed_engines and external_engines lists.
        """
        return get_qe_engine_status()["available_engines"]

    def _handle_set_qe_engine(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Set QE bin directory (two-state model).
        
        Payload:
            bin_dir: Optional absolute path to QE bin directory (None to use internal QE)
        
        Returns success status.
        """
        bin_dir = payload.get("bin_dir")
        return set_qe_engine(bin_dir=bin_dir)
    
    # -------------------------------------------------------------------------
    # Pseudopotential configuration handlers
    # -------------------------------------------------------------------------
    
    def _handle_get_pseudo_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get pseudopotential configuration.

        Payload: (none required)

        Returns:
            store_dir: str - Path to global pseudo store
            seed_dir: str - Path to seed directory
            allow_download: bool - Whether downloads are allowed
            repo_pseudo_dir: str - Path to resources/pseudo (committed demos)
            default_store_dir: str - Default store directory
            default_seed_dir: str - Default seed directory
        """
        return get_pseudo_status_bundle()["config"]
    
    def _handle_set_pseudo_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Set pseudopotential configuration.
        
        Payload:
            store_dir: Optional[str] - Path to global pseudo store
            seed_dir: Optional[str] - Path to seed directory
            allow_download: Optional[bool] - Whether downloads are allowed
            
        Returns:
            Updated config (same format as get_pseudo_config)
        """
        return set_pseudo_config(
            store_dir=payload.get("store_dir"),
            seed_dir=payload.get("seed_dir"),
            allow_download=payload.get("allow_download"),
        )
    
    def _handle_validate_pseudo_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate pseudopotential configuration.

        Payload: (none required, uses saved config)

        Returns:
            ok: bool - Overall validation status
            repo_pseudo_exists: bool
            store_dir_exists: bool
            store_dir_writable: bool
            seed_dir_exists: bool
            seed_has_sssp: bool
            messages: List[str]
            warnings: List[str]
            errors: List[str]
        """
        return get_pseudo_status_bundle()["validation"]
    
    def _handle_init_pseudo_dirs(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Initialize pseudo directories (create if missing).
        
        Payload: (none required, uses saved config)
        
        Returns:
            store_dir_created: bool
            seed_dir_created: bool
            messages: List[str]
            errors: List[str]
        """
        return QVService.init_pseudo_dirs()
    
    def _handle_install_seed_to_store(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Install SSSP libraries from seed to store.
        
        Payload:
            version: Optional[str] - SSSP version (default: all available)
            flavor: Optional[str] - SSSP flavor (default: all available)
            
        Returns:
            success: bool
            installed: List of installed libraries
            skipped: List of skipped (already installed)
            failed: List of failed installations
            messages: List[str]
        """
        from quantumvitas.api import QVService
        from pathlib import Path

        bundle = get_pseudo_status_bundle()
        config = bundle["config"]

        if not config.get("seed_dir"):
            return {
                "success": False,
                "messages": [],
                "errors": ["Seed directory not configured"],
            }

        if not config.get("store_dir"):
            return {
                "success": False,
                "messages": [],
                "errors": ["Store directory not configured"],
            }

        seed_dir = Path(config.get("seed_dir"))
        store_dir = Path(config.get("store_dir"))

        version = payload.get("version")
        flavor = payload.get("flavor")

        if version and flavor:
            # Install specific version/flavor
            result = QVService.install_sssp_from_seed(seed_dir, store_dir, version, flavor)
            return result
        else:
            # Install all available
            return QVService.install_all_sssp_from_seed(seed_dir, store_dir)
    
    def _handle_list_installed_sssp(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List installed SSSP libraries in store.

        Payload: (none required, uses saved config)

        Returns:
            libraries: List of SSSPLibraryInfo dicts
        """
        return {
            "libraries": get_pseudo_status_bundle()["installed_sssp"],
        }
    
    def _handle_list_seed_archives(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List SSSP archives in seed directory.

        Payload: (none required, uses saved config)

        Returns:
            archives: List of SeedArchiveInfo dicts
        """
        return {
            "archives": get_pseudo_status_bundle()["seed_archives"],
        }
    
    def _handle_download_sssp_library(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Download a specific SSSP library from Materials Cloud.
        
        Payload:
            flavor: str - "efficiency" or "precision"
            version: Optional[str] - SSSP version (default: "1.3.0")
            force: Optional[bool] - If True, download even if allow_download is off
            
        Returns:
            success: bool
            version: str
            flavor: str
            files_installed: int
            messages: List[str]
            errors: List[str]
            warnings: List[str]
        """
        from quantumvitas.api import QVService
        from pathlib import Path

        flavor = payload.get("flavor")
        if not flavor:
            raise ValueError("flavor is required ('efficiency' or 'precision')")
        if flavor not in ("efficiency", "precision"):
            raise ValueError(f"Invalid flavor: {flavor}. Must be 'efficiency' or 'precision'")

        version = payload.get("version", "1.3.0")
        force = payload.get("force", False)

        bundle = get_pseudo_status_bundle()
        config = bundle["config"]

        if not config.get("store_dir"):
            return {
                "success": False,
                "errors": ["Store directory not configured"],
                "messages": [],
            }

        store_dir = Path(config.get("store_dir"))
        seed_dir = Path(config.get("seed_dir")) if config.get("seed_dir") else None
        result = QVService.download_sssp_library(
            store_dir=store_dir,
            flavor=flavor,
            version=version,
            force=force,
            allow_download=config.get("allow_download", False),
            seed_dir=seed_dir,
        )

        # Add installed libraries to response (refresh after download)
        result["installed_libraries"] = get_pseudo_status_bundle()["installed_sssp"]

        return result
    
    def _handle_download_all_sssp(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Download all supported SSSP libraries from Materials Cloud.
        
        Payload:
            force: Optional[bool] - If True, download even if allow_download is off
            
        Returns:
            success: bool
            installed: List of installed libraries
            skipped: List of already-installed libraries
            failed: List of failed downloads
            messages: List[str]
        """
        from quantumvitas.api import QVService
        from pathlib import Path

        force = payload.get("force", False)

        bundle = get_pseudo_status_bundle()
        config = bundle["config"]

        if not config.get("store_dir"):
            return {
                "success": False,
                "errors": ["Store directory not configured"],
                "messages": [],
            }

        store_dir = Path(config.get("store_dir"))
        seed_dir = Path(config.get("seed_dir")) if config.get("seed_dir") else None
        result = QVService.download_all_sssp(
            store_dir=store_dir,
            force=force,
            allow_download=config.get("allow_download", False),
            seed_dir=seed_dir,
        )

        # Add installed libraries to response (refresh after download)
        result["installed_libraries"] = get_pseudo_status_bundle()["installed_sssp"]

        return result
    
    def _handle_import_seed_archives(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Import seed archives (tar/zip) into seed_dir with SHA256 deduplication.
        
        Payload:
            file_paths: List[str] - Paths to archive files to import
            
        Returns:
            Dict with imported, skipped, errors lists
        """
        from quantumvitas.api import QVService
        from pathlib import Path

        file_paths = payload.get("file_paths", [])
        if not file_paths:
            return {
                "imported": [],
                "skipped": [],
                "errors": ["No files provided"],
            }

        bundle = get_pseudo_status_bundle()
        config = bundle["config"]
        if not config.get("seed_dir"):
            return {
                "imported": [],
                "skipped": [],
                "errors": ["Seed directory not configured"],
            }

        seed_dir = Path(config.get("seed_dir"))
        archive_paths = [Path(p) for p in file_paths]

        return QVService.import_seed_archives(seed_dir, archive_paths)
    
    def _handle_list_libraries(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List all supported libraries with metadata.
        
        Payload: (none required)
        
        Returns:
            libraries: List of LibraryMetadata dicts
        """
        libraries = QVService.list_pseudo_libraries()
        return {
            "libraries": libraries,
        }
    
    def _handle_get_library_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get status of a library (which variants are installed).
        
        Payload:
            library_id: str - Library identifier (e.g., "sssp")
            
        Returns:
            LibraryStatus dict
        """
        library_id = payload.get("library_id")
        if not library_id:
            return {
                "ok": False,
                "error": {"code": "missing_field", "message": "library_id required"},
            }
        
        try:
            status = QVService.get_library_status(library_id)
            return {
                "ok": True,
                "data": status,
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {"code": "unsupported_library", "message": f"Unsupported library: {library_id}"},
            }
    
    def _handle_install_library(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Install a library with specified variants.
        
        Payload:
            library_id: str - Library identifier
            variants: List[str] - Variant names to install
            source: str - "github_release", "local_archive", or "seed"
            local_archive_paths: Optional[List[str]] - For local_archive source
            force: Optional[bool] - Force download even if allow_download is False
            
        Returns:
            Dict with success, messages, errors, warnings
        """
        library_id = payload.get("library_id")
        variants = payload.get("variants", [])
        source = payload.get("source", "github_release")
        local_archive_paths = payload.get("local_archive_paths")
        force = payload.get("force", False)
        
        if not library_id:
            return {
                "success": False,
                "errors": ["library_id required"],
                "messages": [],
                "warnings": [],
            }
        
        return QVService.install_pseudo_library(
            library_id=library_id,
            variants=variants,
            source=source,
            local_archive_paths=local_archive_paths,
            force=force,
        )
    
    def _handle_remove_library(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove library variants from store.
        
        Payload:
            library_id: str - Library identifier
            variants: List[str] - Variant names to remove
            
        Returns:
            Dict with success, messages, errors
        """
        library_id = payload.get("library_id")
        variants = payload.get("variants", [])
        
        if not library_id:
            return {
                "success": False,
                "errors": ["library_id required"],
                "messages": [],
            }
        
        return QVService.remove_pseudo_library(library_id=library_id, variants=variants)
    
    def _handle_repair_library(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Repair library by re-extracting from seed cache.
        
        Payload:
            library_id: str - Library identifier
            variants: List[str] - Variant names to repair
            
        Returns:
            Dict with success, messages, errors
        """
        library_id = payload.get("library_id")
        variants = payload.get("variants", [])
        
        if not library_id:
            return {
                "success": False,
                "errors": ["library_id required"],
                "messages": [],
            }
        
        return QVService.repair_pseudo_library(library_id=library_id, variants=variants)
    
    def _handle_compute_store_size(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute total size of store directory.
        
        Payload: (none required)
        
        Returns:
            size_bytes: Optional[int] - Total size in bytes, or None if not configured
        """
        size_info = QVService.compute_store_size()
        return {
            "size_bytes": size_info.get("size_bytes") if isinstance(size_info, dict) else size_info,
        }
    
    def _handle_resolve_project_pseudo_provenance(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve pseudo provenance for a pseudo file in a project.
        
        Payload:
            project_root: str - Path to project root
            pseudo_relpath: Optional[str] - Relative path from project root (e.g., "pseudo/Si.upf")
            pseudo_abspath: Optional[str] - Absolute path to pseudo file
            
        Returns:
            Dict with provenance information (serialized PseudoProvenanceResult)
        """
        from quantumvitas.api import QVService
        from pathlib import Path
        
        project_root_str = payload.get("project_root")
        pseudo_relpath = payload.get("pseudo_relpath")
        pseudo_abspath = payload.get("pseudo_abspath")
        
        if pseudo_abspath:
            pseudo_path = Path(pseudo_abspath)
        elif pseudo_relpath and project_root_str:
            pseudo_path = Path(project_root_str) / pseudo_relpath
        else:
            raise ValueError(
                "Must provide either 'pseudo_abspath' or both 'project_root' and 'pseudo_relpath'"
            )
        
        return resolve_pseudo_provenance(
            str(pseudo_path),
            project_root=project_root_str,
        )
    
    def _handle_list_pseudo_archives_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List all pseudopotential archives from vendored manifest with install status.

        Payload: (none required)

        Returns:
            Dict with:
            - archives: List[ArchiveStatus dict] - All archives with install status
            - grouped_by_library: Dict[str, List[ArchiveStatus dict]] - Grouped by library_name
        """
        try:
            bundle = get_pseudo_status_bundle()
            archives_status = bundle["archive_statuses"]

            # Group by library_name + library_version
            grouped: Dict[str, List[Dict[str, Any]]] = {}
            for archive_status in archives_status:
                # Extract library info from archive dict
                library_name = archive_status.get("library_name", "")
                library_version = archive_status.get("library_version", "")
                key = f"{library_name} {library_version}"
                if key not in grouped:
                    grouped[key] = []
                grouped[key].append(archive_status)

            return {
                "archives": archives_status,
                "grouped_by_library": grouped,
            }
        except Exception as e:
            return {
                "archives": [],
                "grouped_by_library": {},
                "error": str(e),
            }
    
    def _handle_install_pseudo_archive(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Install a pseudopotential archive by asset name.
        
        Payload:
            asset_name: str - Archive filename (e.g., "SSSP_1.3.0_PBE_efficiency.tar.gz")
            force: Optional[bool] - Force re-download even if installed (default: False)
        
        Returns:
            Dict with:
            - success: bool
            - messages: List[str]
            - errors: List[str]
            - archive_status: Optional[ArchiveStatus dict] - Updated status after install
        """
        
        asset_name = payload.get("asset_name")
        if not asset_name:
            return {
                "success": False,
                "messages": [],
                "errors": ["asset_name is required"],
                "archive_status": None,
            }
        
        force = payload.get("force", False)

        try:
            bundle = get_pseudo_status_bundle()
            config = bundle["config"]

            # Check if downloads are allowed
            if not config.get("allow_download", False) and not force:
                return {
                    "success": False,
                    "messages": [],
                    "errors": ["Network downloads not allowed. Enable 'Allow Network Downloads' in Settings."],
                    "archive_status": None,
                }

            # Find archive in manifest
            manifest_archives = bundle["manifest_archives"]
            archive = None
            for arch in manifest_archives:
                if arch.get("asset_name") == asset_name:
                    archive = arch
                    break

            if not archive:
                return {
                    "success": False,
                    "messages": [],
                    "errors": [f"Archive not found in manifest: {asset_name}"],
                    "archive_status": None,
                }

            # Check if already installed (unless force)
            if not force:
                if QVService.is_pseudo_archive_installed(
                    asset_name=asset_name,
                    expected_sha256=archive.get("sha256", ""),
                    config=config,
                ):
                    # Return success with current status from bundle
                    archive_status = None
                    for status in bundle["archive_statuses"]:
                        if status.get("asset_name") == asset_name:
                            archive_status = status
                            break
                    return {
                        "success": True,
                        "messages": [f"Archive already installed: {asset_name}"],
                        "errors": [],
                        "archive_status": archive_status,
                    }

            # Install archive
            if not archive.get("upstream_url"):
                return {
                    "success": False,
                    "messages": [],
                    "errors": [f"No upstream URL for archive: {asset_name}"],
                    "archive_status": None,
                }

            result = QVService.install_pseudo_archive(
                asset_url=archive.get("upstream_url", ""),
                asset_name=archive.get("asset_name", ""),
                expected_sha256=archive.get("sha256", ""),
                expected_size=archive.get("size_bytes"),
                config=config,
            )

            # Get updated status (refresh bundle after install)
            updated_bundle = get_pseudo_status_bundle()
            archive_status = None
            for status in updated_bundle["archive_statuses"]:
                if status.get("asset_name") == asset_name:
                    archive_status = status
                    break

            return {
                "success": result.get("success", False),
                "messages": result.get("messages", []),
                "errors": result.get("errors", []),
                "archive_status": archive_status,
            }
        except Exception as e:
            return {
                "success": False,
                "messages": [],
                "errors": [f"Installation failed: {e}"],
                "archive_status": None,
            }
    
    def _handle_set_log_level(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Set daemon log verbosity level.
        
        Payload:
            level: str - "INFO" or "DEBUG"
        
        Returns:
            {"ok": true, "level": "INFO" | "DEBUG"}
        """
        level = payload.get("level", "INFO")
        if level not in ("INFO", "DEBUG"):
            raise ValueError(f"Invalid log level: {level}. Must be 'INFO' or 'DEBUG'")
        
        self._rpc_log_level = level
        self._update_logging_level(level)
        
        return {"ok": True, "level": level}
    
    def _handle_set_debug_resolution(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enable or disable resolution/addressing debug logs.
        
        Payload:
            enabled: bool - True to enable, False to disable
        
        Returns:
            {"ok": true, "enabled": bool}
        """
        enabled = payload.get("enabled", False)
        if not isinstance(enabled, bool):
            raise ValueError(f"Invalid enabled value: {enabled}. Must be boolean")
        
        set_settings({"debug_resolution": enabled})
        
        return {"ok": True, "enabled": enabled}
    
    def _handle_get_debug_resolution(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get current resolution debug flag state.
        
        Returns:
            {"ok": true, "enabled": bool}
        """
        settings = QVService.get_settings()
        return {"ok": True, "enabled": settings.get("debug_resolution", False)}
    
    def _update_logging_level(self, level: str):
        """
        Update Python logging level at runtime.
        
        Args:
            level: "INFO" or "DEBUG"
        """
        log_level = logging.DEBUG if level == "DEBUG" else logging.INFO
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
    
    def _qe_parameter_metadata_internal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Browse QE parameter metadata (modules, sections, parameters, search).
        
        Payload:
            operation: str (required) - One of: "list_modules", "list_sections", "list_parameters", "search"
            
            For "list_modules": no additional fields needed.
            
            For "list_sections": requires "module": str
            
            For "list_parameters": requires "module": str, "section": str (e.g., "&SYSTEM")
            
            For "search": requires "query": str (searches across all modules/sections)
        
        Returns:
            For "list_modules": {"modules": [{"ulid": "pw", "label": "pw.x"}, ...]}
            For "list_sections": {"sections": [{"ulid": "&SYSTEM", "kind": "namelist", "label": "&SYSTEM"}, ...]}
            For "list_parameters": {"parameters": [{name, type, default, enum, description, indexing, ...}, ...]}
            For "search": {"results": [{module, section, name, type, ...}, ...]}
        """
        operation = payload.get("operation", "").strip().lower()
        
        if not operation:
            raise ValueError("'operation' is required in payload. Must be one of: list_modules, list_sections, list_parameters, search")
        
        # Log at info level for visibility with actual values
        # Extract values before logging
        module = payload.get("module", "")
        section = payload.get("section", "")
        query = payload.get("query", "")
        
        if operation == "list_modules":
            self.log("[RPC] list_qe_parameter_metadata (operation: list_modules)")
        elif operation == "list_sections":
            self.log(f"[RPC] list_qe_parameter_metadata (operation: list_sections, module: {module})")
        elif operation == "list_parameters":
            self.log(f"[RPC] list_qe_parameter_metadata (operation: list_parameters, module: {module}, section: {section})")
        elif operation == "search":
            self.log(f"[RPC] list_qe_parameter_metadata (operation: search, query: {query})")
        else:
            self.log(f"[RPC] list_qe_parameter_metadata (operation: {operation})")
        
        try:
            # Get metadata file info for all operations
            metadata_info = get_metadata_file_info()
            
            if operation == "list_modules":
                # List all supported QE modules
                modules = list_supported_modules()
                result = []
                for module_id in modules:
                    doc_url = get_module_doc_url(module_id)
                    label = f"{module_id}.x" if module_id else module_id
                    result.append({
                        "id": module_id,  # Backwards compat alias
                        "ulid": module_id,
                        "label": label,
                        "doc_url": doc_url,
                    })
                return {
                    "modules": result,
                    "metadata_path_abs": metadata_info.get("metadata_path_abs"),
                    "schema_version": metadata_info.get("schema_version"),
                }
            
            elif operation == "list_sections":
                # List sections (namelists/cards) for a given module
                module = payload.get("module", "").strip().lower()
                if not module:
                    raise ValueError("'module' is required for list_sections operation")
                
                self.log(f"[RPC] list_qe_parameter_metadata (operation: list_sections, module: {module})")
                
                # Validate module exists
                supported_modules = list_supported_modules()
                if module not in supported_modules:
                    raise ValueError(
                        f"Unknown module '{module}'. Supported modules: {', '.join(sorted(supported_modules))}"
                    )
                
                result = []
                seen_sections = set()

                # Get card sections (from card_metadata) for reference
                card_sections = get_module_card_sections(module)
                card_names_upper = {card_name.upper() for card_name in card_sections}
                
                # Get raw metadata to preserve JSON order
                raw_data = safe_load_metadata()
                modules_data = raw_data.get("modules", {})
                module_entry = modules_data.get(module)
                
                if not module_entry:
                    metadata_info = get_metadata_file_info()
                    return {
                        "sections": [],
                        "metadata_path_abs": metadata_info.get("metadata_path_abs"),
                        "schema_version": metadata_info.get("schema_version"),
                    }
                
                # Extract section order from parameters map (v2/v3 schema) or sections dict (v1 schema)
                # This preserves the JSON insertion order
                schema_version = raw_data.get("schema_version", 0)
                section_order = []
                
                if schema_version in (1, 2, 3):
                    # v2/v3 schema: extract section names from parameters map keys
                    # Key format: "&SECTION.paramname" or "SECTION.paramname"
                    parameters = module_entry.get("parameters", {})
                    for param_key in parameters.keys():
                        if '.' in param_key:
                            section_part = param_key.split('.')[0]
                            # Normalize: remove '&' for comparison, keep original for label
                            section_normalized = section_part[1:].upper() if section_part.startswith('&') else section_part.upper()
                            if section_normalized not in seen_sections:
                                seen_sections.add(section_normalized)
                                section_order.append((section_part, section_normalized))
                else:
                    # v1 schema: use sections dict order
                    sections_dict = module_entry.get("sections", {})
                    for section_name in sections_dict.keys():
                        section_normalized = section_name[1:].upper() if section_name.startswith("&") else section_name.upper()
                        if section_normalized not in seen_sections:
                            seen_sections.add(section_normalized)
                            section_order.append((section_name, section_normalized))
                    
                # Build result in JSON order
                for section_part, section_normalized in section_order:
                    # Check if it's a card (cards take priority over namelists)
                    if section_normalized in card_names_upper:
                        # This is a card
                        result.append({
                            "id": section_normalized,  # Backwards compat alias
                            "ulid": section_normalized,  # For lookups
                            "name": section_normalized,  # Clean name without '&'
                            "label": section_normalized,  # Label is same as name for cards (no '&')
                            "kind": "card",
                        })
                    elif section_part.startswith("&"):
                        # This is a namelist
                        result.append({
                            "id": section_part,  # Backwards compat alias
                            "ulid": section_part,  # Keep original for backward compatibility (with '&')
                            "name": section_normalized,  # Clean name without '&'
                            "label": section_part,  # Label includes '&' prefix for namelists
                            "kind": "namelist",
                        })
                    else:
                        # Section without '&' prefix - could be a card or namelist
                        # If it's in card_metadata, it's a card; otherwise, treat as namelist
                        if section_normalized in card_names_upper:
                            result.append({
                                "id": section_normalized,  # Backwards compat alias
                                "ulid": section_normalized,
                                "name": section_normalized,
                                "label": section_normalized,
                                "kind": "card",
                            })
                        else:
                            # Treat as namelist (add '&' prefix for label)
                            result.append({
                                "id": f"&{section_normalized}",  # Backwards compat alias
                                "ulid": f"&{section_normalized}",
                                "name": section_normalized,
                                "label": f"&{section_normalized}",
                                "kind": "namelist",
                            })
                
                # Add any cards from card_metadata that weren't in parameters/sections
                # (these should be rare, but we want to include them)
                for card_name in card_sections:
                    card_name_upper = card_name.upper()
                    if card_name_upper not in [s["name"] for s in result]:
                        result.append({
                            "id": card_name_upper,  # Backwards compat alias
                            "ulid": card_name_upper,
                            "name": card_name_upper,
                            "label": card_name_upper,
                            "kind": "card",
                        })
                
                # Preserve JSON insertion order - no sorting
                
                # Log sample sections for debugging
                self.log(f"[RPC] list_sections returning {len(result)} sections (preserving metadata order)")
                for sec in result[:3]:  # Log first 3
                    self.log(f"  - {sec['name']} ({sec['kind']})")
                
                return {
                    "sections": result,
                    "metadata_path_abs": metadata_info.get("metadata_path_abs"),
                    "schema_version": metadata_info.get("schema_version"),
                }
            
            elif operation == "list_parameters":
                # List parameters for a given module and section
                module = payload.get("module", "").strip().lower()
                section = payload.get("section", "").strip()
                
                self.log(f"[RPC] list_qe_parameter_metadata (operation: list_parameters, module: {module}, section: {section})")
                
                if not module:
                    raise ValueError("'module' is required for list_parameters operation")
                if not section:
                    raise ValueError("'section' is required for list_parameters operation")
                
                # Normalize section name (remove '&' prefix if present)
                section_normalized = section[1:].upper() if section.startswith("&") else section.upper()
                is_namelist = section.startswith("&")
                
                result = []
                raw_data = safe_load_metadata()
                modules_data = raw_data.get("modules", {})
                module_entry = modules_data.get(module)
                
                if not module_entry:
                    return {
                        "parameters": [],
                        "metadata_path_abs": metadata_info.get("metadata_path_abs"),
                        "schema_version": metadata_info.get("schema_version"),
                    }
                
                if is_namelist:
                    # Handle namelist sections
                    section_with_prefix = f"&{section_normalized}"

                    # Get all parameters for the module (use internal _iter_params)
                    params = _iter_params(module)
                    
                    # Filter by section
                    for param in params:
                        param_namelist = param.get("namelist", "")
                        param_section = f"&{param_namelist.upper()}" if param_namelist else ""
                        
                        # Match section
                        if param_section == section_with_prefix or param_namelist.upper() == section_normalized:
                            param_name = param.get("name")
                            param_dict = {
                                "name": param_name,
                                "type": param.get("type"),
                                "default": param.get("default"),
                                "enum": param.get("enum"),
                                "description": param.get("description"),
                                "section": section_with_prefix,
                                "module": module,
                            }
                            
                            # For v2/v3 schema, get indexing metadata from raw data
                            schema_version = raw_data.get("schema_version", 0)
                            if schema_version in (1, 2, 3):
                                parameters_map = module_entry.get("parameters", {})
                                # Find the parameter in the map (key format: "&SECTION.paramname")
                                param_key = f"{section_with_prefix}.{param_name}"
                                param_meta = parameters_map.get(param_key)
                                if param_meta and "indexing" in param_meta:
                                    param_dict["indexing"] = param_meta["indexing"]
                            
                            # Add managed/protected parameter metadata
                            # QE managed params: CONTROL.prefix, CONTROL.outdir, CONTROL.pseudo_dir (runtime_overridden)
                            # CONTROL.calculation (step_type_owned)
                            is_managed = False
                            managed_reason = None
                            if section_normalized == "CONTROL":
                                if param_name and param_name.lower() in ("prefix", "outdir", "pseudo_dir"):
                                    is_managed = True
                                    managed_reason = "runtime_overridden"
                                elif param_name and param_name.lower() == "calculation":
                                    is_managed = True
                                    managed_reason = "step_type_owned"
                            
                            param_dict["is_managed"] = is_managed
                            if managed_reason:
                                param_dict["managed_reason"] = managed_reason
                            
                            result.append(param_dict)
                else:
                    # Handle card sections - cards have metadata but not individual parameters
                    # Return the card metadata as a single "parameter" entry
                    card_metadata = module_entry.get("card_metadata", {})
                    card_info = card_metadata.get(section_normalized)
                    
                    if card_info:
                        result.append({
                            "name": card_info.get("name", section_normalized),
                            "type": card_info.get("type"),
                            "default": card_info.get("default"),
                            "enum": card_info.get("enum"),
                            "description": card_info.get("description"),
                            "section": section_normalized,  # Cards don't have '&' prefix
                            "module": module,
                        })
                
                # Sort by name
                result.sort(key=lambda x: x.get("name", ""))
                return {
                    "parameters": result,
                    "metadata_path_abs": metadata_info.get("metadata_path_abs"),
                    "schema_version": metadata_info.get("schema_version"),
                }
            
            elif operation == "search":
                # Global search across all modules and sections
                query = payload.get("query", "").strip()
                if not query:
                    return {"results": []}
                
                query_lower = query.lower()
                modules = list_supported_modules()
                results = []
                
                # Search across all modules
                for module in modules:
                    # Get sections for this module (both namelists and cards)
                    card_sections = get_module_card_sections(module)
                    sections_dict = get_module_param_sections(module)

                    # Search namelist parameters
                    params = _iter_params(module)
                    for param in params:
                        param_name = param.get("name", "").lower()
                        param_desc = (param.get("description") or "").lower()
                        param_default = str(param.get("default", "")).lower() if param.get("default") is not None else ""
                        param_enum = param.get("enum") or []
                        param_section = f"&{param.get('namelist', '').upper()}"
                        
                        # Build searchable text
                        searchable_fields = [
                            param_name,
                            param_desc,
                            param_default,
                        ]
                        if param_enum:
                            searchable_fields.extend(str(val).lower() for val in param_enum)
                        
                        searchable_text = " ".join(searchable_fields)
                        
                        # Match on any field
                        if query_lower in searchable_text:
                            param_dict = {
                                "module": module,
                                "section": param_section,
                                "name": param.get("name"),
                                "key": f"{module}::{param_section}::{param.get('name')}",
                                "type": param.get("type"),
                                "default": param.get("default"),
                                "enum": param.get("enum"),
                                "description": param.get("description"),
                            }
                            
                            # Get indexing metadata for v2/v3 schema
                            try:
                                raw_data = safe_load_metadata()
                                if raw_data.get("schema_version") in (1, 2, 3):
                                    modules_data = raw_data.get("modules", {})
                                    module_entry = modules_data.get(module)
                                    if module_entry:
                                        parameters_map = module_entry.get("parameters", {})
                                        param_key = f"{param_section}.{param.get('name')}"
                                        param_meta = parameters_map.get(param_key)
                                        if param_meta and "indexing" in param_meta:
                                            param_dict["indexing"] = param_meta["indexing"]
                            except Exception:
                                pass  # Indexing is optional
                            
                            results.append(param_dict)
                
                    # Search card sections
                    raw_data = safe_load_metadata()
                    modules_data = raw_data.get("modules", {})
                    module_entry = modules_data.get(module)
                    if module_entry:
                        card_metadata = module_entry.get("card_metadata", {})
                        for card_name in card_sections:
                            card_info = card_metadata.get(card_name)
                            if card_info:
                                card_name_lower = card_name.lower()
                                card_desc = (card_info.get("description") or "").lower()
                                card_default = str(card_info.get("default", "")).lower() if card_info.get("default") is not None else ""
                                card_enum = card_info.get("enum") or []
                                
                                # Build searchable text
                                searchable_fields = [
                                    card_name_lower,
                                    card_desc,
                                    card_default,
                                ]
                                if card_enum:
                                    searchable_fields.extend(str(val).lower() for val in card_enum)
                                
                                searchable_text = " ".join(searchable_fields)
                                
                                # Match on any field
                                if query_lower in searchable_text:
                                    results.append({
                                        "module": module,
                                        "section": card_name.upper(),  # Cards don't have '&' prefix
                                        "name": card_info.get("name", card_name.upper()),
                                        "key": f"{module}::{card_name.upper()}::{card_info.get('name', card_name.upper())}",
                                        "type": card_info.get("type"),
                                        "default": card_info.get("default"),
                                        "enum": card_info.get("enum"),
                                        "description": card_info.get("description"),
                                    })
                
                return {
                    "results": results,
                    "metadata_path_abs": metadata_info.get("metadata_path_abs"),
                    "schema_version": metadata_info.get("schema_version"),
                }
            
            else:
                raise ValueError(f"Unknown operation '{operation}'. Must be one of: list_modules, list_sections, list_parameters, search")
        
        except (RuntimeError, FileNotFoundError) as e:
            # Metadata loading errors should be user-friendly
            raise ValueError(f"QE parameter metadata is not available: {e}. Run `python tools/extract_qe_parameters_v2.py` to generate it.") from e
    
    # _handle_reload_qe_parameter_metadata and _handle_get_qe_parameter_metadata_debug_info
    # removed in M8 — debug-only QE RPCs, no GUI consumer
    # ─────────────────────────────────────────────────────────────────────
    # Generic Engine RPCs (M4)
    # ─────────────────────────────────────────────────────────────────────

    def _handle_list_engine_families(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List all registered engine families with classification.

        Payload: (none required)

        Returns:
            {"engines": [{engine_family, display_name, engine_role, companion_engines, supported_gen_steps}]}
        """
        from quantumvitas.api.utils import list_engine_families
        return {"engines": list_engine_families()}

    def _handle_list_step_palette(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get step palette for a given engine_family (or UNDECIDED).

        Payload:
            engine_family: str | null — If null, returns empty palette.

        Returns:
            {
                "base_steps": [{"gen": "scf", "spec": "qe_scf", "description": "..."}],
                "companion_steps": {"w90": [{"gen": "wannierprep", "spec": "w90_wannierprep", ...}]},
            }
        """
        from quantumvitas.api.utils import get_step_palette
        engine_family = payload.get("engine_family")
        return get_step_palette(engine_family)

    def _handle_list_engine_ui_parameters(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get UI parameter metadata for any engine + step type.

        Payload:
            engine_family: str (required)
            step_type_gen: str (required) — GEN step type (e.g., "scf")

        Returns:
            {"parameters": [{key, label, type, default, description, section, ...}]}
        """
        engine_family = payload.get("engine_family", "").strip().lower()
        step_type_gen = payload.get("step_type_gen", "").strip().lower()

        if not engine_family:
            raise ValueError("'engine_family' is required in payload")
        if not step_type_gen:
            raise ValueError("'step_type_gen' is required in payload")

        self.log(f"[RPC] list_engine_ui_parameters (engine: {engine_family}, gen: {step_type_gen})")

        from quantumvitas.api.utils import get_engine_ui_parameters
        return {"parameters": get_engine_ui_parameters(engine_family, step_type_gen)}

    def _handle_list_engine_parameter_metadata(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Browse parameter metadata for any engine.

        Payload:
            engine_family: str (required)
            operation: str (required) — "list_categories", "list_tags", "search"

        Returns:
            Varies by operation (same shape across engines).
        """
        engine_family = payload.get("engine_family", "").strip().lower()
        operation = payload.get("operation", "").strip().lower()

        if not engine_family:
            raise ValueError("'engine_family' is required in payload")
        if not operation:
            raise ValueError("'operation' is required. Must be: list_categories, list_sections, list_tags, search")

        self.log(f"[RPC] list_engine_parameter_metadata (engine: {engine_family}, op: {operation})")

        # For QE, delegate to existing metadata infrastructure
        if engine_family == "qe":
            qe_payload = dict(payload)
            if operation == "list_categories":
                qe_payload["operation"] = "list_modules"
            elif operation == "list_sections":
                qe_payload["operation"] = "list_sections"
                qe_payload["module"] = payload.get("category", "pw")
            elif operation == "list_tags":
                qe_payload["operation"] = "list_parameters"
                qe_payload["module"] = payload.get("category", "pw")
                qe_payload["section"] = payload.get("section", "")
            elif operation == "search":
                qe_payload["operation"] = "search"
            return self._qe_parameter_metadata_internal(qe_payload)

        # For other engines: delegate to api.utils
        from quantumvitas.api.utils import get_engine_parameter_metadata
        return get_engine_parameter_metadata(
            engine_family=engine_family,
            operation=operation,
            category=payload.get("category", ""),
            query=payload.get("query", ""),
        )

    def _handle_set_engine_family(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Set engine_family on a calculation (UNDECIDED -> DECIDED transition).
        Thin wrapper — delegates to QVService.calculation.set_engine_family().
        """
        project_root = self._require_path(payload, "project_root")
        calculation_selector = self._require_str(payload, "calculation")
        engine_family = self._require_str(payload, "engine_family")

        svc = get_service(project_root)
        svc.calculation.set_engine_family(calculation_selector, engine_family)
        self.log(f"[RPC] set_engine_family: {calculation_selector} -> {engine_family}")
        return {"success": True, "engine_family": engine_family}
    
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
        svc = get_service(project_root)
        return svc.project.get_summary()
    
    def _handle_list_structures(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List structures in project.
        
        Payload:
            project_root: str - Path to project root
        """
        project_root = self._require_path(payload, "project_root")
        svc = get_service(project_root)
        structure_dtos = svc.structure.list()
        # Convert DTOs to dicts for JSON serialization using to_dict()
        structures = [dto.to_dict() for dto in structure_dtos]
        return {"structures": structures, "count": len(structures)}
    
    def _handle_list_calculations(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List calculations in project.

        Payload:
            project_root: str - Path to project root
        """
        project_root = self._require_path(payload, "project_root")
        svc = get_service(project_root)
        calculation_dtos = svc.calculation.list()
        # Convert DTOs to dicts for JSON serialization
        # Note: DTOs have step_ulids but not full steps; compat layer expands these
        calculations = [dto.to_dict() for dto in calculation_dtos]
        return {
            "calculations": calculations,
            "count": len(calculations),
            # Internal: project_root for compat layer to compute absolute paths
            "_project_root": str(project_root),
        }
    
    def _handle_find_project_root(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search up from a directory to find a project root.
        
        Uses the existing context detection from quantumvitas.core.context.
        
        Payload:
            start_dir: str - Directory to start searching from
            
        Returns:
            found: bool - Whether a project was found
            project_root: str | null - Path to project root if found
        """
        from quantumvitas.api import QVService
        from quantumvitas.api.errors import NotFoundError
        
        start_dir = Path(payload.get("start_dir", "")).resolve()
        if not start_dir.exists():
            return {"found": False, "project_root": None}
        
        try:
            ctx = find_path_context_from_pwd(start_dir)
            return {"found": True, "project_root": str(ctx.project_root)}
        except NotFoundError:
            # ContextNotFoundError is mapped to NotFoundError by map_kernel_exception
            return {"found": False, "project_root": None}
        except ValueError:
            # ContextNotFoundError may also be a ValueError in some cases
            return {"found": False, "project_root": None}
    
    # -------------------------------------------------------------------------
    # Project creation handlers
    # -------------------------------------------------------------------------
    
    def _handle_create_project(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new project.
        
        Payload:
            target_dir: str - Directory to create project in
            name: str - Optional project name (defaults to dir name)
            template: str - Optional template name (deprecated)
        """
        target_dir = Path(payload.get("target_dir", "")).resolve()
        name = payload.get("name")
        template = payload.get("template")
        
        if not target_dir:
            raise ValueError("Missing required field: target_dir")
        
        try:
            project_root = QVService.init_project(
                target_dir=target_dir,
                name=name,
                template=template,
            )
        except ValueError as e:
            # Re-raise ValueError as-is (for validation errors like "inside existing project")
            raise
        
        # Project creation creates a new project - registry will be built on first access
        
        # Get summary of newly created project
        svc = get_service(project_root)
        summary = svc.project.get_summary()
        
        return {
            "project_root": str(project_root),
            "name": summary.get("name", name or target_dir.name),
            "ulid": summary.get("ulid"),
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
        
        # Pass cached index for in-place registry updates
        cache = self.state.get_cache(project_root)
        svc = get_service(project_root)
        result_dto = svc.structure.import_file(
            source=source_file,
            name=name,
        )
        
        # Get structure metadata
        structure_dtos = svc.structure.list()
        new_struct_dto = next((s for s in structure_dtos if s.id == result_dto.id), None)
        
        return {
            "structure_ulid": result_dto.id,
            "name": result_dto.name,
            "slug": result_dto.slug,
            "formula": new_struct_dto.formula if new_struct_dto else "?",
            "n_atoms": new_struct_dto.n_atoms if new_struct_dto else 0,
        }
    
    def _handle_structure_search_online(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search online structures (OPTIMADE + COD).
        
        PR0: Updated to call QVService.OnlineSearch.search_structures() (API facade).
        
        Payload:
            query: str - Chemical formula (e.g., "Si", "MoS2")
            max_results: int - Maximum number of results (default: 10)
            mode: str - Optional search mode: "crystal", "molecule", "auto" (default: "auto")
        """
        from quantumvitas.api import QVService
        from quantumvitas.api.types.online_search import StructureRefDTO
        from quantumvitas.api.utils import OnlineStructureCache  # Re-exported for daemon use
        import uuid
        
        query = self._require_str(payload, "query")
        max_results = payload.get("max_results", 10)
        mode = payload.get("mode", "auto")
        
        # PR0: Call API method (not kernel directly)
        # Note: QVService.OnlineSearch methods are static, but we need a service instance
        # for compatibility. Create a minimal service instance (project_root not needed for online search)
        # Actually, OnlineSearch methods are static, so we can call them directly
        result_dto = QVService.OnlineSearch.search_structures(
            query=query,
            mode=mode,
            limit=max_results,
        )
        
        # Cache results using global cache (PR0: no project_root needed)
        cache = OnlineStructureCache()  # Uses global cache location
        
        # Store session in cache
        source_summary = "+".join(result_dto.providers_queried) if result_dto.providers_queried else "none"
        cache.create_session(result_dto.session_id, query, source_summary)
        
        # Cache candidates (structures will be fetched on demand)
        # PR0: Using OnlineStructureCache and CandidateSummary from api.utils (re-exported for daemon)
        # TODO (PR6): Move caching logic into API facade
        for rank, candidate_dto in enumerate(result_dto.candidates):
            from quantumvitas.api.utils import CandidateSummary  # Re-exported for daemon use
            candidate = CandidateSummary(
                candidate_id=candidate_dto.candidate_id,
                label=candidate_dto.label,
                source=candidate_dto.source,
                source_id=candidate_dto.source_id,
                nsites=candidate_dto.nsites,
                spacegroup=candidate_dto.spacegroup,
                flags=candidate_dto.flags,
                score=candidate_dto.score,
            )
            # OPTIMADE entries: store metadata only (structure fetched later)
            cache.add_candidate_metadata_only(result_dto.session_id, candidate, rank, None)
        
        # Serialize DTO (no hand-serialization)
        return result_dto.to_dict()
    
    def _handle_structure_get_online_candidate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get structure data for an online candidate (from cache or fetch from OPTIMADE).
        
        Payload:
            project_root: str - Path to project root
            session_id: str - Session ID from search
            candidate_id: str - Candidate ID
            supercell: [int, int, int] - Optional supercell (default [1,1,1])
            repeat_boundary: bool - Optional (default false)
            display_mode: str - Optional display mode: "primitive", "supercell", "conventional", "box" (default "primitive")
            box_bounds: [float, float, float, float, float, float] - Optional for box mode
            trace_id: str - Optional trace ID for performance logging
        """
        from quantumvitas.api import QVService
        from quantumvitas.api.utils import DisplayModeParams, build_structure_vis_payload
        from quantumvitas.api.utils import write_structure
        import tempfile
        import numpy as np
        from pathlib import Path
        
        # PR6: project_root is optional (fetch uses global cache, not project-specific)
        project_root = payload.get("project_root")
        if project_root:
            project_root = Path(project_root).resolve()
        session_id = self._require_str(payload, "session_id")
        candidate_id = self._require_str(payload, "candidate_id")
        supercell = tuple(payload.get("supercell", [1, 1, 1]))
        repeat_boundary = payload.get("repeat_boundary", False)
        display_mode = payload.get("display_mode", "primitive")
        box_bounds = payload.get("box_bounds")
        if box_bounds is not None:
            box_bounds = tuple(box_bounds)
        trace_id = payload.get("trace_id")
        
        # Diagnostic logging
        import logging
        logger_local = logging.getLogger(__name__)
        logger_local.info(
            f"[ONLINE] get_candidate trace={trace_id or 'none'} session={session_id} candidate={candidate_id}"
        )
        
        # PR0: Use global cache (not project-specific)
        # Use OnlineStructureCache from api.utils (re-exported for daemon use)
        from quantumvitas.api.utils import OnlineStructureCache
        cache = OnlineStructureCache()  # Uses global cache location
        
        # Always get candidate first (needed for provenance building)
        candidates = cache.get_candidates(session_id)
        candidate = next((c for c in candidates if c.candidate_id == candidate_id), None)
        
        found_session = cache.get_session_info(session_id) is not None
        found_candidate = candidate is not None
        
        logger_local.info(
            f"[ONLINE] get_candidate found_session={found_session} found_candidate={found_candidate}"
        )
        
        if candidate is None:
            logger_local.warning(f"[ONLINE] Candidate {candidate_id} not found in session {session_id}")
            return {
                "ok": False,
                "error": {
                    "code": "CANDIDATE_NOT_FOUND",
                    "message": f"Candidate {candidate_id} not found in session {session_id}",
                    "candidate_id": candidate_id,
                    "session_id": session_id,
                }
            }
        
        structure = cache.get_structure(session_id, candidate_id)
        found_structure = structure is not None
        
        # If not in cache, try fetching from provider (2-step approach)
        if structure is None:
            # PR6: Check if source is an OPTIMADE provider (mp, cod, etc.) or "optimade" (legacy)
            is_optimade_provider = (
                candidate.source in ["mp", "cod", "alexandria", "oqmd", "jarvis", "mcloud"] or
                candidate.source == "optimade" or
                candidate.source.startswith("opt_")
            )
            if is_optimade_provider:
                # Get optimade_base from metadata (stored during search)
                metadata = cache.get_candidate_metadata(session_id, candidate_id)
                optimade_base = metadata.get("optimade_base") if metadata else None
                
                # If no optimade_base in metadata, the API fetch_structure will handle it
                # (PR6: API layer has access to provider config, daemon does not)
                if optimade_base and candidate.source_id:
                    # PR0: Use API facade to fetch structure (temporary passthrough in PR0, will be replaced in PR6)
                    from quantumvitas.api.types.online_search import StructureRefDTO
                    ref_dto = StructureRefDTO(session_id=session_id, candidate_id=candidate_id)
                    try:
                        structure_doc_dto = QVService.OnlineSearch.fetch_structure(ref_dto)
                        # Convert StructureDocDTO to pymatgen Structure for visualization
                        from pymatgen.core import Structure as PMGStructure, Lattice
                        if structure_doc_dto.structure_type == "crystal" and structure_doc_dto.lattice:
                            lattice = Lattice(structure_doc_dto.lattice)
                            species = [atom["element"] for atom in structure_doc_dto.atoms]
                            coords = [atom["coords"] for atom in structure_doc_dto.atoms]
                            structure = PMGStructure(lattice, species, coords, coords_are_cartesian=True)
                        else:
                            # Handle molecule case (no lattice)
                            from pymatgen.core import Molecule as PMGMolecule
                            species = [atom["element"] for atom in structure_doc_dto.atoms]
                            coords = [atom["coords"] for atom in structure_doc_dto.atoms]
                            structure = PMGMolecule(species, coords)
                        
                        # Cache the fetched structure
                        # Find rank
                        rank = next((i for i, c in enumerate(candidates) if c.candidate_id == candidate_id), 0)
                        # Update candidate with structure info
                        candidate.nsites = len(structure)
                        cache.add_candidate(session_id, candidate, structure, rank)
                    except Exception as e:
                        logger_local.warning(f"[ONLINE] Failed to fetch structure via API: {e}")
                        structure = None
        
        if structure is None:
            logger_local.error(f"[ONLINE] Structure not found and could not be fetched for candidate {candidate_id}")
            return {
                "ok": False,
                "error": {
                    "code": "STRUCTURE_NOT_FOUND",
                    "message": f"Structure for candidate {candidate_id} not found in cache and could not be fetched",
                    "candidate_id": candidate_id,
                    "session_id": session_id,
                }
            }
        
        # CRITICAL: Convert online structure to the exact same internal representation as project structures
        # This ensures online and project use the same pipeline byte-for-byte.
        # 
        # The shared pipeline (_build_structure_vis_payload -> build_display_atoms) already:
        # - Canonicalizes the structure (wraps frac coords into [0,1) for periodic dims)
        # - Handles all display modes (primitive, supercell, conventional, boundary repeat)
        # - Computes bonds from the exact same atom list that is rendered
        #
        # We only need to ensure the structure is in primitive form (like project structures),
        # then pass it to the shared pipeline. The pipeline will handle canonicalization.
        
        # Get primitive structure (project structures are typically already primitive)
        # This ensures online structures match the representation of project structures
        try:
            structure = structure.get_primitive_structure()
            logger_local.debug(f"[ONLINE] Converted to primitive: n_sites={len(structure)}")
        except Exception as e:
            logger_local.warning(f"Failed to get primitive structure, using as-is: {e}")
        
        logger_local.info(f"[ONLINE] get_candidate found_structure={found_structure} has_raw=<checking>")
        
        # Get candidate metadata for provenance
        metadata = cache.get_candidate_metadata(session_id, candidate_id) or {}
        optimade_base = metadata.get("optimade_base")
        
        # Get optimade_raw from structure meta if available
        optimade_raw = None
        try:
            import sqlite3
            import json
            conn = sqlite3.connect(cache.db_path)
            try:
                cursor = conn.cursor()
                # Get structure_key from candidate
                cursor.execute("""
                    SELECT structure_key FROM candidates
                    WHERE session_id = ? AND candidate_id = ?
                """, (session_id, candidate_id))
                row = cursor.fetchone()
                if row and row[0]:
                    structure_key = row[0]
                    # Get meta from structures table
                    cursor.execute("""
                        SELECT meta FROM structures WHERE structure_key = ?
                    """, (structure_key,))
                    meta_row = cursor.fetchone()
                    if meta_row and meta_row[0]:
                        meta_data = json.loads(meta_row[0].decode('utf-8'))
                        optimade_raw = meta_data.get("optimade_raw")
            finally:
                conn.close()
        except Exception as e:
            logger_local.debug(f"Could not retrieve optimade_raw from cache: {e}")
        
        has_raw = optimade_raw is not None
        logger_local.info(f"[ONLINE] get_candidate found_structure={found_structure} has_raw={has_raw}")
        
        # Build provenance from OPTIMADE data using shared helper
        provenance = None
        if candidate.source == "optimade" and optimade_raw:
            try:
                optimade_data = optimade_raw.get("data", {})
                optimade_attrs = optimade_data.get("attributes", {})
                
                # Extract provider/database from base URL
                provider = "main"  # Default
                database = "unknown"
                if optimade_base:
                    # Parse: https://optimade.materialscloud.org/main/mc3d-pbe-v1
                    parts = optimade_base.rstrip("/").split("/")
                    if len(parts) >= 2:
                        provider = parts[-2] if parts[-2] in ["main", "archive"] else "main"
                        database = parts[-1] if parts[-1] and parts[-1] not in ["v1", "structures"] else "unknown"
                    elif len(parts) == 1 and parts[0]:
                        # Just database name
                        database = parts[0]
                
                # Use shared helper function
                provenance = extract_provenance(
                    provider=provider,
                    database=database,
                    base_url=optimade_base or "",
                    optimade_id=candidate.source_id,
                    attributes=optimade_attrs,
                    raw=optimade_raw,
                )
            except Exception as e:
                logger_local.warning(f"Failed to build provenance: {e}")
                provenance = {
                    "source_name": "Materials Cloud OPTIMADE",
                    "provider": "main",
                    "database": "unknown",
                    "base_url": optimade_base or "",
                    "optimade_id": candidate.source_id,
                }
        elif candidate.source == "cod":
            provenance = {
                "source_name": "Crystallography Open Database (COD)",
                "provider": "cod",
                "database": "cod",
                "cod_id": candidate.source_id,
            }
        
        # CRITICAL: Use the EXACT same pipeline as project structures
        # Build visualization data using shared payload builder
        # Use provided viewer params (same as project structures)
        params = DisplayModeParams(
            mode=display_mode,
            supercell=supercell if display_mode == "supercell" else None,
            box_bounds=box_bounds if display_mode == "box" else None,
            repeat_boundary=repeat_boundary,
        )
        
        # Use kernel payload builder (same transformation as project structures)
        # This pipeline:
        # - Canonicalizes structure (wraps frac coords into [0,1))
        # - Builds display atoms for the chosen mode
        # - Computes bonds from the exact same atom list that is rendered
        # - All using Cartesian coordinates only
        vis_payload = build_structure_vis_payload(
            structure,
            params,
            structure_meta={"structure_ulid": f"online:{candidate_id}"},
        )
        
        # CRITICAL: Payload contract - atoms contains ALL display atoms
        # Convert to format expected by frontend (atoms with both cart and frac coords)
        # vis_payload["atoms"] already contains ALL display atoms (including boundary)
        atoms_data = []
        for atom in vis_payload.get("atoms", []):
            atoms_data.append({
                "position": atom["cart_coords"],  # Cartesian for backward compatibility
                "cart_coords": atom["cart_coords"],  # Explicit cartesian
                "frac_coords": atom["frac_coords"],  # Fractional coordinates (required for supercell/boundary)
                "symbol": atom["element"],
                "color": atom["color"],
                "radius": atom["radius"],
                "is_boundary": atom.get("is_boundary", False),  # Preserve boundary flag
            })
        # boundary_atoms is UI metadata only (already included in atoms_data)
        boundary_atoms_data = []
        for atom in vis_payload.get("boundary_atoms", []):
            boundary_atoms_data.append({
                "position": atom["cart_coords"],
                "cart_coords": atom["cart_coords"],
                "frac_coords": atom["frac_coords"],
                "symbol": atom["element"],
                "color": atom["color"],
                "radius": atom["radius"],
            })
        
        # CRITICAL: Bonds must use idx1/idx2 schema and reference atoms_data array
        # Shared pipeline already validates this, but we verify again
        bonds_data = []
        max_bond_idx = -1
        atoms_data_len = len(atoms_data)
        
        for bond in vis_payload.get("bonds", []):
            # Shared pipeline guarantees idx1/idx2 (no atom1/atom2)
            idx1 = bond["idx1"]
            idx2 = bond["idx2"]
            max_bond_idx = max(max_bond_idx, idx1, idx2)
            bonds_data.append({
                "idx1": idx1,
                "idx2": idx2,
                "coord1": bond.get("coord1", []),
                "coord2": bond.get("coord2", []),
                "distance": bond.get("distance", 0.0),
            })
        
        # HARD ASSERT: bonds must reference atoms_data array
        if bonds_data and max_bond_idx >= atoms_data_len:
            error_msg = (
                f"INVALID ONLINE PAYLOAD: bonds reference invalid atom indices. "
                f"maxBondIndex={max_bond_idx} >= atoms_len={atoms_data_len}. "
                f"Shared pipeline should have caught this."
            )
            logger_local.error(f"[ONLINE] {error_msg}")
            raise ValueError(error_msg)
        
        # EVIDENCE: Log online payload structure for comparison
        boundary_atoms_data_len = len(boundary_atoms_data)
        bonds_data_len = len(bonds_data)
        
        logger_local.info(
            f"[ONLINE] PAYLOAD_EVIDENCE candidate_id={candidate_id} "
            f"atoms_len={atoms_data_len} boundary_atoms_len={boundary_atoms_data_len} "
            f"bonds_len={bonds_data_len} maxBondIndex={max_bond_idx} "
            f"maxBondIndex_valid={max_bond_idx < atoms_data_len if bonds_data else True}"
        )
        if bonds_data:
            first_bond_keys = list(bonds_data[0].keys())
            logger_local.info(
                f"[ONLINE] PAYLOAD_EVIDENCE firstBondKeys={first_bond_keys} "
                f"firstBond={bonds_data[0]} secondBond={bonds_data[1] if len(bonds_data) > 1 else None}"
            )
        
        vis_data = {
            "atoms": atoms_data,
            "boundary_atoms": boundary_atoms_data,
            "bonds": bonds_data,
            "lattice": vis_payload["lattice"],
            "supercell": supercell if display_mode == "supercell" else [1, 1, 1],
            "display_mode": display_mode,
        }
        
        # Also return structure JSON for detail panel
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            tmp_path = Path(tmp.name)
            write_structure(structure, tmp_path)
            structure_json = tmp_path.read_text()
            tmp_path.unlink()
        
        # Extract formula from OPTIMADE attributes if available (preferred over pymatgen composition)
        formula = structure.composition.reduced_formula  # Fallback
        if candidate.source == "optimade" and optimade_raw:
            optimade_data = optimade_raw.get("data", {})
            optimade_attrs = optimade_data.get("attributes", {})
            # Prefer OPTIMADE formula attributes
            opt_formula = optimade_attrs.get("chemical_formula_reduced") or optimade_attrs.get("chemical_formula_descriptive")
            if opt_formula:
                formula = opt_formula
        
        result = {
            "structure_vis": vis_data,
            "structure_json": structure_json,
            "formula": formula,
            "n_atoms": len(structure),
            "n_species": len(structure.composition),
        }
        
        # Include perf metrics from payload builder
        if "perf" in vis_payload:
            result["perf"] = vis_payload["perf"]
            # REMOVED: Old viewer log that showed incorrect outAtoms
            # The shared pipeline already logs [viz] with correct atom counts
        
        # Include provenance
        if provenance:
            result["provenance"] = provenance
        
        return result
    
    def _handle_structure_list_providers(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List available online structure providers.
        
        Payload:
            refresh_registry: bool - Optional, if True force refresh OPTIMADE provider registry cache
        """
        from quantumvitas.api import QVService
        
        refresh_registry = payload.get("refresh_registry", False)
        
        # Call API method
        result_dto = QVService.OnlineSearch.list_providers(refresh_registry=refresh_registry)
        
        # Serialize DTO (no hand-serialization)
        return result_dto.to_dict()
    
    def _handle_structure_update_online_sources(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update online structure source settings.
        
        Payload:
            patch: dict - OnlineSourcesPatchDTO with fields to update
        """
        from quantumvitas.api import QVService
        from quantumvitas.api.types.online_search import (
            OnlineSourcesPatchDTO,
            ProviderPatchDTO,
            MaterialsProjectPatchDTO,
        )
        
        patch_dict = payload.get("patch", {})
        
        # Convert dict to DTO
        optimade_providers = None
        if "optimade_providers" in patch_dict:
            optimade_providers = [
                ProviderPatchDTO(provider_key=p["provider_key"], enabled=p["enabled"])
                for p in patch_dict["optimade_providers"]
            ]
        
        materials_project = None
        if "materials_project" in patch_dict:
            mp_dict = patch_dict["materials_project"]
            materials_project = MaterialsProjectPatchDTO(
                enabled=mp_dict.get("enabled"),
                api_key=mp_dict.get("api_key"),
            )
        
        patch_dto = OnlineSourcesPatchDTO(
            optimade_providers=optimade_providers,
            pubchem_enabled=patch_dict.get("pubchem_enabled"),
            materials_project=materials_project,
            timeout_seconds=patch_dict.get("timeout_seconds"),
            max_results_per_provider=patch_dict.get("max_results_per_provider"),
            max_total_results=patch_dict.get("max_total_results"),
        )
        
        # Call API method
        result_dto = QVService.OnlineSearch.update_online_sources(patch_dto)
        
        # Serialize DTO (no hand-serialization)
        return {"settings": result_dto.to_dict()}
    
    def _handle_structure_import_online_candidate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Import an online candidate structure into the project.
        
        Payload:
            project_root: str - Path to project root
            session_id: str - Session ID from search
            candidate_id: str - Candidate ID
            name: str - Optional structure name
        """
        from quantumvitas.api import QVService
        import tempfile
        
        project_root = self._require_path(payload, "project_root")
        session_id = self._require_str(payload, "session_id")
        candidate_id = self._require_str(payload, "candidate_id")
        name = payload.get("name")
        
        # Load structure from cache
        cache_dir = project_root / "structures" / "cache"
        from quantumvitas.api.utils import OnlineStructureCache
        cache = OnlineStructureCache(cache_dir)
        
        structure = cache.get_structure(session_id, candidate_id)
        if structure is None:
            raise ValueError(f"Candidate {candidate_id} not found in cache")
        
        # Get candidate info for default name
        candidates_list = cache.get_candidates(session_id)
        candidate = next((c for c in candidates_list if c.candidate_id == candidate_id), None)
        default_name = candidate.label if candidate else structure.composition.reduced_formula
        
        # Canonicalize structure (wrap coords, stable species ordering)
        canonicalize_structure(structure)
        
        # Generate unique name and slug
        cache = self.state.get_cache(project_root)
        config = cache.config
        structures = config.setdefault("structures", [])
        existing_slugs = cache.svc.collect_slugs(structures)
        
        structure_name = name or default_name
        final_name, final_slug = generate_unique_name_and_slug(
            kind="structure",
            preferred_name=structure_name,
            existing_slugs=existing_slugs,
        )
        
        # Write structure file
        dest_path = project_root / "structures" / f"{final_slug}.json"
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        meta = meta_from_name(
            name=final_name,
            kind="structure",
            path=str(dest_path),
        )
        
        # Add provenance metadata
        candidates_for_provenance = cache.get_candidates(session_id)
        query_label = candidates_for_provenance[0].label if candidates_for_provenance else ""
        provenance = {
            "source": candidate.source if candidate else "unknown",
            "source_id": candidate.source_id if candidate else "",
            "query": query_label,
            "fetched_at": int(time.time()),
            "score": candidate.score if candidate else 0.0,
            "flags": candidate.flags if candidate else [],
        }
        
        # Store provenance in structure metadata (under extra field)
        write_structure(structure, dest_path, metadata=meta)
        
        # Add provenance to structure JSON file
        import json
        structure_data = json.loads(dest_path.read_text())
        if "extra" not in structure_data:
            structure_data["extra"] = {}
        structure_data["extra"]["online_provenance"] = provenance
        dest_path.write_text(json.dumps(structure_data, indent=2))
        
        # Add to project config
        entry = {
            "structure_ulid": meta.ulid,
        }
        structures.append(entry)
        cache.svc.save_project_config(config)
        
        # Update registry
        cache_state = self.state.get_cache(project_root)
        resolved = self._require_structure_ref(cache_state.svc, final_slug, config=config)
        if cache_state.index is not None:
            cache_state.svc.update_registry_add_structure(cache_state.index, resolved.meta, dest_path)
        
        return {
            "new_structure_ulid": meta.ulid,
            "name": meta.name,
            "slug": meta.slug,
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

        svc = get_service(project_root)
        old_struct = svc.structure.get(selector)
        old_name = old_struct.name if old_struct else selector
        result_dto = svc.structure.update_meta(selector, new_name=new_name)

        return {
            "success": True,
            "old_name": old_name,
            "new_name": result_dto.name,
            "new_slug": result_dto.slug,
        }
    
    def _handle_can_delete_structure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if structure can be deleted.

        Payload:
            project_root: str - Path to project root
            selector: str - Structure selector
        """
        project_root = self._require_path(payload, "project_root")
        selector = self._require_str(payload, "selector")

        svc = get_service(project_root)
        return svc.structure.can_delete(selector)
    
    def _handle_delete_structure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete a structure.

        Payload:
            project_root: str - Path to project root
            selector: str - Structure selector
            force: bool - Force delete even if used by calculations
        """
        project_root = self._require_path(payload, "project_root")
        selector = self._require_str(payload, "selector")
        force = payload.get("force", False)

        svc = get_service(project_root)

        # Get structure name before deletion for response
        struct_dto = svc.structure.get(selector)
        structure_name = struct_dto.name if struct_dto else selector

        svc.structure.delete(selector, force=force)

        return {
            "success": True,
            "name": structure_name,
        }
    
    # -------------------------------------------------------------------------
    # Calculation creation handlers
    # -------------------------------------------------------------------------
    
    def _handle_list_calculation_templates(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List available calculation templates.
        """
        templates = list_calculation_templates()
        
        return {
            "templates": templates,
            "count": len(templates),
        }
    
    def _handle_create_calculation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new calculation.
        
        Payload:
            project_root: str - Path to project root
            name: str - Calculation name
            structure: str - Optional structure selector
            template: str - Optional template name
        """
        project_root = self._require_path(payload, "project_root")
        name = self._require_str(payload, "name")
        structure = payload.get("structure")
        template = payload.get("template")
        
        # Pass cached index and config for in-place registry updates
        cache = self.state.get_cache(project_root)
        svc = get_service(project_root)
        result = svc.project.init_calculation(
            name=name,
            structure_selector=structure,
            template=template,
            index=cache.index,
            config=cache.config,
        )
        
        # Get calculation details
        calculation_dtos = svc.calculation.list()
        new_wf_dto = next((w for w in calculation_dtos if w.id == result.meta.ulid), None)
        
        return {
            "calc_ulid": result.meta.ulid,  # Short alias used by GUI
            "calculation_id": result.meta.ulid,
            "calculation_ulid": result.meta.ulid,  # Explicit ULID for UI to use
            "name": result.meta.name,
            "slug": result.meta.slug,
            "n_steps": new_wf_dto.n_steps if new_wf_dto else 0,
        }
    
    # -------------------------------------------------------------------------
    # Calculation management handlers
    # -------------------------------------------------------------------------
    
    def _handle_rename_calculation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rename a calculation.
        
        Payload:
            project_root: str - Path to project root
            calculation_ulid: str - Calculation ULID (preferred)
            selector: str - Calculation selector (legacy, for backwards compat)
            new_name: str - New name
        """
        project_root = self._require_path(payload, "project_root")
        calculation_ulid = payload.get("calculation_ulid")
        selector = payload.get("selector")
        
        if not calculation_ulid and not selector:
            raise ValueError("Either calculation_ulid or selector must be provided")
        
        # Prefer ULID, fallback to selector for backwards compat
        target = calculation_ulid if calculation_ulid else selector
        new_name = self._require_str(payload, "new_name")
        
        # Pass cached index and config for in-place registry updates
        cache = self.state.get_cache(project_root)
        svc = get_service(project_root)
        result = svc.calculation.rename(
            selector=target,
            new_name=new_name,
            index=cache.index,
            config=cache.config,
        )

        return result
    
    def _handle_can_delete_calculation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if calculation can be deleted.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector (slug/name/ULID, resolved to ULID here)
        """
        import logging
        
        logger = logging.getLogger(__name__)
        
        project_root = self._require_path(payload, "project_root")
        selector = payload.get("calculation") or payload.get("selector")
        
        # Validate selector
        if not selector:
            return {
                "ok": False,
                "error": {
                    "code": "invalid_argument",
                    "message": "calculation selector must be provided"
                }
            }
        
        if not isinstance(selector, str):
            return {
                "ok": False,
                "error": {
                    "code": "invalid_argument",
                    "message": f"calculation selector must be a string, got {type(selector).__name__}"
                }
            }
        
        selector = selector.strip()
        if not selector:
            return {
                "ok": False,
                "error": {
                    "code": "invalid_argument",
                    "message": "calculation selector must be a non-empty string"
                }
            }
        
        # Resolve selector to ULID at boundary
        if is_ulid_like(selector):
            calculation_ulid = selector
        else:
            try:
                calculation_resolved = self._resolve_calculation_with_fallback(project_root, selector)
                calculation_ulid = calculation_resolved.ulid
            except Exception as e:
                return {
                    "ok": False,
                    "error": {
                        "code": "not_found",
                        "message": f"Calculation not found: {str(e)}"
                    }
                }
        
        # Use domain API
        svc = get_service(project_root)
        return svc.calculation.can_delete(calculation_ulid)
    
    def _handle_delete_calculation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete a calculation.
        
        Payload:
            project_root: str - Path to project root
            calculation_ulid: str - Calculation ULID (preferred)
            selector: str - Calculation selector (legacy, for backwards compat)
            force: bool - Force delete
        """
        import logging
        
        logger = logging.getLogger(__name__)
        
        project_root = self._require_path(payload, "project_root")
        calculation_ulid = payload.get("calculation_ulid")
        selector = payload.get("selector")
        
        # Validate selector at boundary
        if not calculation_ulid and not selector:
            return {
                "ok": False,
                "error": {
                    "code": "invalid_argument",
                    "message": "Either calculation_ulid or selector must be provided"
                }
            }
        
        # Validate selector is a non-empty string if provided
        if selector is not None:
            if not isinstance(selector, str):
                logger.warning(
                    f"[DELETE_CALCULATION] Invalid selector type: {type(selector).__name__}, "
                    f"expected string. Returning invalid_argument."
                )
                return {
                    "ok": False,
                    "error": {
                        "code": "invalid_argument",
                        "message": f"selector must be a string, got {type(selector).__name__}"
                    }
                }
            selector = selector.strip()
            if not selector:
                logger.warning(
                    "[DELETE_CALCULATION] Empty selector provided. Returning invalid_argument."
                )
                return {
                    "ok": False,
                    "error": {
                        "code": "invalid_argument",
                        "message": "selector must be a non-empty string"
                    }
                }
        
        # Determine selector type for logging
        if calculation_ulid:
            selector_type = "ulid" if is_ulid_like(calculation_ulid) else "invalid"
            target_selector = calculation_ulid
        else:
            selector_type = "ulid" if is_ulid_like(selector) else ("slug" if "/" not in selector and "\\" not in selector else "path")
            target_selector = selector
        
        # ALWAYS-ON boundary log
        logger.info(
            f"[DELETE_CALCULATION] endpoint=DELETE_CALCULATION "
            f"selector='{target_selector}' selector_type={selector_type}"
        )
        
        # Resolve selector to ULID at boundary
        if calculation_ulid:
            # Already a ULID, validate it
            try:
                calculation_ulid = validate_ulid(calculation_ulid, kind="calculation")
            except ValueError as e:
                return {
                    "ok": False,
                    "error": {
                        "code": "invalid_argument",
                        "message": str(e)
                    }
                }
        else:
            # Resolve selector to ULID
            try:
                calculation_resolved = self._resolve_calculation_with_fallback(project_root, selector)
                calculation_ulid = calculation_resolved.ulid
                logger.info(
                    f"[DELETE_CALCULATION] Resolved selector '{selector}' -> ulid={calculation_ulid}"
                )
            except Exception as e:
                return {
                    "ok": False,
                    "error": {
                        "code": "not_found",
                        "message": f"Calculation not found: {str(e)}"
                    }
                }
        
        force = payload.get("force", False)
        
        # Get calculation name before deletion for response
        try:
            svc = get_service(project_root)
            check = svc.calculation.can_delete(calculation_ulid)
            calculation_name = check.get("calculation_name", calculation_ulid)
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "handler_error",
                    "message": f"Failed to check calculation: {str(e)}"
                }
            }
        
        svc = get_service(project_root)
        svc.calculation.delete(calculation_ulid)
        
        # Invalidate cache after mutation
        self.state.invalidate_cache(project_root)
        
        return {
            "success": True,
            "name": calculation_name,
        }
    
    # -------------------------------------------------------------------------
    # Step handlers
    # -------------------------------------------------------------------------
    
    def _handle_get_step_detail(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get step detail.
        
        GUI → Daemon → Backend API mapping:
        - GUI: StepDetailPanel calls 'get_step_detail' with calculation.slug and step.id (ULID)
        - Daemon: _handle_get_step_detail() resolves calculation slug to ULID at boundary
        - Backend: QVService.get_step_detail() requires calculation_ulid (ULID only)
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector (GUI uses calculation.slug, resolved to ULID here)
            step: str - Step selector (GUI uses step.id ULID from calculation.steps[])
        
        Returns:
            Step detail dict with id, name, slug, step_type, parameters, etc.
        
        Error Handling:
            - If step file is missing (ghost step), QVService.get_step_detail raises ResourceNotFoundError
            - This is caught by handle_request() and converted to RPC error response:
              { ok: False, error: { code: "resource_not_found", kind: "step", ... } }
            - The RPC always resolves (never hangs) - either with data or with an error
        """
        import logging
        from quantumvitas.api import QVService
        
        logger = logging.getLogger(__name__)
        # Replace is_resolution_debug_enabled with get_settings
        settings = QVService.get_settings()
        debug_enabled = settings.get("debug_resolution", False)
        
        project_root = self._require_path(payload, "project_root")
        calculation_selector = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        
        # Resolve calculation selector to ULID (kind-constrained)
        # This is the boundary where we accept slug/name but convert to ULID
        if is_ulid_like(calculation_selector):
            calculation_ulid = calculation_selector
        else:
            # Resolve slug/name to ULID with kind constraint
            # ALWAYS log boundary resolves (not gated by debug flag)
            calculation_resolved = self._resolve_calculation_with_fallback(project_root, calculation_selector)
            calculation_ulid = calculation_resolved.meta.ulid
            # Determine selector type for logging
            selector_type = "slug" if calculation_selector in [calculation_resolved.meta.slug] else "name"
            logger.info(
                f"[BOUNDARY_RESOLVE] endpoint=GET_STEP_DETAIL selector='{calculation_selector}' "
                f"selector_type={selector_type} expected_kind=calculation "
                f"resolved_ulid={calculation_ulid} resolved_kind={calculation_resolved.meta.kind} "
                f"project_root={project_root}"
            )
        
        # Replace validate_ulid with is_ulid_like check
        if not is_ulid_like(calculation_ulid):
            from quantumvitas.api.errors import InvalidArgumentError
            raise InvalidArgumentError(f"Expected ULID, got: {calculation_ulid}")
        
        # DEBUG: Log the step identifier provided by UI (gated by debug flag)
        is_ulid = len(step) == 26 and step.startswith("01")
        if debug_enabled:
            logger.info(
                f"[STEP_DETAIL_RPC] UI provided step identifier: '{step}' "
                f"(is_ulid={is_ulid}, len={len(step)}, expected_kind=step)"
            )
        if not is_ulid:
            # Always log warnings about non-ULID step identifiers (not gated)
            import traceback
            logger.warning(
                f"[STEP_DETAIL_RPC] WARNING: Step identifier is NOT a ULID! "
                f"Value='{step}', Type={type(step).__name__}. "
                f"This may cause slug collision issues. Call stack:\n"
                f"{''.join(traceback.format_stack()[-5:-1])}"
            )
        
        # Use domain accessor API - get_step_detail returns full step info
        svc = get_service(project_root)
        result = svc.calculation.get_step_detail(calculation_ulid, step)

        return result
    
    def _handle_update_step_params(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update step parameters.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            step: str - Step selector
            parameters: Dict[str, Dict[str, Any]] - Namelist parameters to update
            cards: Optional[Dict] - Card data to update
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        parameters = payload.get("parameters", {})
        cards = payload.get("cards")
        parameter_scan = payload.get("parameter_scan")
        
        # Resolve calculation selector to ULID at boundary
        import logging
        
        logger = logging.getLogger(__name__)
        
        # INSTRUMENTATION: Log RPC handler invocation
        logger.info(f"[RPC] update_step_params invoked: step={step}, calculation={calculation}, "
                    f"parameters_keys={list(parameters.keys())}, "
                    f"parameter_scan={parameter_scan is not None and parameter_scan or 'None'}")
        
        if is_ulid_like(calculation):
            calculation_ulid = calculation
        else:
            calculation_resolved = self._resolve_calculation_with_fallback(project_root, calculation)
            calculation_ulid = calculation_resolved.ulid
        
        # Use domain API (supports parameters, cards, and parameter_scan)
        svc = get_service(project_root)
        params = {}
        if parameters:
            params["parameters"] = parameters
        if cards:
            params["cards"] = cards
        if parameter_scan is not None:
            params["parameter_scan"] = parameter_scan

        step_dto = svc.calculation.update_step_params(
            calc_selector=calculation_ulid,
            step_selector=step,
            params=params,
        )
        # Return full step detail for v0 compat
        return svc.calculation.get_step_detail(calculation_ulid, step)
    
    def _handle_promote_relax_structure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Promote a relax step's generated structure to a project resource.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            step: str - Step selector (ULID)
            name: Optional[str] - Name for the new structure
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        name = payload.get("name")
        
        # Pass cached index and config to avoid rebuilding ResourceIndex
        cache = self.state.get_cache(project_root)
        svc = get_service(project_root)
        result = svc.structure.promote_relax_structure(
            calculation_selector=calculation,
            step_selector=step,
            name=name,
            index=cache.index,
            config=cache.config,
        )
        
        # Invalidate cache since we added a new structure
        self.state.invalidate_cache(project_root)

        # StructureDTO doesn't have absolute_path, compute relative path from slug
        structure_rel_path = f"structures/{result.meta.slug}.json"

        return {
            "success": True,
            "structure": {
                "ulid": result.meta.ulid,
                "name": result.meta.name,
                "path": structure_rel_path,
            },
        }
    
    def _handle_get_common_cards(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get view models for common cards (K_POINTS, etc.).
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector (slug/name/ULID, resolved to ULID here)
            step: str - Step selector
        """
        import logging
        
        logger = logging.getLogger(__name__)
        
        project_root = self._require_path(payload, "project_root")
        calculation_selector = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        
        # Resolve calculation selector to ULID at boundary
        if is_ulid_like(calculation_selector):
            calculation_ulid = calculation_selector
        else:
            calculation_resolved = self._resolve_calculation_with_fallback(project_root, calculation_selector)
            calculation_ulid = calculation_resolved.ulid
        
        # Use domain API
        svc = get_service(project_root)
        return svc.calculation.get_common_cards(calculation_ulid, step)

    def _handle_set_common_card(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Set a common card from view model.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            step: str - Step selector
            card_name: str - Card name (e.g., "K_POINTS")
            view_model: Dict - View model dict (from UI)
            
        Returns:
            Updated step detail dict
        """
        import logging
        
        logger = logging.getLogger(__name__)
        
        project_root = self._require_path(payload, "project_root")
        calculation_selector = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        card_name = self._require_str(payload, "card_name")
        view_model = payload.get("view_model", {})
        if not isinstance(view_model, dict):
            raise ValueError("view_model must be a dict")
        
        # Resolve calculation selector to ULID at boundary
        if is_ulid_like(calculation_selector):
            calculation_ulid = calculation_selector
        else:
            calculation_resolved = self._resolve_calculation_with_fallback(project_root, calculation_selector)
            calculation_ulid = calculation_resolved.ulid
        
        cache = self.state.get_cache(project_root)
        
        svc = get_service(project_root)
        return svc.calculation.set_common_card(
            calc_selector=calculation_ulid,
            step_selector=step,
            card_name=card_name,
            view_model=view_model,
            index=cache.index,
            config=cache.config,
        )
    
    def _handle_get_pseudo_mapping(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get pseudopotential mapping for a step.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            step: str - Step selector
            
        Returns:
            Dict with species, mapping, pseudo_dir, available_pseudos, warnings
        """
        import logging
        
        logger = logging.getLogger(__name__)
        
        project_root = self._require_path(payload, "project_root")
        calculation_selector = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        
        # Resolve calculation selector to ULID at boundary
        if is_ulid_like(calculation_selector):
            calculation_ulid = calculation_selector
        else:
            calculation_resolved = self._resolve_calculation_with_fallback(project_root, calculation_selector)
            calculation_ulid = calculation_resolved.ulid
        
        cache = self.state.get_cache(project_root)
        
        svc = get_service(project_root)
        return svc.calculation.get_step_pseudo_mapping(
            calc_selector=calculation_ulid,
            step_selector=step,
            index=cache.index,
            config=cache.config,
        )
    
    def _handle_set_pseudo_mapping(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Set pseudopotential mapping for a step.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            step: str - Step selector
            mapping: Dict[str, str] - Species -> pseudo filename mapping
            pseudo_dir: Optional[str] - Pseudo directory path
            
        Returns:
            Updated step detail dict
        """
        import logging
        
        logger = logging.getLogger(__name__)
        
        project_root = self._require_path(payload, "project_root")
        calculation_selector = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        mapping = payload.get("mapping", {})
        if not isinstance(mapping, dict):
            raise ValueError("mapping must be a dict")
        library_preference = payload.get("library_preference")
        
        # Resolve calculation selector to ULID at boundary
        if is_ulid_like(calculation_selector):
            calculation_ulid = calculation_selector
        else:
            calculation_resolved = self._resolve_calculation_with_fallback(project_root, calculation_selector)
            calculation_ulid = calculation_resolved.ulid
        
        cache = self.state.get_cache(project_root)
        
        svc = get_service(project_root)
        return svc.calculation.set_step_pseudo_mapping(
            calc_selector=calculation_ulid,
            step_selector=step,
            mapping=mapping,
            library_preference=library_preference,
            index=cache.index,
            config=cache.config,
        )
    
    def _handle_import_pseudo_files(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Import pseudopotential files into the project pseudo directory.
        
        Handles filename conflicts by auto-renaming with deterministic suffix.
        
        Payload:
            project_root: str - Path to project root
            file_paths: List[str] - List of file paths to import
            
        Returns:
            Dict with:
            - imported: List of successfully imported filenames
            - renamed: Dict of original_name -> new_name for renamed files
            - errors: List of error messages
        """
        project_root = self._require_path(payload, "project_root")
        file_paths = payload.get("file_paths", [])
        if not isinstance(file_paths, list):
            raise ValueError("file_paths must be a list")
        
        svc = get_service(project_root)
        return svc.project.import_pseudo_files(
            file_paths=file_paths,
        )
    
    def _handle_search_legacy_pseudos(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search for pseudopotentials by element using QE legacy tables.
        
        Payload:
            element: str - Element symbol (e.g., "Si", "Mo")
            project_root: Optional[str] - Project root (for config)
            
        Returns:
            Dict with candidates list and errors
        """
        element = self._require_str(payload, "element")
        project_root = payload.get("project_root")
        
        config = None
        if project_root:
            project_root = self._require_path(payload, "project_root")
            cache = self.state.get_cache(project_root)
            config = cache.config
        
        from quantumvitas.api.utils import search_legacy_pseudos
        return search_legacy_pseudos(
            element=element,
            config=config,
        )
    
    def _handle_download_pseudo_by_filename(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Download a pseudopotential by filename from QE network repository.
        
        Payload:
            project_root: str - Path to project root
            filename: str - Exact UPF filename
            dest_dir: Optional[str] - Destination directory (default: project_root/pseudo)
            
        Returns:
            Dict with filename, renamed, skipped, errors
        """
        project_root = self._require_path(payload, "project_root")
        filename = self._require_str(payload, "filename")
        dest_dir = payload.get("dest_dir")
        
        cache = self.state.get_cache(project_root)
        
        dest_path = None
        if dest_dir:
            dest_path = Path(dest_dir)
        
        return download_pseudo_by_filename(
            project_root=project_root,
            filename=filename,
            dest_dir=dest_path,
            config=cache.config,
        )
    
    def _handle_download_pseudo_candidate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Download a pseudopotential from a candidate (URL or filename).
        
        Payload:
            project_root: str - Path to project root
            candidate: Dict with url and/or filename
            dest_dir: Optional[str] - Destination directory
            
        Returns:
            Dict with filename, renamed, skipped, errors
        """
        project_root = self._require_path(payload, "project_root")
        candidate = payload.get("candidate", {})
        if not isinstance(candidate, dict):
            raise ValueError("candidate must be a dict")
        
        dest_dir = payload.get("dest_dir")
        dest_path = None
        if dest_dir:
            dest_path = Path(dest_dir)
        
        # If candidate has URL, use download_pseudo_from_url
        if "url" in candidate:
            return download_pseudo_from_url(
                project_root=project_root,
                url=candidate["url"],
                dest_dir=dest_path,
                preferred_filename=candidate.get("filename"),
            )
        # Otherwise use download_pseudo_by_filename
        elif "filename" in candidate:
            cache = self.state.get_cache(project_root)
            return download_pseudo_by_filename(
                project_root=project_root,
                filename=candidate["filename"],
                dest_dir=dest_path,
                config=cache.config,
            )
        else:
            raise ValueError("candidate must have either 'url' or 'filename'")
    
    def _handle_reset_step_params(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reset step parameters to in-code defaults based on step type.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            step: str - Step selector
        """
        import logging
        
        logger = logging.getLogger(__name__)
        
        project_root = self._require_path(payload, "project_root")
        calculation_selector = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        
        # Resolve calculation selector to ULID at boundary
        if is_ulid_like(calculation_selector):
            calculation_ulid = calculation_selector
        else:
            calculation_resolved = self._resolve_calculation_with_fallback(project_root, calculation_selector)
            calculation_ulid = calculation_resolved.ulid
        
        # Pass cached index and config to avoid rebuilding ResourceIndex
        cache = self.state.get_cache(project_root)
        svc = get_service(project_root)
        result = svc.calculation.reset_step_params(
            calc_selector=calculation_ulid,
            step_selector=step,
            index=cache.index,
            config=cache.config,
        )
        
        # Parameter resets don't change registry (only change step file contents)
        
        return result
    
    def _handle_get_relax_final_structure_preview(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preview final structure from relax/vc-relax step output (NO SIDE EFFECTS).
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            step: str - Step selector (ULID)
        
        Returns:
            Dict with cell, species, positions, volume (preview only, no structure created)
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_step_with_fallback(project_root, calculation, step)
        
        cache = self.state.get_cache(project_root)
        
        svc = get_service(project_root)
        return svc.analysis.get_relax_final_structure_preview(
            calc_selector=calculation,
            step_selector=step,
            index=cache.index,
            config=cache.config,
        )
    
    def _handle_save_relax_final_structure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save final structure from relax/vc-relax step as new Structure resource (IDEMPOTENT).
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            step: str - Step selector (ULID)
            parent_structure_ulid: str - ULID of input structure (for provenance)
            slug_hint: Optional[str] - Hint for structure name/slug
        
        Returns:
            Dict with structure_ulid and already_exists flag
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        parent_structure_ulid = self._require_str(payload, "parent_structure_ulid")
        slug_hint = payload.get("slug_hint")
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_step_with_fallback(project_root, calculation, step)
        
        cache = self.state.get_cache(project_root)
        svc = get_service(project_root)
        
        result = svc.structure.save_relax_final_structure(
            calculation_selector=calculation,
            step_selector=step,
            parent_structure_ulid=parent_structure_ulid,
            slug_hint=slug_hint,
            index=cache.index,
            config=cache.config,
        )
        
        # Structure creation updates registry - rebuild cache
        self._rebuild_registry_after_write(project_root, reason="save_relax_final_structure")
        
        return result
    
    # -------------------------------------------------------------------------
    # Calculation configuration handlers
    # -------------------------------------------------------------------------
    
    def _handle_delete_step(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete a step from a calculation.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector (slug or ULID)
            step: str - Step selector (ULID from calculation.yaml)
        
        Returns:
            Dict with status: "deleted"
        
        Raises:
            ResourceNotFoundError: If calculation or step not found in calculation.yaml
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        
        # For delete operations, we only need to resolve the calculation (not the step)
        # because delete_step_from_calculation handles ghost steps gracefully
        # Resolve calculation with fallback to ensure cache is up-to-date
        self._resolve_calculation_with_fallback(project_root, calculation)
        
        # Pass cached index and config to QVService to avoid rebuilding ResourceIndex
        cache = self.state.get_cache(project_root)
        
        # Delete the step (moves file to trash and removes from calculation.yaml)
        # This will handle ghost steps (missing files) gracefully
        svc = get_service(project_root)
        svc.calculation.remove_step(
            calc_selector=calculation,
            step_selector=step,
        )
        
        # Registry updated in-place by QVService.delete_step_from_calculation (no rebuild needed)
        
        return {
            "status": "deleted",
        }
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # Preset Detection Handlers (Constitution §10.4.1: Detector B is sole state source)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    def _handle_get_preset_catalog(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get preset catalog for UI rendering.
        
        This is the single source of truth for UI preset dimensions, options,
        labels, and scopes. All information is derived from the variants registry.
        
        Payload:
            (empty - no parameters needed)
        
        Returns:
            Dict with catalog structure:
            {
                "dimensions": [
                    {
                        "dimension": str,
                        "label": str,
                        "description": str,
                        "order": int,
                        "options": [{"value": str, "label": str}],
                        "default": str,
                        "scope": {
                            "step_type_gen": "variant_step_types" | "variants",
                            "step_types": List[str] | None,
                            "variants": List[Dict] | None,
                        }
                    }
                ],
                "schema_version": int
            }
        """
        catalog = get_preset_catalog()
        return catalog
    
    def _handle_detect_presets(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect preset values from a calculation's steps.
        
        Per Constitution §10.4.1: Detector B is the sole legitimate source
        for preset/option state. UI should derive all preset state from this.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector (slug or ULID)
        
        Returns:
            Dict with:
                dimension_states: Dict mapping dimension name to detected value or "Custom"
                    Example: {"magnetism": "collinear_lsda", "occupations_scheme": "smearing_gaussian", "precision": "med"}
        """
        from quantumvitas.api.errors import ConfigError
        
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        
        # Resolve calculation with fallback to ensure cache is up-to-date
        resolved = self._resolve_calculation_with_fallback(project_root, calculation)
        # absolute_path points to calculation.yaml, so get the parent directory
        if resolved.absolute_path.name == "calculation.yaml":
            calculation_dir = resolved.absolute_path.parent
        else:
            calculation_dir = resolved.absolute_path

        # Use bundle for preset detection
        # If precision context resolution fails, it will be mapped to ConfigError by map_kernel_exception
        try:
            bundle = get_calculation_preset_bundle(calculation_dir)
        except ConfigError as e:
            # PrecisionContextError is mapped to ConfigError by map_kernel_exception
            # Check if it's a precision context error by checking the error message or context
            if "precision" in str(e).lower() or "context" in str(e).lower():
                return {
                    "ok": False,
                    "error": {
                        "code": "PRECISION_CONTEXT_ERROR",
                        "message": f"Failed to resolve precision context: {e}",
                    },
                }
            # Re-raise other config errors
            raise

        return {
            "dimension_states": bundle["dimension_states"],
        }

    def _handle_detect_workflow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect workflow type from a calculation's step sequence.
        
        This is informational only - does NOT affect execution.
        Per Constitution: workflow is runtime interpretation only.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector (slug or ULID)
        
        Returns:
            Dict with:
                workflow: Detected workflow type string
                    ("SCF", "DOS", "BandStructure", "Relaxation", "Phonon", "MD", "Unknown")
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")

        # Resolve calculation with fallback to ensure cache is up-to-date
        resolved = self._resolve_calculation_with_fallback(project_root, calculation)
        # absolute_path points to calculation.yaml, so get the parent directory
        if resolved.absolute_path.name == "calculation.yaml":
            calculation_dir = resolved.absolute_path.parent
        else:
            calculation_dir = resolved.absolute_path

        # Use bundle for workflow detection
        bundle = get_calculation_preset_bundle(calculation_dir)

        return {
            "workflow": bundle["workflow_type"],
        }

    def _handle_apply_presets_to_step(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply preset options to a step.
        
        Per Constitution §10.3.3: This OVERWRITES preset-related parameters,
        it does NOT merge. Non-preset parameters are preserved.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector (slug or ULID)
            step: str - Step selector (ULID)
            presets: Dict with preset options
                Example: {"spin": "collinear", "soc": "no_soc", "material": "metal"}
            validate_physics: bool (optional, default True) - Validate physics constraints
        
        Returns:
            Dict with:
                status: "applied"
                presets: Updated detected presets for the calculation
        """
        from quantumvitas.api.errors import ValidationError
        
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step_selector = self._require_str(payload, "step")
        presets = payload.get("presets", {})
        validate_physics = payload.get("validate_physics", True)
        
        # Resolve calculation and step
        self._resolve_calculation_with_fallback(project_root, calculation)
        resolved_step = self._resolve_step_with_fallback(project_root, calculation, step_selector)
        
        step_path = resolved_step.path
        
        try:
            apply_presets_to_step(step_path, presets, validate_physics=validate_physics)
        except ValidationError as e:
            # PresetCompilationError is mapped to ValidationError by map_kernel_exception
            # Check if it's a preset compilation error by checking the error message
            if "preset" in str(e).lower() or "compilation" in str(e).lower():
                return {
                    "ok": False,
                    "error": {
                        "code": "INVALID_PRESET",
                        "message": str(e),
                    },
                }
            # Re-raise other validation errors
            raise
        
        # Return updated dimension states for the calculation
        calculation_dir = step_path.parent.parent  # steps/foo.step.yaml -> calculation_dir
        bundle = get_calculation_preset_bundle(calculation_dir)

        return {
            "status": "applied",
            "dimension_states": bundle["dimension_states"],
        }

    def _handle_apply_presets_to_calculation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply preset options to ALL steps in a calculation (BROADCAST).
        Thin wrapper — delegates to QVService.calculation.apply_presets().
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        presets = payload.get("presets", {})
        validate_physics = payload.get("validate_physics", True)

        svc = get_service(project_root)
        return svc.calculation.apply_presets(
            calculation, presets, validate_physics=validate_physics
        )

    def _handle_get_step_preset_footprints(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get preset-related parameter footprints for all steps in a calculation.
        
        This enables the UI to show parameter summary on each step row
        without fetching full step details for every step.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector (slug/name/ULID, resolved to ULID here)
        
        Returns:
            Dict with:
                footprints: Dict mapping step_file name to footprint data
                    {"1_scf.step.yaml": {"params": {}, "spin": "collinear", ...}}
        """
        import logging
        
        logger = logging.getLogger(__name__)
        
        project_root = self._require_path(payload, "project_root")
        calculation_selector = self._require_str(payload, "calculation")
        
        # Resolve calculation selector to ULID (kind-constrained)
        if is_ulid_like(calculation_selector):
            calculation_ulid = calculation_selector
        else:
            # ALWAYS log boundary resolves (not gated by debug flag)
            resolved = self._resolve_calculation_with_fallback(project_root, calculation_selector)
            calculation_ulid = resolved.meta.ulid
            selector_type = "slug" if calculation_selector == resolved.meta.slug else "name"
            logger.info(
                f"[BOUNDARY_RESOLVE] endpoint=GET_STEP_PRESET_FOOTPRINTS selector='{calculation_selector}' "
                f"selector_type={selector_type} expected_kind=calculation "
                f"resolved_ulid={calculation_ulid} resolved_kind={resolved.meta.kind} "
                f"project_root={project_root}"
            )
        
        # Resolve calculation with fallback to ensure cache is up-to-date
        resolved = self._resolve_calculation_with_fallback(project_root, calculation_ulid)
        # absolute_path points to calculation.yaml, so get the parent directory
        if resolved.absolute_path.name == "calculation.yaml":
            calculation_dir = resolved.absolute_path.parent
        else:
            calculation_dir = resolved.absolute_path

        # Use bundle for step footprints
        bundle = get_calculation_preset_bundle(calculation_dir)

        return {
            "footprints": bundle["step_footprints"],
        }

    def _handle_get_calculation_detail(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get detailed calculation information.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector (slug/name/ULID, resolved to ULID here)
        """
        import logging
        from quantumvitas.api import QVService
        
        logger = logging.getLogger(__name__)
        
        project_root = self._require_path(payload, "project_root")
        calculation_selector = self._require_str(payload, "calculation")
        
        # Resolve calculation selector to ULID (kind-constrained)
        # This is the boundary where we accept slug/name but convert to ULID
        if is_ulid_like(calculation_selector):
            calculation_ulid = calculation_selector
        else:
            # Resolve slug/name to ULID with kind constraint
            # ALWAYS log boundary resolves (not gated by debug flag)
            calculation_resolved = self._resolve_calculation_with_fallback(project_root, calculation_selector)
            calculation_ulid = calculation_resolved.meta.ulid
            # Determine selector type for logging
            selector_type = "slug" if calculation_selector == calculation_resolved.meta.slug else "name"
            logger.info(
                f"[BOUNDARY_RESOLVE] endpoint=GET_CALCULATION_DETAIL selector='{calculation_selector}' "
                f"selector_type={selector_type} expected_kind=calculation "
                f"resolved_ulid={calculation_ulid} resolved_kind={calculation_resolved.meta.kind} "
                f"project_root={project_root}"
            )
        
        # Replace validate_ulid with is_ulid_like check
        if not is_ulid_like(calculation_ulid):
            from quantumvitas.api.errors import InvalidArgumentError
            raise InvalidArgumentError(f"Expected ULID, got: {calculation_ulid}")

        # Use domain API
        svc = get_service(project_root)
        return svc.calculation.get_detail(calculation_ulid)
    
    def _handle_reorder_calculation_steps(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reorder calculation steps.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            new_order: List[str] - Step IDs/slugs in new order
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        new_order = payload.get("new_order", [])
        
        if not isinstance(new_order, list):
            raise ValueError("new_order must be a list of step selectors")
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_calculation_with_fallback(project_root, calculation)
        
        # Pass cached index and config to avoid rebuilding ResourceIndex
        cache = self.state.get_cache(project_root)
        svc = get_service(project_root)
        result = svc.calculation.reorder_steps(
            calc_selector=calculation,
            new_order=new_order,
            index=cache.index,
            config=cache.config,
        )
        
        # Reorder doesn't change registry (only changes step order in calculation.yaml)
        
        return result
    
    def _handle_add_step_to_calculation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a new step to a calculation (from scratch, uses QV defaults).
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector (name, slug, or id)
            step_type: str - Type of step (scf, nscf, relax, bands, dos, etc.)
            step_name: str - Name for the new step (optional, defaults to step_type)
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        # step_type_gen is canonical (GEN only for workflow intent)
        step_type_gen = payload.get("step_type_gen")
        if not step_type_gen:
            raise ValueError("Missing required field: step_type_gen")
        step_name = payload.get("step_name", step_type_gen)
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_calculation_with_fallback(project_root, calculation)
        
        svc = get_service(project_root)
        step_dto = svc.calculation.add_step(
            calc_selector=calculation,
            step_type_gen=step_type_gen,
            name=step_name,
        )
        
        # Get updated steps list using list_steps
        steps = svc.calculation.list_steps(calculation)

        # Get calculation details for v0 compat
        calc_detail = svc.calculation.get(calculation)

        # Use dataclasses.asdict for proper serialization (hand-serialization violation fix)
        # Extract only needed fields from StepDTO using asdict

        def _to_step_dict(s):
            """Convert StepDTO to dict - read both fields from DTO (Constitution v1.1)."""
            s_dict = asdict(s)
            # Constitution v1.1: Kernel populates both. Read from DTO, don't convert.
            return {
                "step_ulid": s_dict.get("step_ulid"),
                "step_type_spec": s_dict.get("step_type_spec"),  # canonical SPEC type
                "step_type_gen": s_dict.get("step_type_gen"),  # canonical GEN type from DTO
                "status": s_dict.get("status"),
            }

        return {
            "calculation_id": calc_detail.calc_ulid if calc_detail else None,
            "calculation_name": calc_detail.name if calc_detail else "",
            "calculation_slug": calc_detail.slug if calc_detail else "",
            "structure": calc_detail.structure_ulid if calc_detail else None,
            "steps": [_to_step_dict(s) for s in steps]
        }
    
    # _handle_import_step_from_qe_input removed in M8 — QE-only import feature

    def _handle_change_calculation_structure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Change calculation structure.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector (slug/name/ULID, resolved to ULID here)
            new_structure: str - New structure selector (slug/name/ULID, resolved to ULID here)
            update_steps: bool - Whether to update step structure fields (default True)
        """
        import logging
        from quantumvitas.api import QVService
        
        logger = logging.getLogger(__name__)
        
        project_root = self._require_path(payload, "project_root")
        calculation_selector = self._require_str(payload, "calculation")
        structure_selector = self._require_str(payload, "new_structure")
        update_steps = payload.get("update_steps", True)
        
        # Log UI-provided identifiers
        logger.info(
            f"[CHANGE_CALC_STRUCTURE_RPC] UI provided calculation selector: '{calculation_selector}' "
            f"(is_ulid={is_ulid_like(calculation_selector)})"
        )
        logger.info(
            f"[CHANGE_CALC_STRUCTURE_RPC] UI provided structure selector: '{structure_selector}' "
            f"(is_ulid={is_ulid_like(structure_selector)})"
        )
        
        # Warn if non-ULID selectors are provided
        if not is_ulid_like(calculation_selector):
            logger.warning(
                f"[CHANGE_CALC_STRUCTURE_RPC] WARNING: Non-ULID calculation selector '{calculation_selector}' "
                f"provided by UI. Resolving to ULID at RPC boundary."
            )
        if not is_ulid_like(structure_selector):
            logger.warning(
                f"[CHANGE_CALC_STRUCTURE_RPC] WARNING: Non-ULID structure selector '{structure_selector}' "
                f"provided by UI. Resolving to ULID at RPC boundary."
            )
        
        # Resolve calculation selector to ULID at RPC boundary
        calculation_resolved = self._resolve_calculation_with_fallback(project_root, calculation_selector)
        calculation_ulid = calculation_resolved.ulid
        
        logger.info(
            f"[CHANGE_CALC_STRUCTURE_RPC] Resolved calculation: selector='{calculation_selector}' -> "
            f"ulid={calculation_ulid}, kind={calculation_resolved.meta.kind}"
        )
        
        # Validate structure selector is not project_root
        from pathlib import Path as PathLib
        project_root_path = PathLib(project_root).resolve()
        # Inline path check (replaces QVService.is_path_like)
        def is_path_like(s: str) -> bool:
            return "/" in s or "\\" in s or s.startswith(".")
        # Check if selector is a path that equals project_root
        if is_path_like(structure_selector):
            try:
                structure_selector_path = PathLib(structure_selector).resolve()
                if structure_selector_path == project_root_path:
                    raise ValueError(
                        f"Invalid structure selector: '{structure_selector}' is the project root path. "
                        f"Please provide a valid structure selector (ULID, slug, or name)."
                    )
            except (OSError, ValueError) as e:
                # If it's our validation error, re-raise it
                if "project root path" in str(e):
                    raise
                # Otherwise, it's not a valid path, continue with normal resolution
                pass
        
        # Resolve structure selector to ULID at RPC boundary
        cache = self.state.get_cache(project_root)
        try:
            structure_resolved = self._require_structure_ref(
                cache.svc,
                structure_selector,
                config=cache.config,
            )
        except Exception as e:
            # Check if error is due to project_root being passed as selector
            error_msg = str(e).lower()
            try:
                if PathLib(structure_selector).resolve() == project_root_path:
                    raise ValueError(
                        f"Invalid structure selector: '{structure_selector}' is the project root path. "
                        f"Please provide a valid structure selector (ULID, slug, or name)."
                    ) from e
            except (ValueError, OSError):
                # Not a path, re-raise original error
                pass
            raise
        
        structure_ulid = structure_resolved.ulid
        
        logger.info(
            f"[CHANGE_CALC_STRUCTURE_RPC] Resolved structure: selector='{structure_selector}' -> "
            f"ulid={structure_ulid}, kind={structure_resolved.meta.kind}"
        )
        
        # Use domain API
        svc = get_service(project_root)
        result = svc.calculation.set_structure(
            calc_selector=calculation_ulid,
            structure_selector=structure_ulid,
            update_steps=update_steps,
        )

        return result
    
    def _handle_get_calculation_pseudo_mapping(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get calculation-level pseudopotential mapping.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector (slug/name/ULID, resolved to ULID here)
            
        Returns:
            Dict with species, mapping, species_map, available_pseudos, warnings, sssp_defaults
        """
        import logging
        from quantumvitas.api import QVService
        
        logger = logging.getLogger(__name__)
        # Replace is_resolution_debug_enabled with get_settings
        settings = QVService.get_settings()
        debug_enabled = settings.get("debug_resolution", False)
        
        project_root = self._require_path(payload, "project_root")
        calculation_selector = self._require_str(payload, "calculation")
        
        # Entry logging
        payload_keys = list(payload.keys())
        logger.info(
            f"[HANDLER_GET_CALCULATION_PSEUDO_MAPPING] ENTRY "
            f"payload_keys={payload_keys} "
            f"calculation_selector={calculation_selector}"
        )
        
        # Resolve calculation selector to ULID (kind-constrained)
        # This is the boundary where we accept slug/name but convert to ULID
        if is_ulid_like(calculation_selector):
            calculation_ulid = calculation_selector
        else:
            # Resolve slug/name to ULID with kind constraint
            # ALWAYS log boundary resolves (not gated by debug flag)
            calculation_resolved = self._resolve_calculation_with_fallback(project_root, calculation_selector)
            calculation_ulid = calculation_resolved.meta.ulid
            # Determine selector type for logging
            selector_type = "slug" if calculation_selector == calculation_resolved.meta.slug else "name"
            logger.info(
                f"[BOUNDARY_RESOLVE] endpoint=GET_CALCULATION_PSEUDO_MAPPING selector='{calculation_selector}' "
                f"selector_type={selector_type} expected_kind=calculation "
                f"resolved_ulid={calculation_ulid} resolved_kind={calculation_resolved.meta.kind} "
                f"project_root={project_root}"
            )
        
        # Validate calculation_ulid
        calculation_ulid = validate_ulid(calculation_ulid, kind="calculation")
        
        # Pass cached index and config
        cache = self.state.get_cache(project_root)
        svc = get_service(project_root)
        result = svc.calculation.get_pseudo_mapping(
            calc_selector=calculation_ulid,
            index=cache.index,
            config=cache.config,
        )
        
        # Exit logging
        logger.info(
            f"[HANDLER_GET_CALCULATION_PSEUDO_MAPPING] EXIT "
            f"calculation_ulid={calculation_ulid} "
            f"resolved_ulid={calculation_ulid} "
            f"mapping_keys={list(result.get('mapping', {}).keys())} "
            f"warnings={result.get('warnings', [])}"
        )
        
        return result
    
    def _handle_update_calculation_species_map(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update calculation species_map (pseudopotential mapping).
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            species_map: dict - New species mapping (element -> {pseudopot, mass})
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        species_map = payload.get("species_map", {})
        
        if not isinstance(species_map, dict):
            raise ValueError("species_map must be a dictionary")
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_calculation_with_fallback(project_root, calculation)
        
        # Pass cached index and config to avoid rebuilding ResourceIndex
        cache = self.state.get_cache(project_root)
        svc = get_service(project_root)
        result = svc.calculation.update_species_map(
            calc_selector=calculation,
            species_map=species_map,
            index=cache.index,
            config=cache.config,
        )
        
        return result
    
    def _handle_analyze_project_pseudo_effects(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze pseudo preparation effects (read-only, safe for UI).
        
        Payload:
            project_root: str - Path to project root
            selections: list[dict] - List of pseudo selections (element, requested_basename, etc.)
        
        Returns:
            Dict with actions, warnings, errors (no mutations performed)
        """
        from quantumvitas.api import QVService

        project_root = self._require_path(payload, "project_root")
        selections_data = payload.get("selections", [])

        # Use nested service method
        svc = QVService(project_root)
        report_dict = svc.project.analyze_pseudo_effects(selections_data)

        return report_dict
    
    def _handle_materialize_pseudo_file(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Materialize a pseudo file from sha256 selection to actual file path.
        
        Payload:
            project_root: str - Path to project root
            element: str - Element symbol
            sha256: str - SHA256 hash of the pseudo file
            preferred_basename: Optional[str] - Preferred basename
            
        Returns:
            Dict with success, file_path, source, error, needs_install, archive_asset
        """
        from quantumvitas.api import QVService
        from pathlib import Path
        
        project_root = self._require_path(payload, "project_root")
        element = self._require_str(payload, "element")
        sha256 = self._require_str(payload, "sha256")
        preferred_basename = payload.get("preferred_basename")
        
        svc = get_service(project_root)
        return svc.project.materialize_pseudo_file(
            element=element,
            sha256=sha256,
            preferred_basename=preferred_basename,
        )
    
    def _handle_get_pseudo_options_for_calculation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get pseudo options for a calculation (derives elements from structure).
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            
        Returns:
            Dict with:
            - options_by_element: Dict[str, List[PseudoOption dict]]
        """
        import inspect
        import logging
        from quantumvitas.api import QVService
        from quantumvitas.api import QVService
        
        logger = logging.getLogger(__name__)
        
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        
        # Log entry
        payload_keys = list(payload.keys())
        logger.info(
            f"[GET_PSEUDO_OPTIONS_FOR_CALCULATION] ENTRY "
            f"payload_keys={payload_keys} "
            f"calculation={calculation}"
        )
        
        # Inspect get_calculation_detail signature
        sig = inspect.signature(QVService.get_calculation_detail)
        logger.info(
            f"[GET_PSEUDO_OPTIONS_FOR_CALCULATION] "
            f"inspect.signature(get_calculation_detail)={list(sig.parameters.keys())}"
        )
        
        # Resolve calculation selector to ULID (boundary resolution, consistent with other endpoints)
        if is_ulid_like(calculation):
            calculation_ulid = calculation
        else:
            calculation_resolved = self._resolve_calculation_with_fallback(project_root, calculation)
            calculation_ulid = calculation_resolved.meta.ulid
        
        # Replace validate_ulid with is_ulid_like check
        if not is_ulid_like(calculation_ulid):
            from quantumvitas.api.errors import InvalidArgumentError
            raise InvalidArgumentError(f"Expected ULID, got: {calculation_ulid}")
        
        cache = self.state.get_cache(project_root)

        # Log actual call parameters
        logger.info(
            f"[GET_PSEUDO_OPTIONS_FOR_CALCULATION] "
            f"calling get_calculation_detail with calculation_ulid={calculation_ulid} "
            f"(resolved from selector={calculation})"
        )

        # Use domain API
        svc = get_service(project_root)
        calc_detail = svc.calculation.get_detail(calculation_ulid)

        # Extract elements from structure
        elements: List[str] = []
        structure_ulid = calc_detail.get("structure_ulid")
        if structure_ulid:
            try:
                struct_resolved = self._require_structure_ref(
                    cache.svc, structure_ulid, config=cache.config
                )
                if struct_resolved.absolute_path.exists():
                    structure = read_structure(struct_resolved.absolute_path)
                    elements = sorted(set(str(el) for el in structure.composition.elements))
            except Exception:
                pass
        
        # Fallback to species list from calc_detail
        if not elements:
            species = calc_detail.get("structure_elements", [])
            elements = sorted(set(species))
        
        # Get options (sha256-keyed, filename-first, constitution-compliant)
        from quantumvitas.api import QVService
        svc = get_service(project_root)
        options = svc.project.get_pseudo_options(
            elements=elements,
            config=cache.config,
        )
        
        return {
            "options_by_element": options,
        }
    
    # -------------------------------------------------------------------------
    # Pre-flight check handlers
    # -------------------------------------------------------------------------
    
    def _handle_preflight_check(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform pre-flight checks before running.
        
        Payload:
            project_root: str - Path to project root
            calculation: Optional[str] - Calculation selector
            step: Optional[str] - Step selector
        """
        project_root = self._require_path(payload, "project_root")
        calculation = payload.get("calculation")
        step = payload.get("step")
        
        # Resolve with fallback if selectors provided
        if calculation:
            self._resolve_calculation_with_fallback(project_root, calculation)
        if calculation and step:
            self._resolve_step_with_fallback(project_root, calculation, step)

        # Use domain API
        svc = get_service(project_root)
        return svc.run.preflight(
            calc_selector=calculation,
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
            demo_id: Optional[str] - Demo snapshot ID (default 'si_bands_demo')
        """
        target_dir = self._require_path(payload, "target_dir")
        name = payload.get("name", "demo-si-project")
        demo_id = payload.get("demo_id")
        
        try:
            result = QVService.create_demo_project(
                target_dir=target_dir,
                name=name,
                demo_id=demo_id,
            )
            # Rebuild registry after demo project creation
            project_root = Path(result.get("project_root", target_dir)).resolve()
            self._rebuild_registry_after_write(project_root, "write_operation:create_demo_project")
            return result
        except ValueError as e:
            # Re-raise ValueError as-is (for validation errors like "inside existing project")
            raise
    
    def _handle_list_demo_projects(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List available demo project snapshots.
        
        Payload: (empty)
        
        Returns:
            Dict with demos list and count
        """
        try:
            demos = QVService.list_demo_projects()
            return {
                "demos": demos,
                "count": len(demos),
            }
        except Exception as e:
            # Log error but return empty list rather than raising
            # This ensures the RPC always returns a valid response
            self.log(f"Error listing demo projects: {e}\n{traceback.format_exc()}")
            return {
                "demos": [],
                "count": 0,
            }
    
    # -------------------------------------------------------------------------
    # Analysis handlers
    # -------------------------------------------------------------------------
    
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
            display_mode: str - Optional display mode: "primitive", "supercell", "conventional", "box" (default "primitive")
            box_bounds: [float, float, float, float, float, float] - Optional for box mode: [xmin, xmax, ymin, ymax, zmin, zmax]
            trace_id: str - Optional trace ID for performance logging
        """
        project_root = self._require_path(payload, "project_root")
        selector = self._require_str(payload, "selector")
        supercell = tuple(payload.get("supercell", [1, 1, 1]))
        repeat_boundary = payload.get("repeat_boundary", False)
        display_mode = payload.get("display_mode", "primitive")
        box_bounds = payload.get("box_bounds")
        if box_bounds is not None:
            box_bounds = tuple(box_bounds)
        trace_id = payload.get("trace_id")
        
        svc = get_service(project_root)
        return svc.structure.get_vis_data(
            selector=selector,
            supercell=supercell,
            repeat_boundary=repeat_boundary,
            display_mode=display_mode,
            box_bounds=box_bounds,
        )
    
    def _handle_get_reference_analysis(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get reference analysis data for demo projects.
        
        Returns reference analysis data if the project was created from a demo
        snapshot that includes reference artifacts.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            analysis_type: str - Analysis type ("scf", "dos", "bands")
            
        Returns:
            Reference analysis data dict, or null if not a demo project
            or no reference data exists for the requested type.
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        analysis_type = self._require_str(payload, "analysis_type")
        
        _VALID_ANALYSIS_TYPES = (
            "scf", "dos", "bands", "convergence",
            "trajectory", "neb_trajectory", "field3d",
        )
        if analysis_type not in _VALID_ANALYSIS_TYPES:
            raise ValueError(
                f"Invalid analysis_type: {analysis_type}. "
                f"Must be one of: {', '.join(_VALID_ANALYSIS_TYPES)}"
            )
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_calculation_with_fallback(project_root, calculation)
        
        svc = get_service(project_root)
        result = svc.analysis.get_reference_analysis(
            calculation_selector=calculation,
            analysis_type=analysis_type,
        )
        
        return result

    def _handle_get_analysis(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Operational analysis derivation (raw evidence -> primitive bundle).

        Payload:
            project_root: str
            run_ulid: str
            object_type: str
            transforms: Optional[list[str]]
        """
        project_root = self._require_path(payload, "project_root")
        run_ulid = self._require_str(payload, "run_ulid")
        object_type = self._require_str(payload, "object_type")
        transforms = payload.get("transforms")
        if transforms is not None and not isinstance(transforms, list):
            raise ValueError("transforms must be a list of transform names")

        svc = get_service(project_root)
        return svc.analysis.get_analysis(
            run_ulid=run_ulid,
            object_type=object_type,
            transforms=transforms,
        )

    def _handle_get_analysis_instances_for_step(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Domain B step-scoped enumeration (spec §5.3-B).

        Payload:
            project_root: str
            calculation: str - Calculation selector
            step_ulid: str
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step_ulid = self._require_str(payload, "step_ulid")

        svc = get_service(project_root)
        return svc.analysis.get_analysis_instances_for_step(
            calc_selector=calculation,
            step_ulid=step_ulid,
        )

    def _handle_get_analysis_snapshot(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Explicit provenance replay endpoint (SQLite + CAS snapshot path).

        Payload:
            project_root: str
            run_ulid: str
            object_type: str
        """
        project_root = self._require_path(payload, "project_root")
        run_ulid = self._require_str(payload, "run_ulid")
        object_type = self._require_str(payload, "object_type")

        svc = get_service(project_root)
        return svc.analysis.get_analysis_snapshot(
            run_ulid=run_ulid,
            object_type=object_type,
        )

    def _handle_get_field3d_grid(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Materialize full Field3D grid to .scratch/ for frontend 3D rendering.

        Payload:
            project_root: str
            run_ulid: str
        """
        project_root = self._require_path(payload, "project_root")
        run_ulid = self._require_str(payload, "run_ulid")

        svc = get_service(project_root)
        return svc.analysis.get_field3d_grid(run_ulid=run_ulid)

    def _handle_get_step_digest(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step digest endpoint for Surface B.

        Payload:
            project_root: str
            run_ulid: str
            step_ulid: str
        """
        project_root = self._require_path(payload, "project_root")
        run_ulid = self._require_str(payload, "run_ulid")
        step_ulid = self._require_str(payload, "step_ulid")

        svc = get_service(project_root)
        return svc.analysis.get_step_digest(
            run_ulid=run_ulid,
            step_ulid=step_ulid,
        )

    def _handle_list_raw_files(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Surface A endpoint: list raw files for a step.
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")

        self._resolve_step_with_fallback(project_root, calculation, step)
        svc = get_service(project_root)
        return svc.analysis.list_raw_files(
            calculation_selector=calculation,
            step_selector=step,
        )

    def _handle_read_raw_file(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Surface A endpoint: read raw file content for a step.
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        filename = self._require_str(payload, "filename")
        head_lines = payload.get("head_lines", 1000)
        tail_lines = payload.get("tail_lines", 100)

        self._resolve_step_with_fallback(project_root, calculation, step)
        svc = get_service(project_root)
        return svc.analysis.read_raw_file(
            calculation_selector=calculation,
            step_selector=step,
            filename=filename,
            head_lines=head_lines,
            tail_lines=tail_lines,
        )
    
    def _handle_list_wannier_3d_fixtures(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List available Wannier90 3D test fixtures.
        
        Payload: (none required, or {"fixture_dir": str} for custom path)
        
        Returns:
            List of fixture metadata
        """
        # Default fixture directory
        fixture_dir = Path(__file__).parent.parent.parent / "tests" / "data" / "wannier_3d_test"
        if "fixture_dir" in payload:
            fixture_dir = Path(payload["fixture_dir"])
        
        fixtures = []
        
        # Scan fixture directories
        if fixture_dir.exists():
            for example_dir in sorted(fixture_dir.iterdir()):
                if not example_dir.is_dir():
                    continue
                
                # Look for XSF or BXSF files
                xsf_files = sorted(example_dir.glob("*.xsf"))
                bxsf_files = sorted(example_dir.glob("*.bxsf"))
                
                if xsf_files:
                    # XSF fixture (MLWF)
                    for xsf_file in xsf_files:
                        fixtures.append({
                            "ulid": f"{example_dir.name}_{xsf_file.stem}",
                            "name": f"{example_dir.name} - {xsf_file.stem}",
                            "file_path": str(xsf_file.resolve()),
                            "type": "xsf",
                            "example_dir": example_dir.name,
                        })
                elif bxsf_files:
                    # BXSF fixture (Fermi surface)
                    for bxsf_file in bxsf_files:
                        fixtures.append({
                            "ulid": f"{example_dir.name}_{bxsf_file.stem}",
                            "name": f"{example_dir.name} - {bxsf_file.stem}",
                            "file_path": str(bxsf_file.resolve()),
                            "type": "bxsf",
                            "example_dir": example_dir.name,
                        })
        
        return {"fixtures": fixtures}
    
    def _handle_compile_fixture_volume(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compile fixture volume file (XSF/BXSF) to blob.
        
        Payload:
            file_path: str - Path to XSF or BXSF file
            calc_dir: str - Calculation directory (sandbox output directory)
            
        Returns:
            Dict with artifact_id, kind, metadata, blob_id, preview_blob_id
        """
        from quantumvitas.api import QVService
        
        file_path = Path(self._require_str(payload, "file_path")).resolve()
        calc_dir = Path(self._require_str(payload, "calc_dir")).resolve()
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Detect file type
        file_type = file_path.suffix.lower().lstrip(".")
        band_index = payload.get("band_index", 1)
        
        return parse_volume_artifact(
            file_path=file_path,
            calc_dir=calc_dir,
            file_type=file_type,
            band_index=band_index,
        )
    
    def _handle_list_step_artifacts(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List artifact files (output files) for a step.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            step: str - Step selector (ULID from calculation.yaml)
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_step_with_fallback(project_root, calculation, step)
        
        svc = get_service(project_root)
        return svc.analysis.list_step_artifacts(
            calculation_selector=calculation,
            step_selector=step,
        )
    
    def _handle_read_step_artifact_text(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Read text content from a step artifact file.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            step: str - Step selector (ULID from calculation.yaml)
            artifact_path: str - Path relative to raw directory (e.g., "scf.out")
            head_lines: Optional[int] - Number of lines from start
            tail_lines: Optional[int] - Number of lines from end
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        artifact_path = self._require_str(payload, "artifact_path")
        head_lines = payload.get("head_lines")
        tail_lines = payload.get("tail_lines")
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_step_with_fallback(project_root, calculation, step)
        
        svc = get_service(project_root)
        return svc.analysis.read_step_artifact_text(
            calculation_selector=calculation,
            step_selector=step,
            artifact_path=artifact_path,
            head_lines=head_lines,
            tail_lines=tail_lines,
        )
    
    def _handle_list_wannier_3d_fixtures(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List available Wannier90 3D test fixtures.
        
        Payload: (none required, or {"fixture_dir": str} for custom path)
        
        Returns:
            List of fixture metadata with: id, label, kind (xsf/bxsf), path
        
        Fixtures root discovery priority:
        1. Environment variable QMATSUITE_WANNIER_3D_FIXTURES (if set)
        2. Repo root derivation: Path(__file__).resolve().parents[3] / "tests/data/wannier_3d_test"
        3. DEV fallback: $HOME/QMatSuite/tests/data/wannier_3d_test (only if exists)
        
        Enumeration priority:
        1. If manifest.json exists, use manifest (stable order)
        2. Otherwise, recursive glob for *.xsf and *.bxsf
        """
        import os
        import json
        
        # Determine fixtures_root with priority
        attempted_paths = []
        fixtures_root = None
        
        # Priority 1: Environment variable
        env_path = os.environ.get("QMATSUITE_WANNIER_3D_FIXTURES")
        if env_path:
            fixtures_root = Path(env_path).resolve()
            attempted_paths.append(("env_var", str(fixtures_root)))
            if fixtures_root.exists() and fixtures_root.is_dir():
                self.log(f"Using fixtures_root from QMATSUITE_WANNIER_3D_FIXTURES: {fixtures_root}")
            else:
                fixtures_root = None
        
        # Priority 2: Repo root derivation
        if fixtures_root is None:
            # __file__ is src/quantumvitas/daemon/server.py
            # parents[3] = src/quantumvitas/daemon -> src/quantumvitas -> src/ -> repo_root
            repo_root = Path(__file__).resolve().parents[3]
            fixtures_root = repo_root / "tests" / "data" / "wannier_3d_test"
            attempted_paths.append(("repo_derived", str(fixtures_root)))
            if fixtures_root.exists() and fixtures_root.is_dir():
                self.log(f"Using fixtures_root from repo derivation: {fixtures_root}")
            else:
                fixtures_root = None
        
        # Priority 3: DEV fallback (only if exists)
        if fixtures_root is None:
            dev_fallback = Path.home() / "QMatSuite" / "tests" / "data" / "wannier_3d_test"
            attempted_paths.append(("dev_fallback", str(dev_fallback)))
            if dev_fallback.exists() and dev_fallback.is_dir():
                fixtures_root = dev_fallback
                self.log(f"Using fixtures_root from DEV fallback: {fixtures_root}")
            else:
                fixtures_root = None
        
        # Override with payload if provided
        if "fixture_dir" in payload:
            fixtures_root = Path(payload["fixture_dir"]).resolve()
            attempted_paths.append(("payload", str(fixtures_root)))
        
        # Validate fixtures_root exists
        if fixtures_root is None or not fixtures_root.exists():
            attempted_str = "\n".join(f"  {source}: {path}" for source, path in attempted_paths)
            raise FileNotFoundError(
                f"Wannier90 3D fixtures directory not found. Attempted paths:\n{attempted_str}\n"
                f"Please set QMATSUITE_WANNIER_3D_FIXTURES environment variable or ensure fixtures exist."
            )
        
        if not fixtures_root.is_dir():
            raise ValueError(f"Fixtures root is not a directory: {fixtures_root}")
        
        self.log(f"Fixtures root resolved to: {fixtures_root}")
        
        fixtures = []
        
        # Check for manifest.json first
        manifest_path = fixtures_root / "manifest.json"
        if manifest_path.exists():
            try:
                manifest_data = json.loads(manifest_path.read_text())
                manifest_fixtures = manifest_data.get("fixtures", [])
                
                for entry in manifest_fixtures:
                    fixture_path = fixtures_root / entry["path"]
                    if fixture_path.exists():
                        fixtures.append({
                            "ulid": entry.get("ulid", f"{fixture_path.parent.name}_{fixture_path.stem}"),
                            "label": entry.get("label", str(fixture_path.relative_to(fixtures_root))),
                            "kind": entry.get("kind", "xsf" if fixture_path.suffix == ".xsf" else "bxsf"),
                            "path": str(fixture_path.resolve()),
                        })
                
                self.log(f"Loaded {len(fixtures)} fixtures from manifest.json")
            except Exception as e:
                self.log(f"Failed to load manifest.json: {e}, falling back to recursive scan")
                fixtures = []  # Fall through to recursive scan
        
        # If no manifest or manifest failed, do recursive scan
        if not fixtures:
            # Recursive glob for *.xsf and *.bxsf
            xsf_files = sorted(fixtures_root.rglob("*.xsf"))
            bxsf_files = sorted(fixtures_root.rglob("*.bxsf"))
            
            for xsf_file in xsf_files:
                rel_path = xsf_file.relative_to(fixtures_root)
                fixtures.append({
                    "ulid": f"{xsf_file.parent.name}_{xsf_file.stem}",
                    "label": str(rel_path),
                    "kind": "xsf",
                    "path": str(xsf_file.resolve()),
                })
            
            for bxsf_file in bxsf_files:
                rel_path = bxsf_file.relative_to(fixtures_root)
                fixtures.append({
                    "ulid": f"{bxsf_file.parent.name}_{bxsf_file.stem}",
                    "label": str(rel_path),
                    "kind": "bxsf",
                    "path": str(bxsf_file.resolve()),
                })
            
            self.log(f"Found {len(xsf_files)} XSF files and {len(bxsf_files)} BXSF files via recursive scan")
        
        self.log(f"Total fixtures discovered: {len(fixtures)}")
        
        return {"fixtures": fixtures}
    
    def _handle_compile_fixture_volume(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compile fixture volume file (XSF/BXSF) to blob.
        
        Payload:
            file_path: str - Path to XSF or BXSF file
            calc_dir: str - Calculation directory (sandbox output directory)
            
        Returns:
            Dict with artifact_id, kind, metadata, blob_id, preview_blob_id
        """
        from quantumvitas.api import QVService
        from quantumvitas.api.errors import EngineError
        
        file_path = Path(self._require_str(payload, "file_path")).resolve()
        calc_dir = Path(self._require_str(payload, "calc_dir")).resolve()
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            import os
            import logging
            logger = logging.getLogger(__name__)
            
            # Detect file type
            file_type = file_path.suffix.lower().lstrip(".")
            band_index = payload.get("band_index", 1)
            if not isinstance(band_index, int) or band_index < 1:
                raise ValueError(f"Invalid band_index: {band_index}. Must be >= 1 (1-based)")
            
            # Parse volume artifact
            result = parse_volume_artifact(
                file_path=file_path,
                calc_dir=calc_dir,
                file_type=file_type,
                band_index=band_index,
            )
            
            # Validate band_index is within range (for BXSF)
            if file_type == "bxsf" and band_index > result.get("n_bands", 0):
                raise ValueError(f"band_index {band_index} exceeds n_bands {result.get('n_bands', 0)}")
            
            # Log blob contract for debugging (Phase 0 contract verification)
            if file_type == "xsf" and result.get("preview_blob_id"):
                # Create blob store for path lookup
                blob_store = create_blob_store(calc_dir)
                preview_path = blob_store.get_blob_path(result["preview_blob_id"])
                if preview_path:
                    preview_size = os.path.getsize(preview_path)
                    metadata = result.get("metadata", {})
                    preview_grid_shape = metadata.get("preview_grid_shape")
                    if preview_grid_shape:
                        preview_nx, preview_ny, preview_nz = preview_grid_shape
                        preview_expected_bytes = 4 * preview_nx * preview_ny * preview_nz
                        logger.info(
                            f"[compile_fixture_volume] XSF preview blob contract: "
                            f"blob_id={result['preview_blob_id']}, "
                            f"blob_path={preview_path}, "
                            f"file_size={preview_size} bytes, "
                            f"preview_grid_shape={preview_grid_shape}, "
                            f"expected_bytes={preview_expected_bytes}, "
                            f"match={preview_size == preview_expected_bytes}"
                        )
                    else:
                        logger.warning(f"[compile_fixture_volume] XSF preview_grid_shape is None")
            
            if file_type == "xsf" and result.get("blob_id"):
                # Create blob store for path lookup
                blob_store = create_blob_store(calc_dir)
                full_path = blob_store.get_blob_path(result["blob_id"])
                if full_path:
                    full_size = os.path.getsize(full_path)
                    metadata = result.get("metadata", {})
                    grid_shape = metadata.get("grid_shape")
                    if grid_shape:
                        nx, ny, nz = grid_shape
                        full_expected_bytes = 4 * nx * ny * nz
                        logger.info(
                            f"[compile_fixture_volume] XSF full blob contract: "
                            f"blob_id={result['blob_id']}, "
                            f"blob_path={full_path}, "
                            f"file_size={full_size} bytes, "
                            f"grid_shape={grid_shape}, "
                            f"expected_bytes={full_expected_bytes}, "
                            f"match={full_size == full_expected_bytes}"
                        )
            
            if file_type == "bxsf" and result.get("preview_blob_id"):
                # Create blob store for path lookup
                blob_store = create_blob_store(calc_dir)
                preview_path = blob_store.get_blob_path(result["preview_blob_id"])
                if preview_path:
                    preview_size = os.path.getsize(preview_path)
                    metadata = result.get("metadata", {})
                    preview_grid_shape = metadata.get("preview_grid_shape")
                    if preview_grid_shape:
                        preview_nx, preview_ny, preview_nz = preview_grid_shape
                        preview_expected_bytes = 4 * preview_nx * preview_ny * preview_nz
                        logger.info(
                            f"[compile_fixture_volume] BXSF preview blob contract: "
                            f"blob_id={result['preview_blob_id']}, "
                            f"blob_path={preview_path}, "
                            f"file_size={preview_size} bytes, "
                            f"preview_grid_shape={preview_grid_shape}, "
                            f"expected_bytes={preview_expected_bytes}, "
                            f"match={preview_size == preview_expected_bytes}"
                        )
            
            return result
        except EngineError as e:
            # VolumeParserError is mapped to EngineError by map_kernel_exception
            # Check if it's a volume parser error by checking the error code or message
            if e.code == "ENGINE_OUTPUT_PARSE_FAILED" or "parse" in str(e).lower() or "volume" in str(e).lower():
                raise ValueError(f"Failed to parse volume file: {e}")
            # Re-raise other engine errors
            raise
    
    # -------------------------------------------------------------------------
    # Job management handlers
    # -------------------------------------------------------------------------
    
    def _handle_run_calculation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit a calculation run job.
        
        GUI → Daemon → Backend API mapping:
        - GUI: handleRunCalculation() calls 'run_calculation' with calculation.slug
        - Daemon: _handle_run_calculation() normalizes project_root and submits job
        - Backend: QVService.run_calculation() executes the calculation
        
        Payload:
            project_root: str - Path to project root (normalized to absolute)
            calculation: str - Calculation selector (GUI uses calculation.slug)
            strict: bool - Optional strict mode (default false)
            verbose: bool - Optional verbose mode (default false)
            run_mode: str - Optional run mode ("incremental" or "full", default "incremental")
            
        Returns:
            job_id: str - ID of submitted job
            status: str - Initial status ("pending")
            target_name: str - Calculation name for display
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        strict = payload.get("strict", False)
        verbose = payload.get("verbose", False)
        run_mode = payload.get("run_mode", "incremental")  # Default incremental
        
        # Resolve with fallback to ensure cache is up-to-date before submitting job
        calculation_resolved = self._resolve_calculation_with_fallback(project_root, calculation)
        
        # Pass cached index and config to avoid rebuilding ResourceIndex
        cache = self.state.get_cache(project_root)
        
        # Load calculation to get initial steps list and io_dir (for step progress visualization and I/O directory display)
        initial_steps = []
        initial_io_dir = None
        try:
            from quantumvitas.api import QVService
            calculation_path = calculation_resolved.absolute_path / "calculation.yaml" if calculation_resolved.absolute_path.is_dir() else calculation_resolved.absolute_path
            if calculation_path.exists():
                wf_model = load_calculation(calculation_path, project_root=project_root)
                # Initialize steps with pending status
                initial_steps = []
                for step in wf_model.steps:
                    d = step.to_dict()
                    # Normalize to exactly required keys
                    d["step_type_spec"] = step.type or "unknown"
                    d["status"] = "pending"
                    d["started_at"] = None
                    d["ended_at"] = None
                    # Remove everything else to avoid schema widening
                    for k in list(d.keys()):
                        if k not in {"step_ulid", "step_type_spec", "status", "started_at", "ended_at"}:
                            d.pop(k, None)
                    initial_steps.append(d)
                # Compute planned_io_dir using the same logic the runner uses (single source of truth)
                # This ensures pending jobs show the correct io_dir that will match the runner's final io_dir
                calculation_dir = calculation_resolved.absolute_path if calculation_resolved.absolute_path.is_dir() else calculation_resolved.absolute_path.parent
                planned_io_dir = compute_io_dir_from_calculation_model(calculation_dir, wf_model.working_dir)
                initial_io_dir = str(planned_io_dir)
        except Exception:
            # If we can't load calculation, just use empty steps and no io_dir
            pass
        
        # Generate job_id using ULID (shared with history run_ulid)
        import ulid as ulid_module
        job_id = str(ulid_module.new())
        
        # Submit job with target info for display
        # Note: job_id is passed to run_calculation as run_ulid for history unification
        # Create wrapper function that uses instance method
        def run_calculation_wrapper(**kwargs):
            project_root = Path(kwargs.pop("project_root"))
            calculation_selector = kwargs.pop("calculation_selector") or kwargs.pop("calculation")
            svc = get_service(project_root)
            # Note: run_calculation instance method doesn't support all kwargs yet
            # For now, only pass steps if provided
            steps = kwargs.pop("steps", None)
            return svc.run.run_calculation(calculation_selector, steps=steps)
        
        self.job_manager.submit_with_id(
            job_id=job_id,
            job_type="run_calculation",
            func=run_calculation_wrapper,
            params={
                "project_root": str(project_root),
                "calculation": calculation,
                "strict": strict,
            },
            target_name=calculation,
            project_root_display=str(project_root.resolve()),  # Normalize to absolute path
            initial_steps=initial_steps,  # Initialize steps at job creation
            initial_io_dir=initial_io_dir,  # Initialize io_dir at job creation (so it shows immediately)
            # kwargs for run_calculation_wrapper
            project_root=project_root,
            calculation_selector=calculation,
            strict=strict,
            verbose=verbose,
            index=cache.index,
            config=cache.config,
            run_ulid=job_id,  # Pass job_id as run_ulid for history unification
            run_mode=run_mode,  # Pass run_mode ("incremental" or "full")
        )
        
        return {"job_id": job_id, "status": "pending", "target_name": calculation}
    
    def _handle_run_step(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit a step run job.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            step: str - Step selector
            verbose: bool - Optional verbose mode (default false)
            
        Returns:
            job_id: str - ID of submitted job
            status: str - Initial status ("pending")
            target_name: str - Step name for display
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        verbose = payload.get("verbose", False)
        
        # Resolve with fallback to ensure cache is up-to-date before submitting job
        calculation_resolved = self._resolve_calculation_with_fallback(project_root, calculation)
        self._resolve_step_with_fallback(project_root, calculation, step)
        
        target_name = f"{calculation}/{step}"
        
        # Compute planned_io_dir using the same logic the runner uses (single source of truth)
        initial_io_dir = None
        try:
            from quantumvitas.api import QVService
            calculation_path = calculation_resolved.absolute_path / "calculation.yaml" if calculation_resolved.absolute_path.is_dir() else calculation_resolved.absolute_path
            if calculation_path.exists():
                wf_model = load_calculation(calculation_path, project_root=project_root)
                calculation_dir = calculation_resolved.absolute_path if calculation_resolved.absolute_path.is_dir() else calculation_resolved.absolute_path.parent
                planned_io_dir = compute_io_dir_from_calculation_model(calculation_dir, wf_model.working_dir)
                initial_io_dir = str(planned_io_dir)
        except Exception:
            pass
        
        # Generate job_id using ULID (shared with history run_ulid)
        import ulid as ulid_module
        job_id = str(ulid_module.new())
        
        # Submit job with target info for display
        # Note: job_id is passed to run_step as run_ulid for history unification
        # Create wrapper function that uses instance method
        def run_step_wrapper(**kwargs):
            project_root = Path(kwargs.pop("project_root"))
            calculation_selector = kwargs.pop("calculation_selector") or kwargs.pop("calculation")
            step_selector = kwargs.pop("step_selector") or kwargs.pop("step")
            svc = get_service(project_root)
            return svc.run.run_step(calculation_selector, step_selector)
        
        self.job_manager.submit_with_id(
            job_id=job_id,
            job_type="run_step",
            func=run_step_wrapper,
            params={
                "project_root": str(project_root),
                "calculation": calculation,
                "step": step,
            },
            target_name=target_name,
            project_root_display=str(project_root),
            initial_io_dir=initial_io_dir,  # Initialize io_dir at job creation (so it shows immediately)
            # kwargs for run_step_wrapper
            project_root=project_root,
            calculation_selector=calculation,
            step_selector=step,
            verbose=verbose,
            run_ulid=job_id,  # Pass job_id as run_ulid for history unification
        )
        
        return {"job_id": job_id, "job_ulid": job_id, "status": "pending", "target_name": target_name}
    
    def _handle_run_single_step(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit a single-step run job (advanced feature, always runs, never skips).
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            step_ulid: str - Step ULID (must match a step in calculation.yaml)
            verbose: bool - Optional verbose mode (default false)
            
        Returns:
            job_id: str - ID of submitted job
            status: str - Initial status ("pending")
            target_name: str - Step name for display
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step_ulid = self._require_str(payload, "step_ulid")
        verbose = payload.get("verbose", False)
        
        # Resolve with fallback to ensure cache is up-to-date
        calculation_resolved = self._resolve_calculation_with_fallback(project_root, calculation)
        
        # Pass cached index and config
        cache = self.state.get_cache(project_root)
        
        target_name = f"{calculation}/{step_ulid}"
        
        # Generate job_id using ULID
        import ulid as ulid_module
        job_id = str(ulid_module.new())
        
        # Submit job
        self.job_manager.submit_with_id(
            job_id=job_id,
            job_type="run_single_step",
            func=QVService.run_single_step,
            params={
                "project_root": str(project_root),
                "calculation": calculation,
                "step_ulid": step_ulid,
            },
            target_name=target_name,
            project_root_display=str(project_root.resolve()),
            # kwargs for QVService.run_single_step
            project_root=project_root,
            calculation_selector=calculation,
            step_ulid=step_ulid,
            verbose=verbose,
            index=cache.index,
            config=cache.config,
            run_ulid=job_id,  # Pass job_id as run_ulid
        )
        
        return {"job_id": job_id, "job_ulid": job_id, "status": "pending", "target_name": target_name}
    
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
        
        GUI → Daemon → Backend API mapping:
        - GUI: useJobs hook calls 'list_jobs' with projectRoot (string from state)
        - Daemon: _handle_list_jobs() normalizes project_root for filtering
        - Backend: JobManager.list_jobs() filters by normalized project_root
        
        Payload:
            status: str - Optional status filter
            job_type: str - Optional job type filter
            project_root: str - Optional project filter (normalized to absolute path)
            limit: int - Maximum jobs to return (default 50)
        """
        status_str = payload.get("status")
        status = JobStatus(status_str) if status_str else None
        job_type = payload.get("job_type")
        project_root = payload.get("project_root")
        limit = payload.get("limit", 50)
        
        # Normalize project_root if provided (GUI sends string, normalize to absolute Path string)
        # This ensures path matching works regardless of trailing slashes or relative vs absolute
        # Handle None/empty string gracefully (list all jobs if no filter)
        if project_root:
            try:
                project_root = str(Path(project_root).resolve())
            except (ValueError, OSError):
                # Invalid path - treat as no filter (list all jobs)
                project_root = None
        
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
    
    def _get_svc(self, project_root: Path) -> QVService:
        """
        Get or create QVService instance for a project.
        
        Args:
            project_root: Path to project root
            
        Returns:
            QVService instance for the project
        """
        project_root = project_root.resolve()
        cache = self.state.get_cache(project_root)
        return cache.svc
    
    # -------------------------------------------------------------------------
    # Resolution helpers with cache fallback
    # -------------------------------------------------------------------------
    
    def _require_calculation_ref(self, svc, selector: str, config: dict | None = None):
        """
        Daemon helper: Require calculation reference via domain API.
        
        Centralized wrapper around svc.calculation.require_ref() to:
        - Isolate return type changes
        - Prevent legacy pattern usage
        - Ensure consistent error handling
        
        Args:
            svc: QVService instance
            selector: Calculation selector (name, slug, id, or path)
            config: Optional project config
            
        Returns:
            ResolvedResource for the calculation
            
        Raises:
            APIError: If calculation not found
        """
        return svc.calculation.require_ref(selector, config=config)
    
    def _require_structure_ref(self, svc, selector: str, config: dict | None = None):
        """
        Daemon helper: Require structure reference via domain API.
        
        Centralized wrapper around svc.structure.require_ref() to:
        - Isolate return type changes
        - Prevent legacy pattern usage
        - Ensure consistent error handling
        
        Args:
            svc: QVService instance
            selector: Structure selector (name, slug, id, or path)
            config: Optional project config
            
        Returns:
            ResolvedResource for the structure
            
        Raises:
            APIError: If structure not found
        """
        return svc.structure.require_ref(selector, config=config)
    
    def _require_step_ref(self, svc, calc_selector: str, step_selector: str, config: dict | None = None):
        """
        Daemon helper: Require step reference via domain API.
        
        Centralized wrapper around svc.calculation.require_step_ref() to:
        - Isolate return type changes
        - Prevent legacy pattern usage
        - Ensure consistent error handling
        
        Args:
            svc: QVService instance
            calc_selector: Calculation selector (name, slug, id, or path)
            step_selector: Step selector (name, slug, id, or index)
            config: Optional project config
            
        Returns:
            ResolvedResource for the step
            
        Raises:
            APIError: If calculation or step not found
        """
        return svc.calculation.require_step_ref(calc_selector, step_selector, config=config)
    
    def _resolve_calculation_with_fallback(self, project_root: Path, selector: str):
        """
        Resolve calculation using domain API methods.
        
        Uses _require_calculation_ref() helper (which wraps svc.calculation.require_ref()).
        No directory-walking fallbacks - all resolution via API domain methods.
        
        Args:
            project_root: Path to project root
            selector: Calculation selector (name, slug, id, or path)
            
        Returns:
            ResolvedResource for the calculation
            
        Raises:
            APIError: If calculation not found
        """
        # Use daemon helper (no kernel imports, no directory walking)
        cache = self.state.get_cache(project_root)
        return self._require_calculation_ref(cache.svc, selector, config=cache.config)
    
    def _resolve_step_with_fallback(
        self,
        project_root: Path,
        calculation_selector: str,
        step_selector: str,
    ):
        """
        Resolve step using cached index.
        
        NOTE: This helper NO LONGER auto-rebuilds on cache miss. The registry
        is only rebuilt in two cases:
        1. When a project is first loaded (get_cache)
        2. When explicitly requested via rebuild_project_registry RPC
        
        Write operations update the registry in-place without rebuilding.
        
        If the resource is not found, SelectorNotFoundError is raised immediately.
        The user should click the Refresh button to rebuild the registry.
        
        Args:
            project_root: Path to project root
            calculation_selector: Calculation selector (name, slug, id, or path)
            step_selector: Step selector (name, slug, id, or path)
            
        Returns:
            ResolvedResource for the step
            
        Raises:
            SelectorNotFoundError: If step not found
        """
        # Use daemon helper (no kernel imports, no directory walking)
        cache = self.state.get_cache(project_root)
        return self._require_step_ref(
            cache.svc,
            calculation_selector,
            step_selector,
            config=cache.config,
        )
    
    # -------------------------------------------------------------------------
    # Registry rebuild handler
    # -------------------------------------------------------------------------
    
    def _handle_rebuild_project_registry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Explicitly rebuild the project registry (ResourceIndex).
        
        This is the ONLY way to rebuild the registry from the GUI.
        The registry is also rebuilt automatically after write operations.
        
        Payload:
            project_root: str (required) - Path to project root
            
        Returns:
            {
                "ok": true,
                "project_root": "<normalized>",
                "index_stats": {
                    "structures": <count>,
                    "calculations": <count>,
                    "steps": <count>
                },
                "dag_diff": {
                    "structures_added": [...],
                    "structures_removed": [...],
                    "calculations_added": [...],
                    "calculations_removed": [...],
                    "calculations_changed": [...]
                }
            }
        """
        import time

        project_root = self._require_path(payload, "project_root")
        project_root = project_root.resolve()

        # Take snapshot of current registry (if any)
        old_cache = self.state._caches.get(project_root)
        old_snapshot = self._snapshot_dag(old_cache.index if old_cache else None)

        # Rebuild the registry
        t0 = time.perf_counter()
        try:
            svc = QVService(project_root)
            config = svc.project.get_config()
            index = svc.project.build_resource_index()
            project_name = config.get("meta", {}).get("name") or project_root.name
            self.state._caches[project_root] = ProjectCache(
                project_root=project_root,
                index=index,
                config=config,
                svc=svc,
            )
        except Exception as e:
            self.logger.error(f"Failed to rebuild registry: {e}", exc_info=True)
            raise
        
        dt_ms = (time.perf_counter() - t0) * 1000
        
        # Log with reason
        self.logger.info(
            "[RPC] rebuild_project_registry (project: %s) took %.1fms [reason=manual_refresh]",
            project_name,
            dt_ms,
        )
        
        # Take snapshot of new registry
        new_snapshot = self._snapshot_dag(index)
        
        # Compute DAG diff
        dag_diff = self._diff_dag(old_snapshot, new_snapshot)
        
        # Compute index stats
        structures = [r for r in index.by_id.values() if r.kind == "structure"]
        calculations = [r for r in index.by_id.values() if r.kind == "calculation"]
        steps = [r for r in index.by_id.values() if r.kind == "step"]
        
        return {
            "project_root": str(project_root),
            "index_stats": {
                "structures": len(structures),
                "calculations": len(calculations),
                "steps": len(steps),
            },
            "dag_diff": dag_diff,
        }
    
    def _rebuild_registry_after_write(self, project_root: Path, reason: str) -> None:
        """
        Rebuild the project registry for a given project after a write operation.
        
        This is a thin wrapper around the canonical registry rebuild logic,
        kept for backwards compatibility with handlers that used to call it.
        
        Args:
            project_root: Path to project root (must be resolved)
            reason: Reason string for logging (e.g., "write_operation:create_demo_project")
        """
        import time

        project_root = project_root.resolve()

        # Rebuild the registry
        t0 = time.perf_counter()
        try:
            svc = QVService(project_root)
            config = svc.project.get_config()
            index = svc.project.build_resource_index()
            project_name = config.get("meta", {}).get("name") or project_root.name
            self.state._caches[project_root] = ProjectCache(
                project_root=project_root,
                index=index,
                config=config,
                svc=svc,
            )
        except Exception as e:
            self.logger.error(f"Failed to rebuild registry after {reason}: {e}", exc_info=True)
            raise
        
        dt_ms = (time.perf_counter() - t0) * 1000
        
        # Log with reason
        self.logger.info(
            "[RPC] _rebuild_registry_after_write (project: %s) took %.1fms [reason=%s]",
            project_name,
            dt_ms,
            reason,
        )
    
    def _snapshot_dag(self, index: Optional[ResourceIndex]) -> Dict[str, Any]:
        """
        Return a lightweight representation of the DAG for diffing.
        
        Args:
            index: ResourceIndex to snapshot (None for empty snapshot)
            
        Returns:
            {
                "structures": { structure_ulid: { "slug": ..., "name": ... } },
                "calculations": {
                    calculation_id: {
                        "slug": ...,
                        "name": ...,
                        "steps": [step_ulid1, step_ulid2, ...]   # in order
                    },
                    ...
                }
            }
        """
        from quantumvitas.api import QVService
        
        if index is None:
            return {"structures": {}, "calculations": {}}
        
        snapshot: Dict[str, Any] = {
            "structures": {},
            "calculations": {},
        }
        
        # Collect all structures
        for resource_id, meta in index.by_id.items():
            if meta.kind == "structure":
                snapshot["structures"][resource_id] = {
                    "slug": meta.slug,
                    "name": meta.name,
                }
        
        # Collect all calculations with their step lists
        for resource_id, meta in index.by_id.items():
            if meta.kind == "calculation":
                # Find calculation.yaml path from index
                calculation_path = None
                for path, path_id in index.by_path.items():
                    if path_id == resource_id and path.name == "calculation.yaml":
                        calculation_path = path
                        break
                
                if calculation_path and calculation_path.exists():
                    try:
                        # Determine project root (calculations/calculation_name/calculation.yaml -> project_root)
                        project_root = calculation_path.parent.parent.parent
                        # Load calculation model to get steps
                        wf_model = load_calculation(calculation_path, project_root=project_root)
                        step_ulids = [entry.step_ulid for entry in wf_model.steps if entry.step_ulid]
                    except Exception:
                        # If we can't load the calculation, just use empty steps
                        step_ulids = []
                else:
                    step_ulids = []
                
                snapshot["calculations"][resource_id] = {
                    "slug": meta.slug,
                    "name": meta.name,
                    "steps": step_ulids,
                }
        
        return snapshot
    
    def _diff_dag(self, old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute a high-level DAG diff between old and new snapshots.
        
        Args:
            old: Old snapshot (from _snapshot_dag)
            new: New snapshot (from _snapshot_dag)
        
        Returns:
            {
                "structures_added": [ { "ulid": ..., "slug": ..., "suffix": ... }, ... ],
                "structures_removed": [ ... ],
                "calculations_added": [ { "ulid": ..., "slug": ..., "suffix": ... }, ... ],
                "calculations_removed": [ ... ],
                "calculations_changed": [
                    {
                        "calculation_id": ...,
                        "calculation_slug": ...,
                        "suffix": ...,
                        "steps_added": [ { "ulid": ..., "suffix": ... }, ... ],
                        "steps_removed": [ { "ulid": ..., "suffix": ... }, ... ],
                    },
                    ...
                ]
            }
        """
        def _ulid_suffix(ulid: str, length: int = 6) -> str:
            """Compute a short suffix for debugging."""
            return ulid[-length:] if ulid and len(ulid) > length else ulid
        
        diff: Dict[str, Any] = {
            "structures_added": [],
            "structures_removed": [],
            "calculations_added": [],
            "calculations_removed": [],
            "calculations_changed": [],
        }
        
        old_structures = old.get("structures", {})
        new_structures = new.get("structures", {})
        old_calculations = old.get("calculations", {})
        new_calculations = new.get("calculations", {})
        
        # Structures added
        for struct_id in new_structures:
            if struct_id not in old_structures:
                diff["structures_added"].append({
                    "ulid": struct_id,
                    "slug": new_structures[struct_id]["slug"],
                    "name": new_structures[struct_id]["name"],
                    "suffix": _ulid_suffix(struct_id),
                })
        
        # Structures removed
        for struct_id in old_structures:
            if struct_id not in new_structures:
                diff["structures_removed"].append({
                    "ulid": struct_id,
                    "slug": old_structures[struct_id]["slug"],
                    "name": old_structures[struct_id]["name"],
                    "suffix": _ulid_suffix(struct_id),
                })
        
        # Calculations added
        for wf_id in new_calculations:
            if wf_id not in old_calculations:
                diff["calculations_added"].append({
                    "ulid": wf_id,
                    "slug": new_calculations[wf_id]["slug"],
                    "name": new_calculations[wf_id]["name"],
                    "suffix": _ulid_suffix(wf_id),
                })
        
        # Calculations removed
        for wf_id in old_calculations:
            if wf_id not in new_calculations:
                diff["calculations_removed"].append({
                    "ulid": wf_id,
                    "slug": old_calculations[wf_id]["slug"],
                    "name": old_calculations[wf_id]["name"],
                    "suffix": _ulid_suffix(wf_id),
                })
        
        # Calculations changed (step lists differ)
        for wf_id in old_calculations:
            if wf_id in new_calculations:
                old_steps = old_calculations[wf_id].get("steps", [])
                new_steps = new_calculations[wf_id].get("steps", [])
                
                steps_added = [s for s in new_steps if s not in old_steps]
                steps_removed = [s for s in old_steps if s not in new_steps]
                
                if steps_added or steps_removed:
                    diff["calculations_changed"].append({
                        "calculation_id": wf_id,
                        "calculation_slug": new_calculations[wf_id]["slug"],
                        "calculation_name": new_calculations[wf_id]["name"],
                        "suffix": _ulid_suffix(wf_id),
                        "steps_added": [{"ulid": s, "suffix": _ulid_suffix(s)} for s in steps_added],
                        "steps_removed": [{"ulid": s, "suffix": _ulid_suffix(s)} for s in steps_removed],
                    })
        
        return diff
    
    # -------------------------------------------------------------------------
    # Journal Handlers
    # -------------------------------------------------------------------------
    
    def _handle_list_journal_entries(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List journal entries.
        
        Payload:
            target_ulid: Optional[str] - Filter by target ULID
            doc_type: Optional[str] - Filter by doc type ("step", "calc", "project")
            limit: Optional[int] - Maximum entries (default 100)
            
        Returns:
            entries: List of journal entry dicts
        """
        from quantumvitas.api import QVService
        
        target_ulid = payload.get("target_ulid")
        doc_type = payload.get("doc_type")
        limit = payload.get("limit", 100)
        
        journal = get_journal()
        entries = journal.list_entries(
            target_ulid=target_ulid,
            doc_type=doc_type,
            limit=limit,
        )
        
        return {
            "entries": [e.to_dict() for e in entries],
            "total": len(entries),
        }
    
    def _handle_get_journal_entry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get a specific journal entry by ID.
        
        Payload:
            entry_id: str - ULID of the entry
            
        Returns:
            entry: Journal entry dict or null
        """
        from quantumvitas.api import QVService
        
        entry_id = self._require_str(payload, "entry_id")
        
        journal = get_journal()
        entry = journal.get_entry(entry_id)
        
        if entry is None:
            return {"entry": None}
        
        return {"entry": entry.to_dict()}
    
    # -------------------------------------------------------------------------
    # Project History Handlers
    # -------------------------------------------------------------------------
    
    def _handle_get_project_history(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get project history timeline for notebook view.

        Payload:
            project_root: str - Path to project root
            limit: Optional[int] - Maximum events (default 100)
            calc_ulid: Optional[str] - Filter by calculation ID

        Returns:
            timeline: List of timeline entries (runs, edits, pins)
            latest_run_ulid: Latest run ULID or null
        """
        project_root = Path(self._require_str(payload, "project_root"))
        limit = payload.get("limit", 100)
        calc_ulid = payload.get("calc_ulid")

        # Use domain API
        svc = get_service(project_root)
        return svc.history.get_timeline(limit=limit, calc_ulid=calc_ulid)
    
    def _handle_get_run_revision(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get details of a specific run revision.

        Payload:
            project_root: str - Path to project root
            run_ulid: str - Run ULID

        Returns:
            revision: Run revision dict or null
        """
        project_root = Path(self._require_str(payload, "project_root"))
        run_ulid = self._require_str(payload, "run_ulid")

        # Use domain API
        svc = get_service(project_root)
        return svc.history.get_run_revision(run_ulid)
    
    def _handle_list_project_runs(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List all runs for a project.

        Payload:
            project_root: str - Path to project root
            calc_ulid: Optional[str] - Filter by calculation ID
            limit: Optional[int] - Maximum runs (default 50)

        Returns:
            runs: List of run summaries
        """
        project_root = Path(self._require_str(payload, "project_root"))
        calc_ulid = payload.get("calc_ulid")
        limit = payload.get("limit", 50)

        # Use domain API
        svc = get_service(project_root)
        return svc.history.list_runs(calc_ulid=calc_ulid, limit=limit)
    
    def _handle_pin_analysis_to_history(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pin analysis results to history.

        Payload:
            project_root: str - Path to project root
            run_ulid: Optional[str] - Run ULID
            step_ulid: str - Step ULID
            analysis_kind: str - Type of analysis (e.g., "bands", "dos")
            png_data_base64: Optional[str] - Base64-encoded PNG data
            json_payload: Optional[dict] - JSON data to store
            run_ulid_source: Optional[str] - "exact" | "inferred" | "unknown"

        Returns:
            result: Pin result dict
        """
        import base64

        project_root = Path(self._require_str(payload, "project_root"))
        run_ulid = payload.get("run_ulid")
        if run_ulid is not None and not isinstance(run_ulid, str):
            raise ValueError("run_ulid must be a string when provided")
        step_ulid = self._require_str(payload, "step_ulid")
        analysis_kind = self._require_str(payload, "analysis_kind")

        # Decode PNG if provided
        png_data = None
        png_base64 = payload.get("png_data_base64")
        if png_base64:
            try:
                png_data = base64.b64decode(png_base64)
            except Exception as e:
                return {"success": False, "error": f"Failed to decode PNG: {e}"}

        json_payload = payload.get("json_payload")
        run_ulid_source = payload.get("run_ulid_source")

        # Use domain API
        svc = get_service(project_root)
        return svc.history.pin_analysis(
            run_ulid=run_ulid,
            step_ulid=step_ulid,
            analysis_kind=analysis_kind,
            png_data=png_data,
            json_payload=json_payload,
            run_ulid_source=run_ulid_source,
        )

    def _handle_can_pin_to_run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if pinning is allowed for a run and step.

        Payload:
            project_root: str - Path to project root
            run_ulid: str - Run ULID
            step_ulid: str - Step ULID

        Returns:
            allowed: bool
            reason: Optional[str] - Reason if not allowed
        """
        project_root = Path(self._require_str(payload, "project_root"))
        run_ulid = self._require_str(payload, "run_ulid")
        step_ulid = self._require_str(payload, "step_ulid")

        # Use domain API
        svc = get_service(project_root)
        return svc.history.can_pin(run_ulid, step_ulid)
    
    def _handle_get_pin_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get pinned data for a step analysis.

        Payload:
            project_root: str - Path to project root
            run_ulid: str - Run ULID
            step_ulid: str - Step ULID
            analysis_kind: str - Type of analysis

        Returns:
            png_path: Optional[str] - Path to PNG file
            json_path: Optional[str] - Path to JSON file
            json_data: Optional[dict] - Parsed JSON data
        """
        project_root = Path(self._require_str(payload, "project_root"))
        run_ulid = self._require_str(payload, "run_ulid")
        step_ulid = self._require_str(payload, "step_ulid")
        analysis_kind = self._require_str(payload, "analysis_kind")

        # Use domain API
        svc = get_service(project_root)
        return svc.history.get_pin_data(run_ulid, step_ulid, analysis_kind)

    def _handle_get_latest_run_for_step(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get the latest run_ulid that includes a specific step.

        Used by the Analysis panel to determine if "Pin to History" should be enabled.

        Payload:
            project_root: str - Path to project root
            step_ulid: str - Step ULID

        Returns:
            run_ulid: Optional[str] - Latest run ULID containing this step
            can_pin: bool - Whether pinning is allowed
            reason: Optional[str] - Reason if cannot pin
        """
        project_root = Path(self._require_str(payload, "project_root"))
        step_ulid = self._require_str(payload, "step_ulid")

        # Use domain API
        svc = get_service(project_root)
        return svc.history.get_latest_run_for_step(step_ulid)
    
    def _handle_delete_project_history(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete the entire .provenance directory for a project.

        Safety:
        - Only deletes the .provenance directory
        - Validates path to prevent traversal attacks
        - Does NOT delete any present-tense truth files

        Payload:
            project_root: str - Path to project root
            confirm: bool - Must be True to confirm deletion

        Returns:
            success: bool
            error: Optional[str]
            deleted_path: Optional[str] - Path that was deleted
        """
        project_root = Path(self._require_str(payload, "project_root"))
        confirm = payload.get("confirm", False)

        # Use domain API
        svc = get_service(project_root)
        return svc.history.delete(confirm=confirm)

    def _handle_get_storage_summary(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get provenance storage summary for a project.

        Payload:
            project_root: str - Path to project root

        Returns:
            tiers, total_objects, total_bytes, run_count, operation_count
        """
        project_root = Path(self._require_str(payload, "project_root"))
        svc = get_service(project_root)
        return svc.history.get_storage_summary()

    # -------------------------------------------------------------------------
    # Workflow Handlers
    # -------------------------------------------------------------------------
    
    def _handle_list_workflow_templates(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List available workflow templates.
        
        Returns:
            templates: List of workflow template dicts
        """
        service = QVService.get_workflow_service()
        templates = service.list_templates()
        
        # Serialize templates using dataclasses.asdict()
        templates_list = []
        for t in templates:
            template_dict = asdict(t)
            # Convert step_sequence from tuple to list for JSON serialization
            template_dict["step_sequence"] = list(template_dict["step_sequence"])
            # Filter to only required keys (prevent schema widening)
            filtered_dict = {
                "id": template_dict["id"],  # Template identifier (not a ULID)
                "ulid": template_dict["id"],  # Backwards compat alias
                "name": template_dict["name"],
                "description": template_dict["description"],
                "step_sequence": template_dict["step_sequence"],
            }
            templates_list.append(filtered_dict)
        
        return {
            "templates": templates_list
        }
    
    def _handle_detect_workflow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect workflow type from an existing calculation.
        
        Payload:
            calculation_path: str - Path to calculation directory
            
        Returns:
            match: Workflow match result dict
        """
        calc_path = self._require_path(payload, "calculation_path")
        
        service = QVService.get_workflow_service()
        match = service.detect_workflow(calc_path)
        
        return {
            "match": {
                "workflow_id": match.workflow_id,
                "workflow_name": match.workflow_name,
                "coverage": match.coverage,
                "present_steps": match.present_steps,
                "missing_steps": match.missing_steps,
                "extra_steps": match.extra_steps,
                "ordering_valid": match.ordering_valid,
            }
        }
    
    def _handle_detect_workflow_for_calculation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect workflow for a calculation and return match + issues.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector (slug/name/ULID, resolved to ULID here)
            
        Returns:
            Dict with:
                workflow_id: str | null - Best matching workflow ID
                workflow_name: str - Workflow name
                coverage: dict with "present" and "required" counts
                missing_step_types: list[str] - Missing required step types
                issues: list[dict] - List of issues with "code" and "message"
        """
        import logging
        
        logger = logging.getLogger(__name__)
        
        project_root = self._require_path(payload, "project_root")
        # Accept both calculation_ulid (preferred) and calculation (legacy selector)
        calculation_ulid_param = payload.get("calculation_ulid")
        calculation_selector = payload.get("calculation")
        
        # Determine selector and type for logging
        if calculation_ulid_param:
            calculation_selector = calculation_ulid_param
            selector_type = "ulid" if is_ulid_like(calculation_selector) else "invalid"
        elif calculation_selector:
            selector_type = "ulid" if is_ulid_like(calculation_selector) else ("slug" if "/" not in calculation_selector and "\\" not in calculation_selector else "path")
        else:
            return {
                "ok": False,
                "error": {
                    "code": "invalid_argument",
                    "message": "Either calculation_ulid or calculation must be provided"
                }
            }
        
        # Resolve calculation selector to ULID (kind-constrained)
        if is_ulid_like(calculation_selector):
            calculation_ulid = calculation_selector
        else:
            # ALWAYS log boundary resolves (not gated by debug flag)
            resolved = self._resolve_calculation_with_fallback(project_root, calculation_selector)
            calculation_ulid = resolved.meta.ulid
            logger.info(
                f"[DETECT_WORKFLOW] endpoint=DETECT_WORKFLOW_FOR_CALCULATION "
                f"selector='{calculation_selector}' selector_type={selector_type} "
                f"resolved_ulid={calculation_ulid}"
            )
        
        # Resolve calculation by ULID (for path resolution)
        resolved = self._resolve_calculation_with_fallback(project_root, calculation_ulid)
        if resolved.absolute_path.name == "calculation.yaml":
            calculation_dir = resolved.absolute_path.parent
        else:
            calculation_dir = resolved.absolute_path
        
        # Validate kind (per Constitution: ULID-based resolution must validate kind)
        if resolved.meta.kind != "calculation":
            from quantumvitas.api import APIError
            raise APIError(
                f"Resource '{calculation_ulid}' is not a calculation (kind: {resolved.meta.kind})"
            )
        
        # Detect workflow (uses calculation.yaml.steps[] as authoritative)
        service = QVService.get_workflow_service()
        match = service.detect_workflow(calculation_dir)
        
        # Validate workflow (get issues)
        issues = service.validate_workflow(calculation_dir, match.workflow_id)
        
        # Build coverage info
        if match.workflow_id:
            workflow = service.get_template(match.workflow_id)
            if workflow:
                required_steps = set(workflow.step_sequence) - workflow.optional_steps
                required_count = len(required_steps)
            else:
                required_count = len(match.present_steps)
        else:
            required_count = 0
        
        present_count = len(match.present_steps)
        
        # Build workflow label (e.g., "DOS (3/3)" or "Bands (2/3)")
        if match.workflow_id and required_count > 0:
            workflow_label = f"{match.workflow_name} ({present_count}/{required_count})"
        elif match.workflow_id:
            workflow_label = f"{match.workflow_name} ({present_count} steps)"
        else:
            workflow_label = "Unknown"
        
        # Convert issues to simple dict format (WorkflowIssue is a dataclass)
        from dataclasses import asdict
        issues_list = []
        for issue in issues:
            d = asdict(issue)
            # Normalize to exactly required keys (rename severity -> code)
            d["code"] = d.pop("severity")
            # Remove any extra keys to avoid schema widening
            for k in list(d.keys()):
                if k not in {"code", "message", "step_type_spec"}:
                    d.pop(k, None)
            issues_list.append(d)
        
        return {
            "workflow_id": match.workflow_id,
            "workflow_name": match.workflow_name,
            "workflow_label": workflow_label,
            "coverage": {
                "present": present_count,
                "required": required_count,
            },
            "present_steps": match.present_steps,
            "missing_step_types": match.missing_steps,
            "issues": issues_list,
        }
    
    def _handle_instantiate_workflow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Instantiate a workflow by creating its steps.
        
        Payload:
            workflow_id: str - Workflow template id
            calculation_path: str - Path to calculation directory
            structure_ulid: str - Structure ULID
            calculation_id: str - Parent calculation ULID
            
        Returns:
            step_paths: List of created step file paths
        """
        workflow_id = self._require_str(payload, "workflow_id")
        calc_path = self._require_path(payload, "calculation_path")
        structure_ulid = self._require_str(payload, "structure_ulid")
        calculation_id = self._require_str(payload, "calculation_id")
        
        service = QVService.get_workflow_service()
        
        paths = service.instantiate_workflow(
            workflow_id=workflow_id,
            calc_dir=calc_path,
            structure_ulid=structure_ulid,
            parent_calculation_id=calculation_id,
        )
        
        return {
            "step_paths": [str(p) for p in paths]
        }
    
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
            # Provide more specific error for project roots
            if key == "project_root":
                raise FileNotFoundError(f"Project folder not found: {path}. The project may have been deleted or moved.")
            raise FileNotFoundError(f"Path not found: {path}")
        # For project_root, also check that project.qv.yml exists
        if key == "project_root":
            config_file = path / "project.qv.yml"
            if not config_file.exists():
                raise FileNotFoundError(f"Project configuration not found: {config_file}. This folder is not a valid QuantumVITAS project.")
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
