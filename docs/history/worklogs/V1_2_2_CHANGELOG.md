# v1.2.2 Changelog

**Date**: 2026-02-26
**Branch**: `v2-python`
**Type**: Bug fix and performance release

---

## Bug Fixes

### Critical
- **P27** — Fix SSSP `.to_dict()` serialization in `_handle_get_library_status` (`25064766`)
- **P32** — Fix demo gallery missing 17 demos on Windows due to UTF-8 encoding (`f8c6326a`)
- **P1** — Disable differential download in auto-updater to fix update failures (`4386e192`)
- **P35** — Persist engine discovery results (`discover(persist=True)`) so bundled QE is retained across sessions (`bc2025a3`)
- **P6** — Fix element name detection ("titanium" -> "Ti") in OPTIMADE formula normalization (`08471340`)
- **P10** — Rebuild species_map and auto-match SSSP pseudopotentials after structure change (`972707b1`)

### High
- **P20/P21** — Fix raw output path showing only filename instead of relative path (`b46ea0ee`)
- **P9** — Refresh structure list after creating a calculation (`af971abb`)

### Medium
- **P3** — Show dynamic app version in sidebar instead of hardcoded "v2.0.0" (`fa06dfeb`)
- **P4** — Replace QE-centric welcome text with engine-agnostic wording (`8a3b9f3f`)
- **P5** — Hide Volume (DEV) sidebar item in production builds (`85e98c5a`)
- **P2** — Show "Up to date" banner for `not-available` state, auto-dismiss after 5s (`5c7fc22d`)
- **P23** — Sanitize home-directory paths in Settings UI to prevent username leaks in screenshots (`1578fc5b`)
- **P12** — Add `[GEN_TYPE]` prefix to Add Step dropdown labels for clarity (`4c42584a`)
- **P13** — Collapse secondary digest fields behind expandable toggle to reduce vertical space (`a8e4a7c7`)
- **P14** — Auto-switch to Plot tab when analysis data is available for a step (`04c9f048`)

## Performance

- **P30** — Lazy-load OPTIMADE registry: return curated defaults instantly on startup, fetch only on explicit refresh (`92bd04db`)
- **P29** — Persist matplotlib font cache via `MPLCONFIGDIR` to avoid 30s+ rebuild on cold start (`8438d728`)
- **P31** — Fast-path `engine.list` from cached `engines.json`; full discovery only on Refresh or after install/uninstall (`b7ba0f89`)

## Not Included

- **P25** — macOS entitlements: blocked (requires `electron-builder.json5` change)
- **P33** — Demo "0 Si SCF": skipped per user request
- **P11** — SSSP library scan: no code changes needed (unblocked by P27 fix)

## Test Results

- **Python**: 6518 passed, 5 skipped
- **TypeScript**: tsc clean (0 errors)
- **Pre-existing failures**: VASP e2e (POTCAR issue), sensitive paths gate (review docs)
