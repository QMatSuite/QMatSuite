# Yambo Curated Inputs (B1)

Committed curated inputs live in `tests/inputformat/samples/yambo/`.
Only minimal input files + case metadata are committed. Runtime outputs remain in `.tmp`.

## Curated Cases

1. `si_gw_ppa`
- Files: `tests/inputformat/samples/yambo/si_gw_ppa/gw.in`
- Capability: G0W0 quasiparticle corrections (`HF_and_locXC`, `gw0`, `ppa`, `dyson`, `em1d`)
- Real-run evidence: `.tmp/engine_research/yambo/real_run/si_gw_qe4x4_20260207`
- Reference citation: `docs/engines/yambo/smoke_si_nc/gw_output/o-gw_si.qp`

2. `si_bse_haydock`
- Files: `tests/inputformat/samples/yambo/si_bse_haydock/bse.in`
- Capability: excitonic optical response via BSE + Haydock solver
- Real-run evidence: `.tmp/engine_research/yambo/real_run/si_bse_qe4x4_20260207`
- Reference citation: `docs/engines/yambo/smoke_si_nc/bse_output/o-bse_si.eps_q1_haydock_bse`

3. `si_ip_optics`
- Files: `tests/inputformat/samples/yambo/si_ip_optics/optics.in`
- Capability: independent-particle optics (`Chimod=IP`) and dielectric spectra
- Real-run evidence: `.tmp/engine_research/yambo/real_run/si_ip_qe4x4_20260207`
- Reference citation: `docs/engines/yambo/smoke_si_nc/ip_output/o-ip_si.eps_q1_ip`

4. `si_tddft_lrc`
- Files: `tests/inputformat/samples/yambo/si_tddft_lrc/optics.in`
- Capability: TDDFT optics path with LRC kernel (`Chimod=LRC`)
- Real-run evidence: `.tmp/engine_research/yambo/real_run/si_lrc_tddft_qe4x4_20260207`
- Reference citation: `.tmp/engine_research/yambo/runs/tmp_template/lrc_template.in` (template provenance; no published numeric benchmark found)

## Diversity Note
These four cases are qualitatively distinct in solver/kernel path:
- GW quasiparticle correction
- BSE excitonic spectrum
- IP optics baseline
- TDDFT-LRC kernel optics
