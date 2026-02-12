# Demo Store Specification

**Status**: Draft v6 (Level-1/Level-2 naming, two materialization paths, two roundtrips, semantic diff)
**Authority**: Governance-level spec. All demo-related code, tests, and CI MUST conform.
**Scope**: Defines the two-level demo system (Level-1 corpus, Level-2 demo YAML), Route-1/Route-2 policy, two materialization paths (Load / Authoring), two roundtrip contracts, real-run validation, integrity suites, Demo Baseline acceptance criteria, semantic diff rules, and governance rules.

---

## S0. Terminology & Scope

| Term | Definition |
|------|-----------|
| **Level-1 store** (Corpus / Source Material) | Raw upstream/tutorial/example folders committed verbatim as engine-native inputs under `tests/inputformat/samples/`. May contain BOTH Route-1 and Route-2 source materials (because it is "as-downloaded"). Not user-facing; serves as the canonical source for deterministic translation to Level-2, and for parser/writer testing. Historically called "Layer A". |
| **Level-2 store** (Demo Projects) | Generated, user-facing demo artifacts stored as single `.yml` snapshot files under `resources/demo_projects/`. The Level-2 `.yml` IS the basis artifact — it is loadable by the daemon, renderable in the GUI gallery, and materializable into a live project workspace. Level-2 is generated deterministically from Level-1 by the translator (single-writer). The `.yml` format is also the future "project snapshot / export" format. Historically called "Layer B". |
| **Corpus case** (Level-1 entry) | A self-contained directory of raw engine input files plus a manifest (`case.yaml`), representing one calculation workflow for one engine. Corpus cases are human-authored or curated from external sources. The full corpus serves parser testing; a subset is eligible for demo generation. |
| **Demo project** (Level-2 entry) | A single generated QMatSuite project snapshot (`.yml` file) under `resources/demo_projects/`. A demo project IS the `.yml` file. Demo projects are **generated artifacts** — never hand-edited. |
| **Demo slug** | A stable, human-friendly identifier for a demo, independent of the corpus directory name. Defined in `case.yaml` as `demo_slug`. Used as the Level-2 filename stem (e.g., `demo_slug: si_scf` → `si_scf.yml`). |
| **Translator** (Generator) | The single deterministic program that reads eligible Level-1 corpus cases and produces Level-2 demo projects. It uses the `inputformat` parse pipeline and `ProjectSnapshot` serialization. It is also the prototype for the future "import user project" feature. |
| **Corpus root index** | A machine-readable index file at the corpus root (`tests/inputformat/samples/corpus_index.yaml`) that classifies every corpus case: demo eligibility, runnability, asset status, and exclusion reasons. This is the authoritative registry for which cases become demos. |
| **Snapshot ULIDs** | The ULIDs embedded inside a demo snapshot `.yml`. These are **stable and deterministic** — regenerating the same demo from the same corpus input produces the same snapshot ULIDs. They serve as portable package-level identifiers. |
| **Materialized ULIDs** | The ULIDs written into the on-disk SSOT files (`project.yaml`, `calculation.yaml`, `*.step.yaml`, structure JSON) when a snapshot is loaded/materialized into a workspace. These are **always freshly generated** to avoid collisions between projects. Once written, they MUST NOT be edited or rewritten. |
| **Snapshot roundtrip** | The contract that loading a demo snapshot → materializing a project → re-snapshotting produces an equivalent snapshot. ULIDs will differ (snapshot ULIDs → fresh materialized ULIDs → preserved in re-snapshot). Equivalence is defined on content, not identity. See S6. |
| **Demo gallery metadata** | The top-level `meta` section in a demo snapshot: title, subtitle, tags, difficulty, attribution, etc. This is display/catalog metadata for the GUI gallery. It is NOT SSOT and is NOT part of project/calculation/step/structure metadata. It MAY be omitted by a generic project snapshot/export. |
| **SSOT metadata** | The `meta` blocks inside `project`, `structures[]`, `calculations[]`, and `steps[]`: ulid, name, slug, path, kind. This IS structural project metadata and MUST be preserved through materialization (with ULID rewrite per the lifecycle rules). |
| **Integrity suite** | A FAST test suite (`tests/integrity/backend/`) that validates demo load and materialize correctness. It DOES NOT execute engines and DOES NOT prove demos are runnable. It is Stage (B) of the Demo Baseline. Not part of default test collection. Iterates ONLY Level-2 demos. See SE.4. |
| **Real-run baseline** | The process of executing every runnable demo through a real engine binary via the daemon/service pipeline (`tools/demo_store/generate_ref_packs_realrun.py`). This is Stage (C) of the Demo Baseline and is the authoritative proof that demos work. |
| **Demo Baseline** | The four mandatory acceptance stages (A: pytest, B: integrity, C: real-run, D: ref-packs) that MUST ALL pass before any demo-store work can be claimed complete. Defined in section DB. |
| **Assets** | External files required to run a calculation: pseudopotentials, basis sets, force-field potentials, PAW datasets, etc. |
| **Redistributable assets** | Assets whose license permits inclusion in the repository (e.g., QE SSSP pseudopotentials under CC-BY, LAMMPS bundled potentials). |
| **Proprietary assets** | Assets that MUST NOT be committed to the repository (e.g., VASP POTCARs, commercial basis sets). Demos requiring proprietary assets MAY be demo-eligible but MUST be clearly labeled with their requirements so that integrity suites can skip or fail appropriately depending on the test environment. |
| **Route-1** (end-to-end runnable) | A demo whose entire execution chain is representable as YAML parameters and materializable into a real engine run. All step inputs come from the demo YAML; only external *assets* (pseudopotentials, potentials, basis sets) are staged separately. Composite multi-engine workflows (e.g., QE→W90) are Route-1 provided every step in the chain is runnable. See section RT. |
| **Route-2** (prebaked-upstream) | Source material that depends on upstream artifacts NOT produced within the demo's own runnable chain (e.g., precomputed `.amn`/`.mmn`/`.eig`, `prefix.save/`, HDF5 wavefunctions, Yambo `SAVE/` databases). Useful as corpus (Level-1) but NOT end-to-end runnable under current demo infrastructure. See section RT. |
| **Path A** (Load Demo) | Materializing a Level-2 demo by loading/importing the `.yml` snapshot into a live project via `create_demo_project()`. This is the primary user-facing gallery workflow. See section MP. |
| **Path B** (Authoring) | Materializing a Level-2 demo by replaying its content as a sequence of user-granularity authoring operations (create project, add structure, add step, set parameters one-by-one) through the daemon/service APIs — the same endpoints used by GUI/CLI. No snapshot import, no bulk YAML write. See section MP. |
| **Roundtrip A** (Load roundtrip) | Level-2 `.yml` → Path A load → re-snapshot → semantic diff ≈ original. Validates demo import/export correctness. See section SE. |
| **Roundtrip B** (Authoring roundtrip) | Level-2 `.yml` → compile to authoring ops → Path B replay → re-snapshot → semantic diff ≈ original. Validates that the authoring capability can express the same semantics as demos. See section SE. |

### Goals

This spec serves three explicit goals:

**G1 — Two-level demo system.** Level-1 (corpus) provides reference input examples for engine direct users and serves as authoritative upstream source material ingested from the internet, manuals, and tutorials. Level-2 (demo projects) provides QMatSuite-native `.yml` snapshots for the GUI gallery and daemon. Both levels are maintained because: (1) they serve different infrastructure targets (corpus → engine users; demo projects → QMatSuite); (2) web-found materials map naturally to corpus and the translation to Level-2 validates parser robustness; (3) the future "import user project" pipeline reuses the same translation machinery. Only a **subset** of the full corpus is translated to Level-2; the remainder serves parser/writer testing.

**G2 — Deterministic translation and robustness.** There is exactly ONE translator from Level-1 → Level-2. Demo projects are generated artifacts and MUST NOT be hand-edited. Any fix MUST be made in corpus and re-generated. The Level-2 demo `.yml` is the **basis artifact** — it must survive both Roundtrip A (load path) and Roundtrip B (authoring path) with well-defined semantic equivalence rules (see section SE).

**G3 — Verification at two levels.** The FAST integrity suite (`tests/integrity/backend/`) validates structural correctness (load + materialize) but DOES NOT execute engines. The real-run baseline (`tools/demo_store/generate_ref_packs_realrun.py`) executes every runnable demo through real engine binaries and is the authoritative proof that demos work. Both are mandatory stages of the Demo Baseline (section DB). A GUI e2e suite (T2) provides additional browser-level verification. The integrity suite and real-run baseline run separately from default test collection. Demos with only redistributable or no assets MUST pass the real-run baseline when the engine binary is present. Demos requiring proprietary assets or missing engine binaries follow Rule DB-EA (install or demote — no third option).

---

## RT. Route-1 vs Route-2 (Definitions & Policy)

### RT.1 Definitions

**Route-1 (end-to-end runnable, SSOT/YAML path):**

- All step inputs are represented in the single demo YAML (Level-2) as parameters.
- Execution is: YAML → materialize (clean rewrite) → `raw/` → real engine run.
- Only external *assets* (pseudopotentials, potentials, basis sets, PAW datasets) may be staged from outside the YAML; all step input definitions MUST come from the YAML itself.
- Composite multi-engine workflows are permitted: an upstream engine (e.g., QE) produces intermediate artifacts, then a companion engine (e.g., Wannier90, QMCPACK, Yambo) consumes them as a subsequent step. The full chain is runnable end-to-end within a single demo project.

**Route-2 (prebaked-upstream / playback-style source material):**

- Requires upstream artifacts that are NOT produced within the demo's own runnable chain — for example, precomputed Wannier `.amn`/`.mmn`/`.eig` files, a `prefix.save/` directory, an HDF5 wavefunction, or a Yambo `SAVE/` database.
- The demo cannot run end-to-end because the artifact-producing step is absent; the prebaked files are supplied as static data.
- Useful as source corpus material (Level-1) for parser testing and as reference examples, but NOT representable as a self-contained runnable demo under current infrastructure.

### RT.2 Examples

