# Abinit Compilation Worklog (macOS arm64)

> **DO NOT DELETE**: This file contains the reproducible compilation recipe for ABINIT on macOS arm64.
> It documents all compilation issues encountered and their solutions.

**Date**: 2026-02-04
**System**: macOS 26.2, Darwin 25.2.0, arm64 (Apple Silicon)
**Target**: Build abinit from source, install to ~/.qmatsuite/engines/abinit/10.4.7/

---

## Phase 1: Reconnaissance

### System inventory

- gfortran: GNU Fortran 15.2.0 (Homebrew GCC 15.2.0)
- mpirun: Open MPI 5.0.8 (Homebrew)
- cmake: available, ninja: available, make: available
- Brew libs: fftw, openblas, scalapack, hdf5 (2.0.0), libxc, netcdf, netcdf-fortran
- Conda MPI wrappers (mpicc, mpifort): BROKEN — looking for cross-compiled gfortran
  `arm64-apple-darwin20.0.0-gfortran` that does not exist
- Homebrew MPI wrappers: WORK — /opt/homebrew/bin/mpifort uses gfortran 15.2.0

### Step 1.1: Find latest abinit version

- Checked GitHub releases: https://github.com/abinit/abinit/releases
- Latest: **v10.4.7** (September 6, 2024)
- Release notes page says v10.4 released May 15, 2025
- Download URL: https://forge.abinit.org/abinit-10.4.7.tar.gz (140 MB)

---

## Phase 2: Download & Setup

### Step 2.1: Download source

```bash
BUILD_DIR="$HOME/.qmatsuite/engines/_build/abinit"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"
curl -L -o abinit-10.4.7.tar.gz "https://forge.abinit.org/abinit-10.4.7.tar.gz"
tar xzf abinit-10.4.7.tar.gz
```

Result: 140 MB tarball, extracted to abinit-10.4.7/

### Step 2.2: Install missing brew deps

```bash
brew install netcdf netcdf-fortran
```

Both installed successfully from bottles (netcdf 4.9.3, netcdf-fortran 4.6.2).

---

## Phase 3: Configure

### Step 3.1: First configure attempt (FAILED)

Config file: `homebrew_arm64.ac9` with `with_linalg_flavor="openblas+scalapack"`

**Error**: `configure: error: invalid linear algebra flavor: 'scalapack'`

**Reason**: Valid flavors are `auto acml aocl asl atlas easybuild elpa essl magma mkl netlib none openblas plasma`. The `+scalapack` suffix is only added by auto-detection, not valid as user input.

**Fix**: Changed to `with_linalg_flavor="openblas"`, keep scalapack in LINALG_LIBS.

### Step 3.2: Second configure attempt (FAILED)

**Error**: HDF5 C interface test fails with:
```
clang: error: no such file or directory: 'Threads::Threads'
```

**Reason**: Homebrew HDF5 2.0.0's `libhdf5.settings` file contains
`Extra libraries: m;dl;Threads::Threads` — a CMake generator expression that is
meaningless outside CMake. The abinit configure script reads this settings file
and injects the raw string into the link command.

**Thought**: When using `with_hdf5="/opt/homebrew/opt/hdf5"` (dir init), the script
reads libhdf5.settings. Must use `env` init method to bypass this.

### Step 3.3: Third configure attempt (SUCCESS)

Changed HDF5 config to pure env-based:
```
with_hdf5="yes"
HDF5_CPPFLAGS="-I/opt/homebrew/opt/hdf5/include"
HDF5_FCFLAGS="-I/opt/homebrew/opt/hdf5/include"
HDF5_LIBS="-L/opt/homebrew/opt/hdf5/lib -lhdf5_fortran -lhdf5_hl -lhdf5 -lz"
```

Also applied same env approach to NetCDF:
```
with_netcdf="yes"
with_netcdf_fortran="yes"
NETCDF_CPPFLAGS="-I/opt/homebrew/opt/netcdf/include"
NETCDF_LIBS="-L/opt/homebrew/opt/netcdf/lib -lnetcdf"
NETCDF_FORTRAN_CPPFLAGS="-I/opt/homebrew/opt/netcdf-fortran/include"
NETCDF_FORTRAN_LIBS="-L/opt/homebrew/opt/netcdf-fortran/lib -lnetcdff"
```

