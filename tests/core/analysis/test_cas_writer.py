"""Tests for canonical CAS and SQLite snapshot writers."""

from __future__ import annotations

import gzip
import json
import sqlite3
from pathlib import Path

import numpy as np

from qmatsuite.core.analysis.bundles import (
    CanonicalPrimitiveBundle,
    ProvenanceMeta,
    RenderMeta,
    compute_canonical_sha,
)
from qmatsuite.core.analysis.cas_writer import (
    write_analysis_snapshot_row,
    write_canonical_to_cas,
)
from qmatsuite.provenance.db import get_db_path, open_provenance_db


def _bundle() -> CanonicalPrimitiveBundle:
    return CanonicalPrimitiveBundle(
        object_type="bands",
        render_meta=RenderMeta(axis_labels={"x": "k", "y": "E"}, units={"x": "1/A", "y": "eV"}),
        provenance_meta=ProvenanceMeta(
            schema_version="1.0",
            object_type="bands",
            run_ulid="01RUN",
            calc_ulid="01CALC",
            step_ulids=["01STEP1"],
            gen_steps=["bandspw"],
            engine_name="qe",
            parser_name="qe_bands",
            parser_version="1.0",
        ),
        arrays={"k_distances": np.array([0.0, 0.5, 1.0])},
    )


def test_write_canonical_to_cas_roundtrip(tmp_path: Path) -> None:
    bundle = _bundle()
    cas_dir = tmp_path / "analysis_cas"

    sha = write_canonical_to_cas(bundle, cas_dir)
    assert sha == compute_canonical_sha(bundle)

    blob_path = cas_dir / f"{sha}.json.gz"
    assert blob_path.exists()

    with gzip.open(blob_path, "rb") as handle:
        payload = json.loads(handle.read().decode("utf-8"))
    assert payload == bundle.to_dict()

    # Rewriting identical content is a no-op.
    sha_again = write_canonical_to_cas(bundle, cas_dir)
    assert sha_again == sha


def test_write_analysis_snapshot_row_upsert(tmp_path: Path) -> None:
    # Initialize provenance DB with schema.
    conn = open_provenance_db(tmp_path)
    conn.close()
    db_path = get_db_path(tmp_path)

    write_analysis_snapshot_row(
        db_path=db_path,
        run_ulid="01RUN",
        object_type="bands",
        canonical_sha="a" * 64,
        step_ulids=["01STEP1"],
        gen_steps=["bandspw"],
        match_key="bands:01STEP1",
        evidence_fingerprint="fp-1",
    )

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            """
            SELECT canonical_sha, step_ulids, gen_steps, match_key, evidence_fingerprint
            FROM analysis_snapshots
            WHERE run_ulid = ? AND object_type = ?
            """,
            ("01RUN", "bands"),
        ).fetchone()
        assert row is not None
        assert row[0] == "a" * 64
        assert json.loads(row[1]) == ["01STEP1"]
        assert json.loads(row[2]) == ["bandspw"]
        assert row[3] == "bands:01STEP1"
        assert row[4] == "fp-1"
    finally:
        conn.close()

    # With multi-match semantics, a different match_key creates a NEW row
    # (not an upsert), since UNIQUE is (run_ulid, object_type, match_key).
    write_analysis_snapshot_row(
        db_path=db_path,
        run_ulid="01RUN",
        object_type="bands",
        canonical_sha="b" * 64,
        step_ulids=["01STEP1", "01STEP2"],
        gen_steps=["scf", "bandspw"],
        match_key="bands:01STEP1,01STEP2",
        evidence_fingerprint="fp-2",
    )

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            """
            SELECT canonical_sha, step_ulids, gen_steps, match_key, evidence_fingerprint
            FROM analysis_snapshots
            WHERE run_ulid = ? AND object_type = ?
            ORDER BY match_key
            """,
            ("01RUN", "bands"),
        ).fetchall()
        # Two distinct match_keys → two rows (AC9: multi-match SQLite)
        assert len(rows) == 2
        # First row: bands:01STEP1
        assert rows[0][0] == "a" * 64
        assert rows[0][3] == "bands:01STEP1"
        # Second row: bands:01STEP1,01STEP2
        assert rows[1][0] == "b" * 64
        assert rows[1][3] == "bands:01STEP1,01STEP2"
    finally:
        conn.close()

    # Upsert with SAME match_key overwrites the existing row
    write_analysis_snapshot_row(
        db_path=db_path,
        run_ulid="01RUN",
        object_type="bands",
        canonical_sha="c" * 64,
        step_ulids=["01STEP1"],
        gen_steps=["bandspw"],
        match_key="bands:01STEP1",
        evidence_fingerprint="fp-3",
    )

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            """
            SELECT canonical_sha, evidence_fingerprint
            FROM analysis_snapshots
            WHERE run_ulid = ? AND object_type = ? AND match_key = ?
            """,
            ("01RUN", "bands", "bands:01STEP1"),
        ).fetchone()
        assert row is not None
        assert row[0] == "c" * 64  # Updated
        assert row[1] == "fp-3"  # Updated
    finally:
        conn.close()