| Scenario | Route | Why |
|----------|-------|-----|
| Standalone W90 tutorial folder with prebaked `.amn`/`.mmn`/`.eig` (no QE steps) | **Route-2** | Upstream QE→pw2wannier90 artifacts are not produced within the demo. |
| QE SCF → QE NSCF → pw2wannier90 → Wannier90 composite pipeline demo | **Route-1** | Every intermediate artifact is produced by a prior step in the chain. |
| QMCPACK demo requiring a prebaked HDF5 wavefunction (no QE→pw2qmcpack) | **Route-2** | The HDF5 is an external prebaked artifact with no producing step. |
| QE SCF → pw2qmcpack → QMCPACK composite pipeline demo | **Route-1** | QE produces the wavefunction, pw2qmcpack converts it, QMCPACK consumes it. |

### RT.3 Current Policy (MUST)

**Rule RT-L1** (Level-1 — corpus): The Level-1 corpus MAY contain both Route-1 and Route-2 folders. Level-1 is a verbatim collection of source material downloaded from the internet, upstream tutorials, and engine manuals. Both routes serve parser/writer testing.

**Rule RT-L2** (Level-2 — demo projects): Level-2 (`resources/demo_projects/`) MUST contain Route-1 demos ONLY. Route-2 material is FORBIDDEN in Level-2 until a dedicated implementation for prebaked-upstream demos exists. No such implementation currently exists.

**Rule RT-D** (demotion requirement): Any corpus entry that requires Route-2 artifacts MUST be marked `demo_eligible: false` in both `case.yaml` and `corpus_index.yaml`, with a non-empty `exclusion_reason` (e.g., `"Route-2: requires prebaked upstream artifacts (*.amn/*.mmn/*.eig) not produced within demo chain"`). Such entries MUST NOT be generated into Level-2 demos.

**Rule RT-E** (existing demo enforcement): If an existing Level-2 demo is discovered to require Route-2 artifacts (i.e., it cannot pass Demo Baseline Stage C without prebaked files that are not produced by any step in its chain), it MUST be demoted: remove the `.yml` from `resources/demo_projects/`, set `demo_eligible: false` and `runnable: false` in the corpus index, and provide an `exclusion_reason`. There is no grandfather clause.

---

## MP. Materializing a Level-2 Demo into a Project (Two Paths)

A Level-2 demo `.yml` is the **basis artifact**. There are exactly TWO equally important ways to materialize it into a live project. Both MUST be supported and both MUST produce semantically equivalent results.

### MP.1 Path A — Load Demo (Snapshot Import)

This is the primary user-facing workflow for the demo gallery.

**Input**: Level-2 demo `.yml` file.

**Action**: Load the demo `.yml` into a live project via `create_demo_project()` (snapshot import). This creates a fully materialized project workspace with canonical SSOT files on disk, fresh ULIDs, and staged assets.

**After materialization, the project can**:
- Be real-run via daemon `run_calc` (engine execution).
- Be re-snapshotted back to a single `.yml` (Roundtrip A).

**Rule MP-A1**: Path A MUST be supported for every Level-2 demo. A demo that cannot be loaded via `create_demo_project()` is broken.

### MP.2 Path B — Authoring from Scratch (User-Granularity Replay)

This simulates a user who reads the source material and builds a project manually through the GUI or CLI — the same authoring operations available to any user.

**Input**: Level-2 demo `.yml` (used ONLY as an oracle/specification of the intended semantics — it is NOT imported).

**Action**: Compile the demo `.yml` into a sequence of **user-granularity authoring operations**, then replay that sequence through daemon/service authoring APIs:
1. Create project.
2. Create structure(s) — set lattice, species, coordinates.
3. Create calculation — set `engine_family`.
4. Add step(s) — set `step_type_gen`, `step_type_spec`.
5. Set parameters **one field at a time** (UI granularity) — set/unset/replace individual parameter keys.
6. Configure `species_map` / `potential_map` if applicable.

**After materialization, the project can**:
- Be real-run via daemon `run_calc` (engine execution).
- Be re-snapshotted back to a single `.yml` (Roundtrip B).

**Rule MP-B1**: Path B MUST NOT shortcut by importing the snapshot, bulk-writing YAML, or staging engine input files directly. Every operation MUST go through the same production authoring endpoints used by GUI/CLI.

**Rule MP-B2**: The authoring operation sequence MUST be at "user/UI granularity" — individual field-level set/unset/replace calls, not bulk tree patches. This validates that the authoring API is expressive enough to construct any demo from scratch.

**Rule MP-B3**: Path B MUST be supported for every Level-2 demo. A demo whose semantics cannot be expressed through the authoring API has an API coverage gap that MUST be fixed.

### MP.3 Why Both Paths Matter

| Concern | Path A validates | Path B validates |
|---------|-----------------|-----------------|
| Demo import/export | Yes | No |
| Authoring API completeness | No | Yes |
| Parameter-level API fidelity | No | Yes |
| Snapshot format correctness | Yes | Indirectly |
| User can reproduce a demo manually | No | Yes |

Neither path alone is sufficient. Path A proves the snapshot pipeline works. Path B proves the authoring pipeline can express the same semantics — which is the foundation for the GUI/CLI user experience.

---

## SE. Semantic Equivalence and Roundtrip Contracts

### SE.1 Two Roundtrips

Both roundtrips use the Level-2 demo `.yml` as the reference and produce a re-snapshot for comparison. The comparison uses the **canonical semantic diff** defined in SE.3.

#### Roundtrip A — Load Path

```
Level-2 demo.yml
  → Path A: create_demo_project() (snapshot import)
  → live project on disk
  → export_project_to_snapshot()
  → re-snapshot.yml
  → canonical semantic diff ≈ original demo.yml
```

**Purpose**: Validates that demo import/export is semantically lossless.

#### Roundtrip B — Authoring Path

```
Level-2 demo.yml
  → compile to user-granularity authoring operations
  → Path B: replay ops through daemon/service authoring APIs
  → live project on disk
  → export_project_to_snapshot()
  → re-snapshot.yml
  → canonical semantic diff ≈ original demo.yml
```

**Purpose**: Validates that the authoring API can express the same semantics as any demo. This is the stronger contract — it proves the API is complete for the demo's domain.

**Rule SE-1**: Both Roundtrip A and Roundtrip B MUST produce re-snapshots that are **semantically equivalent** to the original Level-2 demo `.yml`, per the canonical diff rules in SE.3.

**Rule SE-2**: Roundtrip B authoring operations MUST go through the same production daemon/service endpoints used by GUI/CLI. No direct YAML writing, no snapshot import as a shortcut, no staging of engine input files.

### SE.2 Real-Run Validation (Two Paths)

Real-run validation exists for BOTH paths. After materialization (via either path), the project can be executed with a real engine binary.

**Path A real-run**: Mandatory. This is the primary mechanism by which demos uncover real execution bugs. Defined as Demo Baseline Stage (C).

**Canonical entrypoint**:
```bash
python tools/demo_store/generate_ref_packs_realrun.py
```

**Path B real-run**: Defined as ultimate validation. Once Roundtrip B proves semantic equivalence, Path B real-run confirms that semantic equivalence translates to identical runtime behavior.

**Current priority**:
- Path A real-run is **mandatory** (Demo Baseline Stage C — no deferrals per Rule DB-ND).
- Path B real-run is **not as time-urgent** once Roundtrip B passes, but MUST still be defined as the ultimate validation target. Semantic equivalence alone is not a proof of identical runtime behavior (e.g., parameter ordering, whitespace sensitivity in engine input files, or engine-specific materialization quirks could cause divergence).

**Rule SE-RR**: When both Path A and Path B real-runs are executed for the same demo, the engine outputs (energy, forces, convergence) MUST agree within engine-level numerical tolerance.

### SE.3 Canonical Semantic Diff Rules

Two snapshots are **semantically equivalent** if and only if they agree on all fields after applying the following normalization.

#### Fields that MUST be IGNORED (permitted variance)

| Category | Fields | Reason |
|----------|--------|--------|
| Identity | `*.meta.ulid` (all ULIDs) | Fresh ULIDs generated at materialization (Rule UL1). |
| Paths | `*.meta.path`, filesystem paths | Workspace-dependent. |
| Timestamps | `generated_at`, `materialized_at`, `created_at` | Non-deterministic. |
| Provenance | Provenance IDs, CAS hashes, timeline entries | Generated per-session. |
| Generator metadata | `generator_version`, `corpus_checksum`, generator manifest data | Build-time metadata. |
| Demo gallery display | Top-level `meta` section (title, subtitle, tags, difficulty, etc.) | NOT SSOT; MAY be omitted by generic export. |
| Runtime-managed keys | Engine-specific keys injected/overridden at materialization (e.g., QE `outdir`, `pseudo_dir`, `wfcdir`; VASP `SYSTEM`) | Each engine driver declares its managed keys. |
| Cross-reference ULIDs | `structure_ulid`, step-to-step references | Verified as **structurally isomorphic** (same entity referenced), not by ULID value match. |
| Settings augmentation | `project.settings` (additional keys) | Materialization may add runtime settings; original keys MUST be preserved. |
| Caches | Any cached/derived data | Ephemeral. |
| YAML formatting | Key order, whitespace, quoting style | Equivalence is semantic (parsed dict), not textual. |

#### Fields that MUST MATCH

| Category | Fields |
|----------|--------|
| Engine identity | `engine_family` on every calculation |
| Step ordering | Order of `steps[]` within each calculation |
| Step types | `step_type_gen`, `step_type_spec` for every step |
| Effective parameters | All `steps[].parameters` keys/values EXCLUDING runtime-managed keys |
| Structures | Canonical structure content: lattice vectors, species, coordinates (fractional or Cartesian as appropriate) |
| Scan definitions | Scan parameter names, values, and ordering (if present) |
| Component names | `*.meta.name`, `*.meta.slug`, `*.meta.kind` |
| Pseudo/asset specs | `pseudo.files`, `pseudo.pseudo_sha256` (if present) |

#### Fields that MUST NOT be introduced

No fields may appear in the re-snapshot that were not either (a) in the original snapshot or (b) in the permitted-variance list above. Unexpected new fields are a semantic diff violation.

### SE.4 Integrity Tests Are FAST Checks (NOT Real Runs)

