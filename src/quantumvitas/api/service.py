"""
QVService: Main API service class.

This module provides the QVService class which is the primary entry point
for all API operations.
"""

from __future__ import annotations

from pathlib import Path

from quantumvitas.api._mapping.dto_mapping import (
    structure_to_dto,
    calculation_to_dto,
    step_to_dto,
)
from quantumvitas.api._mapping.exc_mapping import map_kernel_exception
from quantumvitas.api.errors import APIError
from quantumvitas.api.types.calculation import CalculationDTO, CalculationRefDTO, StepDTO
from quantumvitas.api.types.run import RunResultDTO
from quantumvitas.api.types.structure import StructureDTO


class QVService:
    """
    Service layer for QuantumVITAS operations.
    
    PR3: Analysis capabilities added.
    """
    
    def __init__(self, project_root: Path):
        """
        Initialize QVService with a project root.
        
        Args:
            project_root: Path to project root (directory containing project.qv.yml)
        """
        self.project_root = Path(project_root).resolve()
        # Stub: minimal validation
        if not (self.project_root / "project.qv.yml").exists():
            raise ValueError(f"Not a project: {self.project_root}")
        self._analysis_cas_dir = self.project_root / ".provenance" / ".cas" / "analysis"
        self._analysis_memo_by_sha: dict[str, object] = {}
        self._analysis_index: dict[tuple[str, str], dict[str, object]] = {}

    def _safe_step_type_gen(self, step_type_spec: str) -> str:
        """Convert SPEC step type to GEN with robust fallback."""
        from quantumvitas.api import get_step_type_gen
        from quantumvitas.workflow.step_type_convert import gen_from

        try:
            return get_step_type_gen(step_type_spec)
        except Exception:
            return gen_from(step_type_spec)

    def _get_analysis_db_path(self) -> Path:
        from quantumvitas.provenance.db import ensure_provenance_initialized, get_db_path

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
    ) -> None:
        self._analysis_memo_by_sha[canonical_sha] = canonical
        self._analysis_index[(run_ulid, object_type.lower())] = {
            "canonical_sha": canonical_sha,
            "calc_dir": str(calc_dir),
            "evidence_fingerprint": evidence_fingerprint,
        }

    def _get_memoized_canonical_bundle(
        self,
        run_ulid: str,
        object_type: str,
    ) -> object | None:
        from quantumvitas.core.analysis.base import AnalysisObjectMeta, check_staleness

        index_entry = self._analysis_index.get((run_ulid, object_type.lower()))
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
            self._analysis_index.pop((run_ulid, object_type.lower()), None)
            return None
        return bundle

    def _persist_step_digest_rows(self, calculation: object, run_result: object) -> None:
        import json
        import logging
        from pathlib import Path as _Path

        from quantumvitas.parsers.registry import get_parser
        from quantumvitas.provenance import CAS, record_run_step
        from quantumvitas.workflow.step_type_convert import prefix_from

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
            ordered_steps.append((step_ulid, gen_step, raw_dir))
        return ordered_steps

    def _persist_eager_analysis_snapshots(self, calculation: object, run_result: object) -> None:
        import logging

        import quantumvitas.drivers  # noqa: F401 - ensure driver registration
        from quantumvitas.core.analysis.cas_writer import (
            write_analysis_snapshot_row,
            write_canonical_to_cas,
        )
        from quantumvitas.core.analysis.orchestrator import run_post_run_analysis
        from quantumvitas.core.driver_registry import DriverRegistry

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
                from quantumvitas.workflow.step_type_convert import prefix_from

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

        db_path = self._get_analysis_db_path()
        for row in results:
            canonical = row["canonical"]
            object_type = str(row["object_type"])
            try:
                canonical_sha = write_canonical_to_cas(canonical, self._analysis_cas_dir)
                provenance = canonical.provenance_meta
                match_key = f"{object_type}:{','.join(provenance.step_ulids)}"
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

    def _resolve_run_analysis_context(
        self, run_ulid: str
    ) -> tuple[str, Path, str, object, list[tuple[str, str, Path]]]:
        from quantumvitas.provenance import get_run_details
        from quantumvitas.core.models import load_calculation
        from quantumvitas.core.project_utils import load_project_config
        from quantumvitas.core.resolution import make_structure_selector_resolver, require_calculation
        from quantumvitas.core.driver_registry import DriverRegistry
        from quantumvitas.calculation.naming import find_calculation_raw_dir

        run_details = get_run_details(self.project_root, run_ulid)
        if not run_details:
            from quantumvitas.api.errors import NotFoundError

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
                from quantumvitas.workflow.step_type_convert import prefix_from

                engine = prefix_from(first_spec)
        if not engine:
            from quantumvitas.api.errors import ValidationError

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
            # Prefer per-step raw evidence directory when present; fallback to
            # calculation raw root for legacy/non-step-scoped outputs.
            step_raw_dir = raw_dir / step_ulid
            evidence_dir = step_raw_dir if step_raw_dir.exists() else raw_dir
            ordered_gen_steps.append((step_ulid, gen_step, evidence_dir))

        return str(calc_ulid), calc_dir, engine, driver, ordered_gen_steps

    def _derive_canonical_for_run_object(self, run_ulid: str, object_type: str) -> object:
        from quantumvitas.core.analysis.bundles import compute_canonical_sha
        from quantumvitas.core.analysis.cas_writer import (
            write_analysis_snapshot_row,
            write_canonical_to_cas,
        )
        from quantumvitas.core.analysis.orchestrator import run_post_run_analysis

        calc_ulid, calc_dir, engine, driver, ordered_gen_steps = self._resolve_run_analysis_context(
            run_ulid
        )
        if not ordered_gen_steps:
            from quantumvitas.api.errors import NotFoundError

            raise NotFoundError(f"No run steps available for run {run_ulid}")

        memoized = self._get_memoized_canonical_bundle(run_ulid, object_type)
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

        selected = None
        for row in results:
            if str(row.get("object_type", "")).lower() == object_type.lower():
                selected = row
                break
        if selected is None:
            from quantumvitas.api.errors import NotFoundError

            raise NotFoundError(
                f"Analysis object '{object_type}' not available for run {run_ulid}"
            )

        canonical = selected["canonical"]
        canonical_sha = compute_canonical_sha(canonical)
        provenance = canonical.provenance_meta
        match_key = f"{object_type}:{','.join(provenance.step_ulids)}"
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
        )
        return canonical

    def _load_snapshot_bundle(self, run_ulid: str, object_type: str) -> tuple[str, object]:
        import gzip
        import json
        import sqlite3

        from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle

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
            from quantumvitas.api.errors import NotFoundError

            raise NotFoundError(
                f"No snapshot found for run={run_ulid}, object_type={object_type}"
            )

        canonical_sha = row[0]
        blob_path = self._analysis_cas_dir / f"{canonical_sha}.json.gz"
        if not blob_path.exists():
            from quantumvitas.api.errors import NotFoundError

            raise NotFoundError(
                f"Snapshot blob missing for sha={canonical_sha} (run={run_ulid}, object_type={object_type})"
            )

        with gzip.open(blob_path, "rb") as handle:
            payload = json.loads(handle.read().decode("utf-8"))
        return canonical_sha, CanonicalPrimitiveBundle.from_dict(payload)
    
    # Analysis domain (PR3)
    class Analysis:
        """Analysis capabilities."""
        
        def __init__(self, service: QVService):
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
                from quantumvitas.calculation.naming import find_calculation_raw_dir, CalculationFileNaming
                from quantumvitas.core.resolution import require_calculation, require_step
                from quantumvitas.calculation.structure_steps import StructureStepSpec
                from quantumvitas.workflow.registry import normalize_step_type_to_gen
                from quantumvitas.calculation.step_artifacts import get_step_artifacts, get_default_artifact

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
                    from quantumvitas.core.models import load_calculation
                    from quantumvitas.core.project_utils import load_project_config
                    from quantumvitas.core.resolution import make_structure_selector_resolver
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
                from quantumvitas.calculation.naming import find_calculation_raw_dir
                from quantumvitas.core.resolution import require_calculation, require_step
                from quantumvitas.api.errors import ValidationError, NotFoundError

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

                # Normalize to filename only
                artifact_path_normalized = artifact_path_obj.name
                file_path = raw_dir_resolved / artifact_path_normalized

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
                    from quantumvitas.api.errors import EngineError
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
                    from quantumvitas.api.errors import EngineError
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
                from quantumvitas.analysis.parsers import parse_scf_output
                from quantumvitas.analysis.plotting import plot_scf_convergence, save_figure

                project_root = self._service.project_root
                scf_file = Path(scf_file).resolve()
                if not scf_file.exists():
                    from quantumvitas.api.errors import NotFoundError
                    raise NotFoundError(f"SCF output file not found: {scf_file}")

                # Parse SCF output
                result = parse_scf_output(scf_file)
                data = result.to_dict()

                # Determine output directory
                local_output_dir = output_dir
                if local_output_dir is None and project_root:
                    from quantumvitas.calculation.naming import find_calculation_results_dir
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
            from quantumvitas.calculation.naming import find_calculation_raw_dir
            from quantumvitas.core.resolution import require_calculation, require_step

            calculation = require_calculation(self._service.project_root, calculation_selector)
            require_step(self._service.project_root, calculation_selector, step_selector)

            if calculation.absolute_path.name == "calculation.yaml":
                calculation_dir = calculation.absolute_path.parent
            else:
                calculation_dir = calculation.absolute_path

            raw_dir = find_calculation_raw_dir(calculation_dir)
            if not raw_dir.exists():
                from quantumvitas.api.errors import NotFoundError

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

        def read_raw_file(
            self,
            calculation_selector: str,
            step_selector: str,
            filename: str,
            *,
            head_lines: int | None = 1000,
            tail_lines: int | None = 100,
        ) -> dict:
            """
            Surface A wrapper: read one raw text artifact for a step.
            """
            return self.read_step_artifact_text(
                calculation_selector=calculation_selector,
                step_selector=step_selector,
                artifact_path=filename,
                head_lines=head_lines,
                tail_lines=tail_lines,
            )

        def get_step_digest(self, run_ulid: str, step_ulid: str) -> dict:
            """
            Surface B: return post-run digest payload for one step.
            """
            import json
            import sqlite3

            from quantumvitas.provenance import CAS

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
                from quantumvitas.api.errors import NotFoundError

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
            from quantumvitas.api.errors import ValidationError
            from quantumvitas.core.analysis.bundles import compute_canonical_sha
            from quantumvitas.core.analysis.transforms.fermi_shift import FermiShift

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

        def get_reference_analysis(
            self,
            calculation_selector: str,
            analysis_type: str,
        ) -> dict | None:
            """
            Get reference analysis data for demo projects.

            If the project was created from a demo snapshot that includes reference
            artifacts, this returns the reference data for comparison.

            Args:
                calculation_selector: Calculation selector
                analysis_type: Type of analysis ("scf", "dos", "bands")

            Returns:
                Dict with reference analysis data, or None if not a demo project
            """
            try:
                import json
                from quantumvitas.core.project_utils import load_project_config
                from quantumvitas.core.resources import get_resources_dir

                project_root = self._service.project_root
                config = load_project_config(project_root)

                # Check if project has demo origin
                project_settings = config.get("project", {}).get("settings", {})
                origin = project_settings.get("origin", {})

                if origin.get("kind") != "demo":
                    return None

                demo_id = origin.get("demo_id")
                if not demo_id:
                    return None

                # Get reference_artifacts mapping
                reference_artifacts = origin.get("reference_artifacts", {})

                # If no reference_artifacts in project settings, try snapshot meta
                if not reference_artifacts:
                    resources_dir = get_resources_dir()
                    demo_snapshot_path = resources_dir / "demo_projects" / f"{demo_id}.yml"
                    if demo_snapshot_path.exists():
                        import yaml
                        try:
                            snapshot_data = yaml.safe_load(demo_snapshot_path.read_text())
                            snapshot_meta = snapshot_data.get("meta", {})
                            reference_artifacts = snapshot_meta.get("reference_artifacts", {})
                        except Exception:
                            pass

                # Check if reference artifact exists for this analysis type
                artifact_filename = reference_artifacts.get(analysis_type)
                if not artifact_filename:
                    return None

                # Load reference JSON from demo_projects directory
                resources_dir = get_resources_dir()
                reference_path = resources_dir / "demo_projects" / artifact_filename

                if not reference_path.exists():
                    return None

                data = json.loads(reference_path.read_text())
                data["_is_reference"] = True
                data["_reference_source"] = demo_id

                return data
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

        # NOTE: find_band_files REMOVED - use quantumvitas.calculation.naming.find_band_analysis_files directly

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
                from quantumvitas.calculation.geometry import (
                    read_final_geometry_from_output_text,
                    structure_from_qe_geometry_snapshot,
                )
                from quantumvitas.calculation.naming import CalculationFileNaming, find_calculation_raw_dir
                from quantumvitas.core.models import load_calculation
                from quantumvitas.core.project_utils import load_project_config
                from quantumvitas.core.resolution import resolve_calculation, resolve_step
                from quantumvitas.calculation.structure_steps import StructureStepSpec
                from quantumvitas.api.errors import ValidationError

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
                from quantumvitas.api import get_step_type_gen
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

    @property
    def analysis(self) -> Analysis:
        """Access analysis capabilities."""
        return QVService.Analysis(self)

    # Structure domain (PR4)
    class Structure:
        """Structure capabilities."""
        
        def __init__(self, service: QVService):
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
                from quantumvitas.core.resolution import require_structure
                from quantumvitas.core.models import load_structure_model
                from quantumvitas.io.structure_io import read_structure
                
                # Resolve structure
                struct_resolved = require_structure(self._service.project_root, selector)
                
                # Load structure file
                struct_path = struct_resolved.absolute_path
                if not struct_path.exists():
                    from quantumvitas.api.errors import NotFoundError
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
                from quantumvitas.core.resolution import list_structures
                from quantumvitas.core.models import load_structure_model
                from quantumvitas.io.structure_io import read_structure
                
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
                from quantumvitas.core.resolution import require_structure
                from quantumvitas.io.structure_io import read_structure
                
                # Resolve and load structure
                struct_resolved = require_structure(self._service.project_root, selector)
                struct_path = struct_resolved.absolute_path
                
                if not struct_path.exists():
                    from quantumvitas.api.errors import NotFoundError
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
                from quantumvitas.core.resolution import require_structure
                return require_structure(self._service.project_root, selector)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def visualize(self, selector: str, format: str = "json") -> dict:
            """
            Get structure visualization data.
            
            Args:
                selector: Structure selector
                format: Output format ("json" for data, "png"/"svg" for images)
                
            Returns:
                Dict with visualization data
                
            Raises:
                APIError: If structure not found
            """
            try:
                from quantumvitas.core.resolution import require_structure
                from quantumvitas.io.structure_io import read_structure
                from quantumvitas.analysis.structure_viz import visualize_structure
                
                # Resolve and load structure
                struct_resolved = require_structure(self._service.project_root, selector)
                struct_path = struct_resolved.absolute_path
                
                if not struct_path.exists():
                    from quantumvitas.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Structure file not found: {struct_path}",
                        context={"selector": selector}
                    )
                
                pmg_structure = read_structure(struct_path)
                
                # Generate visualization
                if format == "json":
                    # Return JSON-serializable visualization data
                    # For now, return basic structure info for visualization
                    # Full visualization would require the structure_viz module
                    structure_ulid = struct_resolved.meta.ulid if struct_resolved.meta else ""
                    return {
                        "structure_ulid": structure_ulid,
                        "structure_ulid": structure_ulid,  # Backwards compat
                        "num_atoms": len(pmg_structure),
                        "formula": pmg_structure.formula,
                    }
                else:
                    # For image formats, use the visualization function
                    # This is a simplified version - full implementation would generate images
                    result = visualize_structure(
                        structure=pmg_structure,
                        output_path=None,  # Don't save, just get data
                        plot_format=format,
                    )
                    structure_ulid = struct_resolved.meta.ulid if struct_resolved.meta else ""
                    return {
                        "structure_ulid": structure_ulid,
                        "structure_ulid": structure_ulid,  # Backwards compat
                        "n_atoms": result.n_atoms if hasattr(result, "n_atoms") else len(pmg_structure),
                        "format": format,
                    }
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
                from quantumvitas.io import read_structure as _read_structure, write_structure as _write_structure
                from quantumvitas.core.project_utils import load_project_config, save_project_config, collect_slugs
                from quantumvitas.core.resolution import require_structure
                from quantumvitas.core.models import load_structure_model
                from quantumvitas.io.structure_io import read_structure
                from quantumvitas.core.structure_fingerprint import structure_like_fingerprint, DEFAULT_FINGERPRINT_TOL_ANG
                from quantumvitas.core.structure_canonicalize import canonicalize_structure_like_in_place
                from quantumvitas.core.resources import (
                    generate_unique_name_and_slug,
                    meta_from_name,
                    ensure_relative_path,
                )
                import json

                project_root = self._service.project_root
                source_path = Path(source).resolve()
                if not source_path.exists():
                    from quantumvitas.api.errors import NotFoundError
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
                            struct_meta = struct_data.get("__qv_meta__") or struct_data.get("meta") or {}
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
                                struct_meta = struct_data.get("__qv_meta__") or struct_data.get("meta") or {}
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
                from quantumvitas.io import read_structure as _read_structure
                from quantumvitas.core.resolution import resolve_structure
                from quantumvitas.analysis.structure_viz import (
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
                    from quantumvitas.api.errors import NotFoundError
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
                    "structure_ulid": structure_ulid,  # Backwards compat
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
                from quantumvitas.core.project_utils import (
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
                from quantumvitas.core.resolution import require_structure
                from quantumvitas.core.project_utils import (
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
                from quantumvitas.core.resolution import require_structure
                from quantumvitas.core.project_utils import (
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
                    from quantumvitas.api.errors import ConflictError
                    raise ConflictError(
                        f"Structure is used by {len(dependent)} calculation(s)",
                        context={"dependent_calculations": [c.get("meta", {}).get("name", "?") for c in dependent]}
                    )

                # Remove from project.qv.yml
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
                from quantumvitas.core.resolution import require_calculation, require_step
                from quantumvitas.core.project_utils import load_project_config
                from quantumvitas.execution.relax_artifacts import get_generated_structure_path
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
                    from quantumvitas.api.errors import ValidationError
                    raise ValidationError(
                        f"Step '{step_selector}' is not a relax step (type: {step_type_spec})"
                    )

                # Find generated structure (uses step ULID for path)
                calculation_dir = calc_resolved.absolute_path
                generated_path = get_generated_structure_path(calculation_dir, step_resolved.meta.ulid)

                if generated_path is None or not generated_path.exists():
                    from quantumvitas.api.errors import NotFoundError
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
            from quantumvitas.calculation.geometry import (
                read_final_geometry_from_output_text,
                structure_from_qe_geometry_snapshot,
            )
            from quantumvitas.calculation.naming import CalculationFileNaming, find_calculation_raw_dir
            from quantumvitas.calculation.structure_steps import StructureStepSpec
            from quantumvitas.core.models import load_calculation
            from quantumvitas.core.project_utils import load_project_config, save_project_config, collect_slugs
            from quantumvitas.core.resolution import resolve_calculation, resolve_step
            from quantumvitas.core.resources import (
                ensure_relative_path,
                generate_unique_name_and_slug,
                meta_from_name,
            )
            from quantumvitas.io.structure_io import write_structure
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
            from quantumvitas.api import get_step_type_gen
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

            # Find output file
            base_output = raw_dir / CalculationFileNaming.output_filename(step_gen, working_dir=None)
            if base_output.exists():
                output_file = base_output
            else:
                output_filename = CalculationFileNaming.output_filename(step_gen, working_dir=raw_dir)
                output_file = raw_dir / output_filename

            if not output_file.exists():
                raise FileNotFoundError(
                    f"Output file not found for step '{step_selector}': {output_file}. "
                    f"Step may not have completed successfully."
                )

            # Parse final geometry
            output_text = output_file.read_text()
            snapshot, species = read_final_geometry_from_output_text(output_text)

            # Convert to structure
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
            from quantumvitas.core.yamldoc import StepDoc
            from quantumvitas.workflow.step_factory import save_step_doc

            step_doc = StepDoc.load(step_resolved.absolute_path)
            step_doc.set(["produced_structure_ulid"], meta.ulid)
            save_step_doc(step_doc, step_resolved.absolute_path)

            # Update registry in-place if index is provided
            if index is not None:
                from quantumvitas.core.resolution import update_registry_add_structure
                update_registry_add_structure(index, meta, dest_path)

            return {
                "structure_ulid": meta.ulid,
                "already_exists": False,
            }

    @property
    def structure(self) -> Structure:
        """Access structure capabilities."""
        return QVService.Structure(self)

    # Calculation domain (PR5)
    class Calculation:
        """Calculation read capabilities."""
        
        def __init__(self, service: QVService):
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
                from quantumvitas.core.resolution import require_calculation
                from quantumvitas.core.models import load_calculation
                from quantumvitas.project.model import Project
                
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
                    from quantumvitas.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Calculation file not found: {calc_yaml}",
                        context={"selector": selector, "path": str(calc_dir)}
                    )
                
                project = Project.open(self._service.project_root)
                calc_model = load_calculation(calc_yaml, self._service.project_root)
                
                # Load full Calculation object for step info
                from quantumvitas.calculation.calculation import Calculation
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
        
        def list(self, project_selector: str | None = None, status: str | None = None) -> list[CalculationDTO]:
            """
            List calculations in project.
            
            Args:
                project_selector: Unused (for future multi-project support)
                status: Optional status filter (pending, running, completed, failed)
                
            Returns:
                List of CalculationDTO
                
            Raises:
                APIError: If project invalid
            """
            try:
                from quantumvitas.core.resolution import list_calculations
                from quantumvitas.core.models import load_calculation
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation

                # List all calculations
                calc_resolved_list = list_calculations(self._service.project_root)
                
                project = Project.open(self._service.project_root)
                results = []
                
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
                        
                        # Load calculation model and object
                        calc_model = load_calculation(calc_yaml, self._service.project_root)
                        calc_obj = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
                        
                        # Build CalculationDTO
                        dto = calculation_to_dto(
                            calc_resolved=calc_resolved,
                            calc_model=calc_model,
                            calc_obj=calc_obj,
                        )
                        
                        # Filter by status if requested
                        if status is None or dto.status == status:
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
                from quantumvitas.core.resolution import require_calculation
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
                from quantumvitas.core.resolution import require_step
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
                from quantumvitas.core.project_utils import find_enclosing_calculation
                from quantumvitas.api.utils import ensure_relative_path, extract_selector_from_entry
                from quantumvitas.api._mapping.dto_mapping import calculation_ref_to_dto
                
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
                from quantumvitas.api.errors import NotFoundError
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
                from quantumvitas.core.resolution import require_calculation, require_step
                from quantumvitas.core.models import load_calculation
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation
                
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
                    from quantumvitas.api.errors import NotFoundError
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
                from quantumvitas.core.resolution import require_calculation, require_step, make_structure_selector_resolver
                from quantumvitas.calculation.structure_steps import StructureStepSpec
                from quantumvitas.core.project_utils import load_project_config
                from quantumvitas.api._mapping.dto_mapping import step_to_dict

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
                from quantumvitas.core.resolution import require_calculation, list_steps
                from quantumvitas.core.models import load_calculation
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation
                
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
                from quantumvitas.core.project_utils import load_project_config, save_project_config, collect_slugs
                from quantumvitas.core.resolution import require_structure, ResolvedResource
                from quantumvitas.core.models import load_calculation, save_calculation, CalculationModel
                from quantumvitas.core.resources import (
                    ResourceMeta,
                    generate_unique_name_and_slug,
                    generate_resource_id,
                )
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation

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
                    from quantumvitas.core.templates import copy_calculation_template
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
                from quantumvitas.core.resolution import require_calculation
                from quantumvitas.core.models import load_calculation, save_calculation
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation
                
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
                        from quantumvitas.core.resources import slugify
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
                from quantumvitas.core.resolution import ResolvedResource
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
                from quantumvitas.core.resolution import require_calculation, require_step
                from quantumvitas.core.yamldoc import StepDoc
                from quantumvitas.workflow.step_factory import save_step_doc
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation
                from quantumvitas.calculation.step import Step
                from quantumvitas.core.resources import ResourceMeta
                from quantumvitas.core.resolution import ResolvedResource
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
                from quantumvitas.workflow.registry import get_registry
                from quantumvitas.workflow.step_type_convert import gen_from
                registry = get_registry()
                step_type_spec = step_data.get("step_type_spec", "scf")
                step_type_gen = gen_from(step_type_spec)  # Convert SPEC to GEN for registry
                step_spec = registry.get(step_type_gen)
                if step_spec is None:
                    from quantumvitas.workflow.step_type_convert import prefix_from
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
                from quantumvitas.core.resolution import require_calculation
                from quantumvitas.core.models import load_calculation
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation
                from quantumvitas.core.resources import generate_resource_id
                from quantumvitas.core.project_utils import slugify, load_project_config, save_project_config
                from quantumvitas.core.templates import _copy_calculation_from_path
                from quantumvitas.core.resolution import ResolvedResource
                
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
                    from quantumvitas.api.errors import ConflictError
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
                from quantumvitas.core.resolution import require_calculation
                from quantumvitas.core.project_utils import load_project_config, calculations_depending_on

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
                from quantumvitas.core.resolution import require_calculation
                from quantumvitas.core.project_utils import (
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
                    from quantumvitas.api.errors import NotFoundError
                    raise NotFoundError(
                        f"Calculation not found in project config: {selector}",
                        context={"selector": selector}
                    )

                # Check dependencies if not forcing
                if not force:
                    deps = calculations_depending_on(config, entry)
                    if deps:
                        from quantumvitas.api.errors import ConflictError
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
                from quantumvitas.core.resolution import require_calculation, resolve_structure
                from quantumvitas.core.models import load_calculation
                from quantumvitas.core.project_utils import load_project_config
                from quantumvitas.core.resolution import make_structure_selector_resolver
                from quantumvitas.io.structure_io import read_structure
                from quantumvitas.calculation.structure_steps import StructureStepSpec

                # Resolve calculation
                calc_resolved = require_calculation(self._service.project_root, selector)

                # Get calculation directory and yaml path
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calc_dir = calc_resolved.absolute_path.parent
                    calc_yaml = calc_resolved.absolute_path
                else:
                    calc_dir = calc_resolved.absolute_path
                    calc_yaml = calc_dir / "calculation.yaml"

                # Load config
                config = load_project_config(self._service.project_root)
                resolver = make_structure_selector_resolver(self._service.project_root, config=config)

                # Load calculation model
                calc_model = load_calculation(calc_yaml, project_root=self._service.project_root, resolve_structure_selector=resolver)

                # Get structure info
                structure_name = None
                structure_ulid = calc_model.structure_ulid
                structure_elements = []

                if structure_ulid:
                    try:
                        struct_resolved = resolve_structure(self._service.project_root, structure_ulid, config=config)
                        structure_name = struct_resolved.meta.name if struct_resolved.meta else None
                        if struct_resolved.absolute_path.exists():
                            structure = read_structure(struct_resolved.absolute_path)
                            structure_elements = sorted(set(str(el) for el in structure.composition.elements))
                    except Exception:
                        pass

                # Build step summaries
                # Use ResourceIndex to resolve step paths (step files are named by slug, not ULID)
                from quantumvitas.core.resolution import build_resource_index, resolve_step
                step_index = build_resource_index(self._service.project_root)
                calc_ulid_for_resolve = calc_resolved.meta.ulid if calc_resolved.meta else selector

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
                            index=step_index,
                        )
                        step_path = step_resolved.absolute_path
                    except Exception:
                        # If resolution fails, step is missing
                        pass

                    # Use entry.step_type_spec (SPEC type from calculation.yaml) as primary
                    step_type_spec = entry.step_type_spec
                    step_name = step_resolved.meta.name if step_resolved and step_resolved.meta else step_ulid
                    step_status = "pending"

                    if step_path and step_path.exists():
                        try:
                            spec = StructureStepSpec.from_yaml(step_path, resolve_structure_selector=resolver)
                            # Only use spec.step_type_spec if entry didn't have one
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
                            from quantumvitas.api import get_step_type_gen
                            step_type_gen = get_step_type_gen(step_type_spec)
                        except (KeyError, ValueError):
                            pass
                    
                    step_summaries.append({
                        "ulid": step_ulid,  # Backwards compat
                        "step_ulid": step_ulid,
                        "step_type_spec": step_type_spec,
                        "step_type_gen": step_type_gen if step_type_gen else step_type_spec,
                        "type": step_type_gen if step_type_gen else step_type_spec,  # Backwards compat alias
                        "name": step_name,
                        "status": step_status,
                        "missing": not (step_path and step_path.exists()),
                    })

                calc_ulid = calc_resolved.meta.ulid if calc_resolved.meta else selector
                return {
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
                }
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)

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
                from quantumvitas.core.resolution import require_calculation, resolve_structure
                from quantumvitas.core.models import load_calculation, save_calculation
                from quantumvitas.core.project_utils import load_project_config
                from quantumvitas.core.resolution import make_structure_selector_resolver
                from quantumvitas.calculation.structure_steps import StructureStepSpec
                from quantumvitas.core.yamldoc import StepDoc
                from quantumvitas.workflow.step_factory import save_step_doc

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
                from quantumvitas.core.resolution import require_calculation, require_step
                from quantumvitas.calculation.k_points_view import parse_k_points, k_points_from_card_data
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
                from quantumvitas.core.resolution import require_calculation, require_step
                from quantumvitas.core.models import load_calculation, save_calculation
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation
                from quantumvitas.workflow.step_factory import create_and_save_step
                from quantumvitas.workflow.registry import get_registry
                from quantumvitas.core.resources import generate_resource_id
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
                    # Try generic lookup as fallback
                    spec = registry.get(step_type_gen)
                if not spec:
                    # Unknown step_type_gen
                    from quantumvitas.api.errors import ValidationError
                    raise ValidationError(
                        f"Unknown step type: {step_type_gen}",
                        code="VALIDATION_FAILED",
                        context={"step_type_gen": step_type_gen}
                    )
                
                # Use gen type for calculation.yaml (registry.get() accepts both gen and spec types)
                public_step_type = spec.step_type_gen
                
                # Create steps directory
                steps_dir = calc_dir / "steps"
                steps_dir.mkdir(parents=True, exist_ok=True)

                # Generate unique slug (deduplicate against existing step files)
                from quantumvitas.core.resources import slugify
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
                    from quantumvitas.api.errors import InternalError
                    raise InternalError(
                        "Step created but missing ULID in meta",
                        context={"step_path": str(step_path)}
                    )
                
                # Add step to calculation.yaml steps array
                # Use step_type_spec (SPEC value) for calculation.yaml
                from quantumvitas.core.models import CalculationStepEntry
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
                from quantumvitas.core.resources import ResourceMeta
                from quantumvitas.core.resolution import ResolvedResource
                from quantumvitas.calculation.step import Step
                
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
                from quantumvitas.workflow.step_type_convert import gen_from
                step_type_gen = gen_from(step_type_spec)
                step_spec = registry.get(step_type_gen)
                if step_spec is None:
                    from quantumvitas.workflow.step_type_convert import prefix_from
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
                from quantumvitas.core.resolution import require_calculation
                from quantumvitas.core.models import load_calculation, save_calculation, CalculationStepEntry
                from quantumvitas.core.yamldoc import StepDoc
                from quantumvitas.workflow.step_factory import save_step_doc
                import yaml

                # Validate step_spec has required fields
                meta = step_spec.get("meta", {})
                step_ulid = meta.get("ulid")
                step_type_spec = step_spec.get("step_type_spec")
                if not step_ulid:
                    from quantumvitas.api.errors import ValidationError
                    raise ValidationError(
                        "step_spec.meta.ulid is required",
                        code="VALIDATION_FAILED"
                    )
                if not step_type_spec:
                    from quantumvitas.api.errors import ValidationError
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
                from quantumvitas.api.utils import ensure_relative_path
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
                from quantumvitas.core.resolution import require_calculation, require_step, ResourceNotFoundError
                from quantumvitas.core.models import load_calculation, save_calculation
                from quantumvitas.core.project_utils import load_project_config, move_to_trash
                from quantumvitas.core.resolution import make_structure_selector_resolver
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
                    from quantumvitas.api.errors import NotFoundError
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
                from quantumvitas.core.resolution import require_calculation, require_step
                from quantumvitas.core.models import load_calculation, save_calculation
                from quantumvitas.core.project_utils import load_project_config
                from quantumvitas.core.yamldoc import StepDoc
                from quantumvitas.workflow.step_factory import save_step_doc
                from quantumvitas.core.resources import slugify
                from quantumvitas.api.utils import ensure_relative_path
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
                from quantumvitas.core.resolution import make_structure_selector_resolver
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
                    from quantumvitas.api.errors import NotFoundError
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
                            from quantumvitas.api.errors import ValidationError
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
                from quantumvitas.core.resolution import resolve_calculation
                from quantumvitas.core.project_utils import load_project_config, find_calculation_entry
                from quantumvitas.core.resources import slugify

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
                from quantumvitas.core.resolution import validate_ulid, resolve_step, make_structure_selector_resolver
                from quantumvitas.calculation.k_points_view import (
                    KPointsViewModel, KPointsAutomatic, KPointsPoint,
                    format_k_points, k_points_to_card_data,
                )
                from quantumvitas.calculation.structure_steps import StructureStepSpec
                from quantumvitas.core.project_utils import load_project_config
                from quantumvitas.core.yamldoc import StepDoc
                from quantumvitas.workflow.step_factory import save_step_doc

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
                    step_doc.set(["cards", "K_POINTS"], card_data)
                    save_step_doc(step_doc, step.absolute_path)
                else:
                    from quantumvitas.api.errors import ValidationError
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
                from quantumvitas.core.resolution import validate_ulid, resolve_structure
                from quantumvitas.core.project_utils import load_project_config
                from quantumvitas.io import read_structure
                from quantumvitas.core.pseudo_config import PseudoConfig, get_sssp_library_path
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

                # Check SSSP libraries
                sssp_defaults: dict[str, dict[str, str]] = {}
                sssp_installed: dict[str, bool] = {"precision": False, "efficiency": False}
                try:
                    pseudo_config = PseudoConfig.with_defaults()
                    store_dir = Path(pseudo_config.store_dir) if pseudo_config.store_dir else None

                    if store_dir:
                        for flavor in ["precision", "efficiency"]:
                            lib_base = get_sssp_library_path(store_dir, "1.3.0", flavor)
                            lib_path = lib_base / "library"
                            cutoffs_path = lib_base / "cutoffs.json"

                            if lib_path.exists() and any(lib_path.glob("*.upf")) or any(lib_path.glob("*.UPF")):
                                sssp_installed[flavor] = True

                            if cutoffs_path.exists():
                                try:
                                    cutoffs_data = json.loads(cutoffs_path.read_text())
                                    for species in species_list:
                                        if species not in sssp_defaults:
                                            sssp_defaults[species] = {"precision": "", "efficiency": ""}
                                        element_data = cutoffs_data.get(species, {})
                                        filename = element_data.get("filename", "")
                                        if filename and (lib_path / filename).exists():
                                            sssp_defaults[species][flavor] = filename
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
                from quantumvitas.core.resolution import validate_ulid, resolve_step, make_structure_selector_resolver
                from quantumvitas.calculation.structure_steps import StructureStepSpec
                from quantumvitas.core.project_utils import load_project_config
                from quantumvitas.core.yamldoc import StepDoc
                from quantumvitas.workflow.step_factory import save_step_doc

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
                from quantumvitas.core.resolution import resolve_step, make_structure_selector_resolver
                from quantumvitas.calculation.structure_steps import StructureStepSpec
                from quantumvitas.calculation.step_defaults import get_default_step_params
                from quantumvitas.core.project_utils import load_project_config
                from quantumvitas.core.yamldoc import StepDoc
                from quantumvitas.workflow.step_factory import save_step_doc

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
                from quantumvitas.core.resolution import resolve_calculation
                from quantumvitas.core.models import load_calculation, save_calculation
                from quantumvitas.core.project_utils import load_project_config
                from quantumvitas.api.errors import ValidationError

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
                from quantumvitas.core.resolution import require_calculation, require_step, require_structure
                from quantumvitas.core.models import load_calculation
                from quantumvitas.core.project_utils import load_project_config
                from quantumvitas.core.yamldoc import StepDoc
                from quantumvitas.workflow.step_factory import save_step_doc

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
                from quantumvitas.core.resolution import make_structure_selector_resolver
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
                from quantumvitas.core.resolution import validate_ulid, resolve_calculation
                from quantumvitas.calculation.importers import build_step_spec_from_qe_input
                from quantumvitas.core.models import load_calculation, save_calculation, CalculationStepEntry
                from quantumvitas.core.project_utils import load_project_config
                from quantumvitas.api.errors import NotFoundError

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
                from quantumvitas.core.resolution import validate_ulid, resolve_calculation, resolve_structure, make_structure_selector_resolver
                from quantumvitas.core.models import load_calculation
                from quantumvitas.core.project_utils import load_project_config
                from quantumvitas.io import read_structure
                from quantumvitas.core.pseudo_config import load_pseudo_config, get_sssp_library_path
                from quantumvitas.core.pseudo import get_system_pseudo_dir
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

                # Check SSSP libraries
                sssp_defaults: dict[str, dict[str, str]] = {}
                sssp_installed = {"precision": False, "efficiency": False}
                try:
                    pseudo_config = load_pseudo_config()
                    store_dir = Path(pseudo_config.store_dir) if pseudo_config.store_dir else None

                    if store_dir:
                        for flavor in ["precision", "efficiency"]:
                            lib_path = get_sssp_library_path(store_dir, "1.3.0", flavor) / "library"
                            if lib_path.exists() and list(lib_path.glob("*.upf")):
                                sssp_installed[flavor] = True
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
                from quantumvitas.core.resolution import resolve_calculation, make_structure_selector_resolver
                from quantumvitas.core.models import load_calculation, save_calculation
                from quantumvitas.core.project_utils import load_project_config

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
                from quantumvitas.calculation.species_config import configure_species_map as _configure_species_map

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
                    from quantumvitas.api.errors import ValidationError
                    raise ValidationError(
                        str(e),
                        code="VALIDATION_FAILED",
                        context={"calculation": calculation}
                    )
                raise map_kernel_exception(e)

    @property
    def calculation(self) -> Calculation:
        """Access calculation capabilities."""
        return QVService.Calculation(self)
    
    # Run domain (PR7)
    class Run:
        """Run/execution capabilities."""
        
        def __init__(self, service: QVService):
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
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation
                from quantumvitas.calculation.runner import CalculationRunner
                from quantumvitas.engine.registry import create_default_registry
                from quantumvitas.core.locking import calc_run_lock, CalculationLockError
                from quantumvitas.core.resolution import require_calculation, build_resource_index
                from quantumvitas.core.project_utils import load_project_config
                from quantumvitas.api import get_step_type_gen

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

                        if not calculation.structure_ulid:
                            from quantumvitas.api.errors import ValidationError
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
                    from quantumvitas.api.errors import EngineError
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
                from quantumvitas.project.model import Project
                from quantumvitas.calculation.calculation import Calculation
                from quantumvitas.calculation.runner import CalculationRunner
                from quantumvitas.calculation.types import StepStatus
                from quantumvitas.engine.registry import create_default_registry
                from quantumvitas.core.resolution import require_calculation, require_step, build_resource_index
                from quantumvitas.core.project_utils import load_project_config
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
                    from quantumvitas.api.errors import ValidationError
                    raise ValidationError(
                        f"Calculation '{calc_selector}' has no structure. Please set a structure first."
                    )

                # Get step type (SPEC from YAML, convert to GEN for API response)
                step_type_gen = "unknown"
                try:
                    from quantumvitas.api import get_step_type_gen
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
                from quantumvitas.api.errors import NotFoundError, EngineError
                from quantumvitas.provenance import get_run_details

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
                        from quantumvitas.api.types.error import ErrorDTO
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
                from quantumvitas.core.engines.qe_resolver import resolve_qe_bin_dir
                from quantumvitas.core.settings import load_settings
                from quantumvitas.core.resolution import resolve_calculation, resolve_structure
                from quantumvitas.core.models import load_calculation
                from quantumvitas.core.project_utils import load_project_config
                from quantumvitas.core.resolution import make_structure_selector_resolver
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
            from quantumvitas.api.types.error import ErrorDTO
            
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
        return QVService.Run(self)
    
    # Project domain (PR8)
    class Project:
        """Project capabilities."""
        
        def __init__(self, service: QVService):
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
                from quantumvitas.core.project_utils import load_project_config
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
                from quantumvitas.core.project_utils import load_project_config, save_project_config
                
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
                from quantumvitas.core.resolution import build_resource_index
                return build_resource_index(self._service.project_root)
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def list_calculations(self) -> list[CalculationDTO]:
            """
            List all calculations in project.
            
            Returns:
                List of CalculationDTO
                
            Raises:
                APIError: If project invalid
            """
            try:
                # Delegate to calculation.list()
                return self._service.calculation.list()
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
                from quantumvitas.core.project_utils import collect_slugs as _collect_slugs
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
            
            from quantumvitas.core.project_utils import apply_structure_rename as _apply_structure_rename
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
            
            from quantumvitas.core.project_utils import apply_calculation_rename as _apply_calculation_rename
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
                from quantumvitas.core.project_utils import load_project_config
                from quantumvitas.core.resolution import list_structures, list_calculations

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
                from quantumvitas.core.project_utils import load_project_config, save_project_config
                from quantumvitas.core.resources import generate_resource_id, slugify
                from quantumvitas.core.resolution import resolve_structure, build_resource_index
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
                from quantumvitas.core.resolution import ResolvedResource
                from quantumvitas.core.resources import ResourceMeta

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
            from quantumvitas.core.pseudo_runtime import (
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
            from quantumvitas.core.pseudo_options import materialize_pseudo_file as _materialize_pseudo_file
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
            from quantumvitas.core.pseudo_options import get_pseudo_options_for_elements as _get_pseudo_options_for_elements
            from quantumvitas.core.pseudo_config import PseudoConfig

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
        return QVService.Project(self)
    
    # Engine domain (PR9)
    class Engine:
        """Engine discovery capabilities."""
        
        def __init__(self, service: QVService):
            self._service = service
        
        def list(self) -> list[dict]:
            """
            List all available engines.
            
            Returns:
                List of engine info dicts
            """
            try:
                from quantumvitas.engine.registry import create_default_registry
                
                registry = create_default_registry()
                engines = []
                
                for engine_name in registry.list_engines():
                    engine = registry.get(engine_name)
                    engines.append({
                        "name": engine_name,
                        "supported_presets": getattr(engine, "supported_presets", []),
                    })
                
                return engines
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def get_info(self, engine_name: str) -> dict:
            """
            Get information about a specific engine.
            
            Args:
                engine_name: Engine name (e.g., "qe", "pyscf")
                
            Returns:
                Engine info dict
                
            Raises:
                APIError: If engine not found
            """
            try:
                from quantumvitas.engine.registry import create_default_registry
                from quantumvitas.api.errors import NotFoundError
                
                registry = create_default_registry()
                
                if not registry.has(engine_name):
                    raise NotFoundError(
                        f"Engine not found: {engine_name}",
                        context={"engine_name": engine_name}
                    )
                
                engine = registry.get(engine_name)
                
                info = {
                    "name": engine_name,
                    "supported_presets": getattr(engine, "supported_presets", []),
                }
                
                # Add version if available
                if hasattr(engine, "version") and engine.version:
                    info["version"] = engine.version
                
                # Add executable path if available
                if hasattr(engine, "executable"):
                    try:
                        info["executable"] = str(engine.executable)
                    except Exception:
                        pass
                
                return info
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def list_step_types(self, engine_name: str | None = None) -> list[dict]:
            """
            List step types, optionally filtered by engine.
            
            Args:
                engine_name: Optional engine name filter
                
            Returns:
                List of step type info dicts
            """
            try:
                from quantumvitas.workflow.generalized_steps import get_supported_generalized_steps
                from quantumvitas.workflow.registry import get_registry
                
                if engine_name:
                    # Get step types for specific engine
                    step_types = get_supported_generalized_steps(engine_name)
                    return [{"name": st, "engine": engine_name} for st in step_types]
                else:
                    # Get all step types from registry
                    registry = get_registry()
                    step_types = []
                    for step_name in registry.list_step_types():
                        # Get engines that support this step
                        from quantumvitas.workflow.generalized_steps import get_engine_families_for_step
                        engines = get_engine_families_for_step(step_name)
                        step_types.append({
                            "name": step_name,
                            "engines": engines,
                        })
                    return step_types
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
        
        def validate_installation(self, engine_name: str) -> dict:
            """
            Validate engine installation.
            
            Args:
                engine_name: Engine name (e.g., "qe", "vasp", "orca")
                
            Returns:
                Validation result dict with schema:
                - engine_name: str
                - ok: bool
                - details: dict (always present; may be empty)
                - version: str | None (optional)
                - binary: str | None (optional)
                - message: str | None (optional)
                - warnings: list[str] | None (optional)
                
            Raises:
                ValidationError: If engine_name is unknown (invalid input)
                APIError: For other errors
            """
            try:
                from quantumvitas.api.errors import ValidationError
                from quantumvitas.core.driver_registry import DriverRegistry
                from quantumvitas.core.driver_exceptions import UnknownEngineError
                
                # Get driver from registry (canonical source)
                try:
                    driver = DriverRegistry.get_driver(engine_name)
                except UnknownEngineError:
                    # Unknown engine is a validation error (invalid input)
                    raise ValidationError(
                        f"Unknown engine: {engine_name}",
                        code="VALIDATION_FAILED",
                        context={"engine_name": engine_name}
                    )
                
                # Initialize result with required fields
                result = {
                    "engine_name": engine_name,
                    "ok": False,
                    "details": {},
                }
                
                # Engine-specific validation hooks
                warnings = []
                
                if engine_name == "qe":
                    # QE validation: check if binary directory can be resolved
                    try:
                        from quantumvitas.drivers.qe.engine.qe_resolver import resolve_qe_bin_dir
                        from pathlib import Path
                        
                        bin_dir = resolve_qe_bin_dir()
                        result["ok"] = True
                        result["binary"] = str(bin_dir)
                        result["details"]["bin_dir"] = str(bin_dir)
                        result["details"]["mode"] = "external"  # or "internal" - simplified
                        
                        # Try to get version if available
                        try:
                            from quantumvitas.drivers.qe.engine.qe_diagnostics import diagnose_qe_resolution
                            report = diagnose_qe_resolution()
                            if report.version:
                                result["version"] = report.version
                        except Exception:
                            pass
                            
                    except RuntimeError as e:
                        # QE not found or invalid
                        result["ok"] = False
                        result["message"] = str(e)
                        result["details"]["error"] = str(e)
                    except Exception as e:
                        # Other errors during validation
                        result["ok"] = False
                        result["message"] = f"Validation error: {e}"
                        result["details"]["error"] = str(e)
                        warnings.append(f"Unexpected error during QE validation: {e}")
                
                elif engine_name == "orca":
                    # ORCA validation: check if binary can be found
                    try:
                        from quantumvitas.core.engines.orca_resolver import resolve_orca_bin, get_orca_version
                        from pathlib import Path
                        
                        orca_bin = resolve_orca_bin()
                        result["ok"] = True
                        result["binary"] = str(orca_bin)
                        result["details"]["binary"] = str(orca_bin)
                        
                        # Try to get version
                        version = get_orca_version(orca_bin)
                        if version:
                            result["version"] = version
                    except RuntimeError as e:
                        # ORCA not found
                        result["ok"] = False
                        result["message"] = str(e)
                        result["details"]["error"] = str(e)
                    except Exception as e:
                        result["ok"] = False
                        result["message"] = f"Validation error: {e}"
                        result["details"]["error"] = str(e)
                
                elif engine_name in ["pyscf", "cp2k", "lammps", "vasp"]:
                    # For engines without specific validation hooks, return ok=True
                    # with note that validation is not implemented
                    result["ok"] = True
                    result["details"]["note"] = "Engine is registered; validation hook not implemented"
                    result["message"] = "Engine registered successfully"
                
                else:
                    # Unknown engine (shouldn't happen if DriverRegistry is correct)
                    # But if it does, return ok=True with note
                    result["ok"] = True
                    result["details"]["note"] = "Engine is registered; no validation hook available"
                    result["message"] = "Engine registered successfully"
                
                # Add warnings if any
                if warnings:
                    result["warnings"] = warnings
                
                return result
                
            except Exception as e:
                if isinstance(e, APIError):
                    raise
                raise map_kernel_exception(e)
    
    @property
    def engine(self) -> Engine:
        """Access engine capabilities."""
        return QVService.Engine(self)

    # History domain (minimal surface for daemon)
    class History:
        """History/timeline capabilities using provenance system."""

        def __init__(self, service: QVService):
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
                from quantumvitas.provenance import (
                    query_runs,
                    get_run_details,
                    get_latest_run_ulid,
                )

                # Query runs from provenance database
                runs = query_runs(
                    self._service.project_root,
                    calc_ulid=calc_ulid,
                    limit=limit,
                )

                timeline = []

                for run in runs:
                    # Create run_started entry
                    started_entry = {
                        "ulid": run["run_ulid"],
                        "timestamp": run["started_at"],
                        "event_type": "run_started",
                        "calc_ulid": run["calc_ulid"],
                        "run_ulid": run["run_ulid"],
                        "step_ulid": None,
                    }

                    # Get step info from run details
                    run_details = get_run_details(self._service.project_root, run["run_ulid"])
                    if run_details:
                        started_entry["step_ulids"] = run_details.get("step_ulids", [])

                    timeline.append(started_entry)

                    # Create run_finished entry if run is complete
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
                        }
                        timeline.append(finished_entry)

                # Sort by timestamp descending
                timeline.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

                latest_run_ulid = get_latest_run_ulid(self._service.project_root)

                return {
                    "timeline": timeline[:limit],
                    "latest_run_ulid": latest_run_ulid,
                    "latest_run_id": latest_run_ulid,  # Backwards compat alias
                    "total": len(timeline[:limit]),
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
                from quantumvitas.provenance import get_run_details

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

        def list_runs(
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
                from quantumvitas.provenance import query_runs, get_run_details

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

                from quantumvitas.provenance import (
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
                from quantumvitas.provenance import can_pin_to_run
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
                from quantumvitas.provenance import get_pin_data as _get_pin_data
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
                from quantumvitas.provenance import PROVENANCE_DIR_NAME

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
        return QVService.History(self)

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
        Initialize a new QuantumVITAS project.
        
        This is a backwards-compatibility wrapper for the legacy QVService.init_project().
        It creates a new project directory with project.qv.yml and standard subdirectories.
        
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
            from quantumvitas.core.context import detect_enclosing_project
            from quantumvitas.core.project_utils import save_project_config
            from quantumvitas.core.resources import generate_resource_id, slugify
            
            target_dir = Path(target_dir).resolve()
            
            # Check if target_dir is inside an existing project
            enclosing_project = detect_enclosing_project(target_dir)
            if enclosing_project:
                raise ValueError(
                    f"Cannot create a new project inside an existing QuantumVITAS project. "
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
        
        This is a backwards-compatibility wrapper for the legacy QVService.get_settings().
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
            from quantumvitas.core.settings import load_settings
            
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
        from quantumvitas.workflow.templates import get_workflow_service as _get_workflow_service
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
        svc = QVService(project_root)
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
    def get_default_step_params(step_type_gen: str) -> dict[str, Any]:
        """
        Get default parameters for a step type.
        
        This is a backwards-compatibility wrapper for the legacy QVService.get_default_step_params().
        
        Args:
            step_type_gen: Step type (e.g., "scf", "nscf" - gen type, or "qe_scf", "qe_nscf" - spec type, accepts both)
            
        Returns:
            Dict with "parameters", "cards", and "species_overrides" keys.
            Returns empty dicts if step_type_gen is not recognized.
        """
        from quantumvitas.calculation.step_defaults import get_default_step_params as _get_default_step_params
        return _get_default_step_params(step_type_gen)

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
        from quantumvitas.workflow.registry import get_registry
        registry = get_registry()
        spec_obj = registry.get_for_engine(step_type_gen, engine_family)
        return spec_obj.step_type_spec if spec_obj else step_type_gen

    @staticmethod
    def generate_kpath(
        structure: Any,  # pymatgen Structure
        points_per_segment: int = 20,
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
        from quantumvitas.analysis.kpath import generate_kpath as _generate_kpath
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
        Creates a ready-to-run project from resources/demo_projects/.

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
        from quantumvitas.core.resources import get_resources_dir
        from quantumvitas.core.project_utils import find_project_root
        from quantumvitas.project.snapshot import (
            ProjectSnapshot,
            materialize_project_from_snapshot,
        )
        import yaml

        target_dir = Path(target_dir).resolve()
        demo_name = demo_id or "si_bands_demo"

        # Check not inside existing project
        enclosing = find_project_root(target_dir, max_levels=20)
        if enclosing is not None:
            raise ValueError(
                f"Target directory is inside an existing QuantumVITAS project at: {enclosing}. "
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

        return {
            "project_root": str(project_root),
            "demo_id": demo_name,
        }

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
        from quantumvitas.core.resources import get_resources_dir
        import yaml

        resources_dir = get_resources_dir()
        demo_dir = resources_dir / "demo_projects"

        if not demo_dir.exists():
            return []

        demos = []
        for snapshot_path in sorted(demo_dir.glob("*.yml")):
            try:
                with open(snapshot_path, "r") as f:
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
                })
            except Exception:
                # Skip invalid snapshots
                continue

        return demos

    # -------------------------------------------------------------------------
    # Pseudo Management (Global Operations)
    # -------------------------------------------------------------------------

    @staticmethod
    def init_pseudo_dirs() -> dict[str, Any]:
        """
        Initialize pseudopotential directories.

        Returns:
            Dict with: store_dir_created (bool), seed_dir_created (bool),
            messages (list), errors (list)
        """
        from quantumvitas.core.pseudo_config import load_pseudo_config, init_pseudo_dirs as _init_pseudo_dirs

        config = load_pseudo_config()
        return _init_pseudo_dirs(config)

    @staticmethod
    def list_pseudo_libraries() -> list[dict[str, Any]]:
        """
        List available pseudopotential libraries.

        Returns:
            List of library dicts
        """
        from quantumvitas.core.library_manager import get_supported_libraries

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
        from quantumvitas.core.library_manager import get_library_status as _get_library_status

        status = _get_library_status(library_id)
        return status.to_dict() if hasattr(status, 'to_dict') else status

    @staticmethod
    def install_pseudo_library(
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
        from quantumvitas.core.library_manager import install_library as _install_library
        from quantumvitas.core.pseudo_config import load_pseudo_config, save_pseudo_config

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
    def remove_pseudo_library(library_id: str, variants: list[str] | None = None) -> dict[str, Any]:
        """
        Remove a pseudopotential library.

        Args:
            library_id: Library identifier
            variants: Optional list of variants to remove (removes all if None)

        Returns:
            Dict with removal result
        """
        from quantumvitas.core.library_manager import remove_library as _remove_library

        result = _remove_library(library_id=library_id, variants=variants)
        return result

    @staticmethod
    def repair_pseudo_library(library_id: str, variants: list[str] | None = None) -> dict[str, Any]:
        """
        Repair a pseudopotential library (verify checksums, re-extract if needed).

        Args:
            library_id: Library identifier
            variants: List of variant names to repair (optional, repairs all if not specified)

        Returns:
            Dict with repair result
        """
        from quantumvitas.core.library_manager import repair_library as _repair_library

        result = _repair_library(library_id=library_id, variants=variants or [])
        return result

    @staticmethod
    def compute_store_size() -> dict[str, Any]:
        """
        Compute pseudopotential store size.

        Returns:
            Dict with total_bytes and breakdown by library
        """
        from quantumvitas.core.library_manager import compute_store_size as _compute_store_size

        return _compute_store_size()

    @staticmethod
    def is_pseudo_archive_installed(asset_name: str, expected_sha256: str) -> bool:
        """
        Check if a pseudopotential archive is installed.

        Args:
            asset_name: Archive filename
            expected_sha256: Expected SHA256 hash

        Returns:
            True if archive is installed with matching hash
        """
        from quantumvitas.core.pseudo_installs import is_archive_installed

        return is_archive_installed(asset_name=asset_name, expected_sha256=expected_sha256)

    @staticmethod
    def install_pseudo_archive(
        asset_url: str,
        asset_name: str,
        expected_sha256: str,
        expected_size: int | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Install a pseudopotential archive.

        Args:
            asset_url: URL to download archive from
            asset_name: Archive filename
            expected_sha256: Expected SHA256 hash
            expected_size: Optional expected file size
            config: Optional pseudo config dict

        Returns:
            Dict with success, messages, errors
        """
        from quantumvitas.core.pseudo_installs import install_archive as _install_archive
        from quantumvitas.core.pseudo_config import PseudoConfig, load_pseudo_config

        if config is None:
            pseudo_config = load_pseudo_config()
        else:
            pseudo_config = PseudoConfig.from_dict(config)

        result = _install_archive(
            asset_url=asset_url,
            asset_name=asset_name,
            expected_sha256=expected_sha256,
            expected_size=expected_size,
            config=pseudo_config,
        )
        return result.to_dict() if hasattr(result, 'to_dict') else result

    @staticmethod
    def install_sssp_from_seed(
        seed_dir: Path | str,
        store_dir: Path | str,
        version: str = "1.3.0",
        flavor: str = "efficiency",
    ) -> dict[str, Any]:
        """
        Install SSSP library from seed to store.

        Args:
            seed_dir: Path to seed directory
            store_dir: Path to store directory
            version: SSSP version (default: "1.3.0")
            flavor: "efficiency" or "precision" (default: "efficiency")

        Returns:
            Dict with success, messages, errors, files_installed
        """
        from quantumvitas.core.pseudo_config import install_sssp_from_seed as _install_sssp_from_seed

        return _install_sssp_from_seed(Path(seed_dir), Path(store_dir), version, flavor)

    @staticmethod
    def install_all_sssp_from_seed(
        seed_dir: Path | str,
        store_dir: Path | str,
    ) -> dict[str, Any]:
        """
        Install all available SSSP libraries from seed to store.

        Args:
            seed_dir: Path to seed directory
            store_dir: Path to store directory

        Returns:
            Dict with success, installed, skipped, failed, messages
        """
        from quantumvitas.core.pseudo_config import install_all_sssp_from_seed as _install_all_sssp_from_seed

        return _install_all_sssp_from_seed(Path(seed_dir), Path(store_dir))

    @staticmethod
    def download_sssp_library(
        store_dir: Path | str,
        flavor: str,
        version: str = "1.3.0",
        force: bool = False,
        allow_download: bool = True,
        seed_dir: Path | str | None = None,
    ) -> dict[str, Any]:
        """
        Download SSSP library from GitHub release and install into store.

        Args:
            store_dir: Path to pseudo store directory
            flavor: "efficiency" or "precision"
            version: SSSP version (default: "1.3.0")
            force: If True, download even if allow_download is False
            allow_download: Global setting
            seed_dir: Optional seed directory path

        Returns:
            Dict with success, messages, errors, files_installed
        """
        from quantumvitas.core.pseudo_config import download_sssp_library as _download_sssp_library

        return _download_sssp_library(
            Path(store_dir),
            flavor,
            version,
            force,
            allow_download,
            Path(seed_dir) if seed_dir else None,
        )

    @staticmethod
    def download_all_sssp(
        store_dir: Path | str,
        force: bool = False,
        allow_download: bool = True,
        seed_dir: Path | str | None = None,
    ) -> dict[str, Any]:
        """
        Download all supported SSSP libraries from GitHub release.

        Args:
            store_dir: Path to pseudo store directory
            force: If True, download even if allow_download is False
            allow_download: Global setting
            seed_dir: Optional seed directory path

        Returns:
            Dict with success, installed, skipped, failed, messages
        """
        from quantumvitas.core.pseudo_config import download_all_sssp as _download_all_sssp

        return _download_all_sssp(
            Path(store_dir),
            force,
            allow_download,
            Path(seed_dir) if seed_dir else None,
        )

    @staticmethod
    def import_seed_archives(
        seed_dir: Path | str,
        archive_paths: list[Path | str],
    ) -> dict[str, Any]:
        """
        Import seed archives into seed directory.

        Args:
            seed_dir: Path to seed directory
            archive_paths: List of paths to archive files to import

        Returns:
            Dict with success, imported, failed, messages, errors
        """
        from quantumvitas.core.pseudo_config import import_seed_archives as _import_seed_archives

        return _import_seed_archives(Path(seed_dir), [Path(p) for p in archive_paths])
