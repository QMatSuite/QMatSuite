# QE Parameter JSON Diff Report

This report compares parameter metadata across three JSON schema versions:
- **v1** (legacy): `qe_module_parameters.legacy.v1.json`
- **v2** (legacy): `qe_module_parameters.legacy.v2.json`
- **v3** (current): `qe_module_parameters.json`

---

## Per-Module Parameter Counts

| Module | v1 | v2 | v3 | v2-v1 (added/removed) | v3-v2 (added/removed) |
|--------|----|----|----|------------------------|------------------------|
| band_interpolation | 0 | 16 | 16 | +16 | — |
| bands | 0 | 12 | 12 | +12 | — |
| cp | 0 | 182 | 183 | +182 | +1 |
| cppp | 0 | 15 | 15 | +15 | — |
| d3hess | 0 | 4 | 4 | +4 | — |
| dos | 0 | 10 | 10 | +10 | — |
| dynmat | 0 | 14 | 14 | +14 | — |
| hp | 0 | 29 | 30 | +29 | +1 |
| ld1 | 0 | 119 | 119 | +119 | — |
| matdyn | 0 | 46 | 46 | +46 | — |
| neb | 0 | 93 | 93 | +93 | — |
| oscdft_et | 0 | 7 | 7 | +7 | — |
| oscdft_pp | 0 | 2 | 2 | +2 | — |
| ph | 0 | 81 | 83 | +81 | +2 |
| postahc | 0 | 16 | 16 | +16 | — |
| pp | 0 | 32 | 32 | +32 | — |
| ppacf | 0 | 9 | 9 | +9 | — |
| pprism | 0 | 17 | 17 | +17 | — |
| projwfc | 0 | 21 | 21 | +21 | — |
| pw | 0 | 289 | 292 | +289 | +3 |
| pwcond | 0 | 47 | 47 | +47 | — |
| q2r | 0 | 13 | 13 | +13 | — |

### Global Totals

- **v1 total**: 0 parameters
- **v2 total**: 1074 parameters (+1074, -0 vs v1)
- **v3 total**: 1081 parameters (+7, -0 vs v2)

---

## Detailed Parameter Changes

### Module: `band_interpolation`

#### v2-v1: Added (16 parameters)

- `&INTERPOLATION.check_periodicity`
- `&INTERPOLATION.method`
- `&INTERPOLATION.miller_max`
- `&INTERPOLATION.p_metric`
- `&INTERPOLATION.scale_sphere`
- `K_POINTS.nks`
- `K_POINTS.wk`
- `K_POINTS.xk_x`
- `K_POINTS.xk_y`
- `K_POINTS.xk_z`
- `ROUGHNESS.RoughC`
- `ROUGHNESS.RoughN`
- `USER_STARS.NUser`
- `USER_STARS.vec_x`
- `USER_STARS.vec_y`
- `USER_STARS.vec_z`

---

### Module: `bands`

#### v2-v1: Added (12 parameters)

- `&BANDS.filband`
- `&BANDS.filp`
- `&BANDS.firstk`
- `&BANDS.lastk`
- `&BANDS.lp`
- `&BANDS.lsigma`
- `&BANDS.lsym`
- `&BANDS.no_overlap`
- `&BANDS.outdir`
- `&BANDS.plot_2d`
- `&BANDS.prefix`
- `&BANDS.spin_component`

---

### Module: `cp`

#### v2-v1: Added (182 parameters)

