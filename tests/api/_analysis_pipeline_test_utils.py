"""Shared setup helpers for analysis pipeline API tests."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml

from quantumvitas.api.service import QVService
from quantumvitas.calculation.types import StepStatus
from quantumvitas.provenance import record_run_complete, record_run_start
from quantumvitas.provenance.recording import generate_ulid


@dataclass
class _StepSummary:
    step_ulid: str
    step_type_spec: str
    status: StepStatus
    working_dir: Path


@dataclass
class _RunResult:
    run_ulid: str
    status: StepStatus
    steps: list[_StepSummary]


@dataclass
class _CalculationStub:
    ulid: str
    engine_family: str
    dir: Path


def setup_qe_bands_run(tmp_path: Path) -> dict[str, object]:
    """Create a minimal project with one QE bands step and persisted analysis snapshots."""
    project_root = tmp_path / "project"
    QVService.init_project(project_root, name="analysis-test")
    svc = QVService(project_root)

    calc_dto = svc.calculation.create(engine="qe", name="qe_bands_calc")
    calc_ulid = calc_dto.calc_ulid
    calc_dir = project_root / (calc_dto.path or "calculations/qe_bands_calc")
    raw_dir = calc_dir / "raw"
    steps_dir = calc_dir / "steps"
    steps_dir.mkdir(parents=True, exist_ok=True)

    # Seed raw evidence from committed fixture corpus (never .tmp).
    fixture_raw = Path(__file__).resolve().parents[1] / "data" / "analysis_bands"
    shutil.copytree(fixture_raw, raw_dir, dirs_exist_ok=True)

    step_ulid = generate_ulid()
    step_slug = "qe_bands_step"
    step_file = steps_dir / f"{step_slug}.step.yaml"
    step_file.write_text(
        yaml.safe_dump(
            {
                "meta": {
                    "ulid": step_ulid,
                    "name": step_slug,
                    "slug": step_slug,
                    "path": f"{calc_dto.path}/steps/{step_file.name}",
                    "kind": "step",
                },
                "step_type_spec": "qe_bandspw",
                "parameters": {},
            }
        ),
        encoding="utf-8",
    )

    calc_yaml = calc_dir / "calculation.yaml"
    calc_doc = yaml.safe_load(calc_yaml.read_text(encoding="utf-8")) or {}
    calc_doc["engine_family"] = "qe"
    calc_doc["working_dir"] = "raw"
    calc_doc["steps"] = [{"step_ulid": step_ulid, "step_type_spec": "qe_bandspw"}]
    calc_yaml.write_text(yaml.safe_dump(calc_doc), encoding="utf-8")

    run_ulid = generate_ulid()
    record_run_start(
        project_root=project_root,
        run_ulid=run_ulid,
        calc_ulid=calc_ulid,
        engine="qe",
    )

    run_result = _RunResult(
        run_ulid=run_ulid,
        status=StepStatus.SUCCESS,
        steps=[
            _StepSummary(
                step_ulid=step_ulid,
                step_type_spec="qe_bandspw",
                status=StepStatus.SUCCESS,
                working_dir=raw_dir,
            )
        ],
    )
    calc_stub = _CalculationStub(
        ulid=calc_ulid,
        engine_family="qe",
        dir=calc_dir,
    )

    svc._finalize_run_analysis_pipeline(calc_stub, run_result)
    record_run_complete(project_root=project_root, run_ulid=run_ulid, status="success")

    return {
        "project_root": project_root,
        "service": svc,
        "run_ulid": run_ulid,
        "step_ulid": step_ulid,
        "calc_ulid": calc_ulid,
        "calc_dir": calc_dir,
    }
