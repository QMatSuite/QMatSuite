"""Real xTB execution tests (fast cases, skips when xTB is unavailable)."""

from __future__ import annotations

import subprocess

import pytest

from quantumvitas.drivers.xtb.parsers.output import XTBOutputParser


def _write_water_xyz(path):
    path.write_text(
        "3\nwater\n"
        "O 0.000000 0.000000 0.117370\n"
        "H 0.000000 0.756950 -0.469483\n"
        "H 0.000000 -0.756950 -0.469483\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize("flags, expect_opt", [(["--gfn", "2", "--sp"], False), (["--gfn", "2", "--opt"], True)])
def test_xtb_real_run_fast(tmp_path, xtb_binary, xtb_available, flags, expect_opt):
    if not xtb_available or xtb_binary is None:
        pytest.skip("xTB binary is not available")

    xyz = tmp_path / "input.xyz"
    _write_water_xyz(xyz)

    cmd = [xtb_binary, "input.xyz", *flags]
    result = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, timeout=60)

    assert result.returncode == 0, result.stderr[:400]

    # Persist combined output for parser test
    (tmp_path / "xtb.out").write_text(result.stdout + result.stderr, encoding="utf-8")

    parser = XTBOutputParser()
    digest = parser.parse(tmp_path)
    assert digest.normal_termination is True
    assert digest.final_energy_Ha is not None

    if expect_opt:
        assert (tmp_path / "xtbopt.xyz").exists()


def test_xtb_real_md_short(tmp_path, xtb_binary, xtb_available):
    if not xtb_available or xtb_binary is None:
        pytest.skip("xTB binary is not available")

    xyz = tmp_path / "input.xyz"
    _write_water_xyz(xyz)

    (tmp_path / "md.inp").write_text(
        "$md\n"
        "   temp=300\n"
        "   time=0.02\n"
        "   step=1.0\n"
        "   dump=5.0\n"
        "$end\n",
        encoding="utf-8",
    )

    cmd = [xtb_binary, "input.xyz", "--gfn", "2", "--md", "-I", "md.inp"]
    result = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr[:400]

    (tmp_path / "xtb.out").write_text(result.stdout + result.stderr, encoding="utf-8")
    parser = XTBOutputParser()
    digest = parser.parse(tmp_path)
    assert digest.normal_termination is True
    assert digest.md_completed is True