- `&CELL.cell_damping`
- `&CELL.cell_dofree`
- `&CELL.cell_dynamics`
- `&CELL.cell_factor`
- `&CELL.cell_parameters`
- `&CELL.cell_temperature`
- `&CELL.cell_velocities`
- `&CELL.fnoseh`
- `&CELL.greash`
- `&CELL.press`
- `&CELL.temph`
- `&CELL.wmass`
- `&CONTROL.calculation`
- `&CONTROL.disk_io`
- `&CONTROL.dt`
- `&CONTROL.ekin_conv_thr`
- `&CONTROL.etot_conv_thr`
- `&CONTROL.forc_conv_thr`
- `&CONTROL.iprint`
- `&CONTROL.isave`
- `&CONTROL.max_seconds`
- `&CONTROL.memory`
- `&CONTROL.ndr`
- `&CONTROL.ndw`
- `&CONTROL.nstep`
- `&CONTROL.outdir`
- `&CONTROL.prefix`
- `&CONTROL.pseudo_dir`
- `&CONTROL.restart_mode`
- `&CONTROL.saverho`
- `&CONTROL.tabps`
- `&CONTROL.tefield`
- `&CONTROL.title`
- `&CONTROL.tprnfor`
- `&CONTROL.tstress`
- `&CONTROL.verbosity`
- `&ELECTRONS.ampre`
- `&ELECTRONS.conv_thr`
- `&ELECTRONS.efield`
- `&ELECTRONS.ekincw`
- `&ELECTRONS.electron_damping`
- `&ELECTRONS.electron_dynamics`
- `&ELECTRONS.electron_maxstep`
- `&ELECTRONS.electron_temperature`
- `&ELECTRONS.electron_velocities`
- `&ELECTRONS.emass`
- `&ELECTRONS.emass_cutoff`
- `&ELECTRONS.epol`
- `&ELECTRONS.fnosee`
- `&ELECTRONS.grease`
- ... and 132 more

#### v3-v2: Added (1 parameters)

- `ATOMIC_POSITIONS.if_pos`

---

### Module: `cppp`

#### v2-v1: Added (15 parameters)

- `&INPUTPP.atomic_number`
- `&INPUTPP.fileout`
- `&INPUTPP.lcharge`
- `&INPUTPP.ldynamics`
- `&INPUTPP.lforces`
- `&INPUTPP.lpdb`
- `&INPUTPP.lrotation`
- `&INPUTPP.ndr`
- `&INPUTPP.nframes`
- `&INPUTPP.np1`
- `&INPUTPP.np2`
- `&INPUTPP.np3`
- `&INPUTPP.outdir`
- `&INPUTPP.output`
- `&INPUTPP.prefix`

---

### Module: `d3hess`

#### v2-v1: Added (4 parameters)

- `&INPUT.filhess`
- `&INPUT.outdir`
- `&INPUT.prefix`
- `&INPUT.step`

---

### Module: `dos`

#### v2-v1: Added (10 parameters)

- `&DOS.DeltaE`
- `&DOS.Emax`
- `&DOS.Emin`
- `&DOS.bz_sum`
- `&DOS.degauss`
- `&DOS.fildos`
- `&DOS.ngauss`
- `&DOS.outdir`
- `&DOS.prefix`
- `N.Output`

---

### Module: `dynmat`

#### v2-v1: Added (14 parameters)

- `&INPUT.amass`
- `&INPUT.asr`
- `&INPUT.axis`
- `&INPUT.el_ph_nsig`
- `&INPUT.el_ph_sigma`
- `&INPUT.fildyn`
- `&INPUT.fileig`
- `&INPUT.filmol`
- `&INPUT.filout`
- `&INPUT.filxsf`
- `&INPUT.loto_2d`
- `&INPUT.lperm`
- `&INPUT.lplasma`
- `&INPUT.remove_interaction_blocks`

---

### Module: `hp`

#### v2-v1: Added (29 parameters)

