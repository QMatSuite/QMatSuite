# Release macOS #27 — x64 Full-Signed Timeout Investigation

**Date**: 2026-02-27
**Run**: Release macOS #27 (workflow_dispatch `22418935995`)
**Inputs**: `version=1.2.1`, `variant=both`, `sign=true`, `notarize=true`, `wait_for_staple=true`

---

## 1. Summary

The arm64 job completed successfully in 1h 21m (including 37 min notarization wait).
The x64 job hit the GitHub Actions 6-hour timeout while still running **"Build full DMG (signed)"**.

| Job | Outcome | Wall time |
|-----|---------|-----------|
| arm64 (`macos-14`) | Success | 1h 21m |
| x64 (`macos-15-intel`) | Cancelled (timeout) | 6h 5m |

---

## 2. Step-Level Timing (Run #27)

### arm64 (`macos-14`, Apple Silicon)

| Step | Duration |
|------|----------|
| Setup through GUI build | 2 min |
| Build lite DMG (signed) | **20 min** |
| Build full DMG (signed) | **20 min** |
| Notarization wait + staple | 37 min |
| Upload | 1 min |
| **Total** | **1h 21m** |

### x64 (`macos-15-intel`)

| Step | Duration |
|------|----------|
| Setup through GUI build | 5 min |
| Build lite DMG (signed) | **47 min** |
| Build full DMG (signed) | **>5h 13m (killed)** |
| **Total** | **>6h 5m (timeout)** |

---

## 3. Cross-Run Comparison

| Build | arm64 signed | x64 signed | x64 unsigned (Run #26) |
|-------|-------------|------------|------------------------|
| Lite | 20 min | 47 min | N/A |
| Full | 20 min | >5h 13m (timeout) | ~5 min |

### Key finding

x64 full **unsigned** completed in ~5 minutes (Run #26, `sign=false`).
x64 full **signed** did not complete after 5+ hours.

The bottleneck is **codesigning on x64**, not packaging, asar-packing, or DMG creation.

---

## 4. Root Cause Analysis

### What electron-builder does during signed builds

1. Copies app bundle to `release/mac/QMatSuite.app`
2. Copies `extraResources` (runtime, engines, libraries) into `QMatSuite.app/Contents/Resources/`
3. **Deep-codesigns every Mach-O binary** in the app bundle (`codesign --deep --force --sign`)
4. Creates DMG from signed app

### Why x64 full is catastrophically slow

The full build stages into `gui/engines/` and `gui/libraries/`:
- **QE 7.5 binary bundle**: `bin/` (pw.x, ph.x, pp.x, bands.x, etc.) + `lib/` (dozens of .dylib shared libraries) — hundreds of Mach-O files
- **SSSP 1.3.0 pseudopotentials**: ~150 `.UPF` files + JSON metadata — data files, not Mach-O

electron-builder calls `codesign` on every file it discovers in the .app bundle. While `.UPF` data files are skipped by codesign (not Mach-O), the QE binary bundle contains many executables and shared libraries that each require individual signing.

**The performance cliff on `macos-15-intel`**:
- arm64 adds engines/libraries with barely any timing impact (20 min lite → 20 min full)
- x64 shows massive degradation (47 min lite → >313 min full, >6.7x)
- This suggests the Intel runner has severely degraded `codesign` performance, possibly due to:
  - **Rosetta2 overhead**: `macos-15-intel` may run on Apple Silicon via Rosetta, making cryptographic operations in `codesign` extremely slow
  - **Older/weaker hardware**: Intel CI runners have slower single-thread performance than M-series
  - **Disk I/O bottleneck**: Sequential `codesign` calls on many files amplify I/O latency

### Why the lite build also differs (20 min arm64 vs 47 min x64)

The lite build only contains the Python runtime (~526 MB, ~20k files after stripping). The runtime includes many `.so`/`.dylib` files from Python packages (numpy, scipy, etc.) that all need codesigning. The 2.3x slowdown on x64 for lite is consistent with general runner performance difference. The >15x slowdown for full suggests the QE binary bundle specifically triggers pathological signing behavior on the Intel runner.

---

## 5. Observations from CI Logs

From the x64 job output:
```
• file source doesn't exist  from=.../gui/engines    ← lite build (expected, engines not staged yet)
• file source doesn't exist  from=.../gui/libraries  ← lite build (expected, libraries not staged yet)
• skipped macOS notarization  reason=`notarize` options were unable to be generated
```

The "skipped notarization" message is from electron-builder's built-in notarization (which we don't use — we use `xcrun notarytool` separately). This is harmless.

---

## 6. Recommendations

### R1: Use `signIgnore` for vendored engine binaries (preferred)

electron-builder supports `mac.signIgnore` to skip codesigning specific paths within the app bundle. QE binaries are vendored third-party assets — our Developer ID signature on the outer `.app` wrapper is sufficient for Gatekeeper.

```json5
"mac": {
  "signIgnore": [
    "engines/**",
    "libraries/**"
  ]
}
```

**Pros**: Simple config change, works for all architectures, no workflow changes needed.
**Cons**: QE binaries inside the .app won't have our signature (but they don't need it — Gatekeeper checks the outer bundle).

### R2: Split variant by architecture

Only build `full` on arm64, only build `lite` on x64. Intel Mac users install QE separately.

```yaml
matrix:
  include:
    - os: macos-14
      arch: arm64
      variant_override: both      # arm64 builds lite + full
    - os: macos-15-intel
      arch: x64
      variant_override: lite      # x64 builds lite only
```

**Pros**: Eliminates the problem entirely. x64 lite completes in ~47 min.
**Cons**: No full DMG for Intel users. Reduces product offering.

### R3: Pre-sign QE in the toolchain build

Sign QE binaries with our Developer ID during the toolchain CI (in `qmatsuite-toolchain`), then mark them as already-signed so electron-builder skips re-signing.

**Pros**: QE binaries carry our signature.
**Cons**: More complex toolchain CI. Need to pass signing identity to toolchain repo.

### R4: Increase job timeout (band-aid)

```yaml
jobs:
  build-macos:
    timeout-minutes: 480   # 8 hours
```

**Pros**: Might let the build complete.
**Cons**: Wastes CI minutes. x64 full might need 8-10h. Does not fix the root cause.

---

## 7. Recommended Action Plan

1. **Immediate**: Apply R1 (`signIgnore` for engines/libraries). Re-run #27 to verify.
2. **Validate**: Confirm the resulting DMG passes Gatekeeper (`spctl --assess --type execute --verbose`).
3. **If Gatekeeper rejects**: Fall back to R2 (split variant by arch).
4. **Long-term**: Evaluate whether Intel Mac support justifies full builds, given Apple's transition to Apple Silicon.

---

## 8. Files Involved

| File | Role |
|------|------|
| `.github/workflows/release-macos.yml` | Workflow definition, matrix, build steps |
| `gui/electron-builder.json5` | electron-builder config, extraResources, signing |
| `gui/package.json` | Version, build scripts |
| `gui/electron/main.ts` | Engine/library staging on first launch |
