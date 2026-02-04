"""
Integration tests for Yambo execution.

These tests run actual Yambo (and QE) calculations and verify results.
Tests are skipped if Yambo or QE is not installed.

Yambo is a postprocessing engine for many-body perturbation theory (GW, BSE)
that consumes QE wavefunctions via the p2y converter.

To run these tests:
    pytest tests/integration/test_yambo_execution.py -v --tb=long
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from quantumvitas.core.engines.discovery import discover_engine, is_engine_available

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Skip all tests if yambo is not installed
pytestmark = pytest.mark.skipif(
    not is_engine_available("yambo", project_root=Path(__file__).resolve().parent.parent.parent),
    reason="Yambo not installed",
)

# Also need QE for the full workflow
_QE_AVAILABLE = is_engine_available("qe", project_root=Path(__file__).resolve().parent.parent.parent)


def _find_yambo_bin(binary_name: str = "yambo") -> str:
    """Find a yambo binary (yambo, p2y, ypp)."""
    result = discover_engine("yambo", project_root=_REPO_ROOT)
    if result.available and result.executable_path:
        bin_dir = result.executable_path.parent
        candidate = bin_dir / binary_name
        if candidate.is_file():
            return str(candidate)
    found = shutil.which(binary_name)
    assert found is not None, f"{binary_name} binary not found"
    return found


def _find_pw_bin() -> str:
    """Find QE pw.x binary."""
    result = discover_engine("qe", project_root=_REPO_ROOT)
    if result.available and result.executable_path:
        return str(result.executable_path)
    found = shutil.which("pw.x")
    assert found is not None, "pw.x binary not found"
    return found


# ── QE input templates for Si (minimal, 2-atom diamond cell) ──

_SI_SCF_TEMPLATE = """\
&CONTROL
  calculation = 'scf'
  prefix = 'si'
  outdir = './work'
  pseudo_dir = './pseudo'
  tprnfor = .true.
  tstress = .true.
/
&SYSTEM
  ibrav = 2
  celldm(1) = 10.20
  nat = 2
  ntyp = 1
  ecutwfc = 15.0
/
&ELECTRONS
  conv_thr = 1.0d-6
/
ATOMIC_SPECIES
  Si 28.086 {pseudo_file}
ATOMIC_POSITIONS crystal
  Si 0.00 0.00 0.00
  Si 0.25 0.25 0.25
K_POINTS automatic
  2 2 2 0 0 0
"""

_SI_NSCF_TEMPLATE = """\
&CONTROL
  calculation = 'nscf'
  prefix = 'si'
  outdir = './work'
  pseudo_dir = './pseudo'
/
&SYSTEM
  ibrav = 2
  celldm(1) = 10.20
  nat = 2
  ntyp = 1
  ecutwfc = 15.0
  nbnd = 20
  force_symmorphic = .true.
/
&ELECTRONS
  conv_thr = 1.0d-6
  diago_full_acc = .true.
/
ATOMIC_SPECIES
  Si 28.086 {pseudo_file}
ATOMIC_POSITIONS crystal
  Si 0.00 0.00 0.00
  Si 0.25 0.25 0.25
K_POINTS automatic
  2 2 2 0 0 0
