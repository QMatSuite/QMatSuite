"""Tests for MACE trajectory parser."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from qmatsuite.drivers.mace.parsers.trajectory import (
    MACETrajectoryParser,
    _parse_jsonl_frames,
)


class TestMACETrajectoryParser:
    def test_can_parse_with_trajectory(self, mace_relax_dir: Path):
        parser = MACETrajectoryParser()
        assert parser.can_parse(mace_relax_dir)

    def test_cannot_parse_empty_dir(self, tmp_path: Path):
        parser = MACETrajectoryParser()
        assert not parser.can_parse(tmp_path)

    def test_parse_relax_trajectory(self, mace_relax_dir: Path):
        parser = MACETrajectoryParser()
        traj = parser.parse(mace_relax_dir)
        assert traj.trajectory_type == "relax"
        assert traj.n_frames == 3
        assert traj.n_atoms == 2

    def test_parse_md_trajectory(self, mace_md_dir: Path):
        parser = MACETrajectoryParser()
        traj = parser.parse(mace_md_dir)
        assert traj.trajectory_type == "md"
        assert traj.n_frames == 2
        assert traj.n_atoms == 3

    def test_frame_energy(self, mace_relax_dir: Path):
        parser = MACETrajectoryParser()
        traj = parser.parse(mace_relax_dir)
        assert traj[0].energy is not None
        assert traj[0].energy == pytest.approx(-10.2)

    def test_frame_positions(self, mace_relax_dir: Path):
        parser = MACETrajectoryParser()
        traj = parser.parse(mace_relax_dir)
        assert traj[0].positions.shape == (2, 3)
        assert traj[0].species == ["Si", "Si"]

    def test_md_frame_temperature(self, mace_md_dir: Path):
        parser = MACETrajectoryParser()
        traj = parser.parse(mace_md_dir)
        assert traj[0].temperature is not None
        assert traj[0].temperature == pytest.approx(300.0)

    def test_md_frame_time(self, mace_md_dir: Path):
        parser = MACETrajectoryParser()
        traj = parser.parse(mace_md_dir)
        assert traj[0].time == pytest.approx(0.0)
        assert traj[1].time == pytest.approx(10.0)


class TestJSONLParsing:
    def test_parse_empty_text(self):
        frames = _parse_jsonl_frames("")
        assert frames == []

    def test_parse_single_frame(self):
        line = json.dumps({
            "frame_index": 0,
            "energy_eV": -5.0,
            "positions": [[0.0, 0.0, 0.0]],
            "species": ["H"],
            "cell": [[10.0, 0.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 10.0]],
        })
        frames = _parse_jsonl_frames(line)
        assert len(frames) == 1
        assert frames[0].energy == pytest.approx(-5.0)

    def test_skip_invalid_json_lines(self):
        text = '{"frame_index": 0, "positions": [[0,0,0]], "species": ["H"], "cell": [[10,0,0],[0,10,0],[0,0,10]]}\nINVALID JSON\n{"frame_index": 1, "positions": [[1,1,1]], "species": ["H"], "cell": [[10,0,0],[0,10,0],[0,0,10]]}'
        frames = _parse_jsonl_frames(text)
        assert len(frames) == 2

    def test_skip_frames_without_positions(self):
        text = json.dumps({"frame_index": 0, "energy_eV": -5.0, "species": ["H"]})
        frames = _parse_jsonl_frames(text)
        assert len(frames) == 0
