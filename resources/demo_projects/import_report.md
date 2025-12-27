# Tutorial Dataset Import Report

**Total datasets discovered:** 28
**Successfully imported:** 12
**Failed:** 16

**Consistent demos:** 9/12

## Successful Imports

### 00_Si_scf
- Steps: 1
- Structure: ✓ Consistent
- Round-trip validation: ✗ Failed (0 differences)
- Reference artifacts: scf

### 11_Si_100_surface_reconstruction
- Steps: 1
- Structure: ✓ Consistent
- Round-trip validation: ✗ Failed (0 differences)

### 15_bulk_modulus_Si
- Steps: 3
- Structure: ✓ Consistent
- Round-trip validation: ✗ Failed (0 differences)
- Reference artifacts: scf

### 18_H2O_MD
- Steps: 2
- Structure: ✓ Consistent
- Round-trip validation: ✗ Failed (0 differences)

### 19_Si_CPMD
- Steps: 1
- Structure: ✓ Consistent
- Round-trip validation: ✗ Failed (0 differences)

### 19_Si_CPMD
- Steps: 3
- Structure: ✓ Consistent
- Round-trip validation: ✗ Failed (0 differences)

### 19_Si_CPMD
- Steps: 3
- Structure: ✓ Consistent
- Round-trip validation: ✗ Failed (0 differences)

### 19_Si_CPMD
- Steps: 3
- Structure: ✓ Consistent
- Round-trip validation: ✗ Failed (0 differences)

### 01_H2
- Steps: 2
- Structure: ✓ Consistent
- Round-trip validation: ✗ Failed (0 differences)
- Reference artifacts: scf

### 02_H2O
- Steps: 1
- Structure: ✓ Consistent
- Round-trip validation: ✗ Failed (0 differences)

### 03_Si_vc_relax
- Steps: 1
- Structure: ✓ Consistent
- Round-trip validation: ✗ Failed (0 differences)

### 08_Fe_DOS
- Steps: 1
- Structure: ✓ Consistent
- Round-trip validation: ✗ Failed (0 differences)
- Reference artifacts: scf

## Failed Imports

### 10_benzene_TDDFT
- Error: Error creating demo: expected str, bytes or os.PathLike object, not NoneType
Traceback (most recent call last):
  File "/Users/mac13/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac13/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 415, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac13/QMatSuite/src/quantumvitas/api.py", line 4282, in import_step_from_qe_input
    structure = read_structure(structure_path)
  File "/Users/mac13/QMatSuite/src/quantumvitas/io/structure_io.py", line 46, in read_structure
    filepath = Path(filepath)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1072, in __new__
    self = cls._from_parts(args, init=False)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 697, in _from_parts
    drv, root, parts = self._parse_args(args)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 681, in _parse_args
    a = os.fspath(a)
TypeError: expected str, bytes or os.PathLike object, not NoneType


### 12_NMR_gipaw
- Error: Error creating demo: expected str, bytes or os.PathLike object, not NoneType
Traceback (most recent call last):
  File "/Users/mac13/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac13/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 415, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac13/QMatSuite/src/quantumvitas/api.py", line 4282, in import_step_from_qe_input
    structure = read_structure(structure_path)
  File "/Users/mac13/QMatSuite/src/quantumvitas/io/structure_io.py", line 46, in read_structure
    filepath = Path(filepath)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1072, in __new__
    self = cls._from_parts(args, init=False)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 697, in _from_parts
    drv, root, parts = self._parse_args(args)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 681, in _parse_args
    a = os.fspath(a)
TypeError: expected str, bytes or os.PathLike object, not NoneType


### 12_NMR_gipaw
- Error: Error creating demo: expected str, bytes or os.PathLike object, not NoneType
Traceback (most recent call last):
  File "/Users/mac13/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac13/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 415, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac13/QMatSuite/src/quantumvitas/api.py", line 4282, in import_step_from_qe_input
    structure = read_structure(structure_path)
  File "/Users/mac13/QMatSuite/src/quantumvitas/io/structure_io.py", line 46, in read_structure
    filepath = Path(filepath)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1072, in __new__
    self = cls._from_parts(args, init=False)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 697, in _from_parts
    drv, root, parts = self._parse_args(args)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 681, in _parse_args
    a = os.fspath(a)