The **integrity suite** (`tests/integrity/backend/`) is a FAST structural validation of Level-2 demos.

**Canonical command**:
```bash
python -m pytest tests/integrity/backend/ -v --tb=short
```

**What it does**: Validates that every Level-2 demo can be loaded, materialized, and passes structural correctness checks (ULID freshness, field presence, cross-reference validity).

**What it does NOT do**:
- It DOES NOT execute any engine binaries.
- It DOES NOT prove that demos are runnable.
- It DOES NOT perform real-run validation.
- Passing integrity DOES NOT imply demos work end-to-end.

**Rule SE-INT**: The integrity suite is Demo Baseline Stage (B) — necessary but not sufficient. Real-run validation (Stage C) is the authoritative proof that demos work. See section DB.

---

## DB. Demo Baseline (Acceptance Criteria — MANDATORY)

This section defines the **Demo Baseline**: the four mandatory stages that MUST ALL pass before any demo-store work (migration, expansion, new-demo PR, or closeout report) can be claimed as complete. This section has the highest operational authority in the spec — it overrides any softer language elsewhere.

### DB.1 The Four Stages

The Demo Baseline consists of four stages executed **in this exact order**. ALL four MUST pass. Partial completion (e.g., stages A+B pass but C is skipped) means the baseline is **FAILED**.

#### Stage (A): Full pytest suite — MUST be green

The full project test suite MUST pass with zero failures.

**Canonical command** (copy-paste verbatim):
```bash
source .venv/bin/activate
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

This validates that no demo-store work has regressed any existing functionality.

#### Stage (B): FAST integrity suite — MUST be green

The backend integrity suite under `tests/integrity/backend/` MUST pass with zero failures.

**Canonical command** (copy-paste verbatim):
```bash
python -m pytest tests/integrity/backend/ -v --tb=short
```

> **CRITICAL CLARIFICATION**: This suite DOES NOT execute any engines and DOES NOT prove that demos are runnable. It validates load, materialize, and structural correctness only. Passing stage (B) is necessary but NOT sufficient to claim demos work.

#### Stage (C): Real-run baseline — MUST execute engines

Every runnable demo MUST be executed through a real engine run via the daemon/service pipeline. This is the stage that proves demos actually work end-to-end.

**Canonical command** (copy-paste verbatim):
```bash
python tools/demo_store/generate_ref_packs_realrun.py
```

**Definition**: For each runnable demo, this stage MUST:
1. Materialize the demo YAML into a live project via the daemon/service layer.
2. Execute `run_calc` with the **real engine binary** — no mocking, no synthetic output, no skip.
3. Attempt output parsing and analysis providers.
4. Write reference packs (see Stage D).

> **CRITICAL RULE**: If this stage is not executed, the Demo Baseline is **FAILED** even if stages (A) and (B) pass. There is no exception to this rule.

#### Stage (D): Ref-pack generation — MUST be attempted for every runnable demo

The real-run in Stage (C) MUST attempt to generate a reference pack for every runnable demo.

- A ref pack MAY be empty (contain only a manifest with no object types) when there is no matching analysis provider implemented for that engine/calculation type. This is acceptable.
- A ref pack that is "not attempted" or "deferred" is **NEVER** acceptable. Every runnable demo MUST have a ref-pack generation attempt recorded in the results matrix.

### DB.2 Hard Rule: No Deferrals

**Rule DB-ND** (No Deferrals): Any PR, report, or closeout claim that asserts completion of demo-store work WITHOUT having executed Stage (C) is **incorrect** and MUST be treated as FAILED.

- "Requires engine binaries not available" is NOT a valid reason to skip Stage (C). See Rule DB-EA below.
- "Deferred to follow-up" is NOT a valid reason to skip Stage (C).
- "Integrity suite passes so demos work" is NOT a valid claim. Stage (B) does not execute engines.

**Acceptance rule**: A completion claim requires evidence of ALL of (A), (B), (C), and (D). If any stage is missing, the work MUST be labeled **incomplete** or **failed**. No other label is permitted.

### DB.3 Hard Rule: Engines Are Expected Available Locally

**Rule DB-EA** (Engine Availability): For demo baseline verification on developer machines and CI-like environments, all engines required by runnable demos MUST be discoverable and executable.

- Engine discovery follows the standard engine discovery mechanism documented in `docs/architecture/ANALYSIS_PIPELINE_PLAYBOOK.md`.
- "Requires engine binaries / runtime environment" is **NOT** a valid excuse to skip Stage (C).
- If a runnable demo's required engine cannot be found, there are exactly **two** permitted responses:
  1. **Fix engine discovery or install the engine** per the playbook and existing engine configuration, then proceed with Stage (C).
  2. **Demote the demo**: Set `demo_eligible: false`, `runnable: false`, and provide a non-empty `exclusion_reason` in both `case.yaml` and `corpus_index.yaml`.
- **There is no third option.** Leaving a demo marked as `runnable: true` while skipping its real-run is a spec violation.

### DB.4 Definition of "Runnable Demo"

A demo is **runnable** if and only if ALL of the following hold:

1. The daemon can load the generated demo `.yml` into a real project (materialize succeeds).
2. The daemon can execute `run_calc` successfully with the real engine binary (engine run completes without error).
3. Expected output artifacts exist in the working directory after the run.
4. Ref-pack generation was executed for this demo. The ref pack MAY be empty if no analysis provider exists, but the attempt MUST be recorded.

**Corollary**: "Integrity passing" (Stage B green) is **necessary but not sufficient** to establish runnability. Only a successful Stage (C) execution for a specific demo establishes that it is runnable.

### DB.5 Required Closeout Artifacts

Any PR that performs demo-store migration, expansion, or modification MUST include a committed markdown closeout report.

**File path**: `docs/demo_store/DEMO_BASELINE_CLOSEOUT.md` (or a dated variant, e.g., `DEMO_BASELINE_CLOSEOUT_<date>.md`).

The closeout report MUST include ALL of the following:

1. **Stage (A) summary**: pytest pass/fail/skip counts and the exact command executed.
2. **Stage (B) summary**: integrity suite pass/fail/skip counts and the exact command executed.
3. **Stage (C) summary**: Real-run results with per-demo status counts:
   - `OK` — engine ran, output parsed successfully.
   - `FAILED` — engine ran but produced errors, or materialization failed.
   - `NO_ANALYSIS` — engine ran successfully but no analysis provider exists for this calculation type (ref pack is empty).
4. **Per-demo failure details**: For every demo that is not `OK`, the report MUST include:
   - The demo slug and engine.
   - The failure stage (materialize / run / parse / analysis).
   - A pointer to the log file or output directory (relative path, no absolute paths per Law S1).
5. **Exact commands executed**: All commands from stages (A) through (D) MUST be included as copy-pasteable blocks. No paraphrasing.

**Rule DB-CO** (Closeout Obligation): A PR that modifies `resources/demo_projects/`, `corpus_index.yaml`, or `tools/demo_store/` without including the closeout report (or updating an existing one) MUST NOT be merged.

---

## S1. Repository Layout

### S1.1 Layer A — Corpus Root

```
tests/inputformat/samples/
├── corpus_index.yaml                # REQUIRED: master index (see S3)
├── <engine>/                        # e.g., vasp/, orca/, qe/, lammps/
│   ├── <dir_name>/                  # e.g., si_scf/, 00_water_sp/, benzene_tddft/
│   │   ├── case.yaml                # REQUIRED: corpus manifest (see S2)
│   │   ├── <input_file(s)>          # Engine-native input files
│   │   ├── ref_values.yaml          # OPTIONAL: golden reference values
│   │   └── <auxiliary_files>        # OPTIONAL: data files, local potentials, etc.
│   └── ...
└── ...
```

**Rule C1**: Every corpus case MUST reside at `tests/inputformat/samples/<engine>/<dir_name>/` and MUST contain a `case.yaml`.

**Rule C2**: The `<engine>` directory name MUST match a registered `engine_family` in `DriverRegistry` (lowercase). Note: the `DriverRegistry` at runtime is the authoritative list of engine families. The following list is illustrative and non-authoritative: `qe`, `vasp`, `abinit`, `cp2k`, `orca`, `gaussian`, `lammps`, `siesta`, `w90`, `gpaw`, `psi4`, `pyscf`, `xtb`, `qmcpack`, `yambo`.

**Rule C3** (directory naming): The `<dir_name>` MUST be unique within its engine directory. Directory names MAY contain leading digits and MAY preserve upstream naming conventions (e.g., `00_water_sp`, `case_003_ethanol`). Directory names do NOT need to match the `case_id` or `demo_slug` — those are defined in `case.yaml` and are the stable identifiers.

**Rule C4**: The corpus root MUST contain a `corpus_index.yaml` file (see S3) that lists every corpus case with its eligibility classification.

### S1.2 Layer B — Demo Projects Root

```
resources/demo_projects/
├── <demo_slug>.yml                  # Generated snapshot (one per demo)
├── <demo_slug>.<step>.<type>.json   # OPTIONAL: per-step reference artifacts
└── .generator_manifest.json         # Generator state: maps corpus → demo, checksums
```

**Rule D1**: A demo project IS the single `<demo_slug>.yml` file. Loading a demo means loading exactly this file. The `.yml` file is the complete, self-sufficient definition — the demo MUST be loadable and materializable from this file alone.

**Rule D2**: Every `.yml` file in `resources/demo_projects/` MUST be produced by the translator. Manual creation or editing is prohibited.

**Rule D3**: Optional reference artifact files (`*.json`) MAY exist alongside the `.yml` for preview/sanity purposes (e.g., pre-computed SCF energy, band structure data). These are NOT part of the demo definition, NOT SSOT, and the demo MUST be fully functional without them.

**Rule D4**: The `.generator_manifest.json` file records the corpus-to-demo mapping, corpus checksums, and generator version. It is generated alongside demos and committed to the repo.

### S1.3 Assets Roots

```
resources/
├── pseudo/                          # QE pseudopotentials (redistributable)
│   ├── Si.upf
│   ├── O.upf
│   ├── ATTRIBUTION                  # REQUIRED: provenance + license
│   └── ...
├── lammps/
│   └── potentials/                  # LAMMPS potentials (redistributable)
│       ├── Cu_u3.eam
│       ├── SiC.tersoff
│       ├── ATTRIBUTION              # REQUIRED
│       └── ...
└── assets/                          # Future: per-engine redistributable assets
    └── <engine>/
        ├── ATTRIBUTION              # REQUIRED
        └── <asset_files>
