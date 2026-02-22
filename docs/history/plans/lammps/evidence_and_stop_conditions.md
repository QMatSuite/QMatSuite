# Evidence Collection and Stop Conditions

**Version**: 1.0.0  
**Date**: 2026-01-20  
**Status**: Required Protocol for Auto Execution  
**Purpose**: Define when Auto must stop and what evidence to collect

---

## 1. Overview

This document defines the mandatory stop conditions for Cursor Auto during LAMMPS implementation. When Auto encounters any of these conditions, it MUST:

1. **STOP** - Do not attempt to continue or guess
2. **COLLECT** - Gather the specified evidence
3. **REPORT** - Present findings and wait for user guidance

**Principle**: Better to stop early with good evidence than to propagate errors.

---

## 2. Stop Condition Categories

| Category | Severity | Action |
|----------|----------|--------|
| **HARD STOP** | Critical | Halt all work; escalate immediately |
| **SOFT STOP** | Blocking | Stop current task; attempt documented workaround |
| **WARN** | Advisory | Log and continue; note in PR |

---

## 3. Phase 0: Asset Acquisition Stop Conditions

### 3.1 Potential File Not Redistributable

**Trigger**: Cannot find EAM/Tersoff potential with clear GPL/open license.

**Evidence to Collect**:
```markdown
## Potential File License Issue

### Source Attempted
- URL: {url}
- File: {filename}

### License Found
- License text or reference: {text}
- Concern: {why this is problematic}

### Alternative Attempted
- {what else was tried}

### Proposed Resolution
- [ ] Use LAMMPS repo files only (GPL-2.0)
- [ ] Runtime download with hash verification
- [ ] Request user guidance on specific file
```

**Classification**: SOFT STOP - try LAMMPS repo files first.

### 3.2 Brew Install Path Changed

**Trigger**: `/opt/homebrew/opt/lammps/bin/` does not exist or has different structure.

**Evidence to Collect**:
```bash
# Run these commands and capture output:
brew info lammps
brew --prefix lammps
ls -la $(brew --prefix lammps)/bin/ 2>&1
which lmp lmp_serial lmp_mpi 2>&1
```

**Classification**: SOFT STOP - document new paths and update resolver.

### 3.3 Ubuntu Package Name Changed

**Trigger**: `apt install lammps` fails or package name different.

**Evidence to Collect**:
```bash
apt-cache search lammps
apt-cache policy lammps
apt-cache policy lammps-data
dpkg -L lammps 2>&1 | head -20
```

**Classification**: SOFT STOP - find correct package name.

---

## 4. Phase 1: Engine Registration Stop Conditions

### 4.1 Base Engine API Mismatch

**Trigger**: `Engine` base class has different method signatures than expected.

**Evidence to Collect**:
```python
# Capture current Engine base class
from qmatsuite.engine.base import Engine
import inspect

print("Engine methods:")
for name, method in inspect.getmembers(Engine, predicate=inspect.isfunction):
    sig = inspect.signature(method)
    print(f"  {name}{sig}")
```

**Classification**: HARD STOP - need to understand API changes.

### 4.2 Registry Pattern Changed

**Trigger**: `EngineRegistry` has different registration pattern.

**Evidence to Collect**:
```python
from qmatsuite.engine.registry import EngineRegistry, create_default_registry
import inspect

print("EngineRegistry methods:")
print(inspect.getsource(EngineRegistry.register))

print("\ncreate_default_registry:")
print(inspect.getsource(create_default_registry))
```

**Classification**: HARD STOP - registry is core infrastructure.

### 4.3 Workflow Registry Schema Changed

**Trigger**: `StepTypeSpec` has different fields than expected.

**Evidence to Collect**:
```python
from qmatsuite.workflow.registry import StepTypeSpec
from dataclasses import fields

print("StepTypeSpec fields:")
for f in fields(StepTypeSpec):
    print(f"  {f.name}: {f.type}")
```

**Classification**: HARD STOP - affects step type registration.

---

## 5. Phase 2: Materialize Stop Conditions

### 5.1 Structure I/O Format Mismatch

**Trigger**: Cannot convert QMatSuite structure to LAMMPS data format.

**Evidence to Collect**:
```markdown
## Structure Conversion Error

### Input Structure
- Type: {type(structure)}
- Attributes: {dir(structure)}
- Sample: {structure.as_dict() or repr(structure)[:500]}

### Expected Format
- LAMMPS data file with: {expected sections}

### Error
{traceback}

### Proposed Resolution
- {what format adapter is needed}
```

**Classification**: SOFT STOP - may need format adapter.

### 5.2 Template Rendering Error

**Trigger**: Jinja2 template syntax error or missing variable.

**Evidence to Collect**:
```markdown
## Template Error

### Template File
{template_path}

### Template Content (relevant section)
```
{template_content[:500]}
```

### Variables Provided
{json.dumps(variables, indent=2)}

### Error
{jinja2_error}
```

**Classification**: SOFT STOP - fix template.

