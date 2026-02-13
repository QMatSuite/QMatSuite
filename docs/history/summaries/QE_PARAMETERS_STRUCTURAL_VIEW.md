# QE Module Parameters JSON - Structural View

- **Schema version**: 2
- **Generated at**: 2025-12-11T07:32:46.048448+00:00
- **Doc pattern**: `https://www.quantum-espresso.org/Doc/INPUT_{name}.html`

- **Total modules**: 1


---

## Module: PW

- **Doc URL**: https://www.quantum-espresso.org/Doc/INPUT_PW.html
- **Total parameters**: 289

- **Sections**: 16

#### Section: `&CONTROL`
**Parameters**: 31

**Regular parameters**: 31

- `calculation`
- `title`
- `verbosity`
- `restart_mode`
- `wf_collect`
- `nstep`
- `iprint`
- `tstress`
- `tprnfor`
- `dt`
- ... and 21 more

**Sample parameters (detailed)**:

##### `calculation`

- **name**: `calculation`
- **type**: `CHARACTER`
- **default**: `'scf'`
- **enum**: 7 values (first 5: `'scf'`, `'nscf'`, `'bands'`, `'relax'`, `'md'`...)
- **description**: 


A string describing the task to be performed. Options are:
            




'scf'



            






'nscf'



            






'bands'



            






'relax'



            






'md'...

##### `title`

- **name**: `title`
- **type**: `CHARACTER`
- **default**: `' '`
- **description**: 
reprinted on output.
         

##### `verbosity`

- **name**: `verbosity`
- **type**: `CHARACTER`
- **default**: `'low'`
- **enum**: `'high'`, `'low'`
- **description**: 


Currently two verbosity levels are implemented:
            




'high'



            






'low'



            






'debug'
 and 
'medium'
 have the same effect as 
'high';


'default'
 and 
...


#### Section: `&SYSTEM`
**Parameters**: 106

**Array parameters (with indexing)**: 9

- `celldm` (bounded, end=6)
- `starting_charge` (unbounded, end=None)
- `starting_magnetization` (unbounded, end=None)
- `Hubbard_beta` (unbounded, end=None)
- `angle1` (unbounded, end=None)
- `angle2` (unbounded, end=None)
- `fixed_magnetization` (bounded, end=3)
- `london_c6` (unbounded, end=None)
- `london_rvdw` (unbounded, end=None)

**Regular parameters**: 97

- `ibrav`
- `cosAB`
- `cosAC`
- `cosBC`
- `nat`
- `ntyp`
- `nbnd`
- `nbnd_cond`
- `tot_charge`
- `tot_magnetization`
- ... and 87 more

**Sample parameters (detailed)**:

##### `ibrav`

- **name**: `ibrav`
- **type**: `INTEGER`
- **default**: `REQUIRED`
- **enum**: 21 values (first 5: `0`, `1`, `2`, `3`, `-3`...)
- **description**: 
  Bravais-lattice index. Optional only if space_group is set.
  If ibrav /= 0, specify EITHER [ 
celldm
(1)-
celldm
(6) ]
  OR [ 
A
, 
B
, 
C
, 
cosAB
, 
cosAC
, 
cosBC
 ]
  but NOT both. The lattice...

##### `celldm`

- **name**: `celldm`
- **type**: `REAL`
- **default**: `ibrav`
- **indexing**:
  - kind: `bounded`
  - index_name: `i`
  - start: `1`
  - end: `6`
  - keyword_pattern: `celldm({i})`
- **description**: 
Crystallographic constants - see the 
ibrav
 variable.
Specify either these OR 
A
,
B
,
C
,
cosAB
,
cosBC
,
cosAC
 NOT both.
Only needed values (depending on "ibrav") must be specified
alat = 
celldm...

##### `cosAB`

- **name**: `cosAB`
- **type**: `REAL`
- **default**: `ibrav`
- **description**: 
Traditional crystallographic constants:

  a,b,c in ANGSTROM
  cosAB = cosine of the angle between axis a and b (gamma)
  cosAC = cosine of the angle between axis a and c (beta)
  cosBC = cosine of t...


#### Section: `&ELECTRONS`
**Parameters**: 26

**Array parameters (with indexing)**: 1

- `efield_cart` (bounded, end=3)

**Regular parameters**: 25

- `electron_maxstep`
- `exx_maxstep`
- `scf_must_converge`
- `conv_thr`
- `adaptive_thr`
- `conv_thr_init`
- `conv_thr_multi`
- `mixing_mode`
- `mixing_beta`
- `mixing_ndim`
- ... and 15 more

**Sample parameters (detailed)**:

##### `electron_maxstep`

- **name**: `electron_maxstep`
- **type**: `INTEGER`
- **default**: `100`
- **description**: 
maximum number of iterations in a scf step. If exact exchange is active,
this will affect the inner loops.
         