- `&INPUTHP.compute_hp`
- `&INPUTHP.conv_thr_chi`
- `&INPUTHP.determine_num_pert_only`
- `&INPUTHP.determine_q_mesh_only`
- `&INPUTHP.dist_thr`
- `&INPUTHP.docc_thr`
- `&INPUTHP.equiv_type`
- `&INPUTHP.ethr_nscf`
- `&INPUTHP.find_atpert`
- `&INPUTHP.iverbosity`
- `&INPUTHP.last_q`
- `&INPUTHP.lmin`
- `&INPUTHP.max_seconds`
- `&INPUTHP.niter_max`
- `&INPUTHP.nmix`
- `&INPUTHP.no_metq0`
- `&INPUTHP.nq1`
- `&INPUTHP.nq2`
- `&INPUTHP.nq3`
- `&INPUTHP.num_neigh`
- `&INPUTHP.outdir`
- `&INPUTHP.perturb_only_atom`
- `&INPUTHP.prefix`
- `&INPUTHP.rmax`
- `&INPUTHP.skip_equivalence_q`
- `&INPUTHP.skip_type`
- `&INPUTHP.start_q`
- `&INPUTHP.sum_pertq`
- `&INPUTHP.thresh_init`

#### v3-v2: Added (1 parameters)

- `&INPUTHP.alpha_mix`

---

### Module: `ld1`

#### v2-v1: Added (119 parameters)

- `&INPUT.atom`
- `&INPUT.beta`
- `&INPUT.cau_fact`
- `&INPUT.config`
- `&INPUT.deld`
- `&INPUT.dft`
- `&INPUT.dx`
- `&INPUT.emaxld`
- `&INPUT.eminld`
- `&INPUT.file_charge`
- `&INPUT.isic`
- `&INPUT.iswitch`
- `&INPUT.latt`
- `&INPUT.lsd`
- `&INPUT.lsmall`
- `&INPUT.max_out_wfc`
- `&INPUT.nld`
- `&INPUT.noscf`
- `&INPUT.prefix`
- `&INPUT.rel`
- `&INPUT.rel_dist`
- `&INPUT.relpert`
- `&INPUT.rlderiv`
- `&INPUT.rmax`
- `&INPUT.rpwe`
- `&INPUT.rytoev_fact`
- `&INPUT.title`
- `&INPUT.tr2`
- `&INPUT.vdw`
- `&INPUT.verbosity`
- `&INPUT.write_coulomb`
- `&INPUT.xmin`
- `&INPUT.zed`
- `&INPUTP.author`
- `&INPUTP.file_beta`
- `&INPUTP.file_chi`
- `&INPUTP.file_core`
- `&INPUTP.file_pseudopw`
- `&INPUTP.file_qvan`
- `&INPUTP.file_recon`
- `&INPUTP.file_screen`
- `&INPUTP.file_wfcaegen`
- `&INPUTP.file_wfcncgen`
- `&INPUTP.file_wfcusgen`
- `&INPUTP.lgipaw_reconstruction`
- `&INPUTP.lloc`
- `&INPUTP.lpaw`
- `&INPUTP.lsave_wfc`
- `&INPUTP.new_core_ps`
- `&INPUTP.nlcc`
- ... and 69 more

---

### Module: `matdyn`

#### v2-v1: Added (46 parameters)

- `&INPUT.amass`
- `&INPUT.asr`
- `&INPUT.at`
- `&INPUT.degauss`
- `&INPUT.deltaE`
- `&INPUT.dos`
- `&INPUT.eigen_similarity`
- `&INPUT.fd`
- `&INPUT.fldos`
- `&INPUT.fldyn`
- `&INPUT.fleig`
- `&INPUT.flfrc`
- `&INPUT.flfrq`
- `&INPUT.fltau`
- `&INPUT.flvec`
- `&INPUT.huang`
- `&INPUT.l1`
- `&INPUT.l2`
- `&INPUT.l3`
- `&INPUT.la2F`
- `&INPUT.loto_2d`
- `&INPUT.loto_disable`
- `&INPUT.na_ifc`
- `&INPUT.ndos`
- `&INPUT.nk1`
- `&INPUT.nk2`
- `&INPUT.nk3`
- `&INPUT.nosym`
- `&INPUT.ntyp`
- `&INPUT.q_in_band_form`
- `&INPUT.q_in_cryst_coord`
- `&INPUT.read_lr`
- `&INPUT.readtau`
- `&INPUT.write_frc`
- `ATOMICPOSITIONSPECS.ityp`
- `A_P_S.ityp`
- `P_S.nptq`
- `P_S.nq`
- `P_S.q_x`
- `P_S.q_y`
- `P_S.q_z`
- `QPOINTSSPECS.nptq`
- `QPOINTSSPECS.nq`
- `QPOINTSSPECS.q_x`
- `QPOINTSSPECS.q_y`
- `QPOINTSSPECS.q_z`

