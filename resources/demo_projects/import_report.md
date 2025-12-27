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
- Error: Error creating demo: CELL_PARAMETERS card required when ibrav == 0.
Traceback (most recent call last):
  File "/Users/mac11/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 260, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/api.py", line 4254, in import_step_from_qe_input
    import_result = build_step_spec_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/importers.py", line 138, in build_step_spec_from_qe_input
    structure = structure_from_qe_input(qe_input)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 221, in structure_from_qe_input
    lattice = _lattice_from_cell_card(cell_card, system)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 307, in _lattice_from_cell_card
    raise ValueError("CELL_PARAMETERS card required when ibrav == 0.")
ValueError: CELL_PARAMETERS card required when ibrav == 0.


### 12_NMR_gipaw
- Error: Error creating demo: CELL_PARAMETERS card required when ibrav == 0.
Traceback (most recent call last):
  File "/Users/mac11/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 260, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/api.py", line 4254, in import_step_from_qe_input
    import_result = build_step_spec_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/importers.py", line 138, in build_step_spec_from_qe_input
    structure = structure_from_qe_input(qe_input)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 221, in structure_from_qe_input
    lattice = _lattice_from_cell_card(cell_card, system)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 307, in _lattice_from_cell_card
    raise ValueError("CELL_PARAMETERS card required when ibrav == 0.")
ValueError: CELL_PARAMETERS card required when ibrav == 0.


### 12_NMR_gipaw
- Error: Error creating demo: CELL_PARAMETERS card required when ibrav == 0.
Traceback (most recent call last):
  File "/Users/mac11/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 260, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/api.py", line 4254, in import_step_from_qe_input
    import_result = build_step_spec_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/importers.py", line 138, in build_step_spec_from_qe_input
    structure = structure_from_qe_input(qe_input)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 221, in structure_from_qe_input
    lattice = _lattice_from_cell_card(cell_card, system)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 307, in _lattice_from_cell_card
    raise ValueError("CELL_PARAMETERS card required when ibrav == 0.")
ValueError: CELL_PARAMETERS card required when ibrav == 0.


### 13_graphene
- Error: Error creating demo: ibrav=12/-12 requires b, c, and cos(angle).
Traceback (most recent call last):
  File "/Users/mac11/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 260, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/api.py", line 4254, in import_step_from_qe_input
    import_result = build_step_spec_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/importers.py", line 138, in build_step_spec_from_qe_input
    structure = structure_from_qe_input(qe_input)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 219, in structure_from_qe_input
    lattice = _lattice_from_ibrav(system)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 336, in _lattice_from_ibrav
    vectors = _ibrav_vectors(ibrav, params)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 455, in _ibrav_vectors
    raise ValueError("ibrav=12/-12 requires b, c, and cos(angle).")
ValueError: ibrav=12/-12 requires b, c, and cos(angle).


### 14_DFT_plus_U_NiO
- Error: Missing pseudopotentials (could not download): ni_pbe_v1.4.uspp.F.UPF
- Missing pseudopotentials: ni_pbe_v1.4.uspp.F.UPF

### 14_DFT_plus_U_NiO
- Error: Missing pseudopotentials (could not download): ni_pbe_v1.4.uspp.F.UPF
- Missing pseudopotentials: ni_pbe_v1.4.uspp.F.UPF

### 17_H2O_vibration
- Error: Error creating demo: CELL_PARAMETERS card required when ibrav == 0.
Traceback (most recent call last):
  File "/Users/mac11/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 260, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/api.py", line 4254, in import_step_from_qe_input
    import_result = build_step_spec_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/importers.py", line 138, in build_step_spec_from_qe_input
    structure = structure_from_qe_input(qe_input)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 221, in structure_from_qe_input
    lattice = _lattice_from_cell_card(cell_card, system)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 307, in _lattice_from_cell_card
    raise ValueError("CELL_PARAMETERS card required when ibrav == 0.")
ValueError: CELL_PARAMETERS card required when ibrav == 0.


### 19_Si_CPMD
- Error: Error creating demo: CELL_PARAMETERS card required when ibrav == 0.
Traceback (most recent call last):
  File "/Users/mac11/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 260, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/api.py", line 4254, in import_step_from_qe_input
    import_result = build_step_spec_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/importers.py", line 138, in build_step_spec_from_qe_input
    structure = structure_from_qe_input(qe_input)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 221, in structure_from_qe_input
    lattice = _lattice_from_cell_card(cell_card, system)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 307, in _lattice_from_cell_card
    raise ValueError("CELL_PARAMETERS card required when ibrav == 0.")
ValueError: CELL_PARAMETERS card required when ibrav == 0.


### 04_Si_DOS
- Error: Error creating demo: CELL_PARAMETERS card required when ibrav == 0.
Traceback (most recent call last):
  File "/Users/mac11/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 260, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/api.py", line 4254, in import_step_from_qe_input
    import_result = build_step_spec_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/importers.py", line 138, in build_step_spec_from_qe_input
    structure = structure_from_qe_input(qe_input)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 221, in structure_from_qe_input
    lattice = _lattice_from_cell_card(cell_card, system)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 307, in _lattice_from_cell_card
    raise ValueError("CELL_PARAMETERS card required when ibrav == 0.")
