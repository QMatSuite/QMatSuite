# ORCA Documentation Sources

**Last Updated**: 2026-02-06

---

## Official Documentation

| Source | URL | Accessed |
|--------|-----|----------|
| ORCA 6.0 Manual | https://www.faccts.de/docs/orca/6.0/manual/ | 2026-02-05 |
| ORCA 6.1.1 Manual | https://orca-manual.mpi-muelheim.mpg.de/ | 2026-02-05 |
| ORCA Tutorials | https://www.faccts.de/docs/orca/tutorials/ | 2026-02-05 |
| ORCA Forum | https://orcaforum.kofo.mpg.de/ | 2026-02-05 |
| ORCA Input Library | https://sites.google.com/site/orcainputlibrary/ | 2026-02-05 |

---

## Downloaded Materials

### PDFs (in `.tmp/engine_research/orca/raw_pdfs/`)

| File | Size | Source | Downloaded |
|------|------|--------|------------|
| `ORCA_6.0_Manual.pdf` | 55MB | faccts.de | 2026-02-05 |
| `ORCA_Winter_School_2021.pdf` | 2.5MB | winterschool.cc | 2026-02-05 |
| `ORCA_TAMU_Intro.pdf` | 500KB | hprc.tamu.edu | 2026-02-05 |

### GitHub Repositories (in `.tmp/engine_research/orca/extracted/`)

| Repository | URL | Cloned |
|------------|-----|--------|
| OrcaNotes | github.com/raghurama123/OrcaNotes | 2026-02-05 |
| ccinput | github.com/cyllab/ccinput | 2026-02-05 |
| autochem | github.com/tommason14/autochem | 2026-02-05 |

---

## Metadata Catalogs

Generated from documentation analysis:

| File | Location | Description |
|------|----------|-------------|
| `orca_keywords.json` | `.tmp/engine_research/orca/metadata_seed/` | Keyword catalog |
| `orca_step_types.json` | `.tmp/engine_research/orca/metadata_seed/` | Step type mappings |

---

## ORCA Syntax Reference

### Keyword Line (`!`)
```
! B3LYP def2-SVP Opt TIGHTSCF
```

### Block Syntax (`%...end`)
```
%scf
  MaxIter 200
end
```

### Geometry Block (`* xyz ... *`)
```
* xyz 0 1
O  0.0 0.0 0.0
H  1.0 0.0 0.0
*
```

### Key Block Types
- `%scf` - SCF settings
- `%geom` - Geometry optimization
- `%tddft` / `%cis` - Excited states
- `%casscf` - CASSCF
- `%pal` - Parallelization
- `%maxcore` - Memory per core
- `%cpcm` - Solvation

---

## Corpus Summary

- **Location**: `.tmp/engine_research/orca/`
- **Normalized Cases**: 8 cases in `normalized/`
- **Total Files**: ~842
- **Total Size**: ~244MB
