"""
Provenance system errors.

These exceptions are used throughout the provenance module.
Per Law P7, provenance errors must not fail YAML writes.
"""

from __future__ import annotations


class ProvenanceError(Exception):
    """
    Base class for provenance errors.

    Per Law P7 (Graceful Degradation): Provenance failures MUST NOT fail YAML writes.
    All provenance errors are caught and logged; they don't propagate to callers
    of save_yaml_doc().
    """
    pass


class OperationContextRequiredError(ProvenanceError):
    """
    Raised when save_yaml_doc() is called without an OperationContext.

    Per Law P2 (OperationContext Required): Any write to Present World SSOT YAML
    MUST carry an explicit OperationContext.

    This is the ONE exception that IS allowed to fail YAML writes, because it
    indicates a programming error (missing opctx), not a runtime provenance failure.
    """
    pass


class CASIntegrityError(ProvenanceError):
    """
    Raised when CAS content hash doesn't match expected value.

    Per Law P5 (CAS Integrity): CAS objects are immutable and content-addressed.
    This error indicates corruption or tampering.
    """
    pass


class SnapshotNotFoundError(ProvenanceError):
    """
    Raised when a requested snapshot doesn't exist in CAS.

    This can happen if:
    - The snapshot was garbage collected
    - The snapshot SHA was corrupted in the database
    - The CAS directory was manually deleted
    """
    pass


class LockReentrancyError(ProvenanceError):
    """
    Raised when attempting to acquire a lock that's already held by this thread.

    Per Law P6 (Lock Ordering): Locks must be acquired sequentially, never nested.
    This error indicates a programming error in lock acquisition order.
    """
    pass