**Result**: Configure passes. All features working:
- MPI: yes
- FFTW3: yes
- LibXC: yes
- OpenBLAS: yes (with ScaLAPACK)
- HDF5: yes (C interface, no Fortran HDF5 modules tested in this mode)
- NetCDF: yes
- NetCDF-Fortran: yes

Makefile generated successfully.

---

## Phase 4: Build

### Step 4.1: make -j10 (FAILED — Fortran module race condition)

```bash
cd $HOME/.qmatsuite/engines/_build/abinit/build_10.4.7
make -j10
```

**Error**:
```
Fatal Error: Cannot open module file 'm_dfpt_rhotov.mod' for reading at (1): No such file or directory
make[3]: *** [m_dfpt_scfcv.o] Error 1
```

**Reason**: Fortran parallel build race condition. The `.o` file for `m_dfpt_rhotov` was
compiled, but the `.mod` file hadn't been written yet when `m_dfpt_scfcv` tried to read it.
This is a known issue with Fortran's `USE` module dependency system under heavy parallelism:
gfortran writes `.mod` asynchronously relative to `.o`, and `-j10` can start the dependent
compile before the `.mod` file is flushed to disk.

**Fix**: Deleted the stale `.o`, rebuilt the single file, then continued with `-j4`:

```bash
rm -f src/72_response/m_dfpt_rhotov.o
cd src/72_response && make m_dfpt_rhotov.o
cd ../..
make -j4
```

### Step 4.2: make -j4 (SUCCESS)

Build completed successfully. 23 executables produced in `src/98_main/`:

| Binary | Size | Description |
|--------|------|-------------|
| abinit | 28 MB | Main DFT engine |
| multibinit | 19 MB | Multiscale/lattice dynamics |
| abitk | 13 MB | Abinit toolkit |
| mrgscr | 7.8 MB | Screen file merge |
| anaddb | 8.0 MB | Phonon analysis |
| mrgdv | 6.7 MB | Derivative database merge |
| conducti | 6.6 MB | Conductivity |
| atdep | 6.5 MB | Temperature-dependent properties |
| cut3d | 5.3 MB | 3D density cutting tool |
| optic | 5.2 MB | Optics |
| ioprof | 5.0 MB | IO profiler |
| fold2Bloch | 4.3 MB | Unfolding tool |
| mrgddb | 4.5 MB | DDB file merge |
| mrggkk | 4.3 MB | GKK file merge |
| lapackprof | 3.6 MB | LAPACK profiler |
| fftprof | 3.6 MB | FFT profiler |
| lruj | 3.6 MB | Linear response U/J |
| aim | 2.9 MB | AIM/Bader analysis |
| macroave | 2.7 MB | Macroscopic average |
| vdw_kernelgen | 2.5 MB | vdW kernel generator |
| band2eps | 2.1 MB | Band structure to EPS |
| testtransposer | 0.9 MB | MPI transposer test |
| dummy_tests | 0.4 MB | Dummy tests |

---

## Phase 5: Install

```bash
cd $HOME/.qmatsuite/engines/_build/abinit/build_10.4.7
make install
```

All binaries installed to `~/.qmatsuite/engines/abinit/10.4.7/bin/`.
Verification:

```
$ ~/.qmatsuite/engines/abinit/10.4.7/bin/abinit --version
10.4.7-d
```

---

## Phase 6: Smoke Tests

### Test 1: Single H atom (serial)

Input: `tests/fast/Input/t01.abi` — single hydrogen atom in a 10 Bohr cubic box.

```bash
cd smoke_test
ABI_PSPDIR=$HOME/.qmatsuite/engines/_build/abinit/abinit-10.4.7/tests/Pspdir \
$HOME/.qmatsuite/engines/abinit/10.4.7/bin/abinit t01.abi
```