---

### Module: `neb`

#### v2-v1: Added (93 parameters)

- `&PATH.CI_scheme`
- `&PATH.ds`
- `&PATH.fcp_mu`
- `&PATH.fcp_scheme`
- `&PATH.fcp_thr`
- `&PATH.first_last_opt`
- `&PATH.k_max`
- `&PATH.k_min`
- `&PATH.lfcp`
- `&PATH.minimum_image`
- `&PATH.nstep_path`
- `&PATH.num_of_images`
- `&PATH.opt_scheme`
- `&PATH.path_thr`
- `&PATH.restart_mode`
- `&PATH.string_method`
- `&PATH.temp_req`
- `&PATH.use_freezing`
- `&PATH.use_masses`
- `BEGIN.ATOMIC_POSITIONS`
- `BEGIN.BEGIN_ENGINE_INPUT`
- `BEGIN.BEGIN_PATH_INPUT`
- `BEGIN.BEGIN_POSITIONS`
- `BEGIN.CI_scheme`
- `BEGIN.CLIMBING_IMAGES`
- `BEGIN.FIRST_IMAGE`
- `BEGIN.INTERMEDIATE_IMAGE`
- `BEGIN.LAST_IMAGE`
- `BEGIN.TOTAL_CHARGE`
- `BEGIN.ds`
- `BEGIN.fcp_mu`
- `BEGIN.fcp_scheme`
- `BEGIN.fcp_thr`
- `BEGIN.first_last_opt`
- `BEGIN.k_max`
- `BEGIN.k_min`
- `BEGIN.lfcp`
- `BEGIN.minimum_image`
- `BEGIN.nstep_path`
- `BEGIN.num_of_images`
- `BEGIN.opt_scheme`
- `BEGIN.path_thr`
- `BEGIN.restart_mode`
- `BEGIN.string_method`
- `BEGIN.temp_req`
- `BEGIN.tot_charge`
- `BEGIN.use_freezing`
- `BEGIN.use_masses`
- `BEGIN_ENGINE_INPUT.ATOMIC_POSITIONS`
- `BEGIN_ENGINE_INPUT.BEGIN_POSITIONS`
- ... and 43 more

---

### Module: `oscdft_et`

#### v2-v1: Added (7 parameters)

- `&OSCDFT_ET_NAMELIST.final_dir`
- `&OSCDFT_ET_NAMELIST.final_prefix`
- `&OSCDFT_ET_NAMELIST.initial_dir`
- `&OSCDFT_ET_NAMELIST.initial_prefix`
- `&OSCDFT_ET_NAMELIST.print_debug`
- `&OSCDFT_ET_NAMELIST.print_eigvect`
- `&OSCDFT_ET_NAMELIST.print_matrix`

---

### Module: `oscdft_pp`

#### v2-v1: Added (2 parameters)

- `&OSCDFT_PP_NAMELIST.outdir`
- `&OSCDFT_PP_NAMELIST.prefix`

---

### Module: `ph`

#### v2-v1: Added (81 parameters)

