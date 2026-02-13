# QMatSuite Law Documents

**Last Updated**: 2026-02-12

---

## Document Hierarchy

| Level | Authority | Location | Update Protocol |
|-------|-----------|----------|----------------|
| **L0. Central Constitution** | `CONSTITUTION.md` (repo root) | Repo root | Author review required |
| **L1. Laws & Constitutions** | `docs/laws/L1/` (8 files) | This folder | Must not contradict constitution; changes require updating constitution references if scope changes |
| **L2. Specs, Policies, Playbooks** | `docs/laws/L2/` (15 files) | This folder | Binding operational rules; must not contradict L0 or L1 |
| **Non-binding** | `docs/design/`, `docs/guides/` | Other docs/ dirs | For reference only |

**Conflict resolution**: Higher-level document wins. If an L1/L2 spec contradicts the constitution, the constitution is authoritative.

**How to update without dual truths**: When changing a rule, update the authoritative source first (usually the law spec), then update the constitution's summary of that rule to match. Never maintain the same rule in full detail in both places.

---

## Document Index

### L0 — Constitution (Highest Authority)

| Document | Status | Purpose | Last Updated |
|----------|--------|---------|-------------|
| [`CONSTITUTION.md`](../../CONSTITUTION.md) | **FINAL** (v2.1) | Central constitution — all high-level invariants (English) | 2026-02-03 |

### L1 — Laws & Constitutions (8 files)

| Document | Status | Governs | Constitution Reference | Last Updated |
|----------|--------|---------|----------------------|-------------|
| [`API_CONSTITUTION.md`](L1/API_CONSTITUTION.md) | **FINAL** (v2.2) | API surface, import layering, utils policy, DTOs, errors, H9 filesystem control | Constitution §18 | 2026-02-12 |
| [`KERNEL_DEPENDENCY_SPEC.md`](L1/KERNEL_DEPENDENCY_SPEC.md) | **PROPOSED** (v3.1) | Kernel 7-domain model, dependency DAG, SSOT writes, engine inputs | Constitution §19 | 2026-02-03 |
| [`KERNEL_EXCEPTIONS.md`](L1/KERNEL_EXCEPTIONS.md) | **ACTIVE** (v3.1) | Approved exceptions to kernel dependency rules (EXC-001 through EXC-004) | Constitution §19 | 2026-02-03 |
| [`STEP_TYPE_GEN_SPEC_CONSTITUTION.md`](L1/STEP_TYPE_GEN_SPEC_CONSTITUTION.md) | **FINAL** (v1.1) | GEN/SPEC step type namespaces, derivation rule, conversion API, execution layering | Constitution §7 | 2026-02-02 |
| [`ENGINE_INTEGRATION_CONSTITUTION.md`](L1/ENGINE_INTEGRATION_CONSTITUTION.md) | **SPECIFICATION** (v1.0) | Engine integration invariants: no guessing, hard error, explicit mapping, driver self-containment | Constitution §17 | 2026-02-01 |
| [`PARAMSPACE_SPEC.md`](L1/PARAMSPACE_SPEC.md) | **FINAL** (v1.0) | ParamSpace framework: compiler/detector equivalence, single-writer, cell semantics, Oracle | Constitution §8 | 2026-02-03 |
| [`ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md`](L1/ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md) | **FINAL** (v1.0) | Engine recipe system, runner independence, recipe archetypes, directory contracts, bans | Constitution §17 | 2026-02-03 |
| [`PROVENANCE_VERSIONED_HISTORY_SPEC.md`](L1/PROVENANCE_VERSIONED_HISTORY_SPEC.md) | **PROPOSED** (v1.1) | Provenance/history system: SQLite timeline, CAS blobs, OperationContext, rollback, artifact tiers, normalized run_steps | Constitution §3 | 2026-02-05 |

### L2 — Specs, Policies, Playbooks (15 files)

