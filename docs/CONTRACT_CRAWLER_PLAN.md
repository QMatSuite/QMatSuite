# Contract Crawler Implementation Plan

**Version**: 1.1 (Final Revision)
**Date**: 2026-01-28
**Status**: PLANNING (for Cursor Auto execution)

## Overview

This document provides a mechanical, step-by-step implementation plan for building a **Contract Crawler** system that:
1. Enumerates ALL daemon RPC methods programmatically
2. Auto-calls methods and validates JSON-serializable outputs
3. Compares current outputs against golden fixtures from commit 0873ebf
4. Ensures no silent contract drift occurs

## Critical Corrections (Final Revision)

**Phase 3 (Golden Generation) has been revised for correctness and mechanical execution**:

1. **Worktree import isolation enforced**: Runtime assertions verify git HEAD == 0873ebf and quantumvitas module loaded from worktree path, preventing editable install leakage

2. **Package copying strategy**: contract_crawler modules (introspection, payloads, crawler, recipes) are copied from current branch into 0873ebf worktree before execution, since 0873ebf won't have them

3. **Isolated PYTHONPATH**: Subprocess environment set to `PYTHONPATH=worktree/src:worktree/tests` to prevent Python from loading packages from editable install or site-packages

4. **Key-based normalization**: Normalization uses key names only (no value-content heuristics) to avoid accidentally normalizing deterministic values

5. **Source-aware comparison**: auto_crawler methods replayed with stored payload; recipe methods run fresh current recipe (IDs not replayable)

6. **Metadata enforcement**: Golden fixtures include baseline_commit, source, payload (auto_crawler), recipe_name (recipe)

---

## A) Repo Recon Summary

### A.1) Daemon RPC Method Registry Location

**File**: `src/quantumvitas/daemon/server.py`
**Lines**: 255-414
**Structure**: Instance dictionary `self._handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]`

```python
# In QVDaemon.__init__():
self._handlers = {
    "ping": self._handle_ping,
    "shutdown": self._handle_shutdown,
    # ... 109+ methods total
}
```

### A.2) How to Enumerate All Public RPC Methods Programmatically

```python
from quantumvitas.daemon.server import QVDaemon
from io import StringIO

daemon = QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())
all_methods = list(daemon._handlers.keys())
# Returns: ["ping", "shutdown", "detect_qe", ...]
```

### A.3) Request/Response Protocol

**Request format**:
```json
{"id": "req-123", "type": "method_name", "payload": {...}}
```

**Success response**:
```json
{"id": "req-123", "ok": true, "data": {...}}
```

**Error response**:
```json
{"id": "req-123", "ok": false, "error": {"code": "...", "message": "..."}}
```

### A.4) Main User Semantic Flows (GUI/CLI)

| Flow | Key Methods |
|------|-------------|
| Project Setup | `create_project`, `find_project_root`, `get_project_summary` |
| Structure Management | `import_structure`, `list_structures`, `rename_structure`, `delete_structure` |
| Calculation Setup | `create_calculation`, `list_calculations`, `get_calculation_detail`, `add_step_to_calculation` |
| Step Configuration | `get_step_detail`, `update_step_params`, `set_common_card`, `set_pseudo_mapping` |
| Preset Application | `detect_presets`, `apply_presets_to_step`, `apply_presets_to_calculation` |
| Job Execution | `run_calculation`, `run_step`, `get_job_status`, `get_job_logs`, `list_jobs` |
| Analysis | `ensure_calculation_analysis`, `get_scf_convergence`, `get_dos_data`, `get_band_structure_data` |
| History/Journal | `get_project_history`, `list_project_runs`, `get_run_revision` |

---

## B) Phased Implementation Plan

### Phase 0: Introspect Registry and Print Method Inventory

**Goal**: Create a programmatic inventory of all RPC methods with metadata.

**Files to create**:
- `tests/contract_crawler/__init__.py`
- `tests/contract_crawler/introspection.py`
- `tests/contract_crawler/test_introspection.py`

**Implementation**:

```python
# tests/contract_crawler/introspection.py
"""RPC method introspection utilities."""

import inspect
from dataclasses import dataclass
from io import StringIO
from typing import Any

from quantumvitas.daemon.server import QVDaemon


@dataclass
class RPCMethodInfo:
    """Metadata about an RPC method."""
    name: str
    handler_name: str
    signature: inspect.Signature
    docstring: str | None
    required_params: list[str]
    optional_params: list[str]


def get_all_rpc_methods() -> list[RPCMethodInfo]:
    """
    Enumerate all RPC methods from daemon handler registry.

    Returns:
        List of RPCMethodInfo objects sorted by name.
    """
    daemon = QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())
    methods = []

    for name, handler in daemon._handlers.items():
        sig = inspect.signature(handler)
        doc = inspect.getdoc(handler)

        # Parse handler docstrings for payload requirements
        required_params = []
        optional_params = []

        if doc:
            # Extract from "Payload:" section in docstring
            lines = doc.split('\n')
            in_payload = False
            for line in lines:
                stripped = line.strip()
                if stripped.lower().startswith('payload:'):
                    in_payload = True
                    continue
                if in_payload:
                    if stripped.startswith('-') or stripped.startswith('*'):
                        # Parse "- param_name: type - description"
                        if ':' in stripped:
                            param_part = stripped.lstrip('-* ').split(':')[0].strip()
                            if '(optional)' in stripped.lower():
                                optional_params.append(param_part)
                            else:
                                required_params.append(param_part)
                    elif stripped and not stripped.startswith(' '):
                        # End of Payload section
                        in_payload = False

        methods.append(RPCMethodInfo(
            name=name,
            handler_name=handler.__name__,
            signature=sig,
            docstring=doc,
            required_params=required_params,
            optional_params=optional_params,
        ))

    return sorted(methods, key=lambda m: m.name)


def get_method_categories() -> dict[str, list[str]]:
    """
    Categorize RPC methods by functional area.

    Returns:
        Dict mapping category name to list of method names.
    """
    # Categories derived from server.py comments
    return {
        "system": ["ping", "shutdown"],
        "environment": [
            "detect_qe", "get_env_info", "list_qe_engines", "discover_qe_engines",
            "set_qe_engine", "set_log_level", "set_debug_resolution", "get_debug_resolution",
            "list_qe_ui_parameters", "list_qe_parameter_metadata",
            "reload_qe_parameter_metadata", "get_qe_parameter_metadata_debug_info",
        ],
        "pseudo_config": [
            "get_pseudo_config", "set_pseudo_config", "validate_pseudo_config",
            "init_pseudo_dirs", "install_seed_to_store", "list_installed_sssp",
            "list_seed_archives", "download_sssp_library", "download_all_sssp",
            "resolve_project_pseudo_provenance", "import_seed_archives",
            "list_pseudo_archives_status", "install_pseudo_archive",
            "analyze_project_pseudo_effects",
        ],
        "library_manager": [
            "list_libraries", "get_library_status", "install_library",
            "remove_library", "repair_library", "compute_store_size",
        ],
        "project": [
            "get_project_summary", "list_structures", "list_calculations",
            "find_project_root", "rebuild_project_registry", "create_project",
        ],
        "structure": [
            "import_structure", "structure_search_online",
            "structure_get_online_candidate", "structure_import_online_candidate",
            "rename_structure", "delete_structure", "can_delete_structure",
        ],
        "calculation": [
            "list_calculation_templates", "create_calculation", "rename_calculation",
            "delete_calculation", "can_delete_calculation", "get_calculation_detail",
            "reorder_calculation_steps", "add_step_to_calculation",
            "import_step_from_qe_input", "change_calculation_structure",
            "get_calculation_pseudo_mapping", "update_calculation_species_map",
            "get_pseudo_options_for_calculation", "materialize_pseudo_file",
        ],
        "step": [
            "get_step_detail", "update_step_params", "reset_step_params",
            "get_common_cards", "set_common_card", "get_pseudo_mapping",
            "set_pseudo_mapping", "import_pseudo_files", "search_legacy_pseudos",
            "download_pseudo_by_filename", "download_pseudo_candidate",
            "get_relax_final_structure_preview", "save_relax_final_structure",
            "promote_relax_structure", "delete_step",
        ],
        "presets": [
            "get_preset_catalog", "detect_presets", "detect_workflow",
            "detect_workflow_for_calculation", "apply_presets_to_step",
            "apply_presets_to_calculation", "get_step_preset_footprints",
        ],
        "preflight": ["preflight_check"],
        "demo": ["create_demo_project", "list_demo_projects"],
        "analysis": [
            "ensure_calculation_analysis", "get_structure_vis", "get_scf_convergence",
            "get_dos_data", "get_band_structure_data", "get_reference_analysis",
            "list_step_artifacts", "read_step_artifact_text",
        ],
        "visualization_dev": ["list_wannier_3d_fixtures", "compile_fixture_volume"],
        "jobs": [
            "run_calculation", "run_step", "run_single_step", "get_job_status",
            "get_job_logs", "list_jobs", "job_counts", "cancel_job",
        ],
        "journal": ["list_journal_entries", "get_journal_entry"],
        "history": [
            "get_project_history", "get_run_revision", "list_project_runs",
            "pin_analysis_to_history", "can_pin_to_run", "get_pin_data",
            "get_latest_run_for_step", "delete_project_history",
        ],
        "workflow": ["list_workflow_templates", "instantiate_workflow"],
    }


def print_method_inventory():
    """Print formatted inventory of all RPC methods."""
    methods = get_all_rpc_methods()
    categories = get_method_categories()

    print(f"Total RPC methods: {len(methods)}")
    print("\n## By Category:\n")

    covered = set()
    for cat, names in categories.items():
        print(f"### {cat} ({len(names)} methods)")
        for name in names:
            print(f"  - {name}")
            covered.add(name)
        print()

    # Find uncategorized
    all_names = {m.name for m in methods}
    uncategorized = all_names - covered
    if uncategorized:
        print(f"### UNCATEGORIZED ({len(uncategorized)} methods)")
        for name in sorted(uncategorized):
            print(f"  - {name}")


if __name__ == "__main__":
    print_method_inventory()
```

**Test file**:

