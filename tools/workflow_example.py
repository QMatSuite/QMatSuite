"""
Example: Using QE Engine's step and calculation execution.

This demonstrates the generalized step/calculation system where:
- Steps are basic execution units (scf, nscf, dos, bands, etc.)
- Calculations combine multiple steps sequentially
- Step type is auto-detected from input file
- Each step maps to a QE executable (.x file)
"""

from pathlib import Path
from src.qmatsuite.core.engines.qe import QuantumEspressoEngine
from src.qmatsuite.core.engines.base import EngineConfig

# Initialize QE engine
config = EngineConfig(name="qe")
engine = QuantumEspressoEngine(config)

# Example 1: Detect step type from input file
input_file = Path("path/to/si.1_scf.in")
step_type = engine.detect_step_type(input_file)
print(f"Detected step type: {step_type}")  # Should be "scf"

# Example 2: Run a single step
from qmatsuite.core.paths import tmp_runs_dir
working_dir = tmp_runs_dir() / "work"
result = engine.run_step(
    input_file=input_file,
    working_dir=working_dir,
    step_type=None,  # Auto-detect
    timeout=300
)

if result.success:
    print(f"Step {result.step_type} completed successfully")
    print(f"Output file: {result.output_file}")
    print(f"Execution time: {result.execution_time:.2f}s")
else:
    print(f"Step failed: {result.error}")

# Example 3: Run a calculation (SCF -> NSCF -> DOS)
scf_file = Path("path/to/si.1_scf.in")
nscf_file = Path("path/to/si.2_nscf.in")
dos_file = Path("path/to/si.3_dos.in")

calculation_result = engine.run_calculation(
    steps=[
        (scf_file, None),    # Auto-detect step type
        (nscf_file, None),  # Auto-detect step type
        (dos_file, "dos"),   # Explicit step type
    ],
    working_dir=working_dir,
    timeout=300,
    stop_on_error=True
)

if calculation_result.success:
    print(f"Calculation completed successfully in {calculation_result.total_time:.2f}s")
    for i, step_result in enumerate(calculation_result.steps):
        print(f"  Step {i+1} ({step_result.step_type}): {step_result.execution_time:.2f}s")
else:
    print(f"Calculation failed: {calculation_result.error}")