| Document | Status | Governs | Scope |
|----------|--------|---------|-------|
| [`ANALYSIS_OBJECT_PRIMITIVES_SPEC.md`](L2/ANALYSIS_OBJECT_PRIMITIVES_SPEC.md) | **BINDING** (v1.5) | Analysis data model contracts | analysis |
| [`RELAX_SPEC.md`](L2/RELAX_SPEC.md) | **RATIFIED** (v1.0) | Relaxation workflow hard invariants | kernel |
| [`STRUCTURE_FINGERPRINT_SPEC.md`](L2/STRUCTURE_FINGERPRINT_SPEC.md) | **RATIFIED** (v2.1) | Fingerprint algorithm (gate enforced) | kernel |
| [`MULTI_FRONTEND_ARCHITECTURE_SPEC.md`](L2/MULTI_FRONTEND_ARCHITECTURE_SPEC.md) | **HARDENED** (v2.0) | Import boundaries, non-negotiable | api/gui |
| [`API_DTO_SCHEMA.md`](L2/API_DTO_SCHEMA.md) | **SPEC** (v2.0) | DTO construction rules | api |
| [`API_ERROR_TAXONOMY.md`](L2/API_ERROR_TAXONOMY.md) | **SPEC** (v2.0) | Stable error code registry | api |
| [`DEMO_STORE_SPEC.md`](L2/DEMO_STORE_SPEC.md) | **DRAFT** (v6) | Demo code/tests/CI conformance | demo |
| [`GUI_ENGINE_FAMILY_DEMO_SPEC.md`](L2/GUI_ENGINE_FAMILY_DEMO_SPEC.md) | **ACTIVE** (v1.1) | Engine family state machine (GUI) | gui/engine |
| [`B1_ENGINE_PLAYBOOK.md`](L2/B1_ENGINE_PLAYBOOK.md) | **ACTIVE SOP** (v1.0) | Binding SOP for engine B1 work | engine |
| [`ANALYSIS_PIPELINE_PLAYBOOK.md`](L2/ANALYSIS_PIPELINE_PLAYBOOK.md) | **SOP** | Binding playbook with hard rules (P1-P5, R1-R4) | analysis |
| [`CALC_TYPE_SYSTEM_KIND_SPEC.md`](L2/CALC_TYPE_SYSTEM_KIND_SPEC.md) | **DESIGN** (v1.0) | system_kind/engine_group constraints | kernel |
| [`parameter_scan.md`](L2/parameter_scan.md) | **DRAFT** (v1.0) | Persistence schema (Constitution §10) | kernel |
| [`engine_driver_protocol.md`](L2/engine_driver_protocol.md) | **SPEC** (v1.0) | EngineDriver MUST/SHOULD/PLUGIN interface tiers | engine |
| [`engine_registry_and_dispatch.md`](L2/engine_registry_and_dispatch.md) | **SPEC** (v1.0) | 3-registry architecture | engine |
| [`migration_gates_and_test_contract.md`](L2/migration_gates_and_test_contract.md) | **SPEC** (v1.0) | Migration gates (CI enforced) | engine |

### Status Taxonomy

| Status | Meaning |
|--------|---------|
| **FINAL** | Binding law. Changes require constitution review. |
| **ACTIVE** | Binding but may evolve (e.g., exception lists). |
| **PROPOSED** | Under review; expected to become FINAL. |
| **SPECIFICATION** | Binding design spec; may be promoted to FINAL. |
| **RATIFIED** | Ratified amendment; gate-test enforced. |
| **HARDENED** | Non-negotiable; import boundaries enforced. |
| **SOP** | Standard Operating Procedure; binding playbook. |
| **DRAFT** | Work-in-progress; expected to become binding. |

---

## Cross-Reference: Invariants → Definitions → Gates

| Invariant | Constitution § | Law Spec | Enforcement Gate(s) |
|-----------|---------------|----------|---------------------|
| **SSOT = calculation.yaml + step.yaml** | §2.1 | KERNEL_DEPENDENCY_SPEC §2.1 | `test_yaml_write_single_entry.py`, `test_yaml_read_single_entry.py` |
| **History world separation (Law P1)** | §3 | PROVENANCE_VERSIONED_HISTORY_SPEC §2 | `test_provenance_independence.py` |
| **OperationContext required (Law P2)** | §3 | PROVENANCE_VERSIONED_HISTORY_SPEC §2 | `test_provenance_opctx_required.py` |
| **No provenance in skip logic (Law P3)** | §3 | PROVENANCE_VERSIONED_HISTORY_SPEC §2 | `test_provenance_skip_isolation.py` |
| **CAS integrity (Law P5)** | §3 | PROVENANCE_VERSIONED_HISTORY_SPEC §2 | `test_cas_integrity.py` |
| **Lock ordering edit→provenance (Law P6)** | §3, §4 | PROVENANCE_VERSIONED_HISTORY_SPEC §4 | `test_lock_ordering.py` |
| **Graceful degradation (Law P7)** | §3 | PROVENANCE_VERSIONED_HISTORY_SPEC §2 | `test_provenance_failure_graceful.py` |
| **Only SSOT writes are events (Law P8)** | §3 | PROVENANCE_VERSIONED_HISTORY_SPEC §2 | `test_preset_events.py` |
| **Single artifact scanner (Law P9)** | §3 | PROVENANCE_VERSIONED_HISTORY_SPEC §6 | `test_no_duplicate_scanners.py` |
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

## Adding New Law Documents

1. Create the spec in `docs/laws/L1/` (law/constitution) or `docs/laws/L2/` (spec/policy/playbook)
2. Add a summary reference in `CONSTITUTION.md` (appropriate section)
3. Add entry to the Document Index above
4. Add cross-reference entries for each invariant + gate
5. Set initial status (PROPOSED → review → FINAL)

---

**End of Laws Index**
