#!/bin/bash
LMP=/opt/homebrew/opt/lammps/bin/lmp_serial
cd <HOME>/QMatSuite/tests/data/lammps/fixtures

# Generate dump with absolute path
cat > /tmp/dump_test.in << 'IN'
units lj
atom_style atomic
dimension 3
boundary p p p
lattice fcc 0.8442
region box block 0 4 0 4 0 4
create_box 1 box
create_atoms 1 box
mass 1 1.0
pair_style lj/cut 2.5
pair_coeff 1 1 1.0 1.0 2.5
neighbor 0.3 bin
neigh_modify delay 0 every 1 check yes
thermo 10
dump traj all custom 10 <HOME>/QMatSuite/tests/data/lammps/fixtures/dump_minimize.lammpstrj id type x y z vx vy vz fx fy fz
dump_modify traj sort id
minimize 1.0e-6 1.0e-8 50 500
write_data <HOME>/QMatSuite/tests/data/lammps/fixtures/final_minimize.data
IN
$LMP -in /tmp/dump_test.in -screen none && echo "✓ Generated dump_minimize.lammpstrj"

# Generate MD dump
cat > /tmp/dump_md_test.in << 'IN2'
units metal
atom_style atomic
dimension 3
boundary p p p
lattice fcc 3.6
region box block 0 4 0 4 0 4
create_box 1 box
create_atoms 1 box
mass 1 63.546
pair_style lj/cut 5.0
pair_coeff 1 1 0.2 2.4 5.0
neighbor 2.0 bin
neigh_modify delay 0 every 1 check yes
velocity all create 300.0 12345 mom yes rot yes
fix nvt all nvt temp 300.0 300.0 0.1
thermo 10
dump traj all custom 10 <HOME>/QMatSuite/tests/data/lammps/fixtures/dump_md.lammpstrj id type x y z vx vy vz fx fy fz
dump_modify traj sort id
timestep 0.001
run 100
IN2
$LMP -in /tmp/dump_md_test.in -screen none && echo "✓ Generated dump_md.lammpstrj"
