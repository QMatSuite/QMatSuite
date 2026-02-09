"""
Gate tests for analysis-object/primitive-pipeline invariants.

Reference:
- docs/architecture/ANALYSIS_OBJECT_PRIMITIVES_SPEC.md (§2, §5, §12.1)
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pytest

import quantumvitas.core.analysis.orchestrator as orchestrator_mod
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


def _make_test_band_structure(step_ulids: list[str], gen_steps: list[str]) -> BandStructure:
    meta = AnalysisObjectMeta.create(
        object_type="bands",
        source_files=[],
        run_ulid="01RUN",
        calc_ulid="01CALC",
        step_ulids=step_ulids,
        gen_steps=gen_steps,
        engine_name="qe",
        parser_name="test_provider",
        parser_version="1.0",
    )
    return BandStructure(
        meta=meta,
        k_distances=np.array([0.0, 1.0]),
        eigenvalues=np.array([[0.0, 0.5], [1.0, 1.5]]),
        high_symmetry_points=[HighSymPoint(k_distance=0.0, label="G")],
        fermi_energy=0.25,
    )


def test_no_redundant_canonical(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """§5.3: overlapping capabilities for one object_type produce one canonical bundle."""

    class _Provider:
        def can_parse(self, raw_dir: Path) -> bool:
            return True

        def parse(self, raw_dir: Path, calc_dir: Path, **kwargs: object) -> BandStructure:
            return _make_test_band_structure(
                step_ulids=list(kwargs.get("step_ulids", [])),
                gen_steps=list(kwargs.get("gen_steps", [])),
            )

    class _DriverOne:
        ANALYSIS_CAPABILITIES = [
            AnalysisCapability(object_type="bands", gen_step_sequence=["bandspw"], evidence_files=[]),
        ]

    class _DriverOverlap:
        ANALYSIS_CAPABILITIES = [
            AnalysisCapability(object_type="bands", gen_step_sequence=["bandspw"], evidence_files=[]),
            AnalysisCapability(object_type="bands", gen_step_sequence=["scf", "bandspw"], evidence_files=[]),
        ]

    monkeypatch.setattr(orchestrator_mod, "get_parser", lambda engine, object_type: _Provider)
    ordered_gen_steps = [
        ("01SCF", "scf", tmp_path / "scf"),
        ("01BANDS", "bandspw", tmp_path / "bands"),
    ]

    result_single = orchestrator_mod.run_post_run_analysis(
        engine="qe",
        driver=_DriverOne(),
        ordered_gen_steps=ordered_gen_steps,
        run_ulid="01RUN",
        calc_ulid="01CALC",
        calc_dir=tmp_path,
    )
    assert len(result_single) == 1
    assert result_single[0]["object_type"] == "bands"

    result_overlap = orchestrator_mod.run_post_run_analysis(
        engine="qe",
        driver=_DriverOverlap(),
        ordered_gen_steps=ordered_gen_steps,
        run_ulid="01RUN",
        calc_ulid="01CALC",
        calc_dir=tmp_path,
    )
    assert len(result_overlap) == 1
    assert result_overlap[0]["object_type"] == "bands"
    assert result_overlap[0]["canonical"].provenance_meta.step_ulids == ["01SCF", "01BANDS"]


def test_unknown_engine_analysis_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    Inv-A13: unknown parser resolution must not silently succeed.

    Batch orchestrator currently warns and skips; this test also accepts a hard
    error if behavior is tightened in the future.
    """

    class _Driver:
        ANALYSIS_CAPABILITIES = [
            AnalysisCapability(object_type="unknown_object", gen_step_sequence=["scf"], evidence_files=[]),
        ]

    monkeypatch.setattr(orchestrator_mod, "get_parser", lambda engine, object_type: None)

    try:
        with pytest.warns(UserWarning, match="No analysis provider registered"):
            result = orchestrator_mod.run_post_run_analysis(
                engine="qe",
                driver=_Driver(),
                ordered_gen_steps=[("01STEP", "scf", tmp_path / "scf")],
                calc_dir=tmp_path,
            )
        assert result == []
    except RuntimeError:
        # Accept hard error behavior if orchestrator changes to strict mode.
        pass


def test_no_analysis_disk_cache() -> None:
    """Inv-A10: analysis core modules do not write/read disk cache artifacts."""
    for path in _python_files(ANALYSIS_DIR):
        # cas_writer is an explicit CAS persistence helper used by the API layer.
        # It is not an analysis-core memo/cache path.
        if path.name == "cas_writer.py":
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            fn_name = ""
            qualifier = ""
            if isinstance(node.func, ast.Name):
                fn_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                fn_name = node.func.attr
                if isinstance(node.func.value, ast.Name):
                    qualifier = node.func.value.id

            if fn_name == "open":
                raise AssertionError(f"{path}:{node.lineno} contains forbidden disk-cache call 'open'")
            if fn_name == "write_text":
                raise AssertionError(
                    f"{path}:{node.lineno} contains forbidden disk-cache call 'write_text'"
                )
            if fn_name == "write" and qualifier == "Path":
                raise AssertionError(
                    f"{path}:{node.lineno} contains forbidden disk-cache call 'Path.write'"
                )
            if fn_name == "dump" and qualifier in {"json", "pickle"}:
                raise AssertionError(
                    f"{path}:{node.lineno} contains forbidden disk-cache call '{qualifier}.dump'"
                )


