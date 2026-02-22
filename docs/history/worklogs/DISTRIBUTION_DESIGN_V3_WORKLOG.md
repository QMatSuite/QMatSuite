# Distribution Design v3 — Finalization Worklog

**Date**: 2026-02-21
**Scope**: Finalize all 6 design decisions in CROSS_PLATFORM_DISTRIBUTION_DESIGN.md

---

## Decisions Applied

### Decision 1: Python Backend = Micromamba (Final)
- Removed Options A (PyInstaller), B (Nuitka), D (Hybrid) as active options
- Collapsed §4.3 to single "Micromamba" section with final decision framing
- Moved PyInstaller/Nuitka to §4.4 "Future Alternatives" (reference only)
- Added Nuitka priority 3 slot in `findPythonPath()` (non-breaking upgrade path)
- Expanded §4.6 update strategy: pip upgrade, micromamba update, Python version as independent dimensions

### Decision 2: Download Size Framing
- Added §1.5 "Download vs Installed Size" table
- Compressed size estimates: ~190MB lite download, ~290MB full download
- Component breakdown: Electron (~70MB), Python env (~115MB compressed), QE (~50MB), SSSP (~30MB)

### Decision 3: Per-Platform Installation Behavior
- Added §1.6 with detailed per-platform subsections
- Windows: NSIS to %LOCALAPPDATA%\QMatSuite\ (no UAC), follows VS Code/Discord convention
- macOS lite: DMG with drag-to-Applications, compressed conda env tarball inside app bundle
- macOS full: .pkg installer (NOT DMG) — can install to multiple locations, atomic install
- Linux: pip primary, AppImage deferred
- Directory layouts for each platform

### Decision 4: Code Signing Comprehensive Update
- Updated §7 with complete artifact signing table
- Container signatures cover all bundled third-party binaries
- Every distributed executable gets signed

### Decision 5: Python Engines as Micromamba-Managed
- Verified §3.8 already correctly documents Python engine management
- Fixed `pip install quantumvitas[all]` to not include PySCF

### Decision 6: Engine Detection
- Verified §3.4 engine detection table already has correct binary names
- No changes needed

---

## Additional Fixes
- Fixed macOS full references from `.dmg` to `.pkg` in gap analysis table and roadmap
- Updated `findPythonPath()` runtime path from `micromamba/envs/qmatsuite-runtime/` to `runtime/`
- Updated roadmap §3.2 description to match tarball expansion approach
- Updated roadmap §3.4 to mention both `.dmg` (lite) and `.pkg` (full)
- Cleaned up all references to removed Options A-D, Plan A/B language
- Updated ToC to reflect new subsections

## Document Stats
- v2 (pre-finalization): 1414 lines
- v3 (post-finalization): 1509 lines (+95 lines)
- New sections: §1.5 (size table), §1.6 (per-platform install, 4 subsections)
- Rewritten sections: §4.3-4.6, §7.1-7.4

## Files Modified
- `docs/design/CROSS_PLATFORM_DISTRIBUTION_DESIGN.md` — All 6 decisions applied
- `docs/history/worklogs/DISTRIBUTION_DESIGN_V3_WORKLOG.md` — This worklog
