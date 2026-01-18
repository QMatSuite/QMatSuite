"""
Tests for post-job actions and archiving.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from quantumvitas.execution.post_job import (
    ArchiveToSlotAction,
    PostJobContext,
    compute_snapshot_diff,
    snapshot_raw_dir,
)


class TestSnapshotRawDir:
    """Test snapshot_raw_dir() function."""
    
    def test_snapshot_raw_dir_basic(self, tmp_path):
        """Basic snapshot captures files and mtimes."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        # Create some files
        (raw_dir / "file1.txt").write_text("content1")
        (raw_dir / "file2.txt").write_text("content2")
        (raw_dir / "subdir").mkdir()
        (raw_dir / "subdir" / "file3.txt").write_text("content3")
        
        snapshot = snapshot_raw_dir(raw_dir)
        
        assert "file1.txt" in snapshot
        assert "file2.txt" in snapshot
        assert "subdir/file3.txt" in snapshot
        assert all(isinstance(mtime, float) for mtime in snapshot.values())
    
    def test_snapshot_raw_dir_excludes_outdir(self, tmp_path):
        """outdir directory is excluded from snapshot."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        (raw_dir / "file1.txt").write_text("content1")
        (raw_dir / "outdir").mkdir()
        (raw_dir / "outdir" / "scratch.txt").write_text("scratch")
        
        snapshot = snapshot_raw_dir(raw_dir, exclude=["outdir"])
        
        assert "file1.txt" in snapshot
        assert "outdir/scratch.txt" not in snapshot
    
    def test_snapshot_raw_dir_excludes_scan(self, tmp_path):
        """scan directory is excluded from snapshot."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        (raw_dir / "file1.txt").write_text("content1")
        (raw_dir / "scan").mkdir()
        (raw_dir / "scan" / "variant1").mkdir()
        (raw_dir / "scan" / "variant1" / "archived.txt").write_text("archived")
        
        snapshot = snapshot_raw_dir(raw_dir, exclude=["scan"])
        
        assert "file1.txt" in snapshot
        assert "scan/variant1/archived.txt" not in snapshot
    
    def test_snapshot_raw_dir_excludes_both(self, tmp_path):
        """Both outdir and scan are excluded."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        (raw_dir / "file1.txt").write_text("content1")
        (raw_dir / "outdir").mkdir()
        (raw_dir / "outdir" / "scratch.txt").write_text("scratch")
        (raw_dir / "scan").mkdir()
        (raw_dir / "scan" / "variant1").mkdir()
        (raw_dir / "scan" / "variant1" / "archived.txt").write_text("archived")
        
        snapshot = snapshot_raw_dir(raw_dir, exclude=["outdir", "scan"])
        
        assert "file1.txt" in snapshot
        assert "outdir/scratch.txt" not in snapshot
        assert "scan/variant1/archived.txt" not in snapshot


class TestComputeSnapshotDiff:
    """Test compute_snapshot_diff() function."""
    
    def test_compute_diff_new_files(self):
        """New files are detected."""
        before = {
            "file1.txt": 1000.0,
        }
        after = {
            "file1.txt": 1000.0,
            "file2.txt": 2000.0,  # New file
        }
        
        diff = compute_snapshot_diff(before, after)
        
        assert "file2.txt" in diff
        assert "file1.txt" not in diff
    
    def test_compute_diff_modified_files(self):
        """Modified files are detected."""
        before = {
            "file1.txt": 1000.0,
        }
        after = {
            "file1.txt": 2000.0,  # Modified (mtime increased)
        }
        
        diff = compute_snapshot_diff(before, after)
        
        assert "file1.txt" in diff
    
    def test_compute_diff_excludes_outdir(self):
        """Excluded directories are not in diff."""
        before = {}
        after = {
            "file1.txt": 1000.0,
            "outdir/scratch.txt": 2000.0,
        }
        
        diff = compute_snapshot_diff(before, after, exclude=["outdir"])
        
        assert "file1.txt" in diff
        assert "outdir/scratch.txt" not in diff


class TestArchiveToSlotAction:
    """Test ArchiveToSlotAction."""
    
    def test_archive_to_slot_creates_directory(self, tmp_path):
        """Archive action creates destination directory."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        action = ArchiveToSlotAction(variant_key="scan_abc123")
        context = PostJobContext(
            calc_raw_dir=raw_dir,
            variant_key="scan_abc123",
            run_id="run001",
        )
        
        job_result = Mock()
        job_result.pre_snapshot = {}
        job_result.success = True
        
        action.execute(job_result, context)
        
        dest_dir = raw_dir / "scan" / "scan_abc123"
        assert dest_dir.exists()
        assert dest_dir.is_dir()
    
    def test_archive_to_slot_copies_files(self, tmp_path):
        """Archive action copies new/modified files."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        # Create a file
        test_file = raw_dir / "output.txt"
        test_file.write_text("output content")
        
        action = ArchiveToSlotAction(variant_key="scan_abc123")
        context = PostJobContext(
            calc_raw_dir=raw_dir,
            variant_key="scan_abc123",
            run_id="run001",
        )
        
        job_result = Mock()
        job_result.pre_snapshot = {}  # Empty before = all files are new
        job_result.success = True
        
        action.execute(job_result, context)
        
        dest_file = raw_dir / "scan" / "scan_abc123" / "output.txt"
        assert dest_file.exists()
        assert dest_file.read_text() == "output content"
    
    def test_archive_to_slot_overwrites(self, tmp_path):
        """Archive action overwrites existing files in slot."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        # Create initial file
        test_file = raw_dir / "output.txt"
        test_file.write_text("old content")
        
        action = ArchiveToSlotAction(variant_key="scan_abc123")
        context = PostJobContext(
            calc_raw_dir=raw_dir,
            variant_key="scan_abc123",
            run_id="run001",
        )
        
        # First archive
        job_result1 = Mock()
        job_result1.pre_snapshot = {}
        job_result1.success = True
        action.execute(job_result1, context)
        
        # Capture snapshot before modifying (this is what would be captured before job execution)
        pre_snapshot = snapshot_raw_dir(raw_dir, exclude=["outdir", "scan"])
        
        # Modify file (simulating job execution that modifies output)
        import time
        time.sleep(0.01)  # Ensure mtime changes
        test_file.write_text("new content")
        
        # Second archive (should overwrite)
        job_result2 = Mock()
        job_result2.pre_snapshot = pre_snapshot  # Snapshot from before modification
        job_result2.success = True
        action.execute(job_result2, context)
        
        dest_file = raw_dir / "scan" / "scan_abc123" / "output.txt"
        assert dest_file.exists()
        assert dest_file.read_text() == "new content"
    
    def test_archive_on_failure_still_archives(self, tmp_path):
        """Archive action runs even on job failure."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        test_file = raw_dir / "output.txt"
        test_file.write_text("output content")
        
        action = ArchiveToSlotAction(variant_key="scan_abc123")
        context = PostJobContext(
            calc_raw_dir=raw_dir,
            variant_key="scan_abc123",
            run_id="run001",
        )
        
        job_result = Mock()
        job_result.pre_snapshot = {}
        job_result.success = False  # Job failed
        
        action.execute(job_result, context)
        
        dest_file = raw_dir / "scan" / "scan_abc123" / "output.txt"
        assert dest_file.exists()  # Still archived
    
    def test_slots_json_appends_entry(self, tmp_path):
        """slots.json is appended with new entry."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        test_file = raw_dir / "output.txt"
        test_file.write_text("output content")
        
        action = ArchiveToSlotAction(variant_key="scan_abc123")
        context = PostJobContext(
            calc_raw_dir=raw_dir,
            variant_key="scan_abc123",
            run_id="run001",
        )
        
        job_result = Mock()
        job_result.pre_snapshot = {}
        job_result.success = True
        
        action.execute(job_result, context)
        
        slots_file = raw_dir / "scan" / "slots.json"
        assert slots_file.exists()
        
        entries = json.loads(slots_file.read_text())
        assert len(entries) == 1
        assert entries[0]["variant_key"] == "scan_abc123"
        assert entries[0]["run_id"] == "run001"
        assert entries[0]["ok"] is True
        assert "timestamp" in entries[0]
        assert "archived_path" in entries[0]
        
        # Append second entry
        job_result2 = Mock()
        job_result2.pre_snapshot = {}
        job_result2.success = False
        action.execute(job_result2, context)
        
        entries = json.loads(slots_file.read_text())
        assert len(entries) == 2
        assert entries[1]["ok"] is False

