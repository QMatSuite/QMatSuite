# Task 06: Fe Magnetic Moment — WORKLOG

## Task
Calculate the magnetic moment of BCC iron using Quantum ESPRESSO. BCC Fe is a ferromagnetic metal.

## Steps

### Step 1: Ping MCP server
- Tool: `ping`
- Result: version 0.1.0, status ok

### Step 2: Initialize project + Search demos + List structures
- Loaded existing project at `<REPO_ROOT>`
- No QE Fe magnetic demos found
- Only Si structure available — need to import BCC Fe

### Step 3: Check workflows and presets
- QE SCF workflow available
- Presets: magnetism=COL (collinear LSDA), occupations=SMEARING_GAUSSIAN (metal), precision=MED
- Decision: use SCF workflow with COL + SMEARING_GAUSSIAN + MED presets

### Step 4: Import BCC Fe structure
- Using primitive BCC cell (1 atom), a=2.87 Å
- POSCAR format with primitive lattice vectors
- Result: structure_ulid=01KJ0C9E7FXDAPKGZRCDKNY3CW, space_group=Im-3m ✓

### Step 5: Create SCF calculation
- calc_ulid=01KJ0C9P58MJ6Q91G1F6YWTV95, name=Fe_BCC_magnetic_scf

### Step 6: Apply presets
- magnetism=COL (nspin=2, collinear LSDA)
- occupations_scheme=SMEARING_GAUSSIAN (Gaussian smearing, degauss=0.02)
- precision=MED (ecutwfc=50, ecutrho=400, K_POINTS 16x16x16)

### Step 7: Set starting magnetization
- starting_magnetization(1)=0.7 to initialize ferromagnetic state

### Step 8: Auto-resolve pseudopotential
- Library: SSSP efficiency
- Fe → Fe.pbe-spn-kjpaw_psl.0.2.1.UPF (PAW+spin, PBE)

### Step 9: Dry-run inspection
- Input file looks correct: nspin=2, smearing, dense k-mesh, starting_mag
- Ready to run

### Step 10: Run calculation

