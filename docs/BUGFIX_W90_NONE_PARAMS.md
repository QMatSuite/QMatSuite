# Bug Fix: Wannier90 Step Materialization with None Parameters

## Issue

When running the diamond Wannier90 demo, the calculation failed with:
```
int() argument must be a string, a bytes-like object or a number, not 'NoneType'
```

**Root Cause**: The `w90_preproc` step had `num_bands: null` in its parameters. When `materialize_step_spec` tried to convert this to an integer with `int(flat_params["num_bands"])`, it raised a `TypeError`.

## Fix

**File**: `src/quantumvitas/calculation/structure_steps.py`

**Changes**: Added `None` checks before converting parameters to integers in the Wannier90 step materialization code:

```python
# Before (lines 704-717):
if "num_wann" in flat_params:
    w90_input.num_wann = int(flat_params["num_wann"])  # ❌ Fails if value is None
if "num_bands" in flat_params:
    w90_input.num_bands = int(flat_params["num_bands"])  # ❌ Fails if value is None
if "num_iter" in flat_params:
    w90_input.num_iter = int(flat_params["num_iter"])  # ❌ Fails if value is None
if "mp_grid" in flat_params:
    mp_grid = flat_params["mp_grid"]
    if isinstance(mp_grid, list):
        w90_input.mp_grid = [int(x) for x in mp_grid]  # ❌ Fails if any x is None

# After (lines 704-718):
if "num_wann" in flat_params and flat_params["num_wann"] is not None:
    w90_input.num_wann = int(flat_params["num_wann"])
if "num_bands" in flat_params and flat_params["num_bands"] is not None:
    w90_input.num_bands = int(flat_params["num_bands"])
if "num_iter" in flat_params and flat_params["num_iter"] is not None:
    w90_input.num_iter = int(flat_params["num_iter"])
if "mp_grid" in flat_params and flat_params["mp_grid"] is not None:
    mp_grid = flat_params["mp_grid"]
    if isinstance(mp_grid, list):
        # Filter out None values and convert to int
        w90_input.mp_grid = [int(x) for x in mp_grid if x is not None]
if "projections" in flat_params and flat_params["projections"] is not None:
    w90_input.projections_block = str(flat_params["projections"])
if "projections_block" in flat_params and flat_params["projections_block"] is not None:
    w90_input.projections_block = str(flat_params["projections_block"])
```

## Verification

Tested with the actual diamond demo step spec:
```bash
python -c "
from pathlib import Path
from quantumvitas.calculation.structure_steps import StructureStepSpec, materialize_step_spec
import tempfile

spec_file = Path('/Users/kfranke/Documents/diamond-wannier90-demo/calculations/diamond-mlwfs/steps/w90_preproc.step.yaml')
spec = StructureStepSpec.from_yaml(spec_file)

with tempfile.TemporaryDirectory() as tmpdir:
    output_dir = Path(tmpdir) / 'raw'
    output_dir.mkdir()
    
    input_file, _ = materialize_step_spec(
        spec=spec,
        output_dir=output_dir,
        calculation_dir=spec_file.parent.parent,
        project_root=Path('/Users/kfranke/Documents/diamond-wannier90-demo'),
    )
    print(f'✓ Generated: {input_file}')
"
# Result: ✓ Generated successfully
```

## Impact

- ✅ `w90_preproc` and `w90_run` steps can now handle `None` values in optional parameters
- ✅ `num_bands` can be `None` (will be omitted from .win file)
- ✅ `num_iter` can be `None` (will use default value of 20)
- ✅ `mp_grid` can contain `None` values (filtered out before conversion)
- ✅ All Wannier90 demos should now materialize correctly

## Related Files

- `src/quantumvitas/calculation/structure_steps.py`: Main fix location
- `resources/demo_projects/diamond_wannier90_demo.yml`: Contains `num_bands: null` in w90_preproc parameters
- `tools/generate_wannier90_demos.py`: Generates demos with `win_input.num_bands` which can be `None`

