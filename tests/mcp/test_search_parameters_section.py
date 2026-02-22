"""
Tests that search_parameters returns a 'section' field indicating the correct
namelist/block for engines that need structural nesting.
"""

import pytest

from qmatsuite.mcp.search_index import get_search_index, reset_search_index, TagDoc


@pytest.fixture(autouse=True)
def _reset_index():
    """Reset the singleton index before each test so changes are picked up."""
    reset_search_index()
    yield
    reset_search_index()


class TestTagDocSection:
    """Verify TagDoc carries a section field."""

    def test_tagdoc_has_section_slot(self):
        assert "section" in TagDoc.__slots__

    def test_tagdoc_section_defaults_empty(self):
        doc = TagDoc("qe", "ecutwfc", "float", 50, "SYSTEM", "Energy cutoff")
        assert doc.section == ""

    def test_tagdoc_section_set(self):
        doc = TagDoc("qe", "ecutwfc", "float", 50, "SYSTEM", "Energy cutoff", section="SYSTEM")
        assert doc.section == "SYSTEM"


class TestQESectionPopulated:
    """QE parameters must have section = namelist name."""

    def test_ecutwfc_section_is_system(self):
        index = get_search_index()
        hits = index.search("ecutwfc", engine="qe", max_results=1)
        assert len(hits) >= 1
        doc, _ = hits[0]
        assert doc.section == "SYSTEM"

    def test_diago_full_acc_section_is_electrons(self):
        index = get_search_index()
        hits = index.search("diago_full_acc", engine="qe", max_results=1)
        assert len(hits) >= 1
        doc, _ = hits[0]
        assert doc.section == "ELECTRONS"

    def test_conv_thr_section_is_electrons(self):
        index = get_search_index()
        hits = index.search("conv_thr", engine="qe", max_results=5)
        # Find the QE conv_thr (not VASP EDIFF which also matches "convergence threshold")
        qe_docs = [(d, s) for d, s in hits if d.engine == "qe" and d.tag_name == "conv_thr"]
        assert len(qe_docs) >= 1
        doc, _ = qe_docs[0]
        assert doc.section == "ELECTRONS"

    def test_pseudo_dir_section_is_control(self):
        index = get_search_index()
        hits = index.search("pseudo_dir", engine="qe", max_results=5)
        qe_docs = [d for d, _ in hits if d.tag_name == "pseudo_dir" and d.section == "CONTROL"]
        assert len(qe_docs) >= 1


class TestCP2KSectionPopulated:
    """CP2K parameters must have section from metadata."""

    def test_cp2k_run_type_has_section(self):
        index = get_search_index()
        hits = index.search("RUN_TYPE", engine="cp2k", max_results=3)
        cp2k_docs = [d for d, _ in hits if d.engine == "cp2k"]
        assert len(cp2k_docs) >= 1
        # CP2K tags have section field in their metadata
        assert cp2k_docs[0].section != ""


class TestORCASectionPopulated:
    """ORCA keywords get section='keyword_line', block params get 'block:<name>'."""

    def test_orca_keyword_section_is_keyword_line(self):
        index = get_search_index()
        # SP is a simple ORCA keyword
        hits = index.search("SP single point", engine="orca", max_results=5)
        orca_docs = [d for d, _ in hits if d.engine == "orca" and d.section == "keyword_line"]
        assert len(orca_docs) >= 1

    def test_orca_block_param_section(self):
        index = get_search_index()
        # MaxIter is a parameter inside block sections
        hits = index.search("MaxIter", engine="orca", max_results=10)
        block_docs = [d for d, _ in hits if d.engine == "orca" and d.section.startswith("block:")]
        assert len(block_docs) >= 1
        # At least one should be from the scf block
        scf_docs = [d for d in block_docs if d.section == "block:scf"]
        assert len(scf_docs) >= 1


class TestSearchParametersToolSection:
    """Verify the search_parameters response includes section in results."""

    def test_search_results_include_section_for_qe(self):
        """QE results should have section field set to the namelist."""
        from qmatsuite.mcp.search_index import get_search_index

        index = get_search_index()
        hits = index.search("ecutwfc", engine="qe", max_results=1)
        assert len(hits) >= 1
        doc, _ = hits[0]
        # Verify the doc has section populated — this is what the tool reads
        assert doc.section == "SYSTEM"

    def test_search_results_omit_empty_section(self):
        """LAMMPS commands have empty section — should be omitted from response."""
        from qmatsuite.mcp.search_index import get_search_index

        index = get_search_index()
        hits = index.search("units", engine="lammps", max_results=1)
        if hits:
            doc, _ = hits[0]
            # LAMMPS doesn't have structural sections
            assert doc.section == ""