TypeError: expected str, bytes or os.PathLike object, not NoneType


### 13_graphene
- Error: Error creating demo: ibrav=12/-12 requires b, c, and cos(angle).
Traceback (most recent call last):
  File "/Users/mac13/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac13/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 346, in materialize_project_from_qe_input_folder
    ref_structure = structure_from_qe_input(reference_qe_input)
  File "/Users/mac13/QMatSuite/src/quantumvitas/io/structure_io.py", line 332, in structure_from_qe_input
    lattice = _lattice_from_ibrav(system)
  File "/Users/mac13/QMatSuite/src/quantumvitas/io/structure_io.py", line 511, in _lattice_from_ibrav
    vectors = _ibrav_vectors(ibrav, params)
  File "/Users/mac13/QMatSuite/src/quantumvitas/io/structure_io.py", line 630, in _ibrav_vectors
    raise ValueError("ibrav=12/-12 requires b, c, and cos(angle).")
ValueError: ibrav=12/-12 requires b, c, and cos(angle).


### 14_DFT_plus_U_NiO
- Error: Missing pseudopotentials (could not download): ni_pbe_v1.4.uspp.F.UPF
- Missing pseudopotentials: ni_pbe_v1.4.uspp.F.UPF

### 14_DFT_plus_U_NiO
- Error: Missing pseudopotentials (could not download): ni_pbe_v1.4.uspp.F.UPF
- Missing pseudopotentials: ni_pbe_v1.4.uspp.F.UPF

### 17_H2O_vibration
- Error: Error creating demo: expected str, bytes or os.PathLike object, not NoneType
Traceback (most recent call last):
  File "/Users/mac13/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac13/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 415, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac13/QMatSuite/src/quantumvitas/api.py", line 4282, in import_step_from_qe_input
    structure = read_structure(structure_path)
  File "/Users/mac13/QMatSuite/src/quantumvitas/io/structure_io.py", line 46, in read_structure
    filepath = Path(filepath)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1072, in __new__
    self = cls._from_parts(args, init=False)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 697, in _from_parts
    drv, root, parts = self._parse_args(args)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 681, in _parse_args
    a = os.fspath(a)
TypeError: expected str, bytes or os.PathLike object, not NoneType


### 19_Si_CPMD
- Error: Error creating demo: expected str, bytes or os.PathLike object, not NoneType
Traceback (most recent call last):
  File "/Users/mac13/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac13/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 415, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac13/QMatSuite/src/quantumvitas/api.py", line 4282, in import_step_from_qe_input
    structure = read_structure(structure_path)
  File "/Users/mac13/QMatSuite/src/quantumvitas/io/structure_io.py", line 46, in read_structure
    filepath = Path(filepath)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1072, in __new__
    self = cls._from_parts(args, init=False)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 697, in _from_parts
    drv, root, parts = self._parse_args(args)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 681, in _parse_args
    a = os.fspath(a)
TypeError: expected str, bytes or os.PathLike object, not NoneType


### 04_Si_DOS
- Error: Error creating demo: expected str, bytes or os.PathLike object, not NoneType
Traceback (most recent call last):
  File "/Users/mac13/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac13/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 415, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac13/QMatSuite/src/quantumvitas/api.py", line 4282, in import_step_from_qe_input
    structure = read_structure(structure_path)
  File "/Users/mac13/QMatSuite/src/quantumvitas/io/structure_io.py", line 46, in read_structure
    filepath = Path(filepath)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1072, in __new__
    self = cls._from_parts(args, init=False)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 697, in _from_parts
    drv, root, parts = self._parse_args(args)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 681, in _parse_args
    a = os.fspath(a)
TypeError: expected str, bytes or os.PathLike object, not NoneType


### 05_NH3_inversion
- Error: Missing pseudopotentials (could not download): N.oncvpsp.upf
- Missing pseudopotentials: N.oncvpsp.upf

