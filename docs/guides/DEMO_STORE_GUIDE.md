# Demo Store Developer Guide

## Architecture

The demo store uses a two-layer system:

- **Layer A (Corpus)**: Curated engine input samples at `tests/inputformat/samples/<engine>/<case>/`
- **Layer B (Demos)**: Generated demo project snapshots at `resources/demo_projects/<slug>.yml`

A single **translator** converts Layer A to Layer B. All demos are generated artifacts; never hand-edit them.

## Key Files

| Path | Purpose |
|------|---------|
| `src/quantumvitas/demo_store/translator.py` | Core translator: corpus case -> ProjectSnapshot |
| `src/quantumvitas/demo_store/corpus.py` | Corpus index loader and validator |
| `src/quantumvitas/demo_store/ulid_seed.py` | Deterministic ULID generation |
| `src/quantumvitas/demo_store/roundtrip.py` | Roundtrip equivalence checker |
| `src/quantumvitas/demo_store/direct_snapshot.py` | Builder for Python-script engines |
| `src/quantumvitas/demo_store/manifest.py` | Generator manifest reader/writer |
| `tools/demo_store/generate_all.py` | CLI: regenerate all demos |
| `tools/demo_store/generate_corpus_index.py` | CLI: regenerate corpus_index.yaml |
| `tests/inputformat/samples/corpus_index.yaml` | Authoritative corpus registry |
| `resources/demo_projects/.generator_manifest.json` | Tracks generation provenance |

## Regenerating Demos

```bash
source .venv/bin/activate
python tools/demo_store/generate_all.py
```

This reads `corpus_index.yaml`, translates all eligible cases, and writes `.yml` files + manifest to `resources/demo_projects/`.

## Running Integrity Tests

Integrity tests are excluded from default `pytest` runs (C4 constraint). Run explicitly:

```bash
python -m pytest tests/integrity/backend/ -v --tb=short
```

### Why integrity tests are excluded

Integrity tests validate the full demo lifecycle (load snapshot → materialize → roundtrip verify) and are excluded from the default `pytest` invocation for several reasons:

1. **Runtime cost**: Each demo lifecycle test takes ~1-5 seconds. With 37+ demos, the full suite adds 30s+ to the test run.
2. **External dependencies**: Some demos require engine binaries or large assets that may not be available in CI environments.
3. **C4 constraint**: The DEMO_STORE_SPEC.md mandates that integrity tests must NOT run under default pytest.
4. **Stability**: Integrity tests are sensitive to corpus/translator changes and should be run explicitly after regeneration.

**Mechanism**: The `pytest_ignore_collect` hook in `tests/conftest.py` (lines 16-24) checks for the string `"integrity"` in the collection path and skips unless the user explicitly targets an integrity path.

**How to run**:
```bash
# Backend integrity suite
python -m pytest tests/integrity/backend/ -v --tb=short

# All integrity tests
python -m pytest tests/integrity/ -v --tb=short
```

## Gate Tests

Two gate tests enforce demo store invariants:

- `tests/gates/test_demo_generated.py` (S8.1): manifest consistency, checksums
- `tests/gates/test_corpus_index.py` (S8.2): corpus/index agreement, slug uniqueness

These run as part of the normal test suite.

## Translation Strategies

| Strategy | When Used | How |
|----------|-----------|-----|
| Preserve from existing | QE multi-step, Wannier90 | Reuses old demo content with updated metadata |
| Translator pipeline | Parseable engines (VASP, ORCA, ABINIT, etc.) | `parse_engine_inputs()` -> params -> snapshot |
| Direct snapshot | Python-script engines (PySCF, GPAW, Psi4) | Inline params/structure from case.yaml |

## Hard Constraints

- **C1**: `si_bands_demo.yml` and `si_dos_demo.yml` filenames must survive (GUI e2e tests)
- **C4**: Integrity tests must NOT run under default pytest
- All demos are generated; manual edits will be overwritten by `generate_all.py`