- `&INPUTPH.Line_of_input`
- `&INPUTPH.ahc_dir`
- `&INPUTPH.ahc_nbnd`
- `&INPUTPH.ahc_nbndskip`
- `&INPUTPH.alpha_mix`
- `&INPUTPH.amass`
- `&INPUTPH.asr`
- `&INPUTPH.dek`
- `&INPUTPH.dftd3_hess`
- `&INPUTPH.diagonalization`
- `&INPUTPH.do_charge_neutral`
- `&INPUTPH.do_long_range`
- `&INPUTPH.drho_star`
- `&INPUTPH.dvscf_star`
- `&INPUTPH.el_ph_nsigma`
- `&INPUTPH.el_ph_sigma`
- `&INPUTPH.electron_phonon`
- `&INPUTPH.elop`
- `&INPUTPH.epsil`
- `&INPUTPH.eth_ns`
- `&INPUTPH.eth_rps`
- `&INPUTPH.fildrho`
- `&INPUTPH.fildvscf`
- `&INPUTPH.fildyn`
- `&INPUTPH.fpol`
- `&INPUTPH.k1`
- `&INPUTPH.k2`
- `&INPUTPH.k3`
- `&INPUTPH.last_irr`
- `&INPUTPH.last_q`
- `&INPUTPH.ldiag`
- `&INPUTPH.ldisp`
- `&INPUTPH.ldvscf_interpolate`
- `&INPUTPH.lnoloc`
- `&INPUTPH.low_directory_check`
- `&INPUTPH.lqdir`
- `&INPUTPH.lraman`
- `&INPUTPH.lrpa`
- `&INPUTPH.lshift_q`
- `&INPUTPH.max_seconds`
- `&INPUTPH.modenum`
- `&INPUTPH.nat_todo`
- `&INPUTPH.niter_ph`
- `&INPUTPH.nk1`
- `&INPUTPH.nk2`
- `&INPUTPH.nk3`
- `&INPUTPH.nmix_ph`
- `&INPUTPH.nogg`
- `&INPUTPH.nq1`
- `&INPUTPH.nq2`
- ... and 31 more

#### v3-v2: Added (2 parameters)

- `&INPUTPH.xq`
- `QPOINTSSPECS.atom`

---

### Module: `postahc`

#### v2-v1: Added (16 parameters)

- `&INPUT.adiabatic`
- `&INPUT.ahc_dir`
- `&INPUT.ahc_nbnd`
- `&INPUT.ahc_nbndskip`
- `&INPUT.ahc_win_max_eV`
- `&INPUT.ahc_win_min_eV`
- `&INPUT.amass_amu`
- `&INPUT.efermi_eV`
- `&INPUT.eta_eV`
- `&INPUT.flvec`
- `&INPUT.outdir`
- `&INPUT.prefix`
- `&INPUT.skip_dw`
- `&INPUT.skip_upper`
- `&INPUT.temp_kelvin`
- `&INPUT.use_irr_q`

---

### Module: `pp`

#### v2-v1: Added (32 parameters)

- `&INPUTPP.degauss_ldos`
- `&INPUTPP.delta_e`
- `&INPUTPP.emax`
- `&INPUTPP.emin`
- `&INPUTPP.filplot`
- `&INPUTPP.kband`
- `&INPUTPP.kpoint`
- `&INPUTPP.lsign`
- `&INPUTPP.n0`
- `&INPUTPP.nc`
- `&INPUTPP.outdir`
- `&INPUTPP.plot_num`
- `&INPUTPP.prefix`
- `&INPUTPP.sample_bias`
- `&INPUTPP.spin_component`
- `&INPUTPP.title`
- `&INPUTPP.use_gauss_ldos`
- `&PLOT.e1`
- `&PLOT.e2`
- `&PLOT.e3`
- `&PLOT.fileout`
- `&PLOT.filepp`
- `&PLOT.iflag`
- `&PLOT.interpolation`
- `&PLOT.nfile`
- `&PLOT.nx`
- `&PLOT.ny`
- `&PLOT.nz`
- `&PLOT.output_format`
- `&PLOT.radius`
- `&PLOT.weight`
- `&PLOT.x0`

---

### Module: `ppacf`

#### v2-v1: Added (9 parameters)

- `&PPACF.code_num`
- `&PPACF.lfock`
- `&PPACF.lplot`
- `&PPACF.ltks`
- `&PPACF.n_lambda`
- `&PPACF.outdir`
- `&PPACF.prefix`
- `&PPACF.use_ace`
- `&PPACF.vdW_analysis`