**Result**: SUCCESS
- Completed in 0.1s
- Total energy: **-4.3477309579E-01 Ha**
- Space group detected: Pm -3 m (#221) — correct for atom in cubic box
- 7 warnings (tolsym), 8 comments — all informational
- Pseudopotential: `PseudosTM_pwteter/1h.pspnc`

### Test 2: Si crystal SCF (serial)

Input: Custom 2-atom diamond Si cell (a=10.26 Bohr, ecut=8 Ha, 2x2x2 k-grid).

```bash
ABI_PSPDIR=$HOME/.qmatsuite/engines/_build/abinit/abinit-10.4.7/tests/Pspdir \
$HOME/.qmatsuite/engines/abinit/10.4.7/bin/abinit si_scf.abi
```

**Result**: SUCCESS
- Completed in 0.2s
- Total energy: **-8.8662947480E+00 Ha**
- Space group: Fd -3 m (#227) — correct for diamond Si
- 0 warnings, 2 comments
- Pseudopotential: `PseudosTM_pwteter/14si.pspnc`

### Test 3: Si crystal SCF (MPI, 2 processes)

Same input as Test 2, run with MPI:

```bash
ABI_PSPDIR=$HOME/.qmatsuite/engines/_build/abinit/abinit-10.4.7/tests/Pspdir \
mpirun -np 2 $HOME/.qmatsuite/engines/abinit/10.4.7/bin/abinit si_scf.abi
```

**Result**: SUCCESS
- Completed in 0.3s
- Total energy: **-8.8662947480E+00 Ha** (matches serial exactly)
- mpi_procs: 2, omp_threads: 1
- 0 warnings, 0 comments

All three smoke tests PASS. Serial and MPI energies match.

---

## Reproducible Compilation Recipe (macOS arm64)

### Prerequisites

```bash
# Install Homebrew dependencies
brew install gcc open-mpi fftw openblas scalapack libxc hdf5 netcdf netcdf-fortran
```

Required versions (tested):
- GCC/gfortran 15.2.0
- Open MPI 5.0.8
- HDF5 2.0.0
- FFTW 3.x
- OpenBLAS (latest)
- ScaLAPACK (latest)
- LibXC (latest)
- NetCDF 4.9.3 + NetCDF-Fortran 4.6.2

**Important**: Use Homebrew MPI wrappers (`/opt/homebrew/bin/mpifort`), NOT Conda ones.
Conda's `mpifort` looks for a cross-compiled gfortran (`arm64-apple-darwin20.0.0-gfortran`)
that does not exist.

### Step 1: Download

```bash
BUILD_DIR="$HOME/.qmatsuite/engines/_build/abinit"
mkdir -p "$BUILD_DIR" && cd "$BUILD_DIR"
curl -L -o abinit-10.4.7.tar.gz "https://forge.abinit.org/abinit-10.4.7.tar.gz"
tar xzf abinit-10.4.7.tar.gz
```

### Step 2: Create config file

```bash
mkdir -p "$BUILD_DIR/build_10.4.7"
cat > "$BUILD_DIR/build_10.4.7/homebrew_arm64.ac9" << 'ACEOF'
# Abinit 10.4.7 build configuration for macOS arm64 (Apple Silicon)
# Using Homebrew dependencies

# Compilers (Homebrew GCC + Apple Clang via Open MPI wrappers)
CC="/opt/homebrew/bin/mpicc"
CXX="/opt/homebrew/bin/mpicxx"
FC="/opt/homebrew/bin/mpifort"

# MPI
with_mpi="/opt/homebrew/opt/open-mpi"

# Linear algebra: OpenBLAS (ScaLAPACK auto-detected with MPI)
with_linalg_flavor="openblas"
LINALG_CPPFLAGS="-I/opt/homebrew/opt/openblas/include"
LINALG_LIBS="-L/opt/homebrew/opt/openblas/lib -lopenblas -L/opt/homebrew/opt/scalapack/lib -lscalapack"

# LibXC
with_libxc="/opt/homebrew/opt/libxc"

# HDF5 — use env method to bypass broken libhdf5.settings (Threads::Threads cmake artifact)
# DO NOT use with_hdf5=dir, use env vars only
with_hdf5="yes"
HDF5_CPPFLAGS="-I/opt/homebrew/opt/hdf5/include"
HDF5_FCFLAGS="-I/opt/homebrew/opt/hdf5/include"
HDF5_LIBS="-L/opt/homebrew/opt/hdf5/lib -lhdf5_fortran -lhdf5_hl -lhdf5 -lz"

# NetCDF — also use env method
with_netcdf="yes"
with_netcdf_fortran="yes"
NETCDF_CPPFLAGS="-I/opt/homebrew/opt/netcdf/include"
NETCDF_FCFLAGS="-I/opt/homebrew/opt/netcdf/include"
NETCDF_LIBS="-L/opt/homebrew/opt/netcdf/lib -lnetcdf"
NETCDF_FORTRAN_CPPFLAGS="-I/opt/homebrew/opt/netcdf-fortran/include"
NETCDF_FORTRAN_FCFLAGS="-I/opt/homebrew/opt/netcdf-fortran/include"
NETCDF_FORTRAN_LIBS="-L/opt/homebrew/opt/netcdf-fortran/lib -lnetcdff"

# FFTW3
with_fft_flavor="fftw3"
FFTW3_CPPFLAGS="-I/opt/homebrew/opt/fftw/include"
FFTW3_LIBS="-L/opt/homebrew/opt/fftw/lib -lfftw3 -lfftw3f -lfftw3_mpi -lfftw3f_mpi"

# Install prefix
prefix="$HOME/.qmatsuite/engines/abinit/10.4.7"
ACEOF
```

### Step 3: Configure

```bash
cd "$BUILD_DIR/build_10.4.7"
../abinit-10.4.7/configure --with-config-file="./homebrew_arm64.ac9"
```

### Step 4: Build

```bash
# Use -j4 (not higher) to avoid Fortran module race conditions
make -j4
```

**Known issue**: With `-j10` or higher, you may hit:
```
Fatal Error: Cannot open module file 'm_dfpt_rhotov.mod' for reading
```
This is a Fortran parallel build race where `.mod` file writes lag behind `.o` file writes.
Fix: `rm src/72_response/m_dfpt_rhotov.o && cd src/72_response && make m_dfpt_rhotov.o && cd ../.. && make -j4`
Or just use `-j4` from the start.

### Step 5: Install

```bash
make install
# Verify
~/.qmatsuite/engines/abinit/10.4.7/bin/abinit --version
# Expected output: 10.4.7-d
```

### Step 6: Smoke test

```bash
mkdir -p /tmp/abinit_smoke && cd /tmp/abinit_smoke

# Copy and run the fast test
cp "$BUILD_DIR/abinit-10.4.7/tests/fast/Input/t01.abi" .
ABI_PSPDIR="$BUILD_DIR/abinit-10.4.7/tests/Pspdir" \
  ~/.qmatsuite/engines/abinit/10.4.7/bin/abinit t01.abi

# Check output
grep "etotal" t01.abo
# Expected: etotal ~ -4.3477E-01 Ha

# MPI test (optional)
ABI_PSPDIR="$BUILD_DIR/abinit-10.4.7/tests/Pspdir" \
  mpirun -np 2 ~/.qmatsuite/engines/abinit/10.4.7/bin/abinit t01.abi
```

### Known Pitfalls

1. **Conda MPI wrappers are broken on arm64**: They look for `arm64-apple-darwin20.0.0-gfortran`.
   Always use `/opt/homebrew/bin/mpifort` explicitly.

2. **HDF5 2.0.0 `Threads::Threads` bug**: Homebrew's HDF5 2.0.0 has a CMake artifact
   (`Threads::Threads`) in `libhdf5.settings`. Abinit's configure reads this file when using
   `with_hdf5="/path/to/hdf5"` (dir init mode) and passes the raw string to the linker.
   **Workaround**: Use env-based init (`with_hdf5="yes"` + explicit `HDF5_*` variables).

3. **`with_linalg_flavor="openblas+scalapack"` is invalid**: The `+scalapack` suffix is
   auto-detection output only. Use `with_linalg_flavor="openblas"` and put scalapack in
   `LINALG_LIBS`.

4. **Fortran parallel build races**: Use `-j4` or lower. Higher parallelism can cause `.mod`
   file ordering issues in the `72_response` directory.
