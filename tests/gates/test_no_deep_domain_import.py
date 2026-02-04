"""
Gate test G-K2b: No cross-domain deep imports bypassing public.py.

Law K2 (KERNEL_DEPENDENCY_SPEC §3.5): All cross-domain imports MUST go
through the domain's ``public.py`` entry point. This test enforces that rule
for the six domains that have public.py:

    core, calculation, execution, engine, workflow, analysis

Allowlisted violations fall into two categories:
1. **DAG violations** — imports that violate the dependency DAG
   (e.g., core → calculation). These need code movement (PR-K7).
2. **Not-in-public** — symbols too internal for public.py
   (private helpers, resolvers, etc.). These are individually exempted.

To add a new symbol to a domain's public.py:
1. Add the import to ``src/quantumvitas/<domain>/public.py``
2. Migrate all cross-domain consumers to use ``from quantumvitas.<domain>.public import ...``
3. The gate test will automatically pass for the new symbol.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Set

import pytest

SRC = Path(__file__).resolve().parent.parent.parent / "src" / "quantumvitas"

DOMAINS = {"core", "calculation", "execution", "engine", "workflow", "analysis"}

# Dependency DAG: domain → set of domains it may import from.
_DAG = {
    "core": set(),  # L0 — imports from no other domain
    "calculation": {"core"},  # L1
    "workflow": {"core"},  # L1
    "engine": {"core"},  # L1
    "execution": {"core", "calculation", "workflow", "engine"},  # L2
    "analysis": {"core", "calculation", "execution"},  # L2
}

# ---------------------------------------------------------------------------
# Allowlists
# ---------------------------------------------------------------------------

# DAG-violating files — these import from domains they shouldn't.
# They need *code movement* (PR-K7), not import path changes.
# Format: "domain/relative_path.py"
_DAG_VIOLATION_FILES: Set[str] = {
    # core (L0) → calculation (L1)
    "core/resolution.py",
    "core/project_utils.py",
    "core/project_context.py",
    "core/templates.py",
    "core/selectors.py",
    # core (L0) → workflow (L1)
    "core/driver_registry.py",
    "core/calc_identity.py",
    # core (L0) → execution (L2)
    "core/driver_protocol.py",
    # core (L0) → analysis (L2)
    "core/structure_canonicalize.py",
    "core/structure_fingerprint.py",
    # calculation (L1) → workflow (L1)
    "calculation/calculation.py",
    "calculation/compat_executor.py",
    "calculation/importers.py",
    "calculation/input_runner.py",
    "calculation/manifest_reconcile.py",
    "calculation/runner.py",
    "calculation/structure_steps.py",
    "calculation/verification.py",
    # calculation (L1) → engine (L1)
    "calculation/step.py",
    # calculation (L1) → execution (L2)
    # (runner.py already listed above)
    # calculation (L1) → analysis (L2)
    "calculation/geometry.py",
    # engine (L1) → calculation (L1)
    "engine/cp2k_engine.py",
    "engine/cp2k_writer.py",
    "engine/lammps_engine.py",
    "engine/qmcpack_engine.py",
    "engine/vasp_engine.py",
    # engine (L1) → workflow (L1)
    "engine/orca_engine.py",
    "engine/pyscf_engine.py",
    # engine (L1) → execution (L2)
    # (cp2k_engine.py already listed above)
    # workflow (L1) → engine (L1)
    "workflow/registry.py",
    # workflow (L1) → calculation (L1)
    "workflow/step_factory.py",
}

# Symbols that are too internal for public.py — individual (file, module) pairs.
# Format: { "domain/file.py": {"quantumvitas.target_domain.internal_module", ...} }
_NOT_IN_PUBLIC_ALLOWLIST: dict[str, Set[str]] = {
    # Private pseudo helpers
    "calculation/input_runner.py": {"quantumvitas.core.pseudo_config"},
    "calculation/runner.py": {"quantumvitas.core.pseudo_runtime"},
    "calculation/species_config.py": {"quantumvitas.core.project_utils"},  # find_calculation_entry, calculation_directory
    "calculation/structure_steps.py": {"quantumvitas.core.pseudo_config"},
    # Engine-specific resolvers (one per engine family)
    "engine/cp2k_engine.py": {"quantumvitas.core.engines.cp2k_resolver"},
    "engine/lammps_engine.py": {"quantumvitas.core.engines.lammps_resolver"},
    "engine/qmcpack_engine.py": {"quantumvitas.core.engines.qmcpack_resolver"},
    "engine/orca_engine.py": {"quantumvitas.core.engines.orca_resolver"},
    "engine/psi4_engine.py": {"quantumvitas.core.engines.discovery"},
    "engine/vasp_engine.py": {"quantumvitas.core.engines.vasp_resolver"},
    "engine/vasp_writer.py": {"quantumvitas.core.engines.vasp_resolver"},
    # Internal analysis model (trajectory frame)
    "engine/lammps_parser.py": {"quantumvitas.core.analysis.trajectory.model"},
    # Manifest alias (RunManifest = Manifest, TYPE_CHECKING only)
    "execution/executor.py": {"quantumvitas.calculation.manifest"},
    # Calculation geometry helpers (not exported via public.py)
    "execution/relax_artifacts.py": {"quantumvitas.calculation.geometry"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_domain(path: Path) -> str | None:
    """Get the domain name from a file path under src/quantumvitas/."""
    try:
        rel = path.relative_to(SRC)
    except ValueError:
        return None
    parts = rel.parts
    return parts[0] if parts and parts[0] in DOMAINS else None


def _get_target_domain(module: str) -> str | None:
    """Extract target domain from a module path like 'quantumvitas.core.yaml_io'."""
    parts = module.split(".")
    if len(parts) >= 2 and parts[0] == "quantumvitas" and parts[1] in DOMAINS:
        return parts[1]
    return None


def _is_through_public(module: str) -> bool:
    """True if the import goes through public.py."""
    parts = module.split(".")
    return (
        len(parts) == 3
        and parts[0] == "quantumvitas"
        and parts[1] in DOMAINS
        and parts[2] == "public"
    )


def _is_dag_ok(src_domain: str, target_domain: str) -> bool:
    """True if src_domain is allowed to import from target_domain."""
    if src_domain == target_domain:
        return True
    return target_domain in _DAG.get(src_domain, set())


def _rel_path(file_path: Path) -> str:
    """Return domain-relative path like 'core/resolution.py'."""
    return str(file_path.relative_to(SRC))


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def _scan_violations():
    """Scan all 6 domains for cross-domain deep imports."""
    violations = []

    for domain in sorted(DOMAINS):
        domain_dir = SRC / domain
        if not domain_dir.exists():
            continue

        for py_file in sorted(domain_dir.rglob("*.py")):
            if py_file.name == "public.py":
                continue

            src_domain = _get_domain(py_file)
            if not src_domain:
                continue

            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            rel = _rel_path(py_file)

            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue

                module = node.module
                target_domain = _get_target_domain(module)
                if not target_domain or target_domain == src_domain:
                    continue  # intra-domain or non-domain target

                if _is_through_public(module):
                    continue  # correctly using public.py

                # --- This is a cross-domain deep import ---

                # Check DAG violation allowlist
                if not _is_dag_ok(src_domain, target_domain):
                    if rel in _DAG_VIOLATION_FILES:
                        continue  # known DAG violation, allowlisted
                    # New DAG violation — still report it
                    violations.append(
                        f"{rel}:{node.lineno}  DAG violation [{src_domain}→{target_domain}]: "
                        f"from {module} import {', '.join(a.name for a in node.names)}"
                    )
                    continue

                # Check not-in-public allowlist
                allowed_modules = _NOT_IN_PUBLIC_ALLOWLIST.get(rel, set())
                if module in allowed_modules:
                    continue  # individually exempted

                # This is an un-allowlisted deep import — violation!
                names = ", ".join(a.name for a in node.names)
                violations.append(
                    f"{rel}:{node.lineno}  from {module} import {names}"
                )

    return violations


# ---------------------------------------------------------------------------
# Staleness check — warn if allowlist entries no longer match
# ---------------------------------------------------------------------------

def _check_staleness():
    """Find allowlist entries that no longer correspond to actual violations."""
    stale = []

    # Check DAG violation files
    for rel in sorted(_DAG_VIOLATION_FILES):
        py_file = SRC / rel
        if not py_file.exists():
            stale.append(f"DAG allowlist: {rel} — file does not exist")
            continue

        src_domain = _get_domain(py_file)
        if not src_domain:
            stale.append(f"DAG allowlist: {rel} — not in a domain")
            continue

        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue

        has_dag_violation = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                td = _get_target_domain(node.module)
                if td and td != src_domain and not _is_dag_ok(src_domain, td):
                    has_dag_violation = True
                    break

        if not has_dag_violation:
            stale.append(f"DAG allowlist: {rel} — no DAG violations found (can be removed)")

    # Check not-in-public allowlist
    for rel, modules in sorted(_NOT_IN_PUBLIC_ALLOWLIST.items()):
        py_file = SRC / rel
        if not py_file.exists():
            stale.append(f"Not-in-public allowlist: {rel} — file does not exist")
            continue

        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue

        found_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module in modules:
                    found_modules.add(node.module)

        for mod in sorted(modules - found_modules):
            stale.append(f"Not-in-public allowlist: {rel} exempts {mod} — no such import found (can be removed)")

    return stale


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_no_cross_domain_deep_imports():
    """
    G-K2b: All cross-domain imports within the 6 public.py domains
    MUST go through public.py, unless DAG-allowlisted or individually exempted.
    """
    violations = _scan_violations()

    if violations:
        msg = (
            f"Found {len(violations)} cross-domain deep import(s) bypassing public.py.\n"
            "Each import below must be changed to: "
            "from quantumvitas.<domain>.public import <symbol>\n\n"
        )
        msg += "\n".join(f"  {v}" for v in violations)
        pytest.fail(msg)


def test_allowlist_not_stale():
    """
    Warn (do not fail) if allowlist entries no longer match actual violations.
    This helps keep the allowlist clean as code is moved.
    """
    stale = _check_staleness()
    if stale:
        import warnings
        warnings.warn(
            f"Stale allowlist entries ({len(stale)}):\n"
            + "\n".join(f"  {s}" for s in stale),
            stacklevel=2,
        )
