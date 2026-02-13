# M4: Generic Backend RPCs

## Scope

Add 5 new engine-agnostic RPC handlers to the daemon. These replace the QE-specific RPCs but do NOT delete them yet (deletion is M8). The new RPCs dispatch through DriverRegistry.

## Prerequisites

M0 (driver protocol), M1 (demos), M2 (no QE fallbacks), and M3 (companion routing) must be complete.

## Exact File List

### Modify

1. `src/quantumvitas/daemon/server.py` — Add 5 new RPC handlers + register them in `_handlers` dict
2. `src/quantumvitas/api/service.py` — Add service methods to support new RPCs (if needed)
3. `src/quantumvitas/core/driver_protocol.py` — Add `get_managed_keys()` to BaseEngineDriver (optional, for `list_engine_ui_parameters`)

### Create

4. `tests/daemon/test_generic_rpcs.py` — Tests for new RPC handlers

## Do NOT Touch

- `src/quantumvitas/drivers/` (driver code, already done in M0)
- GUI files (that's M5-M7)
- Existing QE RPC handlers in server.py (do NOT delete them — that's M8)
- `src/quantumvitas/api/utils.py` (QE metadata utilities — still used by deprecated RPCs)

## Exact Instructions

### Step 1: Add new RPC registrations in server.py

In the `_handlers` dict (around line 242-370), add these 5 new entries in a new section:

```python
            # ─────────────────────────────────────────────────────────────
            # Generic engine RPCs (engine-agnostic, replaces QE-specific)
            # ─────────────────────────────────────────────────────────────
            "list_engine_families": self._handle_list_engine_families,
            "list_step_palette": self._handle_list_step_palette,
            "list_engine_ui_parameters": self._handle_list_engine_ui_parameters,
            "list_engine_parameter_metadata": self._handle_list_engine_parameter_metadata,
            "set_engine_family": self._handle_set_engine_family,
```

Place this block AFTER the existing QE RPCs (around line 260) so the existing QE RPCs still work.

### Step 2: Implement `_handle_list_engine_families`

Add this handler method to the server class:

```python
def _handle_list_engine_families(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    List all registered engine families with classification.

    Payload: (none required)

    Returns:
        {"engines": [{engine_family, display_name, engine_role, companion_engines, supported_gen_steps}]}
    """
    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers

    engines = []
    for family in sorted(DriverRegistry.get_all_engines()):
        driver = DriverRegistry.get_driver(family)
        engines.append({
            "engine_family": family,
            "display_name": driver.display_name,
            "engine_role": getattr(driver, 'ENGINE_ROLE', 'base'),
            "companion_engines": sorted(getattr(driver, 'COMPANION_ENGINES', frozenset())),
            "supported_gen_steps": sorted(getattr(driver, 'SUPPORTED_GEN_STEPS', set())),
        })

    return {"engines": engines}
```

### Step 3: Implement `_handle_list_step_palette`

```python
def _handle_list_step_palette(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get step palette for a given engine_family (or UNDECIDED).

    Payload:
        engine_family: str | null — If null, returns only postprocessing steps.

    Returns:
        {
            "base_steps": [{"gen": "scf", "spec": "qe_scf", "description": "..."}],
            "companion_steps": {"w90": [{"gen": "wannierprep", "spec": "w90_wannierprep", ...}]},
        }
        If engine_family is null:
        {
            "base_steps": [],
            "companion_steps": {},
        }
    """
    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers

    engine_family = payload.get("engine_family")

    if engine_family is None:
        # UNDECIDED state: no base steps, no companions
        return {"base_steps": [], "companion_steps": {}}

    driver = DriverRegistry.get_driver(engine_family)
    supported = getattr(driver, 'SUPPORTED_GEN_STEPS', set())

    # Base steps
    base_steps = []
    for gen in sorted(supported):
        try:
            spec = DriverRegistry.materialize_step_type(engine_family, gen)
            # Try to get description from StepTypeSpec
            try:
                spec_obj = DriverRegistry.get_step_type_spec(spec)
                desc = spec_obj.description
            except Exception:
                desc = gen
            base_steps.append({"gen": gen, "spec": spec, "description": desc})
        except Exception:
            continue

    # Companion steps
    companions = getattr(driver, 'COMPANION_ENGINES', frozenset())
    companion_steps = {}
    for comp in sorted(companions):
        try:
            comp_driver = DriverRegistry.get_driver(comp)
            comp_supported = getattr(comp_driver, 'SUPPORTED_GEN_STEPS', set())
            comp_list = []
            for gen in sorted(comp_supported):
                try:
                    spec = DriverRegistry.materialize_step_type(comp, gen)
                    try:
                        spec_obj = DriverRegistry.get_step_type_spec(spec)
                        desc = spec_obj.description
                    except Exception:
                        desc = gen
                    comp_list.append({"gen": gen, "spec": spec, "description": desc})
                except Exception:
                    continue
            if comp_list:
                companion_steps[comp] = comp_list
        except Exception:
            continue

    return {"base_steps": base_steps, "companion_steps": companion_steps}
```

### Step 4: Implement `_handle_list_engine_ui_parameters`

```python
def _handle_list_engine_ui_parameters(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get UI parameter metadata for any engine + step type.

    This is the generic replacement for list_qe_ui_parameters.
    For QE, it delegates to the existing QE metadata infrastructure.
    For other engines, it returns metadata from the engine's data module (if available).

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

    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers

    driver = DriverRegistry.get_driver(engine_family)

    # Strategy: Check if engine has metadata module, otherwise return empty
    # QE uses the existing metadata infrastructure
    if engine_family == "qe":
        # Delegate to existing QE metadata (stepTypeToModule mapping lives in GUI)
        # Return the raw QE UI parameters
        from quantumvitas.api.utils import get_ui_parameters, list_supported_modules
        # Determine QE module from step_type_gen
        module_map = {
            "scf": "pw", "nscf": "pw", "relax": "pw",
            "bands_pw": "pw", "bandspw": "pw", "dos": "pw", "md": "pw",
            "bands": "bands", "ph": "ph", "projwfc": "projwfc", "pp": "pp",
        }
        module = module_map.get(step_type_gen)
        if module and module in list_supported_modules():
            ui_params = get_ui_parameters(module, step_type_gen)
            result = []
            for param in ui_params:
                param_dict = {
                    "key": param.name,
                    "label": param.label,
                    "type": param.type,
                    "section": param.namelist,
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

    # For engines with metadata modules (VASP, ORCA, etc.)
    # Try to load from driver's data module
    try:
        metadata_module = None
        if engine_family == "vasp":
            from quantumvitas.drivers.vasp.data import vasp_metadata as metadata_module
        elif engine_family == "orca":
            from quantumvitas.drivers.orca.data import orca_metadata as metadata_module
        elif engine_family == "lammps":
            from quantumvitas.drivers.lammps.data import lammps_metadata as metadata_module
        elif engine_family == "gaussian":
            from quantumvitas.drivers.gaussian.data import gaussian_metadata as metadata_module
        elif engine_family == "abinit":
            from quantumvitas.drivers.abinit.data import abinit_metadata as metadata_module
        elif engine_family == "cp2k":
            from quantumvitas.drivers.cp2k.data import cp2k_metadata as metadata_module
        elif engine_family == "qmcpack":
            from quantumvitas.drivers.qmcpack.data import qmcpack_metadata as metadata_module

        if metadata_module and hasattr(metadata_module, 'list_tags'):
            tags = metadata_module.list_tags()
            result = []
            for tag_name in sorted(tags):
                info = metadata_module.get_tag_info(tag_name)
                if info:
                    result.append({
                        "key": tag_name,
                        "label": tag_name,
                        "type": info.get("type", "string"),
                        "default": info.get("default"),
                        "description": info.get("description", ""),
                        "section": info.get("category", "general"),
                    })
            return {"parameters": result}
    except (ImportError, AttributeError):
        pass

    # Fallback: no metadata available
    return {"parameters": []}
```

**IMPORTANT**: The engine-specific imports inside this handler are acceptable because this is daemon/server.py (above kernel). The imports are lazy and only triggered by the specific engine_family requested. This does NOT violate the "no engine imports in runner/executor" rule — that rule applies to runner/executor, not daemon handlers.

### Step 5: Implement `_handle_list_engine_parameter_metadata`

```python
def _handle_list_engine_parameter_metadata(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Browse parameter metadata for any engine.

    Generic replacement for list_qe_parameter_metadata.

    Payload:
        engine_family: str (required)
        operation: str (required) — "list_categories", "list_tags", "search"

        For "list_categories": no additional fields
        For "list_tags": requires "category": str
        For "search": requires "query": str

    Returns:
        Varies by operation (same shape across engines).
    """
    engine_family = payload.get("engine_family", "").strip().lower()
    operation = payload.get("operation", "").strip().lower()

    if not engine_family:
        raise ValueError("'engine_family' is required in payload")
    if not operation:
        raise ValueError("'operation' is required. Must be: list_categories, list_tags, search")

    self.log(f"[RPC] list_engine_parameter_metadata (engine: {engine_family}, op: {operation})")

    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers

    # For QE, delegate to existing metadata infrastructure
    if engine_family == "qe":
        # Translate operation names and delegate to existing handler
        qe_payload = dict(payload)
        if operation == "list_categories":
            qe_payload["operation"] = "list_modules"
        elif operation == "list_tags":
            qe_payload["operation"] = "list_parameters"
            qe_payload["module"] = payload.get("category", "pw")
            qe_payload["section"] = payload.get("section", "")
        elif operation == "search":
            qe_payload["operation"] = "search"
        return self._handle_list_qe_parameter_metadata(qe_payload)

    # For other engines with metadata modules
    try:
        metadata_module = None
        if engine_family == "vasp":
            from quantumvitas.drivers.vasp.data import vasp_metadata as metadata_module
        elif engine_family == "orca":
            from quantumvitas.drivers.orca.data import orca_metadata as metadata_module
        elif engine_family == "lammps":
            from quantumvitas.drivers.lammps.data import lammps_metadata as metadata_module
        elif engine_family == "gaussian":
            from quantumvitas.drivers.gaussian.data import gaussian_metadata as metadata_module
        elif engine_family == "abinit":
            from quantumvitas.drivers.abinit.data import abinit_metadata as metadata_module
        elif engine_family == "cp2k":
            from quantumvitas.drivers.cp2k.data import cp2k_metadata as metadata_module
        elif engine_family == "qmcpack":
            from quantumvitas.drivers.qmcpack.data import qmcpack_metadata as metadata_module

        if metadata_module is None:
            return {"categories": [], "tags": [], "results": []}

        if operation == "list_categories":
            if hasattr(metadata_module, 'list_categories'):
                cats = metadata_module.list_categories()
                return {"categories": [{"id": c, "label": c} for c in sorted(cats)]}
            return {"categories": []}

        elif operation == "list_tags":
            category = payload.get("category", "")
            if hasattr(metadata_module, 'list_tags'):
                tags = metadata_module.list_tags(category=category) if category else metadata_module.list_tags()
                result = []
                for tag_name in sorted(tags) if isinstance(tags, (list, set)) else sorted(tags):
                    info = metadata_module.get_tag_info(tag_name) if hasattr(metadata_module, 'get_tag_info') else {}
                    if info:
                        result.append({
                            "name": tag_name,
                            "type": info.get("type", "string"),
                            "default": info.get("default"),
                            "description": info.get("description", ""),
                            "category": info.get("category", category),
                        })
                return {"tags": result}
            return {"tags": []}

        elif operation == "search":
            query = payload.get("query", "").lower()
            if not query:
                raise ValueError("'query' is required for search operation")
            if hasattr(metadata_module, 'list_tags'):
                tags = metadata_module.list_tags()
                results = []
                for tag_name in tags if isinstance(tags, (list, set)) else list(tags):
                    info = metadata_module.get_tag_info(tag_name) if hasattr(metadata_module, 'get_tag_info') else {}
                    name_lower = tag_name.lower()
                    desc_lower = (info.get("description", "") or "").lower() if info else ""
                    if query in name_lower or query in desc_lower:
                        results.append({
                            "name": tag_name,
                            "type": info.get("type", "string") if info else "string",
                            "default": info.get("default") if info else None,
                            "description": info.get("description", "") if info else "",
                            "category": info.get("category", "") if info else "",
                        })
                return {"results": results}
            return {"results": []}

        else:
            raise ValueError(f"Unknown operation '{operation}'. Must be: list_categories, list_tags, search")

    except (ImportError, AttributeError) as e:
        return {"categories": [], "tags": [], "results": [], "error": str(e)}
```

### Step 6: Implement `_handle_set_engine_family`

```python
def _handle_set_engine_family(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set engine_family on a calculation (UNDECIDED -> DECIDED transition).

    Payload:
        project_root: str (required)
        calculation: str (required) — Calculation selector
        engine_family: str (required) — Engine to set

    Returns:
        {"success": true, "engine_family": "vasp"}
    """
    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers

    project_root = self._require_path(payload, "project_root")
    calculation_selector = self._require_str(payload, "calculation")
    engine_family = self._require_str(payload, "engine_family")

    # Validate engine_family is registered
    if not DriverRegistry.is_engine_registered(engine_family):
        raise ValueError(
            f"Unknown engine_family '{engine_family}'. "
            f"Registered: {sorted(DriverRegistry.get_all_engines())}"
        )

    # Validate it's a base engine (can't set postprocessing as family)
    driver = DriverRegistry.get_driver(engine_family)
    role = getattr(driver, 'ENGINE_ROLE', 'base')
    if role != 'base':
        raise ValueError(
            f"Cannot set engine_family to '{engine_family}' — it has ENGINE_ROLE='{role}'. "
            "Only base engines can be set as engine_family."
        )

    # Load calculation and update engine_family
    svc = get_service(project_root)
    cache = self.state.get_cache(project_root)

    # Read calculation.yaml, set engine_family, save
    from quantumvitas.api.utils import load_calculation
    calc_model = load_calculation(project_root, calculation_selector, index=cache.index)

    calc_model.engine_family = engine_family
    # Save back to YAML
    svc.calculation.save_calculation_model(calc_model, index=cache.index, config=cache.config)

    self.log(f"[RPC] set_engine_family: {calculation_selector} -> {engine_family}")

    return {"success": True, "engine_family": engine_family}
```

**NOTE**: The exact implementation of `save_calculation_model` depends on the existing service API. If this method doesn't exist, you'll need to use whatever save mechanism the codebase provides. Look at how `_handle_create_calculation` saves calculation data for the pattern.

### Step 7: Write tests

Create `tests/daemon/test_generic_rpcs.py`:

```python
"""
Tests for generic engine RPCs (M4).

These test the RPC handler logic directly, not through the daemon socket.
"""
import pytest

from quantumvitas.core.driver_registry import DriverRegistry
import quantumvitas.drivers


class TestListEngineFamilies:
    """Test list_engine_families RPC."""

    def test_returns_all_15_engines(self):
        engines = sorted(DriverRegistry.get_all_engines())
        assert len(engines) == 15

    def test_engine_has_required_fields(self):
        for family in DriverRegistry.get_all_engines():
            driver = DriverRegistry.get_driver(family)
            assert hasattr(driver, 'display_name')
            assert hasattr(driver, 'ENGINE_ROLE')
            assert hasattr(driver, 'COMPANION_ENGINES')
            assert hasattr(driver, 'SUPPORTED_GEN_STEPS')

    def test_qe_has_companions(self):
        driver = DriverRegistry.get_driver("qe")
        companions = getattr(driver, 'COMPANION_ENGINES', frozenset())
        assert "w90" in companions
        assert "qmcpack" in companions
        assert "yambo" in companions

    def test_postproc_engines_have_correct_role(self):
        for family in ["w90", "qmcpack", "yambo"]:
            driver = DriverRegistry.get_driver(family)
            assert getattr(driver, 'ENGINE_ROLE', 'base') == 'postprocessing'


class TestListStepPalette:
    """Test list_step_palette RPC logic."""

    def test_qe_palette_has_base_steps(self):
        driver = DriverRegistry.get_driver("qe")
        supported = getattr(driver, 'SUPPORTED_GEN_STEPS', set())
        assert "scf" in supported
        assert "nscf" in supported
        assert "relax" in supported

    def test_qe_palette_has_companions(self):
        driver = DriverRegistry.get_driver("qe")
        companions = getattr(driver, 'COMPANION_ENGINES', frozenset())
        assert len(companions) == 3

    def test_vasp_palette_has_no_companions(self):
        driver = DriverRegistry.get_driver("vasp")
        companions = getattr(driver, 'COMPANION_ENGINES', frozenset())
        assert len(companions) == 0

    def test_undecided_returns_empty(self):
        """UNDECIDED (engine_family=None) returns no base steps."""
        # This tests the logic that the handler implements
        # When engine_family is None, base_steps and companion_steps are empty
        pass  # Handler-level test would mock the daemon


class TestResolveCompanionStep:
    """Test DriverRegistry.resolve_companion_step (added in M3)."""

    def test_qe_scf(self):
        assert DriverRegistry.resolve_companion_step("qe", "scf") == "qe_scf"

    def test_qe_wannierprep(self):
        assert DriverRegistry.resolve_companion_step("qe", "wannierprep") == "w90_wannierprep"

    def test_vasp_no_companions(self):
        assert DriverRegistry.resolve_companion_step("vasp", "wannierprep") is None
```

## Invariants to Preserve

- Existing QE RPCs (`detect_qe`, `list_qe_ui_parameters`, etc.) STILL WORK — do NOT delete them
- The `_handlers` dict registration order doesn't matter (it's a dict, not a list)
- New RPCs return consistent shapes across engines (same top-level keys)
- `set_engine_family` validates that the engine is registered and is a base engine
- The daemon import chain remains clean: daemon imports from api/core, never from runners/executors
- No new engine-specific metadata modules are created (use existing ones from drivers/)

## Verifiers

```bash
# 1. New RPC tests pass
source .venv/bin/activate && python -m pytest tests/daemon/test_generic_rpcs.py -v

# 2. Existing QE RPCs still work
python -m pytest tests/daemon/ -v -k "qe" --tb=short

# 3. Verify new handlers are registered
grep -n "list_engine_families\|list_step_palette\|list_engine_ui_parameters\|list_engine_parameter_metadata\|set_engine_family" src/quantumvitas/daemon/server.py

# 4. Full test suite
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

## Do NOT Do

- Do NOT delete existing QE RPC handlers (that's M8)
- Do NOT modify GUI files (that's M5-M7)
- Do NOT modify driver files
- Do NOT create new engine metadata modules — use existing ones from drivers/<engine>/data/
- Do NOT add engine_family to the daemon's global state (it's per-calculation, stored in YAML)
- Do NOT use prefix inference to determine engine from step type
- Do NOT introduce a default engine for `set_engine_family`
- Do NOT modify the DriverRegistry singleton pattern

## Expected Failure Modes

1. **Inconsistent return shapes**: `list_engine_ui_parameters` for QE returns `{namelist, name, ...}` but for VASP returns `{key, label, ...}`. The shapes MUST be normalized to a common schema.
2. **Missing metadata modules**: Some engines (siesta, gpaw, psi4, pyscf, xtb) don't have metadata modules yet. The handler must return `{"parameters": []}` for them, not crash.
3. **Import errors in daemon**: Lazy imports of engine metadata modules may fail if the engine data isn't installed. Wrap in try/except.
4. **Breaking existing QE RPC tests**: If you accidentally modify the QE handler code while adding new handlers, existing tests will break.
5. **`save_calculation_model` doesn't exist**: The `set_engine_family` handler needs to persist the change. Find the existing pattern for saving calculation data (look at `_handle_create_calculation` or `_handle_update_step_params`).