```

**Rule A1**: Redistributable assets live under `resources/` with an `ATTRIBUTION` file in the same directory documenting provenance and license terms.

**Rule A2**: Proprietary assets MUST NOT exist in the repo under any circumstances.

**Rule A3** (QE pseudopotential rule): ALL pseudopotentials required by QE demos whose `asset_policy` is `"redistributable"` MUST be present under `resources/pseudo/`. Any QE corpus case that references a pseudopotential not found there and whose policy is `"redistributable"` is NOT demo-eligible until the pseudo is added.

**Rule A4**: For other engines with redistributable assets: the assets MUST be vendored under `resources/` (with `ATTRIBUTION`) before the corpus case can be marked demo-eligible with `asset_policy: redistributable`.

**Rule A5**: Demos requiring proprietary assets (e.g., VASP POTCARs) MAY be demo-eligible with `asset_policy: proprietary`. The proprietary assets themselves MUST NOT be committed. The demo snapshot MUST clearly declare what is required and where the user should obtain it (see S2.1, S3.2).

### S1.4 Curated Index (Documentation)

```
docs/engines/<engine>/CURATED_INDEX.md
```

Each engine's curated index documents the diversity rationale, parser coverage matrix, and validation status for its corpus cases. This file is human-authored documentation (not machine-consumed) and SHOULD be updated when corpus cases are added or removed.

### S1.5 Research Pipeline (Gitignored)

```
.tmp/engine_research/<engine>/       # Gitignored — development-time only
├── raw_web/                         # Downloaded docs
├── extracted/                       # Extracted example files
├── normalized/                      # Cleaned samples (staging area for corpus)
├── runs/                            # Validation runs
├── SOURCES.md                       # Source URLs and attribution
└── CORPUS_INDEX.json                # Master inventory of collected material
```

This directory is the upstream ingestion pipeline. Materials flow: `raw_web/ → extracted/ → normalized/ → tests/inputformat/samples/<engine>/`. The research pipeline is NOT governed by this spec; only the final committed corpus is.

---

## S2. Corpus Schema (Layer A)

### S2.1 `case.yaml` — Required Fields

Every corpus case MUST contain a `case.yaml` with the following fields:

```yaml
# --- REQUIRED (all corpus cases) ---
case_id: si_scf                       # Stable identifier, unique within engine
engine: vasp                          # Must be registered in DriverRegistry
title: "Silicon diamond SCF"          # Human-readable title
description: "Basic Si diamond ..."   # One-line description
workflow_tags: [scf, electronic]      # From controlled vocabulary (see S2.4)
species: [Si]                         # Chemical elements present

# --- REQUIRED (translation metadata) ---
demo_eligible: true                   # Whether to include in Layer B generation
step_type_gen: scf                    # GEN step type intent
step_type_spec: vasp_scf              # SPEC step type for execution (see S2.2)

# --- REQUIRED if demo_eligible: true ---
demo_slug: vasp_si_scf               # Stable demo identifier, globally unique
                                      # Independent of directory name
                                      # Becomes Layer B filename: <demo_slug>.yml

# --- CONDITIONAL ---
asset_requirements:                   # REQUIRED if demo needs external assets
  pseudopotentials:                   # List of required pseudo files
    - file: Si.upf
      source: resources/pseudo        # "resources/pseudo" | "resources/..." | "bundled"
  potentials: []                      # e.g., for LAMMPS
  basis_sets: []                      # e.g., for Gaussian/ORCA (usually built-in)
  proprietary:                        # REQUIRED if asset_policy: proprietary
    - type: potcar                    # Asset type label
      description: "VASP PAW PBE pseudopotentials for Si"
      species: [Si]
      obtain_from: "VASP POTCAR library (requires VASP license)"
asset_policy: redistributable         # "redistributable" | "proprietary" | "none"
required_engine: vasp                 # Engine binary needed to run (REQUIRED)
availability: requires_local_install  # "bundled" | "open_source" | "requires_local_install"

# --- REQUIRED if demo_eligible: false ---
exclusion_reason: null                # Why not demo-eligible (see S3)

# --- OPTIONAL ---
functional: PBE                       # Exchange-correlation functional
basis_set: null                       # Basis set (molecular codes)
attribution: "VASP manual §6.1"       # Source/credit for the input
difficulty: beginner                  # "beginner" | "intermediate" | "advanced"
recommended_analysis: scf             # Analysis type for GUI auto-open
estimated_runtime_seconds: 30         # Rough runtime on 4-core desktop
multi_step: false                     # True if demo is a multi-step workflow
steps:                                # REQUIRED if multi_step: true
  - step_type_gen: scf
    step_type_spec: qe_scf
    input_files: [si_scf.in]
  - step_type_gen: nscf
    step_type_spec: qe_nscf
    input_files: [si_nscf.in]
    depends_on: [scf]
```

### S2.2 `step_type_spec` in Corpus

The `step_type_spec` field in `case.yaml` is accepted as a controlled-corpus convenience. Because the corpus is a curated, one-time-authored dataset (not production code), including both `step_type_gen` and `step_type_spec` is permitted.

**SHOULD**: The translator SHOULD treat the corpus `step_type_spec` value as an **assertion check**. The translator derives the expected `step_type_spec` from `engine` + `step_type_gen` via the engine driver's step type specs. If the derived value disagrees with the `case.yaml` value, the translator MUST emit an error (not silently override). This guards against stale corpus metadata.

### S2.3 Directory Naming and `demo_slug`

**Rule CN1**: Corpus directory names (`<dir_name>`) MAY contain leading digits, hyphens, and may preserve upstream naming conventions. They serve only as filesystem identifiers.

**Rule CN2**: The `case_id` field in `case.yaml` is the stable corpus-level identifier. It MUST be unique within its engine directory. It need not match the directory name.

**Rule CN3**: The `demo_slug` field is the stable demo-level identifier. It MUST be globally unique across all engines. It is independent of both the directory name and `case_id`. It becomes the Layer B filename stem.

**Rule CN4**: Attribution for the original source MUST be carried in the `attribution` field of `case.yaml` and in the corpus root index, not encoded in the directory name.

### S2.4 Controlled Vocabulary for `workflow_tags`

Workflow tags MUST be drawn from this vocabulary:

| Category | Allowed Values |
|----------|---------------|
| Calculation type | `scf`, `relax`, `vc_relax`, `cell_opt`, `bands`, `dos`, `pdos`, `nscf`, `phonon`, `dfpt`, `md`, `tddft`, `gw`, `bse`, `neb`, `frequencies`, `opt`, `scan`, `ts` |
| Physics | `electronic`, `ionic`, `magnetic`, `spin`, `soc`, `hubbard`, `vdw`, `hybrid`, `solvation`, `multireference`, `relativistic` |
| System type | `solid`, `molecule`, `slab`, `surface`, `1d`, `2d` |
| Method | `dft`, `hf`, `mp2`, `ccsd`, `casscf`, `dmft`, `qmc`, `vmc`, `dmc`, `semi_empirical` |

Additional tags MAY be used for engine-specific features (e.g., `ri`, `rijcosx`, `dispersion`), but SHOULD be documented in the engine's `CURATED_INDEX.md`.

### S2.5 Multi-Step Workflows

For multi-step demos (e.g., QE SCF → NSCF → Bands), `case.yaml` MUST include the `steps` list with explicit ordering and file-to-step mapping. The translator uses this to construct the `CalculationModel` with correct step sequencing.

**Rule CS1**: If `multi_step: true`, the `steps` list is REQUIRED and MUST have at least 2 entries.

**Rule CS2**: If `multi_step: false` (default), the root-level `step_type_gen`, `step_type_spec`, and the directory's input files define a single-step workflow.

**Rule CS3** (no leading relaxation in workflow demos): When a research workflow includes a preliminary relaxation step followed by property calculation steps (e.g., `vc-relax → SCF → NSCF → DOS`), the demo MUST omit the relaxation step and start from the property pipeline (e.g., `SCF → NSCF → DOS`). Relaxation is a separate concern and should be its own demo if needed. This keeps workflow demos focused and fast. The SCF step in the property pipeline uses a pre-relaxed structure (equilibrium lattice parameters) from the corpus.

**Rule CS4** (demo runtime limit): A demo MUST complete within approximately 5 minutes of wall-clock time on a single-core desktop (serial execution). Demos that take significantly longer (e.g., large supercells, very high cutoffs, or computationally expensive post-processing like GIPAW NMR) MUST NOT be demo-eligible. Such cases may remain in the corpus for parser testing but with `demo_eligible: false` and `exclusion_reason: "runtime exceeds demo limit"`.

**Rule CS5** (demo atom count): Demos SHOULD use small systems (typically ≤ 20 atoms). Demos with more than ~30 atoms SHOULD NOT be demo-eligible unless the calculation type inherently requires a larger system (e.g., a minimal slab). Systems like full surface reconstructions (56+ atoms), vacancy supercells (64 atoms), or NEB chains are too large for demos.

**Rule CS6** (runtime flagging): The ref pack generator (`tools/demo_store/generate_ref_packs_realrun.py`) MUST emit a machine-readable results matrix JSON after each run. Any demo whose wall-clock time exceeds **10 minutes** MUST be flagged as a potential dropout candidate in the report. Flagging does NOT automatically remove the demo — only a human decision can drop a demo. The generator SHOULD print a clear warning for flagged demos. See also Rule CS4 (5-minute soft limit for demo eligibility).

---

## S3. Corpus Root Index

### S3.1 Purpose

The corpus root index (`tests/inputformat/samples/corpus_index.yaml`) is the **authoritative registry** that determines which corpus cases become demo projects. The translator reads this file to decide what to generate. No corpus case becomes a demo without an entry here.

### S3.2 Schema

```yaml
# tests/inputformat/samples/corpus_index.yaml
schema_version: 1
entries:
  # --- Example: redistributable assets, fully self-contained ---
  - engine: qe
    case_id: si_scf
    dir_name: 00_si_scf
    demo_eligible: true
    demo_slug: qe_si_scf
    runnable: true                       # Runnable given engine binary + vendored assets
    asset_policy: redistributable
    required_engine: qe
    availability: open_source            # "bundled" | "open_source" | "requires_local_install"
    required_assets:
      - type: pseudopotential
        file: Si.upf
        source: resources/pseudo         # In-repo path
        vendored: true                   # Asset is committed in repo
    exclusion_reason: null
    attribution: "QE tutorial §3"

  # --- Example: no external assets needed ---
  - engine: orca
    case_id: water_sp
    dir_name: water_sp
    demo_eligible: true
    demo_slug: orca_water_sp
    runnable: true
    asset_policy: none
    required_engine: orca
    availability: requires_local_install
    required_assets: []
    exclusion_reason: null
    attribution: "ORCA manual §4.1"

  # --- Example: proprietary assets, demo-eligible but requires user setup ---
  - engine: vasp
    case_id: si_scf
    dir_name: si_scf
    demo_eligible: true
    demo_slug: vasp_si_scf
    runnable: true                       # Runnable IF user has VASP + POTCARs
    asset_policy: proprietary
    required_engine: vasp
    availability: requires_local_install # VASP is commercial
    required_assets:
      - type: potcar
        species: [Si]
        source: "VASP PAW PBE POTCAR library"
        vendored: false                  # NOT in repo — user must provide
        obtain_from: "https://www.vasp.at (requires VASP license)"
    exclusion_reason: null
    attribution: "VASP manual §6.1"

  # --- Example: not demo-eligible (parser testing only) ---
  - engine: gaussian
    case_id: hcn_scan
    dir_name: hcn_scan
    demo_eligible: false
    demo_slug: null
    runnable: true
    asset_policy: none
    required_engine: gaussian
    availability: requires_local_install
    required_assets: []
    exclusion_reason: "Parser test case only; not a meaningful standalone demo"
    attribution: "Gaussian manual"
