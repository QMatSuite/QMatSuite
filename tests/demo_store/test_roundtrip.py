"""Tests for roundtrip equivalence checker."""

from quantumvitas.demo_store.roundtrip import verify_roundtrip_equivalence, RoundtripReport


class TestRoundtripEquivalence:
    def test_identical_snapshots(self):
        """Identical snapshots must be equivalent."""
        snap = {
            "version": 1,
            "project": {"meta": {"ulid": "A", "name": "p", "slug": "p", "kind": "project"}},
            "structures": [{"meta": {"ulid": "B", "name": "Si", "slug": "si", "kind": "structure"},
                            "data": {"lattice": [[1, 0, 0]]}}],
            "calculations": [{"meta": {"ulid": "C", "name": "c", "slug": "c", "kind": "calculation"},
                              "engine_family": "vasp",
                              "structure_ulid": "B",
                              "steps": [{"meta": {"ulid": "D", "name": "scf", "slug": "scf", "kind": "step"},
                                         "step_type_spec": "vasp_scf",
                                         "parameters": {"ENCUT": 300}}]}],
        }
        report = verify_roundtrip_equivalence(snap, snap)
        assert report.equivalent
        assert len(report.differences) == 0

    def test_ulid_variance_allowed(self):
        """ULIDs may differ between snapshots."""
        snap_a = {
            "version": 1,
            "project": {"meta": {"ulid": "AAA", "name": "p", "slug": "p", "kind": "project"}},
            "structures": [],
            "calculations": [],
        }
        snap_b = {
            "version": 1,
            "project": {"meta": {"ulid": "BBB", "name": "p", "slug": "p", "kind": "project"}},
            "structures": [],
            "calculations": [],
        }
        report = verify_roundtrip_equivalence(snap_a, snap_b)
        assert report.equivalent

    def test_meta_section_ignored(self):
        """Top-level meta (gallery) section must be ignored."""
        snap_a = {
            "version": 1,
            "project": {"meta": {"ulid": "A", "name": "p", "slug": "p", "kind": "project"}},
            "structures": [],
            "calculations": [],
            "meta": {"ulid": "demo1", "title": "Title A"},
        }
        snap_b = {
            "version": 1,
            "project": {"meta": {"ulid": "A", "name": "p", "slug": "p", "kind": "project"}},
            "structures": [],
            "calculations": [],
        }
        report = verify_roundtrip_equivalence(snap_a, snap_b)
        assert report.equivalent

    def test_parameter_mismatch_detected(self):
        """Parameter differences must be detected."""
        snap_a = {
            "version": 1,
            "project": {"meta": {"ulid": "A", "name": "p", "slug": "p", "kind": "project"}},
            "structures": [],
            "calculations": [{"meta": {"ulid": "C", "name": "c", "slug": "c", "kind": "calculation"},
                              "engine_family": "vasp",
                              "steps": [{"meta": {"ulid": "D", "name": "scf", "slug": "scf", "kind": "step"},
                                         "step_type_spec": "vasp_scf",
                                         "parameters": {"ENCUT": 300}}]}],
        }
        snap_b = {
            "version": 1,
            "project": {"meta": {"ulid": "A", "name": "p", "slug": "p", "kind": "project"}},
            "structures": [],
            "calculations": [{"meta": {"ulid": "C", "name": "c", "slug": "c", "kind": "calculation"},
                              "engine_family": "vasp",
                              "steps": [{"meta": {"ulid": "D", "name": "scf", "slug": "scf", "kind": "step"},
                                         "step_type_spec": "vasp_scf",
                                         "parameters": {"ENCUT": 500}}]}],
        }
        report = verify_roundtrip_equivalence(snap_a, snap_b)
        assert not report.equivalent
        assert len(report.differences) > 0

    def test_managed_keys_variance_allowed(self):
        """Managed keys (like outdir for QE) may differ."""
        snap_a = {
            "version": 1,
            "project": {"meta": {"ulid": "A", "name": "p", "slug": "p", "kind": "project"}},
            "structures": [],
            "calculations": [{"meta": {"ulid": "C", "name": "c", "slug": "c", "kind": "calculation"},
                              "engine_family": "qe",
                              "steps": [{"meta": {"ulid": "D", "name": "scf", "slug": "scf", "kind": "step"},
                                         "step_type_spec": "qe_scf",
                                         "parameters": {"CONTROL": {"ecutwfc": 40, "outdir": "./tmp"}}}]}],
        }
        snap_b = {
            "version": 1,
            "project": {"meta": {"ulid": "A", "name": "p", "slug": "p", "kind": "project"}},
            "structures": [],
            "calculations": [{"meta": {"ulid": "C", "name": "c", "slug": "c", "kind": "calculation"},
                              "engine_family": "qe",
                              "steps": [{"meta": {"ulid": "D", "name": "scf", "slug": "scf", "kind": "step"},
                                         "step_type_spec": "qe_scf",
                                         "parameters": {"CONTROL": {"ecutwfc": 40}}}]}],
        }
        report = verify_roundtrip_equivalence(snap_a, snap_b)
        assert report.equivalent