##### `exx_maxstep`

- **name**: `exx_maxstep`
- **type**: `INTEGER`
- **default**: `100`
- **description**: 
maximum number of outer iterations in a scf calculation with exact exchange.
         

##### `scf_must_converge`

- **name**: `scf_must_converge`
- **type**: `LOGICAL`
- **default**: `.TRUE.`
- **description**: 
If .false. do not stop molecular dynamics or ionic relaxation
when electron_maxstep is reached. Use with care.
         


#### Section: `&IONS`
**Parameters**: 32

**Array parameters (with indexing)**: 2

- `nhgrp` (unbounded, end=None)
- `fnhscl` (unbounded, end=None)

**Regular parameters**: 30

- `ion_positions`
- `ion_velocities`
- `ion_dynamics`
- `pot_extrapolation`
- `wfc_extrapolation`
- `remove_rigid_rot`
- `ion_temperature`
- `tempw`
- `fnosep`
- `nhpcl`
- ... and 20 more

**Sample parameters (detailed)**:

##### `ion_positions`

- **name**: `ion_positions`
- **type**: `CHARACTER`
- **default**: `'default'`
- **enum**: `'default'`, `'from_input'`
- **description**: 

 Available options are:
            




'default'
 :



if restarting, use atomic positions read from the
restart file; in all other cases, use atomic
positions from standard input.
            


...

##### `ion_velocities`

- **name**: `ion_velocities`
- **type**: `CHARACTER`
- **default**: `'default'`
- **enum**: `'default'`, `'from_input'`
- **description**: 


Initial ionic velocities. Available options are:
            




'default'
 :



start a new simulation from random thermalized
distribution of velocities if 
tempw
 is set,
with zero velocities o...

##### `ion_dynamics`

- **name**: `ion_dynamics`
- **type**: `CHARACTER`
- **enum**: 8 values (first 5: `'bfgs'`, `'damp'`, `'fire'`, `'verlet'`, `'velocity-verlet'`...)
- **description**: 


Specify the type of ionic dynamics.

For different type of calculation different possibilities are
allowed and different default values apply:


CASE
 ( 
calculation
 == 'relax' )
            




...


#### Section: `&CELL`
**Parameters**: 6

**Regular parameters**: 6

- `cell_dynamics`
- `press`
- `wmass`
- `cell_factor`
- `press_conv_thr`
- `cell_dofree`

**Sample parameters (detailed)**:

##### `cell_dynamics`

- **name**: `cell_dynamics`
- **type**: `CHARACTER`
- **enum**: 7 values (first 5: `'none'`, `'sd'`, `'damp-pr'`, `'damp-w'`, `'bfgs'`...)
- **description**: 


Specify the type of dynamics for the cell.
For different type of calculation different possibilities
are allowed and different default values apply:


CASE
 ( 
calculation
 == 'vc-relax' )
        ...

##### `press`

- **name**: `press`
- **type**: `REAL`
- **default**: `0.D0`
- **description**: 
Target pressure [KBar] in a variable-cell md or relaxation run.
         

##### `wmass`

- **name**: `wmass`
- **type**: `REAL`
- **default**: `0.75*Tot_Mass/pi**2 for Parrinello-Rahman MD;
0.75*Tot_Mass/pi**2/Omega**(2/3) for Wentzcovitch MD`
- **description**: 
Fictitious cell mass [amu] for variable-cell simulations
(both 'vc-md' and 'vc-relax')
         


#### Section: `&FCP`
**Parameters**: 12

**Regular parameters**: 12

- `fcp_mu`
- `fcp_dynamics`
- `fcp_conv_thr`
- `fcp_ndiis`
- `fcp_mass`
- `fcp_velocity`
- `fcp_temperature`
- `fcp_tempw`
- `fcp_tolp`
- `fcp_delta_t`
- ... and 2 more

**Sample parameters (detailed)**:

##### `fcp_mu`

- **name**: `fcp_mu`
- **type**: `REAL`
- **default**: `REQUIRED`
- **description**: 
The target Fermi energy (eV). One can start
with appropriate total charge of the system by giving 
tot_charge
 .
         

##### `fcp_dynamics`

- **name**: `fcp_dynamics`
- **type**: `CHARACTER`
- **enum**: 6 values (first 5: `'bfgs'`, `'newton'`, `'damp'`, `'lm'`, `'velocity-verlet'`...)
- **description**: 


Specify the type of dynamics for the Fictitious Charge Particle (FCP).

For different type of calculation different possibilities
are allowed and different default values apply:


