"""
Allow running the PySCF runner as a module.

Usage:
    python -m quantumvitas.engines.pyscf job.json
    python -m quantumvitas.engines.pyscf job_chain.json  # Phase 3C: chain execution
"""

from .runner import run_job, run_job_chain
import sys
import json
from pathlib import Path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m quantumvitas.engines.pyscf <job.json|job_chain.json>", file=sys.stderr)
        sys.exit(3)
    
    job_path = Path(sys.argv[1])
    
    # Phase 3C: Detect chain execution vs single step
    try:
        job_data = json.loads(job_path.read_text())
        if "chain_steps" in job_data:
            # Chain execution
            exit_code = run_job_chain(job_path)
        else:
            # Single step execution
            exit_code = run_job(job_path)
    except Exception as e:
        print(f"ERROR: Failed to read job file: {e}", file=sys.stderr)
        sys.exit(3)
    
    sys.exit(exit_code)