"""


def _find_si_oncv_pseudo() -> Path:
    """Find any Si ONCV norm-conserving pseudo for yambo tests.

    Yambo requires norm-conserving pseudopotentials (not PAW/US).
    Searches multiple locations for any Si_ONCV_PBE-*.upf version.
    """
    import glob as globmod

    # Explicit paths to check (in priority order)
    explicit_paths = [
        _REPO_ROOT / "docs" / "engines" / "yambo"
        / "smoke_si_nc" / "pseudo" / "Si_ONCV_PBE-1.2.upf",
        _REPO_ROOT / "resources" / "pseudo" / "Si_ONCV_PBE-1.2.upf",
    ]
    for p in explicit_paths:
        if p.exists():
            return p

    # Search for any Si_ONCV_PBE-*.upf in known locations
    search_dirs = [
        _REPO_ROOT / "resources" / "pseudo",
        _REPO_ROOT / ".qmatsuite" / "engines" / "qe",
        Path.home() / ".qmatsuite" / "pseudo",
    ]
    for search_dir in search_dirs:
        for match in search_dir.rglob("Si_ONCV_PBE-*.upf"):
            return match

    # Search system pseudo directories
    for sys_dir in [Path("/usr/share/espresso/pseudo"), Path.home() / "pseudo"]:
        if sys_dir.is_dir():
            for match in sys_dir.rglob("Si_ONCV_PBE-*.upf"):
                return match

    return None


def _setup_qe_and_yambo(workdir: Path) -> Path:
    """Run the full QE SCF → NSCF → p2y → yambo init pipeline.

    Returns the working directory containing SAVE/.
    """
    workdir.mkdir(parents=True, exist_ok=True)

    # Find and copy pseudopotential
    pseudo_dir = workdir / "pseudo"
    pseudo_dir.mkdir(exist_ok=True)

    pseudo_src = _find_si_oncv_pseudo()
    if pseudo_src is None:
        pytest.skip("No Si ONCV NC pseudopotential found")
    pseudo_file = pseudo_src.name
    shutil.copy2(pseudo_src, pseudo_dir / pseudo_file)

    pw_bin = _find_pw_bin()
    p2y_bin = _find_yambo_bin("p2y")
    yambo_bin = _find_yambo_bin("yambo")

    # ── Step 1: QE SCF ──
    (workdir / "scf.in").write_text(_SI_SCF_TEMPLATE.format(pseudo_file=pseudo_file))
    scf_result = subprocess.run(
        [pw_bin, "-in", "scf.in"],
        cwd=str(workdir),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert scf_result.returncode == 0, (
        f"QE SCF failed (exit {scf_result.returncode}):\n"
        f"{scf_result.stderr[:500]}"
    )
    assert "JOB DONE" in scf_result.stdout, "SCF did not complete"

    # ── Step 2: QE NSCF ──
    (workdir / "nscf.in").write_text(_SI_NSCF_TEMPLATE.format(pseudo_file=pseudo_file))
    nscf_result = subprocess.run(
        [pw_bin, "-in", "nscf.in"],
        cwd=str(workdir),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert nscf_result.returncode == 0, (
        f"QE NSCF failed (exit {nscf_result.returncode}):\n"
        f"{nscf_result.stderr[:500]}"
    )
    assert "JOB DONE" in nscf_result.stdout, "NSCF did not complete"

    # ── Step 3: p2y ──
    qe_save_dir = workdir / "work" / "si.save"
    assert qe_save_dir.is_dir(), f"QE save dir not found: {qe_save_dir}"

    p2y_result = subprocess.run(
        [p2y_bin],
        cwd=str(qe_save_dir),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert p2y_result.returncode == 0, (
        f"p2y failed (exit {p2y_result.returncode}):\n"
        f"{p2y_result.stderr[:500]}"
    )

    # ── Step 4: Copy SAVE and run yambo init ──
    p2y_save = qe_save_dir / "SAVE"
    assert p2y_save.is_dir(), "p2y did not create SAVE/"

    target_save = workdir / "SAVE"
    if target_save.exists():
        shutil.rmtree(target_save)
    shutil.copytree(p2y_save, target_save)

    init_result = subprocess.run(
        [yambo_bin],
        cwd=str(workdir),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert init_result.returncode == 0, (
        f"yambo init failed (exit {init_result.returncode}):\n"
        f"{init_result.stderr[:500]}"
    )
    assert (target_save / "ns.db1").exists(), "SAVE/ns.db1 missing after init"

    return workdir


# =====================================================================
# Shared fixture: QE + yambo init (expensive, reuse across tests)
# =====================================================================

@pytest.fixture(scope="module")
def yambo_si_workdir(tmp_path_factory):
    """Set up Si QE+yambo SAVE directory, shared across module tests."""
    if not _QE_AVAILABLE:
        pytest.skip("QE (pw.x) not installed — needed for yambo tests")
    base = _REPO_ROOT / ".tmp" / "yambo"
    base.mkdir(parents=True, exist_ok=True)
    workdir = tmp_path_factory.mktemp("yambo_si", numbered=True)
    return _setup_qe_and_yambo(workdir)


# =====================================================================
# Test 1: Raw yambo binary — IP Optics
# =====================================================================

class TestYamboRawExecution:
    """Tests that call yambo directly (no driver framework)."""

    def test_ip_optics_si(self, yambo_si_workdir):
        """Run IP optics on Si and verify dielectric function output."""
        workdir = yambo_si_workdir
        yambo_bin = _find_yambo_bin()

        # Write IP optics input
        ip_input = """\