### 06_Al_DOS
- Error: Error creating demo: expected str, bytes or os.PathLike object, not NoneType
Traceback (most recent call last):
  File "/Users/mac13/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac13/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 415, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac13/QMatSuite/src/quantumvitas/api.py", line 4282, in import_step_from_qe_input
    structure = read_structure(structure_path)
  File "/Users/mac13/QMatSuite/src/quantumvitas/io/structure_io.py", line 46, in read_structure
    filepath = Path(filepath)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1072, in __new__
    self = cls._from_parts(args, init=False)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 697, in _from_parts
    drv, root, parts = self._parse_args(args)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 681, in _parse_args
    a = os.fspath(a)
TypeError: expected str, bytes or os.PathLike object, not NoneType


### 07_Si_bandStructure
- Error: Error creating demo: expected str, bytes or os.PathLike object, not NoneType
Traceback (most recent call last):
  File "/Users/mac13/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac13/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 415, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac13/QMatSuite/src/quantumvitas/api.py", line 4282, in import_step_from_qe_input
    structure = read_structure(structure_path)
  File "/Users/mac13/QMatSuite/src/quantumvitas/io/structure_io.py", line 46, in read_structure
    filepath = Path(filepath)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1072, in __new__
    self = cls._from_parts(args, init=False)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 697, in _from_parts
    drv, root, parts = self._parse_args(args)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 681, in _parse_args
    a = os.fspath(a)
TypeError: expected str, bytes or os.PathLike object, not NoneType


### 08_Fe_DOS
- Error: Error creating demo: expected str, bytes or os.PathLike object, not NoneType
Traceback (most recent call last):
  File "/Users/mac13/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac13/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 415, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac13/QMatSuite/src/quantumvitas/api.py", line 4282, in import_step_from_qe_input
    structure = read_structure(structure_path)
  File "/Users/mac13/QMatSuite/src/quantumvitas/io/structure_io.py", line 46, in read_structure
    filepath = Path(filepath)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1072, in __new__
    self = cls._from_parts(args, init=False)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 697, in _from_parts
    drv, root, parts = self._parse_args(args)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 681, in _parse_args
    a = os.fspath(a)
TypeError: expected str, bytes or os.PathLike object, not NoneType


### 09_Si_phonon
- Error: Error creating demo: expected str, bytes or os.PathLike object, not NoneType
Traceback (most recent call last):
  File "/Users/mac13/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac13/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 415, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac13/QMatSuite/src/quantumvitas/api.py", line 4282, in import_step_from_qe_input
    structure = read_structure(structure_path)
  File "/Users/mac13/QMatSuite/src/quantumvitas/io/structure_io.py", line 46, in read_structure
    filepath = Path(filepath)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1072, in __new__
    self = cls._from_parts(args, init=False)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 697, in _from_parts
    drv, root, parts = self._parse_args(args)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 681, in _parse_args
    a = os.fspath(a)
TypeError: expected str, bytes or os.PathLike object, not NoneType


### 09_Si_phonon
- Error: Error creating demo: expected str, bytes or os.PathLike object, not NoneType
Traceback (most recent call last):
  File "/Users/mac13/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac13/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 415, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac13/QMatSuite/src/quantumvitas/api.py", line 4282, in import_step_from_qe_input
    structure = read_structure(structure_path)
  File "/Users/mac13/QMatSuite/src/quantumvitas/io/structure_io.py", line 46, in read_structure
    filepath = Path(filepath)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1072, in __new__
    self = cls._from_parts(args, init=False)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 697, in _from_parts
    drv, root, parts = self._parse_args(args)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 681, in _parse_args
    a = os.fspath(a)
TypeError: expected str, bytes or os.PathLike object, not NoneType


### 09_Si_phonon
- Error: Error creating demo: expected str, bytes or os.PathLike object, not NoneType
Traceback (most recent call last):
  File "/Users/mac13/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac13/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 415, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac13/QMatSuite/src/quantumvitas/api.py", line 4282, in import_step_from_qe_input
    structure = read_structure(structure_path)
  File "/Users/mac13/QMatSuite/src/quantumvitas/io/structure_io.py", line 46, in read_structure
    filepath = Path(filepath)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1072, in __new__
    self = cls._from_parts(args, init=False)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 697, in _from_parts
    drv, root, parts = self._parse_args(args)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 681, in _parse_args
    a = os.fspath(a)
TypeError: expected str, bytes or os.PathLike object, not NoneType


