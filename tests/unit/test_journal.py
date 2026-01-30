"""
Unit tests for Journal system.

Tests cover:
- JournalEntry creation and serialization
- Journal recording and listing
- Integration with yaml_io.save_yaml_doc()
- No reference leakage into journal
"""

import pytest
from pathlib import Path
import json

from quantumvitas.core.journal import (
    Journal,
    JournalEntry,
    get_journal,
    set_journal,
    reset_journal,
    infer_doc_type,
    extract_target_ulid,
    generate_summary,
)
from quantumvitas.core.yamldoc import YamlDoc, StepDoc
from quantumvitas.core.yaml_io import save_yaml_doc, load_yaml_doc


# =============================================================================
# JournalEntry Tests
# =============================================================================


class TestJournalEntry:
    """Test JournalEntry data model."""
    
    def test_create_entry(self):
        """Create a basic journal entry."""
        entry = JournalEntry.create(
            target_ulid="01ABC123",
            doc_type="step",
            before={"a": 1},
            after={"a": 2},
            summary="Test change",
        )
        
        assert entry.target_ulid == "01ABC123"
        assert entry.doc_type == "step"
        assert entry.before == {"a": 1}
        assert entry.after == {"a": 2}
        assert entry.summary == "Test change"
        assert entry.id  # ULID generated
        assert entry.timestamp  # Timestamp generated
    
    def test_entry_deep_copies(self):
        """Entry deep copies before/after."""
        before = {"nested": {"a": 1}}
        after = {"nested": {"a": 2}}
        
        entry = JournalEntry.create(
            target_ulid="01ABC123",
            doc_type="step",
            before=before,
            after=after,
            summary="Test",
        )
        
        # Mutate originals
        before["nested"]["a"] = 999
        after["nested"]["a"] = 999
        
        # Entry unaffected
        assert entry.before == {"nested": {"a": 1}}
        assert entry.after == {"nested": {"a": 2}}
    
    def test_entry_serialization(self):
        """Entry round-trips through JSON."""
        entry = JournalEntry.create(
            target_ulid="01ABC123",
            doc_type="step",
            before={"a": 1},
            after={"a": 2},
            summary="Test",
            path=Path("/tmp/test.yaml"),
        )
        
        data = entry.to_dict()
        restored = JournalEntry.from_dict(data)
        
        assert restored.id == entry.id
        assert restored.target_ulid == entry.target_ulid
        assert restored.before == entry.before
        assert restored.after == entry.after
        assert restored.path == entry.path


# =============================================================================
# Journal Tests
# =============================================================================