ValueError: CELL_PARAMETERS card required when ibrav == 0.


### 05_NH3_inversion
- Error: Missing pseudopotentials (could not download): N.oncvpsp.upf
- Missing pseudopotentials: N.oncvpsp.upf

### 06_Al_DOS
- Error: Error creating demo: CELL_PARAMETERS card required when ibrav == 0.
Traceback (most recent call last):
  File "/Users/mac11/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 260, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/api.py", line 4254, in import_step_from_qe_input
    import_result = build_step_spec_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/importers.py", line 138, in build_step_spec_from_qe_input
    structure = structure_from_qe_input(qe_input)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 221, in structure_from_qe_input
    lattice = _lattice_from_cell_card(cell_card, system)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 307, in _lattice_from_cell_card
    raise ValueError("CELL_PARAMETERS card required when ibrav == 0.")
ValueError: CELL_PARAMETERS card required when ibrav == 0.


### 07_Si_bandStructure
- Error: Error creating demo: CELL_PARAMETERS card required when ibrav == 0.
Traceback (most recent call last):
  File "/Users/mac11/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 260, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/api.py", line 4254, in import_step_from_qe_input
    import_result = build_step_spec_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/importers.py", line 138, in build_step_spec_from_qe_input
    structure = structure_from_qe_input(qe_input)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 221, in structure_from_qe_input
    lattice = _lattice_from_cell_card(cell_card, system)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 307, in _lattice_from_cell_card
    raise ValueError("CELL_PARAMETERS card required when ibrav == 0.")
ValueError: CELL_PARAMETERS card required when ibrav == 0.


### 08_Fe_DOS
- Error: Error creating demo: CELL_PARAMETERS card required when ibrav == 0.
Traceback (most recent call last):
  File "/Users/mac11/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 260, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/api.py", line 4254, in import_step_from_qe_input
    import_result = build_step_spec_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/importers.py", line 138, in build_step_spec_from_qe_input
    structure = structure_from_qe_input(qe_input)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 221, in structure_from_qe_input
    lattice = _lattice_from_cell_card(cell_card, system)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 307, in _lattice_from_cell_card
    raise ValueError("CELL_PARAMETERS card required when ibrav == 0.")
ValueError: CELL_PARAMETERS card required when ibrav == 0.


### 09_Si_phonon
- Error: Error creating demo: CELL_PARAMETERS card required when ibrav == 0.
Traceback (most recent call last):
  File "/Users/mac11/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 260, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/api.py", line 4254, in import_step_from_qe_input
    import_result = build_step_spec_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/importers.py", line 138, in build_step_spec_from_qe_input
    structure = structure_from_qe_input(qe_input)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 221, in structure_from_qe_input
    lattice = _lattice_from_cell_card(cell_card, system)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 307, in _lattice_from_cell_card
    raise ValueError("CELL_PARAMETERS card required when ibrav == 0.")
ValueError: CELL_PARAMETERS card required when ibrav == 0.


### 09_Si_phonon
- Error: Error creating demo: CELL_PARAMETERS card required when ibrav == 0.
Traceback (most recent call last):
  File "/Users/mac11/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 260, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/api.py", line 4254, in import_step_from_qe_input
    import_result = build_step_spec_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/importers.py", line 138, in build_step_spec_from_qe_input
    structure = structure_from_qe_input(qe_input)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 221, in structure_from_qe_input
    lattice = _lattice_from_cell_card(cell_card, system)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 307, in _lattice_from_cell_card
    raise ValueError("CELL_PARAMETERS card required when ibrav == 0.")
ValueError: CELL_PARAMETERS card required when ibrav == 0.


### 09_Si_phonon
- Error: Error creating demo: CELL_PARAMETERS card required when ibrav == 0.
Traceback (most recent call last):
  File "/Users/mac11/QMatSuite/tools/import_tutorial_datasets.py", line 1251, in create_demo_from_dataset
    snapshot = materialize_project_from_qe_input_folder(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/folder_import.py", line 260, in materialize_project_from_qe_input_folder
    service.import_step_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/api.py", line 4254, in import_step_from_qe_input
    import_result = build_step_spec_from_qe_input(
  File "/Users/mac11/QMatSuite/src/quantumvitas/calculation/importers.py", line 138, in build_step_spec_from_qe_input
    structure = structure_from_qe_input(qe_input)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 221, in structure_from_qe_input
    lattice = _lattice_from_cell_card(cell_card, system)
  File "/Users/mac11/QMatSuite/src/quantumvitas/io/structure_io.py", line 307, in _lattice_from_cell_card
    raise ValueError("CELL_PARAMETERS card required when ibrav == 0.")
ValueError: CELL_PARAMETERS card required when ibrav == 0.


