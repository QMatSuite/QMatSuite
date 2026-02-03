# QMatSuite Governance Documents

**Last Updated**: 2026-02-03

---

## Document Hierarchy

| Level | Authority | Update Protocol |
|-------|-----------|----------------|
| **1. Central Constitution** | `CONSTITUTION.md` (repo root) | Author review required |
| **2. Governance Specs** | This folder (`docs/governance/`) | Must not contradict constitution; changes require updating constitution references if scope changes |
| **3. Implementation Docs** | `docs/` (non-governance) | Not binding; for reference only |

**Conflict resolution**: Higher-level document wins. If a governance spec contradicts the constitution, the constitution is authoritative.

**How to update without dual truths**: When changing a rule, update the authoritative source first (usually the governance spec), then update the constitution's summary of that rule to match. Never maintain the same rule in full detail in both places.

---

## Document Index

### Constitution (Highest Authority)

| Document | Status | Purpose | Last Updated |
|----------|--------|---------|-------------|
| [`CONSTITUTION.md`](../../CONSTITUTION.md) | **FINAL** (v2.1) | Central constitution — all high-level invariants (English) | 2026-02-03 |
| [`CONSTITUTION_ZH.md`](../../CONSTITUTION_ZH.md) | **DEPRECATED** | Former Chinese constitution; retained for reference only | 2026-02-03 |

### Governance Specs (Binding Laws)

| Document | Status | Governs | Constitution Reference | Last Updated |
|----------|--------|---------|----------------------|-------------|
| [`API_CONSTITUTION.md`](API_CONSTITUTION.md) | **FINAL** (v2.1) | API surface, import layering, utils policy, DTOs, errors, H9 filesystem control | Constitution §18 | 2026-02-02 |
| [`KERNEL_DEPENDENCY_SPEC.md`](KERNEL_DEPENDENCY_SPEC.md) | **PROPOSED** (v3.1) | Kernel 7-domain model, dependency DAG, SSOT writes, engine inputs | Constitution §19 | 2026-02-03 |
| [`KERNEL_EXCEPTIONS.md`](KERNEL_EXCEPTIONS.md) | **ACTIVE** (v3.1) | Approved exceptions to kernel dependency rules (EXC-001 through EXC-004) | Constitution §19 | 2026-02-03 |
| [`STEP_TYPE_GEN_SPEC_CONSTITUTION.md`](STEP_TYPE_GEN_SPEC_CONSTITUTION.md) | **FINAL** (v1.1) | GEN/SPEC step type namespaces, derivation rule, conversion API, execution layering | Constitution §7 | 2026-02-02 |
| [`ENGINE_INTEGRATION_CONSTITUTION.md`](ENGINE_INTEGRATION_CONSTITUTION.md) | **SPECIFICATION** (v1.0) | Engine integration invariants: no guessing, hard error, explicit mapping, driver self-containment | Constitution §17 | 2026-02-01 |
| [`PARAMSPACE_SPEC.md`](PARAMSPACE_SPEC.md) | **FINAL** (v1.0) | ParamSpace framework: compiler/detector equivalence, single-writer, cell semantics, Oracle | Constitution §8 | 2026-02-03 |
| [`ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md`](ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md) | **FINAL** (v1.0) | Engine recipe system, runner independence, recipe archetypes, directory contracts, bans | Constitution §17 | 2026-02-03 |

### Status Taxonomy

| Status | Meaning |
|--------|---------|
| **FINAL** | Binding law. Changes require constitution review. |
| **ACTIVE** | Binding but may evolve (e.g., exception lists). |
| **PROPOSED** | Under review; expected to become FINAL. |
| **SPECIFICATION** | Binding design spec; may be promoted to FINAL. |
| **DEPRECATED** | Kept for archaeology; NOT authoritative. Superseded doc is noted. |

---

## Cross-Reference: Invariants → Definitions → Gates

