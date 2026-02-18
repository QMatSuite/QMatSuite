# MCP Stage 8: QE Preflight + dry_run — Worklog

## Summary

Added QE-specific parameter validation (20 rules) and input-file dry-run
materialization to the MCP tool layer. The agent can now catch common
parameter mistakes before wasting compute and preview exact input files.

## Deliverables

### New Files (2)

| File | Lines | Purpose |
|------|-------|---------|
| `src/quantumvitas/drivers/qe/preflight.py` | ~250 | QEPreflightChecker — 20 deterministic rules |
| `tests/mcp/test_stage8.py` | ~285 | 18 tests (12 unit + 3 dry_run + 3 integration) |

### Modified Files (4)

| File | Change |
|------|--------|
| `src/quantumvitas/core/driver_protocol.py` | Added `PreflightIssue` frozen dataclass (7 fields) + `get_preflight_checker()` on `BaseEngineDriver` |
| `src/quantumvitas/drivers/qe/driver.py` | Added `get_preflight_checker()` override (lazy import) |
| `src/quantumvitas/mcp/tools/inspect_calculation.py` | Added `dry_run` param + preflight integration |
| `src/quantumvitas/mcp/tools/preview_compilation.py` | Added preflight integration after compilation |

## Preflight Rules (20)

### Blocking (6)
| Code | Trigger |
|------|---------|
| MISSING_ECUTWFC | ecutwfc absent or <= 0 |
| MISSING_KPOINTS | No kpoints + periodic structure |
| INVALID_CALCULATION_TYPE | calculation not in valid set |
| NSCF_WITHOUT_SCF | nscf/bands without preceding scf |
| NEGATIVE_DEGAUSS | degauss < 0 |
| ZERO_NAT | nat explicitly 0 |

### Warning (8)
| Code | Trigger |
|------|---------|
| METAL_FIXED_OCC | Fixed occupations + metallic elements |
| SPIN_UNPOLARIZED_MAGNETIC | nspin=1 + magnetic elements |
| TETRAHEDRA_WITH_RELAX | Tetrahedra + relax/vc-relax/md |
| TETRAHEDRA_METALS | Tetrahedra + metallic elements |
| SMEARING_NO_DEGAUSS | Smearing without degauss |
| ECUTRHO_TOO_LOW | ecutrho < 4 * ecutwfc |
| VC_RELAX_FIXED_CELL | vc-relax + restricted cell_dofree |
| MD_NO_TEMPERATURE | MD without temperature |

### Advisory (6)
| Code | Trigger |
|------|---------|
| LOW_ECUTWFC | ecutwfc < 20 Ry |
| LOOSE_CONV_THR | conv_thr > 1e-4 |
| LOW_ELECTRON_MAXSTEP | electron_maxstep < 30 |
| GAUSSIAN_SMEARING_FOR_DOS | Gaussian smearing + dos workflow |
| LARGE_MIXING_BETA | mixing_beta > 0.7 |
| ECUTWFC_VERY_HIGH | ecutwfc > 200 Ry |

## Design Decisions

1. **PreflightIssue in driver_protocol.py** — protocol-level type alongside existing PreflightRequirement
2. **get_preflight_checker() on BaseEngineDriver** — follows get_input_spec/get_handler pattern (None default)
3. **Lightweight structure_info dict** — no pymatgen dependency in checker
4. **Cart→frac conversion** for dry_run uses numpy (frac = cart @ inv(lattice))
5. **Best-effort preflight** — wrapped in try/except, never causes tool failure
6. **No kernel changes** — preflight.py is a leaf file in drivers/qe/

## Test Results

```
tests/mcp/test_stage8.py — 18 passed
tests/mcp/ (all) — 120 passed
tests/ (full suite) — 5780 passed, 0 failed, 4 skipped
```

## Cumulative MCP Stats

| Stage | Tools | Tests | Total Suite |
|-------|-------|-------|-------------|
| 0-7 | 18 | 102 | 5762 |
| 8 | 18 (+0 tools, +2 features) | 120 (+18) | 5780 (+18) |