```python
# tests/contract_crawler/test_introspection.py
"""Tests for RPC method introspection."""

import pytest
from tests.contract_crawler.introspection import (
    get_all_rpc_methods,
    get_method_categories,
)


class TestRPCIntrospection:
    """Test RPC method enumeration."""

    def test_enumerate_all_methods(self):
        """All RPC methods can be enumerated."""
        methods = get_all_rpc_methods()
        assert len(methods) >= 100, f"Expected 100+ methods, got {len(methods)}"

    def test_ping_method_exists(self):
        """Essential ping method exists."""
        methods = get_all_rpc_methods()
        names = {m.name for m in methods}
        assert "ping" in names

    def test_all_methods_categorized(self):
        """All methods have a category (no orphans)."""
        methods = get_all_rpc_methods()
        categories = get_method_categories()

        categorized = set()
        for names in categories.values():
            categorized.update(names)

        all_names = {m.name for m in methods}
        uncategorized = all_names - categorized

        assert not uncategorized, f"Uncategorized methods: {uncategorized}"

    def test_handlers_have_docstrings(self):
        """Handlers should have docstrings (warning if missing)."""
        methods = get_all_rpc_methods()
        missing_docs = [m.name for m in methods if not m.docstring]

        # Warning, not failure - but track for coverage
        if missing_docs:
            pytest.warns(UserWarning, match=f"{len(missing_docs)} handlers lack docstrings")
```

**Acceptance Criteria**:
```bash
python -m pytest tests/contract_crawler/test_introspection.py -v --tb=short
# All tests pass
# Output shows 100+ methods enumerated
```

---

### Phase 1: Contract Crawler Auto-Calls Easy Methods

**Goal**: Auto-call methods that require no prerequisites (stateless) and validate JSON serialization.

**Files to create**:
- `tests/contract_crawler/crawler.py`
- `tests/contract_crawler/payloads.py`
- `tests/contract_crawler/test_auto_crawl.py`
- `tests/contract_crawler/coverage_report.py`

**Implementation**:

```python
# tests/contract_crawler/payloads.py
"""Minimal payload generators for RPC methods."""

from pathlib import Path
from typing import Any


def get_minimal_payload(method_name: str, project_root: Path | None = None) -> dict[str, Any] | None:
    """
    Generate minimal payload for an RPC method.

    Returns:
        Payload dict, or None if method requires a recipe (complex prerequisites).
    """
    # Stateless methods (no payload needed)
    STATELESS = {
        "ping": {},
        "get_env_info": {},
        "list_qe_engines": {},
        "discover_qe_engines": {},
        "get_debug_resolution": {},
        "list_qe_ui_parameters": {},
        "list_qe_parameter_metadata": {},
        "get_qe_parameter_metadata_debug_info": {},
        "get_pseudo_config": {},
        "list_installed_sssp": {},
        "list_seed_archives": {},
        "list_libraries": {},
        "list_pseudo_archives_status": {},
        "compute_store_size": {},
        "list_calculation_templates": {},
        "get_preset_catalog": {},
        "list_demo_projects": {},
        "list_workflow_templates": {},
        "list_wannier_3d_fixtures": {},
        "job_counts": {},
        "list_jobs": {},
    }

    if method_name in STATELESS:
        return STATELESS[method_name]

    # Methods requiring project_root only
    PROJECT_ONLY = {
        "get_project_summary",
        "list_structures",
        "list_calculations",
        "list_journal_entries",
        "get_project_history",
        "list_project_runs",
    }

    if method_name in PROJECT_ONLY:
        if project_root is None:
            return None  # Needs recipe
        return {"project_root": str(project_root)}

    # Methods with simple parameters
    SIMPLE_PARAMS = {
        "set_log_level": {"level": "INFO"},
        "set_debug_resolution": {"enabled": False},
        "find_project_root": {"cwd": "."},
    }

    if method_name in SIMPLE_PARAMS:
        return SIMPLE_PARAMS[method_name]

    # Complex methods - require recipes
    return None


def get_methods_needing_recipes() -> set[str]:
    """
    Return set of method names that require explicit recipes.

    These methods have complex prerequisites:
    - Require existing resources (calculations, structures, steps)
    - Perform mutations that need setup/teardown
    - Require external state (QE installed, network access)
    """
    return {
        # Mutations requiring existing resources
        "rename_structure", "delete_structure", "can_delete_structure",
        "rename_calculation", "delete_calculation", "can_delete_calculation",
        "get_calculation_detail", "reorder_calculation_steps",
        "add_step_to_calculation", "import_step_from_qe_input",
        "change_calculation_structure", "get_calculation_pseudo_mapping",
        "update_calculation_species_map", "get_pseudo_options_for_calculation",
        "materialize_pseudo_file", "delete_step",

        # Step operations requiring calculation context
        "get_step_detail", "update_step_params", "reset_step_params",
        "get_common_cards", "set_common_card", "get_pseudo_mapping",
        "set_pseudo_mapping", "get_relax_final_structure_preview",
        "save_relax_final_structure", "promote_relax_structure",

        # Preset operations requiring step context
        "detect_presets", "detect_workflow_for_calculation",
        "apply_presets_to_step", "apply_presets_to_calculation",
        "get_step_preset_footprints",

        # Analysis requiring completed runs
        "ensure_calculation_analysis", "get_structure_vis",
        "get_scf_convergence", "get_dos_data", "get_band_structure_data",
        "get_reference_analysis", "list_step_artifacts", "read_step_artifact_text",

        # Job operations requiring running jobs
        "run_calculation", "run_step", "run_single_step",
        "get_job_status", "get_job_logs", "cancel_job",

        # History operations requiring existing runs
        "get_run_revision", "pin_analysis_to_history",
        "can_pin_to_run", "get_pin_data", "get_latest_run_for_step",
        "delete_project_history", "get_journal_entry",

        # Pseudo operations requiring network/files
        "set_pseudo_config", "validate_pseudo_config", "init_pseudo_dirs",
        "install_seed_to_store", "download_sssp_library", "download_all_sssp",
        "resolve_project_pseudo_provenance", "import_seed_archives",
        "install_pseudo_archive", "analyze_project_pseudo_effects",
        "import_pseudo_files", "search_legacy_pseudos",
        "download_pseudo_by_filename", "download_pseudo_candidate",

        # Library operations requiring network
        "get_library_status", "install_library", "remove_library", "repair_library",

        # Project mutations
        "create_project", "import_structure", "create_calculation",
        "rebuild_project_registry",

        # Online search requiring network
        "structure_search_online", "structure_get_online_candidate",
        "structure_import_online_candidate",

        # Preflight requiring calculation context
        "preflight_check",

        # Demo requiring write access
        "create_demo_project",

        # Dev endpoints
        "compile_fixture_volume",

        # System mutations
        "shutdown", "set_qe_engine", "reload_qe_parameter_metadata",

        # Workflow requiring calculation context
        "detect_workflow", "instantiate_workflow",
    }
```

```python
# tests/contract_crawler/crawler.py
"""Contract crawler for daemon RPC methods."""

import json
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any

from quantumvitas.daemon.server import QVDaemon, RPCRequest

from .introspection import get_all_rpc_methods
from .payloads import get_minimal_payload, get_methods_needing_recipes


@dataclass
class CrawlResult:
    """Result of crawling a single RPC method."""
    method_name: str
    success: bool
    response_data: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    json_serializable: bool = True
    serialization_error: str | None = None
    needs_recipe: bool = False
    skipped_reason: str | None = None


@dataclass
class CrawlReport:
    """Aggregated crawl results."""
    results: list[CrawlResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def covered(self) -> list[CrawlResult]:
        return [r for r in self.results if r.success and not r.needs_recipe]

    @property
    def needs_recipe(self) -> list[CrawlResult]:
        return [r for r in self.results if r.needs_recipe]

    @property
    def failed(self) -> list[CrawlResult]:
        return [r for r in self.results if not r.success and not r.needs_recipe]

    @property
    def not_json_serializable(self) -> list[CrawlResult]:
        return [r for r in self.results if not r.json_serializable]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "covered": len(self.covered),
            "needs_recipe": len(self.needs_recipe),
            "failed": len(self.failed),
            "not_json_serializable": len(self.not_json_serializable),
            "coverage_pct": round(len(self.covered) / self.total * 100, 1) if self.total else 0,
            "results": [
                {
                    "method": r.method_name,
                    "status": "covered" if r.success else ("needs_recipe" if r.needs_recipe else "failed"),
                    "json_ok": r.json_serializable,
                    "error": r.error or r.serialization_error,
                }
                for r in self.results
            ],
        }


def crawl_method(
    daemon: QVDaemon,
    method_name: str,
    payload: dict[str, Any],
) -> CrawlResult:
    """
    Crawl a single RPC method.

    Args:
        daemon: QVDaemon instance
        method_name: RPC method name
        payload: Request payload

    Returns:
        CrawlResult with response data and validation status.
    """
    try:
        response = daemon.handle_request(RPCRequest(
            id=f"crawl-{method_name}",
            type=method_name,
            payload=payload,
        ))

        if not response.ok:
            return CrawlResult(
                method_name=method_name,
                success=False,
                error=response.error,
            )

        # Validate JSON serialization
        try:
            json_str = json.dumps(response.data)
            # Also verify roundtrip
            parsed = json.loads(json_str)

            return CrawlResult(
                method_name=method_name,
                success=True,
                response_data=parsed,
                json_serializable=True,
            )
        except (TypeError, ValueError) as e:
            return CrawlResult(
                method_name=method_name,
                success=True,
                response_data=response.data,
                json_serializable=False,
                serialization_error=str(e),
            )

    except Exception as e:
        return CrawlResult(
            method_name=method_name,
            success=False,
            error={"code": "exception", "message": str(e)},
        )


def crawl_all_methods(
    project_root: Path | None = None,
    include_recipes: bool = False,
) -> CrawlReport:
    """
    Crawl all RPC methods with minimal payloads.

    Args:
        project_root: Optional project path for project-scoped methods
        include_recipes: If True, skip recipe-required methods; else mark them

    Returns:
        CrawlReport with all results.
    """
    daemon = QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())
    methods = get_all_rpc_methods()
    needs_recipes = get_methods_needing_recipes()

    report = CrawlReport()

    for method in methods:
        name = method.name

        if name in needs_recipes:
            if include_recipes:
                continue  # Skip - will be covered by recipe tests
            report.results.append(CrawlResult(
                method_name=name,
                success=False,
                needs_recipe=True,
                skipped_reason="Requires recipe (complex prerequisites)",
            ))
            continue

        payload = get_minimal_payload(name, project_root)

        if payload is None:
            report.results.append(CrawlResult(
                method_name=name,
                success=False,
                needs_recipe=True,
                skipped_reason="No minimal payload defined",
            ))
            continue

        result = crawl_method(daemon, name, payload)
        report.results.append(result)

    return report
```