```

### S3.3 Classification Rules

**Rule CI1**: Every corpus case under `tests/inputformat/samples/<engine>/<dir_name>/` MUST have a corresponding entry in `corpus_index.yaml`. Orphan directories (present on disk but absent in index) MUST be caught by a gate test.

**Rule CI2**: `demo_eligible: true` MUST only be set when ALL of the following hold:
  - The `case.yaml` contains all fields required for translation (including `demo_slug`, `step_type_gen`, `step_type_spec`).
  - If `asset_policy` is `"redistributable"`, ALL required assets with `vendored: true` are present in-repo at their declared `source` paths (e.g., `resources/pseudo/Si.upf` exists).
  - If `asset_policy` is `"proprietary"`, all proprietary requirements are fully documented (`required_assets[].obtain_from` is non-empty).
  - The case is believed to be runnable given the engine binary and required assets.

**Rule CI3**: Corpus cases with `asset_policy: proprietary` MAY be `demo_eligible: true` provided they carry complete requirement labels (see Rule CI2). The demo snapshot MUST propagate these labels so that the GUI, daemon, and integrity suites can determine runnability at load/run time.

**Rule CI4**: If `demo_eligible: false`, the `exclusion_reason` field MUST be a non-empty string explaining why.

**Rule CI5**: The `demo_slug` field MUST be globally unique across all entries where `demo_eligible: true`. Entries with `demo_eligible: false` MUST have `demo_slug: null`.

**Rule CI6**: The `corpus_index.yaml` and the individual `case.yaml` files MUST agree on `demo_eligible`, `demo_slug`, `engine`, and `case_id`. Disagreements MUST be caught by a gate test. The corpus index is the authoritative source; `case.yaml` values serve as cross-checks.

**Rule CI7**: The `required_engine` field MUST name the engine binary needed to execute the demo. The `availability` field classifies how the user obtains it:
  - `"bundled"`: Shipped with QMatSuite (e.g., xTB).
  - `"open_source"`: Freely available but user must install separately (e.g., QE, ORCA for academic use).
  - `"requires_local_install"`: Requires user to obtain and install, possibly with a commercial license (e.g., VASP, Gaussian).

---

## S4. Translator / Generator Contract

### S4.1 Single Writer Rule

**Rule T1**: There MUST be exactly one translator program that produces all demo projects. No other program, script, or manual process may write to `resources/demo_projects/`.

**Rule T2**: The translator MUST be idempotent. Running it twice on unchanged corpus and assets MUST produce byte-identical output (no timestamp jitter, no random ULIDs).

### S4.2 Input

The translator reads:
1. `tests/inputformat/samples/corpus_index.yaml` — to determine which cases are demo-eligible.
2. For each eligible case: the `case.yaml` and engine input files in the corpus directory.
3. Asset files from `resources/` as needed (e.g., pseudo SHA computation for redistributable assets).

### S4.3 Translation Pipeline

The translator MUST execute the following steps for each eligible corpus case:

1. **Validate**: Verify `corpus_index.yaml` entry agrees with `case.yaml`. Verify required redistributable assets exist in-repo. Verify `step_type_spec` assertion (see S2.2). If validation fails, FAIL loudly — do not skip silently.

2. **Parse**: Read engine input files using the `inputformat` parse pipeline (`parse_engine_inputs()` or the engine's custom parser from `inputspec.py`). Extract `params: dict` and `structure: dict | None`.

3. **Map**: Convert parsed data to QMatSuite domain objects:
   - `params` → step parameters (respecting managed/injected parameter rules)
   - `structure` → `StructureModel` (pymatgen `Structure` or `Molecule`)
   - `case.yaml` metadata → `CalculationModel` fields (`engine_family`, `step_type_spec`, `step_type_gen`)

4. **Assemble**: Construct a `ProjectSnapshot` containing:
   - Project metadata (name, slug derived from `demo_slug`)
   - Structure(s)
   - Calculation(s) with step(s)
   - Pseudo/asset requirements
   - Demo gallery metadata (`meta` section)
   - **Snapshot ULIDs**: deterministic identifiers per S4.4

5. **Serialize**: Write snapshot to `resources/demo_projects/<demo_slug>.yml`.

6. **Manifest**: Update `.generator_manifest.json` with corpus checksums and generation metadata.

### S4.4 Snapshot ULID Determinism

**Rule T3**: The translator MUST embed **stable, deterministic snapshot ULIDs** in the generated `.yml`. Specifically:
- All ULIDs within a demo snapshot (project, structures, calculations, steps) MUST be derived from a deterministic seed (e.g., `ULID(sha256(demo_slug + component_name + salt))`) so that re-generation from unchanged corpus produces byte-identical output.
- The exact derivation algorithm is an implementation detail, but MUST be documented and MUST be deterministic given identical inputs.

**Rule T3a**: Snapshot ULID determinism applies ONLY to the translator's output (the `.yml` files in Layer B). It does NOT apply to materialization. When a snapshot is loaded and materialized into a live project workspace, all ULIDs in the on-disk SSOT MUST be freshly generated (see S6.2).

**Rule T4**: YAML output MUST use a stable serialization order (sorted keys or explicit field ordering). No floating-point jitter (use sufficient precision, round-trip safe).

### S4.5 Pseudopotential and Asset Handling

**Rule T5**: For demos with `asset_policy: redistributable`, the translator MUST resolve asset filenames against their declared in-repo paths and include integrity metadata in the snapshot:
- For QE pseudos: `pseudo.directory`, `pseudo.files`, `pseudo.pseudo_sha256`
- For LAMMPS potentials: equivalent fields

If any referenced redistributable asset is missing from the declared in-repo path, the translator MUST fail (not skip). The corpus index should have caught this earlier (Rule CI2), but the translator provides defense-in-depth.

**Rule T6**: For demos with `asset_policy: proprietary`, the translator MUST:
- Include `asset_policy: proprietary` in the snapshot's `meta` section.
- Include `asset_requirements.proprietary` listing what is needed, with `obtain_from` instructions.
- NOT attempt to resolve, hash, or stage the proprietary assets.
- Still succeed in generating the snapshot (the snapshot is a portable package; it need not reference actual files for proprietary assets).

### S4.6 Relationship to Future Import Pipeline

The translator SHOULD be structured so that its core logic (parse → map → assemble) can be reused for the "import user project" feature. Specifically:
- The parse step MUST use the same `inputformat` parsers that the import pipeline will use.
- The map step SHOULD be factored as a reusable function, not embedded in the generator script.
- The translator MUST NOT contain hardcoded demo-specific logic that would prevent reuse.

### S4.7 Generator Manifest

The `.generator_manifest.json` file MUST contain:

```json
{
  "generator_version": "1.0.0",
  "generated_at": "2026-02-11T12:00:00Z",
  "corpus_root": "tests/inputformat/samples",
  "corpus_index_checksum": "<sha256 of corpus_index.yaml>",
  "demos": {
    "<demo_slug>": {
      "engine": "<engine>",
      "case_id": "<case_id>",
      "dir_name": "<dir_name>",
      "corpus_path": "tests/inputformat/samples/<engine>/<dir_name>",
      "corpus_checksum": "<sha256 of case directory contents>",
      "output_file": "resources/demo_projects/<demo_slug>.yml",
      "output_checksum": "<sha256 of generated yml>",
      "asset_policy": "redistributable|proprietary|none"
    }
  }
}
```

---

## S5. Demo Projects Schema (Layer B)

### S5.1 Single-File Snapshot

A demo project is defined by exactly one `.yml` file conforming to the `ProjectSnapshot` schema (version 1). This is the same format used by the future "snapshot/export project" feature — a single file that fully describes a project.

**Rule DP1**: The `.yml` file MUST be self-sufficient. Loading a demo means loading exactly this file. No external files are required to materialize a runnable project (redistributable asset staging is handled at materialization time from `resources/`; proprietary asset staging is the user's responsibility per the declared requirements).

### S5.2 Snapshot Format

```yaml
version: 1

# ─── SSOT metadata + content (preserved through roundtrip, modulo ULID rewrite) ───