optics
chi
dipoles
Chimod= "IP"
% ChiEnRnge
  0.00000 | 10.00000 |         eV
%
% ChiDmRnge
 0.100000 | 0.100000 |         eV
%
ChiEnStps= 100
% BndsRnXd
   1 |  20 |
%
NGsBlkXd= 1                 RL
% LongDrXd
 1.000000 | 0.000000 | 0.000000 |
%
"""
        (workdir / "ip.in").write_text(ip_input)

        result = subprocess.run(
            [yambo_bin, "-F", "ip.in", "-J", "ip_run", "-C", "ip_output"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=300,
        )

        # Save output for debugging
        (workdir / "ip.log").write_text(result.stdout + result.stderr)

        # ── Assert exit code ──
        assert result.returncode == 0, (
            f"yambo IP optics failed (exit {result.returncode}):\n"
            f"{result.stderr[:1000]}"
        )

        # ── Assert output files exist ──
        ip_out = workdir / "ip_output"
        assert ip_out.is_dir(), "ip_output/ directory not created"

        eps_files = list(ip_out.glob("o-*.eps_*"))
        assert len(eps_files) > 0, "No o-*.eps_* spectrum file found"

        report_files = list(ip_out.glob("r-*"))
        assert len(report_files) > 0, "No r-* report file found"

        # ── Assert success strings in report ──
        report_text = report_files[0].read_text()
        assert "Timing" in report_text or "CPU" in report_text, (
            "Missing timing info in report"
        )

        # ── Parse and verify spectrum ──
        from quantumvitas.drivers.yambo.parser import parse_spectrum_file

        spec = parse_spectrum_file(eps_files[0])
        assert len(spec.points) >= 50, (
            f"Expected >= 50 spectrum points, got {len(spec.points)}"
        )
        assert spec.spectrum_type == "ip", f"Expected 'ip' type, got '{spec.spectrum_type}'"

        # Si IP static dielectric constant should be > 5
        static_eps = spec.static_dielectric
        assert static_eps is not None, "Could not determine static dielectric"
        assert static_eps > 5.0, (
            f"Static dielectric {static_eps} too low for Si (expected > 5)"
        )

    def test_gw_si(self, yambo_si_workdir):
        """Run G0W0 PPA on Si and verify QP corrections."""
        workdir = yambo_si_workdir
        yambo_bin = _find_yambo_bin()

        # Write GW input (minimal: 2x2x2 grid, 20 bands, bands 3-6 QP)
        gw_input = """\
HF_and_locXC
gw0
ppa
el_el_corr
dyson
em1d
Chimod= "HARTREE"
% BndsRnXp
   1 |  20 |
%
NGsBlkXp= 1                 RL
% LongDrXp
 1.000000 | 0.000000 | 0.000000 |
%
PPAPntXp= 27.21138       eV
% GbndRnge
   1 |  20 |
