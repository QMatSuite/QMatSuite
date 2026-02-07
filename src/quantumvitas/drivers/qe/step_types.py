"""QE step type specifications."""

from quantumvitas.core.driver_protocol import StepTypeSpec


QE_STEP_TYPE_SPECS: list[StepTypeSpec] = [
    StepTypeSpec(
        step_type_spec="qe_scf",
        engine="qe",
        executable="pw.x",
        description="QE SCF calculation",
    ),
    StepTypeSpec(
        step_type_spec="qe_relax",
        engine="qe",
        executable="pw.x",
        description="QE relaxation (VC is a parameter, not a separate step type)",
    ),
    StepTypeSpec(
        step_type_spec="qe_bands",
        engine="qe",
        executable="bands.x",
        description="QE band structure",
    ),
    StepTypeSpec(
        step_type_spec="qe_bandspw",
        engine="qe",
        executable="pw.x",
        description="QE band structure (pw.x)",
    ),
    StepTypeSpec(
        step_type_spec="qe_nscf",
        engine="qe",
        executable="pw.x",
        description="QE non-self-consistent calculation",
    ),
    StepTypeSpec(
        step_type_spec="qe_dos",
        engine="qe",
        executable="dos.x",
        description="QE density of states",
    ),
    StepTypeSpec(
        step_type_spec="qe_pdos",
        engine="qe",
        executable="projwfc.x",
        description="QE projected density of states",
    ),
    StepTypeSpec(
        step_type_spec="qe_ph",
        engine="qe",
        executable="ph.x",
        description="QE phonon calculation",
    ),
    StepTypeSpec(
        step_type_spec="qe_gipaw",
        engine="qe",
        executable="gipaw.x",
        description="QE GIPAW NMR chemical shifts and EPR g-tensor",
    ),
    StepTypeSpec(
        step_type_spec="qe_q2r",
        engine="qe",
        executable="q2r.x",
        description="QE q2r transformation",
    ),
    StepTypeSpec(
        step_type_spec="qe_matdyn",
        engine="qe",
        executable="matdyn.x",
        description="QE matdyn calculation",
    ),
    StepTypeSpec(
        step_type_spec="qe_dynmat",
        engine="qe",
        executable="dynmat.x",
        description="QE dynmat calculation",
    ),
    StepTypeSpec(
        step_type_spec="qe_pp",
        engine="qe",
        executable="pp.x",
        description="QE post-processing",
    ),
    StepTypeSpec(
        step_type_spec="qe_plotband",
        engine="qe",
        executable="plotband.x",
        description="QE band plotting",
    ),
    StepTypeSpec(
        step_type_spec="qe_hp",
        engine="qe",
        executable="hp.x",
        description="QE Hubbard parameters",
    ),
    StepTypeSpec(
        step_type_spec="qe_md",
        engine="qe",
        executable="pw.x",
        description="QE molecular dynamics (VC is a parameter, not a separate step type)",
    ),
    StepTypeSpec(
        step_type_spec="qe_pw2wannier",
        engine="qe",
        executable="pw2wannier90.x",
        description="QE to Wannier90 interface",
    ),
    StepTypeSpec(
        step_type_spec="qe_custom",
        engine="qe",
        executable="pw.x",
        description="Custom step type (escape hatch)",
    ),
]
