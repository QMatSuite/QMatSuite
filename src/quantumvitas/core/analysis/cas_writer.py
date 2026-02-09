"""CAS/SQLite writers for canonical analysis snapshots."""
from __future__ import annotations

import gzip
import json
import sqlite3
from pathlib import Path
from typing import Sequence

from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha


def _canonical_payload_bytes(bundle: CanonicalPrimitiveBundle) -> bytes:
    return json.dumps(
        bundle.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def write_canonical_to_cas(bundle: CanonicalPrimitiveBundle, cas_dir: Path) -> str:
    """
    Persist canonical bundle payload to CAS directory by canonical content hash.

    The blob path is ``<cas_dir>/<canonical_sha>.json.gz``.
    """
    canonical_sha = compute_canonical_sha(bundle)
    target_dir = Path(cas_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{canonical_sha}.json.gz"

    if target_path.exists():
        return canonical_sha

    payload = _canonical_payload_bytes(bundle)
    temp_path = target_dir / f".{canonical_sha}.tmp"
    with gzip.open(temp_path, mode="wb") as handle:
        handle.write(payload)
    temp_path.replace(target_path)
    return canonical_sha


def write_analysis_snapshot_row(
    db_path: Path,
    run_ulid: str,
    object_type: str,
    canonical_sha: str,
    step_ulids: Sequence[str],
    gen_steps: Sequence[str],
    *,
    thumbnail_sha: str | None = None,
    match_key: str | None = None,
    evidence_fingerprint: str | None = None,
) -> None:
    """Insert or update analysis snapshot linkage in SQLite."""
    conn = sqlite3.connect(str(db_path))
    try:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(analysis_snapshots)").fetchall()
        }
        has_match_key = "match_key" in columns
        has_evidence_fp = "evidence_fingerprint" in columns

        step_ulids_json = json.dumps(list(step_ulids), separators=(",", ":"))
        gen_steps_json = json.dumps(list(gen_steps), separators=(",", ":"))

        if has_match_key and has_evidence_fp:
            conn.execute(
                """
                INSERT INTO analysis_snapshots (
                    run_ulid, object_type, canonical_sha, thumbnail_sha,
                    match_key, evidence_fingerprint, step_ulids, gen_steps
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_ulid, object_type) DO UPDATE SET
                    canonical_sha = excluded.canonical_sha,
                    thumbnail_sha = COALESCE(excluded.thumbnail_sha, analysis_snapshots.thumbnail_sha),
                    match_key = COALESCE(excluded.match_key, analysis_snapshots.match_key),
                    evidence_fingerprint = COALESCE(excluded.evidence_fingerprint, analysis_snapshots.evidence_fingerprint),
                    step_ulids = excluded.step_ulids,
                    gen_steps = excluded.gen_steps
                """,
                (
                    run_ulid,
                    object_type,
                    canonical_sha,
                    thumbnail_sha,
                    match_key,
                    evidence_fingerprint,
                    step_ulids_json,
                    gen_steps_json,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO analysis_snapshots (
                    run_ulid, object_type, canonical_sha, thumbnail_sha, step_ulids, gen_steps
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_ulid, object_type) DO UPDATE SET
                    canonical_sha = excluded.canonical_sha,
                    thumbnail_sha = COALESCE(excluded.thumbnail_sha, analysis_snapshots.thumbnail_sha),
                    step_ulids = excluded.step_ulids,
                    gen_steps = excluded.gen_steps
                """,
                (
                    run_ulid,
                    object_type,
                    canonical_sha,
                    thumbnail_sha,
                    step_ulids_json,
                    gen_steps_json,
                ),
            )
        conn.commit()
    finally:
        conn.close()