%
GTermKind= "none"
DysSolver= "n"
%QPkrange
1|4|3|6|
%
"""
        (workdir / "gw.in").write_text(gw_input)

        result = subprocess.run(
            [yambo_bin, "-F", "gw.in", "-J", "gw_run", "-C", "gw_output"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=600,
        )

        (workdir / "gw.log").write_text(result.stdout + result.stderr)

        assert result.returncode == 0, (
            f"yambo GW failed (exit {result.returncode}):\n"
            f"{result.stderr[:1000]}"
        )

        # ── Assert QP output exists ──
        gw_out = workdir / "gw_output"
        assert gw_out.is_dir(), "gw_output/ directory not created"

        qp_files = list(gw_out.glob("o-*.qp"))
        assert len(qp_files) > 0, "No o-*.qp file found"

        # ── Parse and verify QP corrections ──
        from quantumvitas.drivers.yambo.parser import parse_qp_file

        qp = parse_qp_file(qp_files[0])
        assert len(qp.corrections) > 0, "No QP corrections parsed"

        # Should have corrections for bands 3-6 at k-points 1-4
        bands_found = {c.band for c in qp.corrections}
        assert 4 in bands_found, "Missing VBM (band 4) correction"
        assert 5 in bands_found, "Missing CBM (band 5) correction"

        # QP gap should be > 1 eV for Si (DFT gap ~0.5-1.1 eV, GW opens it)
        qp_gap = qp.qp_gap
        if qp_gap is not None:
            assert qp_gap > 0.5, f"QP gap {qp_gap} eV too small for Si"


# =====================================================================
# Test 2: Driver registration & discovery
# =====================================================================

class TestYamboDriverRegistration:
    """Tests that the yambo driver is registered and discoverable."""

    def test_driver_registry_lookup(self):
        """Verify yambo driver is accessible via DriverRegistry."""
        import quantumvitas.drivers.yambo  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        driver = DriverRegistry.get_driver("yambo")
        assert driver is not None
        assert driver.PREFIX == "yambo"
        assert driver.engine_family == "yambo"
        assert driver.display_name == "Yambo"
        assert driver.driver_api_version == "1.0.0"
        assert "gw" in driver.SUPPORTED_GEN_STEPS
        assert "bse" in driver.SUPPORTED_GEN_STEPS
        assert "optics" in driver.SUPPORTED_GEN_STEPS
        assert "setup" in driver.SUPPORTED_GEN_STEPS

    def test_step_type_specs(self):
        """Verify all 4 step type specs are registered."""
        import quantumvitas.drivers.yambo  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        expected = {"yambo_setup", "yambo_gw", "yambo_bse", "yambo_optics"}
        for spec_name in expected:
            spec = DriverRegistry.get_step_type_spec(spec_name)
            assert spec is not None, f"Step type {spec_name} not registered"
            assert spec.engine == "yambo"

    def test_step_type_handler_lookup(self):
        """Verify handler is resolvable for each step type."""
        import quantumvitas.drivers.yambo  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        for spec_name in ["yambo_gw", "yambo_bse", "yambo_optics", "yambo_setup"]:
            handler = DriverRegistry.get_handler(spec_name)
            assert handler is not None, f"No handler for {spec_name}"
            assert callable(handler)

    def test_materialization_map(self):
        """Verify gen → spec materialization."""
        import quantumvitas.drivers.yambo  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        assert DriverRegistry.materialize_step_type("yambo", "gw") == "yambo_gw"
        assert DriverRegistry.materialize_step_type("yambo", "bse") == "yambo_bse"
        assert DriverRegistry.materialize_step_type("yambo", "optics") == "yambo_optics"
        assert DriverRegistry.materialize_step_type("yambo", "setup") == "yambo_setup"

    def test_engine_discovery(self):
        """Verify yambo is discovered via centralized engine discovery."""
        result = discover_engine("yambo", project_root=_REPO_ROOT)
        assert result.available, f"Yambo should be discovered: {result.reason}"
        assert result.executable_path is not None

    def test_recipe_class(self):
        """Verify recipe class is accessible."""
        import quantumvitas.drivers.yambo  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        recipe_cls = DriverRegistry.get_recipe_class("yambo")
        assert recipe_cls is not None

    def test_workdir_policy(self):
        """Verify ISOLATED workdir policy."""
        import quantumvitas.drivers.yambo  # noqa: F401
        from quantumvitas.core.driver_protocol import WorkdirPolicy
        from quantumvitas.core.driver_registry import DriverRegistry

        driver = DriverRegistry.get_driver("yambo")
        assert driver.get_workdir_policy() == WorkdirPolicy.ISOLATED


# =====================================================================
# Test 3: Parser unit tests with golden references
# =====================================================================

class TestYamboParser:
    """Test parsers against golden reference files from exploration."""

    _GOLDEN = _REPO_ROOT / "docs" / "engines" / "yambo" / "golden_refs"

    @pytest.mark.skipif(
        not (_REPO_ROOT / "docs" / "engines" / "yambo"
             / "golden_refs" / "gw" / "o-gw_si.qp").exists(),
        reason="Golden reference files not available",
    )
    def test_parse_gw_golden(self):
        """Parse golden GW QP file."""
        from quantumvitas.drivers.yambo.parser import parse_qp_file

        qp = parse_qp_file(self._GOLDEN / "gw" / "o-gw_si.qp")
        assert len(qp.corrections) == 40, f"Expected 40 corrections, got {len(qp.corrections)}"

        # VBM at K1 band 4: Eo=0.000
        vbm = [c for c in qp.corrections if c.k_point == 1 and c.band == 4]
        assert len(vbm) == 1
        assert abs(vbm[0].e_dft) < 0.01

    @pytest.mark.skipif(
        not (_REPO_ROOT / "docs" / "engines" / "yambo"
             / "golden_refs" / "ip" / "o-ip_si.eps_q1_ip").exists(),
        reason="Golden reference files not available",
    )
    def test_parse_ip_golden(self):
        """Parse golden IP spectrum file."""
        from quantumvitas.drivers.yambo.parser import parse_spectrum_file

        spec = parse_spectrum_file(self._GOLDEN / "ip" / "o-ip_si.eps_q1_ip")
        assert len(spec.points) == 100
        assert spec.spectrum_type == "ip"
        assert spec.static_dielectric is not None
        assert spec.static_dielectric > 10.0  # Si IP eps(0) ~ 14.5

    @pytest.mark.skipif(
        not (_REPO_ROOT / "docs" / "engines" / "yambo"
             / "golden_refs" / "bse" / "o-bse_si.eps_q1_haydock_bse").exists(),
        reason="Golden reference files not available",
    )
    def test_parse_bse_golden(self):
        """Parse golden BSE spectrum file."""
        from quantumvitas.drivers.yambo.parser import parse_spectrum_file

        spec = parse_spectrum_file(
            self._GOLDEN / "bse" / "o-bse_si.eps_q1_haydock_bse"
        )
        assert len(spec.points) == 200
        assert spec.spectrum_type == "haydock_bse"
        assert spec.static_dielectric is not None


# =====================================================================
# Test 4: Writer unit tests
# =====================================================================

class TestYamboWriter:
    """Test input file writers."""

    def test_write_gw_input(self, tmp_path):
        """Write and verify GW input file."""
        from quantumvitas.drivers.yambo.writer import GWParams, write_gw_input

        params = GWParams(
            polarization_bands=(1, 20),
            self_energy_bands=(1, 20),
            kpt_range=(1, 4),
            band_range=(3, 6),
        )
        out = tmp_path / "gw.in"
        write_gw_input(out, params)

        text = out.read_text()
        assert "HF_and_locXC" in text
        assert "gw0" in text
        assert "ppa" in text
        assert "DysSolver" in text
        assert "QPkrange" in text

    def test_write_bse_input(self, tmp_path):
        """Write and verify BSE input file."""
        from quantumvitas.drivers.yambo.writer import BSEParams, write_bse_input

        params = BSEParams(bse_bands=(3, 6), screening_bands=(1, 20))
        out = tmp_path / "bse.in"
        write_bse_input(out, params)

        text = out.read_text()
        assert "optics" in text
        assert "bse" in text
        assert "em1s" in text
        assert "BSEBands" in text

    def test_write_ip_optics_input(self, tmp_path):
        """Write and verify IP optics input file."""
        from quantumvitas.drivers.yambo.writer import IPOpticsParams, write_ip_optics_input

        params = IPOpticsParams(bands=(1, 20), energy_steps=100)
        out = tmp_path / "ip.in"
        write_ip_optics_input(out, params)

        text = out.read_text()
        assert "optics" in text
        assert "chi" in text
        assert "dipoles" in text
        assert 'Chimod= "IP"' in text
