"""
Gate test for Law P5: CAS Integrity.

Per PROVENANCE_VERSIONED_HISTORY_SPEC.md Law P5:
> CAS objects are immutable and content-addressed by SHA-256.

Key invariants:
- Object path is derived from hash: .cas/objects/<first2>/<rest>
- Once written, a CAS object is never modified
- Duplicate writes (same hash) are no-ops
- SHA exists ONLY for objects actually stored in CAS
"""

import pytest
import hashlib
from pathlib import Path


def test_cas_content_addressed(tmp_path):
    """
    Law P5: CAS objects are content-addressed.

    Same content always produces same SHA, and duplicate writes are no-ops.
    """
    from quantumvitas.provenance.cas import CAS
    from quantumvitas.provenance.db import ensure_provenance_initialized

    ensure_provenance_initialized(tmp_path)
    cas = CAS(tmp_path)

    content = b"test content for CAS"

    # First store
    sha1 = cas.store(content, tier=0)

    # Second store of same content
    sha2 = cas.store(content, tier=0)

    # Same SHA
    assert sha1 == sha2

    # Verify SHA is correct
    expected_sha = hashlib.sha256(content).hexdigest()
    assert sha1 == expected_sha

    # Verify object exists
    assert cas.exists(sha1)


def test_cas_immutable(tmp_path):
    """
    Law P5: CAS objects are immutable - content never changes.

    Once written, retrieving the same SHA returns the same content.
    """
    from quantumvitas.provenance.cas import CAS
    from quantumvitas.provenance.db import ensure_provenance_initialized

    ensure_provenance_initialized(tmp_path)
    cas = CAS(tmp_path)

    content = b"original content that should be preserved"
    sha = cas.store(content, tier=0)

    # Retrieve and verify
    retrieved = cas.retrieve(sha)
    assert retrieved == content

    # Store different content - should get different SHA
    different_content = b"different content"
    sha2 = cas.store(different_content, tier=0)
    assert sha != sha2

    # Original still unchanged
    retrieved_again = cas.retrieve(sha)
    assert retrieved_again == content


def test_cas_duplicate_noop(tmp_path):
    """
    Law P5: Duplicate writes are no-ops.

    Storing the same content twice doesn't create duplicate files.
    """
    from quantumvitas.provenance.cas import CAS
    from quantumvitas.provenance.db import ensure_provenance_initialized

    ensure_provenance_initialized(tmp_path)
    cas = CAS(tmp_path)

    content = b"content for dedup test"
    sha = cas.store(content, tier=0)

    # Get the object path
    obj_path = cas._object_path(sha)
    assert obj_path.exists()

    # Store again
    sha2 = cas.store(content, tier=0)
    assert sha == sha2

    # Still only one file
    assert obj_path.exists()

    # Count files in objects directory
    objects_dir = tmp_path / ".provenance" / ".cas" / "objects"
    all_files = list(objects_dir.rglob("*"))
    file_count = sum(1 for f in all_files if f.is_file())
    assert file_count == 1


def test_cas_path_derivation(tmp_path):
    """
    Law P5: Object path is derived from hash.

    Path format: .cas/objects/<first2>/<rest>
    """
    from quantumvitas.provenance.cas import CAS
    from quantumvitas.provenance.db import ensure_provenance_initialized

    ensure_provenance_initialized(tmp_path)
    cas = CAS(tmp_path)

    content = b"path derivation test"
    sha = cas.store(content, tier=0)

    # Verify path format
    expected_path = tmp_path / ".provenance" / ".cas" / "objects" / sha[:2] / sha[2:]
    assert expected_path.exists()

    # Internal method should give same path
    internal_path = cas._object_path(sha)
    assert internal_path == expected_path


def test_cas_integrity_check(tmp_path):
    """
    Law P5: Integrity check catches corruption.

    Corrupting a CAS object should raise CASIntegrityError on retrieve.
    """
    from quantumvitas.provenance.cas import CAS
    from quantumvitas.provenance.db import ensure_provenance_initialized
    from quantumvitas.provenance.errors import CASIntegrityError

    ensure_provenance_initialized(tmp_path)
    cas = CAS(tmp_path)

    content = b"content that will be corrupted"
    sha = cas.store(content, tier=0)

    # Corrupt the file
    obj_path = cas._object_path(sha)
    obj_path.write_bytes(b"corrupted content")

    # Retrieve should fail with integrity error
    with pytest.raises(CASIntegrityError):
        cas.retrieve(sha)


def test_cas_not_found(tmp_path):
    """
    CAS should raise SnapshotNotFoundError for missing objects.
    """
    from quantumvitas.provenance.cas import CAS
    from quantumvitas.provenance.db import ensure_provenance_initialized
    from quantumvitas.provenance.errors import SnapshotNotFoundError

    ensure_provenance_initialized(tmp_path)
    cas = CAS(tmp_path)

    fake_sha = "a" * 64  # Valid-looking but nonexistent

    with pytest.raises(SnapshotNotFoundError):
        cas.retrieve(fake_sha)

    assert not cas.exists(fake_sha)


def test_cas_json_roundtrip(tmp_path):
    """
    CAS JSON store/retrieve preserves data.
    """
    from quantumvitas.provenance.cas import CAS
    from quantumvitas.provenance.db import ensure_provenance_initialized

    ensure_provenance_initialized(tmp_path)
    cas = CAS(tmp_path)

    data = {
        "name": "test",
        "values": [1, 2, 3],
        "nested": {"key": "value"},
    }

    sha = cas.store_json(data, tier=1)
    retrieved = cas.retrieve_json(sha)

    assert retrieved == data


def test_cas_tier_recorded(tmp_path):
    """
    CAS objects should have their tier recorded in the database.
    """
    from quantumvitas.provenance.cas import CAS
    from quantumvitas.provenance.db import open_provenance_db, ensure_provenance_initialized

    ensure_provenance_initialized(tmp_path)
    cas = CAS(tmp_path)

    content = b"tier test content"
    sha = cas.store(content, tier=2)

    # Check database
    conn = open_provenance_db(tmp_path)
    try:
        cursor = conn.execute(
            "SELECT tier, size_bytes FROM cas_objects WHERE sha256 = ?",
            (sha,),
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["tier"] == 2
    assert row["size_bytes"] == len(content)