project:
  meta:                               # SSOT metadata
    ulid: <snapshot_ulid>             # Stable/deterministic in demo snapshot;
                                      # replaced with fresh ULID on materialization
    name: <project_name>
    slug: <project_slug>
    path: "."
    kind: project
  settings: {}

structures:
  - meta:                             # SSOT metadata
      ulid: <snapshot_ulid>
      name: <structure_name>
      slug: <structure_slug>
      path: "structures/<slug>.json"
      kind: structure
    data:                             # Pymatgen Structure or Molecule dict
      "@module": "pymatgen.core.structure"
      "@class": "Structure"           # or "Molecule"
      lattice: { ... }               # For Structure only
      sites: [ ... ]

calculations:
  - meta:                             # SSOT metadata
      ulid: <snapshot_ulid>
      name: <calculation_name>
      slug: <calculation_slug>
      path: "calculations/<slug>"
      kind: calculation
    engine_family: <engine>           # REQUIRED: explicit, no inference
    mode: normal
    working_dir: raw
    structure_ulid: <ref>             # References a structure's snapshot ULID;
                                      # remapped to fresh ULID on materialization
    species_map: { ... }
    steps:
      - meta:                         # SSOT metadata
          ulid: <snapshot_ulid>
          name: <step_name>
          slug: <step_slug>
          path: "steps/<slug>.step.yaml"
          kind: step
        step_type_gen: <gen_type>     # REQUIRED
        step_type_spec: <spec_type>   # REQUIRED
        parameters: { ... }           # Parsed from corpus input files

pseudo:                               # CONDITIONAL: present if engine needs pseudos
  directory: pseudo
  files: [ "Si.upf", ... ]
  pseudo_sha256: { "Si.upf": "<hash>", ... }  # Only for redistributable
  pseudo_sha_family: "..."

# ─── Demo gallery metadata (NOT SSOT; MAY be omitted by generic project export) ───

meta:
  ulid: <demo_slug>
  title: "<Display Title>"
  subtitle: "<Workflow Description>"
  tags: [ ... ]
  difficulty: "beginner"
  recommended_analysis: "scf"
  asset_policy: "redistributable"     # or "proprietary" or "none"
  asset_requirements: { ... }         # Propagated from corpus (including proprietary reqs)
  required_engine: "<engine>"
  availability: "open_source"         # or "requires_local_install" or "bundled"
  generator_version: "1.0.0"
  corpus_engine: "<engine>"
  corpus_case_id: "<case_id>"
  corpus_checksum: "<sha256>"
```

### S5.3 Two Categories of Metadata

The snapshot contains two distinct categories of metadata:

1. **SSOT metadata** (`project.meta`, `structures[].meta`, `calculations[].meta`, `steps[].meta`): Structural identity of the project components — ulid, name, slug, path, kind. This metadata MUST be preserved through materialization (with ULID rewrite) and re-snapshotting. It is part of the project domain model.

2. **Demo gallery metadata** (top-level `meta` section): Display catalog information — title, subtitle, tags, difficulty, attribution, asset requirements, generator provenance. This metadata is for the GUI gallery and demo management. It is NOT part of the project domain model, NOT SSOT, and MAY be omitted by a generic `export_project_to_snapshot()` that is not demo-aware.

**Rule DP1a**: The demo gallery metadata section MUST NOT duplicate or contradict SSOT metadata. The gallery `meta.ulid` is the demo slug (a display identifier), not a project ULID.

### S5.4 Required Constraints

**Rule DP2**: `engine_family` MUST be explicitly set on every calculation. No inference, no fallback. (Enforced by existing gate `test_demo_integrity.py`.)

**Rule DP3**: Every step MUST have both `step_type_gen` and `step_type_spec`. No bare `step_type`.

**Rule DP4**: `step_type_spec` prefix MUST match `engine_family` or a declared companion engine. (Enforced by existing gate `test_demo_integrity.py`.)

**Rule DP5**: If the calculation requires a structure, `structure_ulid` MUST reference a structure in the `structures` list (using the snapshot's ULIDs). The structure data MUST be embedded in the snapshot (not an external file reference). On materialization, the ULID cross-reference MUST be remapped to the fresh materialized ULIDs.

**Rule DP6**: The demo gallery `meta` section MUST include `generator_version`, `corpus_engine`, `corpus_case_id`, and `corpus_checksum` to enable traceability from demo project back to corpus source.

### S5.5 Reference Artifacts (Optional)

Pre-computed analysis results MAY be shipped alongside the demo `.yml` as separate JSON files. Naming convention: `<demo_slug>.<step_slug>.<analysis_type>.json` (e.g., `qe_si_bands.bands.bands.json`). For single-step demos, the step slug MAY be omitted: `<demo_slug>.<analysis_type>.json`.

**Rule DP7**: Reference artifacts are NOT part of the demo definition. They are supplementary data for GUI preview and sanity checking. The demo MUST be fully functional without them.

**Rule DP8**: Reference artifacts MUST be generated deterministically (by running the demo and extracting analysis results). They MUST NOT be hand-edited.

**Rule DP9**: Reference artifacts are OPTIONAL. Their absence MUST NOT cause any load, materialize, run, or analysis failure.

### S5.6 Provenance Recommendation

**SHOULD**: When loading a demo snapshot and materializing it into a project, the system SHOULD record in its provenance store (e.g., the SQLite timeline defined in `PROVENANCE_VERSIONED_HISTORY_SPEC.md`) that the project originated from a demo snapshot. The provenance entry SHOULD include:
- `demo_slug` (the demo identifier)
- `corpus_engine` and `corpus_case_id` (the corpus origin)
- `generator_version` (the translator version that produced the snapshot)
- `attribution` (original source credit)

This is a spec-level recommendation for audit/traceability; the provenance store is governed by its own spec.

---

## S6. ULID Lifecycle and Snapshot Roundtrip Contract

### S6.1 ULID Lifecycle

Demo snapshots and materialized projects use ULIDs in fundamentally different ways. This section defines the lifecycle to eliminate ambiguity.

#### Phase 1: Snapshot Generation (translator output)

The translator produces a demo `.yml` with **snapshot ULIDs** — deterministic identifiers derived from the corpus content (see Rule T3). These ULIDs are stable across regeneration of the same demo. They serve as portable package-level identifiers within the `.yml` file.

Snapshot ULIDs are used for:
- Internal cross-references within the snapshot (e.g., `structure_ulid` in a calculation referencing a structure's ULID)
- Diff stability (regenerating unchanged demos produces identical files)

#### Phase 2: Materialization (loading a snapshot into a workspace)

When a snapshot is loaded via `create_demo_project()` (or equivalent) and written to disk as SSOT YAML files, ALL ULIDs MUST be **freshly generated**. The snapshot ULIDs are discarded. This is the universal rule for writing new on-disk SSOT:

**Rule UL1**: Any time new YAML SSOT files are written to disk (whether from a demo snapshot, a user import, or any other source), all project/calculation/step/structure ULIDs in the on-disk files MUST be freshly generated. This prevents identity collisions between projects.

**Rule UL2**: Internal cross-references (e.g., `structure_ulid` in a calculation) MUST be remapped from snapshot ULIDs to the corresponding fresh ULIDs during materialization.

**Rule UL3**: Once ULIDs are written to on-disk SSOT files, they MUST NOT be edited or rewritten. The on-disk ULID is the project's identity from that point forward.

#### Phase 3: Re-snapshotting (exporting a materialized project)

Exporting a live project back into a single `.yml` snapshot is a mechanical collection/compile operation. It reads the on-disk SSOT files and assembles them into a single YAML document.

**Rule UL4**: Re-snapshotting MUST preserve the on-disk ULIDs in the exported snapshot. It does NOT regenerate or rewrite ULIDs. The exported snapshot reflects the project's actual identity.

#### Consequence

A demo snapshot's ULIDs and a re-snapshot's ULIDs will NOT match. This is by design:

```
demo_snapshot.yml          →  snapshot ULIDs (deterministic, from corpus)
  ↓ load/materialize
on-disk SSOT               →  materialized ULIDs (fresh, unique)
  ↓ export/re-snapshot