**Test file**:

```python
# tests/contract_crawler/test_auto_crawl.py
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
```

**Acceptance Criteria**:
```bash
python -m pytest tests/contract_crawler/test_auto_crawl.py -v --tb=short -n auto --dist=loadfile
# All tests pass
# 20+ stateless methods covered
# 0 JSON serialization failures
```

---

### Phase 2: Add Recipes for High-Value Flows

**Goal**: Add explicit "recipes" for complex methods that require setup.

**Files to create**:
- `tests/contract_crawler/recipes/__init__.py`
- `tests/contract_crawler/recipes/base.py`
- `tests/contract_crawler/recipes/structure_flow.py`
- `tests/contract_crawler/recipes/calculation_flow.py`
- `tests/contract_crawler/recipes/job_flow.py`
- `tests/contract_crawler/recipes/analysis_flow.py`
- `tests/contract_crawler/test_recipes.py`

**Recipe base class**:

```python
# tests/contract_crawler/recipes/base.py
"""Base class for RPC method recipes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from quantumvitas.daemon.server import QVDaemon, RPCRequest


@dataclass
class RecipeResult:
    """Result of executing a recipe."""
    recipe_name: str
    method_name: str
    success: bool
    response_data: dict[str, Any] | None = None
    error: str | None = None
    setup_ok: bool = True
    teardown_ok: bool = True


class Recipe(ABC):
    """Base class for RPC method test recipes."""

    method_name: str  # RPC method being tested
    description: str  # Human-readable description

    def __init__(self, tmp_path: Path):
        self.tmp_path = tmp_path
        self.project_root: Path | None = None
        self.daemon = QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())

    @abstractmethod
    def setup(self) -> bool:
        """
        Set up prerequisites for the method call.

        Returns:
            True if setup succeeded, False otherwise.
        """
        pass

    @abstractmethod
    def build_payload(self) -> dict[str, Any]:
        """
        Build the request payload.

        Returns:
            Payload dict for RPC call.
        """
        pass

    @abstractmethod
    def validate_response(self, response_data: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate the response data.

        Args:
            response_data: Response from RPC call

        Returns:
            Tuple of (is_valid, error_message)
        """
        pass

    def teardown(self) -> bool:
        """
        Clean up after test.

        Returns:
            True if teardown succeeded.
        """
        return True

    def execute(self) -> RecipeResult:
        """
        Execute the full recipe.

        Returns:
            RecipeResult with all execution details.
        """
        # Setup
        try:
            if not self.setup():
                return RecipeResult(
                    recipe_name=self.__class__.__name__,
                    method_name=self.method_name,
                    success=False,
                    error="Setup failed",
                    setup_ok=False,
                )
        except Exception as e:
            return RecipeResult(
                recipe_name=self.__class__.__name__,
                method_name=self.method_name,
                success=False,
                error=f"Setup exception: {e}",
                setup_ok=False,
            )

        # Execute
        try:
            payload = self.build_payload()
            response = self.daemon.handle_request(RPCRequest(
                id=f"recipe-{self.method_name}",
                type=self.method_name,
                payload=payload,
            ))

            if not response.ok:
                return RecipeResult(
                    recipe_name=self.__class__.__name__,
                    method_name=self.method_name,
                    success=False,
                    error=str(response.error),
                )

            # Validate
            is_valid, error = self.validate_response(response.data)

            return RecipeResult(
                recipe_name=self.__class__.__name__,
                method_name=self.method_name,
                success=is_valid,
                response_data=response.data if is_valid else None,
                error=error,
            )

        except Exception as e:
            return RecipeResult(
                recipe_name=self.__class__.__name__,
                method_name=self.method_name,
                success=False,
                error=f"Execution exception: {e}",
            )
        finally:
            # Teardown
            try:
                self.teardown()
            except Exception:
                pass  # Log but don't fail on teardown
```

**Example recipe for structure flow**:

```python
# tests/contract_crawler/recipes/structure_flow.py
"""Recipes for structure-related RPC methods."""

from pathlib import Path
from typing import Any

from pymatgen.core import Structure, Lattice

from quantumvitas.api import QVService

from .base import Recipe


class GetStepDetailRecipe(Recipe):
    """Recipe for get_step_detail method."""

    method_name = "get_step_detail"
    description = "Get step configuration details"

    def __init__(self, tmp_path: Path):
        super().__init__(tmp_path)
        self.calc_id: str | None = None
        self.step_id: str | None = None

    def setup(self) -> bool:
        """Create project with structure, calculation, and step."""
        from quantumvitas.api.utils import generate_resource_id

        # Create project
        self.project_root = self.tmp_path / "test_project"
        self.project_root.mkdir()
        QVService.init_project(self.project_root, name="test_project")

        # Create structure
        svc = QVService.get_service(self.project_root)
        structure = Structure(Lattice.cubic(5.43), ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        struct_dto = svc.structure.create(structure, name="silicon")

        # Create calculation with step
        calc_dto = svc.calculation.create(
            name="test_calc",
            structure_id=struct_dto.structure_id,
        )
        self.calc_id = calc_dto.calc_id

        # Add SCF step
        step_dto = svc.calculation.add_step(
            calc_selector=self.calc_id,
            step_type="qe_scf",
            step_id="scf",
        )
        self.step_id = step_dto.step_id

        return True

    def build_payload(self) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "calculation": self.calc_id,
            "step": self.step_id,
        }

    def validate_response(self, response_data: dict[str, Any]) -> tuple[bool, str | None]:
        # Required keys
        required = ["step_type", "parameters", "structure"]
        for key in required:
            if key not in response_data:
                return False, f"Missing required key: {key}"

        # JSON serializable check
        import json
        try:
            json.dumps(response_data)
        except (TypeError, ValueError) as e:
            return False, f"Not JSON serializable: {e}"

        return True, None
```

**Recipe test file**:

```python
# tests/contract_crawler/test_recipes.py
"""Tests for recipe-based RPC method coverage."""

import pytest
from pathlib import Path

from tests.contract_crawler.recipes.structure_flow import GetStepDetailRecipe
# Import more recipes as they're added


class TestStructureFlowRecipes:
    """Test structure-related recipes."""

    def test_get_step_detail_recipe(self, tmp_path: Path):
        """get_step_detail recipe executes successfully."""
        recipe = GetStepDetailRecipe(tmp_path)
        result = recipe.execute()

        assert result.setup_ok, f"Setup failed: {result.error}"
        assert result.success, f"Recipe failed: {result.error}"
        assert result.response_data is not None


# Registry of all recipes for coverage tracking
ALL_RECIPES = [
    GetStepDetailRecipe,
    # Add more recipes here
]


class TestRecipeCoverage:
    """Verify recipe coverage of complex methods."""

    def test_all_recipes_execute(self, tmp_path: Path):
        """All registered recipes execute successfully."""
        failures = []

        for recipe_cls in ALL_RECIPES:
            recipe = recipe_cls(tmp_path / recipe_cls.__name__)
            (tmp_path / recipe_cls.__name__).mkdir(exist_ok=True)

            result = recipe.execute()
            if not result.success:
                failures.append(f"{recipe_cls.__name__}: {result.error}")

        assert not failures, f"Recipe failures:\n" + "\n".join(failures)

    def test_recipe_methods_not_duplicated(self):
        """Each method has at most one recipe."""
        method_names = [r.method_name for r in ALL_RECIPES]
        duplicates = [m for m in method_names if method_names.count(m) > 1]

        assert not duplicates, f"Duplicate recipes for: {set(duplicates)}"
```

**Acceptance Criteria**:
```bash
python -m pytest tests/contract_crawler/test_recipes.py -v --tb=short -n auto --dist=loadfile
# All recipe tests pass
# Key flows covered: get_step_detail, get_calculation_detail, etc.
```

---

### Phase 3: Golden Comparison to Baseline (0873ebf)

**Goal**: Compare current outputs against golden fixtures generated from commit 0873ebf.

**CRITICAL FIXES** (for correctness and mechanical execution):
1. **Worktree import isolation**: Runtime assertions verify git HEAD and module paths to prevent editable install leakage
2. **Package copying**: contract_crawler modules copied into worktree (0873ebf won't have them)
3. **Isolated PYTHONPATH**: Subprocess env set to worktree-only paths
4. **Key-based normalization**: No value-content heuristics, only key-based replacement
5. **Source-aware comparison**: auto_crawler methods replayed with payload; recipe methods run fresh recipe
6. **Metadata enforcement**: Golden fixtures include baseline_commit, source, payload/recipe_name

**CRITICAL**: Golden fixtures MUST be generated from commit 0873ebf (pre-DTO baseline), NOT
from the current branch. This ensures we can detect drift relative to the known-good state.

**Files to create**:
- `tests/fixtures/golden_0873ebf/README.md`
- `tests/fixtures/golden_0873ebf/daemon/` (directory for per-method JSON files)
- `tests/fixtures/golden_contracts/generate_golden.py` (main generator script)
- `tests/fixtures/golden_contracts/worktree_runner.py` (runner executed inside worktree)
- `tests/contract_crawler/golden_comparison.py`
- `tests/contract_crawler/test_golden_contracts.py`

#### C) Golden Fixture Strategy

**C.1) Baseline Generation via Git Worktree + Crawler/Recipe Execution**

Golden fixtures are generated from commit 0873ebf using git worktree to avoid
polluting the current working tree. This is a ONE-TIME generation step.

