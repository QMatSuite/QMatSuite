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
import logging
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TextIO

from quantumvitas.api import QVService, QVServiceError
from quantumvitas.core.exceptions import LegacyProjectError
from quantumvitas.core.resolution import (
    ResourceNotFoundError,
    RegistryOutOfSyncError,
    SelectorNotFoundError,
    build_resource_index,
    resolve_calculation,
    resolve_step,
    ResourceIndex,
)
from quantumvitas.core.project_utils import load_project_config
from quantumvitas.daemon.jobs import JobManager, JobStatus
from quantumvitas.data import qe_metadata
from quantumvitas.data.qe_metadata import (
    get_ui_parameters,
    list_supported_modules,
    get_module_param_sections,
    get_module_doc_url,
    get_metadata_file_info,
    get_qe_metadata_debug_info,
    safe_load_metadata,
    reload_metadata,
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
    index: ResourceIndex
    config: dict


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
            # Build fresh cache
            index = build_resource_index(project_root)
            config = load_project_config(project_root)
            self._caches[project_root] = ProjectCache(
                project_root=project_root,
                index=index,
                config=config,
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
        index = build_resource_index(project_root)
        config = load_project_config(project_root)
        self._caches[project_root] = ProjectCache(
            project_root=project_root,
            index=index,
            config=config,
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
            "detect_qe": self._handle_detect_qe,
            "get_env_info": self._handle_get_env_info,
            "set_log_level": self._handle_set_log_level,
            "list_qe_ui_parameters": self._handle_list_qe_ui_parameters,
            "list_qe_parameter_metadata": self._handle_list_qe_parameter_metadata,
            "reload_qe_parameter_metadata": self._handle_reload_qe_parameter_metadata,
            "get_qe_parameter_metadata_debug_info": self._handle_get_qe_parameter_metadata_debug_info,
            
            # Pseudopotential configuration
            "get_pseudo_config": self._handle_get_pseudo_config,
            "set_pseudo_config": self._handle_set_pseudo_config,
            "validate_pseudo_config": self._handle_validate_pseudo_config,
            "init_pseudo_dirs": self._handle_init_pseudo_dirs,
            "install_seed_to_store": self._handle_install_seed_to_store,
            "list_installed_sssp": self._handle_list_installed_sssp,
            "download_sssp_library": self._handle_download_sssp_library,
            "download_all_sssp": self._handle_download_all_sssp,
            
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
            "import_step_from_qe_input": self._handle_import_step_from_qe_input,
            "change_calculation_structure": self._handle_change_calculation_structure,
            "get_calculation_pseudo_mapping": self._handle_get_calculation_pseudo_mapping,
            "update_calculation_species_map": self._handle_update_calculation_species_map,
            "delete_step": self._handle_delete_step,
            
            # Pre-flight checks
            "preflight_check": self._handle_preflight_check,
            
            # Demo project
            "create_demo_project": self._handle_create_demo_project,
            "list_demo_projects": self._handle_list_demo_projects,
            
            # Analysis (ensure artifacts exist, parse if needed)
            "ensure_calculation_analysis": self._handle_ensure_calculation_analysis,
            
            # Visualization data (pure data, no matplotlib)
            "get_structure_vis": self._handle_get_structure_vis,
            "get_scf_convergence": self._handle_get_scf_convergence,
            "get_dos_data": self._handle_get_dos_data,
            "get_band_structure_data": self._handle_get_band_structure_data,
            "get_reference_analysis": self._handle_get_reference_analysis,
            
            # Job management
            "run_calculation": self._handle_run_calculation,
            "run_step": self._handle_run_step,
            "get_job_status": self._handle_get_job_status,
            "get_job_logs": self._handle_get_job_logs,
            "list_jobs": self._handle_list_jobs,
            "job_counts": self._handle_job_counts,
            "cancel_job": self._handle_cancel_job,
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
            result = handler(request.payload)
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
            
            return RPCResponse(id=request.id, ok=True, data=result)
            
        except ValueError as e:
            # ValueError from handler should be converted to structured error
            return RPCResponse(
                id=request.id,
                ok=False,
                error={"code": "invalid_argument", "message": str(e)},
            )
        except LegacyProjectError as e:
            # Convert LegacyProjectError to structured daemon error
            # Provide clear, actionable message with migration command
            migration_command = f"python scripts/qv_migrate_legacy_project.py --project-root {e.project_root}"
            return RPCResponse(
                id=request.id,
                ok=False,
                error={
                    "code": "legacy_project",
                    "message": (
                        f"This project uses a legacy calculation format (structure selector / step_file / non-ULID step IDs). "
                        f"Please migrate it using: {migration_command}"
                    ),
                    "details": {
                        "project_root": str(e.project_root),
                        "hint": migration_command,
                    },
                },
            )
        except ResourceNotFoundError as e:
            # Convert ResourceNotFoundError to structured daemon error
            error_dict = {
                "code": "resource_not_found",
                "kind": e.kind,
                "selector": e.selector,
                "id": e.id,
                "message": str(e),
            }
            # Include details if present (calculation_path, expected_step_path, reason, etc.)
            if hasattr(e, 'details') and e.details:
                error_dict["details"] = e.details
            return RPCResponse(
                id=request.id,
                ok=False,
                error=error_dict,
            )
        except QVServiceError as e:
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
        return QVService.detect_qe()
    
    def _handle_get_env_info(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get environment info.
        
        Payload: (none required)
        
        Returns python_version, qv_version, qe_home, etc.
        """
        return QVService.get_environment_info()
    
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
            repo_pseudo_dir: str - Path to repo/pseudo (committed demos)
            default_store_dir: str - Default store directory
            default_seed_dir: str - Default seed directory
        """
        from quantumvitas.core.pseudo_config import (
            load_pseudo_config,
            PseudoConfig,
            _find_quantumvitas_root,
        )
        
        config = load_pseudo_config()
        repo_root = _find_quantumvitas_root()
        repo_pseudo_dir = str(repo_root / "pseudo") if repo_root else ""
        
        return {
            "store_dir": config.store_dir,
            "seed_dir": config.seed_dir,
            "allow_download": config.allow_download,
            "repo_pseudo_dir": repo_pseudo_dir,
            "default_store_dir": PseudoConfig.get_default_store_dir(),
            "default_seed_dir": PseudoConfig.get_default_seed_dir(),
        }
    
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
        from quantumvitas.core.pseudo_config import (
            load_pseudo_config,
            save_pseudo_config,
            PseudoConfig,
            _find_quantumvitas_root,
        )
        
        config = load_pseudo_config()
        
        # Update fields if provided
        if "store_dir" in payload:
            config.store_dir = payload["store_dir"] or PseudoConfig.get_default_store_dir()
        if "seed_dir" in payload:
            config.seed_dir = payload["seed_dir"] or PseudoConfig.get_default_seed_dir()
        if "allow_download" in payload:
            config.allow_download = bool(payload["allow_download"])
        
        save_pseudo_config(config)
        
        repo_root = _find_quantumvitas_root()
        repo_pseudo_dir = str(repo_root / "pseudo") if repo_root else ""
        
        return {
            "store_dir": config.store_dir,
            "seed_dir": config.seed_dir,
            "allow_download": config.allow_download,
            "repo_pseudo_dir": repo_pseudo_dir,
            "default_store_dir": PseudoConfig.get_default_store_dir(),
            "default_seed_dir": PseudoConfig.get_default_seed_dir(),
        }
    
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
        from quantumvitas.core.pseudo_config import (
            load_pseudo_config,
            validate_pseudo_config,
        )
        
        config = load_pseudo_config()
        result = validate_pseudo_config(config)
        return result.to_dict()
    
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
        from quantumvitas.core.pseudo_config import (
            load_pseudo_config,
            init_pseudo_dirs,
        )
        
        config = load_pseudo_config()
        return init_pseudo_dirs(config)
    
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
        from quantumvitas.core.pseudo_config import (
            load_pseudo_config,
            install_sssp_from_seed,
            install_all_sssp_from_seed,
        )
        from pathlib import Path
        
        config = load_pseudo_config()
        
        if not config.seed_dir:
            return {
                "success": False,
                "messages": [],
                "errors": ["Seed directory not configured"],
            }
        
        if not config.store_dir:
            return {
                "success": False,
                "messages": [],
                "errors": ["Store directory not configured"],
            }
        
        seed_dir = Path(config.seed_dir)
        store_dir = Path(config.store_dir)
        
        version = payload.get("version")
        flavor = payload.get("flavor")
        
        if version and flavor:
            # Install specific version/flavor
            result = install_sssp_from_seed(seed_dir, store_dir, version, flavor)
            return result
        else:
            # Install all available
            return install_all_sssp_from_seed(seed_dir, store_dir)
    
    def _handle_list_installed_sssp(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List installed SSSP libraries in store.
        
        Payload: (none required, uses saved config)
        
        Returns:
            libraries: List of SSSPLibraryInfo dicts
        """
        from quantumvitas.core.pseudo_config import (
            load_pseudo_config,
            list_installed_sssp,
        )
        from pathlib import Path
        
        config = load_pseudo_config()
        
        if not config.store_dir:
            return {"libraries": []}
        
        store_dir = Path(config.store_dir)
        libraries = list_installed_sssp(store_dir)
        
        return {
            "libraries": [lib.to_dict() for lib in libraries],
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
        from quantumvitas.core.pseudo_config import (
            load_pseudo_config,
            download_sssp_library,
            list_installed_sssp,
        )
        from pathlib import Path
        
        flavor = payload.get("flavor")
        if not flavor:
            raise ValueError("flavor is required ('efficiency' or 'precision')")
        if flavor not in ("efficiency", "precision"):
            raise ValueError(f"Invalid flavor: {flavor}. Must be 'efficiency' or 'precision'")
        
        version = payload.get("version", "1.3.0")
        force = payload.get("force", False)
        
        config = load_pseudo_config()
        
        if not config.store_dir:
            return {
                "success": False,
                "errors": ["Store directory not configured"],
                "messages": [],
            }
        
        store_dir = Path(config.store_dir)
        result = download_sssp_library(
            store_dir=store_dir,
            flavor=flavor,
            version=version,
            force=force,
            allow_download=config.allow_download,
        )
        
        # Add installed libraries to response
        result["installed_libraries"] = [lib.to_dict() for lib in list_installed_sssp(store_dir)]
        
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
        from quantumvitas.core.pseudo_config import (
            load_pseudo_config,
            download_all_sssp,
            list_installed_sssp,
        )
        from pathlib import Path
        
        force = payload.get("force", False)
        
        config = load_pseudo_config()
        
        if not config.store_dir:
            return {
                "success": False,
                "errors": ["Store directory not configured"],
                "messages": [],
            }
        
        store_dir = Path(config.store_dir)
        result = download_all_sssp(
            store_dir=store_dir,
            force=force,
            allow_download=config.allow_download,
        )
        
        # Add installed libraries to response
        result["installed_libraries"] = [lib.to_dict() for lib in list_installed_sssp(store_dir)]
        
        return result
    
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
    
    def _update_logging_level(self, level: str):
        """
        Update Python logging level at runtime.
        
        Args:
            level: "INFO" or "DEBUG"
        """
        log_level = logging.DEBUG if level == "DEBUG" else logging.INFO
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
    
    def _handle_list_qe_ui_parameters(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get UI parameter metadata for a QE module and step type.
        
        Payload:
            module: str (required) - QE module name (e.g., "pw", "bands")
            step_type: str (required) - Step type (e.g., "scf", "nscf", "dos", "bands")
        
        Returns:
            List of UI parameter descriptors with namelist, name, label, type, unit, etc.
        """
        module = payload.get("module", "").strip().lower()
        step_type = payload.get("step_type", "").strip().lower()
        
        if not module:
            raise ValueError("'module' is required in payload")
        if not step_type:
            raise ValueError("'step_type' is required in payload")
        
        # Validate module is supported
        supported_modules = list_supported_modules()
        if module not in supported_modules:
            raise ValueError(
                f"Unknown module '{module}'. Supported: {', '.join(sorted(supported_modules))}"
            )
        
        # Log at info level for visibility (short log line)
        self.logger.info(
            "[RPC] list_qe_ui_parameters (module: %s, step_type: %s)",
            module,
            step_type,
        )
        
        # Get UI parameters
        ui_params = get_ui_parameters(module, step_type)
        
        # Convert QEUIParam objects to dicts for JSON serialization
        result = []
        for param in ui_params:
            param_dict = {
                "namelist": param.namelist,
                "name": param.name,
                "label": param.label,
                "type": param.type,
            }
            if param.unit:
                param_dict["unit"] = param.unit
            if param.description:
                param_dict["description"] = param.description
            if param.options:
                param_dict["options"] = param.options
            if param.importance:
                param_dict["importance"] = param.importance
            result.append(param_dict)
        
        return {"parameters": result}
    
    def _handle_list_qe_parameter_metadata(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Browse QE parameter metadata (modules, sections, parameters, search).
        
        Payload:
            operation: str (required) - One of: "list_modules", "list_sections", "list_parameters", "search"
            
            For "list_modules": no additional fields needed.
            
            For "list_sections": requires "module": str
            
            For "list_parameters": requires "module": str, "section": str (e.g., "&SYSTEM")
            
            For "search": requires "query": str (searches across all modules/sections)
        
        Returns:
            For "list_modules": {"modules": [{"id": "pw", "label": "pw.x"}, ...]}
            For "list_sections": {"sections": [{"id": "&SYSTEM", "kind": "namelist", "label": "&SYSTEM"}, ...]}
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
                        "id": module_id,
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
                from quantumvitas.data import get_module_card_sections
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
                            "id": section_normalized,  # For lookups
                            "name": section_normalized,  # Clean name without '&'
                            "label": section_normalized,  # Label is same as name for cards (no '&')
                            "kind": "card",
                        })
                    elif section_part.startswith("&"):
                        # This is a namelist
                        result.append({
                            "id": section_part,  # Keep original for backward compatibility (with '&')
                            "name": section_normalized,  # Clean name without '&'
                            "label": section_part,  # Label includes '&' prefix for namelists
                            "kind": "namelist",
                        })
                    else:
                        # Section without '&' prefix - could be a card or namelist
                        # If it's in card_metadata, it's a card; otherwise, treat as namelist
                        if section_normalized in card_names_upper:
                            result.append({
                                "id": section_normalized,
                                "name": section_normalized,
                                "label": section_normalized,
                                "kind": "card",
                            })
                        else:
                            # Treat as namelist (add '&' prefix for label)
                            result.append({
                                "id": f"&{section_normalized}",
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
                            "id": card_name_upper,
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
                    params = qe_metadata._iter_params(module)
                    
                    # Filter by section
                    for param in params:
                        param_namelist = param.get("namelist", "")
                        param_section = f"&{param_namelist.upper()}" if param_namelist else ""
                        
                        # Match section
                        if param_section == section_with_prefix or param_namelist.upper() == section_normalized:
                            param_dict = {
                                "name": param.get("name"),
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
                                param_key = f"{section_with_prefix}.{param.get('name')}"
                                param_meta = parameters_map.get(param_key)
                                if param_meta and "indexing" in param_meta:
                                    param_dict["indexing"] = param_meta["indexing"]
                            
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
                    from quantumvitas.data import get_module_card_sections
                    card_sections = get_module_card_sections(module)
                    sections_dict = get_module_param_sections(module)
                    
                    # Search namelist parameters
                    params = qe_metadata._iter_params(module)
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
    
    def _handle_reload_qe_parameter_metadata(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reload QE parameter metadata from disk by clearing the cache.
        
        This clears the in-memory metadata cache, forcing the next access to
        re-read the JSON file from disk. This is useful when the metadata file
        has been updated externally.
        
        Payload:
            No fields required.
        
        Returns:
            {"modules": [{"id": "pw", "label": "pw.x"}, ...]} - Fresh list of modules
            after reload, so the frontend can immediately refresh.
        """
        self.log("[RPC] reload_qe_parameter_metadata")
        
        try:
            # Clear the cache
            reload_metadata()
            
            # Get metadata file info after reload
            metadata_info = get_metadata_file_info()
            
            # Optionally return modules so the frontend can immediately refresh
            modules = list_supported_modules()
            result = []
            for module_id in modules:
                doc_url = get_module_doc_url(module_id)
                label = f"{module_id}.x" if module_id else module_id
                result.append({
                    "id": module_id,
                    "label": label,
                    "doc_url": doc_url,
                })
            
            self.log(f"[RPC] reload_qe_parameter_metadata: cache cleared, {len(result)} modules available")
            return {
                "modules": result,
                "metadata_path_abs": metadata_info.get("metadata_path_abs"),
                "schema_version": metadata_info.get("schema_version"),
            }
        
        except (RuntimeError, FileNotFoundError) as e:
            # Metadata loading errors should be user-friendly
            raise ValueError(f"Failed to reload QE parameter metadata: {e}. Run `python tools/extract_qe_parameters_v3.py` to generate it.") from e
    
    def _handle_get_qe_parameter_metadata_debug_info(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get QE metadata load state for debug/internal use.
        
        This command is intended for Settings/Debug UI only, not for customer-facing features.
        
        Payload:
            No fields required.
        
        Returns:
            {
                "loaded_via": "cache" | "disk" | "not_loaded",
                "loaded_at": "<ISO timestamp>" | null,
                "schema_version": int | null,
                "path_abs": str | null,
            }
        """
        self.log("[RPC] get_qe_parameter_metadata_debug_info")
        
        try:
            debug_info = get_qe_metadata_debug_info()
            return debug_info
        except Exception as e:
            self.log(f"[RPC] get_qe_parameter_metadata_debug_info error: {e}")
            # Return safe defaults on error
            return {
                "loaded_via": "not_loaded",
                "loaded_at": None,
                "schema_version": None,
                "path_abs": None,
            }
    
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
    
    def _handle_list_calculations(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List calculations in project.
        
        Payload:
            project_root: str - Path to project root
        """
        project_root = self._require_path(payload, "project_root")
        
        # list_calculations_data uses Project.open() which builds its own index internally
        # This keeps Project.open() self-contained and avoids index mismatches
        calculations = QVService.list_calculations_data(project_root)
        return {"calculations": calculations, "count": len(calculations)}
    
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
        from quantumvitas.core.context import find_path_context_from_pwd, ContextNotFoundError
        
        start_dir = Path(payload.get("start_dir", "")).resolve()
        if not start_dir.exists():
            return {"found": False, "project_root": None}
        
        try:
            ctx = find_path_context_from_pwd(start_dir)
            return {"found": True, "project_root": str(ctx.project_root)}
        except ContextNotFoundError:
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
        
        # Pass cached index for in-place registry updates
        # Note: QVService.import_structure loads config internally; we only pass index
        cache = self.state.get_cache(project_root)
        result = QVService.import_structure(
            project_root=project_root,
            source=source_file,
            name=name,
            index=cache.index,
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
    
    def _handle_structure_search_online(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search online structures (OPTIMADE + COD).
        
        Payload:
            query: str - Chemical formula (e.g., "Si", "MoS2")
            max_results: int - Maximum number of results (default: 10)
        """
        from quantumvitas.io.online_cache import OnlineStructureCache, CandidateSummary
        from quantumvitas.io.online_search import search_online_structures
        import uuid
        import json
        
        query = self._require_str(payload, "query")
        max_results = payload.get("max_results", 10)
        
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Search online (returns optimade_base for 2-step fetch)
        source_summary, candidates, structures, optimade_base = search_online_structures(query, max_results=max_results)
        
        # Cache results
        project_root = self._require_path(payload, "project_root")
        cache_dir = project_root / "structures" / "cache"
        cache = OnlineStructureCache(cache_dir)
        
        # Store optimade_base in source_summary if available
        source_summary_with_base = source_summary
        if optimade_base:
            source_summary_with_base = f"{source_summary}|base={optimade_base}"
        
        cache.create_session(session_id, query, source_summary_with_base)
        
        # Cache candidates and structures (structures may be None for OPTIMADE)
        for rank, (candidate, structure) in enumerate(zip(candidates, structures)):
            if structure is not None:
                # COD entry - cache structure now
                cache.add_candidate(session_id, candidate, structure, rank)
            else:
                # OPTIMADE entry - store metadata only, structure fetched later
                # Store optimade_base in candidate metadata
                cache.add_candidate_metadata_only(session_id, candidate, rank, optimade_base)
        
        # Convert candidates to dict for JSON serialization
        candidates_dict = [
            {
                "candidate_id": c.candidate_id,
                "label": c.label,
                "source": c.source,
                "source_id": c.source_id,
                "nsites": c.nsites,
                "spacegroup": c.spacegroup,
                "flags": c.flags,
                "score": c.score,
            }
            for c in candidates
        ]
        
        return {
            "session_id": session_id,
            "candidates": candidates_dict,
        }
    
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
        from quantumvitas.io.online_cache import OnlineStructureCache
        from quantumvitas.io.online_search import fetch_structure_from_optimade, score_candidate
        from quantumvitas.analysis.structure_viz import (
            build_display_atoms,
            build_bonds,
            get_element_color,
            get_element_radius,
            DisplayModeParams,
        )
        from quantumvitas.io.structure_io import write_structure
        import tempfile
        import numpy as np
        
        project_root = self._require_path(payload, "project_root")
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
        
        # Load from cache
        cache_dir = project_root / "structures" / "cache"
        cache = OnlineStructureCache(cache_dir)
        
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
        
        # If not in cache, try fetching from OPTIMADE (2-step approach)
        if structure is None:
            if candidate.source == "optimade":
                # Get optimade_base from metadata
                metadata = cache.get_candidate_metadata(session_id, candidate_id)
                optimade_base = metadata.get("optimade_base") if metadata else None
                
                if optimade_base and candidate.source_id:
                    # Fetch structure from OPTIMADE
                    structure, optimade_raw_data = fetch_structure_from_optimade(optimade_base, candidate.source_id)
                    
                    if structure:
                        # Score and update candidate
                        from quantumvitas.io.online_search import reduce_formula, score_candidate
                        # Get query from session
                        session_info = cache.get_session_info(session_id)
                        query = session_info.query if session_info else ""
                        query_reduced = reduce_formula(query) if query else ""
                        score, flags = score_candidate(structure, "optimade", query_reduced, {})
                        candidate.score = score
                        candidate.flags = flags
                        candidate.nsites = len(structure)
                        
                        # Cache the fetched structure
                        # Find rank
                        rank = next((i for i, c in enumerate(candidates) if c.candidate_id == candidate_id), 0)
                        cache.add_candidate(session_id, candidate, structure, rank)
                        
                        # Store raw OPTIMADE data in cache metadata for provenance
                        # We'll store it in the meta BLOB of the structures table
                        if optimade_raw_data:
                            import json
                            import sqlite3
                            meta_data = json.dumps({"optimade_raw": optimade_raw_data})
                            # Update structure meta in cache
                            conn = sqlite3.connect(cache.db_path)
                            try:
                                cursor = conn.cursor()
                                structure_key = cache._compute_structure_key(structure)
                                cursor.execute("""
                                    UPDATE structures SET meta = ? WHERE structure_key = ?
                                """, (meta_data.encode('utf-8'), structure_key))
                                conn.commit()
                            finally:
                                conn.close()
        
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
                from quantumvitas.io.online_search import extract_provenance
                
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
        
        # Use shared payload builder with timing (same function as project structures)
        # This pipeline:
        # - Canonicalizes structure (wraps frac coords into [0,1))
        # - Builds display atoms for the chosen mode
        # - Computes bonds from the exact same atom list that is rendered
        # - All using Cartesian coordinates only
        vis_payload = QVService._build_structure_vis_payload(
            structure,
            params,
            structure_meta={"structure_id": f"online:{candidate_id}"},  # Mark as online for logging only
            trace_id=trace_id,
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
    
    def _handle_structure_import_online_candidate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Import an online candidate structure into the project.
        
        Payload:
            project_root: str - Path to project root
            session_id: str - Session ID from search
            candidate_id: str - Candidate ID
            name: str - Optional structure name
        """
        from quantumvitas.io.online_cache import OnlineStructureCache
        from quantumvitas.io.structure_io import write_structure
        from quantumvitas.core.resources import meta_from_name, ensure_relative_path, generate_unique_name_and_slug
        from quantumvitas.core.project_utils import load_project_config, save_project_config, collect_slugs
        import tempfile
        
        project_root = self._require_path(payload, "project_root")
        session_id = self._require_str(payload, "session_id")
        candidate_id = self._require_str(payload, "candidate_id")
        name = payload.get("name")
        
        # Load structure from cache
        cache_dir = project_root / "structures" / "cache"
        cache = OnlineStructureCache(cache_dir)
        
        structure = cache.get_structure(session_id, candidate_id)
        if structure is None:
            raise ValueError(f"Candidate {candidate_id} not found in cache")
        
        # Get candidate info for default name
        candidates_list = cache.get_candidates(session_id)
        candidate = next((c for c in candidates_list if c.candidate_id == candidate_id), None)
        default_name = candidate.label if candidate else structure.composition.reduced_formula
        
        # Canonicalize structure (wrap coords, stable species ordering)
        from quantumvitas.analysis.structure_viz import canonicalize_structure_in_place
        canonicalize_structure_in_place(structure)
        
        # Generate unique name and slug
        config = load_project_config(project_root)
        structures = config.setdefault("structures", [])
        existing_slugs = collect_slugs(structures, project_root=project_root)
        
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
            "structure",
            name=final_name,
            path=ensure_relative_path(dest_path, base=project_root),
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
            "structure_id": meta.id,
        }
        structures.append(entry)
        save_project_config(project_root, config)
        
        # Update registry
        cache_state = self.state.get_cache(project_root)
        from quantumvitas.core.resolution import require_structure, update_registry_add_structure
        resolved = require_structure(project_root, final_slug, config=config, index=cache_state.index)
        if cache_state.index is not None:
            update_registry_add_structure(cache_state.index, resolved.meta, dest_path)
        
        return {
            "new_structure_id": meta.id,
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
        
        # Pass cached index and config for in-place registry updates
        cache = self.state.get_cache(project_root)
        result = QVService.rename_structure(
            project_root=project_root,
            selector=selector,
            new_name=new_name,
            index=cache.index,
            config=cache.config,
        )
        
        return result
    
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
            force: bool - Force delete even if used by calculations
        """
        project_root = self._require_path(payload, "project_root")
        selector = self._require_str(payload, "selector")
        force = payload.get("force", False)
        
        # Get structure name before deletion for response
        check = QVService.can_delete_structure(project_root, selector)
        structure_name = check.get("structure_name", selector)
        
        # Pass cached index for in-place registry updates
        # Note: QVService.delete_structure loads config internally; we only pass index
        cache = self.state.get_cache(project_root)
        QVService.delete_structure(
            project_root=project_root,
            selector=selector,
            force=force,
            index=cache.index,
        )
        
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
        from quantumvitas.core.templates import list_calculation_templates
        
        templates = list_calculation_templates()
        
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
        result = QVService.init_calculation(
            project_root=project_root,
            name=name,
            structure_selector=structure,
            template=template,
            index=cache.index,
            config=cache.config,
        )
        
        # Get calculation details
        calculations = QVService.list_calculations_data(project_root)
        new_wf = next((w for w in calculations if w.get("id") == result.meta.id), None)
        
        return {
            "calculation_id": result.meta.id,
            "name": result.meta.name,
            "slug": result.meta.slug,
            "n_steps": new_wf.get("n_steps", 0) if new_wf else 0,
        }
    
    # -------------------------------------------------------------------------
    # Calculation management handlers
    # -------------------------------------------------------------------------
    
    def _handle_rename_calculation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rename a calculation.
        
        Payload:
            project_root: str - Path to project root
            selector: str - Calculation selector
            new_name: str - New name
        """
        project_root = self._require_path(payload, "project_root")
        selector = self._require_str(payload, "selector")
        new_name = self._require_str(payload, "new_name")
        
        # Pass cached index and config for in-place registry updates
        cache = self.state.get_cache(project_root)
        result = QVService.rename_calculation(
            project_root=project_root,
            selector=selector,
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
            selector: str - Calculation selector
        """
        project_root = self._require_path(payload, "project_root")
        selector = self._require_str(payload, "selector")
        
        return QVService.can_delete_calculation(
            project_root=project_root,
            selector=selector,
        )
    
    def _handle_delete_calculation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete a calculation.
        
        Payload:
            project_root: str - Path to project root
            selector: str - Calculation selector
            force: bool - Force delete
        """
        project_root = self._require_path(payload, "project_root")
        selector = self._require_str(payload, "selector")
        force = payload.get("force", False)
        
        # Get calculation name before deletion for response
        check = QVService.can_delete_calculation(project_root, selector)
        calculation_name = check.get("calculation_name", selector)
        
        QVService.delete_calculation(
            project_root=project_root,
            selector=selector,
            force=force,
        )
        
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
        - Daemon: _handle_get_step_detail() resolves selectors via registry
        - Backend: QVService.get_step_detail() returns step metadata and parameters
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector (GUI uses calculation.slug)
            step: str - Step selector (GUI uses step.id ULID from calculation.steps[])
        
        Returns:
            Step detail dict with id, name, slug, step_type, parameters, etc.
        
        Error Handling:
            - If step file is missing (ghost step), QVService.get_step_detail raises ResourceNotFoundError
            - This is caught by handle_request() and converted to RPC error response:
              { ok: False, error: { code: "resource_not_found", kind: "step", ... } }
            - The RPC always resolves (never hangs) - either with data or with an error
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_step_with_fallback(project_root, calculation, step)
        
        # Pass cached index and config to QVService to avoid rebuilding ResourceIndex
        # This eliminates the ~20s delay from duplicate index building
        cache = self.state.get_cache(project_root)
        
        # CRITICAL: QVService.get_step_detail will raise ResourceNotFoundError
        # if the step file is missing (ghost step). This is caught by handle_request
        # and converted to a structured RPC error response with ok=False.
        # The RPC always resolves (never hangs) - either with data or with an error.
        return QVService.get_step_detail(
            project_root=project_root,
            calculation_selector=calculation,
            step_selector=step,
            index=cache.index,
            config=cache.config,
        )
    
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
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_step_with_fallback(project_root, calculation, step)
        
        # Pass cached index and config to avoid rebuilding ResourceIndex
        cache = self.state.get_cache(project_root)
        result = QVService.update_step_params(
            project_root=project_root,
            calculation_selector=calculation,
            step_selector=step,
            parameters=parameters,
            cards=cards,
            index=cache.index,
            config=cache.config,
        )
        
        # Parameter updates don't change registry (only change step file contents)
        
        return result
    
    def _handle_get_common_cards(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get view models for common cards (K_POINTS, etc.).
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            step: str - Step selector
            
        Returns:
            Dict with card view models
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        
        cache = self.state.get_cache(project_root)
        
        return QVService.get_common_cards(
            project_root=project_root,
            calculation_selector=calculation,
            step_selector=step,
            index=cache.index,
            config=cache.config,
        )
    
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
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        card_name = self._require_str(payload, "card_name")
        view_model = payload.get("view_model", {})
        if not isinstance(view_model, dict):
            raise ValueError("view_model must be a dict")
        
        cache = self.state.get_cache(project_root)
        
        return QVService.set_common_card(
            project_root=project_root,
            calculation_selector=calculation,
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
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        
        cache = self.state.get_cache(project_root)
        
        return QVService.get_pseudo_mapping(
            project_root=project_root,
            calculation_selector=calculation,
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
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        mapping = payload.get("mapping", {})
        if not isinstance(mapping, dict):
            raise ValueError("mapping must be a dict")
        library_preference = payload.get("library_preference")
        
        cache = self.state.get_cache(project_root)
        
        return QVService.set_pseudo_mapping(
            project_root=project_root,
            calculation_selector=calculation,
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
        
        return QVService.import_pseudo_files(
            project_root=project_root,
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
        
        return QVService.search_legacy_pseudos(
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
        
        return QVService.download_pseudo_by_filename(
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
            return QVService.download_pseudo_from_url(
                project_root=project_root,
                url=candidate["url"],
                dest_dir=dest_path,
                preferred_filename=candidate.get("filename"),
            )
        # Otherwise use download_pseudo_by_filename
        elif "filename" in candidate:
            cache = self.state.get_cache(project_root)
            return QVService.download_pseudo_by_filename(
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
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_step_with_fallback(project_root, calculation, step)
        
        # Pass cached index and config to avoid rebuilding ResourceIndex
        cache = self.state.get_cache(project_root)
        result = QVService.reset_step_params(
            project_root=project_root,
            calculation_selector=calculation,
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
        
        return QVService.get_relax_final_structure_preview(
            project_root=project_root,
            calculation_selector=calculation,
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
        
        result = QVService.save_relax_final_structure(
            project_root=project_root,
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
        QVService.delete_step_from_calculation(
            project_root=project_root,
            calculation_selector=calculation,
            step_selector=step,
            index=cache.index,
            config=cache.config,
        )
        
        # Registry updated in-place by QVService.delete_step_from_calculation (no rebuild needed)
        
        return {
            "status": "deleted",
        }
    
    def _handle_get_calculation_detail(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get detailed calculation information.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_calculation_with_fallback(project_root, calculation)
        
        # Pass cached index and config to QVService to avoid rebuilding ResourceIndex
        # This eliminates the ~20s delay from duplicate index building
        cache = self.state.get_cache(project_root)
        return QVService.get_calculation_detail(
            project_root=project_root,
            calculation_selector=calculation,
            index=cache.index,
            config=cache.config,
        )
    
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
        result = QVService.reorder_calculation_steps(
            project_root=project_root,
            calculation_selector=calculation,
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
        step_type = self._require_str(payload, "step_type")
        step_name = payload.get("step_name", step_type)
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_calculation_with_fallback(project_root, calculation)
        
        # Pass cached index and config to avoid rebuilding ResourceIndex
        cache = self.state.get_cache(project_root)
        result = QVService.add_step_to_calculation(
            project_root=project_root,
            calculation_selector=calculation,
            step_type=step_type,
            step_name=step_name,
            index=cache.index,
            config=cache.config,
        )
        
        # Registry updated in-place by QVService.add_step_to_calculation (no rebuild needed)
        
        return result
    
    def _handle_import_step_from_qe_input(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Import a QE input file as a step (preserves original parameters, no defaults).
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector (name, slug, or id)
            input_file: str - Path to QE input file (.in)
            step_name: str - Optional name for the new step (defaults to input file stem)
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        input_file = self._require_path(payload, "input_file")
        step_name = payload.get("step_name")
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_calculation_with_fallback(project_root, calculation)
        
        # Pass cached index and config to avoid rebuilding ResourceIndex
        cache = self.state.get_cache(project_root)
        result = QVService.import_step_from_qe_input(
            project_root=project_root,
            calculation_selector=calculation,
            input_file=input_file,
            step_name=step_name,
            index=cache.index,
            config=cache.config,
        )
        
        # Registry updated in-place by QVService.import_step_from_qe_input (no rebuild needed)
        
        return result
    
    def _handle_change_calculation_structure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Change calculation structure.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            new_structure: str - New structure selector
            update_steps: bool - Whether to update step structure fields (default True)
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        new_structure = self._require_str(payload, "new_structure")
        update_steps = payload.get("update_steps", True)
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_calculation_with_fallback(project_root, calculation)
        
        # Pass cached index and config to avoid rebuilding ResourceIndex
        cache = self.state.get_cache(project_root)
        result = QVService.change_calculation_structure(
            project_root=project_root,
            calculation_selector=calculation,
            new_structure=new_structure,
            update_steps=update_steps,
            index=cache.index,
            config=cache.config,
        )
        
        # Reorder doesn't change registry (only changes step order in calculation.yaml)
        
        return result
    
    def _handle_get_calculation_pseudo_mapping(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get calculation-level pseudopotential mapping.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            
        Returns:
            Dict with species, mapping, species_map, available_pseudos, warnings, sssp_defaults
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_calculation_with_fallback(project_root, calculation)
        
        # Pass cached index and config
        cache = self.state.get_cache(project_root)
        return QVService.get_calculation_pseudo_mapping(
            project_root=project_root,
            calculation_selector=calculation,
            index=cache.index,
            config=cache.config,
        )
    
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
        result = QVService.update_calculation_species_map(
            project_root=project_root,
            calculation_selector=calculation,
            species_map=species_map,
            index=cache.index,
            config=cache.config,
        )
        
        return result
    
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
        
        # Pass cached index and config to avoid rebuilding ResourceIndex
        cache = self.state.get_cache(project_root)
        return QVService.preflight_check(
            project_root=project_root,
            calculation_selector=calculation,
            step_selector=step,
            index=cache.index,
            config=cache.config,
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
    
    def _handle_ensure_calculation_analysis(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure analysis artifacts exist for a calculation.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            analysis_type: str - Type of analysis ("scf", "dos", "bands")
            step: str - Optional step selector (for SCF)
            force: bool - Force re-parse even if artifact exists (default false)
            
        Returns:
            ok: bool - Whether analysis succeeded
            analysis_type: str - Type of analysis
            artifact_path: str | null - Path to JSON artifact
            parsed_fresh: bool - True if just parsed (vs loaded from cache)
            error: str | null - Error message if failed
            summary: dict | null - Quick summary data
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        analysis_type = self._require_str(payload, "analysis_type")
        step = payload.get("step")
        force = payload.get("force", False)
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_calculation_with_fallback(project_root, calculation)
        if step:
            self._resolve_step_with_fallback(project_root, calculation, step)
        
        return QVService.ensure_calculation_analysis(
            project_root=project_root,
            calculation_selector=calculation,
            analysis_type=analysis_type,
            step_selector=step,
            force=force,
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
        
        return QVService.get_structure_vis_data(
            project_root=project_root,
            selector=selector,
            supercell=supercell,
            repeat_boundary=repeat_boundary,
            display_mode=display_mode,
            box_bounds=box_bounds,
            trace_id=trace_id,
        )
    
    def _handle_get_scf_convergence(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get SCF convergence data.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            step: str - Step selector
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step = self._require_str(payload, "step")
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_step_with_fallback(project_root, calculation, step)
        
        return QVService.get_scf_convergence_data(
            project_root=project_root,
            calculation_selector=calculation,
            step_selector=step,
        )
    
    def _handle_get_dos_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get DOS data for plotting.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            step: str - Optional step selector
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step = payload.get("step")
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_calculation_with_fallback(project_root, calculation)
        if step:
            self._resolve_step_with_fallback(project_root, calculation, step)
        
        return QVService.get_dos_data(
            project_root=project_root,
            calculation_selector=calculation,
            step_selector=step,
        )
    
    def _handle_get_band_structure_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get band structure data for plotting.
        
        Payload:
            project_root: str - Path to project root
            calculation: str - Calculation selector
            step: str - Optional step selector
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        step = payload.get("step")
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_calculation_with_fallback(project_root, calculation)
        if step:
            self._resolve_step_with_fallback(project_root, calculation, step)
        
        return QVService.get_band_structure_data(
            project_root=project_root,
            calculation_selector=calculation,
            step_selector=step,
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
        
        if analysis_type not in ("scf", "dos", "bands"):
            raise ValueError(f"Invalid analysis_type: {analysis_type}. Must be one of: scf, dos, bands")
        
        # Resolve with fallback to ensure cache is up-to-date
        self._resolve_calculation_with_fallback(project_root, calculation)
        
        result = QVService.get_reference_analysis(
            project_root=project_root,
            calculation_selector=calculation,
            analysis_type=analysis_type,  # type: ignore
        )
        
        # Return None-safe dict for JSON serialization
        return {"data": result, "has_reference": result is not None}
    
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
            
        Returns:
            job_id: str - ID of submitted job
            status: str - Initial status ("pending")
            target_name: str - Calculation name for display
        """
        project_root = self._require_path(payload, "project_root")
        calculation = self._require_str(payload, "calculation")
        strict = payload.get("strict", False)
        verbose = payload.get("verbose", False)
        
        # Resolve with fallback to ensure cache is up-to-date before submitting job
        calculation_resolved = self._resolve_calculation_with_fallback(project_root, calculation)
        
        # Pass cached index and config to avoid rebuilding ResourceIndex
        cache = self.state.get_cache(project_root)
        
        # Load calculation to get initial steps list and io_dir (for step progress visualization and I/O directory display)
        initial_steps = []
        initial_io_dir = None
        try:
            from quantumvitas.core.models import load_calculation
            from quantumvitas.calculation.runner import compute_io_dir_from_calculation_model
            calculation_path = calculation_resolved.absolute_path / "calculation.yaml" if calculation_resolved.absolute_path.is_dir() else calculation_resolved.absolute_path
            if calculation_path.exists():
                wf_model = load_calculation(calculation_path, project_root=project_root)
                # Initialize steps with pending status
                initial_steps = [
                    {
                        "step_id": step.step_id,
                        "step_type": step.type or "unknown",
                        "status": "pending",
                        "started_at": None,
                        "ended_at": None,
                    }
                    for step in wf_model.steps
                ]
                # Compute planned_io_dir using the same logic the runner uses (single source of truth)
                # This ensures pending jobs show the correct io_dir that will match the runner's final io_dir
                calculation_dir = calculation_resolved.absolute_path if calculation_resolved.absolute_path.is_dir() else calculation_resolved.absolute_path.parent
                planned_io_dir = compute_io_dir_from_calculation_model(calculation_dir, wf_model.working_dir)
                initial_io_dir = str(planned_io_dir)
        except Exception:
            # If we can't load calculation, just use empty steps and no io_dir
            pass
        
        # Submit job with target info for display
        job_id = self.job_manager.submit(
            job_type="run_calculation",
            func=QVService.run_calculation,
            params={
                "project_root": str(project_root),
                "calculation": calculation,
                "strict": strict,
            },
            target_name=calculation,
            project_root_display=str(project_root.resolve()),  # Normalize to absolute path
            initial_steps=initial_steps,  # Initialize steps at job creation
            initial_io_dir=initial_io_dir,  # Initialize io_dir at job creation (so it shows immediately)
            # kwargs for QVService.run_calculation
            project_root=project_root,
            calculation_selector=calculation,
            strict=strict,
            verbose=verbose,
            index=cache.index,
            config=cache.config,
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
        self._resolve_step_with_fallback(project_root, calculation, step)
        
        target_name = f"{calculation}/{step}"
        
        # Compute planned_io_dir using the same logic the runner uses (single source of truth)
        initial_io_dir = None
        try:
            from quantumvitas.core.models import load_calculation
            from quantumvitas.calculation.runner import compute_io_dir_from_calculation_model
            calculation_path = calculation_resolved.absolute_path / "calculation.yaml" if calculation_resolved.absolute_path.is_dir() else calculation_resolved.absolute_path
            if calculation_path.exists():
                wf_model = load_calculation(calculation_path, project_root=project_root)
                calculation_dir = calculation_resolved.absolute_path if calculation_resolved.absolute_path.is_dir() else calculation_resolved.absolute_path.parent
                planned_io_dir = compute_io_dir_from_calculation_model(calculation_dir, wf_model.working_dir)
                initial_io_dir = str(planned_io_dir)
        except Exception:
            pass
        
        # Submit job with target info for display
        job_id = self.job_manager.submit(
            job_type="run_step",
            func=QVService.run_step,
            params={
                "project_root": str(project_root),
                "calculation": calculation,
                "step": step,
            },
            target_name=target_name,
            project_root_display=str(project_root),
            initial_io_dir=initial_io_dir,  # Initialize io_dir at job creation (so it shows immediately)
            # kwargs for QVService.run_step
            project_root=project_root,
            calculation_selector=calculation,
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
    # Resolution helpers with cache fallback
    # -------------------------------------------------------------------------
    
    def _resolve_calculation_with_fallback(self, project_root: Path, selector: str):
        """
        Resolve calculation using cached index.
        
        NOTE: This helper NO LONGER auto-rebuilds on cache miss. The registry
        is only rebuilt in two cases:
        1. When a project is first loaded (get_cache)
        2. When explicitly requested via rebuild_project_registry RPC
        
        Write operations update the registry in-place without rebuilding.
        
        If the resource is not found, SelectorNotFoundError is raised immediately.
        The user should click the Refresh button to rebuild the registry.
        
        Args:
            project_root: Path to project root
            selector: Calculation selector (name, slug, id, or path)
            
        Returns:
            ResolvedResource for the calculation
            
        Raises:
            SelectorNotFoundError: If calculation not found
        """
        # Use cached index (no auto-rebuild on miss)
        cache = self.state.get_cache(project_root)
        return resolve_calculation(
            project_root,
            selector,
            index=cache.index,
            config=cache.config,
        )
    
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
        # Use cached index (no auto-rebuild on miss)
        cache = self.state.get_cache(project_root)
        return resolve_step(
            project_root,
            calculation_selector,
            step_selector,
            index=cache.index,
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
        
        # Get project name for logging
        try:
            config = load_project_config(project_root)
            project_name = config.get("meta", {}).get("name") or project_root.name
        except Exception:
            project_name = project_root.name
        
        # Take snapshot of current registry (if any)
        old_cache = self.state._caches.get(project_root)
        old_snapshot = self._snapshot_dag(old_cache.index if old_cache else None)
        
        # Rebuild the registry
        t0 = time.perf_counter()
        try:
            index = build_resource_index(project_root)
            config = load_project_config(project_root)
            self.state._caches[project_root] = ProjectCache(
                project_root=project_root,
                index=index,
                config=config,
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
        
        # Get project name for logging
        try:
            config = load_project_config(project_root)
            project_name = config.get("meta", {}).get("name") or project_root.name
        except Exception:
            project_name = project_root.name
        
        # Rebuild the registry
        t0 = time.perf_counter()
        try:
            index = build_resource_index(project_root)
            config = load_project_config(project_root)
            self.state._caches[project_root] = ProjectCache(
                project_root=project_root,
                index=index,
                config=config,
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
                "structures": { structure_id: { "slug": ..., "name": ... } },
                "calculations": {
                    calculation_id: {
                        "slug": ...,
                        "name": ...,
                        "steps": [step_id1, step_id2, ...]   # in order
                    },
                    ...
                }
            }
        """
        from quantumvitas.core.models import load_calculation
        
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
                        step_ids = [entry.step_id for entry in wf_model.steps if entry.step_id]
                    except Exception:
                        # If we can't load the calculation, just use empty steps
                        step_ids = []
                else:
                    step_ids = []
                
                snapshot["calculations"][resource_id] = {
                    "slug": meta.slug,
                    "name": meta.name,
                    "steps": step_ids,
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
                "structures_added": [ { "id": ..., "slug": ..., "suffix": ... }, ... ],
                "structures_removed": [ ... ],
                "calculations_added": [ { "id": ..., "slug": ..., "suffix": ... }, ... ],
                "calculations_removed": [ ... ],
                "calculations_changed": [
                    {
                        "calculation_id": ...,
                        "calculation_slug": ...,
                        "suffix": ...,
                        "steps_added": [ { "id": ..., "suffix": ... }, ... ],
                        "steps_removed": [ { "id": ..., "suffix": ... }, ... ],
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
                    "id": struct_id,
                    "slug": new_structures[struct_id]["slug"],
                    "name": new_structures[struct_id]["name"],
                    "suffix": _ulid_suffix(struct_id),
                })
        
        # Structures removed
        for struct_id in old_structures:
            if struct_id not in new_structures:
                diff["structures_removed"].append({
                    "id": struct_id,
                    "slug": old_structures[struct_id]["slug"],
                    "name": old_structures[struct_id]["name"],
                    "suffix": _ulid_suffix(struct_id),
                })
        
        # Calculations added
        for wf_id in new_calculations:
            if wf_id not in old_calculations:
                diff["calculations_added"].append({
                    "id": wf_id,
                    "slug": new_calculations[wf_id]["slug"],
                    "name": new_calculations[wf_id]["name"],
                    "suffix": _ulid_suffix(wf_id),
                })
        
        # Calculations removed
        for wf_id in old_calculations:
            if wf_id not in new_calculations:
                diff["calculations_removed"].append({
                    "id": wf_id,
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
                        "steps_added": [{"id": s, "suffix": _ulid_suffix(s)} for s in steps_added],
                        "steps_removed": [{"id": s, "suffix": _ulid_suffix(s)} for s in steps_removed],
                    })
        
        return diff
    
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

