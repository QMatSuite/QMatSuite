# LAMMPS Assets Acquisition Plan

**Version**: 1.0.0  
**Date**: 2026-01-20  
**Status**: Ready for Execution  
**Constitution Reference**: §B (Assets)

---

## 1. Overview

This document specifies how to acquire LAMMPS potential files for testing, their licensing status, and the acquisition strategy.

**Key Constraint**: We need at least one freely redistributable potential file for each major category (EAM, Tersoff) to include in the repository for CI testing.

---

## 2. Potential Categories for MVP

| Category | Style | Test Priority | File Needed | Notes |
|----------|-------|---------------|-------------|-------|
| LJ | `lj/cut` | P0 | None | Built-in, no external file |
| EAM | `eam`, `eam/alloy` | P0 | Yes | Real metal potential |
| Tersoff | `tersoff` | P1 | Yes | Semiconductor potential |
| ReaxFF | `reaxff` | P3 | Future | Complex, not MVP |

---

## 3. LJ/Cut (Built-in) - No Acquisition Needed

### 3.1 Description

Lennard-Jones potentials are specified inline via `pair_coeff` commands. No external file is required.

### 3.2 Test Configuration

```yaml
potential_map:
  lj_argon:
    style: lj/cut
    cutoff: 2.5
    params:
      "1 1": "1.0 1.0"  # epsilon sigma
```

### 3.3 Generated Commands

```bash
pair_style lj/cut 2.5
pair_coeff 1 1 1.0 1.0
```

**Status**: ✅ Ready - no acquisition needed

---

## 4. EAM Potentials

### 4.1 Source: LAMMPS Distribution

LAMMPS includes example potentials in its distribution under `potentials/` directory. These are covered by the LAMMPS GPL-2.0 license and can be redistributed.

**Location in LAMMPS source**:
```
lammps/potentials/Cu_u3.eam
lammps/potentials/Al_zhou.eam.alloy
lammps/potentials/NiAlH_jea.eam.alloy
```

**Homebrew install path** (if installed):
```
/opt/homebrew/opt/lammps/share/lammps/potentials/
```

### 4.2 Recommended Test Potential: Cu_u3.eam

| Property | Value |
|----------|-------|
| **File** | `Cu_u3.eam` |
| **Style** | `eam` (single element) |
| **Element** | Cu |
| **Format** | DYNAMO funcfl |
| **Size** | ~80 KB |
| **Source** | LAMMPS distribution |
| **License** | GPL-2.0 (LAMMPS) |
| **SHA256** | To be computed after acquisition |

### 4.3 Acquisition Commands

```bash
# Option 1: From Homebrew install (if available)
cp /opt/homebrew/opt/lammps/share/lammps/potentials/Cu_u3.eam \
   resources/lammps/potentials/

# Option 2: From LAMMPS GitHub repository
curl -L -o resources/lammps/potentials/Cu_u3.eam \
  https://raw.githubusercontent.com/lammps/lammps/stable/potentials/Cu_u3.eam

# Option 3: From Ubuntu apt install
cp /usr/share/lammps/potentials/Cu_u3.eam \
   resources/lammps/potentials/
```

### 4.4 Verification

```bash
# Check file exists and has expected format
head -5 resources/lammps/potentials/Cu_u3.eam
# Expected: Header lines with Cu and numerical parameters

# Compute SHA256 for provenance
sha256sum resources/lammps/potentials/Cu_u3.eam
```

### 4.5 Alternative: Al_zhou.eam.alloy

If multi-element testing is needed:

| Property | Value |
|----------|-------|
| **File** | `Al_zhou.eam.alloy` |
| **Style** | `eam/alloy` |
| **Elements** | Al |
| **Source** | LAMMPS distribution |

---

## 5. Tersoff Potentials

### 5.1 Source: LAMMPS Distribution

```
lammps/potentials/SiC.tersoff
lammps/potentials/Si.tersoff
lammps/potentials/BNC.tersoff
```

### 5.2 Recommended Test Potential: SiC.tersoff

| Property | Value |
|----------|-------|
| **File** | `SiC.tersoff` |
| **Style** | `tersoff` |
| **Elements** | Si, C |
| **Size** | ~2 KB |
| **Source** | LAMMPS distribution |
| **License** | GPL-2.0 (LAMMPS) |

### 5.3 Acquisition Commands

```bash
curl -L -o resources/lammps/potentials/SiC.tersoff \
  https://raw.githubusercontent.com/lammps/lammps/stable/potentials/SiC.tersoff
```

---

## 6. NIST Interatomic Potentials Repository (Alternative Source)

### 6.1 About

The NIST Interatomic Potentials Repository provides potentials with clear provenance and citations.

**URL**: https://www.ctcms.nist.gov/potentials/

### 6.2 Licensing Consideration

NIST potentials have varying licenses depending on the original author. Many are freely available but require citation. For repository inclusion, we prefer LAMMPS-distributed potentials which have clear GPL-2.0 coverage.

### 6.3 Use Case

For production use (not test fixtures), users can download potentials from NIST and add them to their project's `potentials/` directory.

---

## 7. Directory Structure

### 7.1 Test Fixtures in Repository