---

### Module: `pprism`

#### v2-v1: Added (17 parameters)

- `&INPUTPP.filplot`
- `&INPUTPP.lpunch`
- `&INPUTPP.outdir`
- `&INPUTPP.prefix`
- `&PLOT.e1`
- `&PLOT.e2`
- `&PLOT.e3`
- `&PLOT.fileout`
- `&PLOT.iflag`
- `&PLOT.interpolation`
- `&PLOT.lebedev`
- `&PLOT.nx`
- `&PLOT.ny`
- `&PLOT.nz`
- `&PLOT.output_format`
- `&PLOT.radius`
- `&PLOT.x0`

---

### Module: `projwfc`

#### v2-v1: Added (21 parameters)

- `&PROJWFC.DeltaE`
- `&PROJWFC.Emax`
- `&PROJWFC.Emin`
- `&PROJWFC.degauss`
- `&PROJWFC.diag_basis`
- `&PROJWFC.filpdos`
- `&PROJWFC.filproj`
- `&PROJWFC.irmax`
- `&PROJWFC.irmin`
- `&PROJWFC.kresolveddos`
- `&PROJWFC.lbinary_data`
- `&PROJWFC.lsym`
- `&PROJWFC.lwrite_overlaps`
- `&PROJWFC.n_proj_boxes`
- `&PROJWFC.ngauss`
- `&PROJWFC.outdir`
- `&PROJWFC.pawproj`
- `&PROJWFC.plotboxes`
- `&PROJWFC.prefix`
- `&PROJWFC.tdosinboxes`
- `N.Format_of_output_files`

---

### Module: `pw`

#### v2-v1: Added (289 parameters)

- `&CELL.cell_dofree`
- `&CELL.cell_dynamics`
- `&CELL.cell_factor`
- `&CELL.press`
- `&CELL.press_conv_thr`
- `&CELL.wmass`
- `&CONTROL.calculation`
- `&CONTROL.dipfield`
- `&CONTROL.disk_io`
- `&CONTROL.dt`
- `&CONTROL.etot_conv_thr`
- `&CONTROL.forc_conv_thr`
- `&CONTROL.gate`
- `&CONTROL.gdir`
- `&CONTROL.iprint`
- `&CONTROL.lberry`
- `&CONTROL.lelfield`
- `&CONTROL.lfcp`
- `&CONTROL.lkpoint_dir`
- `&CONTROL.lorbm`
- `&CONTROL.max_seconds`
- `&CONTROL.nberrycyc`
- `&CONTROL.nppstr`
- `&CONTROL.nstep`
- `&CONTROL.outdir`
- `&CONTROL.prefix`
- `&CONTROL.pseudo_dir`
- `&CONTROL.restart_mode`
- `&CONTROL.tefield`
- `&CONTROL.title`
- `&CONTROL.tprnfor`
- `&CONTROL.trism`
- `&CONTROL.tstress`
- `&CONTROL.twochem`
- `&CONTROL.verbosity`
- `&CONTROL.wf_collect`
- `&CONTROL.wfcdir`
- `&ELECTRONS.adaptive_thr`
- `&ELECTRONS.conv_thr`
- `&ELECTRONS.conv_thr_init`
- `&ELECTRONS.conv_thr_multi`
- `&ELECTRONS.diago_cg_maxiter`
- `&ELECTRONS.diago_david_ndim`
- `&ELECTRONS.diago_full_acc`
- `&ELECTRONS.diago_gs_nblock`
- `&ELECTRONS.diago_rmm_conv`
- `&ELECTRONS.diago_rmm_ndim`
- `&ELECTRONS.diago_thr_init`
- `&ELECTRONS.diagonalization`
- `&ELECTRONS.efield`
- ... and 239 more

#### v3-v2: Added (3 parameters)

- `ATOMIC_POSITIONS.if_pos`
- `HUBBARD.label`
- `HUBBARD.paramType`

