# LAMMPS Long Smoke Test - Evidence Checklist

> **Purpose**: Checklist for Auto to submit after executing LAMMPS long smoke tests.
> Each workflow MUST have evidence attached for verification.

---

## Pre-Run Evidence (Required)

### Environment Verification
- [ ] **Python version**: `python --version` output
- [ ] **QMatSuite import**: `python -c "import qmatsuite"` success/failure
- [ ] **LAMMPS binary path**: output of resolver check
- [ ] **LAMMPS version**: first 5 lines of `lmp -h`

**Evidence Format**:
```
=== PRE-RUN CHECKS ===
Python: 3.11.5
QMatSuite: /path/to/qmatsuite/__init__.py
LAMMPS binary: /opt/homebrew/opt/lammps/bin/lmp
LAMMPS version: LAMMPS (2 Aug 2023)
```

---

## Workflow A: LJ Relax

### Checkpoints
| # | Checkpoint | Pass/Fail | Notes |
|---|------------|-----------|-------|
| A1 | `in.lammps` exists | | |
| A2 | `in.lammps` contains `pair_style lj/cut` | | |
| A3 | `structure.data` exists | | |
| A4 | `log.lammps` exists, no ERROR | | |
| A5 | `final.data` exists | | |
| A6 | `dump.lammpstrj` exists | | |
| A7 | `generated_structures/step_<ulid>/current.json` exists | | |

### Required Evidence
```
=== WORKFLOW A: LJ RELAX ===
Step ULID: <ulid>
Working dir: <path>

File listing:
<output of: ls -la raw/<step_ulid>/>

in.lammps pair_style:
<output of: grep pair_style raw/<step_ulid>/in.lammps>

Log tail (last 20 lines):
<output of: tail -20 raw/<step_ulid>/log.lammps>

Artifact exists:
<output of: ls -la generated_structures/step_<ulid>/current.json>

RESULT: PASS/FAIL
```

---

## Workflow B: EAM MD

### Checkpoints
| # | Checkpoint | Pass/Fail | Notes |
|---|------------|-----------|-------|
| B1 | Potential staged: `raw/<ulid>/potentials/Cu_u3.eam` | | |
| B2 | `in.lammps` contains correct `pair_style eam` | | |
| B3 | `in.lammps` contains correct `pair_coeff` with potential path | | |
| B4 | `log.lammps` exists, no ERROR | | |
| B5 | `dump.lammpstrj` has multiple frames | | |
| B6 | Log shows completion (wall time) | | |

### Required Evidence
```
=== WORKFLOW B: EAM MD ===
Step ULID: <ulid>
Working dir: <path>

Potential staging:
<output of: ls -la raw/<step_ulid>/potentials/>

pair_style:
<output of: grep pair_style raw/<step_ulid>/in.lammps>

pair_coeff:
<output of: grep pair_coeff raw/<step_ulid>/in.lammps>

Dump frame count:
<output of: grep -c "ITEM: TIMESTEP" raw/<step_ulid>/dump.lammpstrj>

Log tail:
<output of: tail -30 raw/<step_ulid>/log.lammps>

RESULT: PASS/FAIL
```

---

## Workflow C: Chain (Relax → MD)

### Checkpoints
| # | Checkpoint | Pass/Fail | Notes |
|---|------------|-----------|-------|
| C1 | Relax step produces `final.data` | | |
| C2 | Relax produces `current.json` artifact | | |
| C3 | MD step uses relax output (check `in.lammps`) | | |
| C4 | MD atom count matches relax | | |
| C5 | Both steps complete without ERROR | | |

### Required Evidence
```
=== WORKFLOW C: CHAIN ===
Relax Step ULID: <ulid1>
MD Step ULID: <ulid2>

Relax outputs:
<output of: ls -la raw/<relax_ulid>/>

MD inputs (first 30 lines):
<output of: head -30 raw/<md_ulid>/in.lammps>

Artifact check:
<output of: ls generated_structures/step_<relax_ulid>/>

Relax log tail:
<output of: tail -10 raw/<relax_ulid>/log.lammps>

MD log tail:
<output of: tail -10 raw/<md_ulid>/log.lammps>

RESULT: PASS/FAIL
```

---

## Workflow D: Restart_from (MD → MD restart)

### Checkpoints
| # | Checkpoint | Pass/Fail | Notes |
|---|------------|-----------|-------|
| D1 | First MD produces `restart.bin` or `restart.final.bin` | | |
| D2 | Second MD's `in.lammps` contains `read_restart` | | |
| D3 | Second MD log shows restart read success | | |
| D4 | All three steps complete without ERROR | | |

### Required Evidence
```
=== WORKFLOW D: RESTART ===
Relax Step ULID: <ulid1>
MD1 Step ULID: <ulid2>
MD2 Step ULID: <ulid3>

Restart files from MD1:
<output of: ls -la raw/<md1_ulid>/restart*>

MD2 in.lammps (first 20 lines):
<output of: head -20 raw/<md2_ulid>/in.lammps>

Restart grep:
<output of: grep -i restart raw/<md2_ulid>/log.lammps | head -5>

MD2 log tail:
<output of: tail -20 raw/<md2_ulid>/log.lammps>

RESULT: PASS/FAIL
```

---

## Summary

```
=== LAMMPS LONG SMOKE TEST SUMMARY ===
Date: <ISO timestamp>
Duration: <total time>

Workflow A (LJ Relax):      PASS/FAIL
Workflow B (EAM MD):        PASS/FAIL
Workflow C (Chain):         PASS/FAIL
Workflow D (Restart):       PASS/FAIL

Overall:                    PASS/FAIL

Notes:
<any additional observations>
```

---

## Failure Mode Evidence

If any workflow fails, MUST include:

### Binary Resolution Failure
```
=== BINARY RESOLUTION FAILURE ===
Resolver error: <error message>

Search paths:
<output of resolver debug>

Manual checks:
<output of: ls -la /opt/homebrew/opt/lammps/bin/>
<output of: which lmp lmp_serial>
```

### Execution Failure
```
=== EXECUTION FAILURE ===
Failed workflow: <A/B/C/D>
Failed step: <ulid>

Full log:
<output of: cat raw/<step_ulid>/log.lammps>

Input script:
<output of: cat raw/<step_ulid>/in.lammps>

Data file header:
<output of: head -50 raw/<step_ulid>/structure.data>

Directory tree:
<output of: ls -laR raw/<step_ulid>/>
```

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-01-20 | Auto | Initial checklist created |