**CRITICAL**: Golden generation covers ALL methods that auto-crawler or recipes successfully
call, NOT just a hardcoded stateless allowlist. This ensures maximal coverage and detects
drift for both simple and complex RPC methods.

**C.2) Implementation: Two-Script Strategy with Package Copying**

The golden generation uses a two-script approach:
1. **generate_golden.py**: Runs in main worktree, manages git worktree lifecycle, copies contract_crawler package into worktree, invokes runner with isolated PYTHONPATH
2. **worktree_runner.py**: Runs inside 0873ebf worktree (self-contained), executes crawler+recipes from copied modules, dumps JSON

**CRITICAL**: 0873ebf will NOT contain `tests/contract_crawler/` modules. Therefore:
- `generate_golden.py` MUST copy current `tests/contract_crawler/` into the worktree before execution
- `worktree_runner.py` runs with PYTHONPATH set to worktree-only paths to prevent editable install leakage
- Runtime assertions verify we're executing baseline code, not current branch code

```python
# tests/fixtures/golden_contracts/worktree_runner.py
"""
Worktree runner: executed INSIDE the 0873ebf worktree to generate golden fixtures.

This script is invoked by generate_golden.py from the main worktree.
It uses the daemon from 0873ebf and crawler/recipes copied into the worktree.

CRITICAL RUNTIME CHECKS:
- Verifies git HEAD == 0873ebf
- Verifies quantumvitas module is loaded from worktree (not editable install)

Outputs JSON to stdout for generate_golden.py to capture and write.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path

# Add worktree src to path (this script runs from worktree)
WORKTREE_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(WORKTREE_ROOT / "src"))
sys.path.insert(0, str(WORKTREE_ROOT / "tests"))

# Import from 0873ebf baseline
from quantumvitas.daemon.server import QVDaemon, RPCRequest
import quantumvitas

# CRITICAL: Runtime assertions to ensure worktree isolation
BASELINE_COMMIT = "0873ebf"

def verify_baseline_isolation():
    """
    Verify we are executing baseline code from worktree, not current branch.

    Checks:
    1. git HEAD matches BASELINE_COMMIT
    2. quantumvitas module is loaded from worktree path

    Raises AssertionError if isolation is violated.
    """
    # Check git HEAD
    git_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=WORKTREE_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert git_head.startswith(BASELINE_COMMIT), (
        f"ERROR: Worktree git HEAD is {git_head}, expected {BASELINE_COMMIT}. "
        f"Worktree isolation violated."
    )

    # Check quantumvitas module path
    qv_module_path = Path(quantumvitas.__file__).resolve()
    worktree_src = (WORKTREE_ROOT / "src").resolve()

    assert str(qv_module_path).startswith(str(worktree_src)), (
        f"ERROR: quantumvitas loaded from {qv_module_path}, expected under {worktree_src}. "
        f"Editable install leakage detected. Set PYTHONPATH correctly."
    )

    print(f"[VERIFIED] git HEAD: {git_head}", file=sys.stderr)
    print(f"[VERIFIED] quantumvitas from: {qv_module_path}", file=sys.stderr)


# Import crawler and recipes (copied into worktree by generate_golden.py)
from contract_crawler.crawler import crawl_all_methods
from contract_crawler.payloads import get_minimal_payload
from contract_crawler.recipes import ALL_RECIPES


# Non-deterministic fields to normalize (NARROWED: only truly non-deterministic)
NORMALIZE_FIELDS = {
    # ULIDs - truly non-deterministic
    "id", "structure_id", "calc_id", "step_id", "run_id", "job_id",
    "calculation_id", "entry_id",
    # Timestamps - truly non-deterministic
    "created_at", "updated_at", "started_at", "completed_at", "timestamp",
    # Paths containing temp directories - non-deterministic due to temp path
    "project_root", "log_path", "io_dir",
}

# Nested fields to normalize (dot notation)
NORMALIZE_NESTED = {
    "meta.id", "meta.created_at", "meta.updated_at",
}


def normalize_value(key: str, value, parent_key: str = ""):
    """
    Normalize non-deterministic fields for comparison.

    KEY-BASED NORMALIZATION (no heuristics):
    - If key in NORMALIZE_FIELDS or full_key in NORMALIZE_NESTED, replace with placeholder
    - Placeholder type depends on field name pattern
    - Do NOT examine value content to decide normalization
    """
    full_key = f"{parent_key}.{key}" if parent_key else key

    # Check if this field should be normalized (key-based only)
    if key in NORMALIZE_FIELDS or full_key in NORMALIZE_NESTED:
        # Determine placeholder by field name (not by value content)
        if "timestamp" in key.lower() or key in ("created_at", "updated_at", "started_at", "completed_at"):
            return "<NORMALIZED_TIMESTAMP>"
        elif "path" in key.lower() or key in ("project_root", "log_path", "io_dir"):
            return "<NORMALIZED_PATH>"
        else:
            # Default: ID-like fields
            return "<NORMALIZED_ID>"

    # Recursively normalize dicts and lists
    if isinstance(value, dict):
        return {k: normalize_value(k, v, full_key) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_value(key, item, parent_key) for item in value]

    return value


def normalize_response(response_data: dict) -> dict:
    """Normalize response for golden comparison."""
    return {k: normalize_value(k, v) for k, v in response_data.items()}


def main():
    """
    Run crawler and recipes, output JSON to stdout.

    Flow:
    1. Verify baseline isolation
    2. Run auto-crawler, store results with payload metadata
    3. Run recipes, store results with recipe_name metadata
    4. Output all golden fixtures as JSON to stdout
    """
    # STEP 1: Verify we're running baseline code
    verify_baseline_isolation()

    baseline_commit = "0873ebf"
    all_golden = {}

    print("\nRunning auto-crawler from 0873ebf...", file=sys.stderr)

    # STEP 2: Run auto-crawler
    report = crawl_all_methods()
    for result in report.results:
        if result.success and not result.needs_recipe:
            # Get the payload used for this method
            payload = get_minimal_payload(result.method_name)

            all_golden[result.method_name] = {
                "method": result.method_name,
                "success": True,
                "response": normalize_response(result.response_data),
                "payload": payload,  # Store for deterministic replay
                "baseline_commit": baseline_commit,
                "generated_at": datetime.now().isoformat(),
                "source": "auto_crawler",
            }
            print(f"  [auto] {result.method_name}: OK", file=sys.stderr)
        elif not result.needs_recipe:
            # Auto-crawler method that failed
            all_golden[result.method_name] = {
                "method": result.method_name,
                "success": False,
                "error": result.error or {"code": "unknown", "message": result.skipped_reason or "Unknown failure"},
                "baseline_commit": baseline_commit,
                "generated_at": datetime.now().isoformat(),
                "source": "auto_crawler",
            }
            print(f"  [auto] {result.method_name}: FAILED - {result.error}", file=sys.stderr)

    print(f"\nRunning {len(ALL_RECIPES)} recipes from 0873ebf...", file=sys.stderr)

    # STEP 3: Run recipes
    import tempfile
    temp_base = Path(tempfile.mkdtemp(prefix="qv_recipe_"))

    for recipe_cls in ALL_RECIPES:
        method_name = recipe_cls.method_name
        recipe_name = recipe_cls.__name__
        recipe_dir = temp_base / recipe_name
        recipe_dir.mkdir(exist_ok=True)

        try:
            recipe = recipe_cls(recipe_dir)
            result = recipe.execute()

            if result.success:
                all_golden[method_name] = {
                    "method": method_name,
                    "success": True,
                    "response": normalize_response(result.response_data),
                    "recipe_name": recipe_name,  # Store recipe class name for replay
                    "baseline_commit": baseline_commit,
                    "generated_at": datetime.now().isoformat(),
                    "source": "recipe",
                }
                print(f"  [recipe] {method_name} ({recipe_name}): OK", file=sys.stderr)
            else:
                all_golden[method_name] = {
                    "method": method_name,
                    "success": False,
                    "error": {"code": "recipe_failure", "message": result.error or "Unknown failure"},
                    "recipe_name": recipe_name,
                    "baseline_commit": baseline_commit,
                    "generated_at": datetime.now().isoformat(),
                    "source": "recipe",
                }
                print(f"  [recipe] {method_name} ({recipe_name}): FAILED - {result.error}", file=sys.stderr)
        except Exception as e:
            all_golden[method_name] = {
                "method": method_name,
                "success": False,
                "error": {"code": "recipe_exception", "message": str(e)},
                "recipe_name": recipe_name,
                "baseline_commit": baseline_commit,
                "generated_at": datetime.now().isoformat(),
                "source": "recipe",
            }
            print(f"  [recipe] {method_name} ({recipe_name}): EXCEPTION - {e}", file=sys.stderr)

    # STEP 4: Output JSON to stdout
    print(json.dumps(all_golden, indent=2))


if __name__ == "__main__":
    main()
```

