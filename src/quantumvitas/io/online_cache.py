"""
Online structure fetch cache.

Stores fetched structures in SQLite with MessagePack binary blobs.
No .json/.yaml/.yml files are created in the cache directory.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import msgpack
    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False
    import pickle

from pymatgen.core import Structure as PMGStructure


# TTL: 30 days in seconds
CACHE_TTL_SECONDS = 30 * 24 * 60 * 60


@dataclass
class CandidateSummary:
    """Summary of an online structure candidate."""
    candidate_id: str
    label: str
    source: str  # "optimade" or "cod"
    source_id: str
    nsites: int
    spacegroup: Optional[str] = None
    flags: List[str] = None
    score: float = 0.0
    
    def __post_init__(self):
        if self.flags is None:
            self.flags = []


@dataclass
class SessionInfo:
    """Information about a search session."""
    session_id: str
    query: str
    created_at: int
    source_summary: str  # "optimade" or "cod" or "optimade+cod"


class OnlineStructureCache:
    """
    SQLite-based cache for online structure searches.
    
    Stores:
    - Sessions (search queries)
    - Candidates (search results with metadata)
    - Structures (full structure data as binary blobs)
    
    Uses MessagePack for binary serialization (fallback to pickle if unavailable).
    
    PR0: Cache location migrated to global user cache (~/.qmatsuite/cache/online_structures/).
    """
    
    def __init__(self, cache_dir: Path | None = None):
        """
        Initialize cache.
        
        Args:
            cache_dir: Directory for cache. If None, uses global cache location
                      (~/.qmatsuite/cache/online_structures/).
        """
        if cache_dir is None:
            # PR0: Use global cache location (not project-specific)
            from quantumvitas.core.paths import get_qmatsuite_home_root
            cache_dir = get_qmatsuite_home_root() / "cache" / "online_structures"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Use .sqlite3 extension (not .json/.yaml/.yml)
        self.db_path = self.cache_dir / "structure_fetch_cache.sqlite3"
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database schema."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    source_summary TEXT
                )
            """)
            
            # Candidates table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS candidates (
                    session_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    rank INTEGER NOT NULL,
                    score REAL NOT NULL,
                    label TEXT NOT NULL,
                    source TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    flags TEXT,
                    structure_key TEXT,
                    PRIMARY KEY (session_id, candidate_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            
            # Structures table
            # payload can be NULL for metadata-only entries (OPTIMADE entries that need 2-step fetch)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS structures (
                    structure_key TEXT PRIMARY KEY,
                    created_at INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    source_id TEXT,
                    payload BLOB,
                    meta BLOB
                )
            """)
            
            # Indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_candidates_session 
                ON candidates(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_structures_created 
                ON structures(created_at)
            """)
            
            conn.commit()
        finally:
            conn.close()
    
    def _serialize_structure(self, structure: PMGStructure) -> bytes:
        """Serialize structure to binary."""
        structure_dict = structure.as_dict()
        if MSGPACK_AVAILABLE:
            return msgpack.packb(structure_dict, use_bin_type=True)
        else:
            return pickle.dumps(structure_dict)
    
    def _deserialize_structure(self, data: bytes) -> PMGStructure:
        """Deserialize structure from binary."""
        if MSGPACK_AVAILABLE:
            structure_dict = msgpack.unpackb(data, raw=False)
        else:
            structure_dict = pickle.loads(data)
        return PMGStructure.from_dict(structure_dict)
    
    def _compute_structure_key(self, structure: PMGStructure) -> str:
        """
        Compute stable hash key for structure deduplication.
        
        Uses SHA256 over a stable serialization of structure.as_dict().
        """
        structure_dict = structure.as_dict()
        # Use JSON for stable serialization (sorted keys for reproducibility)
        # Note: msgpack doesn't reliably support sort_keys across all versions
        import json
        serialized = json.dumps(structure_dict, sort_keys=True).encode('utf-8')
        return hashlib.sha256(serialized).hexdigest()
    
    def create_session(
        self,
        session_id: str,
        query: str,
        source_summary: str,
    ) -> None:
        """Create a new search session."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO sessions (session_id, query, created_at, source_summary)
                VALUES (?, ?, ?, ?)
            """, (session_id, query, int(time.time()), source_summary))
            conn.commit()
        finally:
            conn.close()
    
    def get_session_info(self, session_id: str) -> Optional[SessionInfo]:
        """Get session information."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_id, query, created_at, source_summary
                FROM sessions
                WHERE session_id = ?
            """, (session_id,))
            
            row = cursor.fetchone()
            if row:
                return SessionInfo(
                    session_id=row[0],
                    query=row[1],
                    created_at=row[2],
                    source_summary=row[3],
                )
            return None
        finally:
            conn.close()
    
    def add_candidate(
        self,
        session_id: str,
        candidate: CandidateSummary,
        structure: PMGStructure,
        rank: int,
    ) -> None:
        """
        Add a candidate with its structure to the cache.
        
        Args:
            session_id: Session ID
            candidate: Candidate summary
            structure: Full structure object
            rank: Rank in search results (0-indexed)
        """
        structure_key = self._compute_structure_key(structure)
        structure_blob = self._serialize_structure(structure)
        
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # Store structure if not already present
            cursor.execute("""
                INSERT OR IGNORE INTO structures (structure_key, created_at, source, source_id, payload)
                VALUES (?, ?, ?, ?, ?)
            """, (
                structure_key,
                int(time.time()),
                candidate.source,
                candidate.source_id,
                structure_blob,
            ))
            
            # Store candidate
            flags_str = ",".join(candidate.flags) if candidate.flags else None
            cursor.execute("""
                INSERT OR REPLACE INTO candidates 
                (session_id, candidate_id, rank, score, label, source, source_id, flags, structure_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                candidate.candidate_id,
                rank,
                candidate.score,
                candidate.label,
                candidate.source,
                candidate.source_id,
                flags_str,
                structure_key,
            ))
            
            conn.commit()
        finally:
            conn.close()
    
    def add_candidate_metadata_only(
        self,
        session_id: str,
        candidate: CandidateSummary,
        rank: int,
        optimade_base: Optional[str] = None,
    ) -> None:
        """
        Add a candidate with metadata only (structure fetched later).
        
        Used for OPTIMADE entries that need 2-step fetch.
        
        Args:
            session_id: Session ID
            candidate: Candidate summary
            rank: Rank in search results (0-indexed)
            optimade_base: OPTIMADE base URL (stored in candidates table flags field as JSON)
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # Store optimade_base in flags field as JSON (along with actual flags)
            flags_data = {
                "flags": candidate.flags or [],
                "optimade_base": optimade_base,
            }
            import json
            flags_str = json.dumps(flags_data)
            
            # Store candidate without structure_key (will be set when structure is fetched)
            cursor.execute("""
                INSERT OR REPLACE INTO candidates 
                (session_id, candidate_id, rank, score, label, source, source_id, flags, structure_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                candidate.candidate_id,
                rank,
                candidate.score,
                candidate.label,
                candidate.source,
                candidate.source_id,
                flags_str,
                None,  # structure_key is None until structure is fetched
            ))
            
            conn.commit()
        finally:
            conn.close()
    
    def get_candidate_metadata(self, session_id: str, candidate_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a candidate (e.g., optimade_base)."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT flags
                FROM candidates
                WHERE session_id = ? AND candidate_id = ?
            """, (session_id, candidate_id))
            
            row = cursor.fetchone()
            if row and row[0]:
                import json
                try:
                    flags_data = json.loads(row[0])
                    # Check if it's the new JSON format with optimade_base
                    if isinstance(flags_data, dict) and "optimade_base" in flags_data:
                        return {"optimade_base": flags_data["optimade_base"]}
                except (json.JSONDecodeError, TypeError):
                    # Old format - just a comma-separated string
                    pass
            return None
        finally:
            conn.close()
    
    def get_candidates(self, session_id: str) -> List[CandidateSummary]:
        """Get all candidates for a session."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            # Extract nsites from label if possible, or try to get from structure
            cursor.execute("""
                SELECT candidate_id, label, source, source_id, flags, score, structure_key
                FROM candidates
                WHERE session_id = ?
                ORDER BY rank ASC
            """, (session_id,))
            
            candidates = []
            for row in cursor.fetchall():
                candidate_id, label, source, source_id, flags_str, score, structure_key = row
                
                # Parse flags - can be JSON (new format) or comma-separated (old format)
                flags = []
                import json
                try:
                    flags_data = json.loads(flags_str) if flags_str else {}
                    if isinstance(flags_data, dict):
                        flags = flags_data.get("flags", [])
                    else:
                        flags = flags_str.split(",") if flags_str else []
                except (json.JSONDecodeError, TypeError):
                    # Old format - just a comma-separated string
                    flags = flags_str.split(",") if flags_str else []
                
                # Try to extract nsites from label (format: "Formula (N sites)")
                nsites = 0
                import re
                match = re.search(r'\((\d+)\s+sites?\)', label)
                if match:
                    nsites = int(match.group(1))
                elif structure_key:
                    # Try to load structure to get nsites
                    try:
                        structure = self.get_structure_by_key(structure_key)
                        if structure:
                            nsites = len(structure)
                    except Exception:
                        pass
                
                candidates.append(CandidateSummary(
                    candidate_id=candidate_id,
                    label=label,
                    source=source,
                    source_id=source_id,
                    nsites=nsites,
                    flags=flags,
                    score=score,
                ))
            return candidates
        finally:
            conn.close()
    
    def get_structure_by_key(self, structure_key: str) -> Optional[PMGStructure]:
        """Get structure by structure_key."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT payload
                FROM structures
                WHERE structure_key = ?
            """, (structure_key,))
            
            row = cursor.fetchone()
            if row and row[0]:
                return self._deserialize_structure(row[0])
            return None
        finally:
            conn.close()
    
    def get_structure(self, session_id: str, candidate_id: str) -> Optional[PMGStructure]:
        """
        Get structure for a candidate.
        
        Args:
            session_id: Session ID
            candidate_id: Candidate ID
            
        Returns:
            Structure object or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.payload
                FROM structures s
                JOIN candidates c ON s.structure_key = c.structure_key
                WHERE c.session_id = ? AND c.candidate_id = ?
            """, (session_id, candidate_id))
            
            row = cursor.fetchone()
            if row is None:
                return None
            
            blob = row[0]
            return self._deserialize_structure(blob)
        finally:
            conn.close()
    
    def cleanup_old_entries(self, ttl_seconds: int = CACHE_TTL_SECONDS) -> int:
        """
        Remove entries older than TTL.
        
        Returns:
            Number of entries removed
        """
        cutoff_time = int(time.time()) - ttl_seconds
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # Delete old sessions and their candidates
            cursor.execute("""
                DELETE FROM sessions
                WHERE created_at < ?
            """, (cutoff_time,))
            deleted_sessions = cursor.rowcount
            
            # Delete orphaned structures (not referenced by any candidate)
            cursor.execute("""
                DELETE FROM structures
                WHERE structure_key NOT IN (
                    SELECT DISTINCT structure_key FROM candidates WHERE structure_key IS NOT NULL
                )
                AND created_at < ?
            """, (cutoff_time,))
            deleted_structures = cursor.rowcount
            
            conn.commit()
            return deleted_sessions + deleted_structures
        finally:
            conn.close()
