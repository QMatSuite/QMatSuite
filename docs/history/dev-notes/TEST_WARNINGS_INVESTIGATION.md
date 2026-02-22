# Test Warnings Investigation (2026-02-07)

## Status: Resolved — No Production Code Issues

Current test output: `4397 passed, 18 skipped, 1 xfailed, 1 xpassed, ~906 warnings`

All ~906 warnings originate from **third-party libraries** or **pytest internals**.
Production code (`src/qmatsuite/`) has no resource leaks.

---

## Warning Categories

### 1. sqlite3 ResourceWarning (~82 occurrences)

```
ResourceWarning: unclosed database in <sqlite3.Connection object at 0x...>
```

**Source**: pytest/pluggy internals (ast.py assertion rewriting + GC timing).

**NOT from our code.** Every `open_provenance_db()` call in `recording.py`, `cas.py`,
`query.py`, `pins.py`, `restore.py` uses the correct `try/finally/conn.close()` pattern.

**Evidence**:
- `PYTHONTRACEMALLOC=40` shows **zero** `qmatsuite` frames in allocation tracebacks —
  only `_pytest/runner.py`, `pluggy/_callers.py`, `ast.py`.
- Running the identical QMSService workflow (init_project, import_structure,
  init_calculation, save_yaml_doc, add_step) **outside pytest** with
  `-Werror::ResourceWarning` produces **zero warnings**.
- Turning warnings into errors (`-W error::ResourceWarning`) causes **zero test failures**,
  confirming warnings fire during GC/teardown, not during execution.

**Root cause**: Python 3.14 + pytest interaction. Pytest's assertion rewriting compiles
AST nodes that happen to be in scope when sqlite3 connection wrappers are GC'd, making
the tracemalloc frames point to `ast.py:46` instead of our code. The actual connections
were already `.close()`d by our `finally` blocks.

**Action**: None required. Do not suppress with filterwarnings — the warnings are harmless
and suppressing them would hide any future real leaks.

### 2. spglib DeprecationWarning (~600+ occurrences)

```
DeprecationWarning: Set OLD_ERROR_HANDLING to false and catch the errors directly.
```

**Source**: `spglib` package (called by pymatgen for symmetry operations).

**Action**: Upstream library issue. Will resolve when spglib updates or when we
upgrade pymatgen to a version that adapts to the new API.

### 3. pymatgen FutureWarning (~100+ occurrences)

```
FutureWarning: We strongly discourage using implicit binary/text `mode`
```

**Source**: `pymatgen/io/cif.py` file I/O.

**Action**: Upstream library issue. Will resolve with pymatgen update.

### 4. pymatgen EncodingWarning (~small count)

```
EncodingWarning: We strongly encourage explicit `encoding`
```

**Source**: `pymatgen/core/structure.py`.

**Action**: Upstream library issue.

---

## How to Reproduce the "Production is Clean" Proof

```bash
source .venv/bin/activate
python3 -Werror::ResourceWarning -c "
import warnings, gc, json, tempfile, shutil
from pathlib import Path
warnings.simplefilter('error', ResourceWarning)
tmp = Path(tempfile.mkdtemp())
try:
    from qmatsuite.api import QMSService
    from qmatsuite.core.yaml_io import save_yaml_doc
    from qmatsuite.core.yamldoc import CalcDoc
    from qmatsuite.core.models import load_calculation
    project_root = QMSService.init_project(target_dir=tmp/'proj', name='Test')
    gc.collect()
    svc = QMSService(project_root)
    from pymatgen.core import Structure, Lattice
    lattice = Lattice([[3.37,3.37,0.0],[0.0,3.37,3.37],[3.37,0.0,3.37]])
    structure = Structure(lattice, ['C','C'], [[0.0,0.0,0.0],[0.25,0.25,0.25]])
    sf = tmp / 'diamond.json'
    sf.write_text(json.dumps(structure.as_dict()))
    sr = svc.structure.import_file(sf, name='Diamond C')
    gc.collect()
    cr = svc.project.init_calculation(name='test', structure_selector=sr.meta.ulid)
    cp = cr.absolute_path / 'calculation.yaml'
    cm = load_calculation(cp, project_root=project_root)
    cm.engine_family = 'qmcpack'
    cm.species_map = {}
    save_yaml_doc(CalcDoc(cm.to_dict()), cp)
    gc.collect()
    svc.calculation.add_step(calc_selector=cr.meta.ulid, step_type_gen='vmc')
    gc.collect()
    print('PASS: no ResourceWarning from production code')
finally:
    shutil.rmtree(tmp, ignore_errors=True)
"
```

Expected output: `PASS: no ResourceWarning from production code`

---

## Skip Count (18 skipped)

The 18 skips are all legitimate:
- Engine real-execution tests that require binary availability markers
  (`requires_qe`, `requires_orca`, `requires_pyscf`, `requires_lammps`, `requires_qmcpack`)
- Tests that skip when specific test data is unavailable

Previously there were 24 skips due to a bug where `conftest.py:force_test_cwd_to_tmp`
changed CWD to a tmpdir, breaking engine binary detection. Fixed by making
`_find_repo_root()` in `discovery.py` also walk up from `__file__` location
(not just CWD).
