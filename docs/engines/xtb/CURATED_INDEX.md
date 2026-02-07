# xTB Curated Input Index

Engine: xTB
Format family: dollar-flag + xyz + optional xcontrol
Curated sample root: `tests/inputformat/samples/xtb/`
Updated: 2026-02-07

## Curated Cases

| Case | Capability | Inputs committed | Real-run evidence slug | Primary citation |
|---|---|---|---|---|
| `water_sp` | Basic single-point (`--gfn 2 --sp`) | `input.xyz` | `water_sp_gfn2` | `docs/engines/xtb/EXPLORATION.md:52` |
| `water_opt` | Geometry optimization (`--opt`) | `input.xyz` | `water_opt_gfn2` | `docs/engines/xtb/EXPLORATION.md:60` |
| `water_freq` | Optimize + Hessian (`--ohess`) | `input.xyz` | `water_freq_ohess` | `docs/engines/xtb/EXPLORATION.md:77` |
| `water_md` | MD with xcontrol block (`--md -I`) | `input.xyz`, `xcontrol.inp` | `water_md_short` | `docs/engines/xtb/EXPLORATION.md:92`, `docs/engines/xtb/EXPLORATION.md:186` |
| `ethanol_opt_tight` | Tight optimization regime | `input.xyz` | `ethanol_opt_tight` | `docs/engines/xtb/EXPLORATION.md:69` |
| `water_solvation_alpb` | Implicit solvation (`--alpb water`) | `input.xyz` | `water_sp_solvation_alpb` | `docs/engines/xtb/EXPLORATION.md:177` |
| `o2_triplet_sp` | Open-shell single-point (`-u 2`) | `input.xyz` | `o2_triplet_sp` | `docs/engines/xtb/EXPLORATION.md:176` |
| `caffeine_grad` | Gradient workflow (`--grad`) | `input.xyz` | `caffeine_grad` | `docs/engines/xtb/EXPLORATION.md:85` |

## Diversity Rationale
- Workflow diversity: SP, optimize, ohess/frequency, MD, gradient, solvation, open-shell.
- System diversity: 2-atom diatomic (`O2`), 3-atom water, 9-atom ethanol, 24-atom caffeine.
- Parameter diversity: runtype flags, solvation model, UHF/open-shell, xcontrol block.

## Evidence policy
- Only minimal input files are committed under `tests/inputformat/samples/xtb/`.
- Run outputs and references remain in `.tmp/engine_research/xtb/real_run/`.
