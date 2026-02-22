"""Tests for analysis objects base classes."""
import pytest
from pathlib import Path
from datetime import datetime, timezone

from qmatsuite.core.analysis.base import (
    AnalysisObjectMeta,
    SourceFileStat,
)


class TestSourceFileStat:
    def test_from_path(self, tmp_path):
        """Test creating SourceFileStat from file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")
        
        stat = SourceFileStat.from_path(test_file, tmp_path)
        
        assert stat.path == "test.txt"
        assert stat.size_bytes == 11
        assert stat.mtime > 0
    
    def test_to_dict_from_dict(self):
        """Test serialization round-trip."""
        original = SourceFileStat(
            path="raw/scf.out",
            size_bytes=1234,
            mtime=1234567890.123,
        )
        
        data = original.to_dict()
        restored = SourceFileStat.from_dict(data)
        
        assert restored.path == original.path
        assert restored.size_bytes == original.size_bytes
        assert restored.mtime == original.mtime


class TestAnalysisObjectMeta:
    def test_create_factory(self):
        """Test factory method."""
        source = SourceFileStat("raw/test.out", 100, 12345.0)
        meta = AnalysisObjectMeta.create(
            object_type="trajectory",
            source_files=[source],
            run_ulid="01JTEST",
        )
        
        assert meta.schema_version == "1.0"
        assert meta.object_type == "trajectory"
        assert len(meta.source_files) == 1
        assert meta.run_ulid == "01JTEST"
    
    def test_to_dict_from_dict(self):
        """Test serialization round-trip."""
        source = SourceFileStat("raw/test.out", 100, 12345.0)
        original = AnalysisObjectMeta.create(
            object_type="dos",
            source_files=[source],
            parser_name="qe_dos",
        )
        
        data = original.to_dict()
        restored = AnalysisObjectMeta.from_dict(data)
        
        assert restored.object_type == original.object_type
        assert len(restored.source_files) == 1
        assert restored.parser_name == original.parser_name

