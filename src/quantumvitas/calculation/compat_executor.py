"""
Compat input playback executor for tutorial integration tests.

This module provides a minimal executor that patches existing .in files
with only runtime-managed CONTROL keys (prefix, outdir, pseudo_dir)
without full parsing/merging.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Optional

from quantumvitas.core.pseudo import get_system_pseudo_dir

# Import StepResult from engine base (not calculation.types)
from quantumvitas.engine.base import StepResult


def run_qe_step_from_existing_input_compat(
    existing_input_path: Path,
    working_dir: Path,
    project_root: Path,
    step_ulid: str,
    calculation_slug: str,
    engine,
    step_type: Optional[str] = None,
    timeout: Optional[int] = None,
) -> StepResult:
    """
    Execute a QE step using an existing .in file with minimal patching.
    
    This is a compat mode for tutorial playback tests that use prebuilt .in files.
    Only patches 3 CONTROL keys: prefix, outdir, pseudo_dir.
    Does NOT parse/merge the full .in file.
    
    Args:
        existing_input_path: Path to the existing .in file (from calculation.yaml steps[].input)
        working_dir: Working directory for execution (calculation raw_dir)
        project_root: Project root path
        step_ulid: Step ULID or identifier
        calculation_slug: Calculation slug/name (used for prefix if step spec doesn't provide)
        engine: QE engine instance
        step_type: Optional step type (e.g., "scf", "nscf")
        timeout: Optional execution timeout
        
    Returns:
        StepResult with execution status
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Resolve existing input path relative to working_dir
    if not existing_input_path.is_absolute():
        existing_input_path = (working_dir / existing_input_path).resolve()
    
    if not existing_input_path.exists():
        raise FileNotFoundError(f"Existing input file not found: {existing_input_path}")
    
    # Read .in file as text (no parsing)
    input_text = existing_input_path.read_text()
    
    # Compute runtime values
    # Prefix: use calculation slug (e.g., "si" from "si_bands")
    prefix = calculation_slug.split("_")[0] if "_" in calculation_slug else calculation_slug
    
    # Outdir: standard project outdir
    outdir = "./outdir"
    
    # Pseudo_dir: project pseudo directory (absolute path)
    project_pseudo_dir = project_root / "pseudo"
    project_pseudo_dir.mkdir(parents=True, exist_ok=True)
    pseudo_dir_str = str(project_pseudo_dir.resolve())
    
    # Patch CONTROL namelist (minimal text replacement)
    patched_text = _patch_control_namelist(
        input_text,
        prefix=prefix,
        outdir=outdir,
        pseudo_dir=pseudo_dir_str,
    )
    
    # Stage required pseudos
    required_pseudos = _extract_required_pseudos_from_atomic_species(input_text)
    _stage_required_pseudos(
        required_pseudos=required_pseudos,
        project_pseudo_dir=project_pseudo_dir,
        system_pseudo_dir=get_system_pseudo_dir(),
    )
    
    # Write patched input to working directory
    # Use the same filename as existing input (e.g., si.0_scf.in)
    output_input_path = working_dir / existing_input_path.name
    output_input_path.write_text(patched_text)
    
    # Verify patching worked
    written_text = output_input_path.read_text()
    written_pseudo_dir = None
    for line in written_text.split('\n'):
        if 'pseudo_dir' in line.lower():
            written_pseudo_dir = line.strip()
            break
    
    logger.info(
        f"[COMPAT_EXECUTOR] Patched input: {output_input_path} "
        f"(prefix={prefix}, outdir={outdir}, pseudo_dir={pseudo_dir_str})"
    )
    logger.debug(
        f"[COMPAT_EXECUTOR] Written pseudo_dir line: {written_pseudo_dir}"
    )
    
    # Execute using engine
    try:
        result = engine.backend.run_step(
            input_file=output_input_path,
            working_dir=working_dir,
            step_type=step_type,
            timeout=timeout,
        )
        return result
    except Exception as e:
        logger.exception(f"[COMPAT_EXECUTOR] Step {step_ulid} execution failed")
        from quantumvitas.engine.base import StepResult
        return StepResult(
            success=False,
            error=str(e),
            output_file=None,
            return_code=1,
        )


def _patch_control_namelist(
    input_text: str,
    prefix: str,
    outdir: str,
    pseudo_dir: str,
) -> str:
    """
    Patch CONTROL namelist with prefix, outdir, pseudo_dir.
    
    Ensures these three keys exist in &CONTROL ... / block.
    Works whether keys exist or not.
    """
    # Pattern to match &CONTROL ... / block (case-insensitive, multiline)
    # Match from &CONTROL (or &control) to the next / that's on its own line
    control_pattern = re.compile(
        r'&CONTROL\s*\n(.*?)\n\s*/',
        re.IGNORECASE | re.DOTALL
    )
    
    def replace_control(match):
        control_content = match.group(1)
        
        # Update or add prefix (handle both 'prefix = value' and 'prefix=value')
        # Match until end of line (handles quoted strings, spaces, etc.)
        if re.search(r'\bprefix\s*=', control_content, re.IGNORECASE):
            control_content = re.sub(
                r'\bprefix\s*=\s*[^\n]+',
                f"prefix = '{prefix}'",
                control_content,
                flags=re.IGNORECASE
            )
        else:
            # Add prefix at the end of existing parameters
            control_content = control_content.rstrip() + f"\n    prefix = '{prefix}'"
        
        # Update or add outdir
        if re.search(r'\boutdir\s*=', control_content, re.IGNORECASE):
            control_content = re.sub(
                r'\boutdir\s*=\s*[^\n]+',
                f"outdir = '{outdir}'",
                control_content,
                flags=re.IGNORECASE
            )
        else:
            control_content = control_content.rstrip() + f"\n    outdir = '{outdir}'"
        
        # Update or add pseudo_dir
        if re.search(r'\bpseudo_dir\s*=', control_content, re.IGNORECASE):
            control_content = re.sub(
                r'\bpseudo_dir\s*=\s*[^\n]+',
                f"pseudo_dir = '{pseudo_dir}'",
                control_content,
                flags=re.IGNORECASE
            )
        else:
            control_content = control_content.rstrip() + f"\n    pseudo_dir = '{pseudo_dir}'"
        
        return f"&CONTROL\n{control_content}\n/"
    
    # Replace CONTROL block
    patched = control_pattern.sub(replace_control, input_text)
    
    # If no CONTROL block exists, add one at the beginning
    if not re.search(r'&CONTROL', patched, re.IGNORECASE):
        patched = f"&CONTROL\n    prefix = '{prefix}'\n    outdir = '{outdir}'\n    pseudo_dir = '{pseudo_dir}'\n/\n{patched}"
    
    return patched


def _extract_required_pseudos_from_atomic_species(input_text: str) -> list[str]:
    """
    Extract required pseudo filenames from ATOMIC_SPECIES block.
    
    Minimal parsing: only reads ATOMIC_SPECIES lines until blank line or next card.
    Format: <sym> <mass> <fname>
    """
    required_pseudos = []
    
    # Find ATOMIC_SPECIES block
    atomic_species_match = re.search(
        r'ATOMIC_SPECIES\s*\n(.*?)(?=\n\s*\n|\n[A-Z_]|\Z)',
        input_text,
        re.IGNORECASE | re.DOTALL
    )
    
    if not atomic_species_match:
        return required_pseudos
    
    # Parse lines
    lines = atomic_species_match.group(1).strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line or line.startswith('!'):
            continue
        
        # Split by whitespace: <sym> <mass> <fname>
        parts = line.split()
        if len(parts) >= 3:
            pseudo_filename = parts[2].strip()
            # Skip placeholders
            if pseudo_filename and not pseudo_filename.startswith('__MISSING_PSEUDO__'):
                required_pseudos.append(pseudo_filename)
    
    return required_pseudos


def _stage_required_pseudos(
    required_pseudos: list[str],
    project_pseudo_dir: Path,
    system_pseudo_dir: Optional[Path],
) -> None:
    """
    Copy required pseudo files into project/pseudo directory.
    
    Args:
        required_pseudos: List of pseudo filenames (e.g., ["Si.pbe-n-rrkjus_psl.1.0.0.UPF"])
        project_pseudo_dir: Destination directory (<project_root>/pseudo)
        system_pseudo_dir: Source directory (internal pseudo library, e.g., resources/pseudo)
        
    Raises:
        ValueError: If a required pseudo file is missing in internal library
    """
    if not required_pseudos:
        return
    
    if not system_pseudo_dir or not system_pseudo_dir.exists():
        raise ValueError(
            f"System pseudo directory not found: {system_pseudo_dir}. "
            f"Cannot stage required pseudos: {required_pseudos}"
        )
    
    project_pseudo_dir.mkdir(parents=True, exist_ok=True)
    
    for pseudo_filename in required_pseudos:
        source_path = system_pseudo_dir / pseudo_filename
        dest_path = project_pseudo_dir / pseudo_filename
        
        # Skip if already exists
        if dest_path.exists():
            continue
        
        if not source_path.exists():
            raise ValueError(
                f"Required pseudo file not found in internal library: {pseudo_filename}. "
                f"Expected at: {source_path}. "
                f"Please ensure the file exists in {system_pseudo_dir}."
            )
        
        # Copy file
        shutil.copy2(source_path, dest_path)

