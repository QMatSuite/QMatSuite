# ARCHIVED / OBSOLETE - Previous GEN/SPEC Implementation Plan

---

## STATUS: ROLLED BACK

**Date archived**: 2026-01-29
**Reason**: Semantic explosion from GEN/SPEC/id/public conflicts
**Action**: Repository rolled back to last fully-green commit

---

## DO NOT IMPLEMENT

The file `docs/GEN_SPEC_SEMANTICS_IMPLEMENTATION_PLAN.md` describes an **OBSOLETE** implementation plan that was **ROLLED BACK** due to fundamental semantic conflicts.

**Use instead**:
- `docs/GEN_SPEC_SEMANTICS_REVIEW.md` (updated vocabulary audit)
- `docs/GEN_SPEC_CONVERGENCE_IMPLEMENTATION_PLAN.md` (new 11-phase plan)

---

## Why Rolled Back

### The Semantic Explosion Problem

The previous implementation attempted to converge step-type vocabulary while preserving backward compatibility with **four conflicting semantic layers**:

| Term | Intended Meaning | Actual Usage | Conflict |
|------|------------------|--------------|----------|
| `id` | Public/GEN type | Registry indexing, tests | Confused with ULID identifiers |
| `public_type` | Public/GEN type | Same as `id` | Redundant alias |
| `machine_type` | SPEC type | step.yaml storage | Correctly defined |
| `type` (RPC field) | Varies | Sometimes GEN, sometimes SPEC | Ambiguous |

### Key Problems

1. **StepTypeSpec has THREE overlapping fields**: `id`, `public_type`, `machine_type`
   - `id` and `public_type` are supposed to be identical (both GEN)
   - This created confusion about which field to use where

2. **`id` is a terrible name for GEN**: It collides with:
   - `step_id` (ULID identifier)
   - `calculation_id`
   - Generic "id" fields in RPC responses

3. **DriverRegistry indexes by `spec.id`**: This made it seem like `id` is a special key, when it's really just GEN

4. **`public` / `public_type` naming is confusing**: "Public" suggests external API exposure, not "generalized/user-facing"

5. **The RPC `type` field was ambiguous**: Sometimes it held GEN values (`"scf"`), sometimes SPEC values (`"qe_scf"`)

### The Double-Truth Problem

The previous implementation created "double truths" where:
- Some code paths treated `spec.id` as the canonical GEN type
- Other code paths treated `spec.public_type` as the canonical GEN type
- Some RPC responses used `type` for GEN
- Other RPC responses used `type` for SPEC
- Golden fixtures were inconsistent

This made it impossible to confidently reason about what format any given field contained.

---

## What Replaces This

A new, narrower convergence plan is documented in:

- `docs/GEN_SPEC_SEMANTICS_REVIEW.md` (updated vocabulary audit)
- `docs/GEN_SPEC_CONVERGENCE_IMPLEMENTATION_PLAN.md` (new mechanical plan)

The new approach:
1. Converges to **exactly two terms**: `GEN` and `SPEC`
2. Eliminates `id`/`public`/`public_type`/`public_key` step-type semantics entirely
3. Defines clear, unambiguous field names for RPC contracts
4. Does NOT rename any GEN string values (e.g., "bands" stays "bands")

---

## Files to Ignore (Obsolete)

The following content in these docs is **OBSOLETE** and should not be referenced for implementation:

- `docs/GEN_SPEC_SEMANTICS_IMPLEMENTATION_PLAN.md` - **ENTIRE FILE OBSOLETE**
  - All 8 phases described are superseded
  - The golden fixture patching strategy is invalid
  - The GUI update approach created semantic confusion

- `docs/GEN_SPEC_SEMANTICS_REVIEW.md` (prior to 2026-01-29 update)
  - The "Laws" are still valid in spirit but need re-specification
  - The file/line references may be stale after rollback

---

## Lessons Learned

1. **Do not preserve backward-compatible aliases**: They create double-truths
2. **Do not have multiple field names for the same semantic concept**: Pick ONE name
3. **Do not conflate "id" with step type semantics**: It collides with actual identifiers
4. **Clean convergence > gradual migration**: Rip off the band-aid

---

## Contact

If you need to understand the context of the rollback, see:
- Git commit history for the rollback commit
- `docs/GEN_SPEC_CONVERGENCE_IMPLEMENTATION_PLAN.md` for the new approach
