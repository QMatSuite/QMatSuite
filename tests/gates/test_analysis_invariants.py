"""
Gate tests for analysis-object/primitive-pipeline invariants.

Reference:
- docs/architecture/ANALYSIS_OBJECT_PRIMITIVES_SPEC.md (§2, §5, §12.1)
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Iterable

import numpy as np

from quantumvitas.core.analysis.band_structure import BandStructure, HighSymPoint
from quantumvitas.core.analysis.base import AnalysisObjectMeta
from quantumvitas.core.analysis.bundles import RenderMeta
from quantumvitas.core.analysis.capability import (
    AnalysisCapability,
    find_contiguous_match,
)
from quantumvitas.core.driver_registry import DriverRegistry


REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = REPO_ROOT / "src" / "quantumvitas" / "core" / "analysis"
TRANSFORMS_DIR = ANALYSIS_DIR / "transforms"


def _python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.name != "__init__.py")


def _parse_file(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _class_defs(tree: ast.AST) -> Iterable[ast.ClassDef]:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            yield node


def _func_defs(class_node: ast.ClassDef, name: str) -> list[ast.FunctionDef]:
    return [
        node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]


def _decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        root = _decorator_name(node.value)
        return f"{root}.{node.attr}" if root else node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return ""


def _is_engine_ref(expr: ast.expr) -> bool:
    if isinstance(expr, ast.Name):
        return expr.id in {"engine", "engine_name"}
    if isinstance(expr, ast.Attribute):
        return expr.attr in {"engine", "engine_name"}
    return False


def test_analysis_object_meta_required() -> None:
    """Inv-A2: every AnalysisObject class defines meta: AnalysisObjectMeta."""
    classes_with_to_primitives: list[tuple[Path, str]] = []

    for path in _python_files(ANALYSIS_DIR):
        tree = _parse_file(path)
        for class_node in _class_defs(tree):
            if not _func_defs(class_node, "to_primitives"):
                continue
            classes_with_to_primitives.append((path, class_node.name))

            meta_fields = [
                stmt
                for stmt in class_node.body
                if isinstance(stmt, ast.AnnAssign)
                and isinstance(stmt.target, ast.Name)
                and stmt.target.id == "meta"
            ]
            assert meta_fields, (
                f"{path}:{class_node.lineno} class '{class_node.name}' has to_primitives() "
                "but no 'meta' field"
            )
            annotation_src = ast.unparse(meta_fields[0].annotation)
            assert "AnalysisObjectMeta" in annotation_src, (
                f"{path}:{meta_fields[0].lineno} class '{class_node.name}' meta field "
                f"annotation is '{annotation_src}', expected AnalysisObjectMeta"
            )

    assert classes_with_to_primitives, "No AnalysisObject classes with to_primitives() found"


def test_canonical_bundle_deterministic() -> None:
    """Inv-A4: canonical output is deterministic and excludes created_at."""
    meta = AnalysisObjectMeta.create(
        object_type="bands",
        source_files=[],
        run_ulid="01JTESTRUN",
        calc_ulid="01JTESTCALC",
        step_ulids=["01STEP1"],
        gen_steps=["bandspw"],
        engine_name="qe",
        parser_name="qe_bands",
        parser_version="1.0",
    )
    band_structure = BandStructure(
        meta=meta,
        k_distances=np.array([0.0, 0.5, 1.0]),
        eigenvalues=np.array(
            [
                [-1.0, 0.5],
                [-0.5, 1.0],
                [0.0, 1.5],
            ]
        ),
        high_symmetry_points=[HighSymPoint(k_distance=0.0, label="G")],
        fermi_energy=0.2,
    )

    canonical_1 = band_structure.to_primitives()
    canonical_2 = band_structure.to_primitives()

    serialized_1 = json.dumps(canonical_1.to_dict(), sort_keys=True, separators=(",", ":"))
    serialized_2 = json.dumps(canonical_2.to_dict(), sort_keys=True, separators=(",", ":"))

    assert serialized_1 == serialized_2
    assert "created_at" not in serialized_1


def test_to_primitives_is_parameterless() -> None:
    """Inv-A4: to_primitives signatures accept only self."""
    found = False

    for path in _python_files(ANALYSIS_DIR):
        tree = _parse_file(path)
        for class_node in _class_defs(tree):
            for fn in _func_defs(class_node, "to_primitives"):
                found = True
                args = fn.args
                assert not args.posonlyargs, f"{path}:{fn.lineno} to_primitives has posonly args"
                assert len(args.args) == 1 and args.args[0].arg == "self", (
                    f"{path}:{fn.lineno} to_primitives must accept only self"
                )
                assert args.vararg is None, f"{path}:{fn.lineno} to_primitives has *args"
                assert args.kwarg is None, f"{path}:{fn.lineno} to_primitives has **kwargs"
                assert not args.kwonlyargs, f"{path}:{fn.lineno} to_primitives has kw-only args"
                assert not args.defaults, f"{path}:{fn.lineno} to_primitives has default args"

    assert found, "No to_primitives() methods found"


def test_derived_never_cached() -> None:
    """Inv-A5: no caching decorators/dict-cache writes on Derived bundle producers."""
    derived_files = [
        path
        for path in _python_files(ANALYSIS_DIR)
        if "DerivedPrimitiveBundle" in path.read_text(encoding="utf-8")
    ]
    assert derived_files, "No files referencing DerivedPrimitiveBundle found"

    for path in derived_files:
        tree = _parse_file(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue

            decorator_names = {_decorator_name(decorator) for decorator in node.decorator_list}
            forbidden_decorators = {
                "lru_cache",
                "cache",
                "functools.lru_cache",
                "functools.cache",
            }
            assert not (decorator_names & forbidden_decorators), (
                f"{path}:{node.lineno} uses cache decorator on analysis transform path: "
                f"{decorator_names & forbidden_decorators}"
            )

            annotation_src = ast.unparse(node.returns) if node.returns is not None else ""
            returns_derived = "DerivedPrimitiveBundle" in annotation_src or (
                path.parent == TRANSFORMS_DIR and node.name == "apply"
            )
            if not returns_derived:
                continue

            for subnode in ast.walk(node):
                if not isinstance(subnode, ast.Assign):
                    continue
                for target in subnode.targets:
                    if not isinstance(target, ast.Subscript):
                        continue
                    owner = target.value
                    owner_name = ""
                    if isinstance(owner, ast.Name):
                        owner_name = owner.id
                    elif isinstance(owner, ast.Attribute):
                        owner_name = owner.attr
                    if any(token in owner_name.lower() for token in ("cache", "memo")):
                        assert False, (
                            f"{path}:{subnode.lineno} writes DerivedPrimitiveBundle path into "
                            f"cache-like container '{owner_name}'"
                        )


def test_render_meta_no_provenance() -> None:
    """Inv-A6: RenderMeta excludes provenance fields."""
    forbidden = {
        "engine_name",
        "run_ulid",
        "step_ulids",
        "parser_name",
        "source_files",
        "warnings",
    }
    fields = set(RenderMeta.__dataclass_fields__.keys())
    assert fields.isdisjoint(forbidden), (
        f"RenderMeta contains provenance fields: {sorted(fields & forbidden)}"
    )


def test_transform_no_engine_imports() -> None:
    """Inv-A7: transform modules must not import drivers."""
    for path in _python_files(TRANSFORMS_DIR):
        tree = _parse_file(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith("quantumvitas.drivers"), (
                    f"{path}:{node.lineno} imports from driver module '{module}'"
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("quantumvitas.drivers"), (
                        f"{path}:{node.lineno} imports driver module '{alias.name}'"
                    )


def test_no_engine_branching_in_orchestrator() -> None:
    """Inv-A13: no engine-conditional logic in universal analysis layer."""
    target_files = [
        ANALYSIS_DIR / "orchestrator.py",
        ANALYSIS_DIR / "bundles.py",
        *(_python_files(TRANSFORMS_DIR)),
    ]

    for path in target_files:
        tree = _parse_file(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            left = node.left
            for comparator in node.comparators:
                is_engine_string_cmp = (
                    (_is_engine_ref(left) and isinstance(comparator, ast.Constant) and isinstance(comparator.value, str))
                    or (_is_engine_ref(comparator) and isinstance(left, ast.Constant) and isinstance(left.value, str))
                )
                if is_engine_string_cmp:
                    assert False, (
                        f"{path}:{node.lineno} has engine-conditional comparison: "
                        f"{ast.unparse(node)}"
                    )


def test_analysis_capability_declaration() -> None:
    """§5.2: engines with analysis providers declare matching capabilities."""
    providers_by_engine: dict[str, set[str]] = {}
    parser_dir = REPO_ROOT / "src" / "quantumvitas" / "drivers"

    for path in _python_files(parser_dir):
        if "/parsers/" not in str(path):
            continue
        tree = _parse_file(path)
        for class_node in _class_defs(tree):
            for decorator in class_node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if _decorator_name(decorator.func) != "register_parser":
                    continue
                if len(decorator.args) < 2:
                    continue
                engine_arg, object_arg = decorator.args[0], decorator.args[1]
                if not (
                    isinstance(engine_arg, ast.Constant)
                    and isinstance(engine_arg.value, str)
                    and isinstance(object_arg, ast.Constant)
                    and isinstance(object_arg.value, str)
                ):
                    continue
                object_type = object_arg.value.lower()
                if object_type.endswith("_digest"):
                    continue
                providers_by_engine.setdefault(engine_arg.value.lower(), set()).add(object_type)

    assert providers_by_engine, "No analysis providers discovered in parser decorators"

    import quantumvitas.drivers  # noqa: F401 - ensure drivers are registered

    for engine, object_types in providers_by_engine.items():
        driver = DriverRegistry.get_driver(engine)
        capabilities = getattr(driver, "ANALYSIS_CAPABILITIES", [])
        capability_types = {cap.object_type.lower() for cap in capabilities}

        for capability in capabilities:
            assert isinstance(capability.gen_step_sequence, list), (
                f"{engine} capability '{capability.object_type}' has non-list gen_step_sequence"
            )
            assert len(capability.gen_step_sequence) >= 1, (
                f"{engine} capability '{capability.object_type}' has empty gen_step_sequence"
            )

        missing = object_types - capability_types
        assert not missing, (
            f"Engine '{engine}' has registered analysis providers without capabilities: "
            f"{sorted(missing)}"
        )


def test_capability_match_deterministic() -> None:
    """§5.3: capability matching is deterministic for identical inputs."""
    capability = AnalysisCapability(
        object_type="bands",
        gen_step_sequence=["scf", "bandspw"],
    )
    ordered_steps = [
        ("01STEPA", "scf", Path("/tmp/a")),
        ("01STEPB", "bandspw", Path("/tmp/b")),
        ("01STEPC", "scf", Path("/tmp/c")),
        ("01STEPD", "bandspw", Path("/tmp/d")),
    ]

    first = find_contiguous_match(capability, ordered_steps)
    second = find_contiguous_match(capability, ordered_steps)
    third = find_contiguous_match(capability, ordered_steps)

    assert first == second == third
    assert first is not None
    assert first.step_ulids == ["01STEPA", "01STEPB"]
