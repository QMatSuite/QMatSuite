"""
Allow running the PySCF runner as a module.

Phase 3C: PySCF execution is chain-only. Single-step execution is converted to chain of length 1.

Usage:
    python -m quantumvitas.engines.pyscf job_chain.json
    python -m quantumvitas.engines.pyscf job.json  # Legacy: converted to chain of length 1
"""

from .runner import run_job_chain
import sys
import json
from pathlib import Path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m quantumvitas.engines.pyscf <job_chain.json|job.json>", file=sys.stderr)
        sys.exit(3)
    
    job_path = Path(sys.argv[1])
    
    # Phase 3C: PySCF is chain-only. Convert single job.json to chain of length 1 if needed.
    try:
        job_data = json.loads(job_path.read_text())
        if "chain_steps" in job_data:
            # Already a chain job
            exit_code = run_job_chain(job_path)
        else:
            # Legacy single-step job.json: convert to chain of length 1
            # Extract step info from job.json
            step_type = job_data.get("step_type", "pyscf_scf")
            working_dir = job_data.get("working_dir", str(job_path.parent))
            params = job_data.get("parameters", {})
            resources = job_data.get("resources", {})
            allow_chkfile_init_guess = job_data.get("allow_chkfile_init_guess", False)
            
            # Create chain job spec (chain of length 1)
            chain_job = {
                "base_working_dir": working_dir,
                "chain_steps": [
                    {
                        "step_ulid": "single_step",  # Dummy ULID for single-step conversion
                        "step_type": step_type,
                        "parameters": params,
                        "step_artifacts_dir": working_dir,
                        "allow_chkfile_init_guess": allow_chkfile_init_guess,
                    }
                ],
                "target_step_ulid": "single_step",
                "resources": resources,
            }
            
            # Write temporary chain job file
            chain_job_path = job_path.parent / "job_chain.json"
            chain_job_path.write_text(json.dumps(chain_job, indent=2))
            
            # Execute as chain
            exit_code = run_job_chain(chain_job_path)
            
            # Clean up temporary file if it was created (but keep if it was the original)
            if chain_job_path != job_path:
                try:
                    chain_job_path.unlink()
                except Exception:
                    pass  # Non-fatal cleanup
    except Exception as e:
        print(f"ERROR: Failed to read or execute job file: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(3)
    
    sys.exit(exit_code)