CASE
 ( 
calculat...

##### `fcp_conv_thr`

- **name**: `fcp_conv_thr`
- **type**: `REAL`
- **default**: `1.D-2`
- **description**: 
Convergence threshold on force (eV) for FCP relaxation.
         


#### Section: `&RISM`
**Parameters**: 39

**Array parameters (with indexing)**: 3

- `solute_lj` (unbounded, end=None)
- `solute_epsilon` (unbounded, end=None)
- `solute_sigma` (unbounded, end=None)

**Regular parameters**: 36

- `nsolv`
- `closure`
- `tempv`
- `ecutsolv`
- `starting1d`
- `starting3d`
- `smear1d`
- `smear3d`
- `rism1d_maxstep`
- `rism3d_maxstep`
- ... and 26 more

**Sample parameters (detailed)**:

##### `nsolv`

- **name**: `nsolv`
- **type**: `INTEGER`
- **default**: `REQUIRED`
- **description**: 
The number of solvents (i.e. molecular species) in the unit cell
         

##### `closure`

- **name**: `closure`
- **type**: `CHARACTER`
- **default**: `'kh'`
- **enum**: `'kh'`, `'hnc'`
- **description**: 


Specify the type of closure equation:
            




'kh'
 :



The Kovalenko and Hirata's model.
[A.Kovalenko, F.Hirata, JCP 110, 10095 (1999), 
doi:10.1063/1.478883
]
            






'hnc'
 ...

##### `tempv`

- **name**: `tempv`
- **type**: `REAL`
- **default**: `300.D0`
- **description**: 
Temperature (Kelvin) of solvents.
         


#### Section: `ATOMIC_SPECIES`
**Parameters**: 2

**Regular parameters**: 2

- `Mass_X`
- `PseudoPot_X`

**Sample parameters (detailed)**:

##### `Mass_X`

- **name**: `Mass_X`
- **type**: `REAL`
- **description**: 
mass of the atomic species [amu: mass of C = 12]
Used only when performing Molecular Dynamics run
or structural optimization runs using Damped MD.
Not actually used in all other cases (but stored
in ...

##### `PseudoPot_X`

- **name**: `PseudoPot_X`
- **type**: `CHARACTER`
- **description**: 
File containing PP for this species.

The pseudopotential file is assumed to be in the new UPF format.
If it doesn't work, the pseudopotential format is determined by
the file name:

*.vdb or *.van  ...


#### Section: `K_POINTS`
**Parameters**: 11

**Regular parameters**: 11

- `nks`
- `xk_x`
- `xk_y`
- `xk_z`
- `wk`
- `nk1`
- `nk2`
- `nk3`
- `sk1`
- `sk2`
- ... and 1 more

**Sample parameters (detailed)**:

##### `nks`

- **name**: `nks`
- **type**: `INTEGER`
- **description**:  Number of supplied special k-points.
                     

##### `xk_x`

- **name**: `xk_x`
- **type**: `REAL`
- **description**: 
Special k-points (xk_x/y/z) in the irreducible Brillouin Zone
(IBZ) of the lattice (with all symmetries) and weights (wk)
See the literature for lists of special points and
the corresponding weights....

##### `xk_y`

- **name**: `xk_y`
- **type**: `REAL`
- **description**: 
Special k-points (xk_x/y/z) in the irreducible Brillouin Zone
(IBZ) of the lattice (with all symmetries) and weights (wk)
See the literature for lists of special points and
the corresponding weights....


#### Section: `ADDITIONAL_K_POINTS`
**Parameters**: 5

**Regular parameters**: 5

- `nks_add`
- `k_x`
- `k_y`
- `k_z`
- `wk_`

**Sample parameters (detailed)**:

##### `nks_add`

- **name**: `nks_add`
- **type**: `INTEGER`
- **description**:  Number of supplied "additional" k-points.
               

##### `k_x`

- **name**: `k_x`
- **type**: `REAL`
- **description**: 
for the respective explanation, see the 
xk_x
, 
xk_y
, 
xk_z
, 
wk

                  

##### `k_y`

- **name**: `k_y`
- **type**: `REAL`
- **description**: 
for the respective explanation, see the 
xk_x
, 
xk_y
, 
xk_z
, 
wk

                  


#### Section: `CELL_PARAMETERS`
**Parameters**: 3

**Regular parameters**: 3

- `v1`
- `v2`
- `v3`

**Sample parameters (detailed)**:

##### `v1`

- **name**: `v1`
- **type**: `REAL`
- **description**: 
Crystal lattice vectors (in cartesian axis):
    v1(1)  v1(2)  v1(3)    ... 1st lattice vector
    v2(1)  v2(2)  v2(3)    ... 2nd lattice vector
    v3(1)  v3(2)  v3(3)    ... 3rd lattice vector
    ...

##### `v2`

- **name**: `v2`
- **type**: `REAL`
- **description**: 
Crystal lattice vectors (in cartesian axis):
    v1(1)  v1(2)  v1(3)    ... 1st lattice vector
    v2(1)  v2(2)  v2(3)    ... 2nd lattice vector
    v3(1)  v3(2)  v3(3)    ... 3rd lattice vector
    ...

##### `v3`

- **name**: `v3`
- **type**: `REAL`
- **description**: 
Crystal lattice vectors (in cartesian axis):
    v1(1)  v1(2)  v1(3)    ... 1st lattice vector
    v2(1)  v2(2)  v2(3)    ... 2nd lattice vector
    v3(1)  v3(2)  v3(3)    ... 3rd lattice vector
    ...


#### Section: `CONSTRAINTS`
**Parameters**: 4

**Regular parameters**: 4

- `nconstr`
- `constr_tol`
- `constr_type`
- `constr_target`

**Sample parameters (detailed)**:

##### `nconstr`

- **name**: `nconstr`
- **type**: `INTEGER`
- **description**:  Number of constraints.
               

##### `constr_tol`

- **name**: `constr_tol`
- **type**: `REAL`
- **description**:  Tolerance for keeping the constraints satisfied.
                  

##### `constr_type`

- **name**: `constr_type`
- **type**: `CHARACTER`
- **enum**: 7 values (first 5: `'type_coord'`, `'atom_coord'`, `'distance'`, `'planar_angle'`, `'torsional_angle'`...)
- **description**: 


Type of constraint :
                     




'type_coord'
 :



constraint on global coordination-number, i.e. the
average number of atoms of type B surrounding the
atoms of type A. The coordinat...


#### Section: `OCCUPATIONS`
**Parameters**: 2

**Regular parameters**: 2

- `f_inp1`
- `f_inp2`

**Sample parameters (detailed)**:

##### `f_inp1`

- **name**: `f_inp1`
- **type**: `REAL`
- **description**: 
Occupations of individual states (MAX 10 PER ROW).
For spin-polarized calculations, these are majority spin states.
                  

##### `f_inp2`

- **name**: `f_inp2`
- **type**: `REAL`
- **description**: 
Occupations of minority spin states (MAX 10 PER ROW)
To be specified only for spin-polarized calculations.
                     


#### Section: `ATOMIC_VELOCITIES`
**Parameters**: 3

**Regular parameters**: 3

- `vx`
- `vy`
- `vz`

**Sample parameters (detailed)**:

##### `vx`

- **name**: `vx`
- **type**: `REAL`
- **description**:  atomic velocities along x y and z direction
                  

##### `vy`

- **name**: `vy`
- **type**: `REAL`
- **description**:  atomic velocities along x y and z direction
                  

##### `vz`

- **name**: `vz`
- **type**: `REAL`
- **description**:  atomic velocities along x y and z direction
                  


#### Section: `ATOMIC_FORCES`
**Parameters**: 3

**Regular parameters**: 3

- `fx`
- `fy`
- `fz`

**Sample parameters (detailed)**:

##### `fx`

- **name**: `fx`
- **type**: `REAL`
- **description**: 
external force on atom X (cartesian components, Ry/a.u. units)
                  

##### `fy`

- **name**: `fy`
- **type**: `REAL`
- **description**: 
external force on atom X (cartesian components, Ry/a.u. units)
                  

##### `fz`

- **name**: `fz`
- **type**: `REAL`
- **description**: 
external force on atom X (cartesian components, Ry/a.u. units)
                  


#### Section: `SOLVENTS`
**Parameters**: 4

**Regular parameters**: 4

- `Density`
- `Molecule`
- `Density_Left`
- `Density_Right`

**Sample parameters (detailed)**:

##### `Density`

- **name**: `Density`
- **type**: `REAL`
- **description**: 
density of the solvent molecule.
if not positive value is set, density is read from MOL-file.
                        

##### `Molecule`

- **name**: `Molecule`
- **type**: `CHARACTER`
- **description**: 
MOL-file of the solvent molecule.
in the MOL-file, molecular structure and some other data are written.
                        

##### `Density_Left`

- **name**: `Density_Left`
- **type**: `REAL`
- **description**: 
density of the solvent molecule in the left-hand side.
if not positive value is set, density is read from MOL-file.
                        


**Card metadata**: 5 cards

- `K_POINTS`: CHARACTER
  - Options: 8 values
- `ADDITIONAL_K_POINTS`: CHARACTER
  - Options: 6 values
- `CELL_PARAMETERS`: CHARACTER
  - Options: `alat`, `bohr`, `angstrom`
- `ATOMIC_VELOCITIES`: CHARACTER
  - Options: `a.u`
- `SOLVENTS`: CHARACTER
  - Options: `1/cell`, `mol/L`, `g/cm^3`


---

## Summary

- **Total parameters across all modules**: 289
- **Parameters with indexing metadata**: 15
  - Bounded arrays: 3
  - Unbounded arrays: 12
- **Parameters without indexing**: 274
