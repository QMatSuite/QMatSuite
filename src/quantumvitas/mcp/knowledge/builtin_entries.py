"""Curated built-in knowledge entries for QMatSuite.

Each entry is a dict matching the ``insights`` table schema.
The ``id`` field is assigned deterministically by ``build_builtin.py``.
"""

from __future__ import annotations

BUILTIN_ENTRIES: list[dict] = [
    # =========================================================================
    # Error recovery (5)
    # =========================================================================
    {
        "grade": "finding",
        "scope_engine": "*",
        "scope_workflow": "scf",
        "scope_system_type": "*",
        "scope_method": "dft",
        "content": (
            "SCF oscillation (energy bouncing up and down) is usually caused by "
            "too aggressive charge mixing. Reduce mixing_beta (QE) or AMIX/BMIX "
            "(VASP) to 0.1-0.3. For metals, consider Kerker mixing (QE: "
            "mixing_mode='local-TF', VASP: IMIX=1)."
        ),
        "confidence": "high",
        "source_type": "builtin",
        "source_origin": "DFT best practices",
        "created_by": "qmatsuite-builtin",
        "tags": '["error_recovery", "scf", "convergence", "mixing"]',
    },
    {
        "grade": "finding",
        "scope_engine": "*",
        "scope_workflow": "scf",
        "scope_system_type": "*",
        "scope_method": "dft",
        "content": (
            "SCF not converging within the iteration limit: increase "
            "electron_maxstep (QE) or NELM (VASP) to 200-500. Also check that "
            "ecutwfc/ENCUT and k-mesh are reasonable. A very large system may "
            "need more iterations."
        ),
        "confidence": "high",
        "source_type": "builtin",
        "source_origin": "DFT best practices",
        "created_by": "qmatsuite-builtin",
        "tags": '["error_recovery", "scf", "convergence"]',
    },
    {
        "grade": "finding",
        "scope_engine": "*",
        "scope_workflow": "scf",
        "scope_system_type": "*",
        "scope_method": "dft",
        "content": (
            "SCF energy diverging to very large values: check the input "
            "structure for overlapping atoms or unreasonable bond lengths. "
            "Reduce mixing to 0.05-0.1 and try a simpler starting density. "
            "For pseudopotential codes, verify PP files match the elements."
        ),
        "confidence": "high",
        "source_type": "builtin",
        "source_origin": "DFT best practices",
        "created_by": "qmatsuite-builtin",
        "tags": '["error_recovery", "scf", "convergence", "structure"]',
    },
    {
        "grade": "finding",
        "scope_engine": "*",
        "scope_workflow": "scf",
        "scope_system_type": "metal",
        "scope_method": "dft",
        "content": (
            "Charge sloshing in metals (SCF converges very slowly with "
            "oscillations): use Kerker/diag mixing. In QE: "
            "mixing_mode='local-TF'. In VASP: IMIX=1 with AMIX=0.1, "
            "BMIX=0.0001. Also ensure adequate smearing (see smearing guidance)."
        ),
        "confidence": "high",
        "source_type": "builtin",
        "source_origin": "DFT best practices",
        "created_by": "qmatsuite-builtin",
        "tags": '["error_recovery", "scf", "convergence", "metal", "mixing"]',
    },
    {
        "grade": "finding",
        "scope_engine": "*",
        "scope_workflow": "relax",
        "scope_system_type": "*",
        "scope_method": "dft",
        "content": (
            "Forces not converging in geometry relaxation: tighten SCF "
            "convergence (conv_thr/EDIFF) to at least 10x smaller than the "
            "force threshold. Ensure ecutwfc/ENCUT is well converged. For "
            "problematic cases try a different optimizer (BFGS vs CG)."
        ),
        "confidence": "high",
        "source_type": "builtin",
        "source_origin": "DFT best practices",
        "created_by": "qmatsuite-builtin",
        "tags": '["error_recovery", "relax", "convergence", "forces"]',
    },

    # =========================================================================
    # Smearing / occupations (3)
    # =========================================================================
    {
        "grade": "principle",
        "scope_engine": "*",
        "scope_workflow": "scf",
        "scope_system_type": "metal",
        "scope_method": "dft",
        "content": (
            "Metals require smearing for stable SCF convergence. Use "
            "Methfessel-Paxton smearing: VASP ISMEAR=1, QE smearing='m-p'. "
            "A typical sigma/degauss is 0.1-0.2 eV. Tetrahedron method is "
            "best for final DOS calculations on metals (VASP ISMEAR=-5, "
            "QE occupations='tetrahedra')."
        ),
        "confidence": "high",
        "source_type": "builtin",
        "source_origin": "DFT best practices",
        "created_by": "qmatsuite-builtin",
        "tags": '["smearing", "metal", "occupations"]',
    },
    {
        "grade": "principle",
        "scope_engine": "*",
        "scope_workflow": "scf",
        "scope_system_type": "semiconductor",
        "scope_method": "dft",
        "content": (
            "Semiconductors and insulators: use fixed occupations (QE "
            "occupations='fixed', VASP ISMEAR=0 with small SIGMA=0.05) or "
            "tetrahedron method (VASP ISMEAR=-5, QE occupations='tetrahedra'). "
            "Do NOT use Methfessel-Paxton for insulators."
        ),
        "confidence": "high",
        "source_type": "builtin",
        "source_origin": "DFT best practices",
        "created_by": "qmatsuite-builtin",
        "tags": '["smearing", "semiconductor", "occupations"]',
    },
    {
        "grade": "finding",
        "scope_engine": "*",
        "scope_workflow": "scf",
        "scope_system_type": "*",
        "scope_method": "dft",
        "content": (
            "If SIGMA/degauss is too large, the 'entropy T*S' contribution "
            "will be significant and energies unreliable. Check that the "
            "entropy term is < 1 meV/atom. If not, reduce SIGMA/degauss. "
            "VASP prints this as 'EENTRO', QE as 'smearing contrib.'."
        ),
        "confidence": "high",
        "source_type": "builtin",
        "source_origin": "DFT best practices",
        "created_by": "qmatsuite-builtin",
        "tags": '["smearing", "convergence", "entropy"]',
    },

    # =========================================================================
    # Convergence guidance (4)
    # =========================================================================
    {
        "grade": "principle",
        "scope_engine": "*",
        "scope_workflow": "scf",
        "scope_system_type": "*",
        "scope_method": "dft",
        "content": (
            "Ecutwfc/ENCUT convergence protocol: run a series of SCF "
            "calculations at increasing cutoffs (e.g. 20, 30, 40, 50, 60, "
            "80 Ry for QE or 300, 400, 500, 600, 700 eV for VASP). Plot "
            "total energy vs cutoff. Choose the cutoff where energy changes "
            "< 1 meV/atom between successive points."
        ),
        "confidence": "high",
        "source_type": "builtin",
        "source_origin": "DFT best practices",
        "created_by": "qmatsuite-builtin",
        "tags": '["convergence", "ecutwfc", "encut", "protocol"]',
    },
    {
        "grade": "principle",
        "scope_engine": "*",
        "scope_workflow": "scf",
        "scope_system_type": "*",
        "scope_method": "dft",
        "content": (
            "K-mesh convergence protocol: run SCF with increasing k-point "
            "grids (e.g. 4x4x4, 6x6x6, 8x8x8, 10x10x10, 12x12x12). Plot "
            "total energy vs k-points. Choose the grid where energy changes "
            "< 1 meV/atom. Metals need denser meshes than semiconductors."
        ),
        "confidence": "high",
        "source_type": "builtin",
        "source_origin": "DFT best practices",
        "created_by": "qmatsuite-builtin",
        "tags": '["convergence", "kpoints", "protocol"]',
    },
    {
        "grade": "finding",
        "scope_engine": "*",
        "scope_workflow": "scf",
        "scope_system_type": "*",
        "scope_method": "dft",
        "content": (
            "Typical production SCF convergence thresholds: QE conv_thr = "
            "1.0e-8 to 1.0e-10 Ry, VASP EDIFF = 1.0e-6 to 1.0e-8 eV, "
            "ABINIT toldfe = 1.0e-10 Ha. Tighter thresholds needed for "
            "forces, phonons, and response properties."
        ),
        "confidence": "high",
        "source_type": "builtin",
        "source_origin": "DFT best practices",
        "created_by": "qmatsuite-builtin",
        "tags": '["convergence", "threshold", "production"]',
    },
    {
        "grade": "finding",
        "scope_engine": "qe",
        "scope_workflow": "scf",
        "scope_system_type": "*",
        "scope_method": "dft",
        "content": (
            "In Quantum ESPRESSO, ecutrho (charge density cutoff) should be "
            "8-12x ecutwfc for ultrasoft pseudopotentials. For norm-conserving "
            "PPs, the default 4x is usually fine. PAW also typically needs "
            "8-12x. Check the PP header for recommended cutoffs."
        ),
        "confidence": "high",
        "source_type": "builtin",
        "source_origin": "QE documentation",
        "created_by": "qmatsuite-builtin",
        "tags": '["convergence", "ecutrho", "pseudopotential", "qe"]',
    },

    # =========================================================================
    # Workflow-specific (4)
    # =========================================================================
    {
        "grade": "principle",
        "scope_engine": "*",
        "scope_workflow": "bands",
        "scope_system_type": "*",
        "scope_method": "dft",
        "content": (
            "Band structure calculation requires a converged SCF charge "
            "density first. Run SCF to convergence, then a non-self-consistent "
            "(NSCF) calculation along high-symmetry k-paths. In QE: "
            "calculation='bands'. In VASP: ICHARG=11 with KPOINTS along the "
            "path."
        ),
        "confidence": "high",
        "source_type": "builtin",
        "source_origin": "DFT best practices",
        "created_by": "qmatsuite-builtin",
        "tags": '["workflow", "bands", "nscf"]',
    },
    {
        "grade": "principle",
        "scope_engine": "*",
        "scope_workflow": "dos",
        "scope_system_type": "*",
        "scope_method": "dft",
        "content": (
            "Density of states (DOS) requires a denser k-mesh than the "
            "SCF calculation. Typically 2-3x denser in each direction. Run "
            "SCF first, then NSCF with the dense mesh. In QE: "
            "calculation='nscf' + dos.x. In VASP: ISMEAR=-5 (tetrahedron) "
            "with dense KPOINTS, then use DOSCAR."
        ),
        "confidence": "high",
        "source_type": "builtin",
        "source_origin": "DFT best practices",
        "created_by": "qmatsuite-builtin",
        "tags": '["workflow", "dos", "kpoints"]',
    },
    {
        "grade": "finding",
        "scope_engine": "*",
        "scope_workflow": "relax",
        "scope_system_type": "*",
        "scope_method": "dft",
        "content": (
            "For geometry relaxation, the SCF convergence threshold (EDIFF/ "
            "conv_thr) should be at least 10x tighter than what is needed to "
            "resolve the force convergence. E.g., if targeting forces < "
            "0.01 eV/A, use EDIFF=1e-7 or tighter."
        ),
        "confidence": "high",
        "source_type": "builtin",
        "source_origin": "DFT best practices",
        "created_by": "qmatsuite-builtin",
        "tags": '["workflow", "relax", "convergence"]',
    },
    {
        "grade": "principle",
        "scope_engine": "*",
        "scope_workflow": "phonon",
        "scope_system_type": "*",
        "scope_method": "dft",
        "content": (
            "Phonon calculations (DFPT or finite differences) require very "
            "tight SCF convergence: QE conv_thr < 1e-12 Ry, VASP EDIFF < "
            "1e-8 eV. The k-mesh and ecutwfc/ENCUT should also be very well "
            "converged. Even small noise can produce imaginary frequencies."
        ),
        "confidence": "high",
        "source_type": "builtin",
        "source_origin": "DFT best practices",
        "created_by": "qmatsuite-builtin",
        "tags": '["workflow", "phonon", "convergence", "dfpt"]',
    },

    # =========================================================================
    # Method-specific (4)
    # =========================================================================
    {
        "grade": "finding",
        "scope_engine": "*",
        "scope_workflow": "*",
        "scope_system_type": "*",
        "scope_method": "dft+u",
        "content": (
            "DFT+U typical Hubbard U values for 3d transition metals: "
            "Ti 3-5 eV, V 3-4 eV, Cr 3-4 eV, Mn 3-5 eV, Fe 4-5 eV, "
            "Co 3-5 eV, Ni 5-7 eV, Cu 5-8 eV. These are approximate — "
            "ideally compute U self-consistently (linear response or ACBN0). "
            "QE: Hubbard_U, VASP: LDAUU."
        ),
        "confidence": "medium",
        "source_type": "builtin",
        "source_origin": "DFT+U literature review",
        "created_by": "qmatsuite-builtin",
        "tags": '["method", "dft+u", "hubbard", "transition_metal"]',
    },
    {
        "grade": "finding",
        "scope_engine": "*",
        "scope_workflow": "*",
        "scope_system_type": "*",
        "scope_method": "hse",
        "content": (
            "HSE06 hybrid functional: significantly more expensive than PBE "
            "(10-100x) but gives much better band gaps. Standard parameters: "
            "25% exact exchange, 0.2 A^-1 screening. In QE: "
            "input_dft='HSE'. In VASP: LHFCALC=.TRUE., HFSCREEN=0.2. "
            "Reduce k-mesh to keep cost manageable."
        ),
        "confidence": "high",
        "source_type": "builtin",
        "source_origin": "HSE06 literature",
        "created_by": "qmatsuite-builtin",
        "tags": '["method", "hse", "hybrid", "bandgap"]',
    },
    {
        "grade": "finding",
        "scope_engine": "*",
        "scope_workflow": "*",
        "scope_system_type": "*",
        "scope_method": "gw",
        "content": (
            "GW calculations require many empty bands (typically 10-20x the "
            "number of occupied bands). They are very expensive in memory and "
            "CPU. Start with a well-converged DFT calculation, then check "
            "convergence of the number of bands, energy cutoff for the "
            "dielectric function, and k-mesh independently."
        ),
        "confidence": "high",
        "source_type": "builtin",
        "source_origin": "GW literature",
        "created_by": "qmatsuite-builtin",
        "tags": '["method", "gw", "many-body", "empty_bands"]',
    },
    {
        "grade": "finding",
        "scope_engine": "*",
        "scope_workflow": "scf",
        "scope_system_type": "magnetic",
        "scope_method": "dft",
        "content": (
            "Spin-polarized calculations: set nspin=2 (QE) or ISPIN=2 "
            "(VASP). Provide initial magnetic moments: QE "
            "starting_magnetization(i), VASP MAGMOM. Without initial moments "
            "the calculation may converge to a non-magnetic solution even for "
            "magnetic systems. For antiferromagnets, set opposite signs."
        ),
        "confidence": "high",
        "source_type": "builtin",
        "source_origin": "DFT best practices",
        "created_by": "qmatsuite-builtin",
        "tags": '["method", "spin", "magnetic", "nspin"]',
    },
]