### 5.3 Potential Map Schema Conflict

**Trigger**: Existing calculation.yaml has conflicting `potential_map` usage.

**Evidence to Collect**:
```markdown
## Schema Conflict

### Existing calculation.yaml example
{yaml content}

### Expected Schema
{our schema}

### Conflict
{what's different}
```

**Classification**: HARD STOP - need schema alignment discussion.

---

## 6. Phase 3: Run & Parse Stop Conditions

### 6.1 LAMMPS Binary Not Found

**Trigger**: `resolve_lammps_bin()` cannot find any LAMMPS executable.

**Evidence to Collect**:
```bash
# Collect environment info:
echo "=== PATH ==="
echo $PATH | tr ':' '\n'

echo "=== LAMMPS search ==="
which lmp lmp_serial lmp_mpi lammps 2>&1

echo "=== Brew (if mac) ==="
brew list --versions lammps 2>&1

echo "=== Apt (if linux) ==="
dpkg -l | grep lammps 2>&1

echo "=== Conda ==="
conda list | grep lammps 2>&1

echo "=== Environment ==="
env | grep -i lammps 2>&1
```

**Classification**: SOFT STOP on dev machine, HARD STOP in CI.

### 6.2 LAMMPS Runtime Error

**Trigger**: LAMMPS exits with non-zero code and ERROR in log.

**Evidence to Collect**:
```markdown
## LAMMPS Runtime Error

### Command
{command_line}

### Exit Code
{exit_code}

### Log (last 50 lines or error section)
```
{log_content}
```

### Input Script (relevant section)
```
{script_content}
```

### Working Directory Contents
{ls -la}
```

**Classification**: SOFT STOP - likely script generation bug.

### 6.3 Log Parse Failure

**Trigger**: Log parser cannot extract thermo data.

**Evidence to Collect**:
```markdown
## Log Parse Failure

### Log File
{log_path}

### Log Content (first 100 lines)
```
{log_content}
```

### Expected Format
Step Temp PotEng ...

### Parser Error
{error}

### Parser Code Location
{parser_function}
```

**Classification**: SOFT STOP - need to understand log format variant.

### 6.4 Dump Parse Failure

**Trigger**: Dump parser cannot read trajectory file.

**Evidence to Collect**:
```markdown
## Dump Parse Failure

### Dump File
{dump_path}
{file_size}

### Dump Content (first 50 lines)
```
{dump_content}
```

### Expected Format
ITEM: TIMESTEP
...
ITEM: ATOMS id type x y z ...

### Parser Error
{error}
```

**Classification**: SOFT STOP - need to understand dump format variant.

### 6.5 Units Conversion Error

**Trigger**: Unexpected unit system or conversion factor issue.

**Evidence to Collect**:
```markdown
## Units Conversion Error

### LAMMPS Units
{units_command from script}

### Value Being Converted
- Quantity: {quantity}
- Raw value: {raw_value}
- Expected canonical: {expected}
- Got: {actual}

### Conversion Used
{conversion_code}
```

**Classification**: SOFT STOP - verify conversion factors.

---

## 7. Phase 4: Integration Stop Conditions

### 7.1 Manifest Field Incompatibility

**Trigger**: Adding `potential_assets_sha` breaks existing manifest handling.

**Evidence to Collect**:
```markdown
## Manifest Compatibility Issue

### Current ManifestStepEntry Fields
{fields}

### Proposed Change
{change}

### Compatibility Concern
- Existing manifests have: {existing}
- New code expects: {expected}

### Migration Strategy Needed
{yes/no}
```

**Classification**: HARD STOP - manifest is critical infrastructure.

### 7.2 restart_from Resolution Ambiguity

**Trigger**: Cannot determine which artifact to use for restart.

**Evidence to Collect**:
```markdown
## Restart Resolution Ambiguity

### restart_from Reference
{reference}

### Upstream Step
{step info}

### Available Artifacts
{list of files}

### Ambiguity
- Multiple restart files exist: {list}
- Or no restart files exist: {empty list}

### Resolution Rule Needed
{what rule should apply}
```

**Classification**: SOFT STOP - need to clarify resolution order.

### 7.3 Cross-Calc Reference Detected

**Trigger**: `restart_from` references step in different calculation.

**Evidence to Collect**:
```markdown
## Cross-Calc Reference (Constitution Violation)

### Current Calculation
{calc_id}

### restart_from Reference
{reference}

### Referenced Step Location
{step location, different calc}

### Error Message Generated
{message}
```

**Classification**: This is expected behavior (hard error). Just verify error is clear.

---

## 8. Phase 5: CI Stop Conditions

### 8.1 CI LAMMPS Installation Fails

**Trigger**: brew/apt install fails in CI environment.

**Evidence to Collect**:
```markdown
## CI LAMMPS Install Failure

### CI Platform
{macos-latest / ubuntu-latest}

### Install Command
{command}

### Error Output
```
{error}
```

### Possible Causes
- [ ] Package name changed
- [ ] Network issue
- [ ] Dependency conflict
```