| Invariant | Constitution § | Governance Spec | Enforcement Gate(s) |
|-----------|---------------|-----------------|---------------------|
| **SSOT = calculation.yaml + step.yaml** | §2.1 | KERNEL_DEPENDENCY_SPEC §2.1 | `test_yaml_write_single_entry.py`, `test_yaml_read_single_entry.py` |
| **History world separation** | §3 | — | — (not yet gated) |
| **Concurrency: edit.lock + run.lock** | §4 | KERNEL_DEPENDENCY_SPEC §2.1 | — (runtime enforcement) |
| **Manifest = non-SSOT bookkeeping** | §5 | — | — |
| **ULID-only identity** | §6 | API_CONSTITUTION H7 | `test_no_legacy_identity_fields.py` |
| **GEN/SPEC step types** | §7 | STEP_TYPE_GEN_SPEC_CONSTITUTION | `test_step_type_constitution.py`, `test_no_bare_step_type.py`, `test_underscore_ban.py`, `test_no_manual_join_split.py`, `test_banned_legacy_aliases.py`, `test_no_third_namespace.py` |
| **Preset/ParamSpace non-persistence** | §8 | PARAMSPACE_SPEC | `test_no_spec_in_preset_layer.py` |
| **Species/pseudo SSOT** | §9 | — | — |
| **Scan rules (dict-leaf ban, @scan token)** | §10 | — | — |
| **Managed params UI read-only** | §11 | — | — |
| **A-class / B-class key typing** | §12 | PARAMSPACE_SPEC §5 | — |
| **RELAX = structure transformer** | §13 | — | — |
| **LAMMPS integration** | §14 | — | — |
| **Single canonicalization** | §15 | — | — |
| **QE internal storage (Å, frac)** | §16 | — | — |
| **Engine execution models** | §17 | ENGINE_INTEGRATION_CONSTITUTION | `test_registry_routing.py`, `test_no_fallbacks.py` |
| **Runner engine-agnosticism** | §17.4 | ENGINE_RECIPE_AND_RUNNER_CONSTITUTION §1 | — |
| **One engine → one recipe** | §17.4 | ENGINE_RECIPE_AND_RUNNER_CONSTITUTION §2 | — |
| **No scattered mapping dicts** | §17.4 | ENGINE_RECIPE_AND_RUNNER_CONSTITUTION §9.1 | — |
| **No runner engine imports** | §17.4 | ENGINE_RECIPE_AND_RUNNER_CONSTITUTION §9.2 | — |
| **No prefix inference** | §17.4 | ENGINE_RECIPE_AND_RUNNER_CONSTITUTION §9.3 | — |
| **API 3-layer import boundary** | §18 | API_CONSTITUTION H1 | `test_import_gate.py`, `test_daemon_kernel_ban.py`, `test_import_rules.py` |
| **Frontend no YAML write (H9)** | §18.4 | API_CONSTITUTION H9 | `test_frontend_no_yaml_write.py` |
| **Utils policy (default disallow)** | §18.2 | API_CONSTITUTION H2 | `test_no_service_delegating_utils.py` |
| **No stub service methods** | §18 | API_CONSTITUTION G4 | `test_no_stub_service_methods.py` |
| **Kernel → API reverse ban** | §19.1 | KERNEL_DEPENDENCY_SPEC K0 | `test_kernel_no_api_import.py`, `test_kernel_no_frontend_import.py` |
| **Engine no SSOT import** | §19 | KERNEL_DEPENDENCY_SPEC K6 | `test_engine_no_ssot_import.py` |
| **Resolution meta-only read** | §19.3 | KERNEL_DEPENDENCY_SPEC §2.2 | `test_resolution_meta_only.py` |
| **No legacy imports** | — | KERNEL_EXCEPTIONS EXC-003 | `test_no_legacy_imports.py` |
| **API surface accounting** | — | API_CONSTITUTION G1 | `test_api_surface_final.py` |
| **No conversion above kernel** | §7.3 | STEP_TYPE_GEN_SPEC_CONSTITUTION §4.7 | `test_step_type_cross_assignment.py` |
| **DTO must carry both step type fields** | §7.3 | STEP_TYPE_GEN_SPEC_CONSTITUTION §4.6 | `test_gen_spec_convergence_gate.py` |
| **GUI RPC wiring** | — | — | `test_gui_rpc_wiring.py` |
| **Single SSOT mapping** | §7.2 | STEP_TYPE_GEN_SPEC_CONSTITUTION §3 | `test_single_ssot_mapping.py`, `test_no_nonderived_mappings.py` |

---

## Deprecated / Historical Documents

| Document | Original Location | Superseded By | Notes |
|----------|-------------------|---------------|-------|
| `paramspace_constitution_cn.md` | `docs/` | PARAMSPACE_SPEC.md + Constitution §8 | Merged into global constitution in v1.2; now fully extracted to governance |
| `CONSTITUTION_ZH.md` | repo root | `CONSTITUTION.md` (English v2.1) | Chinese version deprecated; English is now authoritative |
| Old Constitution §10-14 (v1.2) | `CONSTITUTION_ZH.md` | Constitution v2.0 + governance specs | Detailed mechanics extracted; thin summaries remain in constitution |

---

## Adding New Governance Documents

1. Create the spec in `docs/governance/`
2. Add a summary reference in `CONSTITUTION.md` (appropriate section)
3. Add entry to the Document Index above
4. Add cross-reference entries for each invariant + gate
5. Set initial status (PROPOSED → review → FINAL)

---

**End of Governance Index**