def test_no_lazy_payloads() -> None:
    """Inv-A9: no lazy payload wrappers inside analysis core."""
    forbidden = ["LazyArray", "LateList", "deferred", "proxy"]
    for path in _python_files(ANALYSIS_DIR):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path} contains forbidden lazy token '{token}'"


def _iter_non_comment_lines(path: Path) -> Iterable[tuple[int, str]]:
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        yield line_number, stripped


def test_no_tmp_corpus_in_runtime() -> None:
    """Inv-A14: analysis runtime paths do not reference .tmp corpus inputs."""
    runtime_roots = [
        REPO_ROOT / "src" / "quantumvitas" / "core" / "analysis",
        REPO_ROOT / "src" / "quantumvitas" / "drivers",
        REPO_ROOT / "src" / "quantumvitas" / "api",
    ]
    runtime_files = sorted(
        path
        for root in runtime_roots
        for path in root.rglob("*.py")
        if "tests" not in str(path)
    )

    tmp_pattern = re.compile(r"\.tmp/")
    for path in runtime_files:
        for line_number, line in _iter_non_comment_lines(path):
            assert not tmp_pattern.search(line), (
                f"{path}:{line_number} references '.tmp/' in runtime analysis path: {line}"
            )


def test_no_legacy_analysis_artifact_imports() -> None:
    """Legacy analysis/artifacts.py must not be imported by runtime code."""
    runtime_roots = [
        REPO_ROOT / "src" / "quantumvitas" / "api",
        REPO_ROOT / "src" / "quantumvitas" / "daemon",
        REPO_ROOT / "src" / "quantumvitas" / "core",
    ]
    for root in runtime_roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "from quantumvitas.analysis.artifacts" not in text, (
                f"{path} imports deprecated analysis/artifacts module"
            )
            assert "quantumvitas.analysis.artifacts" not in text, (
                f"{path} references deprecated analysis/artifacts module"
            )


def test_derived_never_persisted() -> None:
    """Inv-A11: API persistence paths must not write derived bundles."""
    service_path = REPO_ROOT / "src" / "quantumvitas" / "api" / "service.py"
    source = service_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(service_path))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn_name = ""
        if isinstance(node.func, ast.Name):
            fn_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            fn_name = node.func.attr
        if fn_name != "write_canonical_to_cas":
            continue

        if node.args:
            first_arg_src = ast.unparse(node.args[0]).lower()
            assert "derived" not in first_arg_src, (
                f"{service_path}:{node.lineno} persists derived bundle path: {first_arg_src}"
            )


def test_operational_path_no_cas_read() -> None:
    """Inv-A11: operational get_analysis path must not read CAS snapshots."""
    service_path = REPO_ROOT / "src" / "quantumvitas" / "api" / "service.py"
    source = service_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(service_path))

    analysis_get_analysis = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Analysis":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "get_analysis":
                    analysis_get_analysis = item
                    break
    assert analysis_get_analysis is not None, "QVService.Analysis.get_analysis not found"

    forbidden_calls = {"_load_snapshot_bundle", "retrieve", "retrieve_json"}
    for subnode in ast.walk(analysis_get_analysis):
        if not isinstance(subnode, ast.Call):
            continue
        fn_name = ""
        if isinstance(subnode.func, ast.Name):
            fn_name = subnode.func.id
        elif isinstance(subnode.func, ast.Attribute):
            fn_name = subnode.func.attr
        assert fn_name not in forbidden_calls, (
            f"{service_path}:{subnode.lineno} operational path calls forbidden CAS read API '{fn_name}'"
        )


def test_cas_is_content_addressed() -> None:
    """Inv-A11: analysis snapshots link runs to canonical_sha content hashes."""
    schema_path = REPO_ROOT / "src" / "quantumvitas" / "provenance" / "schema.py"
    schema_src = schema_path.read_text(encoding="utf-8")

    assert "analysis_snapshots" in schema_src
    assert "canonical_sha TEXT NOT NULL" in schema_src
    assert "UNIQUE(run_ulid, object_type)" in schema_src
    assert "owner_step_ulid" not in schema_src


def test_golden_daemon_tests_exist() -> None:
    """Gate: golden daemon E2E tests must exist with correct markers and assertions."""
    tests_dir = REPO_ROOT / "tests" / "daemon"
    checks = [
        ("test_si_bands_golden_daemon.py", "pytest.mark.qe_core"),
        ("test_vasp_bands_golden_daemon.py", "pytest.mark.vasp_core"),
    ]
    for filename, marker in checks:
        path = tests_dir / filename
        assert path.exists(), f"Golden daemon test missing: {path}"
        text = path.read_text(encoding="utf-8")
        assert marker in text, f"{filename} missing marker {marker}"
        assert "analysis_snapshots" in text, f"{filename} missing SQLite assertion"
        assert '".cas"' in text, f"{filename} missing CAS blob assertion"


def test_frontend_no_kernel_import() -> None:
    """Inv-A12: frontend must consume API only, never kernel modules directly."""
    frontend_root = REPO_ROOT / "gui" / "src"
    assert frontend_root.exists(), "gui/src not found"

    forbidden = [
        "quantumvitas.core",
        "quantumvitas.analysis",
        "quantumvitas.drivers",
    ]
    ts_like = list(frontend_root.rglob("*.ts")) + list(frontend_root.rglob("*.tsx"))

    for path in ts_like:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, (
                f"{path} imports forbidden backend kernel path '{token}'"
            )
