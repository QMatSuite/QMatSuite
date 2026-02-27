# pip_requirements for Python Engines — Worklog

## Problem

PySCF's geometry optimization needs `geometric` and `pyberny` (pip packages), but
micromamba/conda installs don't include them. This causes runtime `ImportError` when
PySCF tries `from pyscf.geomopt.geometric_solver import optimize`.

Additionally, `engine_registry.py` had a latent bug: `subprocess` used at line 590
but never imported.

## Design

Store pip deps as `dict[str, str]` in ENGINE_META where key = pip package name,
value = import name:

```python
"pip_requirements": {"pyberny": "berny", "geometric": "geometric"}
```

- Key is used by `pip install`
- Value is used by `import` verification
- Empty dict `{}` for engines with no pip deps

## Changes

| File | Change |
|------|--------|
| `engine_meta.py` | Added `pip_requirements` to all 15 entries |
| `engine_installer.py` | Added `_pip_install_requirements()` + `_verify_pip_requirements()`, wired into `install_engine_conda()` |
| `engine_registry.py` | Fixed missing `import subprocess`, enhanced `_verify_installation()` to check pip deps |
| `test_pip_requirements.py` | New test file (9 tests) |
| `test_engine_registry_distribution.py` | Extended `test_engine_meta_completeness()` |

## Result

- All new tests pass
- Full suite: no regressions
