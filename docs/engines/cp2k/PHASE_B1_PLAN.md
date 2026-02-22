# CP2K Phase B1 Plan

**Engine**: CP2K
**Syntax Family**: F3 nested-section (`&SECTION ... &END SECTION`)
**Baseline Test Count**: 4288 passed, 24 skipped
**Date**: 2026-02-07

## Scope

Bring CP2K driver to full B1 Playbook compliance:
- Parameter metadata catalog (150+ tags)
- Metadata access layer (cached, hot-reload, validation)
- Robust I/O module (parser + writer extracted to `io/cp2k_input.py`)
- Output digest parser (`parsers/output.py`)
- 10 curated golden samples with `case.yaml`
- Comprehensive tests (metadata, parse, roundtrip, digest, driver)

## File Layout

### Committed (new)
```
src/qmatsuite/drivers/cp2k/
  data/
    __init__.py
    cp2k_tags.json          (150+ tags, schema_version 1)
    cp2k_metadata.py        (access layer: get_tag_info, list_tags, validate_params)
  io/
    __init__.py
    cp2k_input.py           (parse_cp2k_text + write_cp2k_text, stdlib only)
  parsers/
    __init__.py
    output.py               (CP2KDigest + CP2KOutputParser, @register_parser)

tests/drivers/cp2k/
  __init__.py
  test_cp2k_driver.py       (existing, enhanced)
  test_cp2k_metadata.py     (new)
  test_cp2k_output.py       (new)

tests/inputformat/samples/cp2k/
  h2o_energy/               (case.yaml + input.inp)
  h2o_geo_opt/
  h2o_md/
  si_scf/
  si_relax/
  si_cell_opt/
  si_bands/
  benzene_energy/
  co2_energy/
  h2o_tddft/

docs/engines/cp2k/
  PHASE_B1_PLAN.md          (this file)
  PHASE_B1_WORKLOG.md       (continuous updates)
  CURATED_INDEX.md          (diversity rationale)
```

## Step Dependency Graph

```
Phase 1 (Metadata JSON)     Phase 3 (Curated Samples)
       |                           |
Phase 2 (Access Layer)             |
       |                           |
Phase 4 (I/O Parser/Writer) ------+
       |
Phase 6 (Output Digest)
       |
Phase 8 (Final Integration + Tests)
```

## Acceptance Criteria

- [ ] Full pytest green (zero failures)
- [ ] 150+ tags in cp2k_tags.json
- [ ] Metadata access layer works (lookup, validation, categories)
- [ ] 10 curated cases with 100% parse + roundtrip success
- [ ] Writer extracted to io/cp2k_input.py (not inline in inputspec.py)
- [ ] Parser handles nested sections, default keywords, units, preprocessor
- [ ] Output parser registered: get_parser("cp2k", "scf_digest") succeeds
- [ ] CP2KDigest has energy, convergence, n_atoms, timing fields
- [ ] No kernel/API surface changes
- [ ] inputformat/ leaf package untouched
- [ ] docs/ complete (plan, worklog, curated index)

## Key Design Decisions

1. **Single combined file**: CP2K uses one `input.inp` (content_role="combined")
2. **Section-path tags**: Tags in cp2k_tags.json use section paths like `FORCE_EVAL/DFT/SCF/MAX_SCF`
3. **Case-insensitive**: CP2K keywords are case-insensitive; metadata uses UPPERCASE by convention
4. **Default keyword**: Some sections have a "default keyword" (value on same line as `&SECTION`)
5. **Units**: CP2K supports `[unit]` annotations before values — parser preserves these
6. **Preprocessor**: `@SET`, `@IF`, `@INCLUDE` — parser strips or ignores these
7. **Output format**: Text-based `.out` file, regex parsing for energy/convergence/timing
8. **Energy units**: CP2K reports in Hartree; digest converts to eV (1 Ha = 27.211386245988 eV)
