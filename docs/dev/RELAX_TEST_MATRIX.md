# RELAX Test Matrix

**Date**: 2026-01-18
**Status**: IN PROGRESS

---

## 3.1 Unit Tests

| Test Name | Step List | Family | Mode | Expected | Key Assertions |
|-----------|-----------|--------|------|----------|----------------|
| `test_qc_topo_verify_scf_then_tddft_valid` | `[scf, tddft]` | ORCA | run_calc | Success | No error raised |
| `test_qc_topo_verify_scf_relax_scf_mp2_valid` | `[scf, tddft, relax, scf, mp2]` | ORCA | run_calc | Success | Chains: [scf,tddft], [relax], [scf,mp2] |
| `test_qc_topo_verify_scf_relax_tddft_invalid` | `[scf, relax, tddft]` | ORCA | run_calc | TopologyError | Error contains "blocked by relax" |
| `test_qc_topo_verify_relax_tddft_invalid` | `[relax, tddft]` | ORCA | run_calc | TopologyError | Error contains "no SCF root" |
| `test_qc_topo_verify_scf_mp2_relax_scf_relax_mp2_invalid` | `[scf, mp2, relax, scf, relax, mp2]` | ORCA | run_calc | TopologyError | Last mp2 blocked by relax |
| `test_qc_run_step_relax_executes_only_relax` | `[scf, relax, tddft]` | ORCA | run_step(relax) | Success | Only relax step executed |
| `test_qc_run_step_tddft_across_relax_error` | `[scf, relax, tddft]` | PySCF | run_step(tddft) | TopologyError | Error raised before execution |
| `test_qe_topo_no_block` | `[scf, relax, nscf]` | QE | run_calc | Success (warn) | All steps execute, warning logged |
| `test_relax_success_writes_current_json` | `[relax]` | QE | run_calc | Success | `current.json` exists, valid structure |
| `test_relax_failure_no_current_json` | `[relax]` | QE | run_calc | Fail | `current.json` does NOT exist |
| `test_relax_job_clears_only_covered_steps` | `[relax1, scf, relax2]` | QE | run_step(relax1) | Success | Only relax1's current.json cleared, relax2's preserved |
| `test_missing_current_json_hard_error` | `[relax, scf(uses effective)]` | QE | run_calc | Error | Error contains "MISSING_ARTIFACT" |
| `test_effective_structure_in_memory_update` | `[relax, scf]` | QE | run_calc | Success | SCF uses relaxed structure (mock engine) |
| `test_promote_creates_new_resource` | N/A | N/A | API call | Success | New structure ULID created, provenance set |
| `test_promote_requires_current_json` | N/A | N/A | API call | Error | "current.json missing" error |
| `test_promote_requires_relax_step` | `[scf]` | N/A | API call | Error | "not a relax step" error |
| `test_canonicalize_relax_output_matches_init` | N/A | N/A | Unit | N/A | Same canonicalize function used for both |
| `test_effective_structure_sha_in_manifest` | `[relax, scf]` | QE | run_calc | Success | Manifest entries have `effective_structure_sha` |
| `test_incremental_skip_with_changed_effective_structure` | `[relax, scf]` | QE | run_calc×2 | Skip logic | Second run: relax skipped, scf re-runs if relax output changed |

## 3.2 Integration Tests

| Test Name | Description | Key Assertions |
|-----------|-------------|----------------|
| `test_qe_vc_relax_e2e` | Full QE vc-relax with structure extraction | Output parsed, current.json created, structure valid |
| `test_qe_relax_then_scf` | relax → scf with effective structure | SCF input uses relaxed coordinates |
| `test_orca_relax_standalone` | ORCA relax (opt) as standalone job | current.json created, chain isolation maintained |
| `test_promote_then_use_in_new_calc` | Promote relaxed structure, use in new calc | New structure ULID works, provenance traceable |
| `test_resume_after_relax_success` | Start run, relax succeeds, crash, resume | current.json read on resume, effective structure correct |
| `test_daemon_promote_rpc` | Daemon RPC for promote | Response contains new structure ULID |

