# PySCF Platform Support Review

**Date**: 2025-01-XX  
**Purpose**: Assess PySCF's platform/support status and integration implications for QMatSuite  
**Sources**: Local PySCF repository snapshot (`.tmp/downloads/pyscf-master`), HTML documentation snapshots, Docker build configs

---

## 1. Official Support Statements

### 1.1 Windows Native Support

**Finding**: PySCF does **not officially support Windows native**. The documentation explicitly mentions only "ubuntu subsystems on Windows 10" as a supported platform.

**Source**: `.tmp/downloads/pyscf-master/doc_legacy/source/install.rst:14`
> "Pypi provides a precompiled PySCF code (python wheel) which works on almost all Linux systems, and most of Mac OS X systems, and the ubuntu subsystems on Windows 10."

**Implication**: Windows users must use WSL (Windows Subsystem for Linux) or Docker. Native Windows builds are not provided or tested.

### 1.2 Installation Recommendations

**Pip wheels (recommended)**:
- **Source**: `.tmp/downloads/pyscf-master/doc_legacy/source/install.rst:9-11`
> "This is the recommended way to install PySCF: `pip install pyscf`"

**Build from source**:
- **Source**: `.tmp/downloads/pyscf-master/doc_legacy/source/install.rst:71-73`
> "Manual installation requires `cmake`, `numpy`, `scipy` and `h5py` libraries."

**Conda**:
- **Source**: `.tmp/downloads/pyscf-master/doc_legacy/source/install.rst:48`
> "PySCF package can be installed with Conda cloud: `conda install -c pyscf pyscf`"

### 1.3 Platform Classifiers

**Source**: `.tmp/downloads/pyscf-master/pyproject.toml:26-29`
```toml
'Operating System :: POSIX',
'Operating System :: Unix',
'Operating System :: MacOS',
```

**Note**: No `Operating System :: Microsoft :: Windows` classifier is present, confirming Windows is not officially supported.

---

## 2. Distribution Channels & Platform Implications

### 2.1 PyPI Wheels (pip)

**Supported Platforms** (from documentation and build configs):

**Linux**:
- **Architecture**: `x86_64` (confirmed via Docker builds)
- **Wheel tag**: `manylinux2014_x86_64` (from `.tmp/downloads/pyscf-master/docker/pypa-env/Dockerfile:4`)
- **Alternative**: `manylinux2010_x86_64` (from `.tmp/downloads/pyscf-master/docker/pypa-env/Dockerfile-2.0-openblas:4`)
- **Glibc baseline**: Not explicitly stated in local sources, but `manylinux2014` implies glibc 2.17+ (CentOS 7 era)

**macOS**:
- **Architectures**: `x86_64` and `arm64` (Apple Silicon)
- **Evidence**: `.tmp/downloads/pyscf-master/setup.py:35-51` shows platform detection for `CMAKE_OSX_ARCHITECTURES` supporting both `arm64` and `x86_64`, with `universal2` support
- **Minimum OS version**: Not explicitly stated in local sources

**Windows**:
- **Status**: No wheels provided
- **Evidence**: No Windows-specific build configs found in repository

**aarch64 (ARM64 Linux)**:
- **Status**: Mentioned in CHANGELOG (`.tmp/downloads/pyscf-master/CHANGELOG:387`)
> "Supports to aarch64 architecture"
- **Wheel availability**: Not confirmed in local build configs (Docker files only show `x86_64`)

### 2.2 Conda / Conda-forge

**Source**: `.tmp/downloads/pyscf-master/conda/meta.yaml`

**Build requirements**:
- `cmake`
- `make`
- `mkl` (Intel Math Kernel Library)
- C/C++ compilers

**Run requirements**:
- `mkl` (runtime dependency)
- `numpy>=1.13`
- `scipy!=1.5`
- `h5py>=2.7`

