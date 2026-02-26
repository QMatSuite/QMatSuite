"""
QMSService: Main API service class.

This module provides the QMSService class which is the primary entry point
for all API operations.
"""

from __future__ import annotations

from pathlib import Path

from qmatsuite.api._mapping.dto_mapping import (
    structure_to_dto,
    calculation_to_dto,
    step_to_dto,
)
from qmatsuite.api._mapping.exc_mapping import map_kernel_exception
from qmatsuite.api.errors import APIError
from qmatsuite.api.types.calculation import CalculationDTO, CalculationRefDTO, StepDTO
from qmatsuite.api.types.run import RunResultDTO
from qmatsuite.api.types.structure import StructureDTO


class QMSService:
    """
    Service layer for QMatSuite operations.
    
    PR3: Analysis capabilities added.
    """
    
    def __init__(self, project_root: Path):
        """
        Initialize QMSService with a project root.
        
        Args:
            project_root: Path to project root (directory containing project.qms.yml)
        """
        self.project_root = Path(project_root).resolve()
        # Stub: minimal validation
        if not (self.project_root / "project.qms.yml").exists():
            raise ValueError(f"Not a project: {self.project_root}")
        self._analysis_cas_dir = self.project_root / ".provenance" / ".cas" / "analysis"
        self._analysis_memo_by_sha: dict[str, object] = {}
        self._analysis_index: dict[tuple[str, str, str], dict[str, object]] = {}

    def _safe_step_type_gen(self, step_type_spec: str) -> str:
        """Convert SPEC step type to GEN with robust fallback."""
        from qmatsuite.api import get_step_type_gen
        from qmatsuite.workflow.step_type_convert import gen_from

        try:
            return get_step_type_gen(step_type_spec)
        except Exception:
            return gen_from(step_type_spec)

    def _get_analysis_db_path(self) -> Path:
        from qmatsuite.provenance.db import ensure_provenance_initialized, get_db_path

        ensure_provenance_initialized(self.project_root)
        return get_db_path(self.project_root)

    def _compute_evidence_fingerprint(
        self,
        object_type: str,
        step_ulids: list[str],
        gen_steps: list[str],
        source_files: list[object],
    ) -> str:
        import hashlib
        import json

        normalized_source_files: list[dict] = []
        for source_file in source_files:
            if hasattr(source_file, "to_dict"):
                normalized_source_files.append(source_file.to_dict())
            elif isinstance(source_file, dict):
                normalized_source_files.append(
                    {
                        "path": source_file.get("path"),
                        "size_bytes": source_file.get("size_bytes"),
                        "mtime": source_file.get("mtime"),
                    }
                )

        normalized_source_files.sort(key=lambda row: str(row.get("path", "")))
        payload = {
            "object_type": object_type,
            "step_ulids": list(step_ulids),
            "gen_steps": list(gen_steps),
            "source_files": normalized_source_files,
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def _memoize_canonical_bundle(
        self,
        *,
        run_ulid: str,
        object_type: str,
        canonical_sha: str,
        canonical: object,
        calc_dir: Path,
        evidence_fingerprint: str,
        match_key: str = "",
    ) -> None:
        self._analysis_memo_by_sha[canonical_sha] = canonical
        self._analysis_index[(run_ulid, object_type.lower(), match_key)] = {
            "canonical_sha": canonical_sha,
            "calc_dir": str(calc_dir),
            "evidence_fingerprint": evidence_fingerprint,
        }

    def _get_memoized_canonical_bundle(
        self,
        run_ulid: str,
        object_type: str,
        match_key: str = "",
    ) -> object | None:
        from qmatsuite.core.analysis.base import AnalysisObjectMeta, check_staleness

        index_entry = self._analysis_index.get((run_ulid, object_type.lower(), match_key))
        if not index_entry:
            return None

        canonical_sha = str(index_entry.get("canonical_sha", ""))
        bundle = self._analysis_memo_by_sha.get(canonical_sha)
        if bundle is None or not hasattr(bundle, "provenance_meta"):
            return None

        provenance_meta = bundle.provenance_meta
        meta = AnalysisObjectMeta(
            schema_version=provenance_meta.schema_version,
            object_type=provenance_meta.object_type,
            created_at="",
            source_files=list(provenance_meta.source_files),
            run_ulid=provenance_meta.run_ulid,
            calc_ulid=provenance_meta.calc_ulid,
            step_ulids=list(provenance_meta.step_ulids),
            gen_steps=list(provenance_meta.gen_steps),
            engine_name=provenance_meta.engine_name,
            parser_name=provenance_meta.parser_name,
            parser_version=provenance_meta.parser_version,
            warnings=list(provenance_meta.warnings),
            manifest_snapshot=provenance_meta.manifest_snapshot,
        )
        calc_dir = Path(str(index_entry.get("calc_dir", "")))
        if check_staleness(meta, calc_dir=calc_dir):
            self._analysis_index.pop((run_ulid, object_type.lower(), match_key), None)
            return None
        return bundle

    def _persist_step_digest_rows(self, calculation: object, run_result: object) -> None:
        import json
        import logging
        from pathlib import Path as _Path

        from qmatsuite.parsers.registry import get_parser
        from qmatsuite.provenance import CAS, record_run_step
        from qmatsuite.workflow.step_type_convert import prefix_from

        logger = logging.getLogger(__name__)
        run_ulid = getattr(run_result, "run_ulid", None)
        if not run_ulid:
            return

        cas = CAS(self.project_root)
        for step_index, summary in enumerate(getattr(run_result, "steps", [])):
            status = getattr(summary, "status", None)
            status_value = status.value if hasattr(status, "value") else str(status or "pending")

            digest_sha = None
            try:
                step_type_spec = getattr(summary, "step_type_spec", "") or ""
                step_engine = getattr(calculation, "engine_family", "") or ""
                if step_type_spec and "_" in step_type_spec:
                    step_engine = prefix_from(step_type_spec)

                parser_cls = get_parser(step_engine, "scf_digest") if step_engine else None
                if parser_cls is not None:
                    parser = parser_cls()
                    raw_dir = _Path(getattr(summary, "working_dir"))
                    if not hasattr(parser, "can_parse") or parser.can_parse(raw_dir):
                        digest_obj = parser.parse(raw_dir)
                        if hasattr(digest_obj, "to_dict"):
                            digest_payload = digest_obj.to_dict()
                        elif isinstance(digest_obj, dict):
                            digest_payload = digest_obj
                        else:
                            digest_payload = {"value": str(digest_obj)}

                        payload = {
                            "engine": step_engine,
                            "step_ulid": getattr(summary, "step_ulid", ""),
                            "digest": digest_payload,
                        }
                        digest_blob = json.dumps(
                            payload,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                        digest_sha = cas.store(digest_blob, tier=1)
            except Exception as exc:
                logger.warning("Step digest parsing failed (non-fatal): %s", exc)

            record_run_step(
                project_root=self.project_root,
                run_ulid=run_ulid,
                step_ulid=getattr(summary, "step_ulid", ""),
                step_index=step_index,
                status=status_value,
                digest_sha=digest_sha,
            )

    def _build_ordered_gen_steps_for_result(self, run_result: object) -> list[tuple[str, str, Path]]:
        ordered_steps: list[tuple[str, str, Path]] = []
        for summary in getattr(run_result, "steps", []):
            status = getattr(summary, "status", None)
            status_value = status.value if hasattr(status, "value") else str(status or "")
            if status_value not in {"success", "skipped"}:
                continue
            step_ulid = getattr(summary, "step_ulid", "")
            step_type_spec = getattr(summary, "step_type_spec", "") or ""
            if not step_ulid or not step_type_spec:
                continue
            gen_step = self._safe_step_type_gen(step_type_spec)
            raw_dir = Path(getattr(summary, "working_dir"))
            # Python-script engines (Psi4, PySCF, GPAW) store output in
            # step_artifacts/<ulid>/ rather than the working dir.
            step_artifacts_dir = raw_dir.parent / "step_artifacts" / step_ulid
            if step_artifacts_dir.exists() and not any(raw_dir.glob("*.out")) and not any(raw_dir.glob("*.log")):
                raw_dir = step_artifacts_dir
            ordered_steps.append((step_ulid, gen_step, raw_dir))
        return ordered_steps

    def _persist_eager_analysis_snapshots(self, calculation: object, run_result: object) -> None:
        import logging

        import qmatsuite.drivers  # noqa: F401 - ensure driver registration
        from qmatsuite.core.analysis.cas_writer import (
            write_analysis_snapshot_row,
            write_canonical_to_cas,
        )
        from qmatsuite.core.analysis.orchestrator import run_post_run_analysis
        from qmatsuite.core.driver_registry import DriverRegistry

        logger = logging.getLogger(__name__)
        run_ulid = getattr(run_result, "run_ulid", None)
        if not run_ulid:
            return

        ordered_gen_steps = self._build_ordered_gen_steps_for_result(run_result)
        if not ordered_gen_steps:
            return

        engine = getattr(calculation, "engine_family", "") or ""
        if not engine:
            first_step_spec = ""
            run_steps = list(getattr(run_result, "steps", []))
            if run_steps:
                first_step_spec = getattr(run_steps[0], "step_type_spec", "") or ""
            if first_step_spec and "_" in first_step_spec:
                from qmatsuite.workflow.step_type_convert import prefix_from

                engine = prefix_from(first_step_spec)
        if not engine:
            return

        driver = DriverRegistry.get_driver(engine)
        calc_ulid = getattr(calculation, "ulid", None)
        calc_dir = Path(getattr(calculation, "dir"))

        results = run_post_run_analysis(
            engine=engine,
            driver=driver,
            ordered_gen_steps=ordered_gen_steps,
            run_ulid=run_ulid,
            calc_ulid=calc_ulid,
            calc_dir=calc_dir,
        )

        from qmatsuite.core.analysis.capability import ResultState

        db_path = self._get_analysis_db_path()
        for row in results:
            if row.state != ResultState.OK:
                logger.info(
                    "Analysis match %s [%s]: %s%s",
                    row.object_type,
                    ",".join(row.step_ulids),
                    row.state.value,
                    f" ({row.reason.value})" if row.reason else "",
                )
                continue
            canonical = row.canonical
            object_type = str(row.object_type)
            try:
                canonical_sha = write_canonical_to_cas(canonical, self._analysis_cas_dir)
                provenance = canonical.provenance_meta
                match_key = row.match_key
                evidence_fingerprint = self._compute_evidence_fingerprint(
                    object_type=object_type,
                    step_ulids=list(provenance.step_ulids),
                    gen_steps=list(provenance.gen_steps),
                    source_files=list(provenance.source_files),
                )
                write_analysis_snapshot_row(
                    db_path=db_path,
                    run_ulid=run_ulid,
                    object_type=object_type,
                    canonical_sha=canonical_sha,
                    step_ulids=list(provenance.step_ulids),
                    gen_steps=list(provenance.gen_steps),
                    match_key=match_key,
                    evidence_fingerprint=evidence_fingerprint,
                )
                self._memoize_canonical_bundle(
                    run_ulid=run_ulid,
                    object_type=object_type,
                    canonical_sha=canonical_sha,
                    canonical=canonical,
                    calc_dir=calc_dir,
                    evidence_fingerprint=evidence_fingerprint,
                    match_key=match_key,
                )
            except Exception as exc:
                logger.warning("Analysis snapshot persistence failed (non-fatal): %s", exc)

    def _finalize_run_analysis_pipeline(self, calculation: object, run_result: object) -> None:
        import logging

        logger = logging.getLogger(__name__)
        try:
            self._persist_step_digest_rows(calculation, run_result)
        except Exception as exc:
            logger.warning("Digest persistence failed (non-fatal): %s", exc)

        status = getattr(run_result, "status", None)
        status_value = status.value if hasattr(status, "value") else str(status or "")
        if status_value != "success":
            return

        try:
            self._persist_eager_analysis_snapshots(calculation, run_result)
        except Exception as exc:
            logger.warning("Eager analysis persistence failed (non-fatal): %s", exc)

    @staticmethod
    def _find_step_evidence_dir(raw_dir: Path, step_ulid: str, gen_step: str) -> Path:
        """Resolve evidence directory for a step within a calculation raw dir.

        Priority:
        1. raw/<step_ulid>/  (exact ULID match, e.g. VASP ISOLATED)
        2. raw/step_artifacts/<step_ulid>/  (Python-script engines: Psi4, PySCF, GPAW)
        3. raw/<gen_step>_<ulid_suffix>/  (recipe-created dirs: ORCA, Gaussian)
        4. raw/  (SHARED workdir: QE, or any fallback)

        Empty directories are skipped (QE creates empty step_artifacts dirs).
        """
        # 1. Exact ULID dir
        step_raw_dir = raw_dir / step_ulid
        if step_raw_dir.exists() and any(step_raw_dir.iterdir()):
            return step_raw_dir

        # 2. step_artifacts/<ulid>
        step_artifacts_dir = raw_dir / "step_artifacts" / step_ulid
        if step_artifacts_dir.exists() and any(step_artifacts_dir.iterdir()):
            return step_artifacts_dir

        # 3. Recipe-created: <gen_step>_<ulid_suffix>/
        #    e.g. scf_JF0ZXA for ulid ...DEAGJF0ZXA (last 6 chars)
        ulid_suffix = step_ulid[-6:] if len(step_ulid) >= 6 else step_ulid
        recipe_dir = raw_dir / f"{gen_step}_{ulid_suffix}"
        if recipe_dir.exists() and recipe_dir.is_dir():
            return recipe_dir

        # 4. Fallback: shared raw dir
        return raw_dir

    def _resolve_run_analysis_context(
        self, run_ulid: str
    ) -> tuple[str, Path, str, object, list[tuple[str, str, Path]]]:
        from qmatsuite.provenance import get_run_details
        from qmatsuite.core.models import load_calculation
        from qmatsuite.core.project_utils import load_project_config
        from qmatsuite.core.resolution import make_structure_selector_resolver, require_calculation
        from qmatsuite.core.driver_registry import DriverRegistry
        from qmatsuite.calculation.naming import find_calculation_raw_dir

        run_details = get_run_details(self.project_root, run_ulid)
        if not run_details:
            from qmatsuite.api.errors import NotFoundError

            raise NotFoundError(f"Run not found: {run_ulid}")

        calc_ulid = run_details.get("calc_ulid")
        calc_resolved = require_calculation(self.project_root, calc_ulid)
        calc_dir = calc_resolved.absolute_path
        if calc_dir.name == "calculation.yaml":
            calc_dir = calc_dir.parent

        config = load_project_config(self.project_root)
        resolver = make_structure_selector_resolver(self.project_root, config=config)
        calc_model = load_calculation(
            calc_dir / "calculation.yaml",
            project_root=self.project_root,
            resolve_structure_selector=resolver,
        )

        engine = getattr(calc_model, "engine_family", "") or run_details.get("engine", "")
        if not engine and calc_model.steps:
            first_spec = calc_model.steps[0].step_type_spec or ""
            if "_" in first_spec:
                from qmatsuite.workflow.step_type_convert import prefix_from

                engine = prefix_from(first_spec)
        if not engine:
            from qmatsuite.api.errors import ValidationError

            raise ValidationError(f"Cannot resolve engine for run {run_ulid}")

        driver = DriverRegistry.get_driver(engine)
        step_type_by_ulid = {
            entry.step_ulid: (entry.step_type_spec or "")
            for entry in calc_model.steps
        }
        raw_dir = find_calculation_raw_dir(calc_dir, getattr(calc_model, "working_dir", None))

        ordered_gen_steps: list[tuple[str, str, Path]] = []
        for step_ulid in run_details.get("step_ulids", []):
            step_type_spec = step_type_by_ulid.get(step_ulid, "")
            if not step_type_spec:
                continue
            gen_step = self._safe_step_type_gen(step_type_spec)
            evidence_dir = self._find_step_evidence_dir(
                raw_dir, step_ulid, gen_step
            )
            ordered_gen_steps.append((step_ulid, gen_step, evidence_dir))

        return str(calc_ulid), calc_dir, engine, driver, ordered_gen_steps

    def _derive_canonical_for_run_object(self, run_ulid: str, object_type: str) -> object:
        from qmatsuite.core.analysis.bundles import compute_canonical_sha
        from qmatsuite.core.analysis.cas_writer import (
            write_analysis_snapshot_row,
            write_canonical_to_cas,
        )
        from qmatsuite.core.analysis.orchestrator import run_post_run_analysis

        calc_ulid, calc_dir, engine, driver, ordered_gen_steps = self._resolve_run_analysis_context(
            run_ulid
        )
        if not ordered_gen_steps:
            from qmatsuite.api.errors import NotFoundError

            raise NotFoundError(f"No run steps available for run {run_ulid}")

        # Try memoized first (no match_key = backward compat first-match)
        # We scan all memo entries for this (run_ulid, object_type) since
        # caller doesn't specify match_key.
        for memo_key, memo_val in list(self._analysis_index.items()):
            if memo_key[0] == run_ulid and memo_key[1] == object_type.lower():
                memoized = self._get_memoized_canonical_bundle(
                    run_ulid, object_type, match_key=memo_key[2]
                )
                if memoized is not None:
                    return memoized

        results = run_post_run_analysis(
            engine=engine,
            driver=driver,
            ordered_gen_steps=ordered_gen_steps,
            run_ulid=run_ulid,
            calc_ulid=calc_ulid,
            calc_dir=calc_dir,
        )

        from qmatsuite.core.analysis.capability import ResultState

        selected = None
        for row in results:
            if row.state == ResultState.OK and row.object_type.lower() == object_type.lower():
                selected = row
                break
        if selected is None:
            from qmatsuite.api.errors import NotFoundError

            raise NotFoundError(
                f"Analysis object '{object_type}' not available for run {run_ulid}"
            )

        canonical = selected.canonical
        canonical_sha = compute_canonical_sha(canonical)
        provenance = canonical.provenance_meta
        match_key = selected.match_key
        evidence_fingerprint = self._compute_evidence_fingerprint(
            object_type=object_type,
            step_ulids=list(provenance.step_ulids),
            gen_steps=list(provenance.gen_steps),
            source_files=list(provenance.source_files),
        )

        # Operational path derives from raw evidence for correctness; persistence is
        # best-effort side effect for replay/audit linkage.
        write_canonical_to_cas(canonical, self._analysis_cas_dir)
        write_analysis_snapshot_row(
            db_path=self._get_analysis_db_path(),
            run_ulid=run_ulid,
            object_type=object_type,
            canonical_sha=canonical_sha,
            step_ulids=list(provenance.step_ulids),
            gen_steps=list(provenance.gen_steps),
            match_key=match_key,
            evidence_fingerprint=evidence_fingerprint,
        )
        self._memoize_canonical_bundle(
            run_ulid=run_ulid,
            object_type=object_type,
            canonical_sha=canonical_sha,
            canonical=canonical,
            calc_dir=calc_dir,
            evidence_fingerprint=evidence_fingerprint,
            match_key=match_key,
        )
        return canonical

    def _load_snapshot_bundle(self, run_ulid: str, object_type: str) -> tuple[str, object]:
        import gzip
        import json
        import sqlite3

        from qmatsuite.core.analysis.bundles import CanonicalPrimitiveBundle

        conn = sqlite3.connect(str(self._get_analysis_db_path()))
        try:
            row = conn.execute(
                """
                SELECT canonical_sha
                FROM analysis_snapshots
                WHERE run_ulid = ? AND object_type = ?
                """,
                (run_ulid, object_type),
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            from qmatsuite.api.errors import NotFoundError

            raise NotFoundError(
                f"No snapshot found for run={run_ulid}, object_type={object_type}"
            )

        canonical_sha = row[0]
        blob_path = self._analysis_cas_dir / f"{canonical_sha}.json.gz"
        if not blob_path.exists():
            from qmatsuite.api.errors import NotFoundError

            raise NotFoundError(
                f"Snapshot blob missing for sha={canonical_sha} (run={run_ulid}, object_type={object_type})"
            )

        with gzip.open(blob_path, "rb") as handle:
            payload = json.loads(handle.read().decode("utf-8"))
        return canonical_sha, CanonicalPrimitiveBundle.from_dict(payload)
    
    # Analysis domain (PR3)
    class Analysis:
        """Analysis capabilities."""
        
        def __init__(self, service: QMSService):
            self._service = service

        def list_step_artifacts(
            self,
            calculation_selector: str,
            step_selector: str,
        ) -> dict:
            """
            List artifact files (output files) for a step.

            Returns a list of artifact entries with metadata, including which one is the
            default candidate for display. Only returns files under the calculation's raw/
            directory (no directory traversal allowed).

            Args:
                calculation_selector: Calculation selector
                step_selector: Step selector (ULID from calculation.yaml)

            Returns:
                Dict with:
                    raw_dir: str - Path to raw directory (relative to project root)
                    artifacts: List[Dict] - Artifact entries with:
                        path_relative_to_raw: str
                        kind: str - File type ("out", "in", "dat", etc.)
                        size_bytes: int
                        mtime: float - Modification time (Unix timestamp)
                        is_default_candidate: bool
            """
            try:
                from qmatsuite.calculation.naming import find_calculation_raw_dir, CalculationFileNaming
                from qmatsuite.core.resolution import require_calculation, require_step
                from qmatsuite.calculation.structure_steps import StructureStepSpec
                from qmatsuite.workflow.registry import normalize_step_type_to_gen
                from qmatsuite.calculation.step_artifacts import get_step_artifacts, get_default_artifact

                project_root = self._service.project_root
                calculation = require_calculation(project_root, calculation_selector)
                calculation_dir = calculation.absolute_path
                if calculation_dir.name == "calculation.yaml":
                    calculation_dir = calculation_dir.parent

                # Resolve step to get step_type
                step = require_step(project_root, calculation_selector, step_selector)

                # Get step_type_spec and parameters from step spec
                spec = None
                step_params = {}
                step_type_spec = None
                try:
                    spec = StructureStepSpec.from_yaml(step.absolute_path, resolve_structure_selector=None)
                    step_type_spec = spec.step_type_spec
                    step_params = spec.parameters or {}
                except Exception:
                    # Fallback: try to get from calculation.yaml step entry
                    from qmatsuite.core.models import load_calculation
                    from qmatsuite.core.project_utils import load_project_config
                    from qmatsuite.core.resolution import make_structure_selector_resolver
                    config = load_project_config(project_root)
                    resolver = make_structure_selector_resolver(project_root, config=config)
                    calc_yaml_path = calculation_dir / "calculation.yaml"
                    wf_model = load_calculation(calc_yaml_path, project_root=project_root, resolve_structure_selector=resolver)
                    step_entry = next((e for e in wf_model.steps if e.step_ulid == step_selector), None)
                    step_type_spec = step_entry.step_type_spec if step_entry and step_entry.step_type_spec else None
                    if step_entry and hasattr(step_entry, 'parameters'):
                        step_params = step_entry.parameters or {}

                # Get raw directory
                raw_dir = find_calculation_raw_dir(calculation_dir)

                if not step_type_spec or not raw_dir.exists():
                    raw_dir_rel = raw_dir.relative_to(project_root) if raw_dir.is_relative_to(project_root) else str(raw_dir)
                    return {"raw_dir": str(raw_dir_rel), "artifacts": []}

                # Use gen type for filenames
                gen_step_type = normalize_step_type_to_gen(step_type_spec)
                output_ext = CalculationFileNaming.output_extension(gen_step_type)
                step_type_lower = gen_step_type.lower()

                # Get step-specific artifacts
                step_artifacts = get_step_artifacts(step_type_lower, step_params, raw_dir)
                artifacts_dict = {}

                for file_path in raw_dir.iterdir():
                    if file_path.is_dir():
                        continue
                    try:
                        file_path_resolved = file_path.resolve()
                        if not file_path_resolved.is_relative_to(raw_dir.resolve()):
                            continue
                    except (ValueError, RuntimeError):
                        continue

                    file_name = file_path.name
                    is_step_artifact = file_name in step_artifacts
                    stdout_file = f"{step_type_lower}.out"
                    stderr_file = f"{step_type_lower}.err"
                    is_stdout = file_name == stdout_file or (file_name.startswith(f"{step_type_lower}-") and file_name.endswith(".out"))
                    is_stderr = file_name == stderr_file or (file_name.startswith(f"{step_type_lower}-") and file_name.endswith(".err"))

                    is_legacy_match = False
                    if file_name == f"{step_type_lower}{output_ext}":
                        is_legacy_match = True
                    elif file_name.startswith(f"{step_type_lower}-") and file_name.endswith(output_ext):
                        middle = file_name[len(f"{step_type_lower}-"):-len(output_ext)]
                        try:
                            int(middle)
                            is_legacy_match = True
                        except ValueError:
                            pass
                    elif file_name.endswith(output_ext) and output_ext != ".out":
                        is_legacy_match = True

                    if not (is_step_artifact or is_stdout or is_stderr or is_legacy_match):
                        continue

                    try:
                        stat = file_path.stat()
                        size_bytes = stat.st_size
                        mtime = stat.st_mtime
                    except OSError:
                        continue

                    if file_name.endswith(".out"):
                        kind = "out"
                    elif file_name.endswith(".err"):
                        kind = "err"
                    elif file_name.endswith(".in"):
                        kind = "in"
                    elif file_name.endswith(".wout"):
                        kind = "wout"
                    elif file_name.endswith(".nnkp"):
                        kind = "nnkp"
                    elif file_name.endswith((".amn", ".mmn", ".eig")):
                        kind = file_name.split(".")[-1]
                    elif file_name.endswith((".gnu", ".dat", ".rap")):
                        kind = file_name.split(".")[-1] if "." in file_name else "unknown"
                    else:
                        suffix = file_path.suffix.lstrip(".")
                        kind = suffix if suffix else "unknown"

                    artifacts_dict[file_name] = {
                        "path_relative_to_raw": file_name,
                        "kind": kind,
                        "size_bytes": size_bytes,
                        "mtime": mtime,
                        "is_default_candidate": False,
                    }

                artifacts = list(artifacts_dict.values())
                artifact_names = [a["path_relative_to_raw"] for a in artifacts]
                default_artifact_name = get_default_artifact(step_type_lower, step_params, raw_dir, artifact_names)

                for artifact in artifacts:
                    if artifact["path_relative_to_raw"] == default_artifact_name:
                        artifact["is_default_candidate"] = True
                        break
                else:
                    exact_name = f"{step_type_lower}{output_ext}"
                    for artifact in artifacts:
                        if artifact["path_relative_to_raw"] == exact_name:
                            artifact["is_default_candidate"] = True
                            break
                    else:
                        if artifacts:
                            artifacts[0]["is_default_candidate"] = True

                raw_dir_rel = raw_dir.relative_to(project_root) if raw_dir.is_relative_to(project_root) else str(raw_dir)
                return {"raw_dir": str(raw_dir_rel), "artifacts": artifacts}
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def read_step_artifact_text(
            self,
            calculation_selector: str,
            step_selector: str,
            artifact_path: str,
            head_lines: int | None = None,
            tail_lines: int | None = None,
        ) -> dict:
            """
            Read text content from a step artifact file.

            Security: Only allows reading files under <calculation_dir>/raw/.
            Rejects directory traversal attempts and directories.

            Args:
                calculation_selector: Calculation selector
                step_selector: Step selector (ULID from calculation.yaml)
                artifact_path: Path relative to raw directory (e.g., "scf.out")
                head_lines: Optional number of lines to read from start
                tail_lines: Optional number of lines to read from end

            Returns:
                Dict with:
                    content: str - File content (possibly truncated)
                    truncated: bool - True if content was truncated
                    total_bytes: int - Total file size in bytes
                    resolved_path: str - Resolved file path (for logging)
            """
            try:
                from qmatsuite.calculation.naming import find_calculation_raw_dir
                from qmatsuite.core.resolution import require_calculation, require_step
                from qmatsuite.api.errors import ValidationError, NotFoundError

                project_root = self._service.project_root
                calculation = require_calculation(project_root, calculation_selector)
                calculation_dir = calculation.absolute_path
                if calculation_dir.name == "calculation.yaml":
                    calculation_dir = calculation_dir.parent

                # Verify step exists
                require_step(project_root, calculation_selector, step_selector)

                # Get raw directory
                raw_dir = find_calculation_raw_dir(calculation_dir)
                raw_dir_resolved = raw_dir.resolve()

                # Security: Check for path traversal
                artifact_path_obj = Path(artifact_path)
                if artifact_path_obj.is_absolute():
                    raise ValidationError(f"Security violation: artifact path '{artifact_path}' is an absolute path")
                if ".." in str(artifact_path):
                    raise ValidationError(f"Security violation: artifact path '{artifact_path}' contains path traversal attempt")

                # Use relative path (security ensured by is_relative_to check below)
                file_path = raw_dir_resolved / str(artifact_path_obj)

                # Security: Ensure resolved path is under raw_dir
                try:
                    file_path_resolved = file_path.resolve()
                    if not file_path_resolved.is_relative_to(raw_dir_resolved):
                        raise ValidationError(f"Security violation: artifact path '{artifact_path}' resolves outside raw directory")
                except (ValueError, RuntimeError) as e:
                    raise ValidationError(f"Invalid artifact path: {artifact_path}") from e

                if file_path_resolved.is_dir():
                    raise ValidationError(f"Artifact path '{artifact_path}' is a directory, not a file")

                if not file_path_resolved.exists():
                    raise NotFoundError(f"Artifact file not found: {artifact_path}")

                try:
                    total_bytes = file_path_resolved.stat().st_size
                except OSError as e:
                    from qmatsuite.api.errors import EngineError
                    raise EngineError(f"Failed to read file stats: {e}") from e

                # Read file content
                try:
                    if head_lines is None and tail_lines is None:
                        content = file_path_resolved.read_text(encoding='utf-8', errors='replace')
                        truncated = False
                    elif head_lines is not None and tail_lines is not None:
                        lines = file_path_resolved.read_text(encoding='utf-8', errors='replace').splitlines(keepends=True)
                        total_lines = len(lines)
                        if total_lines <= head_lines + tail_lines:
                            content = ''.join(lines)
                            truncated = False
                        else:
                            head = ''.join(lines[:head_lines])
                            tail = ''.join(lines[-tail_lines:])
                            content = head + f"\n... [truncated {total_lines - head_lines - tail_lines} lines] ...\n" + tail
                            truncated = True
                    elif head_lines is not None:
                        lines = file_path_resolved.read_text(encoding='utf-8', errors='replace').splitlines(keepends=True)
                        total_lines = len(lines)
                        if total_lines <= head_lines:
                            content = ''.join(lines)
                            truncated = False
                        else:
                            content = ''.join(lines[:head_lines]) + f"\n... [truncated {total_lines - head_lines} lines] ...\n"
                            truncated = True
                    else:  # tail_lines is not None
                        lines = file_path_resolved.read_text(encoding='utf-8', errors='replace').splitlines(keepends=True)
                        total_lines = len(lines)
                        if total_lines <= tail_lines:
                            content = ''.join(lines)
                            truncated = False
                        else:
                            content = f"... [truncated {total_lines - tail_lines} lines] ...\n" + ''.join(lines[-tail_lines:])
                            truncated = True
                except OSError as e:
                    from qmatsuite.api.errors import EngineError
                    raise EngineError(f"Failed to read file: {e}") from e
                except UnicodeDecodeError as e:
                    raise ValidationError(f"File contains binary data and cannot be read as text: {artifact_path}") from e

                return {
                    "content": content,
                    "truncated": truncated,
                    "total_bytes": total_bytes,
                    "resolved_path": str(file_path_resolved),
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def analyze_scf(
            self,
            scf_file: Path,
            plot: bool = False,
            output_dir: Path | None = None,
            plot_format: str = "png",
        ) -> dict:
            """
            Analyze SCF output file for energies and convergence.

            Args:
                scf_file: Path to SCF output file (.out)
                plot: If True, generate convergence plot
                output_dir: Directory for output files (None for auto-detect)
                plot_format: Plot format (png, svg, pdf)

            Returns:
                Dict with SCF analysis results
            """
            try:
                from qmatsuite.analysis.parsers import parse_scf_output
                from qmatsuite.analysis.plotting import plot_scf_convergence, save_figure

                project_root = self._service.project_root
                scf_file = Path(scf_file).resolve()
                if not scf_file.exists():
                    from qmatsuite.api.errors import NotFoundError
                    raise NotFoundError(f"SCF output file not found: {scf_file}")

                # Parse SCF output
                result = parse_scf_output(scf_file)
                data = result.to_dict()

                # Determine output directory
                local_output_dir = output_dir
                if local_output_dir is None and project_root:
                    from qmatsuite.calculation.naming import find_calculation_results_dir
                    # Try to detect calculation context from file location
                    try:
                        # If file is in a calculation/raw/ directory, use calculation/results/
                        if scf_file.parent.name == "raw":
                            calc_dir = scf_file.parent.parent
                            local_output_dir = find_calculation_results_dir(calc_dir)
                    except Exception:
                        pass

                # Generate plot if requested
                plot_path = None
                if plot and result.iterations:
                    fig, ax = plot_scf_convergence(result)
                    if local_output_dir:
                        local_output_dir = Path(local_output_dir)
                        local_output_dir.mkdir(parents=True, exist_ok=True)
                        plot_path = local_output_dir / f"scf_convergence.{plot_format}"
                        save_figure(fig, plot_path)

                return {
                    "data": data,
                    "plot_path": str(plot_path) if plot_path else None,
                    "converged": result.converged,
                    "total_energy_ry": result.total_energy,
                    "fermi_energy_ev": result.fermi_energy,
                    "n_iterations": len(result.iterations),
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def list_raw_files(
            self,
            calculation_selector: str,
            step_selector: str,
        ) -> dict:
            """
            Surface A wrapper: list raw text artifacts for a step.
            """
            from qmatsuite.calculation.naming import find_calculation_raw_dir
            from qmatsuite.core.resolution import require_calculation, require_step

            calculation = require_calculation(self._service.project_root, calculation_selector)
            require_step(self._service.project_root, calculation_selector, step_selector)

            if calculation.absolute_path.name == "calculation.yaml":
                calculation_dir = calculation.absolute_path.parent
            else:
                calculation_dir = calculation.absolute_path

            raw_dir = find_calculation_raw_dir(calculation_dir)
            if not raw_dir.exists():
                from qmatsuite.api.errors import NotFoundError

                raise NotFoundError(f"Raw directory not found: {raw_dir}")

            entries: list[dict] = []
            for file_path in sorted(raw_dir.rglob("*")):
                if not file_path.is_file():
                    continue
                try:
                    # Avoid binary blobs in text viewer lists.
                    with file_path.open("rb") as handle:
                        head = handle.read(2048)
                    if b"\x00" in head:
                        continue
                except OSError:
                    continue

                stat = file_path.stat()
                rel = str(file_path.relative_to(raw_dir))
                suffix = file_path.suffix.lstrip(".").lower() or "file"
                name_lower = file_path.name.lower()
                rank = 3
                if name_lower.endswith((".out", ".stdout", ".log")):
                    rank = 0
                elif ".out" in name_lower:
                    rank = 1
                elif name_lower.endswith((".txt", ".gnu", ".dat")):
                    rank = 2
                entries.append(
                    {
                        "path_relative_to_raw": rel,
                        "kind": suffix,
                        "size_bytes": int(stat.st_size),
                        "mtime": float(stat.st_mtime),
                        "_rank": rank,
                    }
                )

            entries.sort(key=lambda row: (row["_rank"], -row["mtime"], row["path_relative_to_raw"]))
            artifacts = []
            for idx, row in enumerate(entries):
                artifacts.append(
                    {
                        "path_relative_to_raw": row["path_relative_to_raw"],
                        "kind": row["kind"],
                        "size_bytes": row["size_bytes"],
                        "mtime": row["mtime"],
                        "is_default_candidate": idx == 0,
                    }
                )

            return {
                "raw_dir": str(raw_dir.relative_to(self._service.project_root)),
                "files": [artifact["path_relative_to_raw"] for artifact in artifacts],
                "artifacts": artifacts,
            }

        def get_step_digest(self, run_ulid: str, step_ulid: str) -> dict:
            """
            Surface B: return post-run digest payload for one step.
            """
            import json
            import sqlite3

            from qmatsuite.provenance import CAS

            conn = sqlite3.connect(str(self._service._get_analysis_db_path()))
            try:
                row = conn.execute(
                    """
                    SELECT digest_sha
                    FROM run_steps
                    WHERE run_ulid = ? AND step_ulid = ?
                    """,
                    (run_ulid, step_ulid),
                ).fetchone()
            finally:
                conn.close()

            if row is None:
                from qmatsuite.api.errors import NotFoundError

                raise NotFoundError(
                    f"Run step not found for digest lookup: run={run_ulid}, step={step_ulid}"
                )

            digest_sha = row[0]
            if not digest_sha:
                return {"available": False, "digest_sha": None, "digest": None}

            cas = CAS(self._service.project_root)
            payload = json.loads(cas.retrieve(digest_sha).decode("utf-8"))
            digest = payload.get("digest", payload)
            return {
                "available": True,
                "digest_sha": digest_sha,
                "engine": payload.get("engine"),
                "digest": digest,
            }

        def get_analysis(
            self,
            run_ulid: str,
            object_type: str,
            transforms: list[str] | None = None,
        ) -> dict:
            """
            Surface C operational path: derive from present raw evidence.
            """
            from qmatsuite.api.errors import ValidationError
            from qmatsuite.core.analysis.bundles import compute_canonical_sha
            from qmatsuite.core.analysis.transforms.fermi_shift import FermiShift

            canonical = self._service._derive_canonical_for_run_object(run_ulid, object_type)
            canonical_sha = compute_canonical_sha(canonical)

            bundle = canonical
            for transform_name in transforms or []:
                normalized = transform_name.strip().lower()
                if normalized in {"fermishift", "fermi_shift", "fermi-shift"}:
                    bundle = FermiShift().apply(bundle)
                    continue
                raise ValidationError(f"Unknown transform: {transform_name}")

            return {
                "run_ulid": run_ulid,
                "object_type": object_type,
                "canonical_sha": canonical_sha,
                "bundle": bundle.to_dict(),
            }

        def get_analysis_snapshot(self, run_ulid: str, object_type: str) -> dict:
            """
            Explicit replay endpoint: reads SQLite linkage + CAS blob.
            """
            canonical_sha, bundle = self._service._load_snapshot_bundle(run_ulid, object_type)
            return {
                "run_ulid": run_ulid,
                "object_type": object_type,
                "canonical_sha": canonical_sha,
                "bundle": bundle.to_dict(),
            }

        def get_analysis_instances_for_step(
            self,
            calc_selector: str,
            step_ulid: str,
        ) -> dict:
            """
            Domain B step-scoped enumeration (spec §5.3-B).

            Returns all analysis instances whose matched step_ulids include the
            given step_ulid. Best-effort: attempts parse if evidence exists.
            """
            import logging

            from qmatsuite.core.analysis.capability import (
                ResultState,
                enumerate_all_matches,
            )
            from qmatsuite.core.analysis.orchestrator import run_post_run_analysis
            from qmatsuite.core.driver_registry import DriverRegistry
            from qmatsuite.core.models import load_calculation
            from qmatsuite.core.project_utils import load_project_config
            from qmatsuite.core.resolution import (
                make_structure_selector_resolver,
                require_calculation,
            )

            import qmatsuite.drivers  # noqa: F401

            logger = logging.getLogger(__name__)
            project_root = self._service.project_root

            calc_resolved = require_calculation(project_root, calc_selector)
            calc_dir = calc_resolved.absolute_path
            if calc_dir.name == "calculation.yaml":
                calc_dir = calc_dir.parent

            config = load_project_config(project_root)
            resolver = make_structure_selector_resolver(project_root, config=config)
            calc_model = load_calculation(
                calc_dir / "calculation.yaml",
                project_root=project_root,
                resolve_structure_selector=resolver,
            )

            engine = getattr(calc_model, "engine_family", "") or ""
            if not engine and calc_model.steps:
                first_spec = calc_model.steps[0].step_type_spec or ""
                if "_" in first_spec:
                    from qmatsuite.workflow.step_type_convert import prefix_from
                    engine = prefix_from(first_spec)
            if not engine:
                return {"instances": []}

            driver = DriverRegistry.get_driver(engine)
            capabilities = getattr(driver, "ANALYSIS_CAPABILITIES", []) or []

            # Build ordered gen_steps from ALL calculation steps (Domain B)
            ordered_gen_steps: list[tuple[str, str]] = []
            for step_entry in calc_model.steps:
                s_ulid = step_entry.step_ulid or ""
                s_spec = step_entry.step_type_spec or ""
                if not s_ulid or not s_spec:
                    continue
                gen_step = self._service._safe_step_type_gen(s_spec)
                from pathlib import Path as _Path
                from qmatsuite.calculation.naming import find_calculation_raw_dir
                raw_dir = find_calculation_raw_dir(
                    calc_dir, getattr(calc_model, "working_dir", None)
                )
                evidence_dir = QMSService._find_step_evidence_dir(
                    raw_dir, s_ulid, gen_step
                )
                ordered_gen_steps.append((s_ulid, gen_step, evidence_dir))

            matches = enumerate_all_matches(capabilities, ordered_gen_steps)
            # Filter to instances containing the selected step_ulid
            relevant = [m for m in matches if step_ulid in m.step_ulids]

            instances = []
            for match in relevant:
                entry = {
                    "object_type": match.object_type,
                    "step_ulids": match.step_ulids,
                    "gen_steps": match.gen_steps,
                    "state": ResultState.MISSING_EVIDENCE.value,
                    "bundle": None,
                }
                # Best-effort parse
                try:
                    from qmatsuite.parsers.registry import get_parser
                    provider_cls = get_parser(engine, match.object_type)
                    if provider_cls is not None:
                        provider = provider_cls()
                        primary_raw_dir = match.evidence_dirs[0]
                        if not hasattr(provider, "can_parse") or provider.can_parse(primary_raw_dir):
                            from qmatsuite.core.analysis.evidence import EvidenceBundle
                            evidence = EvidenceBundle(
                                primary_raw_dir=primary_raw_dir,
                                calc_dir=calc_dir,
                                run_ulid=None,
                                calc_ulid=None,
                                step_ulids=match.step_ulids,
                                gen_steps=match.gen_steps,
                                engine_name=engine,
                                evidence_steps=[],
                            )
                            obj = provider.parse(evidence)
                            canonical = obj.to_primitives()
                            entry["state"] = ResultState.OK.value
                            entry["bundle"] = canonical.to_dict()
                except Exception as exc:
                    logger.debug("Domain B parse attempt failed (non-fatal): %s", exc)
                    entry["state"] = ResultState.PARSER_ERROR.value

                instances.append(entry)

            return {"instances": instances}

        def get_field3d_grid(self, run_ulid: str) -> dict:
            """Materialize full Field3D grid data to .scratch/ for frontend consumption."""
            import json
            import os

            from qmatsuite.core.analysis.field3d import Field3D
            from qmatsuite.core.analysis.orchestrator import run_post_run_analysis

            calc_ulid, calc_dir, engine, driver, ordered_gen_steps = (
                self._service._resolve_run_analysis_context(run_ulid)
            )
            if not ordered_gen_steps:
                from qmatsuite.api.errors import NotFoundError

                raise NotFoundError(f"No run steps available for run {run_ulid}")

            results = run_post_run_analysis(
                engine=engine,
                driver=driver,
                ordered_gen_steps=ordered_gen_steps,
                run_ulid=run_ulid,
                calc_ulid=calc_ulid,
                calc_dir=calc_dir,
            )

            from qmatsuite.core.analysis.capability import ResultState

            field3d_obj = None
            for row in results:
                if row.state == ResultState.OK and row.object_type.lower() == "field3d":
                    field3d_obj = row.analysis_object
                    break

            if field3d_obj is None or not isinstance(field3d_obj, Field3D):
                from qmatsuite.api.errors import NotFoundError

                raise NotFoundError(
                    f"Field3D analysis object not available for run {run_ulid}"
                )

            # Materialize to .scratch/ (I/O stays in API layer, not analysis core)
            scratch_dir = calc_dir / ".scratch" / "field3d"
            scratch_dir.mkdir(parents=True, exist_ok=True)

            tmp_f32 = scratch_dir / "active.f32.tmp"
            final_f32 = scratch_dir / "active.f32"
            field3d_obj.get_grid_as_float32().tofile(str(tmp_f32))
            os.rename(str(tmp_f32), str(final_f32))

            metadata = field3d_obj.get_scratch_metadata()

            tmp_json = scratch_dir / "active.json.tmp"
            final_json = scratch_dir / "active.json"
            with open(str(tmp_json), "w") as f:
                json.dump(metadata, f)
            os.rename(str(tmp_json), str(final_json))

            return {"calc_dir": str(calc_dir), **metadata}

        def get_reference_analysis(
            self,
            calculation_selector: str,
            analysis_type: str,
        ) -> dict | None:
            """
            Get reference analysis data for demo projects.

            If the project was created from a demo snapshot and has a reference
            pack, this returns the pre-computed analysis data for comparison.

            Uses the demo_source field in project settings (S11) to locate
            ref packs at qmatsuite/resources/demo_projects/ref_packs/<demo_id>/.

            Args:
                calculation_selector: Calculation selector
                analysis_type: Type of analysis ("scf", "dos", "bands", "convergence")

            Returns:
                Dict with reference analysis data, or None if not a demo project
                or no ref pack available
            """
            try:
                from qmatsuite.core.project_utils import load_project_config

                project_root = self._service.project_root
                config = load_project_config(project_root)

                # Strategy 1: Check project-level demo_source (S11)
                demo_id = None
                project_settings = config.get("project", {}).get("settings", {})
                demo_source = project_settings.get("demo_source")
                if demo_source:
                    demo_id = demo_source.get("demo_id")

                # Strategy 2: Check per-calculation demo_origin
                if not demo_id:
                    from qmatsuite.core.models import load_calculation
                    from qmatsuite.core.resolution import resolve_calculation

                    try:
                        resolved = resolve_calculation(
                            project_root, calculation_selector, config=config,
                        )
                        calc_path = resolved.absolute_path
                        if calc_path.name == "calculation.yaml":
                            calc_model = load_calculation(calc_path, project_root=project_root)
                        else:
                            calc_model = load_calculation(calc_path / "calculation.yaml", project_root=project_root)
                        if calc_model.demo_origin:
                            demo_id = calc_model.demo_origin.get("demo_id")
                    except Exception:
                        pass

                if not demo_id:
                    return None

                # Load ref pack via ref_packs module
                from qmatsuite.demo_store.ref_packs import load_ref_pack

                bundle_data = load_ref_pack(demo_id, analysis_type)
                if bundle_data is None:
                    return None

                # Wrap in AnalysisResponse shape so frontend can render directly
                return {
                    "run_ulid": "REFERENCE",
                    "object_type": analysis_type,
                    "canonical_sha": "reference",
                    "bundle": bundle_data,
                    "_is_reference": True,
                    "_reference_source": demo_id,
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        # NOTE: find_band_files REMOVED - use qmatsuite.calculation.naming.find_band_analysis_files directly

        def get_relax_final_structure_preview(
            self,
            calc_selector: str,
            step_selector: str,
            *,
            index: Any = None,
            config: dict | None = None,
        ) -> dict:
            """
            Preview final structure from relax/vc-relax step output (NO SIDE EFFECTS).

            Parses QE output file to extract final coordinates block.
            Does NOT create any Structure resource.

            Args:
                calc_selector: Calculation selector
                step_selector: Step selector (ULID)
                index: Optional ResourceIndex
                config: Optional project config

            Returns:
                Dict with cell, species, positions, volume
            """
            try:
                from qmatsuite.calculation.geometry import (
                    read_final_geometry_from_output_text,
                    structure_from_qe_geometry_snapshot,
                )
                from qmatsuite.calculation.naming import CalculationFileNaming, find_calculation_raw_dir
                from qmatsuite.core.models import load_calculation
                from qmatsuite.core.project_utils import load_project_config
                from qmatsuite.core.resolution import resolve_calculation, resolve_step
                from qmatsuite.calculation.structure_steps import StructureStepSpec
                from qmatsuite.api.errors import ValidationError

                if config is None:
                    config = load_project_config(self._service.project_root)

                # Resolve calculation and step
                calculation_resolved = resolve_calculation(
                    self._service.project_root, calc_selector, config=config, index=index
                )
                calculation_dir = (
                    calculation_resolved.absolute_path.parent
                    if calculation_resolved.absolute_path.name == "calculation.yaml"
                    else calculation_resolved.absolute_path
                )

                # Load calculation to get working_dir
                wf_model = load_calculation(
                    calculation_dir / "calculation.yaml", project_root=self._service.project_root
                )
                working_dir_name = wf_model.working_dir
                raw_dir = find_calculation_raw_dir(calculation_dir, working_dir_name)

                # Resolve step
                step_resolved = resolve_step(
                    self._service.project_root, calc_selector, step_selector, config=config, index=index
                )
                spec = StructureStepSpec.from_yaml(step_resolved.absolute_path, resolve_structure_selector=None)
                step_type_spec = spec.step_type_spec

                # Validate step type (convert to GEN type for comparison)
                from qmatsuite.api import get_step_type_gen
                step_gen = get_step_type_gen(step_type_spec)
                if step_gen != "relax":
                    raise ValidationError(
                        f"Step '{step_selector}' is not a relax step (type: {step_type_spec})"
                    )

                # Find output file
                output_filename = CalculationFileNaming.output_filename(step_gen, working_dir=raw_dir)
                output_file = raw_dir / output_filename

                if not output_file.exists():
                    raise ValidationError(
                        f"Output file not found for step '{step_selector}': {output_file}. "
                        "Step may not have completed successfully."
                    )

                # Parse final geometry
                output_text = output_file.read_text()
                snapshot, species = read_final_geometry_from_output_text(output_text)
                structure = structure_from_qe_geometry_snapshot(snapshot, species)

                return {
                    "cell": structure.lattice.matrix.tolist(),
                    "species": species,
                    "positions": structure.cart_coords.tolist(),
                    "volume": structure.volume,
                    "n_atoms": len(species),
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        @staticmethod
        def list_3d_fixtures(fixture_dir: str | None = None) -> dict:
            """
            List available Wannier90 3D test fixtures (XSF/BXSF files).

            Fixture root discovery priority:
            1. ``fixture_dir`` argument (if provided)
            2. Environment variable ``QMATSUITE_WANNIER_3D_FIXTURES``
            3. Repo root derivation (tests/data/wannier_3d_test)
            4. DEV fallback ($HOME/QMatSuite/tests/data/wannier_3d_test)

            Returns dict with ``fixtures`` list.
            """
            import json
            import os
            from pathlib import Path as _Path

            attempted_paths: list[tuple[str, str]] = []
            fixtures_root = None

            # When fixture_dir is explicitly provided, use it without fallback
            if fixture_dir is not None:
                fixtures_root = _Path(fixture_dir).resolve()
                attempted_paths.append(("argument", str(fixtures_root)))
            else:
                # Auto-discovery priority chain
                env_path = os.environ.get("QMATSUITE_WANNIER_3D_FIXTURES")
                if env_path:
                    fixtures_root = _Path(env_path).resolve()
                    attempted_paths.append(("env_var", str(fixtures_root)))
                    if not (fixtures_root.exists() and fixtures_root.is_dir()):
                        fixtures_root = None

                if fixtures_root is None:
                    # service.py is at src/qmatsuite/api/service.py
                    # parents[3] = repo root (not parents[2] which is src/)
                    repo_root = _Path(__file__).resolve().parents[3]
                    fixtures_root = repo_root / "tests" / "data" / "wannier_3d_test"
                    attempted_paths.append(("repo_derived", str(fixtures_root)))
                    if not (fixtures_root.exists() and fixtures_root.is_dir()):
                        fixtures_root = None

                if fixtures_root is None:
                    dev_fallback = _Path.home() / "QMatSuite" / "tests" / "data" / "wannier_3d_test"
                    attempted_paths.append(("dev_fallback", str(dev_fallback)))
                    if dev_fallback.exists() and dev_fallback.is_dir():
                        fixtures_root = dev_fallback

            if fixtures_root is None or not fixtures_root.exists():
                attempted_str = "\n".join(f"  {source}: {path}" for source, path in attempted_paths)
                raise FileNotFoundError(
                    f"Wannier90 3D fixtures directory not found. Attempted paths:\n{attempted_str}\n"
                    "Please set QMATSUITE_WANNIER_3D_FIXTURES environment variable or ensure fixtures exist."
                )

            if not fixtures_root.is_dir():
                raise ValueError(f"Fixtures root is not a directory: {fixtures_root}")

            fixtures: list[dict] = []

            manifest_path = fixtures_root / "manifest.json"
            if manifest_path.exists():
                try:
                    manifest_data = json.loads(manifest_path.read_text())
                    for entry in manifest_data.get("fixtures", []):
                        fixture_path = fixtures_root / entry["path"]
                        if fixture_path.exists():
                            fixtures.append({
                                "ulid": entry.get("ulid", f"{fixture_path.parent.name}_{fixture_path.stem}"),
                                "label": entry.get("label", str(fixture_path.relative_to(fixtures_root))),
                                "kind": entry.get("kind", "xsf" if fixture_path.suffix == ".xsf" else "bxsf"),
                                "path": str(fixture_path.resolve()),
                            })
                except Exception:
                    fixtures = []

            if not fixtures:
                for xsf_file in sorted(fixtures_root.rglob("*.xsf")):
                    rel_path = xsf_file.relative_to(fixtures_root)
                    fixtures.append({
                        "ulid": f"{xsf_file.parent.name}_{xsf_file.stem}",
                        "label": str(rel_path),
                        "kind": "xsf",
                        "path": str(xsf_file.resolve()),
                    })
                for bxsf_file in sorted(fixtures_root.rglob("*.bxsf")):
                    rel_path = bxsf_file.relative_to(fixtures_root)
                    fixtures.append({
                        "ulid": f"{bxsf_file.parent.name}_{bxsf_file.stem}",
                        "label": str(rel_path),
                        "kind": "bxsf",
                        "path": str(bxsf_file.resolve()),
                    })

            return {"fixtures": fixtures}

        @staticmethod
        def compile_fixture_volume(
            file_path: str,
            calc_dir: str,
            band_index: int = 1,
        ) -> dict:
            """
            Compile a fixture volume file (XSF/BXSF) into blob storage.

            Args:
                file_path: Path to XSF or BXSF file
                calc_dir: Calculation directory for blob storage
                band_index: Band index for BXSF (1-based, default 1)

            Returns:
                Dict with artifact_id, kind, metadata, blob_id, preview_blob_id
            """
            from pathlib import Path as _Path
            from qmatsuite.api.utils import parse_volume_artifact

            fp = _Path(file_path).resolve()
            cd = _Path(calc_dir).resolve()

            if not fp.exists():
                raise FileNotFoundError(f"File not found: {fp}")

            file_type = fp.suffix.lower().lstrip(".")
            if not isinstance(band_index, int) or band_index < 1:
                raise ValueError(f"Invalid band_index: {band_index}. Must be >= 1 (1-based)")

            result = parse_volume_artifact(
                file_path=fp,
                calc_dir=cd,
                file_type=file_type,
                band_index=band_index,
            )

            if file_type == "bxsf" and band_index > result.get("n_bands", 0):
                raise ValueError(f"band_index {band_index} exceeds n_bands {result.get('n_bands', 0)}")

            return result

    @property
    def analysis(self) -> Analysis:
        """Access analysis capabilities."""
        return QMSService.Analysis(self)

    # Structure domain (PR4)
    class Structure:
        """Structure capabilities."""
        
        def __init__(self, service: QMSService):
            self._service = service
        
        def get(self, selector: str) -> StructureDTO:
            """
            Get structure by selector.
            
            Args:
                selector: Structure selector (ULID, slug, name, or path)
                
            Returns:
                StructureDTO (no coordinate arrays)
                
            Raises:
                APIError: If structure not found
            """
            try:
                from qmatsuite.core.resolution import require_structure
                from qmatsuite.core.models import load_structure_model
                from qmatsuite.io.structure_io import read_structure
                
                # Resolve structure
                struct_resolved = require_structure(self._service.project_root, selector)
                
                # Load structure file
                struct_path = struct_resolved.absolute_path
                if not struct_path.exists():
                    from qmatsuite.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Structure file not found: {struct_path}",
                        context={"selector": selector, "path": str(struct_path)}
                    )
                
                # Load structure model for metadata
                struct_model = load_structure_model(struct_path, self._service.project_root)
                
                # Load pymatgen structure for crystallographic data
                pmg_structure = read_structure(struct_path)
                
                # Build StructureDTO
                return structure_to_dto(
                    struct_resolved=struct_resolved,
                    struct_model=struct_model,
                    pmg_structure=pmg_structure,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def list(self, project_selector: str | None = None) -> list[StructureDTO]:
            """
            List all structures in project.
            
            Args:
                project_selector: Unused (for future multi-project support)
                
            Returns:
                List of StructureDTO
                
            Raises:
                APIError: If project invalid
            """
            try:
                from qmatsuite.core.resolution import list_structures
                from qmatsuite.core.models import load_structure_model
                from qmatsuite.io.structure_io import read_structure
                
                # List all structures
                struct_resolved_list = list_structures(self._service.project_root)
                
                results = []
                for struct_resolved in struct_resolved_list:
                    try:
                        struct_path = struct_resolved.absolute_path
                        if not struct_path.exists():
                            continue
                        
                        # Load structure model and pymatgen structure
                        struct_model = load_structure_model(struct_path, self._service.project_root)
                        pmg_structure = read_structure(struct_path)
                        
                        # Build StructureDTO
                        dto = structure_to_dto(
                            struct_resolved=struct_resolved,
                            struct_model=struct_model,
                            pmg_structure=pmg_structure,
                        )
                        results.append(dto)
                    except Exception:
                        # Skip structures that can't be loaded
                        continue
                
                return results
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def get_atoms(self, selector: str) -> dict:
            """
            Get full atomic coordinates (Jupyter-only).
            
            Args:
                selector: Structure selector
                
            Returns:
                Dict with full atomic data (positions, species, etc.)
                
            Raises:
                APIError: If structure not found
            """
            try:
                from qmatsuite.core.resolution import require_structure
                from qmatsuite.io.structure_io import read_structure
                
                # Resolve and load structure
                struct_resolved = require_structure(self._service.project_root, selector)
                struct_path = struct_resolved.absolute_path
                
                if not struct_path.exists():
                    from qmatsuite.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Structure file not found: {struct_path}",
                        context={"selector": selector}
                    )
                
                pmg_structure = read_structure(struct_path)
                
                # Extract full atomic data
                positions = pmg_structure.cart_coords.tolist()
                species = [str(site.specie) for site in pmg_structure]
                
                result = {
                    "positions": positions,
                    "species": species,
                    "num_atoms": len(pmg_structure),
                }
                
                # Add lattice if periodic
                if hasattr(pmg_structure, "lattice"):
                    result["lattice"] = pmg_structure.lattice.matrix.tolist()
                    result["lattice_abc"] = pmg_structure.lattice.abc
                    result["lattice_angles"] = pmg_structure.lattice.angles
                
                return result
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def require_ref(self, selector: str, config: dict | None = None) -> Any:
            """
            Resolve structure selector to ResolvedResource (for internal use).
            
            Args:
                selector: Structure selector (ULID, slug, name, or path)
                config: Optional project config (for backward compatibility)
                
            Returns:
                ResolvedResource (kernel type, not DTO)
                
            Raises:
                APIError: If structure not found
            """
            try:
                from qmatsuite.core.resolution import require_structure
                return require_structure(self._service.project_root, selector)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def import_file(
            self,
            source: Path | str,
            name: str | None = None,
            format: str = "auto",
            *,
            dedup_by_fingerprint: bool = False,
        ) -> StructureDTO:
            """
            Import a structure file into the project.

            Args:
                source: Path to source structure file
                name: Optional name for the structure (defaults to filename stem)
                format: File format hint ("auto" to detect)
                dedup_by_fingerprint: If True, reuse existing structure with same content fingerprint

            Returns:
                StructureDTO for the imported structure

            Raises:
                APIError: If import fails
            """
            try:
                from qmatsuite.io import read_structure as _read_structure, write_structure as _write_structure
                from qmatsuite.core.project_utils import load_project_config, save_project_config, collect_slugs
                from qmatsuite.core.resolution import require_structure
                from qmatsuite.core.models import load_structure_model
                from qmatsuite.io.structure_io import read_structure
                from qmatsuite.core.structure_fingerprint import structure_like_fingerprint, DEFAULT_FINGERPRINT_TOL_ANG
                from qmatsuite.core.structure_canonicalize import canonicalize_structure_like_in_place
                from qmatsuite.core.resources import (
                    generate_unique_name_and_slug,
                    meta_from_name,
                    ensure_relative_path,
                )
                import json

                project_root = self._service.project_root
                source_path = Path(source).resolve()
                if not source_path.exists():
                    from qmatsuite.api.errors import NotFoundError
                    raise NotFoundError(f"Source file not found: {source_path}")

                config = load_project_config(project_root)
                structures = config.setdefault("structures", [])
                existing_slugs = collect_slugs(structures, project_root=project_root)

                # Also check existing structure files for slugs
                structures_dir = project_root / "structures"
                if structures_dir.exists():
                    for struct_file in structures_dir.glob("*.json"):
                        try:
                            struct_data = json.loads(struct_file.read_text())
                            struct_meta = struct_data.get("__qms_meta__") or struct_data.get("meta") or {}
                            if struct_meta.get("slug"):
                                existing_slugs.append(struct_meta["slug"])
                        except Exception:
                            pass

                structure_name = name or source_path.stem
                final_name, final_slug = generate_unique_name_and_slug(
                    kind="structure",
                    preferred_name=structure_name,
                    existing_slugs=existing_slugs,
                )

                # Read and convert structure
                structure = _read_structure(source_path)

                # Dedup by fingerprint if requested
                if dedup_by_fingerprint:
                    canonicalize_structure_like_in_place(structure)
                    fingerprint = structure_like_fingerprint(structure, tol_ang=DEFAULT_FINGERPRINT_TOL_ANG)

                    if structures_dir.exists():
                        for struct_file in structures_dir.glob("*.json"):
                            try:
                                struct_data = json.loads(struct_file.read_text())
                                struct_meta = struct_data.get("__qms_meta__") or struct_data.get("meta") or {}
                                existing_fingerprint = struct_meta.get("fingerprint")
                                if existing_fingerprint == fingerprint:
                                    existing_id = struct_meta.get("ulid")
                                    if existing_id:
                                        # Return existing structure DTO
                                        struct_resolved = require_structure(project_root, existing_id, config=config)
                                        struct_model = load_structure_model(struct_resolved.absolute_path, project_root)
                                        pmg_structure = read_structure(struct_resolved.absolute_path)
                                        return structure_to_dto(
                                            struct_resolved=struct_resolved,
                                            struct_model=struct_model,
                                            pmg_structure=pmg_structure,
                                        )
                            except Exception:
                                pass

                if not dedup_by_fingerprint:
                    canonicalize_structure_like_in_place(structure)

                fingerprint = structure_like_fingerprint(structure, tol_ang=DEFAULT_FINGERPRINT_TOL_ANG)

                # Write to structures directory
                dest_path = project_root / "structures" / f"{final_slug}.json"
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                meta = meta_from_name(
                    "structure",
                    name=final_name,
                    path=ensure_relative_path(dest_path, base=project_root),
                )
                meta_dict = meta.to_dict()
                meta_dict["fingerprint"] = fingerprint
                _write_structure(structure, dest_path, metadata=meta_dict)

                # Add to config (ID-only reference)
                entry = {"structure_ulid": meta.ulid}
                structures.append(entry)
                save_project_config(project_root, config)

                # Resolve and return
                struct_resolved = require_structure(project_root, final_slug, config=config)
                struct_model = load_structure_model(struct_resolved.absolute_path, project_root)
                pmg_structure = read_structure(struct_resolved.absolute_path)

                return structure_to_dto(
                    struct_resolved=struct_resolved,
                    struct_model=struct_model,
                    pmg_structure=pmg_structure,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def import_online(
            self,
            session_id: str,
            candidate_id: str,
            name: str | None = None,
        ) -> Any:
            """
            Import an online candidate structure into the project.

            Loads the structure from the global online cache, canonicalizes it,
            generates a unique name/slug, writes the structure file with online
            provenance, and updates the project config.

            Args:
                session_id: Session ID from online search
                candidate_id: Candidate ID to import
                name: Optional name for the imported structure

            Returns:
                ImportOnlineResultDTO with structure_ulid, name, slug

            Raises:
                NotFoundError: If candidate not found in cache
                APIError: If structure not available
            """
            try:
                import json
                import time as _time

                from qmatsuite.api.errors import NotFoundError, APIError
                from qmatsuite.api.types.online_search import (
                    ImportOnlineResultDTO,
                    StructureRefDTO,
                )
                from qmatsuite.io.online_cache import OnlineStructureCache
                from qmatsuite.core.paths import get_qmatsuite_home_root
                from qmatsuite.core.project_utils import (
                    load_project_config,
                    save_project_config,
                    collect_slugs,
                )
                from qmatsuite.core.resources import (
                    generate_unique_name_and_slug,
                    meta_from_name,
                    ensure_relative_path,
                )
                from qmatsuite.core.structure_canonicalize import (
                    canonicalize_structure_like_in_place,
                )
                from qmatsuite.io import write_structure as _write_structure

                project_root = self._service.project_root

                # Use global cache (not project-local)
                cache_dir = get_qmatsuite_home_root() / "cache" / "online_structures"
                cache = OnlineStructureCache(cache_dir)

                # Get candidate metadata
                candidates_list = cache.get_candidates(session_id)
                candidate = next(
                    (c for c in candidates_list if c.candidate_id == candidate_id),
                    None,
                )

                # Get structure from cache
                structure = cache.get_structure(session_id, candidate_id)

                if structure is None:
                    # Try fetching via API
                    ref = StructureRefDTO(
                        session_id=session_id, candidate_id=candidate_id
                    )
                    doc_dto = QMSService.OnlineSearch.fetch_structure(ref)

                    from pymatgen.core import Structure as PMGStructure, Lattice
                    from pymatgen.core import Molecule as PMGMolecule

                    if doc_dto.structure_type == "crystal" and doc_dto.lattice:
                        lattice = Lattice(doc_dto.lattice)
                        species = [atom["element"] for atom in doc_dto.atoms]
                        coords = [atom["coords"] for atom in doc_dto.atoms]
                        structure = PMGStructure(
                            lattice, species, coords, coords_are_cartesian=True
                        )
                    else:
                        species = [atom["element"] for atom in doc_dto.atoms]
                        coords = [atom["coords"] for atom in doc_dto.atoms]
                        structure = PMGMolecule(species, coords)

                if structure is None:
                    raise APIError(
                        f"Structure for candidate {candidate_id} not available"
                    )

                # Determine default name
                default_name = (
                    candidate.label
                    if candidate
                    else structure.composition.reduced_formula
                )

                # Canonicalize
                canonicalize_structure_like_in_place(structure)

                # Generate unique name/slug
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
                _write_structure(structure, dest_path, metadata=meta)

                # Add online provenance to structure JSON extra field
                online_provenance = {
                    "source": candidate.source if candidate else "unknown",
                    "source_id": candidate.source_id if candidate else "",
                    "session_id": session_id,
                    "fetched_at": int(_time.time()),
                    "score": candidate.score if candidate else 0.0,
                    "flags": candidate.flags if candidate else [],
                }

                structure_data = json.loads(dest_path.read_text())
                if "extra" not in structure_data:
                    structure_data["extra"] = {}
                structure_data["extra"]["online_provenance"] = online_provenance
                dest_path.write_text(json.dumps(structure_data, indent=2))

                # Add to project config
                entry = {"structure_ulid": meta.ulid}
                structures.append(entry)
                save_project_config(project_root, config)

                return ImportOnlineResultDTO(
                    structure_ulid=meta.ulid,
                    name=final_name,
                    slug=final_slug,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def get_vis_data(
            self,
            selector: str,
            supercell: tuple[int, int, int] = (1, 1, 1),
            repeat_boundary: bool = False,
            display_mode: str = "primitive",
            box_bounds: tuple[float, float, float, float, float, float] | None = None,
        ) -> dict:
            """
            Get pure visualization data for a structure (no matplotlib).

            Returns all data needed for 3D rendering in a GUI:
            - Lattice vectors and parameters
            - Atom positions (Cartesian and fractional)
            - Element information and colors
            - Detected bonds

            Args:
                selector: Structure selector (name/slug/path)
                supercell: Tuple of (a, b, c) supercell scaling factors (for supercell mode)
                repeat_boundary: If True, include periodic images at boundaries
                display_mode: One of "primitive", "supercell", "conventional", "box"
                box_bounds: For box mode: (xmin, xmax, ymin, ymax, zmin, zmax)

            Returns:
                Dict with all visualization data (JSON-serializable)
            """
            try:
                from qmatsuite.io import read_structure as _read_structure
                from qmatsuite.core.resolution import resolve_structure
                from qmatsuite.analysis.structure_viz import (
                    DisplayModeParams,
                    _normalize_supercell,
                    build_structure_vis_payload as _build_payload,
                )
                import logging

                logger = logging.getLogger(__name__)
                project_root = self._service.project_root

                # Resolve structure
                resolved = resolve_structure(project_root, selector)
                if not resolved.absolute_path.exists():
                    from qmatsuite.api.errors import NotFoundError
                    raise NotFoundError(f"Structure file not found: {resolved.absolute_path}")

                # Load structure
                original_structure = _read_structure(resolved.absolute_path)

                # Normalize supercell input
                supercell_normalized = _normalize_supercell(supercell)

                # Determine effective display mode and supercell
                effective_mode = display_mode
                effective_supercell = None
                if display_mode == "supercell":
                    effective_supercell = supercell_normalized
                elif display_mode != "box" and supercell_normalized != (1, 1, 1):
                    effective_supercell = supercell_normalized
                    if display_mode == "primitive":
                        effective_mode = "supercell"

                # Box mode: enforce repeat_boundary=False
                if effective_mode == "box":
                    effective_repeat_boundary = False
                else:
                    effective_repeat_boundary = repeat_boundary

                # Build display mode params
                params = DisplayModeParams(
                    mode=effective_mode,
                    supercell=effective_supercell,
                    box_bounds=box_bounds if effective_mode == "box" else None,
                    repeat_boundary=effective_repeat_boundary,
                )

                # Build payload
                structure_ulid = resolved.meta.ulid if resolved.meta else None
                structure_meta = {
                    "structure_ulid": structure_ulid,
                    "structure_name": resolved.meta.name if resolved.meta else None,
                    "formula": original_structure.composition.reduced_formula,
                    "supercell": list(supercell_normalized),
                    "display_mode": effective_mode,
                }

                return _build_payload(original_structure, params, structure_meta)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def update_meta(
            self,
            selector: str,
            *,
            new_name: str | None = None,
            new_slug: str | None = None,
        ) -> StructureDTO:
            """
            Update structure metadata (rename).

            Args:
                selector: Structure selector
                new_name: New name for the structure
                new_slug: New slug for the structure

            Returns:
                Updated StructureDTO

            Raises:
                APIError: If structure not found or update fails
            """
            try:
                from qmatsuite.core.project_utils import (
                    load_project_config,
                    save_project_config,
                    find_structure_entry,
                    apply_structure_rename,
                )

                project_root = self._service.project_root
                config = load_project_config(project_root)
                entry = find_structure_entry(config, selector, project_root)

                apply_structure_rename(
                    project_root=project_root,
                    config=config,
                    entry=entry,
                    new_name=new_name,
                    new_slug=new_slug,
                    new_path=None,
                )

                save_project_config(project_root, config)

                # Re-fetch structure to get updated DTO
                new_selector = new_slug or new_name or selector
                return self.get(new_selector)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def can_delete(self, selector: str) -> dict:
            """
            Check if a structure can be safely deleted.

            Args:
                selector: Structure selector (ULID, slug, or name)

            Returns:
                Dict with:
                    - can_delete: bool - True if structure is not used by any calculations
                    - using_calculations: list[str] - Names of calculations using this structure
                    - structure_name: str - Name of the structure

            Raises:
                APIError: If structure not found
            """
            try:
                from qmatsuite.core.resolution import require_structure
                from qmatsuite.core.project_utils import (
                    load_project_config,
                    find_structure_entry,
                    calculations_using_structure,
                )

                project_root = self._service.project_root
                config = load_project_config(project_root)

                # Resolve structure to get entry
                entry = find_structure_entry(config, selector, project_root)

                # Check for dependent calculations
                using_calculations = calculations_using_structure(project_root, config, entry)
                calculation_names = [c.get("name") or c.get("meta", {}).get("name", "?") for c in using_calculations]

                return {
                    "can_delete": len(using_calculations) == 0,
                    "using_calculations": calculation_names,
                    "structure_name": (entry.get("meta") or {}).get("name") or entry.get("name"),
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def delete(self, selector: str, force: bool = False) -> None:
            """
            Delete a structure.

            Args:
                selector: Structure selector (ULID)
                force: If True, delete even if used by calculations

            Raises:
                ConflictError: If structure is used by calculations and force=False
                APIError: If structure not found or deletion fails
            """
            try:
                from qmatsuite.core.resolution import require_structure
                from qmatsuite.core.project_utils import (
                    load_project_config,
                    save_project_config,
                    calculations_using_structure,
                    move_to_trash,
                )
                import shutil

                project_root = self._service.project_root
                config = load_project_config(project_root)

                # Resolve structure
                struct_resolved = require_structure(project_root, selector, config=config)
                structure_ulid = struct_resolved.meta.ulid

                # Build structure entry dict for calculations_using_structure
                struct_entry = {"structure_ulid": structure_ulid}

                # Check for dependent calculations
                dependent = calculations_using_structure(project_root, config, struct_entry)
                if dependent and not force:
                    from qmatsuite.api.errors import ConflictError
                    raise ConflictError(
                        f"Structure is used by {len(dependent)} calculation(s)",
                        context={"dependent_calculations": [c.get("meta", {}).get("name", "?") for c in dependent]}
                    )

                # Remove from project.qms.yml
                structures = config.get("structures", [])
                config["structures"] = [
                    s for s in structures
                    if s.get("structure_ulid") != structure_ulid and s.get("meta", {}).get("ulid") != structure_ulid
                ]
                save_project_config(project_root, config)

                # Move structure file to trash
                trash_dir = project_root / ".trash"
                if struct_resolved.absolute_path.exists():
                    move_to_trash(struct_resolved.absolute_path, trash_dir)

            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def promote_relax_structure(
            self,
            calculation_selector: str,
            step_selector: str,
            name: str | None = None,
            *,
            index: Any = None,
            config: dict | None = None,
        ) -> Any:
            """
            Promote a relax step's generated structure to a project resource.

            Args:
                calculation_selector: Calculation selector (ULID, slug, or name)
                step_selector: Step selector (ULID, slug, or name)
                name: Optional name for the new structure (defaults to calc_step_relaxed)
                index: Optional resource index
                config: Optional project config

            Returns:
                ResolvedResource for the newly created structure

            Raises:
                APIError: If step not found, not a relax step, or no generated structure
            """
            try:
                from qmatsuite.core.resolution import require_calculation, require_step
                from qmatsuite.core.project_utils import load_project_config
                from qmatsuite.execution.relax_artifacts import get_generated_structure_path
                import yaml

                project_root = self._service.project_root

                if config is None:
                    config = load_project_config(project_root)

                calc_resolved = require_calculation(project_root, calculation_selector, config=config, index=index)
                step_resolved = require_step(project_root, calculation_selector, step_selector, config=config, index=index)

                # Get step type to verify it's a relax step
                step_data = yaml.safe_load(step_resolved.absolute_path.read_text()) or {}
                step_type_spec = step_data.get("step_type_spec", "")

                if "relax" not in step_type_spec.lower() and "vc-" not in step_type_spec.lower() and "md" not in step_type_spec.lower():
                    from qmatsuite.api.errors import ValidationError
                    raise ValidationError(
                        f"Step '{step_selector}' is not a relax step (type: {step_type_spec})"
                    )

                # Find generated structure (uses step ULID for path)
                calculation_dir = calc_resolved.absolute_path
                generated_path = get_generated_structure_path(calculation_dir, step_resolved.meta.ulid)

                if generated_path is None or not generated_path.exists():
                    from qmatsuite.api.errors import NotFoundError
                    raise NotFoundError(
                        f"No generated structure found for step '{step_selector}'. "
                        f"Make sure the step has completed successfully."
                    )

                # Generate structure name
                calc_slug = calc_resolved.meta.slug or calc_resolved.meta.ulid[:8]
                step_slug = step_resolved.meta.slug or step_resolved.meta.ulid[:8]
                structure_name = name or f"{calc_slug}_{step_slug}_relaxed"

                # Import the generated structure using nested accessor
                struct_dto = self._service.structure.import_file(
                    source=generated_path,
                    name=structure_name,
                )
                # Return the StructureDTO directly (callers may need to adapt to the new return type)
                return struct_dto
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def save_relax_final_structure(
            self,
            calculation_selector: str,
            step_selector: str,
            parent_structure_ulid: str,
            slug_hint: str | None = None,
            index: Any | None = None,
            config: dict | None = None,
        ) -> dict[str, Any]:
            """
            Save the final structure from a relax/vc-relax step as a new Structure resource.

            IDEMPOTENT: For a given (calculation_ulid, step_ulid), at most ONE structure
            may ever be created. Repeated calls return the existing structure ULID.

            Args:
                calculation_selector: Calculation selector
                step_selector: Step selector (ULID)
                parent_structure_ulid: ULID of the input structure (for provenance)
                slug_hint: Optional hint for structure slug/name
                index: Optional ResourceIndex
                config: Optional project config

            Returns:
                Dict with structure_ulid and already_exists flag

            Raises:
                ValueError: If step is not a relax/vc-relax step
                FileNotFoundError: If output file not found
            """
            from qmatsuite.calculation.geometry import (
                read_final_geometry_from_output_text,
                structure_from_qe_geometry_snapshot,
            )
            from qmatsuite.calculation.naming import CalculationFileNaming, find_calculation_raw_dir
            from qmatsuite.calculation.structure_steps import StructureStepSpec
            from qmatsuite.core.models import load_calculation
            from qmatsuite.core.project_utils import load_project_config, save_project_config, collect_slugs
            from qmatsuite.core.resolution import resolve_calculation, resolve_step
            from qmatsuite.core.resources import (
                ensure_relative_path,
                generate_unique_name_and_slug,
                meta_from_name,
            )
            from qmatsuite.io.structure_io import write_structure
            import yaml
            import json

            project_root = self._service.project_root

            # Resolve calculation and step
            calculation_resolved = resolve_calculation(project_root, calculation_selector, config=config, index=index)
            calculation_dir = calculation_resolved.absolute_path.parent if calculation_resolved.absolute_path.name == "calculation.yaml" else calculation_resolved.absolute_path
            calculation_ulid = calculation_resolved.meta.ulid

            if config is None:
                config = load_project_config(project_root)

            # Load calculation to get working_dir
            wf_model = load_calculation(calculation_dir / "calculation.yaml", project_root=project_root)
            working_dir_name = wf_model.working_dir
            raw_dir = find_calculation_raw_dir(calculation_dir, working_dir_name)

            # Resolve step
            step_resolved = resolve_step(project_root, calculation_selector, step_selector, config=config, index=index)
            step_ulid = step_resolved.meta.ulid

            # Load step spec
            spec = StructureStepSpec.from_yaml(step_resolved.absolute_path, resolve_structure_selector=None)
            step_type_spec = spec.step_type_spec

            # Validate step type (convert to GEN type for comparison)
            from qmatsuite.api import get_step_type_gen
            step_gen = get_step_type_gen(step_type_spec)
            if step_gen != "relax":
                raise ValueError(
                    f"Step '{step_selector}' is not a relax step (type: {step_type_spec})"
                )

            # Check if structure already created (idempotency check)
            step_yaml_data = yaml.safe_load(step_resolved.absolute_path.read_text()) or {}
            existing_structure_ulid = step_yaml_data.get("produced_structure_ulid")

            if existing_structure_ulid:
                return {
                    "structure_ulid": existing_structure_ulid,
                    "already_exists": True,
                }

            # Detect engine from step_type_spec (e.g. "xtb_relax" → "xtb")
            from qmatsuite.workflow.step_type_convert import prefix_from as _prefix_from
            engine_from_spec = (
                _prefix_from(str(step_type_spec))
                if step_type_spec and "_" in str(step_type_spec)
                else ""
            )

            if engine_from_spec == "xtb":
                # xTB relax: optimized geometry is in xtbopt.xyz.
                # xTB recipe uses WorkdirPolicy.ISOLATED: working dir is raw/<step_ulid>/
                from qmatsuite.io.structure_io import read_structure as _read_structure
                xtbopt_path = raw_dir / step_ulid / "xtbopt.xyz"
                # Also try directly in raw_dir for non-isolated layouts
                if not xtbopt_path.exists():
                    xtbopt_path = raw_dir / "xtbopt.xyz"
                if not xtbopt_path.exists():
                    raise FileNotFoundError(
                        f"xTB optimized geometry not found for step: "
                        f"{raw_dir / step_ulid / 'xtbopt.xyz'}. "
                        f"Run the xTB relax calculation first."
                    )
                structure = _read_structure(xtbopt_path)
            else:
                # QE and other engines: find relax.out (or equivalent) and parse geometry
                base_output = raw_dir / CalculationFileNaming.output_filename(step_gen, working_dir=None)
                if base_output.exists():
                    output_file = base_output
                else:
                    output_filename = CalculationFileNaming.output_filename(step_gen, working_dir=raw_dir)
                    output_file = raw_dir / output_filename

                if not output_file.exists():
                    raise FileNotFoundError(
                        f"Output file not found for step: {output_file}. "
                        f"Run the calculation first."
                    )

                # Parse final geometry (QE-specific)
                output_text = output_file.read_text()
                snapshot, species = read_final_geometry_from_output_text(output_text)
                structure = structure_from_qe_geometry_snapshot(snapshot, species)

            # Generate structure name/slug
            structures = config.setdefault("structures", [])
            existing_slugs = collect_slugs(structures, project_root=project_root)

            if slug_hint:
                preferred_name = slug_hint
            else:
                step_name = spec.meta.name or step_type_spec
                preferred_name = f"{step_name} relaxed"

            final_name, final_slug = generate_unique_name_and_slug(
                kind="structure",
                preferred_name=preferred_name,
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

            write_structure(structure, dest_path, metadata=meta)

            # Add provenance
            structure_data = json.loads(dest_path.read_text())
            if "extra" not in structure_data:
                structure_data["extra"] = {}
            structure_data["extra"]["relax_provenance"] = {
                "parent_structure_ulid": parent_structure_ulid,
                "source_calculation_ulid": calculation_ulid,
                "source_step_ulid": step_ulid,
            }
            dest_path.write_text(json.dumps(structure_data, indent=2))

            # Add to project config
            entry = {"structure_ulid": meta.ulid}
            structures.append(entry)
            save_project_config(project_root, config)

            # Update step YAML with produced_structure_ulid
            from qmatsuite.core.yamldoc import StepDoc
            from qmatsuite.workflow.step_factory import save_step_doc

            step_doc = StepDoc.load(step_resolved.absolute_path)
            step_doc.set(["produced_structure_ulid"], meta.ulid)
            save_step_doc(step_doc, step_resolved.absolute_path)

            # Update registry in-place if index is provided
            if index is not None:
                from qmatsuite.core.resolution import update_registry_add_structure
                update_registry_add_structure(index, meta, dest_path)

            return {
                "structure_ulid": meta.ulid,
                "already_exists": False,
            }

    @property
    def structure(self) -> Structure:
        """Access structure capabilities."""
        return QMSService.Structure(self)

    # Online structure search domain (PR0)
    class OnlineSearch:
        """Online structure search capabilities."""
        
        @staticmethod
        def search_structures(
            query: str,
            *,
            mode: str = "auto",
            sources: Any = None,
            limit: int = 10,
            timeout_s: float = 15.0,
            refresh_registry: bool = False,
        ) -> Any:
            """
            Search online structures (OPTIMADE crystals + PubChem molecules).
            
            PR6: Uses unified provider system.
            
            Args:
                query: Chemical formula or molecule name (e.g., "Si", "caffeine", "H2O")
                mode: Search mode - "crystal" (OPTIMADE only), "molecule" (PubChem only), "auto" (both)
                sources: Source configuration (provider enable/disable, ordering). If None, uses settings defaults.
                limit: Maximum total results to return
                timeout_s: Per-provider timeout in seconds
                refresh_registry: If True, force refresh OPTIMADE provider registry cache
                
            Returns:
                SearchResultDTO with candidates, session_id, providers_queried, partial flag
            """
            from qmatsuite.api.types.online_search import (
                SearchResultDTO,
                CandidateDTO,
            )
            from qmatsuite.io.providers import unified_search
            from qmatsuite.io.providers.optimade import Candidate as OptimadeCandidate
            from qmatsuite.io.providers.pubchem import PubChemCandidate
            from qmatsuite.io.online_cache import OnlineStructureCache, CandidateSummary
            from qmatsuite.core.paths import get_qmatsuite_home_root
            import uuid
            
            # Convert sources to user_settings dict if provided
            user_settings = None
            if sources:
                # TODO: Convert SourceConfigDTO to user_settings dict
                pass
            
            # Call unified search
            result = unified_search(
                query,
                mode=mode,
                max_results=limit,
                timeout_s=timeout_s,
                refresh_registry=refresh_registry,
                user_settings=user_settings,
            )
            
            # Create session and cache candidates
            session_id = str(uuid.uuid4())
            cache_dir = get_qmatsuite_home_root() / "cache" / "online_structures"
            cache = OnlineStructureCache(cache_dir)
            
            candidate_dtos = []
            source_summary_parts = []
            
            # Convert candidates to DTOs and cache them
            for idx, candidate in enumerate(result.candidates):
                if isinstance(candidate, OptimadeCandidate):
                    # OPTIMADE/MP native candidate
                    structure_type = "crystal"
                    source = candidate.provider_id
                    source_id = candidate.entry_id
                    formula = candidate.reduced_formula
                    nsites = candidate.nsites
                    spacegroup = f"SG {candidate.space_group_number}" if candidate.space_group_number else None
                    flags = []
                    if candidate.has_partial_occupancy:
                        flags.append("partial_occ")
                    if candidate.provider_id in ["cod"]:
                        flags.append("experimental")
                    else:
                        flags.append("computed")
                    
                    # Build label
                    label = f"{formula} ({nsites} sites)"
                    if spacegroup:
                        label += f", {spacegroup}"
                    
                    candidate_id = f"opt_{source}-{source_id}"
                    providers = [candidate.provider_id]
                    
                    # Store in cache
                    cache_candidate = CandidateSummary(
                        candidate_id=candidate_id,
                        label=label,
                        source=source,
                        source_id=source_id,
                        nsites=nsites,
                        spacegroup=spacegroup,
                        flags=flags,
                        score=candidate.score,
                    )
                    cache.add_candidate_metadata_only(session_id, cache_candidate, idx)
                    
                    if source not in source_summary_parts:
                        source_summary_parts.append(source)
                    
                elif isinstance(candidate, PubChemCandidate):
                    # PubChem molecule candidate
                    structure_type = "molecule"
                    source = "pubchem"
                    source_id = candidate.cid
                    formula = candidate.formula
                    nsites = len(candidate.molecule) if candidate.molecule else 0
                    spacegroup = None
                    flags = ["molecule"]
                    
                    label = f"{candidate.name or formula} ({nsites} atoms)"
                    candidate_id = f"pubchem-{source_id}"
                    providers = ["pubchem"]
                    
                    # Store in cache
                    cache_candidate = CandidateSummary(
                        candidate_id=candidate_id,
                        label=label,
                        source=source,
                        source_id=source_id,
                        nsites=nsites,
                        spacegroup=None,
                        flags=flags,
                        score=0.0,
                    )
                    cache.add_candidate_metadata_only(session_id, cache_candidate, idx)
                    
                    if "pubchem" not in source_summary_parts:
                        source_summary_parts.append("pubchem")
                else:
                    # Unknown candidate type, skip
                    continue
                
                candidate_dto = CandidateDTO(
                    candidate_id=candidate_id,
                    label=label,
                    source=source,
                    source_id=source_id,
                    structure_type=structure_type,
                    formula=formula,
                    nsites=nsites,
                    spacegroup=spacegroup,
                    providers=providers,
                    score=candidate.score if hasattr(candidate, "score") else 0.0,
                    flags=flags,
                    metadata=candidate.metadata if hasattr(candidate, "metadata") else {},
                )
                candidate_dtos.append(candidate_dto)
            
            # Store session info
            source_summary = "+".join(source_summary_parts) if source_summary_parts else "none"
            cache.create_session(session_id, query, source_summary)
            
            return SearchResultDTO(
                session_id=session_id,
                candidates=candidate_dtos,
                providers_queried=result.providers_queried,
                partial=result.partial,
                query=query,
                mode=mode,
            )
        
        @staticmethod
        def fetch_structure(ref: Any) -> Any:
            """
            Fetch full structure from online source.
            
            Uses global user cache at ~/.qmatsuite/cache/online_structures (not project-specific).
            
            PR6: Uses provider system to fetch from correct source.
            
            Args:
                ref: StructureRefDTO with session_id + candidate_id, or direct_ref
                
            Returns:
                StructureDocDTO with full structure data (atoms, lattice if crystal, etc.)
            """
            from qmatsuite.api.types.online_search import StructureDocDTO
            from qmatsuite.io.online_cache import OnlineStructureCache
            from qmatsuite.io.online_search import fetch_structure_from_optimade
            from qmatsuite.io.providers.pubchem import fetch_3d_sdf, parse_sdf_to_molecule
            from qmatsuite.core.paths import get_qmatsuite_home_root
            from qmatsuite.api.errors import NotFoundError, APIError
            from pymatgen.core import Structure as PMGStructure, Molecule as PMGMolecule
            
            # Use global cache location (not project-specific)
            cache_dir = get_qmatsuite_home_root() / "cache" / "online_structures"
            cache = OnlineStructureCache(cache_dir)
            
            if hasattr(ref, 'session_id') and ref.session_id and hasattr(ref, 'candidate_id') and ref.candidate_id:
                # Get candidate from cache
                candidates = cache.get_candidates(ref.session_id)
                candidate = next((c for c in candidates if c.candidate_id == ref.candidate_id), None)
                if not candidate:
                    raise NotFoundError(f"Candidate not found: {ref.candidate_id}")
                
                # Try to get structure from cache first
                structure = cache.get_structure(ref.session_id, ref.candidate_id)
                
                # Fetch structure if needed
                if structure is None:
                    if candidate.source == "pubchem":
                        # Fetch PubChem molecule
                        sdf_content = fetch_3d_sdf(candidate.source_id)
                        if not sdf_content:
                            raise APIError(f"Failed to fetch 3D SDF for PubChem CID: {candidate.source_id}")
                        structure = parse_sdf_to_molecule(sdf_content, candidate.source_id)
                        if not structure:
                            raise APIError(f"Failed to parse SDF for PubChem CID: {candidate.source_id}")
                    elif candidate.source in ["mp", "cod", "alexandria", "oqmd", "jarvis", "mcloud"] or candidate.candidate_id.startswith("opt_"):
                        # OPTIMADE provider
                        # Extract provider ID and entry ID from candidate_id
                        if candidate.candidate_id.startswith("opt_"):
                            # Format: opt_mp-123 -> provider=mp, entry_id=mp-123
                            parts = candidate.candidate_id.split("-", 1)
                            if len(parts) > 1:
                                provider_id = parts[0].replace("opt_", "")
                                entry_id = candidate.source_id  # Use source_id which is the actual entry ID
                            else:
                                provider_id = candidate.source
                                entry_id = candidate.source_id
                        else:
                            provider_id = candidate.source
                            entry_id = candidate.source_id
                        
                        # Get OPTIMADE base URL for provider
                        from qmatsuite.io.providers.optimade import get_providers_with_settings
                        providers = get_providers_with_settings(refresh_registry=False)
                        provider = next((p for p in providers if p.provider_key == provider_id), None)
                        if not provider:
                            raise APIError(f"Provider not found: {provider_id}")
                        
                        optimade_base = provider.base_url
                        structure, raw_data = fetch_structure_from_optimade(optimade_base, entry_id)
                        if not structure:
                            raise APIError(f"Failed to fetch structure from OPTIMADE: {entry_id}")
                    elif candidate.source == "mp-native":
                        # Materials Project native - structure should already be in metadata
                        # For now, fall back to OPTIMADE fetch
                        from qmatsuite.io.providers.optimade import get_providers_with_settings
                        providers = get_providers_with_settings(refresh_registry=False)
                        mp_provider = next((p for p in providers if p.provider_key == "mp"), None)
                        if mp_provider:
                            structure, raw_data = fetch_structure_from_optimade(mp_provider.base_url, candidate.source_id)
                            if not structure:
                                raise APIError(f"Failed to fetch structure from MP: {candidate.source_id}")
                        else:
                            raise APIError("MP provider not available")
                    else:
                        raise APIError(f"Unknown source: {candidate.source}")
                    
                    # Cache the fetched structure
                    rank = next((i for i, c in enumerate(candidates) if c.candidate_id == ref.candidate_id), 0)
                    cache.add_candidate(ref.session_id, candidate, structure, rank)
            else:
                raise APIError("Invalid structure reference: must provide session_id + candidate_id")
            
            # Convert to StructureDocDTO
            if isinstance(structure, PMGStructure):
                # Crystal structure
                atoms = []
                for site in structure:
                    atoms.append({
                        "element": str(site.specie),
                        "coords": site.coords.tolist() if hasattr(site.coords, 'tolist') else list(site.coords),
                    })
                
                lattice = structure.lattice.matrix.tolist() if structure.lattice else None
                pbc = [True, True, True] if structure.lattice else [False, False, False]
                
                return StructureDocDTO(
                    structure_type="crystal",
                    formula=structure.composition.reduced_formula,
                    atoms=atoms,
                    lattice=lattice,
                    pbc=pbc,
                    provenance={"source": candidate.source, "source_id": candidate.source_id},
                )
            elif isinstance(structure, PMGMolecule):
                # Molecule structure
                atoms = []
                for site in structure:
                    atoms.append({
                        "element": str(site.specie),
                        "coords": site.coords.tolist() if hasattr(site.coords, 'tolist') else list(site.coords),
                    })
                
                return StructureDocDTO(
                    structure_type="molecule",
                    formula=structure.composition.formula,
                    atoms=atoms,
                    lattice=None,
                    pbc=[False, False, False],
                    provenance={"source": candidate.source, "source_id": candidate.source_id},
                )
            else:
                raise APIError(f"Unsupported structure type: {type(structure)}")

        @staticmethod
        def get_candidate_detail(
            session_id: str,
            candidate_id: str,
            *,
            display_mode: str = "primitive",
            supercell: tuple[int, int, int] = (1, 1, 1),
            box_bounds: tuple | None = None,
            repeat_boundary: bool = False,
        ) -> Any:
            """
            Get detailed structure data for an online candidate, including visualization.

            Fetches structure from cache (or provider if not cached), converts to
            primitive cell, builds provenance, runs the shared visualization pipeline,
            and returns a CandidateDetailDTO ready for display.

            Args:
                session_id: Session ID from search
                candidate_id: Candidate ID
                display_mode: "primitive", "supercell", "conventional", or "box"
                supercell: Supercell dimensions (used when display_mode="supercell")
                box_bounds: Box bounds (used when display_mode="box")
                repeat_boundary: Whether to repeat boundary atoms

            Returns:
                CandidateDetailDTO with visualization data, structure JSON, and provenance
            """
            import logging
            import tempfile
            from pathlib import Path

            from qmatsuite.api.errors import NotFoundError, APIError
            from qmatsuite.api.types.online_search import (
                CandidateDetailDTO,
                StructureRefDTO,
            )
            from qmatsuite.api.utils import (
                DisplayModeParams,
                build_structure_vis_payload,
                write_structure,
            )
            from qmatsuite.io.online_cache import OnlineStructureCache
            from qmatsuite.io.online_search import (
                extract_provenance as _extract_provenance,
            )
            from qmatsuite.core.paths import get_qmatsuite_home_root

            logger = logging.getLogger(__name__)

            # --- 1. Resolve candidate from global cache ---
            cache_dir = get_qmatsuite_home_root() / "cache" / "online_structures"
            cache = OnlineStructureCache(cache_dir)

            candidates = cache.get_candidates(session_id)
            candidate = next(
                (c for c in candidates if c.candidate_id == candidate_id), None
            )
            if candidate is None:
                raise NotFoundError(
                    f"Candidate {candidate_id} not found in session {session_id}",
                    context={"candidate_id": candidate_id, "session_id": session_id},
                )

            # --- 2. Get or fetch structure ---
            structure = cache.get_structure(session_id, candidate_id)

            if structure is None:
                # Use existing fetch_structure() API method
                ref = StructureRefDTO(session_id=session_id, candidate_id=candidate_id)
                doc_dto = QMSService.OnlineSearch.fetch_structure(ref)

                # Convert StructureDocDTO back to pymatgen for vis pipeline
                from pymatgen.core import Structure as PMGStructure, Lattice
                from pymatgen.core import Molecule as PMGMolecule

                if doc_dto.structure_type == "crystal" and doc_dto.lattice:
                    lattice = Lattice(doc_dto.lattice)
                    species = [atom["element"] for atom in doc_dto.atoms]
                    coords = [atom["coords"] for atom in doc_dto.atoms]
                    structure = PMGStructure(
                        lattice, species, coords, coords_are_cartesian=True
                    )
                else:
                    species = [atom["element"] for atom in doc_dto.atoms]
                    coords = [atom["coords"] for atom in doc_dto.atoms]
                    structure = PMGMolecule(species, coords)

            # --- 3. Convert to primitive cell ---
            try:
                structure = structure.get_primitive_structure()
            except Exception as e:
                logger.warning(f"Failed to get primitive structure, using as-is: {e}")

            # --- 4. Build provenance from OPTIMADE metadata ---
            metadata = cache.get_candidate_metadata(session_id, candidate_id) or {}
            optimade_base = metadata.get("optimade_base")

            # Retrieve optimade_raw from structure meta in cache
            optimade_raw = None
            try:
                import sqlite3
                import json as _json

                conn = sqlite3.connect(cache.db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT structure_key FROM candidates "
                        "WHERE session_id = ? AND candidate_id = ?",
                        (session_id, candidate_id),
                    )
                    row = cursor.fetchone()
                    if row and row[0]:
                        cursor.execute(
                            "SELECT meta FROM structures WHERE structure_key = ?",
                            (row[0],),
                        )
                        meta_row = cursor.fetchone()
                        if meta_row and meta_row[0]:
                            meta_data = _json.loads(meta_row[0].decode("utf-8"))
                            optimade_raw = meta_data.get("optimade_raw")
                finally:
                    conn.close()
            except Exception as e:
                logger.debug(f"Could not retrieve optimade_raw from cache: {e}")

            provenance = None
            if candidate.source == "optimade" and optimade_raw:
                try:
                    optimade_data = optimade_raw.get("data", {})
                    optimade_attrs = optimade_data.get("attributes", {})

                    provider = "main"
                    database = "unknown"
                    if optimade_base:
                        parts = optimade_base.rstrip("/").split("/")
                        if len(parts) >= 2:
                            provider = (
                                parts[-2]
                                if parts[-2] in ["main", "archive"]
                                else "main"
                            )
                            database = (
                                parts[-1]
                                if parts[-1]
                                and parts[-1] not in ["v1", "structures"]
                                else "unknown"
                            )
                        elif len(parts) == 1 and parts[0]:
                            database = parts[0]

                    provenance = _extract_provenance(
                        provider=provider,
                        database=database,
                        base_url=optimade_base or "",
                        optimade_id=candidate.source_id,
                        attributes=optimade_attrs,
                        raw=optimade_raw,
                    )
                except Exception as e:
                    logger.warning(f"Failed to build provenance: {e}")
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

            # --- 5. Run shared visualization pipeline ---
            params = DisplayModeParams(
                mode=display_mode,
                supercell=supercell if display_mode == "supercell" else None,
                box_bounds=box_bounds if display_mode == "box" else None,
                repeat_boundary=repeat_boundary,
            )

            vis_payload = build_structure_vis_payload(
                structure,
                params,
                structure_meta={"structure_ulid": f"online:{candidate_id}"},
            )

            # Format atoms for frontend
            atoms_data = []
            for atom in vis_payload.get("atoms", []):
                atoms_data.append({
                    "position": atom["cart_coords"],
                    "cart_coords": atom["cart_coords"],
                    "frac_coords": atom["frac_coords"],
                    "symbol": atom["element"],
                    "color": atom["color"],
                    "radius": atom["radius"],
                    "is_boundary": atom.get("is_boundary", False),
                })

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

            # Validate and format bonds
            bonds_data = []
            max_bond_idx = -1
            atoms_data_len = len(atoms_data)

            for bond in vis_payload.get("bonds", []):
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

            if bonds_data and max_bond_idx >= atoms_data_len:
                raise ValueError(
                    f"INVALID ONLINE PAYLOAD: bonds reference invalid atom indices. "
                    f"maxBondIndex={max_bond_idx} >= atoms_len={atoms_data_len}."
                )

            vis_data = {
                "atoms": atoms_data,
                "boundary_atoms": boundary_atoms_data,
                "bonds": bonds_data,
                "lattice": vis_payload["lattice"],
                "supercell": list(supercell) if display_mode == "supercell" else [1, 1, 1],
                "display_mode": display_mode,
            }

            # --- 6. Serialize structure to JSON ---
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as tmp:
                tmp_path = Path(tmp.name)
                write_structure(structure, tmp_path)
                structure_json = tmp_path.read_text()
                tmp_path.unlink()

            # --- 7. Extract formula ---
            formula = structure.composition.reduced_formula
            if candidate.source == "optimade" and optimade_raw:
                optimade_data = optimade_raw.get("data", {})
                optimade_attrs = optimade_data.get("attributes", {})
                opt_formula = optimade_attrs.get(
                    "chemical_formula_reduced"
                ) or optimade_attrs.get("chemical_formula_descriptive")
                if opt_formula:
                    formula = opt_formula

            perf = vis_payload.get("perf")

            return CandidateDetailDTO(
                structure_vis=vis_data,
                structure_json=structure_json,
                formula=formula,
                n_atoms=len(structure),
                n_species=len(structure.composition),
                provenance=provenance,
                perf=perf,
            )

        @staticmethod
        def list_providers(*, refresh_registry: bool = False) -> Any:
            """
            List available online structure providers.
            
            PR6: Uses provider registry system.
            
            Args:
                refresh_registry: If True, force refresh OPTIMADE provider registry cache
                
            Returns:
                ProviderListDTO with optimade_providers, pubchem_enabled, materials_project_enabled
            """
            from qmatsuite.api.types.online_search import ProviderListDTO, ProviderInfoDTO
            from qmatsuite.io.providers.optimade import get_providers_with_settings
            from qmatsuite.core.settings import load_settings
            
            # Get providers with user settings applied
            providers = get_providers_with_settings(refresh_registry=refresh_registry)
            
            # Convert to DTOs
            optimade_provider_dtos = []
            for provider in providers:
                optimade_provider_dtos.append(ProviderInfoDTO(
                    provider_key=provider.provider_key,
                    name=provider.name,
                    base_url=provider.base_url,
                    enabled=provider.enabled,
                    structure_count=provider.structure_count,
                    requires_api_key=False,
                ))
            
            # Get PubChem and MP settings
            settings = load_settings()
            pubchem_enabled = settings.online_structures.pubchem_enabled
            mp_config = settings.online_structures.materials_project
            materials_project_enabled = mp_config.enabled
            materials_project_has_key = mp_config.has_key()
            
            return ProviderListDTO(
                optimade_providers=optimade_provider_dtos,
                pubchem_enabled=pubchem_enabled,
                materials_project_enabled=materials_project_enabled,
                materials_project_has_key=materials_project_has_key,
            )
        
        @staticmethod
        def update_online_sources(patch: Any) -> Any:
            """
            Update online structure source settings.
            
            PR6: Persists settings via global settings mechanism.
            
            Args:
                patch: OnlineSourcesPatchDTO with fields to update
                
            Returns:
                OnlineSourcesSettingsDTO with current settings after patch
            """
            from qmatsuite.core.settings import load_settings, save_settings
            from qmatsuite.api.types.online_search import (
                OnlineSourcesSettingsDTO,
                ProviderInfoDTO,
                MaterialsProjectConfigDTO,
            )
            from qmatsuite.io.providers.optimade import get_providers_with_settings
            
            # Load current settings
            settings = load_settings()
            online_config = settings.online_structures
            
            # Apply patch
            if patch.optimade_providers is not None:
                # Update provider enable/disable flags
                # Migrate legacy "id" -> "provider_key" during read
                provider_map = {}
                for p in online_config.optimade_providers:
                    key = p.get("provider_key") or p.get("id")
                    # Migrate: ensure provider_key is set, remove legacy "id"
                    migrated = {k: v for k, v in p.items() if k != "id"}
                    migrated["provider_key"] = key
                    provider_map[key] = migrated
                for provider_patch in patch.optimade_providers:
                    patch_key = provider_patch.provider_key
                    if patch_key in provider_map:
                        provider_map[patch_key]["enabled"] = provider_patch.enabled
                    else:
                        provider_map[patch_key] = {"provider_key": patch_key, "enabled": provider_patch.enabled}
                online_config.optimade_providers = list(provider_map.values())
            
            if patch.pubchem_enabled is not None:
                online_config.pubchem_enabled = patch.pubchem_enabled
            
            if patch.materials_project is not None:
                mp_patch = patch.materials_project
                if mp_patch.enabled is not None:
                    online_config.materials_project.enabled = mp_patch.enabled
                if mp_patch.api_key is not None:
                    online_config.materials_project.api_key = mp_patch.api_key
            
            if patch.timeout_seconds is not None:
                online_config.timeout_seconds = patch.timeout_seconds
            
            if patch.max_results_per_provider is not None:
                online_config.max_results_per_provider = patch.max_results_per_provider
            
            if patch.max_total_results is not None:
                online_config.max_total_results = patch.max_total_results
            
            # Save settings
            save_settings(settings)
            
            # Build response DTO
            providers = get_providers_with_settings(refresh_registry=False)
            provider_dtos = []
            for provider in providers:
                # Check if enabled in settings
                enabled = provider.enabled
                provider_settings = next(
                    (p for p in online_config.optimade_providers if p.get("provider_key") == provider.provider_key),
                    None
                )
                if provider_settings:
                    enabled = provider_settings.get("enabled", enabled)
                
                provider_dtos.append(ProviderInfoDTO(
                    provider_key=provider.provider_key,
                    name=provider.name,
                    base_url=provider.base_url,
                    enabled=enabled,
                    structure_count=provider.structure_count,
                    requires_api_key=False,
                ))
            
            return OnlineSourcesSettingsDTO(
                optimade_providers=provider_dtos,
                pubchem_enabled=online_config.pubchem_enabled,
                materials_project=MaterialsProjectConfigDTO(
                    enabled=online_config.materials_project.enabled,
                    has_key=online_config.materials_project.has_key(),
                ),
                timeout_seconds=online_config.timeout_seconds,
                max_results_per_provider=online_config.max_results_per_provider,
                max_total_results=online_config.max_total_results,
            )

    @property
    def online_search(self) -> OnlineSearch:
        """Access online structure search capabilities."""
        return QMSService.OnlineSearch

    # Calculation domain (PR5)
    class Calculation:
        """Calculation read capabilities."""
        
        def __init__(self, service: QMSService):
            self._service = service
        
        def get(self, selector: str) -> CalculationDTO:
            """
            Get calculation by selector.
            
            Args:
                selector: Calculation selector (ULID, slug, name, or path)
                
            Returns:
                CalculationDTO
                
            Raises:
                APIError: If calculation not found
            """
            try:
                from qmatsuite.core.resolution import require_calculation
                from qmatsuite.core.models import load_calculation
                from qmatsuite.project.model import Project
                
                # Resolve calculation
                calc_resolved = require_calculation(self._service.project_root, selector)
                
                # Get calculation directory
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                # Load calculation model
                calc_yaml = calc_dir / "calculation.yaml"
                if not calc_yaml.exists():
                    from qmatsuite.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Calculation file not found: {calc_yaml}",
                        context={"selector": selector, "path": str(calc_dir)}
                    )
                
                project = Project.open(self._service.project_root)
                calc_model = load_calculation(calc_yaml, self._service.project_root)
                
                # Load full Calculation object for step info
                from qmatsuite.calculation.calculation import Calculation
                calc_obj = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
                
                # Build CalculationDTO
                return calculation_to_dto(
                    calc_resolved=calc_resolved,
                    calc_model=calc_model,
                    calc_obj=calc_obj,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def list(
            self,
            project_selector: str | None = None,
            status: str | None = None,
            detail: bool = False,
        ) -> list[CalculationDTO] | list[dict]:
            """
            List calculations in project.

            Args:
                project_selector: Unused (for future multi-project support)
                status: Optional status filter (pending, running, completed, failed)
                detail: If True, return full detail dicts (as from get_detail)
                    instead of CalculationDTO objects

            Returns:
                List of CalculationDTO (detail=False) or list of detail dicts (detail=True)

            Raises:
                APIError: If project invalid
            """
            try:
                from qmatsuite.core.resolution import list_calculations, build_resource_index
                from qmatsuite.core.models import load_calculation
                from qmatsuite.project.model import Project
                from qmatsuite.calculation.calculation import Calculation

                # S4: Build ResourceIndex ONCE for the entire request (request-scoped sharing)
                _shared_index = build_resource_index(self._service.project_root)

                # List all calculations
                calc_resolved_list = list_calculations(self._service.project_root)

                project = Project.open(self._service.project_root, index=_shared_index)
                results: list = []

                # Build additional shared context for detail mode (F001+F002)
                if detail:
                    from qmatsuite.core.project_utils import load_project_config
                    from qmatsuite.core.resolution import make_structure_selector_resolver
                    _shared_config = load_project_config(self._service.project_root)
                    _shared_resolver = make_structure_selector_resolver(self._service.project_root, config=_shared_config)
                else:
                    _shared_config = _shared_resolver = None

                for calc_resolved in calc_resolved_list:
                    try:
                        # Get calculation directory
                        if calc_resolved.absolute_path.name == "calculation.yaml":
                            calc_dir = calc_resolved.absolute_path.parent
                        else:
                            calc_dir = calc_resolved.absolute_path

                        calc_yaml = calc_dir / "calculation.yaml"
                        if not calc_yaml.exists():
                            continue

                        # Load calculation model and object (pass shared index)
                        calc_model = load_calculation(calc_yaml, self._service.project_root, index=_shared_index)
                        calc_obj = Calculation.from_yaml(calc_dir, project, materialize_steps=False, index=_shared_index)

                        # Build CalculationDTO
                        dto = calculation_to_dto(
                            calc_resolved=calc_resolved,
                            calc_model=calc_model,
                            calc_obj=calc_obj,
                        )

                        # Filter by status if requested
                        if status is None or dto.status == status:
                            if detail:
                                try:
                                    results.append(self._get_detail_with_shared_context(
                                        dto.calc_ulid,
                                        index=_shared_index,
                                        config=_shared_config,
                                        resolver=_shared_resolver,
                                    ))
                                except Exception:
                                    results.append(dto.to_dict())
                            else:
                                results.append(dto)
                    except Exception:
                        # Skip calculations that can't be loaded
                        continue

                return results
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def require_ref(self, selector: str, config: dict | None = None) -> Any:
            """
            Resolve calculation selector to ResolvedResource (for internal use).

            Args:
                selector: Calculation selector (ULID, slug, name, or path)
                config: Optional project config (for backward compatibility)
                
            Returns:
                ResolvedResource (kernel type, not DTO)
                
            Raises:
                APIError: If calculation not found
            """
            try:
                from qmatsuite.core.resolution import require_calculation
                return require_calculation(self._service.project_root, selector)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def require_step_ref(
            self,
            calc_selector: str,
            step_selector: str,
            config: dict | None = None,
        ) -> Any:
            """
            Resolve step selector to ResolvedResource (for internal use).
            
            Args:
                calc_selector: Calculation selector
                step_selector: Step selector (ULID, slug, name, or index)
                config: Optional project config (for backward compatibility)
                
            Returns:
                ResolvedResource (kernel type, not DTO)
                
            Raises:
                APIError: If calculation or step not found
            """
            try:
                from qmatsuite.core.resolution import require_step
                return require_step(self._service.project_root, calc_selector, step_selector)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def resolve_enclosing_path(self, path: Path | None = None) -> CalculationRefDTO | None:
            """
            Resolve calculation that encloses the given path.
            
            Args:
                path: Path to check (defaults to current working directory)
                
            Returns:
                CalculationRefDTO if found, None otherwise
            """
            try:
                from qmatsuite.core.project_utils import find_enclosing_calculation
                from qmatsuite.api.utils import ensure_relative_path, extract_selector_from_entry
                from qmatsuite.api._mapping.dto_mapping import calculation_ref_to_dto
                
                if path is None:
                    path = Path.cwd()
                path = Path(path).resolve()
                
                config = self._service.project.get_config()
                entry = find_enclosing_calculation(self._service.project_root, config, start=path)
                
                if entry is None:
                    return None
                
                # Extract selector from entry and resolve to get path
                selector = extract_selector_from_entry(entry, "calculation")
                if not selector:
                    return None
                
                # Resolve to get ResolvedResource with path
                calc_resolved = self.require_ref(selector)
                
                # Get calculation directory path
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                # Get relative path
                rel_path = ensure_relative_path(calc_dir, base=self._service.project_root)
                
                # Build CalculationRefDTO
                return calculation_ref_to_dto(calc_resolved, rel_path)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                # Return None on any error (not found)
                return None
        
        def require_enclosing(self, path: Path | None = None) -> CalculationRefDTO:
            """
            Require calculation that encloses the given path.
            
            Args:
                path: Path to check (defaults to current working directory)
                
            Returns:
                CalculationRefDTO
                
            Raises:
                NotFoundError: If no calculation encloses the path
            """
            result = self.resolve_enclosing_path(path)
            if result is None:
                from qmatsuite.api.errors import NotFoundError
                path_str = str(path) if path else "current directory"
                raise NotFoundError(
                    f"No calculation found enclosing {path_str}",
                    context={"path": str(path) if path else None}
                )
            return result
        
        def get_step(self, calc_selector: str, step_selector: str) -> StepDTO:
            """
            Get step by selectors.
            
            Args:
                calc_selector: Calculation selector
                step_selector: Step selector (ULID, slug, name, or index)
                
            Returns:
                StepDTO
                
            Raises:
                APIError: If calculation or step not found
            """
            try:
                from qmatsuite.core.resolution import require_calculation, require_step
                from qmatsuite.core.models import load_calculation
                from qmatsuite.project.model import Project
                from qmatsuite.calculation.calculation import Calculation
                
                # Resolve calculation and step
                calc_resolved = require_calculation(self._service.project_root, calc_selector)
                step_resolved = require_step(
                    self._service.project_root,
                    calc_selector,
                    step_selector
                )
                
                # Get calculation directory
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                # Load calculation to get step info
                project = Project.open(self._service.project_root)
                calc_obj = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
                
                # Find matching step
                step_obj = None
                resolved_step_ulid = step_resolved.meta.ulid if step_resolved.meta else None
                for step in calc_obj.steps:
                    step_ulid = step.meta.ulid if hasattr(step, 'meta') and step.meta else None
                    if step_ulid == resolved_step_ulid:
                        step_obj = step
                        break
                
                if step_obj is None:
                    from qmatsuite.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Step not found in calculation",
                        context={"calc_selector": calc_selector, "step_selector": step_selector}
                    )
                
                # Build StepDTO
                return step_to_dto(
                    step_resolved=step_resolved,
                    step_obj=step_obj,
                    calc_ulid=calc_resolved.meta.ulid if calc_resolved.meta else "",
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def get_step_detail(self, calc_selector: str, step_selector: str) -> dict:
            """
            Get detailed step information as a dict (for daemon responses).

            Unlike get_step() which returns a StepDTO, this returns a full dict
            including parameters, cards, species_overrides, etc.

            Args:
                calc_selector: Calculation selector
                step_selector: Step selector

            Returns:
                Dict with step detail including parameters, cards, etc.
            """
            try:
                import yaml
                from qmatsuite.core.resolution import require_calculation, require_step, make_structure_selector_resolver
                from qmatsuite.calculation.structure_steps import StructureStepSpec
                from qmatsuite.core.project_utils import load_project_config
                from qmatsuite.api._mapping.dto_mapping import step_to_dict

                # Get StepDTO first
                step_dto = self.get_step(calc_selector, step_selector)
                result = step_to_dict(step_dto)

                # Resolve step to get file path
                step_resolved = require_step(
                    self._service.project_root,
                    calc_selector,
                    step_selector
                )

                # Add path info
                step_path = step_resolved.absolute_path
                result["path"] = str(step_path.relative_to(self._service.project_root))
                result["absolute_path"] = str(step_path)

                # Load step spec to get parameters, cards, species_overrides
                if step_path.exists():
                    config = load_project_config(self._service.project_root)
                    resolver = make_structure_selector_resolver(self._service.project_root, config=config)
                    spec = StructureStepSpec.from_yaml(step_path, resolve_structure_selector=resolver)

                    result["parameters"] = spec.parameters or {}
                    result["cards"] = spec.cards or {}
                    result["species_overrides"] = spec.species_overrides or {}
                    result["structure"] = spec.structure_ulid or spec.structure or ""
                    result["parent_calculation_id"] = spec.parent_calculation_id or ""
                    result["parent_calculation_ulid"] = spec.parent_calculation_id or ""  # Alias for backwards compat

                    # Add name/slug from spec meta if available
                    if spec.meta:
                        result["name"] = spec.meta.name or step_resolved.meta.name if step_resolved.meta else step_selector
                        result["slug"] = spec.meta.slug or step_resolved.meta.slug if step_resolved.meta else step_selector
                        result["ulid"] = step_resolved.meta.ulid if step_resolved.meta else step_selector

                    # Add prefix/outdir injection info (if applicable)
                    if spec.parameters and "CONTROL" in spec.parameters:
                        control = spec.parameters["CONTROL"]
                        result["prefix_outdir_injection"] = {
                            "effective_prefix": control.get("calculation", ""),
                            "effective_outdir": control.get("outdir", "./outdir"),
                        }
                else:
                    result["parameters"] = {}
                    result["cards"] = {}
                    result["species_overrides"] = {}
                    result["structure"] = ""
                    result["parent_calculation_id"] = ""
                    result["parent_calculation_ulid"] = ""  # Alias for backwards compat

                return result
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def list_steps(self, calc_selector: str) -> list[StepDTO]:
            """
            List all steps in a calculation.
            
            Args:
                calc_selector: Calculation selector
                
            Returns:
                List of StepDTO
                
            Raises:
                APIError: If calculation not found
            """
            try:
                from qmatsuite.core.resolution import require_calculation, list_steps
                from qmatsuite.core.models import load_calculation
                from qmatsuite.project.model import Project
                from qmatsuite.calculation.calculation import Calculation
                
                # Resolve calculation
                calc_resolved = require_calculation(self._service.project_root, calc_selector)
                
                # Get calculation directory
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                # Load calculation to get steps
                project = Project.open(self._service.project_root)
                calc_obj = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
                
                # List step resources
                step_resolved_list = list_steps(self._service.project_root, calc_selector)
                
                # Build step ID to step object mapping
                step_map = {(step.meta.ulid if hasattr(step, 'meta') and step.meta else None): step for step in calc_obj.steps}
                
                results = []
                calc_ulid = calc_resolved.meta.ulid if calc_resolved.meta else ""
                
                for step_resolved in step_resolved_list:
                    try:
                        step_ulid = step_resolved.meta.ulid if step_resolved.meta else None
                        step_obj = step_map.get(step_ulid) if step_ulid else None
                        
                        if step_obj:
                            dto = step_to_dto(
                                step_resolved=step_resolved,
                                step_obj=step_obj,
                                calc_ulid=calc_ulid,
                            )
                            results.append(dto)
                    except Exception:
                        # Skip steps that can't be loaded
                        continue
                
                return results
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        # NOTE: get_effective_params REMOVED - internal detail, use get_calculation DTO
        # which includes step.parameters. If merged params needed, should be StepDTO field.

        def create(
            self,
            engine: str,
            name: str | None = None,
            structure_selector: str | None = None,
            **kwargs
        ) -> CalculationDTO:
            """
            Create a new calculation.
            
            Args:
                engine: Engine family (e.g., "qe", "pyscf")
                name: Optional calculation name
                structure_selector: Optional structure selector
                **kwargs: Additional options (template, structure_kind, etc.)
                
            Returns:
                CalculationDTO for the new calculation
                
            Raises:
                APIError: If creation fails
            """
            try:
                from qmatsuite.core.project_utils import load_project_config, save_project_config, collect_slugs
                from qmatsuite.core.resolution import require_structure, ResolvedResource
                from qmatsuite.core.models import load_calculation, save_calculation, CalculationModel
                from qmatsuite.core.resources import (
                    ResourceMeta,
                    generate_unique_name_and_slug,
                    generate_resource_id,
                )
                from qmatsuite.project.model import Project
                from qmatsuite.calculation.calculation import Calculation

                project_root = self._service.project_root
                template = kwargs.get("template")
                calc_name = name or f"{engine}_calculation"

                config = load_project_config(project_root)
                calculations = config.setdefault("calculations", [])
                existing_slugs = collect_slugs(calculations, project_root=project_root)

                final_name, final_slug = generate_unique_name_and_slug(
                    kind="calculation",
                    preferred_name=calc_name,
                    existing_slugs=existing_slugs,
                )

                calculation_id = generate_resource_id()
                calculation_path = f"calculations/{final_slug}"
                calculation_dir = project_root / calculation_path

                if template:
                    from qmatsuite.core.templates import copy_calculation_template
                    calculation_dir, _, new_ulid = copy_calculation_template(
                        template,
                        calculation_dir,
                        project_root,
                        new_name=final_name,
                        structure=structure_selector,
                        calculation_ulid=calculation_id,
                    )
                    calculation_id = new_ulid
                    calculation_meta = ResourceMeta(ulid=calculation_id,
                        name=final_name,
                        slug=final_slug,
                        path=calculation_path,
                        kind="calculation",
                    )
                else:
                    calculation_dir.mkdir(parents=True, exist_ok=True)
                    (calculation_dir / "steps").mkdir(exist_ok=True)
                    (calculation_dir / "raw").mkdir(exist_ok=True)
                    (calculation_dir / "reference").mkdir(exist_ok=True)

                    # Resolve structure selector to structure_ulid
                    structure_ulid = None
                    structure_name = None
                    if structure_selector:
                        resolved_structure = require_structure(project_root, structure_selector, config=config)
                        structure_ulid = resolved_structure.meta.ulid
                        structure_name = resolved_structure.meta.name

                    calculation_meta = ResourceMeta(ulid=calculation_id,
                        name=final_name,
                        slug=final_slug,
                        path=calculation_path,
                        kind="calculation",
                    )
                    calculation_model = CalculationModel(
                        meta=calculation_meta,
                        structure_ulid=structure_ulid,
                        structure_name=structure_name,
                    )
                    save_calculation(calculation_model, calculation_dir)

                # Add to project config (ID-only reference)
                entry = {"calculation_id": calculation_id}
                calculations.append(entry)
                save_project_config(project_root, config)

                # Build ResolvedResource
                calc_resolved = ResolvedResource(
                    meta=calculation_meta,
                    entry=entry,
                    absolute_path=calculation_dir,
                )

                # Load calculation model and object
                calc_yaml = calculation_dir / "calculation.yaml"
                calc_model = load_calculation(calc_yaml, project_root)
                project = Project.open(project_root)
                calc_obj = Calculation.from_yaml(calculation_dir, project, materialize_steps=False)

                # Build CalculationDTO
                return calculation_to_dto(
                    calc_resolved=calc_resolved,
                    calc_model=calc_model,
                    calc_obj=calc_obj,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def update_meta(self, selector: str, **meta_kwargs) -> CalculationDTO:
            """
            Update calculation metadata.
            
            Args:
                selector: Calculation selector
                **meta_kwargs: Metadata fields to update (name, description, tags, etc.)
                
            Returns:
                Updated CalculationDTO
                
            Raises:
                APIError: If calculation not found or update fails
            """
            try:
                from qmatsuite.core.resolution import require_calculation
                from qmatsuite.core.models import load_calculation, save_calculation
                from qmatsuite.project.model import Project
                from qmatsuite.calculation.calculation import Calculation
                
                # Resolve calculation
                calc_resolved = require_calculation(self._service.project_root, selector)
                
                # Get calculation directory
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                # Load calculation model
                calc_yaml = calc_dir / "calculation.yaml"
                calc_model = load_calculation(calc_yaml, self._service.project_root)
                
                # Update metadata
                if "name" in meta_kwargs:
                    calc_model.meta.name = meta_kwargs["name"]
                    # Auto-update slug if name changed (unless slug explicitly provided)
                    if "slug" not in meta_kwargs:
                        from qmatsuite.core.resources import slugify
                        calc_model.meta.slug = slugify(meta_kwargs["name"])
                if "slug" in meta_kwargs:
                    calc_model.meta.slug = meta_kwargs["slug"]
                if "description" in meta_kwargs:
                    calc_model.meta.description = meta_kwargs["description"]
                if "tags" in meta_kwargs:
                    calc_model.meta.tags = set(meta_kwargs["tags"]) if meta_kwargs["tags"] else set()
                
                # Save updated model
                save_calculation(calc_model, calc_dir)
                
                # Reload calculation object
                project = Project.open(self._service.project_root)
                calc_obj = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
                
                # Rebuild resolved resource with updated meta
                from qmatsuite.core.resolution import ResolvedResource
                calc_resolved = ResolvedResource(
                    meta=calc_model.meta,
                    entry=calc_resolved.entry,
                    absolute_path=calc_dir,
                )
                
                # Build CalculationDTO
                return calculation_to_dto(
                    calc_resolved=calc_resolved,
                    calc_model=calc_model,
                    calc_obj=calc_obj,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def update_step_params(
            self,
            calc_selector: str,
            step_selector: str,
            params: dict
        ) -> StepDTO:
            """
            Update step parameters by modifying the step YAML file.

            Args:
                calc_selector: Calculation selector
                step_selector: Step selector
                params: Parameters to update. Can contain:
                    - 'parameters': dict of QE namelist parameters
                    - 'cards': dict of QE card data
                    - 'species_overrides': dict of species-specific overrides
                    - Any other step-level keys

            Returns:
                Updated StepDTO

            Raises:
                APIError: If calculation or step not found
            """
            try:
                from qmatsuite.core.resolution import require_calculation, require_step
                from qmatsuite.core.yamldoc import StepDoc
                from qmatsuite.workflow.step_factory import save_step_doc
                from qmatsuite.project.model import Project
                from qmatsuite.calculation.calculation import Calculation
                from qmatsuite.calculation.step import Step
                from qmatsuite.core.resources import ResourceMeta
                from qmatsuite.core.resolution import ResolvedResource
                import logging

                # Resolve calculation and step
                calc_resolved = require_calculation(self._service.project_root, calc_selector)
                step_resolved = require_step(
                    self._service.project_root,
                    calc_selector,
                    step_selector
                )

                # Get step path
                step_path = step_resolved.absolute_path

                # Load as StepDoc
                step_doc = StepDoc.load(step_path)

                # Apply updates via StepDoc API
                for key, value in params.items():
                    if value is not None:
                        if key in ("parameters", "cards", "species_overrides", "parameter_scan"):
                            # Use apply_patch for nested dicts (deep merge or replace)
                            step_doc.apply_patch({key: value})
                        elif isinstance(value, dict):
                            # Any other dict values also need apply_patch
                            step_doc.apply_patch({key: value})
                        else:
                            step_doc.set([key], value)

                # Save via factory (journaled) - warnings are logged
                warnings = save_step_doc(step_doc, step_path)
                if warnings:
                    logger = logging.getLogger(__name__)
                    for warning in warnings:
                        logger.warning(warning)

                # Get calculation directory for step_to_dto
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path

                # Get calc_ulid
                calc_ulid = calc_resolved.meta.ulid if calc_resolved.meta else ""

                # Re-read step file for fresh data
                import yaml
                step_data = yaml.safe_load(step_path.read_text())
                step_meta_dict = step_data.get("meta", {})
                step_meta = ResourceMeta.from_dict(
                    step_meta_dict,
                    kind="step",
                    default_name=step_selector,
                    default_path=str(step_path.relative_to(self._service.project_root))
                )

                # Create updated ResolvedResource
                step_resolved_updated = ResolvedResource(
                    meta=step_meta,
                    entry={},
                    absolute_path=step_path
                )

                # Get step_type_spec and engine from registry
                from qmatsuite.workflow.registry import get_registry
                from qmatsuite.workflow.step_type_convert import gen_from
                registry = get_registry()
                step_type_spec = step_data.get("step_type_spec", "scf")
                step_type_gen = gen_from(step_type_spec)  # Convert SPEC to GEN for registry
                step_spec = registry.get(step_type_gen)
                if step_spec is None:
                    from qmatsuite.workflow.step_type_convert import prefix_from
                    engine = prefix_from(step_type_spec)
                else:
                    engine = step_spec.engine

                # Create minimal Step object
                step_obj = Step(
                    meta=step_meta,
                    input_file=step_path,
                    engine=engine,
                    step_type_spec=step_type_spec,
                )

                # Build StepDTO
                return step_to_dto(
                    step_resolved=step_resolved_updated,
                    step_obj=step_obj,
                    calc_ulid=calc_ulid,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def duplicate(
            self,
            selector: str,
            *,
            new_name: str | None = None,
            new_slug: str | None = None,
        ) -> CalculationDTO:
            """
            Duplicate a calculation.
            
            Copies SSOT files (calculation.yaml, step.yaml) and raw/ directory.
            Does NOT copy outdir/, .history/, or other execution artifacts.
            
            Args:
                selector: Calculation selector
                new_name: Optional name for the duplicate (defaults to "{original_name}_copy")
                new_slug: Optional slug for the duplicate (defaults to slugified new_name)
                
            Returns:
                CalculationDTO for the duplicate
                
            Raises:
                NotFoundError: If calculation not found
                ConflictError: If new_slug already exists
                APIError: For other duplication failures
            """
            try:
                from qmatsuite.core.resolution import require_calculation
                from qmatsuite.core.models import load_calculation
                from qmatsuite.project.model import Project
                from qmatsuite.calculation.calculation import Calculation
                from qmatsuite.core.resources import generate_resource_id
                from qmatsuite.core.project_utils import slugify, load_project_config, save_project_config
                from qmatsuite.core.templates import _copy_calculation_from_path
                from qmatsuite.core.resolution import ResolvedResource
                
                # Resolve and load original calculation
                calc_resolved = require_calculation(self._service.project_root, selector)
                
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                calc_yaml = calc_dir / "calculation.yaml"
                calc_model = load_calculation(calc_yaml, self._service.project_root)
                
                # Generate new ID and determine name/slug
                new_id = generate_resource_id()
                if new_name is None:
                    new_name = f"{calc_model.meta.name}_copy"
                if new_slug is None:
                    new_slug = slugify(new_name)
                
                # Check for slug conflict
                new_path = f"calculations/{new_slug}"
                new_dir = self._service.project_root / new_path
                if new_dir.exists():
                    from qmatsuite.api.errors import ConflictError
                    raise ConflictError(
                        f"Calculation with slug '{new_slug}' already exists",
                        context={"new_slug": new_slug, "new_path": new_path}
                    )
                
                # Use existing copy function which handles SSOT + raw/ only
                # This copies: calculation.yaml, steps/*.step.yaml, raw/ (if exists)
                # Does NOT copy: outdir/, .history/, or other execution artifacts
                # Note: _copy_calculation_from_path derives slug from name, so if new_slug
                # is provided, we need to pass a name that will slugify to new_slug, or
                # manually update the slug after copying
                new_calc_yaml, _, _ = _copy_calculation_from_path(
                    source_path=calc_dir,
                    dest_dir=new_dir,
                    project_root=self._service.project_root,
                    new_name=new_name,  # Will be used for both name and slug derivation
                    calculation_ulid=new_id,
                )
                
                # If new_slug was explicitly provided and differs from slugified name,
                # update the calculation.yaml to use the explicit slug
                if new_slug != slugify(new_name):
                    import yaml
                    calc_data = yaml.safe_load(new_calc_yaml.read_text())
                    calc_data["meta"]["slug"] = new_slug
                    calc_data["meta"]["path"] = f"calculations/{new_slug}"
                    new_calc_yaml.write_text(yaml.safe_dump(calc_data, sort_keys=False, default_flow_style=False))
                    
                    # Also need to rename the directory if slug changed
                    expected_dir = self._service.project_root / f"calculations/{new_slug}"
                    if new_dir != expected_dir:
                        new_dir.rename(expected_dir)
                        new_dir = expected_dir
                        new_calc_yaml = expected_dir / "calculation.yaml"
                
                # Reload model
                new_calc_model = load_calculation(new_calc_yaml, self._service.project_root)
                
                # Add to project config with full meta
                config = load_project_config(self._service.project_root)
                calculations = config.setdefault("calculations", [])
                # Check if already in config (shouldn't be, but be safe)
                if not any((c.get("meta") or {}).get("ulid") == new_id for c in calculations):
                    calc_entry = {
                        "meta": {
                            "ulid": new_id,
                            "name": new_calc_model.meta.name,
                            "slug": new_calc_model.meta.slug,
                            "path": new_calc_model.meta.path,
                            "kind": "calculation",
                        }
                    }
                    calculations.append(calc_entry)
                save_project_config(self._service.project_root, config)

                # Build ResolvedResource
                new_calc_resolved = ResolvedResource(
                    meta=new_calc_model.meta,
                    entry=calc_entry,
                    absolute_path=new_dir,
                )
                
                # Load calculation object
                project = Project.open(self._service.project_root)
                new_calc_obj = Calculation.from_yaml(new_dir, project, materialize_steps=False)
                
                # Build CalculationDTO
                return calculation_to_dto(
                    calc_resolved=new_calc_resolved,
                    calc_model=new_calc_model,
                    calc_obj=new_calc_obj,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def can_delete(self, selector: str) -> dict:
            """
            Check if a calculation can be safely deleted.

            Args:
                selector: Calculation selector (ULID)

            Returns:
                Dict with calculation_name, dependent_calculations, has_dependencies

            Raises:
                APIError: If calculation not found
            """
            try:
                from qmatsuite.core.resolution import require_calculation
                from qmatsuite.core.project_utils import load_project_config, calculations_depending_on

                # Resolve calculation
                calc_resolved = require_calculation(self._service.project_root, selector)

                # Load config
                config = load_project_config(self._service.project_root)

                # Find entry in config
                entry = None
                for calc_entry in config.get("calculations", []):
                    calc_ulid = (calc_entry.get("meta") or {}).get("ulid") or calc_entry.get("calculation_id")
                    if calc_ulid == calc_resolved.meta.ulid:
                        entry = calc_entry
                        break

                if entry is None:
                    entry = {
                        "meta": calc_resolved.meta.to_dict() if calc_resolved.meta else {},
                        "calculation_id": calc_resolved.meta.ulid if calc_resolved.meta else selector,
                    }

                dependent_calculations = calculations_depending_on(config, entry)
                dep_names = [w.get("name", "?") for w in dependent_calculations]

                return {
                    "calculation_name": calc_resolved.meta.name if calc_resolved.meta else selector,
                    "dependent_calculations": dep_names,
                    "has_dependencies": len(dep_names) > 0,
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def delete(self, selector: str, force: bool = False) -> None:
            """
            Delete a calculation.

            Args:
                selector: Calculation selector (ULID)
                force: If True, delete even with dependencies

            Raises:
                ConflictError: If calculation has dependencies and force=False
                APIError: If calculation not found or deletion fails
            """
            try:
                from qmatsuite.core.resolution import require_calculation
                from qmatsuite.core.project_utils import (
                    load_project_config, save_project_config,
                    move_to_trash, calculations_depending_on
                )

                # Resolve calculation
                calc_resolved = require_calculation(self._service.project_root, selector)
                calc_ulid = calc_resolved.meta.ulid if calc_resolved.meta else selector

                # Get calculation directory
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path

                # Load config
                config = load_project_config(self._service.project_root)

                # Find entry in config
                entry = None
                entry_idx = None
                for idx, calc_entry in enumerate(config.get("calculations", [])):
                    entry_calc_ulid = (calc_entry.get("meta") or {}).get("ulid") or calc_entry.get("calculation_id")
                    if entry_calc_ulid == calc_ulid:
                        entry = calc_entry
                        entry_idx = idx
                        break

                if entry is None:
                    from qmatsuite.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Calculation not found in project config: {selector}",
                        context={"selector": selector}
                    )

                # Check dependencies if not forcing
                if not force:
                    deps = calculations_depending_on(config, entry)
                    if deps:
                        from qmatsuite.api.errors import ConflictError
                        dep_names = [d.get("name", "?") for d in deps]
                        raise ConflictError(
                            f"Calculation has dependencies: {dep_names}",
                            context={"dependencies": dep_names}
                        )

                # Remove from config
                config["calculations"].pop(entry_idx)
                save_project_config(self._service.project_root, config)

                # Move directory to trash
                if calc_dir.exists():
                    trash_dir = self._service.project_root / "trash"
                    move_to_trash(calc_dir, trash_dir)

            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def get_detail(self, selector: str) -> dict:
            """
            Get detailed calculation information for GUI display.

            Args:
                selector: Calculation selector (ULID)

            Returns:
                Dict with full calculation details including steps

            Raises:
                APIError: If calculation not found
            """
            try:
                from qmatsuite.core.resolution import build_resource_index
                from qmatsuite.core.project_utils import load_project_config
                from qmatsuite.core.resolution import make_structure_selector_resolver

                config = load_project_config(self._service.project_root)
                resolver = make_structure_selector_resolver(self._service.project_root, config=config)
                index = build_resource_index(self._service.project_root)

                return self._get_detail_with_shared_context(
                    selector, index=index, config=config, resolver=resolver,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def _get_detail_with_shared_context(
            self,
            selector: str,
            *,
            index,
            config: dict,
            resolver,
        ) -> dict:
            """
            Internal: get_detail using pre-built shared context.

            Avoids redundant build_resource_index / load_project_config calls
            when called in a loop (e.g. list(detail=True)).
            """
            from qmatsuite.core.resolution import require_calculation, resolve_structure, resolve_step
            from qmatsuite.core.models import load_calculation
            from qmatsuite.io.structure_io import read_structure
            from qmatsuite.calculation.structure_steps import StructureStepSpec

            # Resolve calculation (pass shared index to avoid rebuild)
            calc_resolved = require_calculation(self._service.project_root, selector, config=config, index=index)

            # Get calculation directory and yaml path
            if calc_resolved.absolute_path.name == "calculation.yaml":
                calc_dir = calc_resolved.absolute_path.parent
                calc_yaml = calc_resolved.absolute_path
            else:
                calc_dir = calc_resolved.absolute_path
                calc_yaml = calc_dir / "calculation.yaml"

            # Load calculation model (pass shared index to avoid rebuild)
            calc_model = load_calculation(calc_yaml, project_root=self._service.project_root, resolve_structure_selector=resolver, index=index)

            # Get structure info
            structure_name = None
            structure_ulid = calc_model.structure_ulid
            structure_elements = []

            if structure_ulid:
                try:
                    struct_resolved = resolve_structure(self._service.project_root, structure_ulid, config=config, index=index)
                    structure_name = struct_resolved.meta.name if struct_resolved.meta else None
                    if struct_resolved.absolute_path.exists():
                        structure = read_structure(struct_resolved.absolute_path)
                        structure_elements = sorted(set(str(el) for el in structure.composition.elements))
                except Exception:
                    pass

            calc_ulid_for_resolve = calc_resolved.meta.ulid if calc_resolved.meta else selector

            # Batch-read all step YAML files (F006: avoid per-step from_yaml in the loop)
            calc_steps_dir = calc_dir / "steps"
            step_specs_by_ulid: dict = {}
            if calc_steps_dir.exists():
                for sf in calc_steps_dir.glob("*.step.yaml"):
                    try:
                        spec = StructureStepSpec.from_yaml(sf, resolve_structure_selector=resolver)
                        if spec.meta and spec.meta.ulid:
                            step_specs_by_ulid[spec.meta.ulid] = (sf, spec)
                    except Exception:
                        pass

            step_summaries = []
            for entry in calc_model.steps:
                step_ulid = entry.step_ulid

                # Resolve step to get actual file path
                step_path = None
                step_resolved = None
                try:
                    step_resolved = resolve_step(
                        self._service.project_root,
                        calc_ulid_for_resolve,
                        step_ulid,
                        config=config,
                        index=index,
                    )
                    step_path = step_resolved.absolute_path
                except Exception:
                    pass

                # Use entry.step_type_spec (SPEC type from calculation.yaml) as primary
                step_type_spec = entry.step_type_spec
                step_name = step_resolved.meta.name if step_resolved and step_resolved.meta else step_ulid
                step_status = "pending"

                # Use batch-loaded spec if available, else fall back to individual read
                if step_ulid in step_specs_by_ulid:
                    _sf, spec = step_specs_by_ulid[step_ulid]
                    if not step_type_spec:
                        step_type_spec = spec.step_type_spec
                    step_name = spec.meta.name if spec.meta else step_name
                    step_status = spec.status if hasattr(spec, "status") else "pending"
                    if step_path is None:
                        step_path = _sf
                elif step_path and step_path.exists():
                    try:
                        spec = StructureStepSpec.from_yaml(step_path, resolve_structure_selector=resolver)
                        if not step_type_spec:
                            step_type_spec = spec.step_type_spec
                        step_name = spec.meta.name if spec.meta else step_name
                        step_status = spec.status if hasattr(spec, "status") else "pending"
                    except Exception:
                        pass

                # Convert step_type_spec to step_type_gen for response
                step_type_gen = None
                if step_type_spec:
                    try:
                        from qmatsuite.api import get_step_type_gen
                        step_type_gen = get_step_type_gen(step_type_spec)
                    except (KeyError, ValueError):
                        pass

                # Derive step_file (YAML filename) and slug for GUI
                step_file = step_path.name if step_path else None
                step_slug = step_resolved.meta.slug if step_resolved and step_resolved.meta else None

                step_summaries.append({
                    "ulid": step_ulid,  # Backwards compat
                    "step_ulid": step_ulid,
                    "step_type_spec": step_type_spec,
                    "step_type_gen": step_type_gen if step_type_gen else step_type_spec,
                    "type": step_type_gen if step_type_gen else step_type_spec,  # Backwards compat alias
                    "name": step_name,
                    "slug": step_slug or step_name,
                    "step_file": step_file or f"{step_name}.step.yaml",
                    "status": step_status,
                    "missing": not (step_path and step_path.exists()),
                })

            calc_ulid = calc_resolved.meta.ulid if calc_resolved.meta else selector
            return {
                "calc_ulid": calc_ulid,
                "ulid": calc_ulid,
                "calculation_id": calc_ulid,
                "name": calc_resolved.meta.name if calc_resolved.meta else selector,
                "slug": calc_resolved.meta.slug if calc_resolved.meta else None,
                "path": str(calc_dir.relative_to(self._service.project_root)),
                "absolute_path": str(calc_dir),
                "structure": structure_name,
                "structure_ulid": structure_ulid,
                "structure_name": structure_name,
                "structure_elements": structure_elements,
                "engine_family": getattr(calc_model, 'engine_family', None),
                "steps": step_summaries,
                "n_steps": len(step_summaries),
                "mode": calc_model.mode.value if hasattr(calc_model.mode, "value") else str(calc_model.mode) if calc_model.mode else "normal",
                "species_map": getattr(calc_model, 'species_map', None),
            }

        def set_structure(
            self,
            calc_selector: str,
            structure_selector: str,
            update_steps: bool = True,
        ) -> dict:
            """
            Change the structure associated with a calculation.

            Args:
                calc_selector: Calculation selector (ULID)
                structure_selector: New structure selector (ULID)
                update_steps: Whether to also update all steps' structure field

            Returns:
                Updated calculation info with any warnings

            Raises:
                APIError: If calculation or structure not found
            """
            try:
                from qmatsuite.core.resolution import require_calculation, resolve_structure
                from qmatsuite.core.models import load_calculation, save_calculation
                from qmatsuite.core.project_utils import load_project_config
                from qmatsuite.core.resolution import make_structure_selector_resolver
                from qmatsuite.calculation.structure_steps import StructureStepSpec
                from qmatsuite.core.yamldoc import StepDoc
                from qmatsuite.workflow.step_factory import save_step_doc

                # Resolve calculation and structure
                calc_resolved = require_calculation(self._service.project_root, calc_selector)
                struct_resolved = resolve_structure(self._service.project_root, structure_selector)

                # Get calculation directory
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                    calc_yaml = calc_resolved.absolute_path
                else:
                    calc_dir = calc_resolved.absolute_path
                    calc_yaml = calc_dir / "calculation.yaml"

                # Load and update calculation model
                config = load_project_config(self._service.project_root)
                resolver = make_structure_selector_resolver(self._service.project_root, config=config)
                calc_model = load_calculation(calc_yaml, project_root=self._service.project_root, resolve_structure_selector=resolver)

                old_structure = calc_model.structure_name or calc_model.structure
                calc_model.structure_ulid = struct_resolved.meta.ulid
                calc_model.structure_name = struct_resolved.meta.name
                calc_model.structure = struct_resolved.meta.slug
                save_calculation(calc_model, calc_yaml)

                warnings = []
                updated_steps = []

                if update_steps:
                    steps_dir = calc_dir / "steps"
                    if steps_dir.exists():
                        for step_file in steps_dir.glob("*.step.yaml"):
                            try:
                                spec = StructureStepSpec.from_yaml(step_file, resolve_structure_selector=resolver)
                                step_doc = StepDoc.load(step_file)
                                current_structure_ulid = step_doc.get(["structure_ulid"], default=None)

                                if current_structure_ulid != struct_resolved.meta.ulid:
                                    old_step_struct_id = current_structure_ulid
                                    step_doc.set(["structure_ulid"], struct_resolved.meta.ulid)
                                    step_doc.set(["structure"], "")
                                    save_step_doc(step_doc, step_file)
                                    updated_steps.append({
                                        "step_ulid": spec.meta.ulid,
                                        "step_ulid": spec.meta.ulid,  # Backwards compat
                                        "old_structure_ulid": old_step_struct_id,
                                        "new_structure_ulid": struct_resolved.meta.ulid,
                                    })
                            except Exception as e:
                                warnings.append(f"Failed to update step {step_file.name}: {e}")

                # Return updated calculation detail
                result = self.get_detail(calc_selector)
                result["old_structure"] = old_structure
                result["updated_steps"] = updated_steps
                result["warnings"] = warnings
                return result

            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def get_common_cards(
            self,
            calc_selector: str,
            step_selector: str,
        ) -> dict:
            """
            Get view models for common cards (K_POINTS, etc.).

            Args:
                calc_selector: Calculation selector (ULID)
                step_selector: Step selector

            Returns:
                Dict with card view models, e.g. {"k_points": KPointsViewModel}

            Raises:
                APIError: If calculation or step not found
            """
            try:
                from qmatsuite.core.resolution import require_calculation, require_step
                from qmatsuite.calculation.k_points_view import parse_k_points, k_points_from_card_data
                import yaml

                # Resolve step
                step_resolved = require_step(
                    self._service.project_root,
                    calc_selector,
                    step_selector
                )

                # Load step data
                step_data = yaml.safe_load(step_resolved.absolute_path.read_text())

                result = {}

                # Parse K_POINTS if present
                cards = step_data.get("cards", {})
                if "K_POINTS" in cards:
                    card_data = cards["K_POINTS"]
                    raw = k_points_from_card_data(card_data)
                    view_model = parse_k_points(raw)
                    result["k_points"] = {
                        "raw": view_model.raw,
                        "mode": view_model.mode,
                        "automatic": {
                            "nk1": view_model.automatic.nk1,
                            "nk2": view_model.automatic.nk2,
                            "nk3": view_model.automatic.nk3,
                            "sk1": view_model.automatic.sk1,
                            "sk2": view_model.automatic.sk2,
                            "sk3": view_model.automatic.sk3,
                        } if view_model.automatic else None,
                        "points": [
                            {"x": p.x, "y": p.y, "z": p.z, "w": p.w}
                            for p in (view_model.points or [])
                        ],
                        "parse_ok": view_model.parse_ok,
                        "canonical_raw": view_model.canonical_raw,
                        "warnings": view_model.warnings,
                        "errors": view_model.errors,
                        "summary": view_model.summary,
                    }

                return result
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def set_engine_family(
            self,
            calc_selector: str,
            engine_family: str,
        ) -> CalculationDTO:
            """
            Set engine_family on a calculation (UNDECIDED -> DECIDED transition).

            Args:
                calc_selector: Calculation selector (slug, ULID, or name)
                engine_family: Engine to set (e.g., "qe", "vasp")

            Returns:
                Updated CalculationDTO

            Raises:
                APIError: If calculation not found or engine_family invalid
            """
            try:
                from qmatsuite.api.utils import validate_engine_family
                from qmatsuite.core.resolution import require_calculation
                from qmatsuite.core.models import load_calculation, save_calculation

                # Validate engine_family is registered and is a base engine
                is_valid, error_msg = validate_engine_family(engine_family)
                if not is_valid:
                    raise ValueError(error_msg)

                # Resolve calculation
                calc_resolved = require_calculation(self._service.project_root, calc_selector)
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path

                # Load, update, save
                calc_yaml = calc_dir / "calculation.yaml"
                calc_model = load_calculation(calc_yaml, self._service.project_root)
                calc_model.engine_family = engine_family
                save_calculation(calc_model, calc_dir)

                # Return updated DTO
                return self.get(calc_selector)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def apply_presets(
            self,
            calc_selector: str,
            presets: dict,
            *,
            validate_physics: bool = True,
        ) -> dict:
            """
            Apply preset options to ALL steps in a calculation (BROADCAST).

            Per Constitution §10.3.3: This OVERWRITES preset-related parameters.

            Args:
                calc_selector: Calculation selector (slug, ULID, or name)
                presets: Dict with preset options (e.g., {"spin": "collinear", "precision": "med"})
                validate_physics: Validate physics constraints (default True)

            Returns:
                Dict with status, steps_updated, steps_skipped, step_results, dimension_states
            """
            try:
                import yaml
                from qmatsuite.presets.compiler import PresetCompilationError
                from qmatsuite.presets.precision_context import PrecisionContextError
                from qmatsuite.presets.dimensions import DIMENSION_PRECISION, PrecisionOption
                from qmatsuite.api.utils import (
                    apply_presets_to_step,
                    get_calculation_preset_bundle,
                )
                from qmatsuite.presets.precision_context import resolve_precision_context
                from qmatsuite.core.resolution import require_calculation

                calc_resolved = require_calculation(self._service.project_root, calc_selector)
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calculation_dir = calc_resolved.absolute_path.parent
                else:
                    calculation_dir = calc_resolved.absolute_path
                steps_dir = calculation_dir / "steps"

                # Precision advisor setup
                precision_advisor = None
                precision_option = presets.get(DIMENSION_PRECISION) or presets.get("precision")
                if precision_option:
                    try:
                        context = resolve_precision_context(
                            calculation_dir=calculation_dir,
                            project_root=self._service.project_root,
                        )
                        from qmatsuite.api.utils import create_precision_advisor
                        precision_advisor = create_precision_advisor(
                            species_map=context.species_map,
                            lattice_matrix=context.lattice_matrix,
                            repo_root=self._service.project_root,
                        )
                    except PrecisionContextError as e:
                        raise APIError(f"Failed to resolve precision context: {e}") from e

                step_files = sorted(steps_dir.glob("*.step.yaml"))
                steps_updated = 0
                steps_skipped = 0
                step_results = []

                for step_path in step_files:
                    step_name = step_path.name
                    step_type_gen = "unknown"
                    try:
                        content = yaml.safe_load(step_path.read_text()) or {}
                        step_type_gen = content.get("step_type_gen", content.get("step_type_spec", "scf"))

                        precision_advice = None
                        if precision_advisor and precision_option:
                            try:
                                precision_level = PrecisionOption(precision_option)
                                precision_advice = precision_advisor.advise_for_step(precision_level, step_type_gen)
                            except (ValueError, KeyError):
                                pass

                        result = apply_presets_to_step(
                            step_path, presets,
                            validate_physics=validate_physics,
                            precision_advice=precision_advice,
                        )

                        if result["accepted"]:
                            steps_updated += 1
                            step_results.append({
                                "step_file": step_name,
                                "step_type_gen": step_type_gen,
                                "status": "updated",
                                "applied_presets": list(result["filtered_options"].keys()),
                                "updated_fields": result.get("updated_fields", []),
                                "skipped_fields": result.get("skipped_fields", []),
                            })
                        else:
                            steps_skipped += 1
                            step_results.append({
                                "step_file": step_name,
                                "step_type_gen": step_type_gen,
                                "status": "skipped",
                                "reason": "non-receiver",
                                "updated_fields": [],
                                "skipped_fields": result.get("skipped_fields", ["non-receiver step"]),
                            })
                    except PresetCompilationError:
                        steps_skipped += 1
                        step_results.append({
                            "step_file": step_name,
                            "step_type_gen": step_type_gen,
                            "status": "error",
                            "reason": str(e),
                            "updated_fields": [],
                            "skipped_fields": [],
                        })
                    except Exception as e:
                        steps_skipped += 1
                        step_results.append({
                            "step_file": step_name,
                            "step_type_gen": step_type_gen,
                            "status": "error",
                            "reason": str(e),
                            "updated_fields": [],
                            "skipped_fields": [],
                        })

                bundle = get_calculation_preset_bundle(calculation_dir)
                return {
                    "status": "applied",
                    "steps_updated": steps_updated,
                    "steps_skipped": steps_skipped,
                    "step_results": step_results,
                    "dimension_states": bundle["dimension_states"],
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def add_step(
            self,
            calc_selector: str,
            step_type_gen: str,
            *,
            name: str | None = None,
            params: dict | None = None,
            cards: dict | None = None,
            species_overrides: dict | None = None,
            step_spec: dict | None = None,
            index: int | None = None,
        ) -> StepDTO:
            """
            Add a step to a calculation.

            Args:
                calc_selector: Calculation selector
                step_type_gen: Step type (e.g., "scf", "nscf" - gen type, or "qe_scf" - spec type, accepts both)
                name: Optional step name (defaults to step_type_gen)
                params: Optional parameter overrides (applied via apply_patch, respects managed keys)
                cards: Optional card overrides (e.g., K_POINTS)
                species_overrides: Optional species overrides
                step_spec: Optional full step spec dict (if provided, overrides other params)
                index: Optional insertion index (0-indexed, defaults to append)

            Returns:
                StepDTO for the new step

            Raises:
                NotFoundError: If calculation not found
                ValidationError: If step_type_gen is invalid or unmapped
                APIError: For other step creation failures
            """
            try:
                from qmatsuite.core.resolution import require_calculation, require_step
                from qmatsuite.core.models import load_calculation, save_calculation
                from qmatsuite.project.model import Project
                from qmatsuite.calculation.calculation import Calculation
                from qmatsuite.workflow.step_factory import create_and_save_step
                from qmatsuite.workflow.registry import get_registry
                from qmatsuite.core.resources import generate_resource_id
                import yaml
                
                # Resolve calculation
                calc_resolved = require_calculation(self._service.project_root, calc_selector)
                
                # Get calculation directory
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path
                
                calc_yaml = calc_dir / "calculation.yaml"
                calc_model = load_calculation(calc_yaml, self._service.project_root)
                
                # Get calculation ULID
                calc_ulid = calc_resolved.meta.ulid if calc_resolved.meta else ""
                
                # Get structure_ulid from calculation
                structure_ulid = calc_model.structure_ulid if calc_model else None
                
                # Determine step name
                step_name = name or step_type_gen

                # Validate step_type_gen and get spec type for calculation.yaml
                # Use engine_family to pick the correct engine-specific step type
                registry = get_registry()
                engine_family = getattr(calc_model, 'engine_family', None)
                if engine_family is None:
                    raise ValueError(
                        f"Cannot add step '{step_type_gen}' to calculation without engine_family. "
                        "Set engine_family on the calculation first."
                    )
                spec = registry.get_for_engine(step_type_gen, engine_family)
                if not spec:
                    # Try companion engines (e.g., w90 in QE calc, yambo in QE calc)
                    from qmatsuite.core.driver_registry import DriverRegistry
                    from qmatsuite.workflow.step_type_convert import gen_from
                    resolved = DriverRegistry.resolve_companion_step(
                        engine_family, step_type_gen
                    )
                    if resolved is not None:
                        resolved_step_type_gen = gen_from(resolved)
                        spec = registry.get(resolved_step_type_gen)
                if not spec:
                    from qmatsuite.api.errors import ValidationError
                    raise ValidationError(
                        f"No step type '{step_type_gen}' registered for engine "
                        f"'{engine_family}' or its companion engines",
                        code="VALIDATION_FAILED",
                        context={"step_type_gen": step_type_gen, "engine_family": engine_family}
                    )
                
                # Use gen type for calculation.yaml (registry.get() accepts both gen and spec types)
                public_step_type = spec.step_type_gen
                
                # Create steps directory
                steps_dir = calc_dir / "steps"
                steps_dir.mkdir(parents=True, exist_ok=True)

                # Generate unique slug (deduplicate against existing step files)
                from qmatsuite.core.resources import slugify
                base_slug = slugify(step_name)
                unique_slug = base_slug
                suffix = 1
                while (steps_dir / f"{unique_slug}.step.yaml").exists():
                    unique_slug = f"{base_slug}-{suffix}"
                    suffix += 1

                # Use unique_slug as name (step factory uses name for slug)
                unique_name = unique_slug if unique_slug != base_slug else step_name

                # Create and save step using canonical factory
                # Factory expects gen type - convert spec to gen
                step_path = create_and_save_step(
                    step_type_gen=spec.step_type_gen,  # Use gen type (e.g., "relax")
                    engine_family=spec.engine,  # Provide engine for materialization
                    name=unique_name,
                    steps_dir=steps_dir,
                    structure_ulid=structure_ulid,
                    parent_calculation_id=calc_ulid,
                    overrides=params,  # apply_patch will be called inside create_step_doc
                )
                
                # Read step file to get step_ulid
                step_data = yaml.safe_load(step_path.read_text())
                step_ulid = step_data.get("meta", {}).get("ulid") or step_data.get("meta", {}).get("ulid")
                if not step_ulid:
                    from qmatsuite.api.errors import InternalError
                    raise InternalError(
                        "Step created but missing ULID in meta",
                        context={"step_path": str(step_path)}
                    )
                
                # Add step to calculation.yaml steps array
                # Use step_type_spec (SPEC value) for calculation.yaml
                from qmatsuite.core.models import CalculationStepEntry
                step_entry = CalculationStepEntry(
                    step_ulid=step_ulid,
                    step_type_spec=spec.step_type_spec,  # SPEC type (e.g., "qe_scf")
                )
                
                # Update calculation model
                if not hasattr(calc_model, 'steps') or calc_model.steps is None:
                    calc_model.steps = []
                calc_model.steps.append(step_entry)
                
                # Save calculation.yaml
                save_calculation(calc_model, calc_yaml)
                
                # Build ResolvedResource and Step object from step_data for DTO
                # (We don't resolve via require_step because ResourceIndex may not be updated yet)
                from qmatsuite.core.resources import ResourceMeta
                from qmatsuite.core.resolution import ResolvedResource
                from qmatsuite.calculation.step import Step
                
                step_meta_dict = step_data.get("meta", {})
                step_meta = ResourceMeta.from_dict(
                    step_meta_dict,
                    kind="step",
                    default_name=step_name,
                    default_path=str(step_path.relative_to(self._service.project_root))
                )
                step_resolved = ResolvedResource(
                    meta=step_meta,
                    entry={},  # Empty entry - step not in project config
                    absolute_path=step_path
                )
                
                # Get step_type_spec from step_data (machine type)
                step_type_spec = step_data.get("step_type_spec", public_step_type)
                # Get engine from registry (registry.get expects GEN)
                from qmatsuite.workflow.step_type_convert import gen_from
                step_type_gen = gen_from(step_type_spec)
                step_spec = registry.get(step_type_gen)
                if step_spec is None:
                    from qmatsuite.workflow.step_type_convert import prefix_from
                    engine = prefix_from(step_type_spec)
                else:
                    engine = step_spec.engine
                # Create minimal Step object
                step_obj = Step(
                    meta=step_meta,
                    input_file=step_path,  # Placeholder - not used for DTO
                    engine=engine,
                    step_type_spec=step_type_spec,
                )
                
                # Build StepDTO
                return step_to_dto(
                    step_resolved=step_resolved,
                    step_obj=step_obj,
                    calc_ulid=calc_ulid,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def add_step_from_spec(
            self,
            calc_selector: str,
            step_spec: dict,
            *,
            index: int | None = None,
        ) -> dict:
            """
            Add a step to a calculation using a pre-built step spec dict.

            This is the Law H9 compliant way for CLI to add steps.
            CLI builds the spec dict (with all its complex logic like --auto-kpath,
            --no-defaults, etc.), then passes it to this method for file writing.

            Args:
                calc_selector: Calculation selector (ULID or slug)
                step_spec: Complete step spec dict (must have meta.ulid, step_type_spec, etc.)
                index: Optional insertion index (0-indexed, defaults to append)

            Returns:
                Dict with step_path and step_ulid

            Raises:
                NotFoundError: If calculation not found
                ValidationError: If step_spec is missing required fields
            """
            try:
                from qmatsuite.core.resolution import require_calculation
                from qmatsuite.core.models import load_calculation, save_calculation, CalculationStepEntry
                from qmatsuite.core.yamldoc import StepDoc
                from qmatsuite.workflow.step_factory import save_step_doc
                import yaml

                # Validate step_spec has required fields
                meta = step_spec.get("meta", {})
                step_ulid = meta.get("ulid")
                step_type_spec = step_spec.get("step_type_spec")
                if not step_ulid:
                    from qmatsuite.api.errors import ValidationError
                    raise ValidationError(
                        "step_spec.meta.ulid is required",
                        code="VALIDATION_FAILED"
                    )
                if not step_type_spec:
                    from qmatsuite.api.errors import ValidationError
                    raise ValidationError(
                        "step_spec.step_type_spec is required",
                        code="VALIDATION_FAILED"
                    )

                # Resolve calculation
                calc_resolved = require_calculation(self._service.project_root, calc_selector)

                # Get calculation directory
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                else:
                    calc_dir = calc_resolved.absolute_path

                calc_yaml = calc_dir / "calculation.yaml"
                calc_model = load_calculation(calc_yaml, self._service.project_root)
                calc_ulid = calc_resolved.meta.ulid if calc_resolved.meta else ""

                # Create steps directory
                steps_dir = calc_dir / "steps"
                steps_dir.mkdir(parents=True, exist_ok=True)

                # Determine step file path from meta.slug or meta.name
                step_slug = meta.get("slug") or meta.get("name") or step_ulid[:8]
                step_path = steps_dir / f"{step_slug}.step.yaml"

                # Update meta.path in spec
                from qmatsuite.api.utils import ensure_relative_path
                rel_path = ensure_relative_path(step_path, base=self._service.project_root)
                step_spec["meta"]["path"] = str(rel_path)

                # Create StepDoc and save via journaled path
                step_doc = StepDoc(data=step_spec)
                save_step_doc(step_doc, step_path)

                # Add step to calculation.yaml steps array
                step_entry = CalculationStepEntry(
                    step_ulid=step_ulid,
                    step_type_spec=step_type_spec,
                )

                # Determine insertion index
                if not hasattr(calc_model, 'steps') or calc_model.steps is None:
                    calc_model.steps = []

                if index is not None:
                    insert_at = max(0, min(len(calc_model.steps), index))
                    calc_model.steps.insert(insert_at, step_entry)
                else:
                    calc_model.steps.append(step_entry)

                # Save calculation.yaml
                save_calculation(calc_model, calc_yaml)

                return {
                    "step_path": str(step_path),
                    "step_ulid": step_ulid,
                    "calc_ulid": calc_ulid,
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def remove_step(self, calc_selector: str, step_selector: str) -> None:
            """
            Remove a step from a calculation.
            
            Removes step from calculation.yaml steps array and moves step file to trash.
            Handles ghost steps (missing files) gracefully.
            
            Args:
                calc_selector: Calculation selector
                step_selector: Step selector (ULID)
                
            Raises:
                NotFoundError: If calculation or step not found in calculation.yaml
                APIError: For other removal failures
            """
            try:
                from qmatsuite.core.resolution import require_calculation, require_step, ResourceNotFoundError
                from qmatsuite.core.models import load_calculation, save_calculation
                from qmatsuite.core.project_utils import load_project_config, move_to_trash
                from qmatsuite.core.resolution import make_structure_selector_resolver
                import yaml
                
                # Resolve calculation
                calc_resolved = require_calculation(self._service.project_root, calc_selector)
                
                # Get calculation directory
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                    calc_yaml = calc_resolved.absolute_path
                else:
                    calc_dir = calc_resolved.absolute_path
                    calc_yaml = calc_dir / "calculation.yaml"
                
                # Load calculation model
                config = load_project_config(self._service.project_root)
                resolver = make_structure_selector_resolver(self._service.project_root, config=config)
                calc_model = load_calculation(calc_yaml, project_root=self._service.project_root, resolve_structure_selector=resolver)
                
                # Find step in calculation.yaml steps array
                step_ulid = step_selector
                step_entry = None
                for entry in calc_model.steps:
                    if entry.step_ulid == step_ulid:
                        step_entry = entry
                        break
                
                if step_entry is None:
                    from qmatsuite.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Step '{step_selector}' not found in calculation",
                        context={"calc_selector": calc_selector, "step_selector": step_selector}
                    )
                
                # Remove step entry from calculation model
                calc_model.steps = [e for e in calc_model.steps if e.step_ulid != step_ulid]
                
                # Save calculation.yaml
                save_calculation(calc_model, calc_yaml)
                
                # Try to move step file to trash (handle ghost steps gracefully)
                trash_dir = (self._service.project_root / "trash").resolve()
                try:
                    step_resolved = require_step(
                        self._service.project_root,
                        calc_selector,
                        step_selector
                    )
                    step_path = step_resolved.absolute_path
                    if step_path.exists():
                        move_to_trash(step_path, trash_dir)
                except (ResourceNotFoundError, FileNotFoundError):
                    # Ghost step - file already missing, just continue
                    pass
                
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def rename_step(
            self,
            calc_selector: str,
            step_selector: str,
            new_name: str,
            *,
            new_path: str | None = None,
            index: Any = None,
            config: dict | None = None,
        ) -> dict:
            """
            Rename a step or relocate its spec file (Law H9 compliant).

            Updates step meta (name, slug), optionally moves file, and updates
            calculation.yaml step entry.

            Args:
                calc_selector: Calculation selector
                step_selector: Current step selector (ULID)
                new_name: New step name
                new_path: Optional new path for step file (relative to calculation dir)
                index: Optional ResourceIndex
                config: Optional project config

            Returns:
                Dict with old_name, new_name, new_slug, step_path
            """
            try:
                from qmatsuite.core.resolution import require_calculation, require_step
                from qmatsuite.core.models import load_calculation, save_calculation
                from qmatsuite.core.project_utils import load_project_config
                from qmatsuite.core.yamldoc import StepDoc
                from qmatsuite.workflow.step_factory import save_step_doc
                from qmatsuite.core.resources import slugify
                from qmatsuite.api.utils import ensure_relative_path
                import shutil

                if config is None:
                    config = load_project_config(self._service.project_root)

                # Resolve calculation and step
                calc_resolved = require_calculation(self._service.project_root, calc_selector, config=config, index=index)
                step_resolved = require_step(self._service.project_root, calc_selector, step_selector)

                # Get paths
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                    calc_yaml = calc_resolved.absolute_path
                else:
                    calc_dir = calc_resolved.absolute_path
                    calc_yaml = calc_dir / "calculation.yaml"

                step_path = step_resolved.absolute_path
                old_name = step_resolved.meta.name

                # Load calculation model
                from qmatsuite.core.resolution import make_structure_selector_resolver
                resolver = make_structure_selector_resolver(self._service.project_root, config=config)
                calc_model = load_calculation(calc_yaml, project_root=self._service.project_root, resolve_structure_selector=resolver)

                # Find and update step entry
                step_ulid = step_resolved.meta.ulid
                step_entry = None
                for entry in calc_model.steps:
                    if entry.step_ulid == step_ulid:
                        step_entry = entry
                        break

                if step_entry is None:
                    from qmatsuite.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Step '{step_selector}' not found in calculation",
                        context={"calc_selector": calc_selector, "step_selector": step_selector}
                    )

                # Update step entry ULID to new name
                new_slug = slugify(new_name)
                step_entry.step_ulid = new_slug

                # Handle file move/rename
                destination_path = step_path
                if new_path:
                    # Explicit new path
                    dest = Path(new_path)
                    if not dest.is_absolute():
                        destination_path = (calc_dir / dest).resolve()
                    else:
                        destination_path = dest.resolve()
                    destination_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(step_path), str(destination_path))
                else:
                    # Auto-rename file to match new name
                    new_filename = step_path.with_name(f"{new_slug}.step.yaml")
                    if new_filename != step_path:
                        if new_filename.exists():
                            from qmatsuite.api.errors import ValidationError
                            raise ValidationError(
                                f"Step file '{new_filename.name}' already exists",
                                context={"existing_file": str(new_filename)}
                            )
                        destination_path = new_filename
                        destination_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(step_path), str(destination_path))

                # Update step spec meta
                step_doc = StepDoc.load(destination_path)
                relative_project = ensure_relative_path(destination_path, base=self._service.project_root)
                step_doc.set(["meta", "name"], new_name)
                step_doc.set(["meta", "slug"], new_slug)
                step_doc.set(["meta", "path"], relative_project)
                save_step_doc(step_doc, destination_path)

                # Save calculation.yaml
                save_calculation(calc_model, calc_yaml)

                return {
                    "success": True,
                    "old_name": old_name,
                    "new_name": new_name,
                    "new_slug": new_slug,
                    "step_path": str(destination_path),
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def rename(
            self,
            selector: str,
            new_name: str,
            *,
            index: Any = None,
            config: dict | None = None,
        ) -> dict:
            """
            Rename a calculation.

            Args:
                selector: Calculation selector
                new_name: New name for the calculation
                index: Optional ResourceIndex (for in-place updates)
                config: Optional project config

            Returns:
                Dict with old_name, new_name, new_slug
            """
            try:
                from qmatsuite.core.resolution import resolve_calculation
                from qmatsuite.core.project_utils import load_project_config, find_calculation_entry
                from qmatsuite.core.resources import slugify

                if config is None:
                    config = load_project_config(self._service.project_root)

                resolved = resolve_calculation(self._service.project_root, selector, config=config, index=index)
                old_name = resolved.meta.name
                calculation_id = resolved.meta.ulid

                # Use update_meta to update name
                self.update_meta(selector, name=new_name)

                return {
                    "success": True,
                    "old_name": old_name,
                    "new_name": new_name,
                    "new_slug": slugify(new_name),
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def set_common_card(
            self,
            calc_selector: str,
            step_selector: str,
            card_name: str,
            view_model: dict,
            *,
            index: Any = None,
            config: dict | None = None,
        ) -> dict:
            """
            Set a common card (K_POINTS, etc.) from view model.

            Args:
                calc_selector: Calculation selector (ULID)
                step_selector: Step selector
                card_name: Card name (e.g., "K_POINTS")
                view_model: View model dict from UI
                index: Optional ResourceIndex
                config: Optional project config

            Returns:
                Updated step detail dict
            """
            try:
                from qmatsuite.core.resolution import validate_ulid, resolve_step, make_structure_selector_resolver
                from qmatsuite.calculation.k_points_view import (
                    KPointsViewModel, KPointsAutomatic, KPointsPoint,
                    format_k_points, k_points_to_card_data,
                )
                from qmatsuite.calculation.structure_steps import StructureStepSpec
                from qmatsuite.core.project_utils import load_project_config
                from qmatsuite.core.yamldoc import StepDoc
                from qmatsuite.workflow.step_factory import save_step_doc

                # Validate ULID
                calc_ulid = validate_ulid(calc_selector, kind="calculation")

                if config is None:
                    config = load_project_config(self._service.project_root)

                step = resolve_step(self._service.project_root, calc_ulid, step_selector, config=config, index=index)

                # Convert view model to raw text based on card type
                if card_name.upper() == "K_POINTS":
                    kp_vm = KPointsViewModel(
                        raw=view_model.get("raw", ""),
                        mode=view_model.get("mode", "custom"),
                        automatic=KPointsAutomatic(**view_model["automatic"]) if view_model.get("automatic") else None,
                        points=[
                            KPointsPoint(x=p["x"], y=p["y"], z=p["z"], w=p["w"])
                            for p in (view_model.get("points") or [])
                        ] if view_model.get("points") else None,
                        warnings=view_model.get("warnings"),
                    )
                    raw = format_k_points(kp_vm)
                    card_data = k_points_to_card_data(raw)

                    step_doc = StepDoc.load(step.absolute_path)
                    # cards.K_POINTS is a dict subtree; StepDoc.set() rejects dict writes.
                    # Use apply_patch() so set_common_card can persist card payloads from GUI/RPC.
                    step_doc.apply_patch({"cards": {"K_POINTS": card_data}})
                    save_step_doc(step_doc, step.absolute_path)
                else:
                    from qmatsuite.api.errors import ValidationError
                    raise ValidationError(f"Unsupported card: {card_name}")

                # Return updated step detail
                return self.get_step_detail(calc_selector, step_selector)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def get_step_pseudo_mapping(
            self,
            calc_selector: str,
            step_selector: str,
            *,
            index: Any = None,
            config: dict | None = None,
        ) -> dict:
            """
            Get pseudopotential mapping for a step.

            Args:
                calc_selector: Calculation selector (ULID)
                step_selector: Step selector
                index: Optional ResourceIndex
                config: Optional project config

            Returns:
                Dict with species, mapping, pseudo_dir, available_pseudos, warnings
            """
            try:
                from qmatsuite.core.resolution import validate_ulid, resolve_structure
                from qmatsuite.core.project_utils import load_project_config
                from qmatsuite.io import read_structure
                from qmatsuite.core.pseudo_config import PseudoConfig
                from qmatsuite.core.paths import home_pseudo_libraries_dir
                import json

                # Validate ULID
                calc_ulid = validate_ulid(calc_selector, kind="calculation")

                # Get step detail
                step_detail = self.get_step_detail(calc_selector, step_selector)

                if config is None:
                    config = load_project_config(self._service.project_root)

                # Get species list from structure
                species_list: list[str] = []
                if step_detail.get("structure"):
                    try:
                        structure = resolve_structure(
                            self._service.project_root, step_detail["structure"], config=config, index=index
                        )
                        if structure.absolute_path.exists():
                            struct_obj = read_structure(structure.absolute_path)
                            species_set = set()
                            species_list = []
                            for site in struct_obj.sites:
                                symbol = site.specie.symbol
                                if symbol not in species_set:
                                    species_set.add(symbol)
                                    species_list.append(symbol)
                    except Exception:
                        pass

                # Get current mapping from species_overrides
                mapping: dict[str, str] = {}
                species_overrides = step_detail.get("species_overrides", {})
                for species, overrides in species_overrides.items():
                    if isinstance(overrides, dict) and "pseudopot" in overrides:
                        mapping[species] = str(overrides["pseudopot"])

                # Get pseudo_dir from CONTROL namelist
                pseudo_dir = ""
                parameters = step_detail.get("parameters", {})
                control_params = parameters.get("CONTROL", {})
                if isinstance(control_params, dict) and "pseudo_dir" in control_params:
                    pseudo_dir = str(control_params["pseudo_dir"])

                # List available UPF files in project
                available_pseudos: list[str] = []
                project_pseudo_dir = self._service.project_root / "pseudo"
                if project_pseudo_dir.exists():
                    for file in project_pseudo_dir.iterdir():
                        if file.is_file() and file.suffix.lower() == ".upf":
                            available_pseudos.append(file.name)
                available_pseudos.sort()

                # Check SSSP libraries (NEW layout via shared utility)
                sssp_defaults: dict[str, dict[str, str]] = {}
                sssp_installed: dict[str, bool] = {"precision": False, "efficiency": False}
                try:
                    from qmatsuite.pseudo.layout import iter_installed_libraries

                    libraries_root = home_pseudo_libraries_dir()
                    for lib in iter_installed_libraries(libraries_root):
                        if lib.library_key.lower() != "sssp":
                            continue
                        if lib.variant not in sssp_installed:
                            continue
                        upf_files = [f for f in lib.install_dir.iterdir() if f.suffix.lower() == ".upf"]
                        if upf_files:
                            sssp_installed[lib.variant] = True
                        # Check cutoffs JSON companion
                        for cutoffs_candidate in lib.install_dir.glob("*cutoffs*.json"):
                            try:
                                cutoffs_data = json.loads(cutoffs_candidate.read_text())
                                for species in species_list:
                                    if species not in sssp_defaults:
                                        sssp_defaults[species] = {"precision": "", "efficiency": ""}
                                    element_data = cutoffs_data.get(species, {})
                                    filename = element_data.get("filename", "")
                                    if filename and (lib.install_dir / filename).exists():
                                        sssp_defaults[species][lib.variant] = filename
                            except Exception:
                                pass
                except Exception:
                    pass

                # Generate warnings
                warnings: list[str] = []
                for species in species_list:
                    if species not in mapping:
                        warnings.append(f"Missing pseudopotential for {species}")
                    elif mapping[species] and mapping[species] not in available_pseudos:
                        warnings.append(f"Pseudopotential file '{mapping[species]}' not found in project")

                return {
                    "species": species_list,
                    "mapping": mapping,
                    "pseudo_dir": pseudo_dir,
                    "available_pseudos": available_pseudos,
                    "warnings": warnings,
                    "sssp_defaults": sssp_defaults,
                    "sssp_installed": sssp_installed,
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def set_step_pseudo_mapping(
            self,
            calc_selector: str,
            step_selector: str,
            mapping: dict[str, str],
            library_preference: str | None = None,
            *,
            index: Any = None,
            config: dict | None = None,
        ) -> dict:
            """
            Set pseudopotential mapping for a step.

            Args:
                calc_selector: Calculation selector (ULID)
                step_selector: Step selector
                mapping: Species -> pseudo filename mapping
                library_preference: Optional library preference
                index: Optional ResourceIndex
                config: Optional project config

            Returns:
                Updated step detail dict
            """
            try:
                from qmatsuite.core.resolution import validate_ulid, resolve_step, make_structure_selector_resolver
                from qmatsuite.calculation.structure_steps import StructureStepSpec
                from qmatsuite.core.project_utils import load_project_config
                from qmatsuite.core.yamldoc import StepDoc
                from qmatsuite.workflow.step_factory import save_step_doc

                # Validate ULID
                calc_ulid = validate_ulid(calc_selector, kind="calculation")

                if config is None:
                    config = load_project_config(self._service.project_root)

                step = resolve_step(self._service.project_root, calc_ulid, step_selector, config=config, index=index)

                # Load step spec
                resolver = make_structure_selector_resolver(self._service.project_root, config=config)
                spec = StructureStepSpec.from_yaml(step.absolute_path, resolve_structure_selector=resolver)

                # Update species_overrides
                if not spec.species_overrides:
                    spec.species_overrides = {}

                for species, pseudo_filename in mapping.items():
                    if species not in spec.species_overrides:
                        spec.species_overrides[species] = {}

                    if pseudo_filename:
                        spec.species_overrides[species]["pseudopot"] = str(pseudo_filename)
                    else:
                        if "pseudopot" in spec.species_overrides[species]:
                            del spec.species_overrides[species]["pseudopot"]
                        if not spec.species_overrides[species]:
                            del spec.species_overrides[species]

                # Save via StepDoc
                step_doc = StepDoc.load(step.absolute_path)
                step_doc.apply_patch({"species_overrides": spec.species_overrides})
                save_step_doc(step_doc, step.absolute_path)

                return self.get_step_detail(calc_selector, step_selector)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def reset_step_params(
            self,
            calc_selector: str,
            step_selector: str,
            *,
            index: Any = None,
            config: dict | None = None,
        ) -> dict:
            """
            Reset step parameters to defaults based on step type.

            Args:
                calc_selector: Calculation selector
                step_selector: Step selector
                index: Optional ResourceIndex
                config: Optional project config

            Returns:
                Updated step detail dict
            """
            try:
                from qmatsuite.core.resolution import resolve_step, make_structure_selector_resolver
                from qmatsuite.calculation.structure_steps import StructureStepSpec
                from qmatsuite.calculation.step_defaults import get_default_step_params
                from qmatsuite.core.project_utils import load_project_config
                from qmatsuite.core.yamldoc import StepDoc
                from qmatsuite.workflow.step_factory import save_step_doc

                if config is None:
                    config = load_project_config(self._service.project_root)

                step = resolve_step(self._service.project_root, calc_selector, step_selector, config=config, index=index)

                # Load step spec to get step_type
                resolver = make_structure_selector_resolver(self._service.project_root, config=config)
                spec = StructureStepSpec.from_yaml(step.absolute_path, resolve_structure_selector=resolver)

                # Get defaults for this step type
                defaults = get_default_step_params(spec.step_type_spec)

                # Reset parameters and cards via StepDoc
                step_doc = StepDoc.load(step.absolute_path)
                step_doc.apply_patch({
                    "parameters": defaults.get("parameters", {}),
                    "cards": defaults.get("cards", {}),
                    "species_overrides": defaults.get("species_overrides", {}),
                })
                save_step_doc(step_doc, step.absolute_path)

                return self.get_step_detail(calc_selector, step_selector)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def reorder_steps(
            self,
            calc_selector: str,
            new_order: list[str],
            *,
            index: Any = None,
            config: dict | None = None,
        ) -> dict:
            """
            Reorder calculation steps.

            Args:
                calc_selector: Calculation selector
                new_order: List of step IDs/slugs in new order
                index: Optional ResourceIndex
                config: Optional project config

            Returns:
                Updated calculation info dict
            """
            try:
                from qmatsuite.core.resolution import resolve_calculation
                from qmatsuite.core.models import load_calculation, save_calculation
                from qmatsuite.core.project_utils import load_project_config
                from qmatsuite.api.errors import ValidationError

                if config is None:
                    config = load_project_config(self._service.project_root)

                calculation = resolve_calculation(self._service.project_root, calc_selector, config=config, index=index)
                wf_path = calculation.absolute_path / "calculation.yaml"
                wf_model = load_calculation(wf_path)

                # Validate all step IDs exist
                existing_ids = {s.step_ulid for s in wf_model.steps}
                existing_slugs = {}
                for s in wf_model.steps:
                    if s.step_ulid:
                        existing_slugs[s.step_ulid] = s
                    if s.step_type_spec:
                        existing_slugs[s.step_type_spec] = s

                # Resolve the new order
                reordered = []
                seen = set()
                for selector in new_order:
                    if selector in existing_slugs:
                        step = existing_slugs[selector]
                        if step.step_ulid not in seen:
                            reordered.append(step)
                            seen.add(step.step_ulid)
                    else:
                        raise ValidationError(f"Step '{selector}' not found in calculation")

                # Ensure all steps are accounted for
                if len(reordered) != len(wf_model.steps):
                    missing = existing_ids - seen
                    raise ValidationError(f"New order missing steps: {missing}")

                # Update the model
                wf_model.steps = reordered
                save_calculation(wf_model, wf_path)

                # Return updated detail
                return self.get_detail(calc_selector)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def update_steps_structure(
            self,
            calc_selector: str,
            structure_selector: str,
            *,
            index: Any = None,
            config: dict | None = None,
        ) -> dict:
            """
            Update structure reference in all steps of a calculation (Law H9 compliant).

            Updates structure_ulid in all step spec files.

            Args:
                calc_selector: Calculation selector
                structure_selector: New structure selector
                index: Optional ResourceIndex
                config: Optional project config

            Returns:
                Dict with old_structure, new_structure, steps_updated count
            """
            try:
                from qmatsuite.core.resolution import require_calculation, require_step, require_structure
                from qmatsuite.core.models import load_calculation
                from qmatsuite.core.project_utils import load_project_config
                from qmatsuite.core.yamldoc import StepDoc
                from qmatsuite.workflow.step_factory import save_step_doc

                if config is None:
                    config = load_project_config(self._service.project_root)

                # Resolve calculation
                calc_resolved = require_calculation(self._service.project_root, calc_selector, config=config, index=index)
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                    calc_yaml = calc_resolved.absolute_path
                else:
                    calc_dir = calc_resolved.absolute_path
                    calc_yaml = calc_dir / "calculation.yaml"

                # Resolve new structure
                structure_resolved = require_structure(self._service.project_root, structure_selector, config=config)
                new_structure_ulid = structure_resolved.meta.ulid

                # Load calculation to get steps
                from qmatsuite.core.resolution import make_structure_selector_resolver
                resolver = make_structure_selector_resolver(self._service.project_root, config=config)
                calc_model = load_calculation(calc_yaml, project_root=self._service.project_root, resolve_structure_selector=resolver)

                # Get old structure for reporting
                old_structure = calc_model.structure_ulid or "none"

                # Update each step's structure_ulid
                steps_updated = 0
                errors = []
                for step_entry in calc_model.steps:
                    step_ulid = step_entry.step_ulid
                    if not step_ulid:
                        continue

                    try:
                        step_resolved = require_step(
                            self._service.project_root,
                            calc_selector,
                            step_ulid
                        )
                        step_path = step_resolved.absolute_path
                        if not step_path.exists():
                            continue

                        # Load and update step spec
                        step_doc = StepDoc.load(step_path)
                        step_doc.set(["structure_ulid"], new_structure_ulid)
                        # Clear legacy structure field
                        step_doc.set(["structure"], "")
                        save_step_doc(step_doc, step_path)
                        steps_updated += 1
                    except Exception as e:
                        errors.append(f"Step {step_ulid}: {e}")

                return {
                    "success": True,
                    "old_structure": old_structure,
                    "new_structure": structure_selector,
                    "new_structure_ulid": new_structure_ulid,
                    "steps_updated": steps_updated,
                    "errors": errors if errors else None,
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def import_step_from_qe_input(
            self,
            calc_selector: str,
            input_file: Path | str,
            step_name: str | None = None,
            *,
            index: Any = None,
            config: dict | None = None,
        ) -> dict:
            """
            Import a QE input file as a step (preserves original parameters).

            Args:
                calc_selector: Calculation selector (ULID)
                input_file: Path to QE input file
                step_name: Optional step name
                index: Optional ResourceIndex
                config: Optional project config

            Returns:
                Updated calculation info dict
            """
            try:
                from qmatsuite.core.resolution import validate_ulid, resolve_calculation
                from qmatsuite.calculation.importers import build_step_spec_from_qe_input
                from qmatsuite.core.models import load_calculation, save_calculation, CalculationStepEntry
                from qmatsuite.core.project_utils import load_project_config
                from qmatsuite.api.errors import NotFoundError

                # Validate ULID
                calc_ulid = validate_ulid(calc_selector, kind="calculation")

                input_file = Path(input_file).resolve()
                if not input_file.exists():
                    raise NotFoundError(f"QE input file not found: {input_file}")

                if config is None:
                    config = load_project_config(self._service.project_root)

                calculation = resolve_calculation(self._service.project_root, calc_ulid, config=config, index=index)
                calculation_dir = calculation.absolute_path
                steps_dir = calculation_dir / "steps"
                steps_dir.mkdir(exist_ok=True)

                # Load calculation model
                wf_model = load_calculation(calculation_dir, self._service.project_root)

                # Determine step name
                step_name = step_name or input_file.stem

                # Import step spec from QE input (apply_defaults=False for import mode)
                import_result = build_step_spec_from_qe_input(
                    input_file=input_file,
                    destination_dir=steps_dir,
                    structure_dir=self._service.project_root / "structures",
                    step_ulid=step_name,
                    structure_ulid=None,
                    reference_structure_by="id",
                    apply_defaults=False,
                )

                spec = import_result.spec
                step_ulid = spec.meta.ulid if spec.meta else import_result.step_ulid

                # Add step to calculation.yaml
                step_entry = CalculationStepEntry(
                    step_ulid=step_ulid,
                    step_type_spec=spec.step_type_spec,
                )

                if not hasattr(wf_model, 'steps') or wf_model.steps is None:
                    wf_model.steps = []
                wf_model.steps.append(step_entry)

                # Save calculation.yaml
                wf_path = calculation_dir / "calculation.yaml"
                save_calculation(wf_model, wf_path)

                return self.get_detail(calc_selector)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def get_pseudo_mapping(
            self,
            calc_selector: str,
            *,
            index: Any = None,
            config: dict | None = None,
        ) -> dict:
            """
            Get pseudopotential mapping for a calculation (calculation-level).

            Args:
                calc_selector: Calculation selector (ULID)
                index: Optional ResourceIndex
                config: Optional project config

            Returns:
                Dict with species, mapping, species_map, available_pseudos, etc.
            """
            try:
                from qmatsuite.core.resolution import validate_ulid, resolve_calculation, resolve_structure, make_structure_selector_resolver
                from qmatsuite.core.models import load_calculation
                from qmatsuite.core.project_utils import load_project_config
                from qmatsuite.io import read_structure
                from qmatsuite.core.pseudo_config import load_pseudo_config
                from qmatsuite.core.pseudo import get_system_pseudo_dir
                from qmatsuite.core.paths import home_pseudo_libraries_dir
                import json

                # Validate ULID
                calc_ulid = validate_ulid(calc_selector, kind="calculation")

                if config is None:
                    config = load_project_config(self._service.project_root)

                calculation = resolve_calculation(self._service.project_root, calc_ulid, config=config, index=index)
                wf_path = calculation.absolute_path / "calculation.yaml"

                resolver = make_structure_selector_resolver(self._service.project_root, config=config)
                wf_model = load_calculation(wf_path, project_root=self._service.project_root, resolve_structure_selector=resolver)

                # Get element list from structure
                species_list: list[str] = []
                if wf_model.structure_ulid:
                    try:
                        struct_resolved = resolve_structure(self._service.project_root, wf_model.structure_ulid, config=config, index=index)
                        if struct_resolved.absolute_path.exists():
                            structure = read_structure(struct_resolved.absolute_path)
                            species_list = sorted(set(str(el) for el in structure.composition.elements))
                    except Exception:
                        pass

                # Build mapping from species_map
                mapping: dict[str, str] = {}
                if wf_model.species_map:
                    for element, settings in wf_model.species_map.items():
                        pseudo = settings.get("pseudopot", "")
                        if pseudo:
                            mapping[element] = pseudo

                # Get available pseudos
                pseudo_dir = self._service.project_root / "pseudo"
                available_pseudos: list[str] = []
                if pseudo_dir.exists():
                    available_pseudos = sorted([
                        f.name for f in pseudo_dir.iterdir()
                        if f.is_file() and f.suffix.lower() == ".upf"
                    ])

                # Check SSSP libraries (NEW layout)
                sssp_defaults: dict[str, dict[str, str]] = {}
                sssp_installed = {"precision": False, "efficiency": False}
                try:
                    from qmatsuite.pseudo.layout import iter_installed_libraries

                    libraries_root = home_pseudo_libraries_dir()
                    for lib in iter_installed_libraries(libraries_root):
                        if lib.library_key.lower() != "sssp":
                            continue
                        if lib.variant not in sssp_installed:
                            continue
                        if any(f.suffix.lower() == ".upf" for f in lib.install_dir.iterdir() if f.is_file()):
                            sssp_installed[lib.variant] = True
                except Exception:
                    pass

                # Generate warnings
                warnings: list[str] = []
                for species in species_list:
                    if species not in mapping:
                        warnings.append(f"Missing pseudopotential for {species}")

                return {
                    "species": species_list,
                    "mapping": mapping,
                    "species_map": wf_model.species_map or {},
                    "available_pseudos": available_pseudos,
                    "pseudo_dir": str(pseudo_dir),
                    "warnings": warnings,
                    "sssp_defaults": sssp_defaults,
                    "sssp_installed": sssp_installed,
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def update_species_map(
            self,
            calc_selector: str,
            species_map: dict[str, dict],
            *,
            index: Any = None,
            config: dict | None = None,
        ) -> dict:
            """
            Update calculation species_map (pseudopotential mapping).

            Args:
                calc_selector: Calculation selector
                species_map: New species mapping
                index: Optional ResourceIndex
                config: Optional project config

            Returns:
                Updated calculation info dict
            """
            try:
                from qmatsuite.core.resolution import resolve_calculation, make_structure_selector_resolver
                from qmatsuite.core.models import load_calculation, save_calculation
                from qmatsuite.core.project_utils import load_project_config

                if config is None:
                    config = load_project_config(self._service.project_root)

                calculation = resolve_calculation(self._service.project_root, calc_selector, config=config, index=index)
                wf_path = calculation.absolute_path / "calculation.yaml"

                resolver = make_structure_selector_resolver(self._service.project_root, config=config)
                wf_model = load_calculation(wf_path, project_root=self._service.project_root, resolve_structure_selector=resolver)

                old_species_map = wf_model.species_map
                wf_model.species_map = species_map
                save_calculation(wf_model, wf_path)

                result = self.get_detail(calc_selector)
                result["old_species_map"] = old_species_map

                return result
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def configure_species_map(
            self,
            calculation: str,
            *,
            from_qe_input: Path | str | None = None,
            set_entries: list[tuple[str, float, str]] | None = None,
            merge: bool = True,
        ) -> dict[str, dict[str, Any]]:
            """
            Configure calculation-level species_map.

            Args:
                calculation: Calculation selector (id/name/slug/path)
                from_qe_input: Optional QE input file to extract ATOMIC_SPECIES from
                set_entries: Optional list of explicit (element, mass, pseudopot) triples
                merge: If True (default), merge with existing species_map. If False, replace.

            Returns:
                Updated species_map dictionary (element -> {mass, pseudopot, ...})
            """
            try:
                from qmatsuite.calculation.species_config import configure_species_map as _configure_species_map

                project_root = self._service.project_root
                if from_qe_input:
                    from_qe_input = Path(from_qe_input).resolve()

                # Use shared API
                return _configure_species_map(
                    project_root=project_root,
                    calculation=calculation,
                    from_qe_input=from_qe_input,
                    set_entries=set_entries,
                    merge=merge,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                # Map ValueError to ValidationError for API consistency
                if isinstance(e, ValueError):
                    from qmatsuite.api.errors import ValidationError
                    raise ValidationError(
                        str(e),
                        code="VALIDATION_FAILED",
                        context={"calculation": calculation}
                    )
                raise map_kernel_exception(e)

    @property
    def calculation(self) -> Calculation:
        """Access calculation capabilities."""
        return QMSService.Calculation(self)
    
    # Run domain (PR7)
    class Run:
        """Run/execution capabilities."""
        
        def __init__(self, service: QMSService):
            self._service = service
        
        def run_calculation(
            self,
            calc_selector: str,
            steps: list[str] | None = None,
            *,
            run_mode: str = "incremental",
            run_ulid: str | None = None,
        ) -> RunResultDTO:
            """
            Run a calculation.

            Args:
                calc_selector: Calculation selector
                steps: Optional list of step selectors to run (None = all steps)
                run_mode: Run mode ("incremental" or "full", default "incremental")
                run_ulid: External run ID to use (e.g., job_id from JobManager)

            Returns:
                RunResultDTO

            Raises:
                APIError: If calculation not found or run fails
            """
            try:
                from qmatsuite.project.model import Project
                from qmatsuite.calculation.calculation import Calculation
                from qmatsuite.calculation.runner import CalculationRunner
                from qmatsuite.engine.registry import create_default_registry
                from qmatsuite.core.locking import calc_run_lock, CalculationLockError
                from qmatsuite.core.resolution import require_calculation, build_resource_index
                from qmatsuite.core.project_utils import load_project_config
                from qmatsuite.api import get_step_type_gen

                project_root = self._service.project_root
                config = load_project_config(project_root)
                index = build_resource_index(project_root)

                # Resolve calculation
                calc_resolved = require_calculation(project_root, calc_selector, config=config, index=index)
                calc_ulid = calc_resolved.meta.ulid if calc_resolved.meta else ""
                calculation_dir = calc_resolved.absolute_path

                # Acquire run lock
                try:
                    with calc_run_lock(calculation_dir, fail_fast=True):
                        # Load calculation with materialized steps
                        project = Project.open(project_root)
                        calculation = Calculation.from_yaml(calculation_dir, project, materialize_steps=True)

                        # Engines that embed structure in input (e.g., LAMMPS lattice
                        # commands, QE ATOMIC_POSITIONS in input file) may not require
                        # a separate structure assignment.
                        _structureless_ok = {"lammps", "yambo"}
                        engine_fam = getattr(calculation, "engine_family", "")
                        _has_embedded = bool(calculation.steps)  # has steps with params
                        if not calculation.structure_ulid and engine_fam not in _structureless_ok and not _has_embedded:
                            from qmatsuite.api.errors import ValidationError
                            raise ValidationError(
                                f"Calculation '{calc_selector}' has no structure. Please set a structure first."
                            )

                        # Create engine registry and runner
                        registry = create_default_registry()
                        runner = CalculationRunner(registry)

                        results = runner.run(
                            calculation,
                            run_ulid=run_ulid,
                            run_mode=run_mode,
                        )
                except CalculationLockError as e:
                    from qmatsuite.api.errors import EngineError
                    error = EngineError(str(e))
                    error.code = "CALCULATION_LOCKED"
                    raise error

                # Post-run pipeline (digest persistence + eager analysis snapshots).
                # Failures are non-fatal and must not change run completion status.
                self._service._finalize_run_analysis_pipeline(calculation, results)

                # Convert results to dict
                result_dict = {
                    "calculation": calc_selector,
                    "status": results.status.value,
                    "n_steps": len(results.steps),
                    "steps": [
                        {
                            "step_ulid": s.step_ulid,
                            "step_ulid": s.step_ulid,  # Backwards compat
                            "step_type_spec": s.step_type_spec if s.step_type_spec else None,
                            "step_type_gen": get_step_type_gen(s.step_type_spec) if s.step_type_spec else None,  # Proper conversion
                            "status": s.status.value,
                            "message": s.message,
                            "metrics": s.metrics,
                        }
                        for s in results.steps
                    ],
                    "io_dir": str(results.io_dir) if results.io_dir else None,
                    "run_ulid": results.run_ulid,
                }

                return self._result_dict_to_dto(result_dict, calc_ulid)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def run_step(
            self,
            calc_selector: str,
            step_selector: str,
            *,
            run_ulid: str | None = None,
        ) -> RunResultDTO:
            """
            Run a single step.

            Args:
                calc_selector: Calculation selector
                step_selector: Step selector
                run_ulid: Optional external run ID (e.g., job_id from daemon)

            Returns:
                RunResultDTO

            Raises:
                APIError: If calculation or step not found or run fails
            """
            try:
                from qmatsuite.project.model import Project
                from qmatsuite.calculation.calculation import Calculation
                from qmatsuite.calculation.runner import CalculationRunner
                from qmatsuite.calculation.types import StepStatus
                from qmatsuite.engine.registry import create_default_registry
                from qmatsuite.core.resolution import require_calculation, require_step, build_resource_index
                from qmatsuite.core.project_utils import load_project_config
                import logging
                import yaml

                logger = logging.getLogger(__name__)
                project_root = self._service.project_root

                config = load_project_config(project_root)
                index = build_resource_index(project_root)

                # Resolve calculation and step
                calc_resolved = require_calculation(project_root, calc_selector, config=config, index=index)
                calc_ulid = calc_resolved.meta.ulid if calc_resolved.meta else ""
                step_resolved = require_step(project_root, calc_selector, step_selector, config=config, index=index)

                # Load calculation with materialized steps
                project = Project.open(project_root)
                calculation = Calculation.from_yaml(calc_resolved.absolute_path, project, materialize_steps=True)

                if not calculation.structure_ulid:
                    from qmatsuite.api.errors import ValidationError
                    raise ValidationError(
                        f"Calculation '{calc_selector}' has no structure. Please set a structure first."
                    )

                # Get step type (SPEC from YAML, convert to GEN for API response)
                step_type_gen = "unknown"
                try:
                    from qmatsuite.api import get_step_type_gen
                    step_data = yaml.safe_load(step_resolved.absolute_path.read_text()) or {}
                    step_type_spec = step_data.get("step_type_spec", "unknown")
                    step_type_gen = get_step_type_gen(step_type_spec) if step_type_spec else "unknown"
                except Exception:
                    pass

                # Create engine registry and runner
                engine_registry = create_default_registry()
                runner = CalculationRunner(engine_registry)

                target_step_ulid = step_resolved.meta.ulid
                logger.info(f"[RUN_STEP] Running step {step_selector} (id={target_step_ulid})")

                try:
                    result = runner.run(
                        calculation,
                        run_ulid=run_ulid,
                        run_mode="incremental",
                        target_step_ulid=target_step_ulid,
                    )
                except Exception as e:
                    logger.exception(f"[RUN_STEP] Execution failed: {e}")
                    result_dict = {
                        "step": step_selector,
                        "step_ulid": target_step_ulid,
                        "step_type_gen": step_type_gen,
                        "success": False,
                        "error": str(e),
                        "output_file": None,
                        "io_dir": str(calculation.raw_dir.resolve()) if calculation.raw_dir else None,
                        "run_ulid": run_ulid,
                    }
                    return self._result_dict_to_dto(result_dict, calc_ulid)

                # Post-run pipeline (digest persistence + eager analysis snapshots).
                self._service._finalize_run_analysis_pipeline(calculation, result)

                # Find target step's result
                target_summary = None
                for summary in result.steps:
                    if summary.step_ulid == target_step_ulid:
                        target_summary = summary
                        break

                success = result.status == StepStatus.SUCCESS
                error_msg = None
                if target_summary and target_summary.status == StepStatus.FAILED:
                    success = False
                    error_msg = target_summary.message

                io_dir = str(result.io_dir.resolve()) if result.io_dir else str(calculation.raw_dir.resolve())

                input_file = None
                output_file = None
                if target_summary:
                    if target_summary.input_file and target_summary.input_file != Path():
                        input_file = str(target_summary.input_file)
                    if target_summary.output_file and target_summary.output_file != Path():
                        output_file = str(target_summary.output_file)

                result_dict = {
                    "step": step_selector,
                    "step_ulid": target_step_ulid,
                    "step_type_gen": step_type_gen,
                    "success": success,
                    "error": error_msg,
                    "input_file": input_file,
                    "output_file": output_file,
                    "io_dir": io_dir,
                    "working_dir": io_dir,
                    "run_ulid": result.run_ulid,
                }

                return self._result_dict_to_dto(result_dict, calc_ulid)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def cancel(self, run_ulid: str) -> RunResultDTO:
            """
            Cancel a running job.
            
            Attempts to cancel a job via JobManager if available (daemon context).
            If JobManager is not available, attempts to find run info from history
            and returns appropriate status.
            
            Args:
                run_ulid: Run ID (ULID)
                
            Returns:
                RunResultDTO with cancelled status (or current status if already terminal)
                
            Raises:
                NotFoundError: If run not found
                EngineError: If cancellation fails (e.g., job already running)
            """
            try:
                from qmatsuite.api.errors import NotFoundError, EngineError
                from qmatsuite.provenance import get_run_details

                # Try to access JobManager if available (daemon context)
                # Check for thread-local or context variable
                job_manager = None
                try:
                    import threading
                    # Check if there's a thread-local job manager
                    if hasattr(threading.current_thread(), 'job_manager'):
                        job_manager = threading.current_thread().job_manager
                except Exception:
                    pass
                
                # If JobManager is available, use it to cancel
                if job_manager is not None:
                    job = job_manager.get_job(run_ulid)
                    if job is None:
                        raise NotFoundError(
                            f"Run not found: {run_ulid}",
                            context={"run_ulid": run_ulid}
                        )
                    
                    # Attempt cancellation
                    cancelled = job_manager.cancel_job(run_ulid)
                    
                    # Get updated job status
                    job = job_manager.get_job(run_ulid)
                    if job is None:
                        raise NotFoundError(
                            f"Run not found after cancellation attempt: {run_ulid}",
                            context={"run_ulid": run_ulid}
                        )
                    
                    # Convert job to RunResultDTO
                    status_map = {
                        "pending": "submitted",
                        "running": "running",
                        "completed": "completed",
                        "failed": "failed",
                        "cancelled": "cancelled",
                    }
                    status = status_map.get(job.status.value, "submitted")
                    
                    # Extract calc_ulid from job params or result
                    calc_ulid = ""
                    if job.params:
                        calc_ulid = job.params.get("calc_ulid", job.params.get("calc_selector", ""))
                    if not calc_ulid and job.result:
                        calc_ulid = job.result.get("calc_ulid", "")
                    
                    # Extract step_ulids
                    step_ulids = []
                    if job.steps:
                        step_ulids = [s.get("step_ulid", "") for s in job.steps if s.get("step_ulid")]
                    
                    # Format timestamps
                    started_at = job.started_at.isoformat() if job.started_at else None
                    completed_at = job.completed_at.isoformat() if job.completed_at else None
                    
                    # Calculate duration if both timestamps available
                    duration_seconds = None
                    if job.started_at and job.completed_at:
                        duration_seconds = (job.completed_at - job.started_at).total_seconds()
                    
                    # Build error DTO if failed
                    error = None
                    if status == "failed" and job.error:
                        from qmatsuite.api.types.error import ErrorDTO
                        error = ErrorDTO(
                            type="RunError",
                            code="RUN_FAILED",
                            message=job.error,
                            retryable=True,
                        )
                    
                    return RunResultDTO(
                        run_ulid=run_ulid,
                        calc_ulid=calc_ulid,
                        status=status,
                        step_ulids=step_ulids,
                        started_at=started_at,
                        completed_at=completed_at,
                        duration_seconds=duration_seconds,
                        exit_code=None,
                        log_path=job.output_file,
                        error=error,
                    )
                
                # If JobManager not available, try to find run in provenance
                run_info = get_run_details(self._service.project_root, run_ulid)

                if run_info is None:
                    raise NotFoundError(
                        f"Run not found: {run_ulid}",
                        context={"run_ulid": run_ulid}
                    )

                # Check if run is already terminal
                run_status = run_info.get("status", "")
                if run_status in ["success", "completed", "failed", "cancelled"]:
                    # Map status for DTO
                    status_map = {
                        "success": "completed",
                        "completed": "completed",
                        "failed": "failed",
                        "cancelled": "cancelled",
                    }
                    status = status_map.get(run_status, "completed")
                else:
                    # Run is active but we can't cancel without JobManager
                    # Return current status with hint that cancellation requires daemon
                    status = "running"  # or "submitted" depending on run_info.status

                return RunResultDTO(
                    run_ulid=run_ulid,
                    calc_ulid=run_info.get("calc_ulid", ""),
                    status=status,
                    step_ulids=run_info.get("step_ulids", []),
                    started_at=run_info.get("started_at"),
                    completed_at=run_info.get("finished_at"),
                    duration_seconds=None,  # Would need to calculate from timestamps
                    exit_code=None,
                    log_path=None,
                    error=None,
                )
                    
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def list_runs(
            self,
            calc_selector: str | None = None,
            status: str | None = None,
        ) -> list[RunResultDTO]:
            """
            List runs, optionally filtered.

            Note: This is a simplified implementation. In a full system,
            this would query job history or a job manager.

            Args:
                calc_selector: Optional calculation selector filter
                status: Optional status filter

            Returns:
                List of RunResultDTO
            """
            try:
                # Simplified: For now, return empty list
                # This would need to query calculation history or job manager
                return []
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def preflight(
            self,
            calc_selector: str | None = None,
            step_selector: str | None = None,
        ) -> dict:
            """
            Perform pre-flight checks before running a calculation or step.

            Args:
                calc_selector: Optional calculation selector
                step_selector: Optional step selector (requires calc_selector)

            Returns:
                Dict with check results: {
                    "ok": bool,
                    "checks": [{"name": str, "ok": bool, "message": str}],
                    "errors": [str],
                    "warnings": [str],
                }
            """
            try:
                from qmatsuite.core.engines.qe_resolver import resolve_qe_bin_dir
                from qmatsuite.core.settings import load_settings
                from qmatsuite.core.resolution import resolve_calculation, resolve_structure
                from qmatsuite.core.models import load_calculation
                from qmatsuite.core.project_utils import load_project_config
                from qmatsuite.core.resolution import make_structure_selector_resolver
                import logging

                logger = logging.getLogger(__name__)

                checks = []
                errors = []
                warnings = []

                # Check 1: QE installation
                logger.info("[PREFLIGHT] Starting QE check")
                try:
                    settings = load_settings()
                    qe_bin_dir = resolve_qe_bin_dir(settings)

                    pw_x = qe_bin_dir / "pw.x"
                    pw_exe = qe_bin_dir / "pw.x.exe"

                    if pw_x.exists() or pw_exe.exists():
                        executable_path = pw_x if pw_x.exists() else pw_exe
                        checks.append({
                            "name": "QE Installation",
                            "ok": True,
                            "message": f"QE: pw.x found at {executable_path}"
                        })
                    else:
                        checks.append({
                            "name": "QE Installation",
                            "ok": False,
                            "message": "pw.x not found"
                        })
                        errors.append("Quantum ESPRESSO pw.x executable not found")
                except RuntimeError as e:
                    checks.append({
                        "name": "QE Installation",
                        "ok": False,
                        "message": str(e)
                    })
                    errors.append("Quantum ESPRESSO not detected. Use Settings to detect or configure QE.")
                except Exception as e:
                    checks.append({
                        "name": "QE Installation",
                        "ok": False,
                        "message": str(e)
                    })
                    errors.append(f"QE installation error: {e}")

                # Check 2: Project path
                project_path = self._service.project_root
                if project_path.exists():
                    if project_path.is_dir():
                        checks.append({
                            "name": "Project Path",
                            "ok": True,
                            "message": f"Project exists: {project_path}"
                        })
                    else:
                        checks.append({
                            "name": "Project Path",
                            "ok": False,
                            "message": "Project path is not a directory"
                        })
                        errors.append("Project path is not a directory")
                else:
                    checks.append({
                        "name": "Project Path",
                        "ok": False,
                        "message": "Project path does not exist"
                    })
                    errors.append(f"Project path does not exist: {project_path}")

                # Check 3: Calculation exists
                calculation = None
                config = None
                if calc_selector:
                    try:
                        config = load_project_config(self._service.project_root)
                        calculation = resolve_calculation(
                            self._service.project_root,
                            calc_selector,
                            config=config
                        )
                        checks.append({
                            "name": "Calculation",
                            "ok": True,
                            "message": f"Calculation found: {calculation.meta.name}"
                        })
                    except Exception as e:
                        checks.append({
                            "name": "Calculation",
                            "ok": False,
                            "message": str(e)
                        })
                        errors.append(f"Calculation not found: {calc_selector}")

                # Check 4: Structure exists (if calculation found)
                if calculation:
                    try:
                        if config is None:
                            config = load_project_config(self._service.project_root)
                        resolver = make_structure_selector_resolver(
                            self._service.project_root,
                            config=config
                        )

                        # Get calculation directory
                        if calculation.absolute_path.name == "calculation.yaml":
                            calc_yaml = calculation.absolute_path
                        else:
                            calc_yaml = calculation.absolute_path / "calculation.yaml"

                        calc_model = load_calculation(
                            calc_yaml,
                            project_root=self._service.project_root,
                            resolve_structure_selector=resolver
                        )

                        if calc_model.structure_ulid:
                            struct_resolved = resolve_structure(
                                self._service.project_root,
                                calc_model.structure_ulid,
                                config=config
                            )
                            if struct_resolved.absolute_path.exists():
                                checks.append({
                                    "name": "Structure",
                                    "ok": True,
                                    "message": f"Structure found: {struct_resolved.meta.name}"
                                })
                            else:
                                checks.append({
                                    "name": "Structure",
                                    "ok": False,
                                    "message": f"Structure file missing: {struct_resolved.absolute_path}"
                                })
                                errors.append(f"Structure file missing")
                        else:
                            checks.append({
                                "name": "Structure",
                                "ok": False,
                                "message": "No structure assigned to calculation"
                            })
                            warnings.append("No structure assigned to calculation")
                    except Exception as e:
                        checks.append({
                            "name": "Structure",
                            "ok": False,
                            "message": str(e)
                        })
                        errors.append(f"Structure check failed: {e}")

                # Check 5: Pseudopotentials (v0 contract compatibility)
                if calculation:
                    try:
                        # Get calculation directory
                        if calculation.absolute_path.name == "calculation.yaml":
                            calc_yaml = calculation.absolute_path
                        else:
                            calc_yaml = calculation.absolute_path / "calculation.yaml"

                        if config is None:
                            config = load_project_config(self._service.project_root)
                        resolver = make_structure_selector_resolver(
                            self._service.project_root,
                            config=config
                        )
                        calc_model = load_calculation(
                            calc_yaml,
                            project_root=self._service.project_root,
                            resolve_structure_selector=resolver
                        )

                        # Check if species_map is defined in any step
                        has_species_map = False
                        if calc_model.steps:
                            for step in calc_model.steps:
                                if hasattr(step, 'species_map') and step.species_map:
                                    has_species_map = True
                                    break

                        if not has_species_map:
                            checks.append({
                                "name": "Pseudopotentials",
                                "ok": True,
                                "message": "No species_map defined - skipping pseudo check"
                            })
                        else:
                            # species_map exists, would need to verify pseudos exist
                            # For now, just mark as ok (detailed check can be added later)
                            checks.append({
                                "name": "Pseudopotentials",
                                "ok": True,
                                "message": "Pseudopotential configuration found"
                            })
                    except Exception as e:
                        checks.append({
                            "name": "Pseudopotentials",
                            "ok": False,
                            "message": str(e)
                        })
                        warnings.append(f"Pseudopotential check failed: {e}")

                # Check 6: Working Directory (v0 contract compatibility)
                if calculation:
                    try:
                        # Working directory is typically calculation's io_dir
                        calc_dir = calculation.absolute_path
                        if calc_dir.name == "calculation.yaml":
                            calc_dir = calc_dir.parent

                        # Check if directory exists and is writable
                        if calc_dir.exists() and calc_dir.is_dir():
                            checks.append({
                                "name": "Working Directory",
                                "ok": True,
                                "message": "Working directory exists"
                            })
                        else:
                            checks.append({
                                "name": "Working Directory",
                                "ok": False,
                                "message": f"Working directory does not exist: {calc_dir}"
                            })
                            errors.append("Working directory does not exist")
                    except Exception as e:
                        checks.append({
                            "name": "Working Directory",
                            "ok": False,
                            "message": str(e)
                        })
                        warnings.append(f"Working directory check failed: {e}")

                return {
                    "ok": len(errors) == 0,
                    "checks": checks,
                    "errors": errors,
                    "warnings": warnings,
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def _result_dict_to_dto(self, result_dict: dict, calc_ulid: str) -> RunResultDTO:
            """Convert legacy result dict to RunResultDTO."""
            from qmatsuite.api.types.error import ErrorDTO
            
            # Extract step IDs and step details
            step_ulids = []
            step_details = None
            if "steps" in result_dict:
                step_details = result_dict["steps"]
                step_ulids = [s.get("step_ulid", "") for s in result_dict["steps"] if s.get("step_ulid")]
            # Handle single step_ulid (from run_step)
            elif "step_ulid" in result_dict and result_dict["step_ulid"]:
                step_ulids = [result_dict["step_ulid"]]
            
            # Map status - handle both "status" key and "success" boolean
            status_map = {
                "success": "completed",
                "failed": "failed",
                "pending": "submitted",
                "running": "running",
                "completed": "completed",
            }
            # First check for explicit "status" key
            raw_status = result_dict.get("status", "")
            if raw_status:
                status = status_map.get(raw_status.lower() if isinstance(raw_status, str) else str(raw_status), "submitted")
            # Fall back to "success" boolean
            elif "success" in result_dict:
                status = "completed" if result_dict["success"] else "failed"
            else:
                status = "submitted"
            
            # Extract timing (if available)
            started_at = None
            completed_at = None
            duration_seconds = None
            
            # Extract error if failed
            error = None
            if status == "failed":
                error_msg = result_dict.get("error") or "Run failed"
                error = ErrorDTO(
                    type="RunError",
                    code="RUN_FAILED",
                    message=error_msg,
                    retryable=True,
                )
            
            return RunResultDTO(
                run_ulid=result_dict.get("run_ulid", ""),
                calc_ulid=calc_ulid,
                status=status,
                step_ulids=step_ulids,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration_seconds,
                exit_code=None,
                log_path=result_dict.get("io_dir"),
                error=error,
                _step_details=step_details,
                io_dir=result_dict.get("io_dir"),
                input_file=result_dict.get("input_file"),
                output_file=result_dict.get("output_file"),
            )
    
    @property
    def run(self) -> Run:
        """Access run capabilities."""
        return QMSService.Run(self)
    
    # Project domain (PR8)
    class Project:
        """Project capabilities."""
        
        def __init__(self, service: QMSService):
            self._service = service
        
        def get_config(self) -> dict:
            """
            Get project configuration.
            
            Returns:
                Project configuration dict
                
            Raises:
                APIError: If project invalid
            """
            try:
                from qmatsuite.core.project_utils import load_project_config
                return load_project_config(self._service.project_root)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def update_config(self, patch: dict) -> dict:
            """
            Update project configuration.
            
            Args:
                patch: Dict with config updates (merged into existing config)
                
            Returns:
                Updated project configuration dict
                
            Raises:
                APIError: If project invalid or update fails
            """
            try:
                from qmatsuite.core.project_utils import load_project_config, save_project_config
                
                # Load current config
                config = load_project_config(self._service.project_root)
                
                # Merge patch into config
                config.update(patch)
                
                # Save updated config
                save_project_config(self._service.project_root, config)
                
                return config
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        # NOTE: get_species_map, get_potential_map REMOVED - use get_config() instead

        def build_resource_index(self) -> Any:
            """
            Build resource index for project (for internal use).
            
            Returns:
                ResourceIndex (kernel type)
                
            Raises:
                APIError: If project invalid
            """
            try:
                from qmatsuite.core.resolution import build_resource_index
                return build_resource_index(self._service.project_root)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def collect_slugs(self, entries: list[dict], *, exclude: dict | None = None) -> list[str]:
            """
            Collect all slugs from a list of structure or calculation entries.
            
            Args:
                entries: List of entry dicts
                exclude: Optional entry to exclude from collection
                
            Returns:
                List of slug strings
            """
            try:
                from qmatsuite.core.project_utils import collect_slugs as _collect_slugs
                return _collect_slugs(entries, exclude=exclude, project_root=self._service.project_root)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def apply_structure_rename(
            self,
            entry: dict,
            new_name: str | None = None,
            new_slug: str | None = None,
            new_path: Path | None = None,
            config: dict | None = None,
        ) -> None:
            """
            Apply a rename operation to a structure entry.
            
            Args:
                entry: Structure entry dict
                new_name: Optional new name
                new_slug: Optional new slug
                new_path: Optional new path
                config: Optional project config (avoids reloading if provided)
            """
            if config is None:
                config = self.get_config()
            
            from qmatsuite.core.project_utils import apply_structure_rename as _apply_structure_rename
            _apply_structure_rename(
                project_root=self._service.project_root,
                config=config,
                entry=entry,
                new_name=new_name,
                new_slug=new_slug,
                new_path=new_path,
            )
        
        def apply_calculation_rename(
            self,
            entry: dict,
            new_name: str | None = None,
            new_slug: str | None = None,
            new_path: Path | None = None,
            config: dict | None = None,
        ) -> None:
            """
            Apply a rename operation to a calculation entry.
            
            Args:
                entry: Calculation entry dict
                new_name: Optional new name
                new_slug: Optional new slug
                new_path: Optional new path
                config: Optional project config (avoids reloading if provided)
            """
            if config is None:
                config = self.get_config()
            
            from qmatsuite.core.project_utils import apply_calculation_rename as _apply_calculation_rename
            _apply_calculation_rename(
                project_root=self._service.project_root,
                config=config,
                entry=entry,
                new_name=new_name,
                new_slug=new_slug,
                new_path=new_path,
            )

        def import_pseudo_files(
            self,
            file_paths: list[str],
        ) -> dict:
            """
            Import pseudopotential files into project pseudo directory.

            Handles filename conflicts by auto-renaming with deterministic suffix.

            Args:
                file_paths: List of source file paths to import

            Returns:
                Dict with imported, renamed, skipped, errors
            """
            try:
                import shutil
                import hashlib

                def compute_sha256(file_path: Path) -> str:
                    sha256 = hashlib.sha256()
                    with open(file_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(8192), b''):
                            sha256.update(chunk)
                    return sha256.hexdigest()

                project_pseudo_dir = self._service.project_root / "pseudo"
                project_pseudo_dir.mkdir(parents=True, exist_ok=True)

                # Build SHA256 index of existing pseudos for deduplication
                existing_hashes: dict[str, str] = {}
                for existing_file in project_pseudo_dir.iterdir():
                    if existing_file.is_file() and existing_file.suffix.lower() == ".upf":
                        try:
                            existing_hashes[compute_sha256(existing_file)] = existing_file.name
                        except Exception:
                            pass

                imported: list[str] = []
                renamed: dict[str, str] = {}
                skipped: list[str] = []
                errors: list[str] = []

                for file_path_str in file_paths:
                    try:
                        source_path = Path(file_path_str).resolve()

                        if not source_path.exists():
                            errors.append(f"File not found: {file_path_str}")
                            continue

                        if not source_path.is_file():
                            errors.append(f"Not a file: {file_path_str}")
                            continue

                        suffix_lower = source_path.suffix.lower()
                        if suffix_lower != ".upf":
                            errors.append(f"Invalid file type (expected .UPF): {source_path.name}")
                            continue

                        source_hash = compute_sha256(source_path)

                        # Check for content duplicate
                        if source_hash in existing_hashes:
                            existing_name = existing_hashes[source_hash]
                            skipped.append(f"{source_path.name} (identical to {existing_name})")
                            imported.append(existing_name)
                            continue

                        # Determine target filename
                        original_name = source_path.name
                        target_name = original_name
                        target_path = project_pseudo_dir / target_name

                        # Handle filename conflict
                        if target_path.exists():
                            base_name = source_path.stem
                            extension = source_path.suffix
                            counter = 1
                            while target_path.exists():
                                target_name = f"{base_name}_{counter}{extension}"
                                target_path = project_pseudo_dir / target_name
                                counter += 1
                            renamed[original_name] = target_name

                        shutil.copy2(source_path, target_path)
                        imported.append(target_name)
                        existing_hashes[source_hash] = target_name

                    except Exception as e:
                        errors.append(f"Error importing {file_path_str}: {e}")

                return {
                    "imported": imported,
                    "renamed": renamed,
                    "skipped": skipped,
                    "errors": errors,
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def get_summary(self) -> dict[str, Any]:
            """
            Get a high-level summary of the project.

            Returns:
                Dict with project name, id, structure count, calculation count, etc.
            """
            try:
                from qmatsuite.core.project_utils import load_project_config
                from qmatsuite.core.resolution import list_structures, list_calculations

                project_root = self._service.project_root
                config = load_project_config(project_root)

                project_info = config.get("project", {})
                meta = project_info.get("meta", {})
                structures = config.get("structures", [])
                calculations = config.get("calculations", [])

                # Use registry to resolve structure/calculation names (ID-only model)
                structure_names = []
                try:
                    resolved_structures = list_structures(project_root)
                    structure_names = [res.meta.name for res in resolved_structures]
                except Exception:
                    # Fallback: try to get names from structure entries if they have meta
                    structure_names = [
                        s.get("meta", {}).get("name") or s.get("name", "?")
                        for s in structures
                    ]

                calculation_names = []
                try:
                    resolved_calculations = list_calculations(project_root)
                    calculation_names = [res.meta.name for res in resolved_calculations]
                except Exception:
                    # Fallback: try to get names from calculation entries if they have meta
                    calculation_names = [
                        w.get("meta", {}).get("name") or w.get("name", "?")
                        for w in calculations
                    ]

                return {
                    "id": meta.get("ulid"),  # Backwards compat alias
                    "ulid": meta.get("ulid"),
                    "name": project_info.get("name") or meta.get("name") or project_root.name,
                    "slug": meta.get("slug"),
                    "path": str(project_root),
                    "n_structures": len(structures),
                    "n_calculations": len(calculations),
                    "structure_names": structure_names,
                    "calculation_names": calculation_names,
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def init_calculation(
            self,
            name: str,
            structure_selector: str | None = None,
            template: str | None = None,
            *,
            structure_kind: str | None = None,
            engine_family: str | None = None,
            parents: list[str] | None = None,
            index: Any = None,
            config: dict | None = None,
        ) -> Any:
            """
            Create a new calculation.

            Args:
                name: Calculation name
                structure_selector: Optional structure selector for calculation
                template: Optional template name
                structure_kind: 'periodic' or 'molecule' (defaults based on engine)
                engine_family: 'qe', 'pyscf', etc. (defaults to 'qe')
                parents: Optional list of parent calculation IDs (metadata only)
                index: Optional resource index (for performance)
                config: Optional project config (for performance)

            Returns:
                ResolvedResource for the new calculation
            """
            try:
                from qmatsuite.core.project_utils import load_project_config, save_project_config
                from qmatsuite.core.resources import generate_resource_id, slugify
                from qmatsuite.core.resolution import resolve_structure, build_resource_index
                import yaml

                project_root = self._service.project_root

                # Load project config
                if config is None:
                    config = load_project_config(project_root)

                calculations = config.setdefault("calculations", [])

                # Collect existing slugs
                existing_slugs = {calc.get("meta", {}).get("slug") or calc.get("slug") for calc in calculations if calc.get("meta", {}).get("slug") or calc.get("slug")}

                # Generate unique name and slug
                base_slug = slugify(name)
                final_slug = base_slug
                counter = 1
                while final_slug in existing_slugs:
                    final_slug = f"{base_slug}-{counter}"
                    counter += 1

                final_name = name

                # Generate calculation ID
                calc_ulid = generate_resource_id()

                # Create calculation directory and subdirectories
                calc_dir = project_root / "calculations" / final_slug
                calc_dir.mkdir(parents=True, exist_ok=True)
                (calc_dir / "raw").mkdir(exist_ok=True)
                (calc_dir / "steps").mkdir(exist_ok=True)

                # Determine structure_kind defaults
                if structure_kind is None:
                    structure_kind = "periodic"
                # engine_family may be None (UNDECIDED state per Law EF1).
                # Caller must provide engine_family; do not infer.

                # Build meta dict
                meta_dict = {
                    "ulid": calc_ulid,
                    "name": final_name,
                    "slug": final_slug,
                    "path": f"calculations/{final_slug}",
                    "kind": "calculation",
                }
                if parents:
                    meta_dict["parents"] = parents

                # Create calculation.yaml
                calc_yaml = calc_dir / "calculation.yaml"
                calc_data = {
                    "meta": meta_dict,
                    "mode": "normal",
                    "working_dir": "raw",
                    "steps": [],
                    "structure_kind": structure_kind,
                    "engine_family": engine_family,
                }

                # Add structure reference if provided
                if structure_selector:
                    if index is None:
                        index = build_resource_index(project_root)
                    struct_resolved = resolve_structure(project_root, structure_selector, index=index)
                    calc_data["structure_ulid"] = struct_resolved.meta.ulid

                # Write calculation.yaml
                with open(calc_yaml, "w", encoding="utf-8") as f:
                    yaml.dump(calc_data, f, default_flow_style=False, sort_keys=False)

                # Add to project config with full meta
                calc_entry = {
                    "meta": {
                        "ulid": calc_ulid,
                        "name": final_name,
                        "slug": final_slug,
                        "path": f"calculations/{final_slug}",
                        "kind": "calculation",
                    }
                }
                calculations.append(calc_entry)
                save_project_config(project_root, config)

                # Return ResolvedResource
                from qmatsuite.core.resolution import ResolvedResource
                from qmatsuite.core.resources import ResourceMeta

                meta = ResourceMeta(ulid=calc_ulid,
                    name=final_name,
                    slug=final_slug,
                    path=f"calculations/{final_slug}",
                    kind="calculation",
                )

                # absolute_path must point to the calculation directory, not the file
                return ResolvedResource(
                    meta=meta,
                    entry=calc_entry,
                    absolute_path=calc_dir,
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def analyze_pseudo_effects(
            self,
            selections: list[Any],
        ) -> dict[str, Any]:
            """
            Analyze what would happen if pseudo selections were applied (read-only).

            Args:
                selections: List of PseudoSelection objects or dicts

            Returns:
                PseudoPrepareReport as dict
            """
            from qmatsuite.core.pseudo_runtime import (
                analyze_project_pseudo_effects as _analyze_project_pseudo_effects,
                PseudoSelection,
            )

            # Convert dicts to PseudoSelection if needed
            converted_selections = []
            for sel in selections:
                if isinstance(sel, dict):
                    converted_selections.append(PseudoSelection(
                        element=sel["element"],
                        requested_basename=sel["requested_basename"],
                        requested_sha256=sel.get("requested_sha256"),
                        requested_sha_family=sel.get("requested_sha_family"),
                        source_kind=sel.get("source_kind", "project"),
                        source_path=Path(sel["source_path"]) if sel.get("source_path") else None,
                    ))
                else:
                    converted_selections.append(sel)

            report = _analyze_project_pseudo_effects(self._service.project_root, converted_selections)

            # Convert report to dict
            return {
                "actions": [
                    {
                        "action": a.action,
                        "element": a.element,
                        "detail": a.detail,
                        "source_path": str(a.source_path) if a.source_path else None,
                        "dest_path": str(a.dest_path) if a.dest_path else None,
                        "renamed_from": str(a.renamed_from) if a.renamed_from else None,
                        "renamed_to": str(a.renamed_to) if a.renamed_to else None,
                    }
                    for a in report.actions
                ],
                "warnings": report.warnings,
                "errors": report.errors,
            }
        
        def materialize_pseudo_file(
            self,
            element: str,
            sha256: str,
            preferred_basename: str | None = None,
        ) -> dict[str, Any]:
            """
            Materialize a pseudo file from sha256 selection to actual file path.

            Args:
                element: Element symbol
                sha256: SHA256 hash of the pseudo file
                preferred_basename: Preferred basename (for display/filename)

            Returns:
                Dict with success, file_path, source, error, needs_install, archive_asset
            """
            from qmatsuite.core.pseudo_options import materialize_pseudo_file as _materialize_pseudo_file
            return _materialize_pseudo_file(
                project_root=self._service.project_root,
                element=element,
                sha256=sha256,
                preferred_basename=preferred_basename,
            )
        
        def get_pseudo_options(
            self,
            elements: list[str],
            config: dict[str, Any] | None = None,
        ) -> dict[str, list[dict[str, Any]]]:
            """
            Get deduplicated pseudo options for a list of elements.

            Args:
                elements: List of element symbols
                config: Optional PseudoConfig dict (loads if not provided)

            Returns:
                Dict mapping element -> List[PseudoVariant dict] (sha256-keyed)
            """
            from qmatsuite.core.pseudo_options import get_pseudo_options_for_elements as _get_pseudo_options_for_elements
            from qmatsuite.core.pseudo_config import PseudoConfig

            # Convert config dict to PseudoConfig if needed
            pseudo_config = None
            if config is not None:
                if isinstance(config, dict):
                    pseudo_config = PseudoConfig.from_dict(config) if hasattr(PseudoConfig, 'from_dict') else None
                else:
                    pseudo_config = config

            options = _get_pseudo_options_for_elements(
                project_root=self._service.project_root,
                elements=elements,
                config=pseudo_config,
            )

            # Convert PseudoVariant objects to dicts
            result = {}
            for element, variants in options.items():
                result[element] = [
                    v.to_dict() if hasattr(v, 'to_dict') else v
                    for v in variants
                ]
            return result

    @property
    def project(self) -> Project:
        """Access project capabilities."""
        return QMSService.Project(self)
    
    # History domain (minimal surface for daemon)
    class History:
        """History/timeline capabilities using provenance system."""

        def __init__(self, service: QMSService):
            self._service = service

        def get_timeline(
            self,
            limit: int = 100,
            calc_ulid: str | None = None,
        ) -> dict:
            """
            Get project timeline (runs, edits, pins).

            Args:
                limit: Maximum events (default 100)
                calc_ulid: Optional filter by calculation ID

            Returns:
                Dict with timeline entries and latest_run_ulid
            """
            try:
                from qmatsuite.provenance import (
                    query_runs,
                    get_run_details,
                    get_latest_run_ulid,
                    query_operations,
                    build_timeline_entry,
                )

                timeline: list[dict] = []

                # 1. Query runs → produce run_started + run_finished entries
                runs = query_runs(
                    self._service.project_root,
                    calc_ulid=calc_ulid,
                    limit=limit,
                )

                for run in runs:
                    started_entry = {
                        "ulid": run["run_ulid"],
                        "timestamp": run["started_at"],
                        "event_type": "run_started",
                        "calc_ulid": run["calc_ulid"],
                        "run_ulid": run["run_ulid"],
                        "step_ulid": None,
                        "kind": "run",
                    }

                    run_details = get_run_details(self._service.project_root, run["run_ulid"])
                    if run_details:
                        started_entry["step_ulids"] = run_details.get("step_ulids", [])

                    timeline.append(started_entry)

                    if run.get("finished_at"):
                        finished_entry = {
                            "ulid": run["run_ulid"] + "_finished",
                            "timestamp": run["finished_at"],
                            "event_type": "run_finished",
                            "calc_ulid": run["calc_ulid"],
                            "run_ulid": run["run_ulid"],
                            "status": run.get("status", ""),
                            "step_ulid": None,
                            "error_summary": run.get("error_message"),
                            "kind": "run",
                        }
                        timeline.append(finished_entry)

                # 2. Query operations → use canonical build_timeline_entry()
                operations = query_operations(
                    self._service.project_root,
                    calc_ulid=calc_ulid,
                    limit=limit,
                )

                for op in operations:
                    entry = build_timeline_entry(op, self._service.project_root)
                    timeline.append(entry)

                # 3. Merge: sort by timestamp DESC, truncate to limit
                timeline.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

                latest_run_ulid = get_latest_run_ulid(self._service.project_root)

                merged = timeline[:limit]
                return {
                    "timeline": merged,
                    "latest_run_ulid": latest_run_ulid,
                    "latest_run_id": latest_run_ulid,  # Backwards compat alias
                    "total": len(merged),
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def get_run_revision(self, run_ulid: str) -> dict:
            """
            Get details of a specific run revision.

            Args:
                run_ulid: Run ULID

            Returns:
                Dict with revision or error
            """
            try:
                from qmatsuite.provenance import get_run_details

                run_details = get_run_details(self._service.project_root, run_ulid)

                if not run_details:
                    return {"revision": None, "error": f"Run not found: {run_ulid}"}

                # Convert to legacy revision format for compatibility
                revision = {
                    "ulid": run_details["run_ulid"],
                    "calc_ulid": run_details["calc_ulid"],
                    "project_ulid": run_details.get("project_ulid"),
                    "status": run_details.get("status"),
                    "started_at": run_details.get("started_at"),
                    "finished_at": run_details.get("finished_at"),
                    "step_ulids": run_details.get("step_ulids", []),
                    "engine": run_details.get("engine"),
                    "snapshot_sha": run_details.get("snapshot_sha"),
                    "steps": run_details.get("steps", []),
                }

                return {"revision": revision}
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def get_storage_summary(self) -> dict:
            """
            Get storage summary for the provenance system.

            Returns:
                Dict with tier breakdown, total counts, and run/operation counts.
            """
            try:
                from qmatsuite.provenance import (
                    open_provenance_db,
                    PROVENANCE_DIR_NAME,
                )

                project_root = self._service.project_root
                provenance_dir = project_root / PROVENANCE_DIR_NAME

                if not provenance_dir.exists():
                    return {
                        "tiers": [],
                        "total_objects": 0,
                        "total_bytes": 0,
                        "run_count": 0,
                        "operation_count": 0,
                    }

                conn = open_provenance_db(project_root)
                try:
                    # CAS tier summary
                    tiers = []
                    total_objects = 0
                    total_bytes = 0
                    try:
                        cursor = conn.execute(
                            """
                            SELECT tier, COUNT(*), COALESCE(SUM(size_bytes), 0)
                            FROM cas_objects
                            WHERE deleted = 0
                            GROUP BY tier
                            """
                        )
                        for row in cursor.fetchall():
                            tier_info = {
                                "tier": row[0],
                                "count": row[1],
                                "total_bytes": row[2],
                            }
                            tiers.append(tier_info)
                            total_objects += row[1]
                            total_bytes += row[2]
                    except Exception:
                        pass  # cas_objects table may not exist

                    # Run count
                    run_count = 0
                    try:
                        cursor = conn.execute("SELECT COUNT(*) FROM runs")
                        run_count = cursor.fetchone()[0]
                    except Exception:
                        pass

                    # Operation count
                    operation_count = 0
                    try:
                        cursor = conn.execute("SELECT COUNT(*) FROM operations")
                        operation_count = cursor.fetchone()[0]
                    except Exception:
                        pass

                    return {
                        "tiers": tiers,
                        "total_objects": total_objects,
                        "total_bytes": total_bytes,
                        "run_count": run_count,
                        "operation_count": operation_count,
                    }
                finally:
                    conn.close()
            except Exception:
                return {
                    "tiers": [],
                    "total_objects": 0,
                    "total_bytes": 0,
                    "run_count": 0,
                    "operation_count": 0,
                }

        def list_run_history(
            self,
            calc_ulid: str | None = None,
            limit: int = 50,
        ) -> dict:
            """
            List all runs for a project.

            Args:
                calc_ulid: Optional filter by calculation ID
                limit: Maximum runs (default 50)

            Returns:
                Dict with runs list
            """
            try:
                from qmatsuite.provenance import query_runs, get_run_details

                runs_data = query_runs(
                    self._service.project_root,
                    calc_ulid=calc_ulid,
                    limit=limit,
                )

                runs = []
                for run in runs_data:
                    run_info = {
                        "run_ulid": run["run_ulid"],
                        "calc_ulid": run["calc_ulid"],
                        "status": run.get("status"),
                        "started_at": run.get("started_at"),
                        "finished_at": run.get("finished_at"),
                        "step_ulids": [],
                    }

                    # Get step ULIDs
                    run_details = get_run_details(self._service.project_root, run["run_ulid"])
                    if run_details:
                        run_info["step_ulids"] = run_details.get("step_ulids", [])

                    runs.append(run_info)

                return {"runs": runs, "total": len(runs)}
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def pin_analysis(
            self,
            run_ulid: str | None,
            step_ulid: str,
            analysis_kind: str,
            png_data: bytes | None = None,
            json_payload: dict | None = None,
            run_ulid_source: str | None = None,
        ) -> dict:
            """
            Pin analysis to history.

            Args:
                run_ulid: Optional run ULID
                step_ulid: Step ULID
                analysis_kind: Type of analysis (e.g., "bands", "dos")
                png_data: Optional PNG image data
                json_payload: Optional JSON data to store
                run_ulid_source: Optional caller override for provenance confidence
                    ("exact" | "inferred" | "unknown")

            Returns:
                Pin result dict
            """
            try:
                normalized_analysis_kind = analysis_kind.lower()
                import json
                import sqlite3

                from qmatsuite.provenance import (
                    can_pin_to_run,
                    pin_analysis_to_history,
                    PinError,
                )

                def _extract_pin_evidence_fingerprint() -> str | None:
                    if not isinstance(json_payload, dict):
                        return None

                    bundle_payload = json_payload.get("bundle")
                    if isinstance(bundle_payload, dict):
                        payload = bundle_payload
                    else:
                        payload = json_payload

                    provenance = payload.get("provenance_meta")
                    if not isinstance(provenance, dict):
                        return None

                    source_files = provenance.get("source_files")
                    step_ulids = provenance.get("step_ulids")
                    gen_steps = provenance.get("gen_steps")
                    if not (
                        isinstance(source_files, list)
                        and isinstance(step_ulids, list)
                        and isinstance(gen_steps, list)
                    ):
                        return None

                    object_type = str(
                        payload.get("object_type")
                        or provenance.get("object_type")
                        or normalized_analysis_kind
                    ).lower()

                    return self._service._compute_evidence_fingerprint(
                        object_type=object_type,
                        step_ulids=[str(step) for step in step_ulids],
                        gen_steps=[str(step) for step in gen_steps],
                        source_files=source_files,
                    )

                def _infer_run_link() -> tuple[str | None, str, dict]:
                    details: dict[str, object] = {
                        "analysis_kind": analysis_kind,
                        "analysis_kind_normalized": normalized_analysis_kind,
                        "step_ulid": step_ulid,
                    }

                    if run_ulid:
                        can_pin = can_pin_to_run(
                            self._service.project_root,
                            run_ulid,
                            step_ulid,
                        )
                        if not can_pin.get("allowed"):
                            reason = can_pin.get("reason")
                            if reason:
                                raise PinError(str(reason))
                            raise PinError(f"Run not found: {run_ulid}")
                        details["strategy"] = "provided_run_ulid"
                        return run_ulid, "exact", details

                    evidence_fingerprint = _extract_pin_evidence_fingerprint()
                    if evidence_fingerprint:
                        details["evidence_fingerprint"] = evidence_fingerprint
                        conn = sqlite3.connect(str(self._service._get_analysis_db_path()))
                        try:
                            rows = conn.execute(
                                """
                                SELECT s.run_ulid, s.step_ulids
                                FROM analysis_snapshots s
                                JOIN runs r ON r.run_ulid = s.run_ulid
                                WHERE s.object_type = ? AND s.evidence_fingerprint = ?
                                  AND r.status = 'success'
                                ORDER BY COALESCE(r.finished_at, r.started_at) DESC, s.id DESC
                                """,
                                (normalized_analysis_kind, evidence_fingerprint),
                            ).fetchall()
                        finally:
                            conn.close()

                        details["fingerprint_match_count"] = len(rows)
                        for matched_run_ulid, step_ulids_json in rows:
                            try:
                                matched_step_ulids = json.loads(step_ulids_json or "[]")
                            except Exception:
                                matched_step_ulids = []
                            if step_ulid in matched_step_ulids:
                                details["strategy"] = "evidence_fingerprint"
                                details["matched_run_ulid"] = matched_run_ulid
                                return str(matched_run_ulid), "exact", details

                    conn = sqlite3.connect(str(self._service._get_analysis_db_path()))
                    try:
                        fallback = conn.execute(
                            """
                            SELECT r.run_ulid
                            FROM runs r
                            JOIN run_steps rs ON rs.run_ulid = r.run_ulid
                            WHERE rs.step_ulid = ? AND r.status = 'success'
                            ORDER BY COALESCE(r.finished_at, r.started_at) DESC
                            LIMIT 1
                            """,
                            (step_ulid,),
                        ).fetchone()
                    finally:
                        conn.close()

                    if fallback is not None:
                        details["strategy"] = "latest_success_fallback"
                        details["matched_run_ulid"] = fallback[0]
                        return str(fallback[0]), "inferred", details

                    details["strategy"] = "unknown"
                    details["reason"] = "no_matching_run_found"
                    return None, "unknown", details

                try:
                    resolved_run_ulid, resolved_source, source_details = _infer_run_link()
                    if run_ulid_source is not None:
                        if run_ulid_source not in {"exact", "inferred", "unknown"}:
                            raise PinError(f"Invalid run_ulid_source: {run_ulid_source}")
                        resolved_source = run_ulid_source

                    result = pin_analysis_to_history(
                        project_root=self._service.project_root,
                        run_ulid=resolved_run_ulid,
                        step_ulid=step_ulid,
                        analysis_kind=normalized_analysis_kind,
                        png_data=png_data,
                        json_payload=json_payload,
                        run_ulid_source=resolved_source,
                        run_ulid_source_details=source_details,
                    )
                    payload = result.to_dict()
                    payload["run_ulid"] = resolved_run_ulid
                    payload["run_ulid_source_details"] = source_details
                    return payload
                except PinError as e:
                    return {"success": False, "error": str(e)}
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def can_pin(self, run_ulid: str, step_ulid: str) -> dict:
            """
            Check if pinning is allowed for a run and step.

            Args:
                run_ulid: Run ULID
                step_ulid: Step ULID

            Returns:
                Dict with allowed and reason
            """
            try:
                from qmatsuite.provenance import can_pin_to_run
                return can_pin_to_run(self._service.project_root, run_ulid, step_ulid)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def get_pin_data(
            self,
            run_ulid: str,
            step_ulid: str,
            analysis_kind: str,
        ) -> dict:
            """
            Get pinned data for a step analysis.

            Args:
                run_ulid: Run ULID
                step_ulid: Step ULID
                analysis_kind: Type of analysis

            Returns:
                Dict with png_data, json_data
            """
            try:
                from qmatsuite.provenance import get_pin_data as _get_pin_data
                return _get_pin_data(
                    self._service.project_root, run_ulid, step_ulid, analysis_kind
                )
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def get_latest_run_for_step(self, step_ulid: str) -> dict:
            """
            Get the latest run_ulid that includes a specific step.

            Args:
                step_ulid: Step ULID

            Returns:
                Dict with run_ulid, can_pin, reason
            """
            try:
                import sqlite3

                conn = sqlite3.connect(str(self._service._get_analysis_db_path()))
                try:
                    row = conn.execute(
                        """
                        SELECT r.run_ulid
                        FROM runs r
                        JOIN run_steps rs ON rs.run_ulid = r.run_ulid
                        WHERE rs.step_ulid = ? AND r.status = 'success'
                        ORDER BY COALESCE(r.finished_at, r.started_at) DESC
                        LIMIT 1
                        """,
                        (step_ulid,),
                    ).fetchone()
                finally:
                    conn.close()

                if row is None:
                    return {
                        "run_ulid": None,
                        "can_pin": False,
                        "reason": "No runs found in history",
                    }

                latest_run_ulid = str(row[0])

                return {
                    "run_ulid": latest_run_ulid,
                    "can_pin": True,
                    "reason": None,
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        def delete(self, confirm: bool = False) -> dict:
            """
            Delete the entire .provenance directory for a project.

            Args:
                confirm: Must be True to confirm deletion

            Returns:
                Dict with success, error, deleted_path
            """
            try:
                import shutil
                from qmatsuite.provenance import PROVENANCE_DIR_NAME

                if not confirm:
                    return {
                        "success": False,
                        "error": "Deletion requires confirmation (confirm: true)",
                    }

                project_root = self._service.project_root.resolve()
                provenance_dir = project_root / PROVENANCE_DIR_NAME

                # Validate path
                try:
                    provenance_dir_resolved = provenance_dir.resolve()
                    if not str(provenance_dir_resolved).startswith(str(project_root)):
                        return {
                            "success": False,
                            "error": "Security error: invalid path",
                        }
                    if provenance_dir_resolved.name != PROVENANCE_DIR_NAME:
                        return {
                            "success": False,
                            "error": "Security error: invalid provenance directory name",
                        }
                except Exception:
                    return {
                        "success": False,
                        "error": "Security error: path resolution failed",
                    }

                if not provenance_dir.exists():
                    return {
                        "success": True,
                        "deleted_path": None,
                        "message": "Provenance directory does not exist",
                    }

                shutil.rmtree(provenance_dir)
                return {
                    "success": True,
                    "deleted_path": str(provenance_dir),
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                return {"success": False, "error": str(e)}

    @property
    def history(self) -> History:
        """Access history capabilities."""
        return QMSService.History(self)

    # -------------------------------------------------------------------------
    # Static methods (backwards compatibility)
    # -------------------------------------------------------------------------
    
    @staticmethod
    def init_project(
        target_dir: Path | str,
        name: str | None = None,
        template: str | None = None,
    ) -> Path:
        """
        Initialize a new QMatSuite project.
        
        This is a backwards-compatibility wrapper for the legacy QMSService.init_project().
        It creates a new project directory with project.qms.yml and standard subdirectories.
        
        Args:
            target_dir: Directory to create the project in
            name: Project name (defaults to directory name)
            template: Optional template name (deprecated, not used)
            
        Returns:
            Path to project root
            
        Raises:
            ValueError: If target_dir is inside an existing project
            APIError: If project creation fails
        """
        try:
            from qmatsuite.core.context import detect_enclosing_project
            from qmatsuite.core.project_utils import save_project_config
            from qmatsuite.core.resources import generate_resource_id, slugify
            
            target_dir = Path(target_dir).resolve()
            
            # Check if target_dir is inside an existing project
            enclosing_project = detect_enclosing_project(target_dir)
            if enclosing_project:
                enclosing_project = Path(enclosing_project).resolve()
                allow_under_tmp = False
                try:
                    rel = target_dir.relative_to(enclosing_project)
                    allow_under_tmp = bool(rel.parts) and rel.parts[0] == ".tmp"
                except ValueError:
                    allow_under_tmp = False

                if not allow_under_tmp:
                    raise ValueError(
                        f"Cannot create a new project inside an existing QMatSuite project. "
                        f"The selected folder is inside a project at: {enclosing_project}. "
                        f"Please choose a parent folder above your current project directory."
                    )
            
            target_dir.mkdir(parents=True, exist_ok=True)
            
            project_name = name or target_dir.name
            project_slug = slugify(project_name)
            project_ulid = generate_resource_id()

            config = {
                "project": {
                    "name": project_name,
                    "meta": {
                        "ulid": project_ulid,  # CANONICAL: ulid not id
                        "name": project_name,
                        "slug": project_slug,
                        "path": ".",
                        "kind": "project",
                    },
                },
                "structures": [],
                "calculations": [],
            }
            
            save_project_config(target_dir, config)
            
            # Create standard directories
            (target_dir / "structures").mkdir(exist_ok=True)
            (target_dir / "calculations").mkdir(exist_ok=True)
            (target_dir / "pseudo").mkdir(exist_ok=True)
            (target_dir / "trash").mkdir(exist_ok=True)
            
            return target_dir
            
        except Exception as e:
            if isinstance(e, (ValueError, APIError)):
                raise
            raise map_kernel_exception(e)
    
    @staticmethod
    def get_settings() -> dict[str, Any]:
        """
        Get global QMatSuite settings.
        
        This is a backwards-compatibility wrapper for the legacy QMSService.get_settings().
        Returns global settings from .qmatsuite/config/settings.json with safe defaults.
        
        Returns:
            Dict with settings:
            - version: int
            - qe: dict with "bin_dir" (str | None)
            - debug_resolution: bool
            - max_concurrent_calcs: int
            - analysis_cache_enabled: bool
        """
        try:
            from qmatsuite.core.settings import load_settings
            
            settings = load_settings()
            return {
                "version": settings.version,
                "qe": {
                    "bin_dir": settings.qe.bin_dir,
                },
                "debug_resolution": settings.debug_resolution,
                "max_concurrent_calcs": settings.max_concurrent_calcs,
                "analysis_cache_enabled": settings.analysis_cache_enabled,
            }
        except Exception as e:
            if isinstance(e, APIError):
                raise
            # If loading fails, return safe defaults (matches load_settings behavior)
            # This ensures the daemon can still start even if settings file is corrupted
            return {
                "version": 1,
                "qe": {
                    "bin_dir": None,
                },
                "debug_resolution": False,
                "max_concurrent_calcs": 2,
                "analysis_cache_enabled": True,
            }
    
    @staticmethod
    def get_workflow_service() -> Any:
        """
        Get workflow service instance.
        
        Returns:
            WorkflowService instance
        """
        from qmatsuite.workflow.templates import get_workflow_service as _get_workflow_service
        return _get_workflow_service()
    
    @staticmethod
    def run_single_step(
        project_root: Path | str,
        calculation_selector: str,
        step_ulid: str,
        verbose: bool = False,
        *,
        index: Any = None,
        config: dict | None = None,
        run_ulid: str | None = None,
    ) -> dict[str, Any]:
        """
        Run a single step in a calculation by ULID (advanced feature, always runs).

        This is a variant of run_step that accepts step_ulid instead of step_selector.
        For backward compatibility with the daemon's job submission.

        Args:
            project_root: Project root path
            calculation_selector: Calculation selector
            step_ulid: Step ULID (must match a step in calculation.yaml)
            verbose: If True, print detailed output
            index: Optional resource index (for performance)
            config: Optional project config (for performance)
            run_ulid: External run ID to use (e.g., job_id from JobManager)

        Returns:
            Dict with step, step_ulid, step_type, success, error, input_file, output_file, etc.
        """
        # Delegate to nested run_step using step_ulid as the step_selector
        svc = QMSService(project_root)
        dto = svc.run.run_step(
            calc_selector=calculation_selector,
            step_selector=step_ulid,  # step_ulid works as a step selector
            run_ulid=run_ulid,
        )
        # Convert DTO to dict for backward compatibility with daemon
        return {
            "step": step_ulid,
            "step_ulid": dto.step_ulids[0] if dto.step_ulids else step_ulid,
            "step_type_gen": "unknown",  # DTO doesn't carry this, fallback
            "success": dto.status == "completed",
            "error": dto.error.message if dto.error else None,
            "input_file": dto.input_file,
            "output_file": dto.output_file,
            "io_dir": dto.io_dir,
            "working_dir": dto.io_dir,
            "run_ulid": dto.run_ulid,
        }

    @staticmethod
    def get_default_step_params(step_type_spec: str) -> dict[str, Any]:
        """
        Get default parameters for a step type (SPEC-keyed).

        Args:
            step_type_spec: SPEC step type (e.g., "qe_scf", "pyscf_scf").
                Non-QE engines return empty defaults.

        Returns:
            Dict with "parameters", "cards", and "species_overrides" keys.
            Returns empty dicts if step_type_spec is not recognized.
        """
        from qmatsuite.calculation.step_defaults import get_default_step_params as _get_default_step_params
        return _get_default_step_params(step_type_spec)

    @staticmethod
    def resolve_step_type_spec(step_type_gen: str, engine_family: str) -> str:
        """
        Resolve a GEN step type to a SPEC step type for a given engine.

        GEN layer: step_type_gen (e.g., "scf") - used in UI/workflow/presets
        SPEC layer: step_type_spec (e.g., "qe_scf") - persisted in step.yaml

        Args:
            step_type_gen: GEN step type (e.g., "scf", "relax") or SPEC type (returned as-is if valid)
            engine_family: Engine family (e.g., "qe", "pyscf", "lammps", "orca")

        Returns:
            SPEC step type (e.g., "qe_scf", "pyscf_scf", "lammps_relax")
            If step_type_gen is already a valid SPEC type, returns it as-is.
            If no match found, returns the original step_type_gen.
        """
        from qmatsuite.workflow.registry import get_registry
        registry = get_registry()
        spec_obj = registry.get_for_engine(step_type_gen, engine_family)
        return spec_obj.step_type_spec if spec_obj else step_type_gen

    @staticmethod
    def generate_kpath(
        structure: Any,  # pymatgen Structure
        points_per_segment: int = 10,
        path_type: str = "hinuma",
    ) -> Any:  # KPathResult
        """
        Generate high-symmetry k-path for a structure.

        This is a convenience method for generating k-paths for band structure calculations.

        Args:
            structure: pymatgen Structure object
            points_per_segment: Number of k-points per path segment
            path_type: Path convention ("hinuma" or "seekpath")

        Returns:
            KPathResult object with k-points and labels
        """
        from qmatsuite.analysis.kpath import generate_kpath as _generate_kpath
        return _generate_kpath(
            structure=structure,
            points_per_segment=points_per_segment,
            path_type=path_type,
        )

    # -------------------------------------------------------------------------
    # Demo Projects (Onboarding)
    # -------------------------------------------------------------------------

    @staticmethod
    def create_demo_project(
        target_dir: Path | str,
        name: str = "demo-si-project",
        demo_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a demo project from a bundled snapshot.

        This is the primary onboarding entry point for new users.
        Creates a ready-to-run project from qmatsuite/resources/demo_projects/.

        Args:
            target_dir: Directory to create the project in
            name: Project name
            demo_id: Demo snapshot ID (default 'si_bands_demo')

        Returns:
            Dict with project_root and demo_id

        Raises:
            ValueError: If target_dir is inside an existing project
            FileNotFoundError: If demo snapshot not found
        """
        from qmatsuite.core.resources import get_resources_dir
        from qmatsuite.core.project_utils import find_project_root
        from qmatsuite.project.snapshot import (
            ProjectSnapshot,
            materialize_project_from_snapshot,
        )
        import yaml

        target_dir = Path(target_dir).resolve()
        demo_name = demo_id or "si_bands_demo"

        # Check not inside existing project (allow under .tmp/ for E2E tests)
        enclosing = find_project_root(target_dir, max_levels=20)
        if enclosing is not None:
            enclosing_path = Path(enclosing).resolve()
            allow_under_tmp = False
            try:
                rel = target_dir.relative_to(enclosing_path)
                allow_under_tmp = bool(rel.parts) and rel.parts[0] == ".tmp"
            except ValueError:
                allow_under_tmp = False

            if not allow_under_tmp:
                raise ValueError(
                    f"Target directory is inside an existing QMatSuite project at: {enclosing}. "
                    "Please choose a parent workspace folder, not a project folder."
                )

        # Locate and load demo snapshot
        resources_dir = get_resources_dir()
        demo_snapshot_path = resources_dir / "demo_projects" / f"{demo_name}.yml"

        if not demo_snapshot_path.exists():
            available = [f.stem for f in (resources_dir / "demo_projects").glob("*.yml")]
            raise FileNotFoundError(
                f"Demo snapshot '{demo_name}' not found. "
                f"Available demos: {', '.join(available) or 'none'}"
            )

        with open(demo_snapshot_path, "r") as f:
            snapshot_data = yaml.safe_load(f)

        if not snapshot_data:
            raise ValueError(f"Demo snapshot '{demo_name}' is empty or invalid")

        snapshot = ProjectSnapshot.from_dict(snapshot_data)

        # Materialize project
        project_root = materialize_project_from_snapshot(
            snapshot=snapshot,
            parent_dir=target_dir,
            new_project_name=name,
        )

        # Inject demo_source into project settings (S11)
        from qmatsuite.core.project_utils import (
            load_project_config,
            save_project_config,
        )
        from qmatsuite.demo_store.manifest import read_manifest

        project_config = load_project_config(project_root)
        project_settings = project_config.get("project", {}).get("settings", {})

        # Read generator manifest for digest
        resources_dir = get_resources_dir()
        manifest = read_manifest(resources_dir / "demo_projects")
        demo_entry = manifest.get("demos", {}).get(demo_name, {})

        # Extract engine from snapshot meta
        snapshot_meta = snapshot_data.get("meta", {})
        engine = snapshot_meta.get("corpus_engine", demo_entry.get("engine", ""))

        from datetime import datetime, timezone
        project_settings["demo_source"] = {
            "demo_id": demo_name,
            "generator_digest": demo_entry.get("output_checksum", ""),
            "engine": engine,
            "materialized_at": datetime.now(timezone.utc).isoformat(),
        }

        # Write back the updated settings
        if "project" not in project_config:
            project_config["project"] = {}
        project_config["project"]["settings"] = project_settings
        save_project_config(project_root, project_config)

        result: dict[str, Any] = {
            "project_root": str(project_root),
            "demo_id": demo_name,
        }

        # Enrich with structure/calculation summaries for GUI
        try:
            svc = QMSService(project_root)
            summary = svc.get_summary()
            result["project_id"] = summary.get("id", "")
            result["project_name"] = summary.get("name", name)

            structures = svc.structure.list()
            if structures:
                s = structures[0]
                s_dict = s.to_dict() if hasattr(s, "to_dict") else {}
                result["structure"] = {
                    "structure_id": getattr(s, "structure_ulid", "") or s_dict.get("ulid", ""),
                    "name": getattr(s, "name", "") or s_dict.get("name", ""),
                    "slug": getattr(s, "slug", "") or s_dict.get("slug", ""),
                    "formula": getattr(s, "formula", "") or s_dict.get("formula", ""),
                    "n_atoms": getattr(s, "n_atoms", 0) or s_dict.get("n_atoms", 0),
                }
            else:
                result["structure"] = None

            calcs = svc.calculation.list()
            if calcs:
                c = calcs[0]
                c_dict = c.to_dict() if hasattr(c, "to_dict") else {}
                result["calculation"] = {
                    "calculation_id": c.calc_ulid,
                    "name": c_dict.get("name", ""),
                    "slug": c_dict.get("slug", ""),
                    "n_steps": c_dict.get("n_steps", 0) or c_dict.get("step_count", 0) or 0,
                }
            else:
                result["calculation"] = None

            result["ready_to_run"] = bool(result.get("structure") and result.get("calculation"))
        except Exception:
            result.setdefault("project_id", "")
            result.setdefault("project_name", name)
            result.setdefault("structure", None)
            result.setdefault("calculation", None)
            result.setdefault("ready_to_run", False)

        return result

    @staticmethod
    def list_demo_projects() -> list[dict[str, Any]]:
        """
        List available demo project snapshots.

        Returns:
            List of dicts with id, name, title, subtitle, description, tags for each demo.
            - title: Human-readable display name (e.g., "Silicon band structure")
            - subtitle: Workflow description (e.g., "SCF → NSCF → Bands")
            - name: Internal project name (for backwards compat)
        """
        from qmatsuite.core.resources import get_resources_dir
        import yaml

        resources_dir = get_resources_dir()
        demo_dir = resources_dir / "demo_projects"

        if not demo_dir.exists():
            return []

        demos = []
        for snapshot_path in sorted(demo_dir.glob("*.yml")):
            try:
                with open(snapshot_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                # Top-level meta contains display fields (title, subtitle, tags)
                demo_meta = data.get("meta", {})
                # project.meta contains internal project info
                project_data = data.get("project", {})
                project_meta = project_data.get("meta", {})

                # Use top-level meta.title for display, fallback to project.meta.name
                title = demo_meta.get("title") or project_meta.get("name") or snapshot_path.stem

                demos.append({
                    "ulid": snapshot_path.stem,
                    # name: Keep project.meta.name for backwards compat
                    "name": project_meta.get("name", snapshot_path.stem),
                    # title: Human-readable display name (GUI uses this for card titles)
                    "title": title,
                    # subtitle: Workflow description
                    "subtitle": demo_meta.get("subtitle", ""),
                    # description: Longer description
                    "description": demo_meta.get("description") or project_data.get("description", ""),
                    # tags: Category tags for filtering
                    "tags": demo_meta.get("tags", []),
                    # Extra fields from snapshot meta (GUI uses these for display)
                    "recommended_use": demo_meta.get("recommended_use", ""),
                    "recommended_analysis": demo_meta.get("recommended_analysis"),
                    "difficulty": demo_meta.get("difficulty"),
                    # estimated_runtime_s: wall-time seconds from audit (canonical name)
                    "estimated_runtime_s": demo_meta.get("estimated_runtime_s"),
                    # New enriched metadata fields
                    "system_class": demo_meta.get("system_class", ""),
                    "periodicity": demo_meta.get("periodicity", ""),
                    "method": demo_meta.get("method", ""),
                    "property_of_interest": demo_meta.get("property_of_interest", ""),
                    "spin_treatment": demo_meta.get("spin_treatment", ""),
                    "multi_engine": demo_meta.get("multi_engine", False),
                    "engines_used": demo_meta.get("engines_used", []),
                    "n_steps": demo_meta.get("n_steps"),
                    "step_summary": demo_meta.get("step_summary", ""),
                    "available_analysis": demo_meta.get("available_analysis", []),
                })
            except Exception:
                # Skip invalid snapshots
                continue

        return demos

    def load_demo_as_calculation(
        self, demo_id: str, name: str | None = None,
    ) -> dict[str, Any]:
        """Load a demo as a new calculation in the current project.

        Directly materializes the demo snapshot's structure, calculation, and
        step YAML files into the current project — mirroring how
        ``materialize_project_from_snapshot`` works, but without creating a
        new project.  Step YAML files are written verbatim from the snapshot
        (via ``StructureStepSpec``), preserving engine-specific parameter
        nesting exactly.

        Args:
            demo_id: Demo identifier (e.g., "qe_si_scf", "vasp_si_relax")
            name: Optional name for the calculation (defaults to demo title)

        Returns:
            Dict with calc_ulid, structure_ulid, demo_id, engine, name, steps

        Raises:
            FileNotFoundError: If demo snapshot not found
            ValueError: If demo snapshot is invalid or has no calculations
        """
        import json
        import yaml
        from qmatsuite.core.resources import (
            ResourceMeta,
            generate_resource_id,
            get_resources_dir,
            slugify,
        )
        from qmatsuite.core.models import (
            CalculationEntry,
            CalculationModel,
            CalculationStepEntry,
            StructureEntry,
            load_project,
            save_calculation,
            save_project,
            migrate_species_overrides_to_calc,
        )
        from qmatsuite.core.yamldoc import StepDoc
        from qmatsuite.core.yaml_io import save_yaml_doc
        from qmatsuite.calculation.structure_steps import StructureStepSpec
        from qmatsuite.project.snapshot import STRUCTURE_META_KEY, STRUCTURE_DATA_KEY

        # ── 1. Load demo YAML ──────────────────────────────────────
        resources_dir = get_resources_dir()
        demo_path = resources_dir / "demo_projects" / f"{demo_id}.yml"
        if not demo_path.exists():
            available = [
                f.stem for f in (resources_dir / "demo_projects").glob("*.yml")
            ]
            raise FileNotFoundError(
                f"Demo snapshot '{demo_id}' not found. "
                f"Available: {', '.join(sorted(available)) or 'none'}"
            )

        with open(demo_path, "r") as f:
            snapshot_data = yaml.safe_load(f)
        if not snapshot_data:
            raise ValueError(f"Demo snapshot '{demo_id}' is empty or invalid")

        calcs = snapshot_data.get("calculations", [])
        if not calcs:
            raise ValueError(f"Demo snapshot '{demo_id}' has no calculations")

        structures = snapshot_data.get("structures", [])
        demo_meta = snapshot_data.get("meta", {})
        calc_data = calcs[0]
        engine = calc_data.get("engine_family", "")
        project_root = self.project_root

        # ── 2. Load current project model ──────────────────────────
        project_model = load_project(project_root)

        # Build set of existing slugs for dedup
        existing_struct_slugs = {
            e.meta.slug for e in project_model.structures
        }
        existing_calc_slugs = {
            e.meta.slug for e in project_model.calculations
        }

        # ── 3. Import structure (write file + register in project) ─
        structure_ulid: str | None = None
        if structures:
            struct_entry_data = structures[0]
            struct_meta_data = struct_entry_data.get("meta", {})
            struct_name = struct_meta_data.get("name", demo_id)
            struct_slug = struct_meta_data.get("slug") or slugify(struct_name)

            # Dedup slug
            base_slug = struct_slug
            suffix = 2
            while struct_slug in existing_struct_slugs:
                struct_slug = f"{base_slug}-{suffix}"
                suffix += 1

            structure_ulid = generate_resource_id()
            struct_rel_path = f"structures/{struct_slug}.json"

            # Write structure JSON (same format as snapshot materialiser)
            structures_dir = project_root / "structures"
            structures_dir.mkdir(exist_ok=True)
            struct_file = structures_dir / f"{struct_slug}.json"
            struct_json = {
                STRUCTURE_META_KEY: {
                    "ulid": structure_ulid,
                    "name": struct_name,
                    "slug": struct_slug,
                    "path": struct_rel_path,
                    "kind": "structure",
                },
                STRUCTURE_DATA_KEY: struct_entry_data.get("data", {}),
            }
            struct_file.write_text(json.dumps(struct_json, indent=2))

            # Register in project model
            project_model.structures.append(
                StructureEntry(
                    meta=ResourceMeta(
                        ulid=structure_ulid,
                        name=struct_name,
                        slug=struct_slug,
                        path=struct_rel_path,
                        kind="structure",
                    ),
                    file=struct_rel_path,
                    format="auto",
                )
            )

        # ── 4. Create calculation directory + calculation.yaml ─────
        calc_meta_data = calc_data.get("meta", {})
        calc_name = name or demo_meta.get("title") or calc_meta_data.get("name") or demo_id
        calc_slug = slugify(calc_name)

        # Dedup slug
        base_slug = calc_slug
        suffix = 2
        while calc_slug in existing_calc_slugs:
            calc_slug = f"{base_slug}-{suffix}"
            suffix += 1

        calc_ulid = generate_resource_id()
        calc_rel_path = f"calculations/{calc_slug}"

        calc_dir = project_root / "calculations" / calc_slug
        calc_dir.mkdir(parents=True, exist_ok=True)
        steps_dir = calc_dir / "steps"
        steps_dir.mkdir(exist_ok=True)
        (calc_dir / "raw").mkdir(exist_ok=True)

        # Resolve species_map (same logic as snapshot materialiser)
        calc_species_map = calc_data.get("species_map")
        if not calc_species_map:
            step_species_list = [
                s.get("species_overrides")
                for s in calc_data.get("steps", [])
            ]
            if any(step_species_list):
                temp_calc = CalculationModel(
                    meta=ResourceMeta(
                        ulid=calc_ulid, name=calc_name, slug=calc_slug,
                        path=calc_rel_path, kind="calculation",
                    ),
                )
                temp_calc = migrate_species_overrides_to_calc(
                    temp_calc, step_species_list,
                )
                calc_species_map = temp_calc.species_map

        from datetime import datetime, timezone

        calc_model = CalculationModel(
            meta=ResourceMeta(
                ulid=calc_ulid,
                name=calc_name,
                slug=calc_slug,
                path=calc_rel_path,
                kind="calculation",
            ),
            structure_ulid=structure_ulid,
            engine_family=engine,
            mode=calc_data.get("mode", "normal"),
            working_dir=calc_data.get("working_dir", "raw"),
            steps=[],
            species_map=calc_species_map,
            demo_origin={
                "demo_id": demo_id,
                "engine": engine,
                "materialized_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # ── 5. Write step YAML files directly (same as snapshot) ───
        steps_out: list[dict[str, Any]] = []
        for idx, step_data in enumerate(calc_data.get("steps", [])):
            step_meta_data = step_data.get("meta", {})
            step_type_spec = step_data.get("step_type_spec", "step")
            step_name = step_meta_data.get("name") or step_type_spec
            step_slug = step_meta_data.get("slug") or slugify(step_name)

            # Dedup slug within this calculation
            base_step_slug = step_slug
            step_suffix = 1
            while (steps_dir / f"{step_slug}.step.yaml").exists():
                step_slug = f"{base_step_slug}-{step_suffix}"
                step_suffix += 1

            new_step_ulid = generate_resource_id()
            step_rel_path = f"{calc_rel_path}/steps/{step_slug}.step.yaml"

            # Build step spec dict — copy everything, update meta
            step_spec_dict = dict(step_data)
            step_spec_dict.pop("structure_ulid", None)
            step_spec_dict.pop("parent_calculation_id", None)
            step_spec_dict.pop("structure", None)

            if "step_type_spec" not in step_spec_dict:
                raise ValueError(
                    f"Step spec missing 'step_type_spec': {step_spec_dict}"
                )

            step_spec_dict["meta"] = {
                "ulid": new_step_ulid,
                "name": step_name,
                "slug": step_slug,
                "path": step_rel_path,
                "kind": "step",
            }

            # Roundtrip through StructureStepSpec for proper serialisation
            step_spec = StructureStepSpec.from_dict(step_spec_dict)

            step_file = steps_dir / f"{step_slug}.step.yaml"
            step_doc = StepDoc(step_spec.to_dict())
            save_yaml_doc(step_doc, step_file, skip_journal=True)

            calc_model.steps.append(
                CalculationStepEntry(
                    step_ulid=new_step_ulid,
                    step_type_spec=step_spec.step_type_spec,
                )
            )
            steps_out.append({
                "step_index": idx,
                "step_type_spec": step_spec.step_type_spec,
                "step_ulid": new_step_ulid,
            })

        # ── 6. Save calculation.yaml ───────────────────────────────
        save_calculation(calc_model, calc_dir / "calculation.yaml")

        # ── 7. Register calculation in project and save ────────────
        project_model.calculations.append(
            CalculationEntry(
                meta=ResourceMeta(
                    ulid=calc_ulid,
                    name=calc_name,
                    slug=calc_slug,
                    path=calc_rel_path,
                    kind="calculation",
                ),
            )
        )
        save_project(project_model, project_root)

        # ── 8. Create pseudo directory (empty — resolved at run time)
        pseudo_data = snapshot_data.get("pseudo")
        if pseudo_data:
            pseudo_dir = project_root / pseudo_data.get("directory", "pseudo")
            pseudo_dir.mkdir(exist_ok=True)

        return {
            "calc_ulid": calc_ulid,
            "structure_ulid": structure_ulid,
            "demo_id": demo_id,
            "engine": engine,
            "name": calc_name,
            "steps": steps_out,
        }

    # -------------------------------------------------------------------------
    # Pseudo Management (Global Operations)
    # -------------------------------------------------------------------------

    class Pseudo:
        """Pseudo-potential management capabilities (global operations)."""

        def __init__(self, service: QMSService):
            self._service = service

        @staticmethod
        def init_dirs() -> dict[str, Any]:
            """
            Initialize pseudopotential directories.

            Returns:
                Dict with: store_dir_created (bool), seed_dir_created (bool),
                messages (list), errors (list)
            """
            from qmatsuite.core.pseudo_config import load_pseudo_config, init_pseudo_dirs as _init_pseudo_dirs

            config = load_pseudo_config()
            return _init_pseudo_dirs(config)

        @staticmethod
        def list_libraries() -> list[dict[str, Any]]:
            """
            List available pseudopotential libraries.

            Returns:
                List of library dicts
            """
            from qmatsuite.core.library_manager import get_supported_libraries

            libraries = get_supported_libraries()
            return [lib.to_dict() if hasattr(lib, 'to_dict') else lib for lib in libraries]

        @staticmethod
        def get_library_status(library_id: str) -> dict[str, Any]:
            """
            Get status of a pseudopotential library.

            Args:
                library_id: Library identifier (e.g., "sssp_precision_1.3")

            Returns:
                Dict with library status
            """
            from qmatsuite.core.library_manager import get_library_status as _get_library_status

            status = _get_library_status(library_id)
            return status.to_dict() if hasattr(status, 'to_dict') else status

        @staticmethod
        def install_library(
            library_id: str,
            variants: list[str],
            source: str = "github_release",
            local_archive_paths: list[str] | None = None,
            force: bool = False,
            allow_download: bool | None = None,
        ) -> dict[str, Any]:
            """
            Install a pseudopotential library.

            Args:
                library_id: Library identifier
                variants: List of variant names to install
                source: Installation source ("github_release", "local_archive", or "seed")
                local_archive_paths: For source="local_archive", paths to archive files
                force: If True, download even if allow_download is False
                allow_download: Optional override for allow_download (uses config if None)

            Returns:
                Dict with installation result
            """
            from qmatsuite.core.library_manager import install_library as _install_library
            from qmatsuite.core.pseudo_config import load_pseudo_config, save_pseudo_config

            config = load_pseudo_config()
            if allow_download is None:
                allow_download = config.allow_download

            # If force=True and downloads are disabled, enable them automatically
            if force and not allow_download and source == "github_release":
                config.allow_download = True
                save_pseudo_config(config)
                allow_download = True

            result = _install_library(
                library_id=library_id,
                variants=variants,
                source=source,
                local_archive_paths=local_archive_paths,
                config=config,
                force=force,
                allow_download=allow_download,
            )
            return result

        @staticmethod
        def remove_library(library_id: str, variants: list[str] | None = None) -> dict[str, Any]:
            """
            Remove a pseudopotential library.

            Args:
                library_id: Library identifier
                variants: Optional list of variants to remove (removes all if None)

            Returns:
                Dict with removal result
            """
            from qmatsuite.core.library_manager import remove_library as _remove_library

            result = _remove_library(library_id=library_id, variants=variants)
            return result

        @staticmethod
        def repair_library(library_id: str, variants: list[str] | None = None) -> dict[str, Any]:
            """
            Repair a pseudopotential library (verify checksums, re-extract if needed).

            Args:
                library_id: Library identifier
                variants: List of variant names to repair (optional, repairs all if not specified)

            Returns:
                Dict with repair result
            """
            from qmatsuite.core.library_manager import repair_library as _repair_library

            result = _repair_library(library_id=library_id, variants=variants or [])
            return result

        @staticmethod
        def compute_store_size() -> dict[str, Any]:
            """
            Compute pseudopotential store size.

            Returns:
                Dict with total_bytes and breakdown by library
            """
            from qmatsuite.core.library_manager import compute_store_size as _compute_store_size

            return _compute_store_size()

        @staticmethod
        def download_and_install(
            library: str = "sssp",
            variant: str = "precision",
            version: str = "1.3.0",
        ) -> dict[str, Any]:
            """
            Download and install a pseudopotential library via NEW pipeline.

            Args:
                library: Library identifier (default: "sssp")
                variant: Library variant (default: "precision")
                version: Library version (default: "1.3.0")

            Returns:
                Dict with success, messages, errors, upf_count
            """
            from qmatsuite.pseudo.pipeline import download_and_install as _download_and_install

            return _download_and_install(library=library, variant=variant, version=version)

    @property
    def pseudo(self) -> Pseudo:
        """Access pseudo-potential management capabilities."""
        return QMSService.Pseudo(self)