```python
# tests/fixtures/golden_contracts/generate_golden.py
"""
Generate golden fixture files from commit 0873ebf.

This script:
1. Creates git worktree at 0873ebf
2. Copies contract_crawler package into worktree (0873ebf won't have it)
3. Copies worktree_runner.py into worktree
4. Runs worktree_runner.py with isolated PYTHONPATH (worktree-only)
5. Captures JSON output and writes to tests/fixtures/golden_0873ebf/daemon/
6. Cleans up worktree

Usage:
    python generate_golden.py    # Generate from 0873ebf worktree (REQUIRED)

IMPORTANT: Golden MUST come from 0873ebf. No --current flag allowed.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASELINE_COMMIT = "0873ebf"
REPO_ROOT = Path(__file__).parent.parent.parent.parent
GOLDEN_OUTPUT_DIR = REPO_ROOT / "tests" / "fixtures" / "golden_0873ebf" / "daemon"


def setup_worktree(commit: str, worktree_path: Path) -> bool:
    """
    Create git worktree for the specified commit.

    Args:
        commit: Git commit hash or ref
        worktree_path: Path where worktree will be created

    Returns:
        True if worktree created successfully.
    """
    # Remove existing worktree if present
    if worktree_path.exists():
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_path)],
            cwd=REPO_ROOT,
            capture_output=True,
        )

    # Create new worktree
    result = subprocess.run(
        ["git", "worktree", "add", str(worktree_path), commit],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"ERROR: Failed to create worktree: {result.stderr}", file=sys.stderr)
        return False

    return True


def cleanup_worktree(worktree_path: Path):
    """Remove git worktree."""
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(worktree_path)],
        cwd=REPO_ROOT,
        capture_output=True,
    )


def copy_contract_crawler_to_worktree(worktree_path: Path):
    """
    Copy contract_crawler package into worktree.

    0873ebf does not contain tests/contract_crawler/, so we must copy
    the current implementation (crawler, payloads, recipes, introspection)
    into the worktree before execution.

    Files copied:
    - tests/contract_crawler/__init__.py
    - tests/contract_crawler/introspection.py
    - tests/contract_crawler/payloads.py
    - tests/contract_crawler/crawler.py
    - tests/contract_crawler/recipes/ (entire directory)
    """
    src_crawler = REPO_ROOT / "tests" / "contract_crawler"
    dst_crawler = worktree_path / "tests" / "contract_crawler"

    # Create destination directory
    dst_crawler.mkdir(parents=True, exist_ok=True)

    # Copy package files
    files_to_copy = [
        "__init__.py",
        "introspection.py",
        "payloads.py",
        "crawler.py",
    ]

    for filename in files_to_copy:
        src_file = src_crawler / filename
        dst_file = dst_crawler / filename
        if src_file.exists():
            shutil.copy2(src_file, dst_file)
            print(f"  Copied {filename} to worktree", file=sys.stderr)
        else:
            print(f"  WARNING: {filename} not found, skipping", file=sys.stderr)

    # Copy recipes directory
    src_recipes = src_crawler / "recipes"
    dst_recipes = dst_crawler / "recipes"
    if src_recipes.exists():
        shutil.copytree(src_recipes, dst_recipes, dirs_exist_ok=True)
        print(f"  Copied recipes/ to worktree", file=sys.stderr)
    else:
        print(f"  WARNING: recipes/ not found, skipping", file=sys.stderr)


def run_worktree_runner(worktree_path: Path) -> dict:
    """
    Execute worktree_runner.py inside the worktree and capture JSON output.

    CRITICAL: Sets PYTHONPATH to worktree-only paths to prevent editable install leakage.

    Args:
        worktree_path: Path to git worktree

    Returns:
        Dict of method_name -> golden fixture data
    """
    runner_script = worktree_path / "tests" / "fixtures" / "golden_contracts" / "worktree_runner.py"

    print(f"Running worktree_runner.py from {worktree_path}...", file=sys.stderr)

    # Set PYTHONPATH to worktree-only paths
    # This prevents Python from loading quantumvitas from editable install
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([
        str(worktree_path / "src"),
        str(worktree_path / "tests"),
    ])

    # Run the runner script from worktree with isolated PYTHONPATH
    result = subprocess.run(
        [sys.executable, str(runner_script)],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        env=env,  # Use isolated environment
    )

    # Print stderr (contains verification output)
    print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        print(f"\nERROR: worktree_runner.py failed with exit code {result.returncode}", file=sys.stderr)
        print(f"stderr output shown above", file=sys.stderr)
        sys.exit(1)

    # Parse JSON from stdout
    try:
        all_golden = json.loads(result.stdout)
        return all_golden
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse JSON output from worktree_runner.py:", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
        print(f"stdout:\n{result.stdout}", file=sys.stderr)
        sys.exit(1)


def main():
    """
    Generate golden fixtures from commit 0873ebf via worktree runner.

    Flow:
    1. Create worktree at 0873ebf
    2. Copy contract_crawler package into worktree
    3. Copy worktree_runner.py into worktree
    4. Run worktree_runner.py with isolated PYTHONPATH
    5. Capture JSON and write to golden_0873ebf/daemon/
    6. Clean up worktree
    """
    print(f"Generating golden fixtures from baseline commit {BASELINE_COMMIT}")
    print("Using git worktree + worktree_runner.py...\n")

    # Create worktree in temp directory
    worktree_path = Path(tempfile.mkdtemp(prefix="qv_golden_0873ebf_"))

    try:
        # STEP 1: Create worktree
        if not setup_worktree(BASELINE_COMMIT, worktree_path):
            print("ERROR: Failed to create worktree. Aborting.", file=sys.stderr)
            sys.exit(1)

        print(f"Worktree created at: {worktree_path}\n")

        # STEP 2: Copy contract_crawler package into worktree
        print("Copying contract_crawler package into worktree...", file=sys.stderr)
        copy_contract_crawler_to_worktree(worktree_path)
        print()

        # STEP 3: Copy worktree_runner.py into the worktree
        runner_src = Path(__file__).parent / "worktree_runner.py"
        runner_dst = worktree_path / "tests" / "fixtures" / "golden_contracts" / "worktree_runner.py"
        runner_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(runner_src, runner_dst)
        print(f"Copied worktree_runner.py to worktree\n", file=sys.stderr)

        # STEP 4: Run worktree_runner.py and capture JSON
        all_golden = run_worktree_runner(worktree_path)

    finally:
        print("\nCleaning up worktree...", file=sys.stderr)
        cleanup_worktree(worktree_path)
        if worktree_path.exists():
            shutil.rmtree(worktree_path, ignore_errors=True)

    # STEP 5: Write output files to tests/fixtures/golden_0873ebf/daemon/
    GOLDEN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    success_count = 0
    failure_count = 0

    for method_name, golden in all_golden.items():
        output_file = GOLDEN_OUTPUT_DIR / f"{method_name}.json"
        with open(output_file, "w") as f:
            json.dump(golden, f, indent=2)

        if golden.get("success"):
            success_count += 1
        else:
            failure_count += 1

    # Write combined manifest
    manifest = {
        "baseline_commit": BASELINE_COMMIT,
        "total_methods": len(all_golden),
        "success_count": success_count,
        "failure_count": failure_count,
        "methods": list(all_golden.keys()),
    }
    with open(GOLDEN_OUTPUT_DIR / "_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Golden fixture generation complete")
    print(f"{'='*60}")
    print(f"Baseline commit: {BASELINE_COMMIT}")
    print(f"Total methods: {len(all_golden)}")
    print(f"  Success: {success_count}")
    print(f"  Failure: {failure_count}")
    print(f"Output directory: {GOLDEN_OUTPUT_DIR}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
```

**C.3) Golden Comparison Test**:

```python
# tests/contract_crawler/golden_comparison.py
"""Golden fixture comparison utilities."""

import json
from pathlib import Path
from typing import Any


GOLDEN_DIR = Path(__file__).parent.parent / "fixtures" / "golden_0873ebf" / "daemon"


def load_golden(method_name: str) -> dict | None:
    """
    Load golden fixture for a method.

    Returns:
        Golden fixture dict, or None if not found.
    """
    golden_file = GOLDEN_DIR / f"{method_name}.json"
    if not golden_file.exists():
        return None

    with open(golden_file) as f:
        return json.load(f)


def compare_to_golden(
    method_name: str,
    response_data: dict,
) -> tuple[bool, list[str]]:
    """
    Compare response to golden fixture.

    Args:
        method_name: RPC method name
        response_data: Actual response data

    Returns:
        Tuple of (matches, list of differences)
    """
    # Import normalization from worktree_runner (shared logic)
    from tests.fixtures.golden_contracts.worktree_runner import normalize_response

    golden = load_golden(method_name)
    if golden is None:
        return False, [f"No golden fixture for {method_name}"]

    if not golden.get("success"):
        return False, [f"Golden fixture shows failure: {golden.get('error')}"]

    golden_response = golden["response"]
    actual_normalized = normalize_response(response_data)

    differences = []
    _compare_dicts(golden_response, actual_normalized, "", differences)

    return len(differences) == 0, differences


def _compare_dicts(
    expected: dict,
    actual: dict,
    path: str,
    differences: list[str],
):
    """
    Recursively compare two dicts and collect differences.
    """
    all_keys = set(expected.keys()) | set(actual.keys())

    for key in all_keys:
        current_path = f"{path}.{key}" if path else key

        if key not in expected:
            differences.append(f"Extra key: {current_path}")
            continue

        if key not in actual:
            differences.append(f"Missing key: {current_path}")
            continue

        exp_val = expected[key]
        act_val = actual[key]

        # Skip normalized placeholders
        if isinstance(exp_val, str) and exp_val.startswith("<NORMALIZED"):
            continue

        if type(exp_val) != type(act_val):
            differences.append(f"Type mismatch at {current_path}: expected {type(exp_val).__name__}, got {type(act_val).__name__}")
            continue

        if isinstance(exp_val, dict):
            _compare_dicts(exp_val, act_val, current_path, differences)
        elif isinstance(exp_val, list):
            if len(exp_val) != len(act_val):
                differences.append(f"List length mismatch at {current_path}: expected {len(exp_val)}, got {len(act_val)}")
            else:
                for i, (e, a) in enumerate(zip(exp_val, act_val)):
                    if isinstance(e, dict):
                        _compare_dicts(e, a, f"{current_path}[{i}]", differences)
                    elif e != a and not (isinstance(e, str) and e.startswith("<NORMALIZED")):
                        differences.append(f"Value mismatch at {current_path}[{i}]: expected {e!r}, got {a!r}")
        elif exp_val != act_val:
            differences.append(f"Value mismatch at {current_path}: expected {exp_val!r}, got {act_val!r}")
```

**Golden comparison test**:

