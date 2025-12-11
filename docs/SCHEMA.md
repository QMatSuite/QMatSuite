# QuantumVITAS Schema: DAG + ID-only Model

This document describes the current schema for QuantumVITAS projects, workflows, steps, and structures. The schema follows a **DAG (Directed Acyclic Graph) + ID-only** model where all cross-resource references use ULIDs (Universally Unique Lexicographically Sortable Identifiers).

## Core Principles

1. **ID-only cross-references**: All relationships between resources (project → workflow, workflow → structure, workflow → step) use only ULIDs, never selectors (name/slug/path).
2. **No duplication**: Resource metadata (name, slug, path) is stored once in the resource's own file, not duplicated in parent resources.
3. **DAG structure**: Steps inherit structure from their parent workflow; steps do NOT store structure references.

## Schema Structure

### 1. project.qv.yml

The project registry file lists all workflows and structures by ID only:

```yaml
project:
  meta:
    id: 01JXYZ123ABC456DEF789GHI  # ULID
    name: "Si DOS Project"
    slug: "si-dos-project"
    path: "."
    kind: "project"
  settings: {}
workflows:
  - workflow_id: 01KBH0S...  # ✅ Only ID, no meta duplication
structures:
  - structure_id: 01KBH0RF...  # ✅ Only ID, no meta duplication
```

**Key points:**
- `workflow_id` and `structure_id` are ULIDs, not selectors
- No `name`, `slug`, or `path` fields in entries (these come from the resource files themselves)
- Full metadata is loaded from `workflow.yaml` and structure JSON files when needed

### 2. workflow.yaml

Workflow definition with ID-only references:

```yaml
meta:
  id: 01JXYZ123ABC456DEF789GHI  # ULID
  name: si-dos
  slug: si-dos
  path: workflows/si-dos
  kind: workflow
mode: normal
structure_id: 01SABC123...        # ✅ Structure reference (ULID only)
working_dir: raw
steps:
  - step_id: 01TXYZ789...          # ✅ Step reference (ULID only)
    type: scf                       # ✅ Relationship metadata
  - step_id: 01TUVW456...
    type: nscf
```

**Key points:**
- `structure_id` is a ULID pointing to a structure resource
- `step_id` entries are ULIDs pointing to step resources
- Step file locations are resolved via registry using `step_id` (not stored in workflow.yaml)
- Optional `type`, `input`, and `reference` fields may be present for workflow-local metadata
- Optional `structure_name` may be present for display purposes (cosmetic only)

### 3. step YAML (*.step.yaml)

Step specifications contain **only step-local configuration**:

```yaml
meta:
  id: 01KB8FEQWVYJAB16NMRVZ7JYEG  # ULID
  name: scf
  slug: scf
  path: scf.step.yaml
  kind: step
step_type: scf
parameters:
  CONTROL:
    calculation: scf
  SYSTEM:
    ecutwfc: 50
cards:
  K_POINTS:
    option: automatic
    data: [[8, 8, 8, 0, 0, 0]]
species_overrides:
  Si:
    mass: 28.0855
    pseudopot: Si.pbe-n-rrkjus_psl.1.0.0.UPF
kpath_metadata:  # Optional, for band structure calculations
  segments: [...]
```

**Key points:**
- ✅ **NO `structure_id`** - Structure is inherited from workflow.structure_id
- ✅ **NO `parent_workflow_id`** - Parent workflow is implicit from file location (`workflows/<slug>/steps/<step>.step.yaml`)
- ✅ **NO `structure` selector** - Legacy field, not written to YAML
- Step YAML contains only step-local configuration (parameters, cards, species_overrides, kpath_metadata)

### 4. Structure JSON

Structure files contain full structure data with embedded metadata:

```json
{
  "__qv_meta__": {
    "id": "01SABC123...",
    "name": "Si bulk",
    "slug": "si-bulk",
    "path": "structures/si-bulk.json",
    "kind": "structure"
  },
  "@module": "pymatgen.core.structure",
  "@class": "Structure",
  "lattice": {...},
  "sites": [...]
}
```

## Serialization Behavior

### Project Model (`ProjectModel.to_dict()`)

- `StructureEntry.to_dict()` writes only `{"id": self.meta.id}` - no name/slug/path
- `WorkflowEntry.to_dict()` writes only `{"id": self.meta.id}` - no name/slug/path
- Full metadata is loaded from resource files when needed

### Workflow Model (`WorkflowModel.to_dict()`)

- Writes `structure_id` (ULID) for structure reference
- Writes `step_id` (ULID) for each step entry
- Does NOT write structure selector (legacy field)

### Step Spec (`StructureStepSpec.to_dict()`)

- Writes only step-local fields: `meta`, `step_type`, `parameters`, `cards`, `species_overrides`, `kpath_metadata`
- **Explicitly excludes**: `structure_id`, `parent_workflow_id`, `structure` selector
- These fields may exist in memory for backwards compatibility when loading legacy YAML, but are never written

## Backwards Compatibility

The codebase supports loading legacy formats:

- **Legacy workflow.yaml**: May have `structure` selector instead of `structure_id` - resolved on load
- **Legacy step YAML**: May have `structure_id` or `parent_workflow_id` - accepted on load but not written
- **Legacy project.qv.yml**: May have full meta in entries - normalized to ID-only on load

All legacy formats are normalized to the ID-only model when loaded, ensuring consistency.

## Verification

The schema is verified by:
- `tests/unit/test_id_based_references.py` - Tests ID-only serialization
- `tests/unit/test_project_snapshot.py` - Tests snapshot round-trips with ID remapping
- `CONSISTENCY_SWEEP_REPORT.md` - Comprehensive audit of all cross-references

All tests confirm that YAML serialization uses ID-only references throughout.
