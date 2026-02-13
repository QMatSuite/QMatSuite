# ParamSpace / Preset / IR Specification

**Status**: FINAL (binding law)
**Version**: 1.0
**Date**: 2026-02-03
**Parent Law**: `CONSTITUTION.md` §8

---

## Overview

This spec defines the detailed mechanics of the ParamSpace framework. The high-level invariants are in the central constitution §8; this document provides the complete definition.

**Extracted from**: CONSTITUTION.md v1.2 §10 (ParamSpace / Preset Apply / Invariant Enforcement)

---

## 1. Non-Entity Principle

Workflow and preset are NOT first-class entities. They MUST NOT persist on the filesystem. They are:
- Runtime interpretation of the current step DAG
- Forward generation and reverse interpretation of step parameter sets

## 2. Compiler (Forward Generation)

### 2.1 Definition
Compiler is a pure function family: `compile_one(step_type, options) -> full_parameter_dict`

### 2.2 Input Independence
Compiler MUST NOT depend on: step topology/DAG, workflow, structure, pseudopotential, calc state.

Compiler MAY only depend on: step_type, user options (spin/soc/material/accuracy).

**Exception**: Precision resolver may depend on context (structure/pseudo) through named resolvers that are pure functions with contract tests.

### 2.3 Local Precise Modification
Preset Apply MUST be a local precise modification: only modify keys explicitly declared by the dimension's ParamSpace Variant. All parameters not owned by that preset dimension MUST remain unchanged.

### 2.4 Canonical Encoding
Compiler output MUST use canonical parameter representation, explicitly writing all key parameters. MUST NOT depend on defaults.

## 3. Detector (Reverse Detection)

### 3.1 Sole Authority
Detector B is the ONLY legal source of preset/option state determination. UI MUST NOT display state based on user "selection history".

### 3.2 No A Principle
No "Selected vs Detected" dual-track state model exists. All state is inferred by Detector B from step parameters in real-time.

### 3.3 Per-Dimension Detection
For each preset dimension d:
1. Select relevant step set R_d
2. Extract value v_d(step) from each step (with implicit default semantics per §3.4)
3. Construct set V = unique(v_d(step) for step in R_d)
4. If |V| == 1 → Detected = that unique value
5. If |V| > 1 → Detected = Custom

No Unknown state exists.

### 3.4 Implicit Default Semantics
Detector MUST support reverse interpretation of implicit defaults. Example: missing `nspin` → interpret as `nonspin` (= `nspin = 1`).

## 4. Compiler/Detector Equivalence

### 4.1 For Compiler Output (Strict)
`detect(compile_one(step_type, options))` MUST equal the options value for that dimension.

### 4.2 For Non-Compiler Output (Tolerant)
Detector allows more tolerant semantic inference based on implicit defaults.

### 4.3 No Guessing
When key parameters are missing and no reliable implicit default exists → Detector MUST return CUSTOM. Guessing based on "most likely value" / "common value" / "historical experience" is FORBIDDEN.

## 5. ParamSpace Declaration

### 5.1 Required Elements
Each preset dimension MUST declare a ParamSpace with:
- **keys**: Fixed ordered list of parameter keys
- **defaults**: Implicit default value dictionary
- **aliases/canonicalizers**: Synonym tables / normalization rules
- **profiles**: Full matrix of cells over keys (must be "full matrix" — all keys covered)
- **numeric tolerances**: E.g., float abs_tol

### 5.2 Cell Semantics (Three-State)
Each profile cell MUST be one of:
- **VALUE(v)**: Expected value; detect compares effective_value
- **NOT_APPLICABLE**: Key MUST NOT be present; apply MUST delete
- **WILDCARD**: Key not participating in matching; apply leaves unchanged

### 5.3 present vs effective_value
Detect MUST distinguish:
- **present**: Whether YAML explicitly contains the key (boolean)
- **effective_value**: If present → YAML value; else → defaults value; then canonicalize

Matching rules:
- VALUE: Compare effective_value (with canonicalize/tolerance)
- NOT_APPLICABLE: present MUST be False
- WILDCARD: Not checked

### 5.4 explicit_defaults Switch
`apply(profile, explicit_defaults=True|False)`:
- VALUE + True: Always write (even if value == default)
- VALUE + False: If value == default, don't write (rely on implicit default)
- NOT_APPLICABLE: Always delete
- WILDCARD: Don't touch

**Policy**: Production compiler MUST use `explicit_defaults=True` by default.

## 6. Single-Writer Principle

Every YAML key can only be written/deleted by ONE ParamSpace. Any "multiple ParamSpaces managing the same key" design is illegal.

**Semantic ownership ≠ write ownership**: E.g., degauss semantically depends on occupation, but writer ownership belongs to precision.

## 7. ParamSpace Unified Responsibility Model

Each ParamSpace MUST do exactly three things:

1. **Detect**: Use matrix to determine preset/CUSTOM; depends only on YAML truth + Oracle (read-only)
2. **Preset Apply**: Only when user explicitly selects preset; uses same matrix to write values
3. **Custom Apply (Invariant Enforcement)**: Always executes; maintains key domain invariants even for CUSTOM. Default is no-op.

CUSTOM ≠ "do nothing" is FORBIDDEN as implicit assumption.

## 8. Oracle

Oracle provides "semantic prerequisites" only. Oracle MUST:
- Be read-only
- Return only small discrete values (bool / small enum)
- NOT return preset id or "suggested values"
- Read only YAML truth (current in-memory state), NOT preset intention

## 9. Apply Execution Order

1. **Prerequisite ParamSpaces**: Those that change applicability (e.g., occupation, step_type)
2. **Dependent ParamSpaces**: Those that depend on Oracle (e.g., precision)

## 10. Key Access Rules

### 10.1 ParamSpace Key Access
Any ParamSpace can only access: its own declared owned keys + Oracle-exposed semantic prerequisites.

FORBIDDEN: Direct read, indirect read, or derived-state access of other ParamSpaces' owned keys.

### 10.2 Key Ownership Uniqueness (Runtime Enforced)
Any YAML key MUST be owned by exactly one ParamSpace. Overlap → system MUST fail at initialization. Cannot be downgraded to warning.

### 10.3 Non-YAML Inputs
Structure, pseudo, derived cutoff are read-only external facts. Not part of ParamSpace key space. Not subject to key-access rules.

## 11. Variant Scope

Each ParamSpace Variant MUST explicitly declare `applies_to_step_types`. Apply/detect only acts on steps in that list; others are N/A.

No overlap: same (dimension, step_type) MUST NOT be covered by multiple variants.

## 12. Contract Tests (Required)

Each preset space MUST have roundtrip contract tests covering:
1. For each profile: apply → detect must hit same profile
2. For NOT_APPLICABLE: forcing that key present → detect must become CUSTOM
3. For aliases: synonym spellings must detect to same profile

## 13. Precision Specifics

- ecut/kmesh are context-dependent; profiles store "strategy parameters" (multiplier/delta_k/conv_thr)
- bands_pw precision variant MUST exclude K_POINTS (belongs to kpath semantic)
- Regression test required: applying precision to bands_pw MUST NOT change kpath K_POINTS

## 14. Zero Technical Debt

No "backward compatibility for two YAML representations". Non-conforming old representations must use one-time migration. No silent runtime fallback to old format.

---

**End of ParamSpace Spec**