re-snapshot.yml            →  materialized ULIDs (preserved from disk)
```

The semantic equivalence contract (section SE) accounts for this. The ULID lifecycle rules (UL1–UL4) apply equally to both Path A (load) and Path B (authoring) materialization.

### S6.2 Roundtrip and Equivalence

The detailed roundtrip definitions (Roundtrip A — load path, Roundtrip B — authoring path), the canonical semantic diff rules, and the real-run validation contracts are defined in **section SE** (Semantic Equivalence and Roundtrip Contracts).

**Rule SE-ref**: All references to "roundtrip" or "content-equivalence" in this spec refer to the canonical semantic diff defined in SE.3. The ULID lifecycle rules in this section (S6) define how ULIDs flow through materialization; section SE defines how to compare the results.

---

## S7. Integrity Test Suites

### S7.1 Scope

Both integrity suites iterate ONLY the demo projects in Level-2 (`resources/demo_projects/*.yml`). Corpus cases that are not demo-eligible are not tested by these suites (they are tested by parser/writer unit tests and the corpus harness instead).

> **See also SE.4** for a concise statement of what integrity tests are and are NOT.

### S7.2 Backend Integrity Suite (T1)

> **WARNING**: This suite is a FAST structural validation. It DOES NOT execute engines and DOES NOT prove demos are runnable. See section **DB** (Demo Baseline) for the full acceptance criteria including real engine runs.

**Purpose**: Verify that every demo project can be loaded, materialized, and structurally validated through the daemon/service layer. This is Stage (B) of the Demo Baseline — necessary but not sufficient.

**Lifecycle per demo**:

1. **Load**: `service.create_demo_project(target_dir, name, demo_id)` — MUST succeed for all demos regardless of asset policy.
2. **Materialize**: Verify that materialized project directory contains expected files (YAML, structure JSON, step YAML) with fresh ULIDs (per Rule UL1).
3. **Asset staging**: For `redistributable`/`none` demos: verify assets are correctly staged; missing redistributable assets are a hard **FAIL**. For `proprietary` demos: check if proprietary assets are available in the test environment (see S7.4).
4. **Roundtrip A** (RECOMMENDED): Re-snapshot the materialized project and verify semantic equivalence per SE.3.
5. **Run** (conditional): Execute the calculation if the engine binary AND all required assets are available. Otherwise, skip per S7.4.
6. **Parse output**: If run completed, parse outputs using the engine's `OutputParser`. Verify `Digest` fields are populated.
7. **Analysis**: If run completed, invoke analysis transforms (SCF convergence, band structure, DOS, etc. per `recommended_analysis`). Verify return types and array shapes.
8. **Sanity checks**: Energy is finite, forces array shape matches atom count, no NaN values.

**Rule I1**: The backend suite MUST NOT be collected by default `pytest` invocation. It MUST be in a dedicated directory (`tests/integrity/backend/`) or marked with a custom pytest marker (`@pytest.mark.integrity`) and excluded from default collection via `conftest.py` or `pytest.ini`.

**Invocation**: `python -m pytest tests/integrity/backend/ -v --tb=short` (explicit opt-in).

### S7.3 GUI End-to-End Integrity Suite (T2)

**Purpose**: Verify that every demo is renderable and functional through the full GUI stack.

**Lifecycle per demo**:

1. **Gallery render**: Navigate to demo gallery, verify demo card is present with correct title, tags, difficulty, and asset requirement labels.
2. **Load**: Click demo card, create project in temp directory.
3. **Project view**: Verify project tree renders correctly (structure, calculation, steps).
4. **Run** (conditional): If engine and assets available, trigger run and wait for completion. Otherwise, skip per S7.4.
5. **Analysis view**: Navigate to recommended analysis panel. Verify panel renders without errors.
6. **Digest render**: If run completed, verify digest panel shows expected data (energy value, convergence plot, etc.).

**Rule I2**: The GUI suite MUST NOT be collected by default Playwright/e2e invocation. It MUST use a separate test file or config (e.g., `gui/tests/e2e/integrity/demo_integrity.spec.ts`) excluded from the default `playwright.config.ts` project.

**Invocation**: `npx playwright test gui/tests/e2e/integrity/` (explicit opt-in).

### S7.4 Failure and Skip Rules

Integrity suites distinguish between demos that MUST pass and demos that MAY be skipped based on the test environment's capabilities.

| Condition | Behavior | Status |
|-----------|----------|--------|
| Engine binary not installed | Skip run + parse + analysis; load + materialize MUST still pass | `skipped_no_engine` |
| Proprietary assets not available in test environment | Skip run + parse + analysis; load + materialize MUST still pass | `skipped_proprietary_assets` |
| Redistributable asset missing from repo | **FAIL** — repo integrity violation | `failed` |
| Load or materialize failure (any demo) | **FAIL** | `failed` |
| Run attempted and fails (engine + assets available) | **FAIL** | `failed` |
| Run completes but produces wrong results | **FAIL** | `failed` |

**Rule I3**: Load and materialization MUST succeed for ALL demos in Layer B, regardless of asset policy. A demo that cannot even be loaded/materialized is broken and MUST be fixed.

**Rule I4**: When a test environment declares that it has a specific engine and its assets (e.g., a developer workstation with VASP installed and POTCARs configured), the integrity suite MUST attempt to run those demos. If the run fails in such an environment, it is a hard **FAIL**, not a skip.

**Rule I5**: The mechanism for declaring environment capabilities (e.g., env vars, config file) is an implementation detail. The spec requires only that the integrity suite can distinguish "asset not available (skip)" from "asset declared available but run failed (fail)".

### S7.5 Report Format

Both suites MUST produce a JSON report at `<output_dir>/integrity_report.json`:

```json
{
  "suite": "backend|gui_e2e",
  "generated_at": "2026-02-11T12:00:00Z",
  "environment": {
    "platform": "darwin",
    "python_version": "3.11.8",
    "available_engines": ["qe", "orca"],
    "available_proprietary_assets": ["vasp_potcar"],
    "qmatsuite_version": "2.0.0-dev"
  },
  "summary": {
    "total": 25,
    "passed": 15,
    "failed": 1,
    "skipped_no_engine": 5,
    "skipped_proprietary_assets": 4,
    "duration_seconds": 342.1
  },
  "demos": [
    {
      "demo_id": "qe_si_scf",
      "engine": "qe",
      "asset_policy": "redistributable",
      "status": "passed|failed|skipped_no_engine|skipped_proprietary_assets",
      "duration_seconds": 12.3,
      "failure_reason": null,
      "lifecycle_stages": {
        "load": "passed",
        "materialize": "passed",
        "asset_staging": "passed",
        "roundtrip": "passed",
        "run": "passed",
        "parse_output": "passed",
        "analysis": "passed",
        "sanity": "passed"
      },
      "sanity_metrics": {
        "energy_eV": -10.234,
        "n_atoms": 2,
        "forces_shape": [2, 3],
        "converged": true
      }
    }
  ]
}
```

**Rule I6**: The report file MUST be written to a gitignored location (default: `.tmp/integrity_reports/`). CI pipelines MAY upload it as a build artifact.

**Rule I7**: The report MUST NOT contain absolute paths, usernames, or hostnames (conforming to Law S1).

---

## S8. Governance Rules

### S8.1 No Hand-Editing Generated Demos

**Rule G1**: Files in `resources/demo_projects/` MUST NOT be manually created or edited. All changes MUST flow through the corpus → translator pipeline.

**Enforcement**: A gate test (`tests/gates/test_demo_generated.py`) MUST verify that:
- Every `.yml` file in `resources/demo_projects/` has a corresponding entry in `.generator_manifest.json`.
- The `output_checksum` in the manifest matches the actual file checksum.
- No `.yml` file exists without a manifest entry.

If the gate fails, the remedy is: fix the corpus, re-run the translator, commit both corpus changes and regenerated demos.

### S8.2 Corpus Index Consistency

**Enforcement**: A gate test (`tests/gates/test_corpus_index.py`) MUST verify that:
- Every directory under `tests/inputformat/samples/<engine>/` that contains a `case.yaml` has a corresponding entry in `corpus_index.yaml`.
- No orphan entries exist in `corpus_index.yaml` (entry without corresponding directory).
- For every `demo_eligible: true` entry with `asset_policy: redistributable`: required assets with `vendored: true` exist in-repo at declared paths.
- For every `demo_eligible: true` entry with `asset_policy: proprietary`: `required_assets[].obtain_from` is non-empty for all proprietary items.
- `demo_slug` values are globally unique among eligible entries.
- `case.yaml` and `corpus_index.yaml` agree on `demo_eligible`, `demo_slug`, `engine`, and `case_id`.

### S8.3 Adding a New Demo

The process for adding a new demo MUST follow this pipeline. Each step validates the output of the previous step, ensuring end-to-end correctness.

**Phase 1: Curate raw input files (Layer A)**

1. **Obtain raw input files**: Get engine-native input files from a trustworthy source — official engine tutorials, published examples, manual appendices, or the project's own `tests/data/` reference collection. Raw files MUST be complete and runnable as-is (all required cards, coordinates, parameters). Record the source in `case.yaml:attribution`.
2. **Place in corpus directory**: Create `tests/inputformat/samples/<engine>/<dir_name>/` and place the raw input files there **unchanged**. Do not edit, truncate, or "clean up" the files — they must be faithful copies of the originals. Write `case.yaml` with all required fields per S2.1.
3. **Verify raw files run with real engine** (RECOMMENDED): Before proceeding, run the raw input files directly with the engine binary to confirm they produce correct output. This catches problems at the source before they propagate through the pipeline. Document the verification status (e.g., `estimated_runtime_seconds`, `ref_values.yaml`).

**Phase 2: Generate demo snapshot (Layer B)**

4. **Stage assets**: If the demo requires redistributable assets not yet in `resources/`, add them with proper `ATTRIBUTION` files. If the demo requires proprietary assets, document them in `asset_requirements.proprietary` with `obtain_from` instructions.
5. **Add to corpus index**: Add entry to `corpus_index.yaml` with `demo_eligible: true`, globally unique `demo_slug`, and all classification fields.
6. **Run translator**: Execute the translator (`tools/demo_store/generate_all.py`) to regenerate all demo projects. Verify the new demo `.yml` appears in `resources/demo_projects/` with correct structure data, parameters, and step types.
7. **Update curated index**: Update `docs/engines/<engine>/CURATED_INDEX.md` with the new case.

**Phase 3: Real-run verification and ref pack generation (Demo Baseline Stages C+D — MANDATORY)**

8. **Run demo through daemon**: Use the ref pack generator (`tools/demo_store/generate_ref_packs_realrun.py`) or manually via `QVService` to: load the demo → materialize a project → run the calculation with the real engine → parse output → run analysis. This is the definitive proof that the demo works end-to-end. **Per Rule DB-ND, this step MUST NOT be deferred or skipped.** "Engine not available" is not a valid excuse — see Rule DB-EA.
9. **Generate ref pack**: The real-run MUST attempt ref-pack generation for the demo. If the run succeeds and produces analysis output, serialize the canonical primitive bundles as a ref pack under `resources/demo_projects/ref_packs/<demo_slug>/`. A ref pack MAY be empty if no analysis provider exists, but the attempt MUST be recorded.
10. **Debug failures**: If the real run fails, the defect is in the pipeline (corpus files, parser, translator, materialization, engine handler, or analysis). Fix at the appropriate layer — always fix corpus (Layer A) first, then regenerate Layer B. Do NOT patch Layer B directly.

**Phase 4: Commit (with Demo Baseline closeout)**

11. **Commit**: Commit corpus entry, corpus index, regenerated demos, manifest, curated index, ref pack, and **Demo Baseline closeout report** (`docs/demo_store/DEMO_BASELINE_CLOSEOUT.md`) together. The closeout report MUST include evidence of all four Demo Baseline stages per section DB.5.

**Rule G2a** (real-run gate for new demos — MANDATORY): A new demo MUST NOT be merged without a successful real-run verification (Phase 3, step 8). Per Rule DB-ND, deferral is not permitted. Per Rule DB-EA, "engine not available" is not a valid excuse — install the engine or demote the demo. The closeout report MUST include the real-run results for the new demo.

**Rule G2**: A PR that adds or modifies demo-eligible corpus cases MUST include the regenerated Layer B output in the same commit. Partial updates (corpus without regeneration, or regeneration without corpus change) MUST NOT be merged.

### S8.4 Adding a Non-Demo Corpus Case

For corpus cases that are NOT demo-eligible (parser testing only):

1. **Create corpus entry**: Add directory with input files and `case.yaml`. Set `demo_eligible: false` and provide `exclusion_reason`.
2. **Add to corpus index**: Add entry with `demo_eligible: false`, `demo_slug: null`, and `exclusion_reason`.
3. **Commit**: No translator run needed. Commit corpus entry and index update.

### S8.5 Removing a Demo

1. Remove the corpus directory (or set `demo_eligible: false` in both `case.yaml` and `corpus_index.yaml`).
2. Re-run the translator (which will remove the corresponding demo project).
3. Commit the changes to corpus, index, and regenerated demo projects together.

### S8.6 Licensing and Attribution

**Rule G3**: Every directory under `resources/` that contains third-party assets MUST include an `ATTRIBUTION` file listing:
- Asset name and version
- Original source URL
- License type (e.g., CC-BY-4.0, LGPL-2.1)
- Copyright holder
- Any modifications made

**Rule G4**: Proprietary assets MUST NOT be committed under any circumstances. The `asset_policy: proprietary` marker plus `obtain_from` instructions are the ONLY permitted references.

**Rule G5**: Corpus cases sourced from external tutorials or manuals MUST include `attribution` in `case.yaml` citing the original source.

### S8.7 Constitutional Alignment

This spec operates within the existing QMatSuite governance framework:

- **SSOT**: Demo snapshots serialize `calculation.yaml` + `step.yaml` equivalent data into a single `.yml`. Upon materialization, the daemon writes canonical SSOT files on disk with fresh ULIDs (Rule UL1). The snapshot itself is NOT runtime SSOT — it is a generation/distribution artifact. The roundtrip contract (S6) guarantees that materialization is semantically lossless.
- **ULID rule**: Any time new YAML SSOT is written to disk, ULIDs are freshly generated. Once written, on-disk ULIDs are immutable. This applies to demo materialization, user project creation, and all other SSOT writes.
- **GEN/SPEC**: Every step in a demo project MUST have both `step_type_gen` and `step_type_spec`. The translator populates both from `case.yaml`.
- **Engine family**: Every calculation MUST have explicit `engine_family`. Existing gate `test_demo_integrity.py` enforces this. The `DriverRegistry` is the authoritative source for valid engine families.
- **No prefix inference**: The translator MUST NOT infer engine from step type prefix. Engine identity comes from `case.yaml:engine`.
- **No silent fallback**: If an engine is unregistered or a step type is unknown, the translator MUST fail loudly.
- **Managed parameters**: Runtime-managed keys (e.g., `outdir`, `pseudo_dir` for QE) MAY be present in corpus input files but MUST be handled by the translator according to the engine's materialization rules. The roundtrip contract (S6.3) accounts for managed-key variance.
- **Provenance**: Loading a demo SHOULD record origin metadata in the provenance system (see S5.6).

---

## S9. Open Questions / Decision Points

**Q1**: **Python-script engines** (GPAW, Psi4, PySCF). These engines have no parseable input files — their "input" is a Python script. Corpus entries for these engines MAY include the Python script and a `case.yaml` with `parser_mode: script` (or similar), but the translator cannot use `parse_engine_inputs()` for them. The translator MUST support a `direct_snapshot` mode where `case.yaml` includes enough metadata to construct the demo project without parsing. This requires a separate design decision for the script-engine translation contract.

**Q2**: **Reference artifacts generation**. ~~Should the translator also produce reference artifacts (pre-computed JSON), or should that be a separate step?~~ **RESOLVED**: Ref packs are a separate post-translation step that REQUIRES real engine runs (see S10.4). The translator produces only the `.yml` snapshot. Ref packs are generated by `tools/demo_store/generate_ref_packs_realrun.py` which loads the demo through `QVService`, runs the engine, and serializes the analysis output. This is not optional — it is the authoritative pipeline verification.

**Q3**: **Existing QE demos with numbered names** (e.g., `00_Si_scf.yml`, `07_Si_bandStructure.yml`). These predate the corpus system and were generated by `tools/demo_generators/verified/generate_qe_demos.py` from hardcoded definitions. Migration path: create corresponding corpus entries in `tests/inputformat/samples/qe/`, add them to `corpus_index.yaml`, then regenerate. The old numbered `.yml` files in `resources/demo_projects/` will be replaced by `demo_slug`-named files.

**Q4**: **Whether to include optional reference outputs in corpus**. Some corpus cases could ship with small reference output files (e.g., a truncated log with final energy) for parser round-trip testing. This is already done via `ref_values.yaml`. Adding actual output files would increase repo size but improve parser test coverage. **Recommendation**: Keep `ref_values.yaml` for numerical references; actual output files belong in `docs/engines/<engine>/golden_refs/` (existing convention), not in corpus.

---

## S10. Reference Packs

Reference packs provide pre-computed analysis primitives for demo projects, enabling "plot without run" — users can view reference band structures, DOS, convergence curves, etc. without running the engine.

### S10.1 Definition

A **reference pack** is a set of pre-computed analysis bundles stored as JSON files. Each bundle contains serialized analysis primitives (e.g., `CanonicalPrimitiveBundle.to_dict()`) that can be loaded and displayed by the GUI.

### S10.2 Storage Layout

```
resources/demo_projects/ref_packs/
    <demo_slug>/
        manifest.json        # Lists available object types + checksums
        bands.json           # Band structure data (if applicable)
        dos.json             # Density of states data (if applicable)
        convergence.json     # SCF convergence data (if applicable)
        ...
```

### S10.3 Manifest Format

Each ref pack directory contains a `manifest.json`:

```json
{
    "demo_slug": "<demo_slug>",
    "engine": "<engine>",
    "generated_at": "<ISO timestamp>",
    "generator_version": "1.0.0",
    "object_types": {
        "convergence": {
            "file": "convergence.json",
            "sha256": "<hash>"
        },
        "bands": {
            "file": "bands.json",
            "sha256": "<hash>"
        }
    }
}
```

### S10.4 Generation — Real-Run Pipeline (REQUIRED)

Reference packs MUST be generated from **real engine runs** through the full `QVService` daemon pipeline. This is the authoritative verification that the entire chain works: corpus → translator → demo YAML → materialize → engine execution → output parse → analysis → canonical primitive serialization. Synthetic or hand-crafted ref packs are prohibited.

**Tool**: `tools/demo_store/generate_ref_packs_realrun.py`

**Pipeline per demo** (mandatory sequence):

1. **Load**: `QVService.create_demo_project(work_dir, demo_slug, demo_slug)` — materializes the demo snapshot into a live project workspace with fresh ULIDs.
2. **Run**: `svc.run.run_calculation(calc_ulid, run_mode="full")` — executes the calculation using the real engine binary. No mocking, no skip, no synthetic output.
3. **Analyze**: `svc.analysis.get_analysis(run_ulid, object_type)` — invokes the standard analysis pipeline (output parser → analysis transforms → canonical primitives).
4. **Serialize**: Write each `CanonicalPrimitiveBundle.to_dict()` as a JSON file in `ref_packs/<demo_slug>/`.

**Rule RP2** (no synthetic ref packs): Every ref pack JSON file MUST originate from a real engine run through the above pipeline. Ref packs MUST NOT be generated from:
- Hand-crafted JSON
- Golden test fixtures (`tests/data/`)
- Synthetic or truncated output files
- Any source other than a complete daemon-level run

**Rule RP3** (engine availability determines ref pack availability): A demo can only have a ref pack if its engine is available in the generation environment. Demos whose engines are unavailable simply have no ref pack — this is acceptable per S10.6 (incremental growth).

**Rule RP4** (ref packs validate the full pipeline): The ref pack generation process serves double duty: it produces GUI-displayable analysis data AND it validates that the corpus → demo → run → analyze pipeline is end-to-end correct. A ref pack that exists is proof that the demo ran successfully. A demo that cannot produce a ref pack has a pipeline defect that must be fixed.

**Lesson learned**: Previous approaches that generated ref packs from golden test fixtures (synthetic output files in `tests/data/`) masked real pipeline defects — broken materialization, missing structure data, incorrect parameter handling, and incompatible step types. These defects were only discovered when attempting real engine runs. The real-run requirement eliminates this class of bugs by construction.

### S10.5 Gate Test

**Rule RP1**: Every ref pack directory MUST contain a valid `manifest.json`. Every JSON file listed in the manifest MUST exist and its SHA256 MUST match. Gate test: `tests/gates/test_ref_packs.py`.

### S10.6 Incremental Growth

Ref packs are optional and grow incrementally. A demo without a ref pack is fully functional — it just cannot display pre-computed analysis. The `has_ref_pack` column in `docs/demo_store/DEMO_MATRIX.md` tracks availability.

---

## S11. Demo Source Field

### S11.1 Purpose

When a demo project is materialized via `create_demo_project()`, the project needs a way to identify itself as a demo and locate its reference pack (if any). The `demo_source` field serves this purpose.

### S11.2 Schema

New field in `project.qv.yml` → `settings.demo_source`:

```yaml
settings:
  demo_source:
    demo_id: "vasp_si_scf"          # demo slug, used as lookup key
    generator_digest: "abc123..."    # from manifest, for staleness check
    engine: "vasp"                   # engine name
    materialized_at: "2025-..."      # ISO timestamp
```

### S11.3 Lifecycle

- **Written by**: `create_demo_project()` at materialization time (Step 2a in implementation plan)
- **Read by**: `get_reference_analysis()` to locate ref packs
- **Constraint**: No SQLite/CAS/provenance dependency — pure filesystem field (C1)
- **Absent for non-demo projects**: Regular user-created projects will not have this field

### S11.4 Reference Analysis Lookup

The `get_reference_analysis()` service method uses `settings.demo_source.demo_id` to:
1. Look up ref pack at `resources/demo_projects/ref_packs/<demo_id>/manifest.json`
2. If the requested `object_type` is present, load and return the JSON bundle
3. Return `None` if no ref pack available

---

*End of specification.*
