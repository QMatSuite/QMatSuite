# Siesta Phase B1 Plan (Playbook Compliance)

**Engine**: `siesta`
**Date Started**: 2026-02-07
**Status**: COMPLETE
**Authoritative SOP**: `docs/architecture/B1_ENGINE_PLAYBOOK.md`
**Input Parser/Writer Design**: `docs/design/UNIVERSAL_PARSER_WRITER_DESIGN.md`

## Baseline
- Existing siesta driver tests: `15 passed` (`tests/drivers/siesta/test_siesta_driver.py`, `-n 6`)
- Existing siesta inputformat samples: none (`tests/inputformat/samples/siesta/` missing)
- Existing siesta input parser via `EngineInputSpec`: missing (`custom_parser` not wired)
- Existing siesta output digest parser registration: missing (`("siesta", "scf_digest")` absent)

## Objectives
1. Bring `siesta` to Playbook-aligned B1 for parser/writer/digest/curated corpus and evidence.
2. Keep all research artifacts in `.tmp/engine_research/siesta/` (append-only).
3. Commit only curated docs/samples/tests/code; no CI dependence on `.tmp`.

## Scope
- In scope:
  - `src/quantumvitas/drivers/siesta/`
  - `tests/inputformat/` and `tests/drivers/siesta/`
  - `docs/engines/siesta/`
  - `.tmp/engine_research/siesta/`
- Out of scope:
  - Non-siesta engine changes
  - Kernel routing or runner architecture changes

## Execution Steps
1. Documentation and compliance scaffolding
- Create/update committed: `PHASE_B1_WORKLOG.md`, `SOURCES.md`, `CORPUS_INDEX.md`, `CURATED_INDEX.md`.
- Audit existing `.tmp` corpus and canonicalize evidence layout via copy/promote (no deletions).

2. Parser/writer implementation (universal design aligned)
- Implement FDF I/O module in `src/quantumvitas/drivers/siesta/io/fdf.py`.
- Wire `src/quantumvitas/drivers/siesta/inputspec.py` to `custom_parser` + `custom_writer`.
- Keep compatibility wrappers for existing driver handler use.

3. Minimal output digest
- Add `src/quantumvitas/drivers/siesta/parsers/output.py` with `SiestaDigest` and `@register_parser("siesta", "scf_digest")`.
- Ensure parser is imported for registration.

4. Curated examples
- Add diverse curated inputs under `tests/inputformat/samples/siesta/<case>/` (+ `case.yaml`).
- Ensure each curated case has a corresponding canonical `.tmp` real run folder.

5. Evidence and real-run validation
- Execute real siesta runs with installed binary and staged pseudopotentials.
- For each curated case, record canonical evidence:
  - `command.txt`, `run_manifest.json`, `inputs/`, `outputs/`, `compare_note.md`
- Compare observed values to best-effort references with precise citations.

6. Tests
- Add tests for:
  - yaml->inputs writer semantics vs curated inputs
  - input->yaml parser coverage using normalized corpus
  - semantic roundtrip yaml->inputs->yaml
  - digest parser + parser registry lookup
- Final validation command executed (siesta-scoped to avoid cross-thread test collisions):
  - `source .venv/bin/activate && python -m pytest tests/inputformat/test_siesta_parse.py tests/inputformat/test_siesta_digest.py tests/inputformat/test_engine_materialize.py::TestSiestaMaterialize tests/drivers/siesta/test_siesta_driver.py -v --tb=short -n 6 --dist=loadfile`

## Dependency Graph
1. Docs/worklog scaffolding
2. FDF io + inputspec wiring
3. Curated sample creation
4. Parser/writer tests
5. Output digest + tests
6. Real-run evidence canonicalization
7. Final full test command and closeout checklist

## Acceptance Criteria
- `docs/engines/siesta/PHASE_B1_WORKLOG.md` exists and is continuously updated.
- `docs/engines/siesta/SOURCES.md`, `CORPUS_INDEX.md`, `CURATED_INDEX.md` exist and match evidence.
- `tests/inputformat/samples/siesta/` exists with diverse curated cases.
- Siesta `EngineInputSpec` supports both parse and write for FDF.
- Semantic roundtrip tests pass for curated cases.
- `get_parser("siesta", "scf_digest")` resolves and digest parsing tests pass.
- Each curated case has canonical `.tmp` real-run evidence folder.
- Siesta-scoped `-n 6` validation command is executed and recorded.
