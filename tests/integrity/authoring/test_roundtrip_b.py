"""
Roundtrip B: compile demo → replay → re-snapshot → verify equivalence.

Proves every Level-2 demo snapshot can be compiled to fine-grained user-like ops,
replayed through QMSService, and the resulting project re-snapshots to semantic
equivalence with the original.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from qmatsuite.demo_store.authoring_ops import is_bulk_op
from qmatsuite.demo_store.compiler import compile_snapshot
from qmatsuite.demo_store.replay import replay_ops
from qmatsuite.demo_store.roundtrip import (
    MismatchCategory,
    categorize_diff,
    verify_roundtrip_equivalence,
)
from qmatsuite.core.resources import get_resources_dir

DEMO_DIR = get_resources_dir() / "demo_projects"


def _load_demo(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def _all_demo_files():
    return sorted(DEMO_DIR.glob("*.yml"))


def _demo_ids():
    return [f.stem for f in _all_demo_files()]


@pytest.mark.integrity
class TestRoundtripB:
    """Full roundtrip B: compile → replay → re-snapshot → verify."""

    @pytest.mark.parametrize("demo_file", _all_demo_files(), ids=_demo_ids())
    def test_compile_produces_ops(self, demo_file):
        """Each demo compiles to a non-empty ops list starting with InitProject."""
        snap = _load_demo(demo_file)
        ops = compile_snapshot(snap)
        assert len(ops) > 0, f"No ops produced for {demo_file.stem}"
        assert ops[0].op == "InitProject", f"First op is {ops[0].op}, not InitProject"

    @pytest.mark.parametrize("demo_file", _all_demo_files(), ids=_demo_ids())
    def test_no_bulk_ops(self, demo_file):
        """No bulk ops (entire parameters tree as value) in any compiled ops list."""
        snap = _load_demo(demo_file)
        ops = compile_snapshot(snap)
        bulk_ops = [op for op in ops if is_bulk_op(op)]
        assert not bulk_ops, (
            f"{demo_file.stem}: {len(bulk_ops)} bulk ops found. "
            f"First: {bulk_ops[0] if bulk_ops else 'N/A'}"
        )

    @pytest.mark.parametrize("demo_file", _all_demo_files(), ids=_demo_ids())
    def test_roundtrip_b(self, demo_file, tmp_path):
        """Compile → replay → re-snapshot → verify semantic equivalence."""
        original_snap = _load_demo(demo_file)

        # Compile
        ops = compile_snapshot(original_snap)

        # Replay
        project_root = replay_ops(ops, tmp_path)

        # Re-snapshot
        from qmatsuite.project.snapshot import export_project_to_snapshot
        replayed_snap = export_project_to_snapshot(project_root).to_dict()

        # Verify
        report = verify_roundtrip_equivalence(original_snap, replayed_snap)

        if not report.equivalent:
            # Diagnostic output
            diag_lines = [f"FAIL: {demo_file.stem} ({len(report.differences)} mismatches)"]
            for diff in report.differences[:10]:
                cat = categorize_diff(diff)
                diag_lines.append(f"  [{cat.value}] {diff[:200]}")
            if len(report.differences) > 10:
                diag_lines.append(f"  ... and {len(report.differences) - 10} more")

            # Op summary
            from collections import Counter
            op_counts = Counter(type(op).__name__ for op in ops)
            diag_lines.append(f"\n  Ops: {dict(op_counts)}")

            pytest.fail("\n".join(diag_lines))