**Classification**: HARD STOP - cannot test without LAMMPS.

### 8.2 CI Test Timeout

**Trigger**: LAMMPS tests exceed reasonable time (>5 min).

**Evidence to Collect**:
```markdown
## CI Timeout

### Test
{test_name}

### Expected Duration
< 60 seconds

### Actual Duration
> 300 seconds (timed out)

### Possible Causes
- [ ] Test system too large
- [ ] Infinite loop in script
- [ ] CI runner performance issue
```

**Classification**: SOFT STOP - reduce test system size.

### 8.3 Test Results Differ Between Platforms

**Trigger**: Same test passes on mac, fails on ubuntu (or vice versa).

**Evidence to Collect**:
```markdown
## Platform Difference

### Test
{test_name}

### Mac Result
{pass/fail + details}

### Ubuntu Result
{pass/fail + details}

### LAMMPS Versions
- Mac: {version}
- Ubuntu: {version}

### Difference Analysis
{what's different}
```

**Classification**: SOFT STOP - may need platform-specific handling.

---

## 9. Evidence Collection Script

Auto should use this script to collect comprehensive evidence:

```python
#!/usr/bin/env python3
"""Collect LAMMPS integration debugging evidence."""

import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime

def collect_evidence(context: str) -> dict:
    """Collect comprehensive debugging evidence."""
    
    evidence = {
        "timestamp": datetime.now().isoformat(),
        "context": context,
        "python_version": sys.version,
        "platform": sys.platform,
    }
    
    # LAMMPS availability
    for cmd in ["lmp", "lmp_serial", "lmp_mpi"]:
        result = subprocess.run(["which", cmd], capture_output=True, text=True)
        if result.returncode == 0:
            evidence["lammps_binary"] = result.stdout.strip()
            
            # Get version
            ver = subprocess.run(
                [result.stdout.strip(), "-h"],
                capture_output=True, text=True
            )
            evidence["lammps_version"] = ver.stdout[:200]
            break
    else:
        evidence["lammps_binary"] = None
    
    # Environment
    import os
    evidence["env"] = {
        k: v for k, v in os.environ.items()
        if "LAMMPS" in k.upper() or "QMATS" in k.upper()
    }
    
    # Package versions
    try:
        import qmatsuite
        evidence["qmatsuite_version"] = getattr(qmatsuite, "__version__", "unknown")
    except ImportError:
        evidence["qmatsuite_version"] = "not installed"
    
    return evidence

def save_evidence(evidence: dict, path: Path):
    """Save evidence to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(evidence, f, indent=2)
    print(f"Evidence saved to: {path}")

if __name__ == "__main__":
    context = sys.argv[1] if len(sys.argv) > 1 else "manual collection"
    evidence = collect_evidence(context)
    print(json.dumps(evidence, indent=2))
```

---

## 10. Escalation Protocol

### 10.1 HARD STOP Escalation

When Auto hits a HARD STOP:

1. **Stop all LAMMPS-related work immediately**
2. **Collect evidence per this document**
3. **Create a markdown report**:

```markdown
## LAMMPS Integration: HARD STOP

### Phase
{phase number and name}

### Stop Condition
{which condition triggered}

### Evidence
{collected evidence}

### Impact
{what cannot proceed}

### Questions for User
1. {specific question}
2. {specific question}

### Proposed Next Steps (pending guidance)
- Option A: {option}
- Option B: {option}
```

4. **Present to user and WAIT**

### 10.2 SOFT STOP Escalation

When Auto hits a SOFT STOP:

1. **Document the issue**
2. **Attempt documented workaround if available**
3. **If workaround succeeds**: Continue, note in PR
4. **If workaround fails**: Escalate as HARD STOP

---

## 11. Recovery Procedures

### 11.1 After User Provides Guidance

1. **Document the resolution** in the plan
2. **Update this document** if new stop condition discovered
3. **Resume from the phase that was blocked**
4. **Verify resolution worked** before proceeding

### 11.2 Rollback if Needed

Each phase has documented rollback:

| Phase | Rollback |
|-------|----------|
| 0 | Delete `resources/lammps/` |
| 1 | Remove from registry; delete engine file |
| 2 | Delete templates, writer modules |
| 3 | Delete parser modules |
| 4 | Revert manifest changes |
| 5 | Disable CI jobs |

---

## 12. Checklist for Auto

Before starting each phase, Auto should verify:

- [ ] Previous phase completed successfully
- [ ] All tests from previous phase pass
- [ ] No unresolved stop conditions
- [ ] Required dependencies available
- [ ] Evidence collection script accessible

During each task, Auto should:

- [ ] Check for stop condition triggers frequently
- [ ] Collect evidence immediately when issues arise
- [ ] Not attempt to "work around" HARD STOPs
- [ ] Document all decisions in code comments or docs

After completing each phase, Auto should:

- [ ] Run all tests
- [ ] Verify no new stop conditions
- [ ] Update TODO list
- [ ] Prepare phase summary for user review