class TestJournal:
    """Test Journal recording and listing."""
    
    @pytest.fixture
    def journal(self, tmp_path):
        """Create a journal in a temp directory."""
        j = Journal(journal_dir=tmp_path / "journal")
        yield j
        j.clear()
    
    def test_record_and_list(self, journal):
        """Record entries and list them."""
        entry1 = JournalEntry.create(
            target_ulid="01ABC111",
            doc_type="step",
            before={},
            after={"a": 1},
            summary="First",
        )
        entry2 = JournalEntry.create(
            target_ulid="01ABC222",
            doc_type="calc",
            before={},
            after={"b": 2},
            summary="Second",
        )
        
        journal.record_change(entry1)
        journal.record_change(entry2)
        
        entries = journal.list_entries()
        
        assert len(entries) == 2
        # Most recent first
        assert entries[0].target_ulid == "01ABC222"
        assert entries[1].target_ulid == "01ABC111"
    
    def test_filter_by_target(self, journal):
        """Filter entries by target ULID."""
        entry1 = JournalEntry.create(
            target_ulid="TARGET1",
            doc_type="step",
            before={},
            after={},
            summary="A",
        )
        entry2 = JournalEntry.create(
            target_ulid="TARGET2",
            doc_type="step",
            before={},
            after={},
            summary="B",
        )
        
        journal.record_change(entry1)
        journal.record_change(entry2)
        
        entries = journal.list_entries(target_ulid="TARGET1")
        
        assert len(entries) == 1
        assert entries[0].target_ulid == "TARGET1"
    
    def test_filter_by_doc_type(self, journal):
        """Filter entries by document type."""
        entry1 = JournalEntry.create(
            target_ulid="ID1",
            doc_type="step",
            before={},
            after={},
            summary="Step change",
        )
        entry2 = JournalEntry.create(
            target_ulid="ID2",
            doc_type="project",
            before={},
            after={},
            summary="Project change",
        )
        
        journal.record_change(entry1)
        journal.record_change(entry2)
        
        step_entries = journal.list_entries(doc_type="step")
        
        assert len(step_entries) == 1
        assert step_entries[0].doc_type == "step"
    
    def test_limit_entries(self, journal):
        """Limit number of returned entries."""
        for i in range(10):
            entry = JournalEntry.create(
                target_ulid=f"ID{i}",
                doc_type="step",
                before={},
                after={},
                summary=f"Entry {i}",
            )
            journal.record_change(entry)
        
        entries = journal.list_entries(limit=3)
        
        assert len(entries) == 3
    
    def test_get_entry_by_id(self, journal):
        """Get specific entry by ID."""
        entry = JournalEntry.create(
            target_ulid="TARGET",
            doc_type="step",
            before={},
            after={"x": 1},
            summary="Test",
        )
        journal.record_change(entry)
        
        retrieved = journal.get_entry(entry.id)
        
        assert retrieved is not None
        assert retrieved.id == entry.id
        assert retrieved.after == {"x": 1}
    
    def test_get_nonexistent_entry(self, journal):
        """Get returns None for nonexistent ID."""
        result = journal.get_entry("nonexistent")
        assert result is None
    
    def test_disabled_journal(self, tmp_path):
        """Disabled journal doesn't record."""
        journal = Journal(journal_dir=tmp_path / "journal", enabled=False)
        
        entry = JournalEntry.create(
            target_ulid="ID",
            doc_type="step",
            before={},
            after={},
            summary="Test",
        )
        journal.record_change(entry)
        
        assert len(journal.list_entries()) == 0
    
    def test_clear_journal(self, journal):
        """Clear removes all entries."""
        entry = JournalEntry.create(
            target_ulid="ID",
            doc_type="step",
            before={},
            after={},
            summary="Test",
        )
        journal.record_change(entry)
        
        assert len(journal.list_entries()) == 1
        
        journal.clear()
        
        assert len(journal.list_entries()) == 0


# =============================================================================
# Integration Tests
# =============================================================================


