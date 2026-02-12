"""Yambo step handler.

Executes yambo calculations by:
1. setup: running p2y + yambo init on QE wavefunctions
2. gw/bse/optics: writing input, symlinking SAVE, running yambo
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from quantumvitas.execution.executor import JobResult
from quantumvitas.execution.job_graph import Job

if TYPE_CHECKING:
    from quantumvitas.calculation.calculation import Calculation
    from quantumvitas.calculation.step import Step
    from quantumvitas.engine.registry import EngineRegistry

logger = logging.getLogger(__name__)


def _find_step_by_ulid(
    calculation: "Calculation", step_ulid: str
) -> Optional["Step"]:
    """Find a step in calculation by its ULID."""
    for step in calculation.steps:
        if step.meta.ulid == step_ulid:
            return step
    return None


def _resolve_yambo_bin(binary_name: str = "yambo") -> Optional[str]:
    """Resolve yambo binary using centralized discovery."""
    from quantumvitas.core.engines.discovery import discover_engine

    result = discover_engine("yambo")
    if result.available and result.executable_path:
        bin_dir = result.executable_path.parent
        candidate = bin_dir / binary_name
        if candidate.is_file():
            return str(candidate)
    # Fallback to PATH
    found = shutil.which(binary_name)
    return found


def _handle_setup(
    job: Job,
    calc_raw_dir: Path,
    step_ulid: str,
    timeout: int,
) -> JobResult:
    """Handle the setup step: p2y conversion + yambo initialization."""
    from .artifact_resolver import find_qe_save_dir

    # Find QE save directory
    qe_save_dir = find_qe_save_dir(calc_raw_dir)
    if qe_save_dir is None:
        return JobResult(
            job_id=job.id, success=False,
            error="No QE prefix.save/ directory found in calc/raw/. "
                  "Run QE SCF+NSCF before yambo setup.",
        )

    # Resolve p2y binary
    p2y_bin = _resolve_yambo_bin("p2y")
    if p2y_bin is None:
        return JobResult(
            job_id=job.id, success=False,
            error="p2y binary not found. Ensure yambo is installed.",
        )

    # Resolve yambo binary
    yambo_bin = _resolve_yambo_bin("yambo")
    if yambo_bin is None:
        return JobResult(
            job_id=job.id, success=False,
            error="yambo binary not found. Ensure yambo is installed.",
        )

    # Step 1: Run p2y inside QE prefix.save/
    logger.info("Running p2y in %s", qe_save_dir)
    try:
        p2y_result = subprocess.run(
            [p2y_bin],
            cwd=str(qe_save_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return JobResult(
            job_id=job.id, success=False, error="p2y timed out",
        )
    except Exception as e:
        return JobResult(
            job_id=job.id, success=False, error=f"p2y failed: {e}",
        )

    if p2y_result.returncode != 0:
        return JobResult(
            job_id=job.id, success=False,
            error=f"p2y failed (exit {p2y_result.returncode}): "
                  f"{p2y_result.stderr[:500]}",
        )

    # Step 2: Copy SAVE from inside QE save dir to calc/raw/SAVE/
    p2y_save = qe_save_dir / "SAVE"
    if not p2y_save.is_dir():
        return JobResult(
            job_id=job.id, success=False,
            error=f"p2y did not create SAVE/ in {qe_save_dir}",
        )

    target_save = calc_raw_dir / "SAVE"
    if target_save.exists():
        shutil.rmtree(target_save)
    shutil.copytree(p2y_save, target_save)
    logger.info("Copied SAVE to %s", target_save)

    # Step 3: Run yambo initialization (bare yambo to create ndb.gops, ndb.kindx)
    logger.info("Running yambo init in %s", calc_raw_dir)
    try:
        init_result = subprocess.run(
            [yambo_bin],
            cwd=str(calc_raw_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return JobResult(
            job_id=job.id, success=False, error="yambo init timed out",
        )
    except Exception as e:
        return JobResult(
            job_id=job.id, success=False, error=f"yambo init failed: {e}",
        )

    if init_result.returncode != 0:
        return JobResult(
            job_id=job.id, success=False,
            error=f"yambo init failed (exit {init_result.returncode}): "
                  f"{init_result.stderr[:500]}",
        )

    # Verify SAVE directory has expected files
    if not (target_save / "ns.db1").exists():
        return JobResult(
            job_id=job.id, success=False,
            error="SAVE/ns.db1 not found after initialization",
        )

    return JobResult(
        job_id=job.id,
        success=True,
        step_results={step_ulid: {
            "success": True,
            "save_dir": str(target_save),
            "p2y_output": p2y_result.stdout[:500],
        }},
    )


def _handle_calculation(
    job: Job,
    calc_raw_dir: Path,
    step: "Step",
    step_ulid: str,
    gen_type: str,
    timeout: int,
) -> JobResult:
    """Handle a yambo calculation step (gw, bse, optics)."""
    from .artifact_resolver import find_yambo_save_dir, find_gw_qp_db
    from .writer import (
        GWParams, BSEParams, IPOpticsParams,
        write_gw_input, write_bse_input, write_ip_optics_input,
    )

    # Resolve yambo binary
    yambo_bin = _resolve_yambo_bin("yambo")
    if yambo_bin is None:
        return JobResult(
            job_id=job.id, success=False,
            error="yambo binary not found. Ensure yambo is installed.",
        )

    working_dir = job.working_dir
    working_dir.mkdir(parents=True, exist_ok=True)

    # Find and symlink SAVE directory
    save_dir = find_yambo_save_dir(calc_raw_dir)
    if save_dir is None:
        return JobResult(
            job_id=job.id, success=False,
            error="No SAVE/ directory found. Run yambo_setup first.",
        )

    save_link = working_dir / "SAVE"
    if not save_link.exists():
        os.symlink(save_dir, save_link)

    # Get step parameters
    params: dict = {}
    if hasattr(step, "params") and step.params:
        params = dict(step.params)

    # Generate input file
    jobname = f"{gen_type}_run"
    input_file = f"{gen_type}.in"
    output_dir = f"{gen_type}_output"

    # If the materializer already created the input file with canonical yambo
    # params (via inputformat writer), use it directly instead of regenerating
    # from semantic keys.  Canonical-form files contain yambo keywords like
    # "Chimod", "BSEBands", "BndsRnXp" which the writer.py dataclasses do
    # not understand.
    materialized_input = working_dir / input_file
    if not materialized_input.exists() or materialized_input.stat().st_size == 0:
        if gen_type == "gw":
            gw_params = GWParams(
                polarization_bands=tuple(params.get("polarization_bands", (1, 50))),
                self_energy_bands=tuple(params.get("self_energy_bands", (1, 50))),
                ngs_blk_xp=params.get("ngs_blk_xp", 1),
                kpt_range=tuple(params.get("kpt_range", (1, 1))),
                band_range=tuple(params.get("band_range", (1, 8))),
                dyson_solver=params.get("dyson_solver", "n"),
                gw_terminator=params.get("gw_terminator", "none"),
            )
            write_gw_input(working_dir / input_file, gw_params)
        elif gen_type == "bse":
            bse_params = BSEParams(
                screening_bands=tuple(params.get("screening_bands", (1, 20))),
                bse_bands=tuple(params.get("bse_bands", (1, 8))),
                energy_steps=params.get("energy_steps", 200),
                bsk_mod=params.get("bsk_mod", "SEX"),
                bss_mod=params.get("bss_mod", "h"),
            )
            # Optionally use GW QP corrections
            qp_db = find_gw_qp_db(calc_raw_dir)
            if qp_db is not None:
                bse_params.qp_db = f"E < {qp_db}"
            write_bse_input(working_dir / input_file, bse_params)
        elif gen_type == "optics":
            ip_params = IPOpticsParams(
                bands=tuple(params.get("bands", (1, 50))),
                energy_steps=params.get("energy_steps", 100),
                chi_mod=params.get("chi_mod", "IP"),
            )
            write_ip_optics_input(working_dir / input_file, ip_params)
        else:
            return JobResult(
                job_id=job.id, success=False,
                error=f"Unknown yambo gen type: {gen_type}",
            )
    else:
        logger.info(
            "Using materialized input file %s (skipping handler regeneration)",
            materialized_input,
        )

    # Execute yambo
    cmd = [yambo_bin, "-F", input_file, "-J", jobname, "-C", output_dir]
    logger.info("Running: %s in %s", " ".join(cmd), working_dir)
    try:
        result = subprocess.run(
            cmd,
            cwd=str(working_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return JobResult(
            job_id=job.id, success=False, error="yambo calculation timed out",
        )
    except Exception as e:
        return JobResult(
            job_id=job.id, success=False, error=f"yambo execution failed: {e}",
        )

    # Save stdout/stderr
    log_file = working_dir / f"{gen_type}.log"
    log_file.write_text(result.stdout + result.stderr)

    if result.returncode != 0:
        stderr_snippet = result.stderr[:1000] if result.stderr else ""
        return JobResult(
            job_id=job.id, success=False,
            error=f"yambo exited with code {result.returncode}: {stderr_snippet}",
        )

    # Parse results
    step_result_data: Dict[str, Any] = {"success": True}
    out_dir = working_dir / output_dir
    if out_dir.is_dir():
        step_result_data["output_dir"] = str(out_dir)

        # Parse QP results (GW)
        if gen_type == "gw":
            from .parser import parse_qp_file
            qp_files = list(out_dir.glob("o-*.qp"))
            if qp_files:
                qp_result = parse_qp_file(qp_files[0])
                step_result_data["n_corrections"] = len(qp_result.corrections)
                if qp_result.qp_gap is not None:
                    step_result_data["qp_gap_eV"] = qp_result.qp_gap
                if qp_result.dft_gap is not None:
                    step_result_data["dft_gap_eV"] = qp_result.dft_gap

        # Parse spectrum results (BSE, optics)
        if gen_type in ("bse", "optics"):
            from .parser import parse_spectrum_file
            eps_files = list(out_dir.glob("o-*.eps_*"))
            if eps_files:
                spec_result = parse_spectrum_file(eps_files[0])
                step_result_data["n_spectrum_points"] = len(spec_result.points)
                if spec_result.static_dielectric is not None:
                    step_result_data["static_dielectric"] = spec_result.static_dielectric

    return JobResult(
        job_id=job.id,
        success=True,
        step_results={step_ulid: step_result_data},
    )


def yambo_step_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
    """Execute a yambo step job.

    Dispatches to setup or calculation handler based on gen type.
    """
    if not job.step_ulids:
        return JobResult(
            job_id=job.id, success=False, error="No step ULIDs in job",
        )

    step_ulid = job.step_ulids[0]
    step = _find_step_by_ulid(calculation, step_ulid)
    if step is None:
        return JobResult(
            job_id=job.id, success=False,
            error=f"Step not found: {step_ulid}",
        )

    gen_type = job.metadata.get("step_type_gen", "optics")
    calc_raw_dir = calculation.raw_dir
    timeout = context.get("timeout", 3600)

    if gen_type == "setup":
        return _handle_setup(job, calc_raw_dir, step_ulid, timeout)
    else:
        return _handle_calculation(
            job, calc_raw_dir, step, step_ulid, gen_type, timeout,
        )