```python
# tests/contract_crawler/test_golden_contracts.py
"""
Tests comparing current responses to golden fixtures.

CRITICAL: Dispatches based on golden source:
- auto_crawler methods: replayed with stored payload
- recipe methods: run fresh recipe, compare normalized responses
"""

import pytest
from io import StringIO
from pathlib import Path

from quantumvitas.daemon.server import QVDaemon, RPCRequest
from tests.contract_crawler.golden_comparison import load_golden, compare_to_golden
from tests.contract_crawler.recipes import ALL_RECIPES


GOLDEN_DIR = Path(__file__).parent.parent / "fixtures" / "golden_0873ebf" / "daemon"


def get_golden_methods() -> list[str]:
    """Get list of methods with golden fixtures."""
    if not GOLDEN_DIR.exists():
        return []
    return [
        f.stem for f in GOLDEN_DIR.glob("*.json")
        if f.stem not in ("_manifest",)  # Skip manifest file
    ]


# Build recipe lookup by method_name
RECIPE_BY_METHOD = {r.method_name: r for r in ALL_RECIPES}


@pytest.fixture
def daemon():
    return QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())


class TestGoldenContracts:
    """Test current responses match golden fixtures."""

    @pytest.mark.parametrize("method_name", get_golden_methods())
    def test_matches_golden(self, daemon, method_name: str, tmp_path: Path):
        """
        Current response matches golden fixture.

        Dispatches based on source:
        - auto_crawler: replay with stored payload
        - recipe: run current recipe, compare normalized
        """
        golden = load_golden(method_name)
        assert golden is not None, f"Missing golden for {method_name}"

        if not golden.get("success"):
            pytest.skip(f"Golden shows expected failure for {method_name}")

        source = golden.get("source")
        assert source in ("auto_crawler", "recipe"), f"Unknown source: {source}"

        # Dispatch based on source
        if source == "auto_crawler":
            # Auto-crawler method: replay with stored payload
            payload = golden.get("payload", {})

            response = daemon.handle_request(RPCRequest(
                id=f"golden-test-{method_name}",
                type=method_name,
                payload=payload,
            ))

            assert response.ok, f"Request failed: {response.error}"

            matches, differences = compare_to_golden(method_name, response.data)

            assert matches, f"Contract drift detected:\n" + "\n".join(differences)

        elif source == "recipe":
            # Recipe method: run current recipe, compare normalized responses
            recipe_name = golden.get("recipe_name")
            assert recipe_name, f"Golden missing recipe_name for {method_name}"

            recipe_cls = RECIPE_BY_METHOD.get(method_name)
            assert recipe_cls is not None, (
                f"Recipe for {method_name} not found in current ALL_RECIPES. "
                f"Golden expects recipe: {recipe_name}"
            )

            # Run recipe to get current response
            recipe_dir = tmp_path / recipe_name
            recipe_dir.mkdir(exist_ok=True)

            recipe = recipe_cls(recipe_dir)
            result = recipe.execute()

            assert result.success, f"Recipe failed: {result.error}"

            # Compare normalized responses
            matches, differences = compare_to_golden(method_name, result.response_data)

            assert matches, f"Contract drift detected:\n" + "\n".join(differences)

    def test_all_golden_methods_have_metadata(self):
        """All golden fixtures have required metadata fields."""
        methods = get_golden_methods()
        missing_metadata = []

        for method_name in methods:
            golden = load_golden(method_name)

            # Check required metadata
            required = ["method", "success", "baseline_commit", "source", "generated_at"]
            for field in required:
                if field not in golden:
                    missing_metadata.append(f"{method_name}: missing '{field}'")

            # Check source-specific metadata
            if golden.get("success"):
                source = golden.get("source")
                if source == "auto_crawler" and "payload" not in golden:
                    missing_metadata.append(f"{method_name}: auto_crawler missing 'payload'")
                elif source == "recipe" and "recipe_name" not in golden:
                    missing_metadata.append(f"{method_name}: recipe missing 'recipe_name'")

            # Check baseline_commit value
            if golden.get("baseline_commit") != "0873ebf":
                missing_metadata.append(
                    f"{method_name}: baseline_commit is '{golden.get('baseline_commit')}', expected '0873ebf'"
                )

        assert not missing_metadata, (
            f"Golden fixtures missing required metadata:\n" +
            "\n".join(f"  - {m}" for m in missing_metadata)
        )
```

**README for golden_0873ebf directory**:

```markdown
# Golden Contract Fixtures from 0873ebf

These fixtures capture the daemon RPC response shapes from commit `0873ebf` (pre-DTO baseline).

## Coverage

Golden fixtures cover ALL methods that the auto-crawler and recipes successfully call at baseline:
- Auto-crawl methods: stateless methods with minimal payloads
- Recipe methods: complex methods requiring setup (calculations, steps, structures)

This ensures maximal contract coverage and drift detection.

## Generation

Golden fixtures were generated using git worktree + worktree_runner.py with guaranteed baseline isolation:

```bash
cd tests/fixtures/golden_contracts
python generate_golden.py
```

Process:
1. Creates git worktree at commit 0873ebf
2. **Copies contract_crawler package into worktree** (0873ebf won't have it)
   - Copies: introspection.py, payloads.py, crawler.py, recipes/
3. Copies worktree_runner.py into worktree
4. Runs worktree_runner.py with **isolated PYTHONPATH** (worktree-only)
   - PYTHONPATH=worktree/src:worktree/tests
   - Prevents editable install leakage
5. **Runtime assertions verify baseline isolation**:
   - git HEAD == 0873ebf
   - quantumvitas module loaded from worktree path
6. Runs crawler + ALL_RECIPES from 0873ebf baseline code
7. Captures JSON output and writes to golden_0873ebf/daemon/*.json
8. Cleans up worktree

**CRITICAL**: The runtime assertions in step 5 MUST appear in console output.
If missing, baseline isolation failed and golden fixtures are INVALID.

Do NOT regenerate unless updating the baseline. Document reason if doing so.

## Normalization

Non-deterministic fields are normalized using **key-based replacement** (no content heuristics):
- ULIDs: `<NORMALIZED_ID>` (for keys: id, structure_id, calc_id, step_id, run_id, job_id, etc.)
- Timestamps: `<NORMALIZED_TIMESTAMP>` (for keys: created_at, updated_at, started_at, completed_at, timestamp)
- Temp paths: `<NORMALIZED_PATH>` (for keys: project_root, log_path, io_dir)

Deterministic fields (sha256, relative paths, filenames) are NOT normalized and must match exactly.

## Baseline Commit

All fixtures were generated from: `0873ebf`

Each fixture JSON contains:
- `"baseline_commit": "0873ebf"` - proves baseline origin
- `"source": "auto_crawler"` or `"recipe"` - identifies generation method
- `"payload": {...}` (auto_crawler only) - for deterministic replay
- `"recipe_name": "..."` (recipe only) - for current recipe lookup

## Manifest

See `_manifest.json` for summary:
- `baseline_commit`: "0873ebf"
- `total_methods`: count of methods with golden
- `success_count`: methods that succeeded at baseline
- `failure_count`: methods that failed at baseline (marked success:false)
- `methods`: list of all method names

## Comparison Logic

**Auto-crawler methods**: Current daemon called with stored `payload`, response compared to golden

**Recipe methods**: Current recipe executed fresh (IDs non-replayable), normalized response compared to golden normalized baseline
```

**Acceptance Criteria**:
```bash
# Generate golden fixtures FROM 0873ebf via worktree (run once to establish baseline)
cd tests/fixtures/golden_contracts
python generate_golden.py

# Expected console output (critical assertions):
#   Worktree created at: /tmp/qv_golden_0873ebf_XXXXXX
#   Copying contract_crawler package into worktree...
#     Copied introspection.py to worktree
#     Copied payloads.py to worktree
#     Copied crawler.py to worktree
#     Copied recipes/ to worktree
#   Copied worktree_runner.py to worktree
#   Running worktree_runner.py from ...
#   [VERIFIED] git HEAD: 0873ebf...   <-- CRITICAL: Proves baseline isolation
#   [VERIFIED] quantumvitas from: /tmp/.../worktree/src/...   <-- CRITICAL: Proves no editable leak
#   Running auto-crawler from 0873ebf...
#   [auto] ping: OK
#   [auto] get_env_info: OK
#   ...
#   Running N recipes from 0873ebf...
#   [recipe] get_step_detail (GetStepDetailRecipe): OK
#   ...
#   Cleaning up worktree...
#   ============================================================
#   Golden fixture generation complete
#   ============================================================
#   Baseline commit: 0873ebf
#   Total methods: 50+
#     Success: 45+
#     Failure: <5 (network-dependent methods expected to fail)
#   Output directory: .../tests/fixtures/golden_0873ebf/daemon
#   ============================================================

# Verify runtime assertions appeared in output
grep "\[VERIFIED\] git HEAD: 0873ebf" <output>
grep "\[VERIFIED\] quantumvitas from:" <output>
# Both must be present to confirm baseline isolation

# Verify output structure
ls tests/fixtures/golden_0873ebf/daemon/
# Expected: _manifest.json, ping.json, get_env_info.json, get_step_detail.json, ...

# Verify metadata in golden fixtures
cat tests/fixtures/golden_0873ebf/daemon/ping.json
# Expected fields:
#   "method": "ping"
#   "success": true
#   "baseline_commit": "0873ebf"
#   "source": "auto_crawler"
#   "payload": {}
#   "response": {...normalized...}
#   "generated_at": "2026-..."

cat tests/fixtures/golden_0873ebf/daemon/get_step_detail.json
# Expected fields (recipe method):
#   "method": "get_step_detail"
#   "success": true
#   "baseline_commit": "0873ebf"
#   "source": "recipe"
#   "recipe_name": "GetStepDetailRecipe"
#   "response": {...normalized...}

# Verify manifest
cat tests/fixtures/golden_0873ebf/daemon/_manifest.json
# Expected:
#   "baseline_commit": "0873ebf"
#   "total_methods": 50+
#   "success_count": 45+
#   "failure_count": <5
#   "methods": ["ping", "get_env_info", ...]

# Run golden comparison tests
python -m pytest tests/contract_crawler/test_golden_contracts.py -v --tb=short
# Expected:
#   test_matches_golden[ping] PASSED
#   test_matches_golden[get_env_info] PASSED
#   test_matches_golden[get_step_detail] PASSED (uses recipe dispatch)
#   ...
#   test_all_golden_methods_have_metadata PASSED

# Run full test suite
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
# All tests pass, including golden comparison
```

---

### Phase 4: Harden Serialization Guards

**Goal**: Ensure DTO leakage fails fast; align with existing gates.

**Files to modify**:
- `tests/gates/test_daemon_no_hand_serialization.py` (enhance)
- `src/quantumvitas/api/types/base.py` (add runtime guards if needed)