```
resources/lammps/potentials/
├── README.md                   # License and provenance information
├── Cu_u3.eam                   # EAM single-element test potential
├── SiC.tersoff                 # Tersoff test potential
└── .gitattributes              # LFS tracking if files are large
```

### 7.2 README.md Content

```markdown
# LAMMPS Test Potentials

These potential files are included for testing purposes only.

## License

All files are from the LAMMPS distribution and are covered by GPL-2.0.

## Provenance

| File | Source | Retrieved | SHA256 |
|------|--------|-----------|--------|
| Cu_u3.eam | lammps/potentials/ | 2026-01-20 | {hash} |
| SiC.tersoff | lammps/potentials/ | 2026-01-20 | {hash} |

## Citation

If using these potentials for research, please cite the original sources
as documented in the LAMMPS manual and NIST repository.
```

---

## 8. Fallback Strategy: Runtime Download

If we cannot or prefer not to include potential files in the repository, we can download them at test time.

### 8.1 Download Script

Create `tools/download_lammps_potentials.py`:

```python
#!/usr/bin/env python3
"""Download LAMMPS test potentials with hash verification."""

import hashlib
import urllib.request
from pathlib import Path

POTENTIALS = [
    {
        "name": "Cu_u3.eam",
        "url": "https://raw.githubusercontent.com/lammps/lammps/stable/potentials/Cu_u3.eam",
        "sha256": "EXPECTED_SHA256_HASH",
    },
    {
        "name": "SiC.tersoff",
        "url": "https://raw.githubusercontent.com/lammps/lammps/stable/potentials/SiC.tersoff",
        "sha256": "EXPECTED_SHA256_HASH",
    },
]

def download_potentials(target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    
    for pot in POTENTIALS:
        target = target_dir / pot["name"]
        
        if target.exists():
            # Verify hash
            actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual_hash == pot["sha256"]:
                print(f"✓ {pot['name']} already exists with correct hash")
                continue
            else:
                print(f"! {pot['name']} exists but hash mismatch, re-downloading")
        
        print(f"Downloading {pot['name']}...")
        urllib.request.urlretrieve(pot["url"], target)
        
        # Verify download
        actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual_hash != pot["sha256"]:
            raise ValueError(
                f"Hash mismatch for {pot['name']}: "
                f"expected {pot['sha256']}, got {actual_hash}"
            )
        
        print(f"✓ {pot['name']} downloaded and verified")

if __name__ == "__main__":
    download_potentials(Path("resources/lammps/potentials"))
```

### 8.2 CI Integration

```yaml
# .github/workflows/ci.yml
- name: Download LAMMPS test potentials
  run: python tools/download_lammps_potentials.py
```

### 8.3 Offline Fallback

For offline CI or air-gapped environments:

1. Pre-download potentials and commit to repository
2. OR use LFS for larger files
3. OR skip tests that require external potentials (not recommended per constitution)

---

## 9. Acquisition Checklist

### 9.1 Phase 0 Tasks

- [ ] Create `resources/lammps/potentials/` directory
- [ ] Download `Cu_u3.eam` from LAMMPS repo
- [ ] Compute and record SHA256
- [ ] Download `SiC.tersoff` from LAMMPS repo
- [ ] Compute and record SHA256
- [ ] Create README.md with provenance
- [ ] Verify files work with local LAMMPS installation
- [ ] Commit files to repository

### 9.2 Verification Commands

```bash
# Verify EAM works
echo "
units metal
atom_style atomic
boundary p p p
region box block 0 10 0 10 0 10
create_box 1 box
create_atoms 1 random 100 12345 box
mass 1 63.546
pair_style eam
pair_coeff * * resources/lammps/potentials/Cu_u3.eam
run 0
" | lmp

# Verify Tersoff works
echo "
units metal
atom_style atomic
boundary p p p
region box block 0 10 0 10 0 10
create_box 2 box
create_atoms 1 random 50 12345 box
create_atoms 2 random 50 67890 box
mass 1 28.0855
mass 2 12.0107
pair_style tersoff
pair_coeff * * resources/lammps/potentials/SiC.tersoff Si C
run 0
" | lmp
```

---

## 10. License Compliance Summary

| File | Original Source | License | Redistribution |
|------|-----------------|---------|----------------|
| Cu_u3.eam | LAMMPS repo | GPL-2.0 | ✅ Allowed |
| SiC.tersoff | LAMMPS repo | GPL-2.0 | ✅ Allowed |
| LJ params | Built-in | N/A | ✅ No file needed |

**Note**: If we later add potentials from NIST or other sources, we must verify their individual licenses before including in the repository.

---

## 11. Future Extensions

### 11.1 DeepMD Models

For future ML potential testing, we may need:
- Small pre-trained DeepMD model
- Model file can be large (10-100 MB)
- Consider LFS or external download

### 11.2 ReaxFF Parameters

- `ffield.reax.*` files from LAMMPS distribution
- License: GPL-2.0
- Add when ReaxFF workflow implemented

### 11.3 User-Supplied Potentials

Documentation for users on:
- Adding potentials to `project/potentials/`
- Registering in `potential_map`
- Recommended sources (NIST, OpenKIM)