class TestJournalIntegration:
    """Test Journal integration with yaml_io."""
    
    @pytest.fixture
    def test_journal(self, tmp_path):
        """Set up test journal."""
        journal = Journal(journal_dir=tmp_path / "journal")
        set_journal(journal)
        yield journal
        journal.clear()
        reset_journal()
    
    def test_save_doc_produces_journal_entry(self, tmp_path, test_journal):
        """Saving a Doc produces one JournalEntry."""
        path = tmp_path / "test.yaml"
        
        doc = YamlDoc({"meta": {"ulid": "01TEST123"}, "value": 1})
        doc.set(["value"], 2)
        
        save_yaml_doc(doc, path)
        
        entries = test_journal.list_entries()
        
        assert len(entries) == 1
        assert entries[0].target_ulid == "01TEST123"
    
    def test_before_after_differ(self, tmp_path, test_journal):
        """before/after differ when mutation happens."""
        path = tmp_path / "test.yaml"
        
        doc = YamlDoc({"meta": {"ulid": "01TEST456"}, "a": 1, "b": 2})
        doc.set(["a"], 99)
        doc.delete(["b"])
        doc.set(["c"], 3)
        
        save_yaml_doc(doc, path)
        
        entries = test_journal.list_entries()
        entry = entries[0]
        
        # Before has original values
        assert entry.before == {"meta": {"ulid": "01TEST456"}, "a": 1, "b": 2}
        
        # After has new values
        assert entry.after == {"meta": {"ulid": "01TEST456"}, "a": 99, "c": 3}
    
    def test_step_doc_produces_entry(self, tmp_path, test_journal):
        """StepDoc save produces journal entry with correct type."""
        path = tmp_path / "step.yaml"
        
        doc = StepDoc({
            "meta": {"ulid": "01STEP789", "kind": "step"},
            "step_type_gen": "scf",
            "parameters": {"SYSTEM": {"ecutwfc": 60}},
        })
        doc.set(["parameters", "SYSTEM", "ecutrho"], 480)
        
        doc.save(path)
        
        entries = test_journal.list_entries()
        
        assert len(entries) == 1
        assert entries[0].doc_type == "step"
        assert entries[0].target_ulid == "01STEP789"
    
    def test_no_entry_when_disabled(self, tmp_path, test_journal):
        """No entry when journal is disabled."""
        path = tmp_path / "test.yaml"
        
        test_journal.disable()
        
        doc = YamlDoc({"a": 1})
        save_yaml_doc(doc, path)
        
        assert len(test_journal.list_entries()) == 0
    
    def test_journal_entry_no_reference_leakage(self, tmp_path, test_journal):
        """Journal entries don't leak references to doc internals."""
        path = tmp_path / "test.yaml"
        
        doc = YamlDoc({"meta": {"ulid": "01TEST"}, "list": [1, 2, 3]})
        save_yaml_doc(doc, path)
        
        entries = test_journal.list_entries()
        entry = entries[0]
        
        # Mutate entry's data
        entry.after["list"].append(4)
        
        # Doc unaffected
        assert doc.get(["list"]) == [1, 2, 3]
        
        # Fresh entry read is also unaffected
        fresh_entry = test_journal.get_entry(entry.id)
        assert fresh_entry.after["list"] == [1, 2, 3]


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Test Journal helper functions."""
    
    def test_infer_doc_type_step(self):
        """Infer step doc type."""
        data = {"step_type_gen": "scf", "parameters": {}}
        assert infer_doc_type(data) == "step"
        
        data2 = {"meta": {"kind": "step"}}
        assert infer_doc_type(data2) == "step"
    
    def test_infer_doc_type_calc(self):
        """Infer calc doc type."""
        data = {"meta": {"kind": "calculation"}}
        assert infer_doc_type(data) == "calc"
        
        data2 = {"steps": [], "parent_calculation_id": "x"}
        assert infer_doc_type(data2) == "calc"
    
    def test_infer_doc_type_project(self):
        """Infer project doc type."""
        data = {"meta": {"kind": "project"}}
        assert infer_doc_type(data) == "project"
        
        data2 = {"calculations": []}
        assert infer_doc_type(data2) == "project"
    
    def test_infer_doc_type_unknown(self):
        """Unknown doc type fallback."""
        assert infer_doc_type({}) == "unknown"
        assert infer_doc_type({"random": "data"}) == "unknown"
    
    def test_extract_target_ulid(self):
        """Extract ULID from meta.id."""
        data = {"meta": {"ulid": "01ABC123"}}
        assert extract_target_ulid(data) == "01ABC123"
    
    def test_extract_target_ulid_fallback(self):
        """Fallback generates ULID when none present."""
        data = {}
        ulid = extract_target_ulid(data)
        assert len(ulid) == 26  # ULID length
    
    def test_generate_summary(self):
        """Generate human-readable summary."""
        before = {"a": 1, "b": 2}
        after = {"a": 99, "c": 3}  # a modified, b removed, c added
        
        summary = generate_summary("step", before, after)
        
        assert "step" in summary
        assert "+1" in summary or "~" in summary or "-" in summary