**New guards**:

```python
# Add to tests/gates/test_daemon_no_hand_serialization.py

def test_all_handler_responses_json_serializable():
    """
    Every handler response must be JSON-serializable.

    This is a runtime guard complementing the static AST checks.
    """
    import json
    from io import StringIO
    from tests.contract_crawler.crawler import crawl_all_methods

    report = crawl_all_methods()

    failures = report.not_json_serializable
    if failures:
        failure_details = "\n".join([
            f"  - {r.method_name}: {r.serialization_error}"
            for r in failures
        ])
        pytest.fail(f"Handlers returning non-JSON-serializable data:\n{failure_details}")


def test_no_dto_leakage_in_responses():
    """
    Handler responses must not contain DTO instances (must use to_dict()).
    """
    from io import StringIO
    from tests.contract_crawler.crawler import crawl_all_methods
    from quantumvitas.api.types.base import BaseDTO

    def check_for_dto_leakage(obj, path=""):
        """Recursively check for DTO instances."""
        if isinstance(obj, BaseDTO):
            return [f"{path}: Found raw DTO {type(obj).__name__}"]

        leaks = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                leaks.extend(check_for_dto_leakage(v, f"{path}.{k}"))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                leaks.extend(check_for_dto_leakage(v, f"{path}[{i}]"))

        return leaks

    report = crawl_all_methods()

    all_leaks = []
    for result in report.covered:
        if result.response_data:
            leaks = check_for_dto_leakage(result.response_data, result.method_name)
            all_leaks.extend(leaks)

    assert not all_leaks, f"DTO leakage detected:\n" + "\n".join(all_leaks)
```

**Acceptance Criteria**:
```bash
python -m pytest tests/gates/test_daemon_no_hand_serialization.py -v --tb=short
# All tests pass, including new runtime guards
```

---

## D) Method Coverage Policy

### D.1) Public/User-Facing RPC Methods

**Definition**: All methods in `QVDaemon._handlers` are considered public.

**Exclusions**: None by default. All methods must be covered or explicitly exempt.

### D.2) EXEMPT List (Structured with Reasons)

**Type**: `dict[str, str]` mapping method name to exemption reason.

**Enforcement**:
- Every exempt method MUST have a non-empty reason string
- Every exempt method MUST exist in the daemon handler registry
- Total exempt count capped at 15 to prevent exemption creep

**Example**:
```python
EXEMPT_METHODS: dict[str, str] = {
    "shutdown": "Terminates daemon process; tested manually",
    "compile_fixture_volume": "Dev-only endpoint requiring specific fixture files",
    "download_sssp_library": "Network-dependent; tested in integration suite",
    "download_all_sssp": "Network-dependent; tested in integration suite",
    "structure_search_online": "Network-dependent; tested in integration suite",
    "structure_get_online_candidate": "Network-dependent; tested in integration suite",
    "structure_import_online_candidate": "Network-dependent; tested in integration suite",
    "search_legacy_pseudos": "Network-dependent; tested in integration suite",
    "download_pseudo_by_filename": "Network-dependent; tested in integration suite",
    "download_pseudo_candidate": "Network-dependent; tested in integration suite",
}
```

### D.3) Coverage Enforcement (Based on Actual Crawl Success)

**IMPORTANT**: Coverage is verified by actually running the crawler and checking which
methods succeeded, NOT by set subtraction of "methods that should work". This ensures
we detect real failures rather than assuming coverage.

```python
# tests/contract_crawler/test_coverage.py
"""Enforce method coverage policy based on actual crawl success."""

import pytest

from tests.contract_crawler.introspection import get_all_rpc_methods
from tests.contract_crawler.crawler import crawl_all_methods, CrawlReport
from tests.contract_crawler.recipes import ALL_RECIPES


# Exempt methods with mandatory reasons
EXEMPT_METHODS: dict[str, str] = {
    "shutdown": "Terminates daemon process; tested manually",
    "compile_fixture_volume": "Dev-only endpoint requiring specific fixture files",
    "download_sssp_library": "Network-dependent; tested in integration suite",
    "download_all_sssp": "Network-dependent; tested in integration suite",
    "structure_search_online": "Network-dependent; tested in integration suite",
    "structure_get_online_candidate": "Network-dependent; tested in integration suite",
    "structure_import_online_candidate": "Network-dependent; tested in integration suite",
    "search_legacy_pseudos": "Network-dependent; tested in integration suite",
    "download_pseudo_by_filename": "Network-dependent; tested in integration suite",
    "download_pseudo_candidate": "Network-dependent; tested in integration suite",
}


def test_exempt_methods_are_valid():
    """
    Verify EXEMPT_METHODS structure and integrity.

    Requirements:
    - Every exempt method must exist in daemon handler registry
    - Every exempt method must have a non-empty reason string
    - Total exempt count capped at 15 to prevent exemption creep
    """
    all_methods = {m.name for m in get_all_rpc_methods()}

    # Check all exempt methods exist
    unknown_exempt = set(EXEMPT_METHODS.keys()) - all_methods
    assert not unknown_exempt, f"EXEMPT contains unknown methods: {unknown_exempt}"

    # Check all reasons are non-empty
    empty_reasons = [m for m, reason in EXEMPT_METHODS.items() if not reason or not reason.strip()]
    assert not empty_reasons, f"EXEMPT methods with empty reasons: {empty_reasons}"

    # Check exemption count cap
    assert len(EXEMPT_METHODS) <= 15, (
        f"EXEMPT list has {len(EXEMPT_METHODS)} entries (max 15). "
        f"Review exemptions to prevent coverage erosion."
    )

    print(f"\nExempt methods validated: {len(EXEMPT_METHODS)} methods with reasons")


def test_auto_crawl_methods_actually_succeed():
    """
    Verify that methods we expect to auto-crawl ACTUALLY succeed when crawled.

    This test runs the actual crawler and checks success, rather than
    using set subtraction to assume coverage.
    """
    report = crawl_all_methods()

    # Methods that failed (not just marked as needing recipes)
    actual_failures = [
        r for r in report.results
        if not r.success and not r.needs_recipe and r.method_name not in EXEMPT_METHODS
    ]

    if actual_failures:
        failure_details = "\n".join([
            f"  - {r.method_name}: {r.error or r.skipped_reason}"
            for r in actual_failures
        ])
        pytest.fail(
            f"Methods expected to auto-crawl but ACTUALLY FAILED:\n{failure_details}\n\n"
            f"Fix the method or add it to needs_recipes() if it requires setup."
        )

    # Report coverage stats
    covered_count = len(report.covered)
    total_count = report.total
    print(f"\nAuto-crawl coverage: {covered_count}/{total_count} methods succeeded")


def test_recipes_actually_succeed(tmp_path):
    """
    Verify that recipe-covered methods ACTUALLY succeed when executed.

    This test runs each recipe and checks success, rather than
    just checking if a recipe exists for the method.
    """
    failures = []

    for recipe_cls in ALL_RECIPES:
        recipe_dir = tmp_path / recipe_cls.__name__
        recipe_dir.mkdir(exist_ok=True)

        recipe = recipe_cls(recipe_dir)
        result = recipe.execute()

        if not result.success:
            failures.append(f"{recipe_cls.__name__} ({recipe.method_name}): {result.error}")

    if failures:
        pytest.fail(
            f"Recipes that ACTUALLY FAILED:\n" +
            "\n".join(f"  - {f}" for f in failures) +
            "\n\nFix the recipe or the underlying handler."
        )

    print(f"\nRecipe coverage: {len(ALL_RECIPES)} methods succeeded via recipes")


def test_all_methods_covered_or_exempt():
    """
    Every public RPC method must be:
    1. ACTUALLY covered by auto-crawler (verified by success), OR
    2. ACTUALLY covered by a recipe (verified by success), OR
    3. Explicitly exempt with documented reason

    This is the final gate - it combines auto-crawl and recipe results.
    """
    # Get all registered methods
    all_methods = {m.name for m in get_all_rpc_methods()}

    # Run actual crawler to get real successes
    report = crawl_all_methods()
    auto_crawl_succeeded = {r.method_name for r in report.covered}

    # Get recipe-covered methods
    recipe_covered = {r.method_name for r in ALL_RECIPES}

    # Calculate actual coverage
    exempt_methods_set = set(EXEMPT_METHODS.keys())
    actually_covered = auto_crawl_succeeded | recipe_covered | exempt_methods_set
    uncovered = all_methods - actually_covered

    # Check all methods are covered
    if uncovered:
        pytest.fail(
            f"Methods with NO ACTUAL COVERAGE:\n" +
            "\n".join(f"  - {m}" for m in sorted(uncovered)) +
            "\n\nEach method must either:\n"
            "  1. Succeed in auto-crawl (add minimal payload to payloads.py)\n"
            "  2. Have a working recipe (add to recipes/)\n"
            "  3. Be explicitly exempt (add to EXEMPT_METHODS with reason)"
        )

    # Print coverage summary
    print(f"\nCoverage summary:")
    print(f"  Auto-crawl succeeded: {len(auto_crawl_succeeded)}")
    print(f"  Recipe covered: {len(recipe_covered)}")
    print(f"  Exempt: {len(EXEMPT_METHODS)}")
    print(f"  Total methods: {len(all_methods)}")
    print(f"  Coverage: {len(actually_covered)}/{len(all_methods)} ({len(actually_covered)*100//len(all_methods)}%)")
```

---

## E) Issues/Risks Found

### E.1) Current Gaps Identified

| Issue | Severity | Location | Suggested Fix |
|-------|----------|----------|---------------|
| Placeholder tests in `test_daemon_payload_contracts.py` | High | `tests/daemon/` | Replace with actual tests using recipes |
| No golden fixtures exist | High | `tests/fixtures/` | Generate baseline with Phase 3 |
| `detect_workflow` registered twice in handlers | Low | `server.py:357,411` | Remove duplicate |
| Many handlers lack complete docstrings | Medium | `server.py` | Add payload documentation |
| No integration tests for job lifecycle | High | `tests/daemon/` | Add recipe for run→poll→complete flow |
| Status mapping inconsistency (SUCCESS vs completed) | Medium | Multiple | Standardize on legacy mapping |