---

### Module: `pwcond`

#### v2-v1: Added (47 parameters)

- `&INPUTCOND.band_file`
- `&INPUTCOND.bdl`
- `&INPUTCOND.bdr`
- `&INPUTCOND.bds`
- `&INPUTCOND.denergy`
- `&INPUTCOND.ecut2d`
- `&INPUTCOND.energy0`
- `&INPUTCOND.epsproj`
- `&INPUTCOND.ewind`
- `&INPUTCOND.fil_loc`
- `&INPUTCOND.ikind`
- `&INPUTCOND.iofspin`
- `&INPUTCOND.last_e`
- `&INPUTCOND.last_k`
- `&INPUTCOND.llocal`
- `&INPUTCOND.loop_ek`
- `&INPUTCOND.lread_cond`
- `&INPUTCOND.lread_loc`
- `&INPUTCOND.lwrite_cond`
- `&INPUTCOND.lwrite_loc`
- `&INPUTCOND.max_seconds`
- `&INPUTCOND.nenergy`
- `&INPUTCOND.nz1`
- `&INPUTCOND.orbj_fin`
- `&INPUTCOND.orbj_in`
- `&INPUTCOND.outdir`
- `&INPUTCOND.prefixl`
- `&INPUTCOND.prefixr`
- `&INPUTCOND.prefixs`
- `&INPUTCOND.prefixt`
- `&INPUTCOND.recover`
- `&INPUTCOND.save_file`
- `&INPUTCOND.start_e`
- `&INPUTCOND.start_k`
- `&INPUTCOND.tk_plot`
- `&INPUTCOND.tran_file`
- `&INPUTCOND.tran_prefix`
- `K_AND_ENERGY_POINTS.kx`
- `K_AND_ENERGY_POINTS.ky`
- `K_AND_ENERGY_POINTS.nenergy`
- `K_AND_ENERGY_POINTS.nkpts`
- `K_AND_ENERGY_POINTS.weight`
- `K_E_P.kx`
- `K_E_P.ky`
- `K_E_P.nenergy`
- `K_E_P.nkpts`
- `K_E_P.weight`

---

### Module: `q2r`

#### v2-v1: Added (13 parameters)

- `&INPUT.Line_of_input`
- `&INPUT.fildyn`
- `&INPUT.flfrc`
- `&INPUT.loto_2d`
- `&INPUT.nr1`
- `&INPUT.nr2`
- `&INPUT.nr3`
- `&INPUT.write_lr`
- `&INPUT.zasr`
- `FILESPECS.file`
- `FILESPECS.nfile`
- `S.file`
- `S.nfile`

---

## v3 Schema Improvements

v3 introduces the following improvements over v2:

### A) Better Default/Status/See Parsing

- Parses `Default:`, `Status:`, and `See:` rows by reading left cell text, not row index
- Fixes cases where `See:` row appears before `Default:` (e.g., `celldm` parameter)
- Correctly identifies `Status: REQUIRED` for parameters like `ibrav`

### B) Better Enum Extraction

- Prioritizes `<span class="flag">` elements (e.g., PH `verbosity` parameter)
- Falls back to `<dl><dt><tt>` structures
- Preserves quotes in enum values (e.g., `'debug'`, `'high'`)

### C) Improved Indexing Support

- Enhanced detection of array parameters like `celldm(i), i=1,6`
- Better handling of unbounded arrays like `alpha_mix(niter)`
- Consistent `keyword_pattern` format: `{base}({{index}})`

### D) Better Description Rendering

- Handles `<pre>` blocks with proper dedenting and blank line compression
- Renders `<dl>` definition lists as readable bullet lists
- Preserves structure while removing excessive whitespace
- Ensures max 2 consecutive blank lines

### E) Schema Version 3

- Adds optional `status` field (e.g., `REQUIRED`, `OPTIONAL`)
- Adds optional `see_also` field (list of related parameter names)
- Maintains backward compatibility with v2 structure
