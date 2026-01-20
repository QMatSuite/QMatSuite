"""LAMMPS input script generation from templates."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

from jinja2 import Environment, FileSystemLoader, Template

logger = logging.getLogger(__name__)


def get_template_dir() -> Path:
    """Get LAMMPS template directory."""
    import quantumvitas
    pkg_path = Path(quantumvitas.__file__).parent.parent.parent  # Go up to repo root
    return pkg_path / "resources" / "calculation_templates" / "lammps"


def render_lammps_template(
    template_name: str,
    context: Dict,
) -> str:
    """
    Render LAMMPS input script from Jinja2 template.
    
    Args:
        template_name: Template filename (e.g., "minimize.in.j2", "md_nvt.in.j2")
        context: Template variables
    
    Returns:
        Rendered script content
    
    Raises:
        FileNotFoundError: If template not found
    """
    template_dir = get_template_dir()
    
    if not template_dir.exists():
        raise FileNotFoundError(f"Template directory not found: {template_dir}")
    
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    
    try:
        template = env.get_template(template_name)
        return template.render(**context)
    except Exception as e:
        raise RuntimeError(f"Failed to render template {template_name}: {e}") from e


def get_template_for_step_type(step_type: str) -> str:
    """
    Map step type to template filename.
    
    Args:
        step_type: Machine step type (e.g., "lammps_relax", "lammps_md")
    
    Returns:
        Template filename
    """
    if step_type == "lammps_relax":
        return "minimize.in.j2"
    elif step_type == "lammps_md":
        # Need to determine ensemble from parameters
        # Default to NVT, can be overridden
        return "md_nvt.in.j2"
    elif step_type == "lammps_restart":
        # Restart uses same template as MD but with restart_from
        return "md_nvt.in.j2"
    else:
        raise ValueError(f"Unknown step type: {step_type}")


def build_template_context(
    step: "Step",
    calculation: "Calculation",
    pair_style_block: str,
    restart_file: Optional[str] = None,
) -> Dict:
    """
    Build template context from step and calculation.
    
    Args:
        step: Step object
        calculation: Calculation context
        pair_style_block: Generated pair_style/pair_coeff commands
        restart_file: Optional restart file path (for restart_from)
    
    Returns:
        Template context dictionary
    """
    params = step.parameters if hasattr(step, "parameters") else {}
    
    # Get step ULID
    step_ulid = step.meta.id if hasattr(step, "meta") and hasattr(step.meta, "id") else ""
    
    context = {
        "step_type": step.step_type if hasattr(step, "step_type") else "",
        "step_ulid": step_ulid,
        "units": params.get("units", "metal"),
        "atom_style": params.get("atom_style", "atomic"),
        "pair_style_block": pair_style_block,
        "restart_from": restart_file is not None,
        "restart_file": restart_file,
    }
    
    # Minimize-specific
    if "energy_tolerance" in params:
        context["energy_tolerance"] = params["energy_tolerance"]
        context["force_tolerance"] = params.get("force_tolerance", 1.0e-8)
        context["max_iterations"] = params.get("max_iterations", 1000)
        context["max_evaluations"] = params.get("max_evaluations", 10000)
        context["min_style"] = params.get("engine_params", {}).get("lammps", {}).get("min_style", "cg")
    
    # MD-specific
    if "ensemble" in params:
        context["ensemble"] = params["ensemble"]
        context["temperature"] = params.get("temperature", 300)
        context["pressure"] = params.get("pressure", 0.0)
        context["n_steps"] = params.get("n_steps", 1000)
        
        # Timestep conversion (canonical fs -> LAMMPS units)
        timestep_fs = params.get("timestep_fs", 1.0)
        units = params.get("units", "metal")
        if units == "metal":
            # metal: ps, so divide by 1000
            context["timestep"] = timestep_fs / 1000.0
        elif units == "real":
            # real: fs, so use directly
            context["timestep"] = timestep_fs
        else:
            # lj: use timestep_tau if provided
            context["timestep"] = params.get("timestep_tau", 0.005)
        
        # Engine params
        engine_params = params.get("engine_params", {}).get("lammps", {})
        context["thermostat_damp"] = engine_params.get("thermostat_damp", 100.0)
        context["barostat_damp"] = engine_params.get("barostat_damp", 1000.0)
        context["barostat"] = engine_params.get("barostat", "iso")
        context["velocity_seed"] = engine_params.get("velocity_seed", 12345)
    
    # Output control
    context["thermo_frequency"] = params.get("thermo_frequency", 100)
    context["dump_frequency"] = params.get("dump_frequency", 1000)
    context["dump_trajectory"] = params.get("dump_trajectory", True)
    context["restart_frequency"] = params.get("restart_frequency", 10000)
    
    return context