### E.2) Architecture Risks

1. **DTO drift risk**: DTOs may add fields without updating golden fixtures
   - **Mitigation**: Golden comparison tests will catch this

2. **Serialization regression risk**: Hand-serialization may creep back
   - **Mitigation**: AST gate + runtime guards

3. **Coverage blind spot**: Recipe-required methods may be skipped
   - **Mitigation**: Coverage enforcement test

---

## Final Checklist

### PR1: Phase 0 - Introspection
- [ ] Create `tests/contract_crawler/__init__.py`
- [ ] Create `tests/contract_crawler/introspection.py`
- [ ] Create `tests/contract_crawler/test_introspection.py`
- [ ] Run: `python -m pytest tests/contract_crawler/test_introspection.py -v --tb=short`
- [ ] Verify: 109+ methods enumerated
- [ ] Merge when green

### PR2: Phase 1 - Auto-Crawler
- [ ] Create `tests/contract_crawler/payloads.py`
- [ ] Create `tests/contract_crawler/crawler.py`
- [ ] Create `tests/contract_crawler/test_auto_crawl.py`
- [ ] Run: `python -m pytest tests/contract_crawler/ -v --tb=short -n auto --dist=loadfile`
- [ ] Verify: 20+ stateless methods covered, 0 serialization failures
- [ ] Merge when green

### PR3: Phase 2 - Recipes
- [ ] Create `tests/contract_crawler/recipes/` directory structure
- [ ] Create recipe for `get_step_detail`
- [ ] Create recipe for `get_calculation_detail`
- [ ] Create recipe for `run_step` + `get_job_status` flow
- [ ] Create `tests/contract_crawler/test_recipes.py`
- [ ] Run: `python -m pytest tests/contract_crawler/test_recipes.py -v --tb=short`
- [ ] Verify: Key flows covered
- [ ] Merge when green

### PR4: Phase 3 - Golden Comparison (from 0873ebf via Worktree)

**Files to create**:
- [ ] `tests/fixtures/golden_contracts/` directory
- [ ] `tests/fixtures/golden_contracts/worktree_runner.py`
  - [ ] Runtime assertions: verify_baseline_isolation()
    - [ ] Assert git HEAD == 0873ebf
    - [ ] Assert quantumvitas.__file__ under worktree path
  - [ ] Key-based normalization (no content heuristics)
  - [ ] Imports crawler and recipes from copied modules
  - [ ] Runs crawl_all_methods() and ALL_RECIPES
  - [ ] Stores payload for auto_crawler methods, recipe_name for recipe methods
  - [ ] Outputs JSON to stdout with normalized responses
- [ ] `tests/fixtures/golden_contracts/generate_golden.py`
  - [ ] Creates git worktree at 0873ebf
  - [ ] Copies contract_crawler package into worktree (0873ebf won't have it)
    - [ ] Copy introspection.py, payloads.py, crawler.py, recipes/
  - [ ] Copies worktree_runner.py into worktree
  - [ ] Runs `python worktree_runner.py` with isolated PYTHONPATH
    - [ ] PYTHONPATH=worktree/src:worktree/tests
  - [ ] Captures JSON stdout and writes to golden_0873ebf/daemon/*.json
  - [ ] Cleans up worktree
- [ ] `tests/fixtures/golden_0873ebf/README.md` documenting baseline and process
- [ ] `tests/contract_crawler/golden_comparison.py`
  - [ ] load_golden() points to golden_0873ebf/daemon/
  - [ ] Uses normalize_response from worktree_runner.py
  - [ ] compare_to_golden() compares normalized responses
- [ ] `tests/contract_crawler/test_golden_contracts.py`
  - [ ] Parametrized test over all golden methods
  - [ ] Dispatches based on source:
    - [ ] auto_crawler: replay with stored payload
    - [ ] recipe: run current recipe, compare normalized
  - [ ] test_all_golden_methods_have_metadata: validates metadata

**Generation step** (ONE-TIME):
- [ ] Run: `cd tests/fixtures/golden_contracts && python generate_golden.py`
- [ ] **CRITICAL**: Verify runtime assertions in console output:
  - [ ] `[VERIFIED] git HEAD: 0873ebf...` appears
  - [ ] `[VERIFIED] quantumvitas from: /tmp/.../worktree/src/...` appears
  - [ ] If either missing, baseline isolation FAILED - abort and investigate
- [ ] Verify output:
  - [ ] Console shows "Copying contract_crawler package into worktree..."
  - [ ] Console shows "Running auto-crawler from 0873ebf..."
  - [ ] Console shows "Running N recipes from 0873ebf..."
  - [ ] Console shows success/failure for each method
  - [ ] `tests/fixtures/golden_0873ebf/daemon/_manifest.json` exists
  - [ ] `tests/fixtures/golden_0873ebf/daemon/*.json` files exist (50+ methods)
- [ ] Verify metadata in golden fixtures:
  - [ ] Each .json file contains `"baseline_commit": "0873ebf"`
  - [ ] Each .json file contains `"source": "auto_crawler"` or `"recipe"`
  - [ ] auto_crawler methods have `"payload": {...}`
  - [ ] recipe methods have `"recipe_name": "..."`

**Test step**:
- [ ] Run: `python -m pytest tests/contract_crawler/test_golden_contracts.py::test_all_golden_methods_have_metadata -v`
  - [ ] PASS: All golden fixtures have required metadata
- [ ] Run: `python -m pytest tests/contract_crawler/test_golden_contracts.py::test_matches_golden -v --tb=short`
  - [ ] PASS: All methods (auto_crawler + recipe) match baseline
  - [ ] Verify both dispatch paths work (auto replay, recipe execution)
- [ ] Run full suite: `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
  - [ ] All tests pass
- [ ] Merge when green

### PR5: Phase 4 - Guards + Coverage (Actual Crawl Verification)
**Files to create/modify**:
- [ ] Add runtime serialization guards to `tests/gates/test_daemon_no_hand_serialization.py`
  - [ ] `test_all_handler_responses_json_serializable` - runtime guard
  - [ ] `test_no_dto_leakage_in_responses` - recursive DTO check
- [ ] Create `tests/contract_crawler/test_coverage.py` with actual crawl verification
  - [ ] Define `EXEMPT_METHODS: dict[str, str]` with method -> reason mapping
  - [ ] `test_exempt_methods_are_valid` - validates structure, reasons, count cap
  - [ ] `test_auto_crawl_methods_actually_succeed` - runs crawler, checks real success
  - [ ] `test_recipes_actually_succeed` - runs recipes, checks real success
  - [ ] `test_all_methods_covered_or_exempt` - combines results, uses actual success

**Validation**:
- [ ] Verify EXEMPT_METHODS has non-empty reasons for all entries
- [ ] Verify EXEMPT_METHODS count <= 15
- [ ] Run: `python -m pytest tests/contract_crawler/test_coverage.py -v --tb=short`
  - [ ] test_exempt_methods_are_valid: PASS
  - [ ] test_auto_crawl_methods_actually_succeed: PASS (20+ methods)
  - [ ] test_recipes_actually_succeed: PASS (N recipes)
  - [ ] test_all_methods_covered_or_exempt: PASS (100% coverage or explicit exemptions)
- [ ] Run full suite: `python -m pytest tests/gates/ tests/contract_crawler/ -v --tb=short -n auto --dist=loadfile`
- [ ] Verify: Coverage based on ACTUAL SUCCESS, not assumed coverage
- [ ] Merge when green

---

## Appendix: Full Method Registry (109 methods)

```
ping, shutdown, detect_qe, get_env_info, list_qe_engines, discover_qe_engines,
set_qe_engine, set_log_level, set_debug_resolution, get_debug_resolution,
list_qe_ui_parameters, list_qe_parameter_metadata, reload_qe_parameter_metadata,
get_qe_parameter_metadata_debug_info, get_pseudo_config, set_pseudo_config,
validate_pseudo_config, init_pseudo_dirs, install_seed_to_store, list_installed_sssp,
list_seed_archives, download_sssp_library, download_all_sssp,
resolve_project_pseudo_provenance, import_seed_archives, list_pseudo_archives_status,
install_pseudo_archive, analyze_project_pseudo_effects, list_libraries,
get_library_status, install_library, remove_library, repair_library,
compute_store_size, get_project_summary, list_structures, list_calculations,
find_project_root, rebuild_project_registry, create_project, import_structure,
structure_search_online, structure_get_online_candidate, structure_import_online_candidate,
rename_structure, delete_structure, can_delete_structure, list_calculation_templates,
create_calculation, rename_calculation, delete_calculation, can_delete_calculation,
get_step_detail, update_step_params, reset_step_params, get_common_cards,
promote_relax_structure, set_common_card, get_pseudo_mapping, set_pseudo_mapping,
import_pseudo_files, search_legacy_pseudos, download_pseudo_by_filename,
download_pseudo_candidate, get_relax_final_structure_preview, save_relax_final_structure,
get_calculation_detail, reorder_calculation_steps, add_step_to_calculation,
import_step_from_qe_input, change_calculation_structure, get_calculation_pseudo_mapping,
update_calculation_species_map, get_pseudo_options_for_calculation,
materialize_pseudo_file, delete_step, get_preset_catalog, detect_presets,
detect_workflow, apply_presets_to_step, apply_presets_to_calculation,
get_step_preset_footprints, preflight_check, create_demo_project, list_demo_projects,
ensure_calculation_analysis, get_structure_vis, get_scf_convergence, get_dos_data,
get_band_structure_data, get_reference_analysis, list_step_artifacts,
read_step_artifact_text, list_wannier_3d_fixtures, compile_fixture_volume,
run_calculation, run_step, run_single_step, get_job_status, get_job_logs,
list_jobs, job_counts, cancel_job, list_journal_entries, get_journal_entry,
get_project_history, get_run_revision, list_project_runs, pin_analysis_to_history,
can_pin_to_run, get_pin_data, get_latest_run_for_step, delete_project_history,
list_workflow_templates, detect_workflow_for_calculation, instantiate_workflow
```