**Platform support**: Conda build config (`.tmp/downloads/pyscf-master/conda/conda_build_config.yaml`) only lists Python versions (3.8-3.13), not OS/arch. Conda-forge typically supports:
- Linux (x86_64, aarch64, ppc64le)
- macOS (x86_64, arm64)
- Windows (via conda-forge, but PySCF's CMakeLists.txt has `if (WIN32) #?` placeholder, suggesting incomplete Windows support)

**Gap**: Windows conda packages may exist but are not officially supported per documentation.

### 2.3 Docker

**Source**: `.tmp/downloads/pyscf-master/docker/`

**Available images**:
- `pyscf/pyscf-1.5.0` (example from install docs)
- Build environments: `pyscf/pyscf-pypa-env`, `pyscf/pyscf-conda-env`

**Windows support**: Docker containers can run on Windows via Docker Desktop, providing a workaround for native Windows limitations.

**Source**: `.tmp/downloads/pyscf-master/doc_legacy/source/install.rst:54-60`
> "The following command starts a container with the jupyter notebook server listening for HTTP connections on port 8888: `docker run -it -p 8888:8888 pyscf/pyscf-1.5.0`"

---

## 3. Wheel Compatibility / "Minimum OS" Evidence

### 3.1 Wheel Tags (Not Available Locally)

**Finding**: Actual wheel filenames are not present in the local snapshot. Evidence is inferred from:
- Docker build configs using `manylinux2014_x86_64` and `manylinux2010_x86_64` base images
- `setup.py` platform detection logic for macOS universal2 builds

### 3.2 macOS Minimum Versions

**Evidence**: `.tmp/downloads/pyscf-master/setup.py:35-51` shows architecture detection but no explicit minimum OS version.

**Practical meaning**:
- **arm64 (Apple Silicon)**: Requires macOS 11.0+ (Big Sur) as baseline for native ARM support
- **x86_64 (Intel)**: Likely macOS 10.9+ (Mavericks) or later, but not explicitly documented
- **Universal2**: Supported via `CMAKE_OSX_ARCHITECTURES` with `arm64;x86_64`

**Gap**: No explicit minimum macOS version stated in local sources.

### 3.3 Linux manylinux/glibc Baseline

**Evidence**: Docker files use `manylinux2014_x86_64` and `manylinux2010_x86_64` base images.

**Practical meaning**:
- **manylinux2014**: Requires glibc 2.17+ (CentOS 7 baseline, ~2014)
- **manylinux2010**: Requires glibc 2.12+ (CentOS 6 baseline, ~2010)
- **Implication**: Older Linux distributions (pre-2010) may not be supported

**Source**: `.tmp/downloads/pyscf-master/docker/pypa-env/Dockerfile:4`
> `FROM quay.io/pypa/manylinux2014_x86_64:2023-03-26-14247e5`

---

## 4. Build-from-Source Dependency Graph

### 4.1 Required Toolchain

**Source**: `.tmp/downloads/pyscf-master/doc_legacy/source/install.rst:71-73`

**Core dependencies**:
- `cmake` (minimum version 3.22 per `.tmp/downloads/pyscf-master/pyscf/lib/CMakeLists.txt:15`)
- `numpy` (>=1.13, !=1.16, !=1.17 per `.tmp/downloads/pyscf-master/pyproject.toml:38`)
- `scipy` (>=1.6.0 per `.tmp/downloads/pyscf-master/pyproject.toml:39`)
- `h5py` (>=2.7 per `.tmp/downloads/pyscf-master/pyproject.toml:40`)
- C/C++ compiler (GCC, Clang, or Intel)
- `make` (for building external projects)

### 4.2 External Libraries (Auto-downloaded)

**Source**: `.tmp/downloads/pyscf-master/pyscf/lib/CMakeLists.txt:169-300`

#### libcint (Gaussian integral library)
- **Default**: Built automatically via `ExternalProject_Add`
- **Git**: `https://github.com/sunqm/libcint.git`, tag `v6.1.3`
- **Alternative**: `qcint` (optimized for x86-64) via `USE_QCINT=ON`
- **CMake options**:
  - `BUILD_LIBCINT=ON` (default)
  - `WITH_F12=ON` (default, F12 integrals)
  - `WITH_RANGE_COULOMB=1`
  - `WITH_COULOMB_ERF=1`

#### Libxc (DFT exchange-correlation)
- **Default**: Built automatically if `ENABLE_LIBXC=ON` and `BUILD_LIBXC=ON`
- **URL**: `https://gitlab.com/libxc/libxc/-/archive/7.0.0/libxc-7.0.0.tar.gz`
- **CMake options**:
  - `ENABLE_LIBXC=ON` (default)
  - `BUILD_LIBXC=ON` (default)
  - `-DENABLE_FORTRAN=0 -DDISABLE_KXC=0 -DDISABLE_LXC=1`

#### XCFun (Alternative XC library)
- **Default**: Built automatically if `ENABLE_XCFUN=ON` and `BUILD_XCFUN=ON`
- **Git**: `https://github.com/dftlibs/xcfun.git`, tag `a89b783`
- **CMake options**:
  - `ENABLE_XCFUN=ON` (default)
  - `BUILD_XCFUN=ON` (default)
  - `XCFUN_MAX_ORDER=3` (default)

### 4.3 Critical CMake Options

**Source**: `.tmp/downloads/pyscf-master/pyscf/lib/CMakeLists.txt`

**Options affecting functionality**:
- `ENABLE_LIBXC=ON/OFF`: Enable Libxc for DFT (default: ON)
- `ENABLE_XCFUN=ON/OFF`: Enable XCFun for DFT (default: ON)
- `DISABLE_DFT=ON/OFF`: Disable entire DFT module (default: OFF)
- `BUILD_LIBCINT=ON/OFF`: Build libcint (default: ON)
- `BUILD_MARCH_NATIVE=ON/OFF`: Use `-march=native` optimization (default: OFF)
- `ENABLE_OPENMP=ON/OFF`: Enable OpenMP parallelization (default: ON)
- `ENABLE_NAO=ON/OFF`: Enable numerical atomic orbitals (default: OFF)
- `ENABLE_TBLIS=ON/OFF`: Enable TBLIS tensor library (default: OFF, requires C++11)

### 4.4 Breaking Combinations

**Source**: `.tmp/downloads/pyscf-master/pyscf/lib/CMakeLists.txt:220-281`

**Critical dependency**:
- If `DISABLE_DFT=ON`, the entire `pyscf.dft` module is disabled (line 220-221)
- If both `ENABLE_LIBXC=OFF` and `ENABLE_XCFUN=OFF`, DFT calculations will fail (no XC library available)
- **Note**: The code does not explicitly prevent this combination, but DFT functionality requires at least one XC library

**Evidence**: `.tmp/downloads/pyscf-master/pyscf/lib/CMakeLists.txt:223-264` shows conditional compilation of DFT modules based on `ENABLE_LIBXC` and `ENABLE_XCFUN`.

### 4.5 Manual Build Process

**Source**: `.tmp/downloads/pyscf-master/doc_legacy/source/install.rst:80-86`

**Steps**:
1. `cd pyscf/lib`
2. `mkdir build && cd build`
3. `cmake ..`
4. `make`

**External library download**: CMake's `ExternalProject_Add` automatically downloads and builds libcint, libxc, and xcfun during the build process.

---

## 5. Runtime Libraries & Performance-Related Dependencies

### 5.1 BLAS/LAPACK Selection

**Source**: `.tmp/downloads/pyscf-master/pyscf/lib/CMakeLists.txt:71-94`

**Detection**: CMake's `find_package(BLAS)` automatically detects available BLAS libraries.

**Manual specification**:
- **Environment variable**: `LDFLAGS="-L/path/to/blas -lblas"` (from install docs)
- **CMake variable**: `BLA_VENDOR` (e.g., `Intel10_64lp_seq`, `ATLAS`, `OpenBLAS`, `IBMESSL`)
- **Direct assignment**: `BLAS_LIBRARIES` in `CMakeLists.txt` or `cmake.arch.inc`

**Source**: `.tmp/downloads/pyscf-master/doc_legacy/source/install.rst:198-199`
> "You can compile the package with other BLAS vendors to improve performance, for example the Intel Math Kernel Library (MKL), which can provide 10x speedup in many modules: `cmake -DBLA_VENDOR=Intel10_64lp_seq ..`"

**Conda default**: MKL (from `.tmp/downloads/pyscf-master/conda/meta.yaml:19,26`)

### 5.2 OpenMP / Runtime Conflicts

**Source**: `.tmp/downloads/pyscf-master/pyscf/lib/CMakeLists.txt:97-105`

**Default**: `ENABLE_OPENMP=ON`

**Risks** (conceptual, not explicitly documented):
- OpenMP runtime conflicts if multiple OpenMP implementations are loaded (GNU libgomp vs. Intel libiomp5)
- Threading conflicts with NumPy/SciPy if they use different OpenMP runtimes
- **Note**: No explicit warnings found in local sources, but this is a common issue with scientific Python packages

### 5.3 Environment Variables

**Source**: `.tmp/downloads/pyscf-master/pyscf/__config__.py`

#### `PYSCF_MAX_MEMORY`
- **Default**: 4000 MB
- **Purpose**: Maximum memory allocation for PySCF operations
- **Usage**: `export PYSCF_MAX_MEMORY=10000` (10 GB example)

#### `PYSCF_TMPDIR`
- **Default**: System `TMPDIR` (from `tempfile.gettempdir()`)
- **Purpose**: Scratch directory for temporary files
- **Usage**: `export PYSCF_TMPDIR=/path/to/scratch`

#### `PYSCF_CONFIG_FILE`
- **Default**: None (searches `.pyscf_conf.py` in current directory or `$HOME`)
- **Purpose**: Path to custom configuration file
- **Usage**: `export PYSCF_CONFIG_FILE=/path/to/config.py`

#### `PYSCF_EXT_PATH`
- **Source**: `.tmp/downloads/pyscf-master/pyscf/__init__.py:44-83`
- **Purpose**: Load external PySCF extensions/modules
- **Format**: Colon-separated paths (Unix) or semicolon-separated (Windows, though Windows not supported)
- **Usage**: `export PYSCF_EXT_PATH=/path/to/extension1:/path/to/extension2`

**Additional build-time variables**:
- `CMAKE_CONFIGURE_ARGS`: Pass additional CMake arguments during pip install
- `CMAKE_BUILD_ARGS`: Pass additional build arguments
- `CMAKE_BUILD_PARALLEL_LEVEL`: Control parallel compilation (default: sequential to avoid OOM)

**Source**: `.tmp/downloads/pyscf-master/setup.py:64-77`

---

## 6. Integration Implications for QMatSuite

### 6.1 Current QMatSuite Engine Architecture

**Source**: Codebase search results and existing QE engine implementation

**Key patterns**:
- Engines are detected via `detect_executable()` method
- Engines run via subprocess execution (not direct Python imports in daemon)
- Platform detection exists for QE (Windows `.exe` vs. Unix `.x` extensions)
- Engine registry system for managed engines (`.qmatsuite/engines/`)

### 6.2 Integration Path A: Dev-Mode (Daemon Venv)

**Description**: Install PySCF into the daemon's virtual environment, with platform markers to exclude Windows.

**Pros**:
- Simple: `pip install pyscf` in daemon venv
- Direct Python API access (if needed for validation/preprocessing)
- Consistent with existing optional dependency pattern

**Cons**:
- Windows users cannot use PySCF (must use Docker/WSL)
- Daemon must have PySCF importable (adds dependency to core daemon)
- Platform-specific wheel selection handled by pip (may fail on unsupported platforms)

**Risks**:
- **Windows**: Import will fail gracefully, but user experience is poor (no clear error message)
- **Platform detection**: Need to detect `sys.platform` and skip PySCF on Windows
- **Wheel compatibility**: Older Linux systems may not have compatible wheels (glibc version)

**Implementation notes**:
- Add `pyscf` to `pyproject.toml` optional dependencies with platform markers:
  ```toml
  [project.optional-dependencies]
  pyscf = [
    "pyscf; sys_platform != 'win32'",
  ]
  ```
- Update `PySCFEngine.detect_executable()` to return `False` on Windows
- Document Windows limitation in user-facing error messages

### 6.3 Integration Path B: Managed Engine Bundle

**Description**: Separate engine environment/bundle per platform; daemon never imports PySCF directly.

**Pros**:
- Isolation: PySCF never imported in daemon process
- Platform-specific builds: Can bundle pre-built wheels or build from source per platform
- Windows support: Could bundle Docker image or WSL instructions
- Consistent with QE engine pattern (executables in `.qmatsuite/engines/`)

**Cons**:
- Complex: Need to manage engine bundles, versioning, platform detection
- Build overhead: Must build or download PySCF wheels per platform
- Python subprocess: PySCF is a Python library, not a binary executable (unlike QE's `pw.x`)

**Risks**:
- **Subprocess execution**: PySCF runs as `python -m pyscf` or via generated script, not a single executable
- **Environment isolation**: Each engine bundle needs its own Python environment (venv/conda)
- **Version management**: PySCF version must be pinned per engine bundle
- **Windows**: Still requires Docker/WSL, but bundled instructions could help

**Implementation notes**:
- Engine bundle structure:
  ```
  .qmatsuite/engines/pyscf/
    managed:pyscf-2.11.0:linux-x86_64/
      venv/  # Isolated Python environment
      bin/   # Wrapper scripts (pyscf_scf.py, etc.)
      meta.json  # Version, platform, dependencies
  ```
- Daemon runs: `python .qmatsuite/engines/pyscf/.../venv/bin/python -m pyscf ...`
- Platform detection: Match `sys.platform` and `platform.machine()` to bundle

### 6.4 Windows-Specific Implications

**Official stance**: PySCF does not support Windows native. Users must use:
1. WSL (Windows Subsystem for Linux)
2. Docker Desktop
3. Linux virtual machine

**QMatSuite options**:
- **Option 1**: Disable PySCF on Windows entirely (Path A with platform marker)
- **Option 2**: Provide Docker-based execution on Windows (Path B with Docker wrapper)
- **Option 3**: Detect WSL and use WSL Python interpreter (complex, not recommended)

**Recommendation**: Option 1 (disable on Windows) for MVP, with clear error message pointing to Docker/WSL alternatives.

### 6.5 Comparison with QE Engine

**QE Engine** (from codebase):
- Binary executables (`pw.x`, `ph.x`, etc.)
- Cross-platform detection (Windows `.exe` vs. Unix `.x`)
- PATH-based detection fallback
- Managed engine bundles in `.qmatsuite/engines/qe/`

**PySCF differences**:
- Python library (not binary)
- No Windows support
- Requires Python environment (venv/conda)
- Subprocess execution via `python -m pyscf` or generated scripts

**Implication**: PySCF integration cannot follow QE pattern exactly; requires Python subprocess execution model.

---

## 7. Concrete "Next Actions" Checklist

### 7.1 Local Verification Tasks

1. **CMakeLists.txt inspection**:
   - [ ] Verify `ExternalProject_Add` usage for libcint, libxc, xcfun
   - [ ] Check if `make` is required (vs. `cmake --build`)
   - [ ] Verify Windows build path (`if (WIN32) #?` placeholder)

2. **Wheel tag inspection** (if PyPI access available later):
   - [ ] Query PyPI for actual wheel tags: `pip index versions pyscf --format json`
   - [ ] Verify macOS minimum version from wheel tags
   - [ ] Check aarch64 wheel availability

3. **Build dependency verification**:
   - [ ] Test minimal build: `BUILD_LIBXC=OFF BUILD_XCFUN=OFF` (DFT disabled)
   - [ ] Test with only Libxc: `ENABLE_XCFUN=OFF`
   - [ ] Test with only XCFun: `ENABLE_LIBXC=OFF`
   - [ ] Verify import fails gracefully when both XC libs disabled

### 7.2 Minimal Smoke Test Example

**Molecular calculation** (H2O RHF):
```python
from pyscf import gto, scf
mol = gto.M(atom='H 0 0 0; O 0 0 0.96; H 0 0.91 -0.39', basis='sto-3g')
mf = scf.RHF(mol)
energy = mf.kernel()
assert abs(energy + 74.9) < 1.0  # Approximate energy check
```

**PBC calculation** (if needed for comparison):
```python
from pyscf import gto, scf, pbc
cell = pbc.gto.Cell()
cell.atom = 'He 0 0 0'
cell.a = [[2.0, 0, 0], [0, 2.0, 0], [0, 0, 2.0]]
cell.basis = 'sto-3g'
cell.build()
mf = pbc.scf.RHF(cell)
energy = mf.kernel()
```

**Note**: Do not implement this in QMatSuite yet; this is for manual verification only.

### 7.3 QMatSuite Changes Needed (Future)

**Engine manifest fields** (if using Path B):
- `engine_id`: `managed:pyscf-2.11.0:linux-x86_64`
- `platform`: `linux-x86_64`, `darwin-arm64`, `darwin-x86_64`
- `python_version`: `3.9`, `3.10`, etc.
- `pyscf_version`: `2.11.0`
- `requires_dft`: `true`/`false` (if XC libraries included)

**Engine probe/run contract**:
- `detect_executable()`: Check if PySCF importable (Path A) or engine bundle exists (Path B)
- `generate_input()`: Create Python script for PySCF calculation
- `build_command()`: `['python', 'pyscf_input.py']` or `['python', '-m', 'pyscf', '...']`
- `parse_output()`: Extract energy, MOs, HOMO/LUMO from `results.json` or stdout

**Platform detection**:
- Add `sys.platform == 'win32'` check in `PySCFEngine.detect_executable()`
- Return `False` on Windows with helpful error message
- Document Windows limitation in user-facing docs

**Error handling**:
- Import error: "PySCF not installed. Install with: `pip install pyscf`"
- Windows error: "PySCF does not support Windows native. Use Docker or WSL."
- Build error: "PySCF build failed. Check CMake/BLAS dependencies."

---

## 8. Summary of Findings

### 8.1 Platform Support Matrix

| Platform | Pip Wheels | Conda | Docker | Build from Source |
|----------|------------|-------|--------|-------------------|
| Linux x86_64 | ✅ (manylinux2014) | ✅ | ✅ | ✅ |
| Linux aarch64 | ⚠️ (mentioned, not confirmed) | ✅ | ✅ | ✅ |
| macOS x86_64 | ✅ | ✅ | ✅ | ✅ |
| macOS arm64 | ✅ (universal2) | ✅ | ✅ | ✅ |
| Windows native | ❌ | ⚠️ (may exist, not supported) | ✅ (via Docker) | ❌ |

### 8.2 Critical Dependencies

**Build-time**:
- CMake >= 3.22
- C/C++ compiler
- BLAS/LAPACK (MKL recommended for performance)
- NumPy, SciPy, h5py

**Runtime**:
- BLAS/LAPACK (must match build-time selection)
- OpenMP (optional, but enabled by default)
- libcint (auto-built)
- libxc and/or xcfun (for DFT)

### 8.3 Integration Recommendation

**For MVP**: Use **Path A (Dev-Mode)** with platform markers:
- Simple implementation
- Leverages existing optional dependency pattern
- Clear Windows limitation (documented, not supported)
- Can migrate to Path B later if needed

**For Production**: Consider **Path B (Managed Engine Bundle)** if:
- Need better Windows support (Docker wrapper)
- Want to isolate PySCF from daemon
- Need platform-specific optimizations (MKL, qcint)

---

## 9. Evidence Citations

All claims in this report are backed by local file citations:

- **Installation docs**: `.tmp/downloads/pyscf-master/doc_legacy/source/install.rst`
- **Build config**: `.tmp/downloads/pyscf-master/pyscf/lib/CMakeLists.txt`
- **Python config**: `.tmp/downloads/pyscf-master/pyscf/__config__.py`
- **Project metadata**: `.tmp/downloads/pyscf-master/pyproject.toml`
- **Docker configs**: `.tmp/downloads/pyscf-master/docker/`
- **Conda config**: `.tmp/downloads/pyscf-master/conda/`

**Missing evidence** (not found in local snapshot):
- Actual PyPI wheel filenames/tags
- Explicit macOS minimum version
- Windows build attempt results
- aarch64 wheel availability confirmation

---

**Report compiled from local sources only. No internet access used.**


