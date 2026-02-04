"""
Allow running the Psi4 runner as a module.

Usage:
    python -m quantumvitas.engines.psi4 job_chain.json
    python -m quantumvitas.engines.psi4 job.json  # Legacy: converted to chain of length 1
"""

from .runner import run_job_chain
import sys
import json
from pathlib import Path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m quantumvitas.engines.psi4 <job_chain.json|job.json>", file=sys.stderr)
        sys.exit(3)

    job_path = Path(sys.argv[1])

    try:
        job_data = json.loads(job_path.read_text())
        if "chain_steps" in job_data:
            exit_code = run_job_chain(job_path)
        else:
            # Legacy single-step job.json: convert to chain of length 1
            step_type = job_data.get("step_type_spec", "psi4_scf")
            working_dir = job_data.get("working_dir", str(job_path.parent))
            params = job_data.get("parameters", {})
            resources = job_data.get("resources", {})

            chain_job = {
                "base_working_dir": working_dir,
                "chain_steps": [
                    {
                        "step_ulid": "single_step",
                        "step_type_spec": step_type,
                        "parameters": params,
                        "step_artifacts_dir": working_dir,
                    }
                ],
                "target_step_ulid": "single_step",
                "resources": resources,
            }

            chain_job_path = job_path.parent / "job_chain.json"
            chain_job_path.write_text(json.dumps(chain_job, indent=2))
            exit_code = run_job_chain(chain_job_path)

            if chain_job_path != job_path:
                try:
                    chain_job_path.unlink()
                except Exception:
                    pass
    except Exception as e:
        print(f"ERROR: Failed to read or execute job file: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(3)

    sys.exit(exit_code)
