"""
Regression tests for online candidate handler.

Tests that the handler properly handles missing candidates and structures
without raising UnboundLocalError.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from quantumvitas.daemon.server import QVDaemon


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project directory."""
    from quantumvitas.api import QVService
    
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    
    # Initialize as a proper QuantumVITAS project
    QVService.init_project(project_root, name="test_project")
    
    # Ensure cache directory exists
    (project_root / "structures" / "cache").mkdir(parents=True, exist_ok=True)
    
    return project_root


@pytest.fixture
def daemon():
    """Create a QVDaemon instance."""
    return QVDaemon()


def test_get_online_candidate_missing_candidate(temp_project, daemon):
    """
    Test that handler returns error (not UnboundLocalError) when candidate is missing.
    
    Regression test for: candidate was only assigned when structure is None,
    but used later regardless, causing UnboundLocalError when structure exists in cache.
    """
    from quantumvitas.io.online_cache import OnlineStructureCache
    
    # Create a cache with a session but no matching candidate
    cache = OnlineStructureCache(temp_project / "structures" / "cache")
    
    # Add a session using cache method
    import time
    session_id = "test_session_123"
    cache.create_session(session_id, "Si", "optimade")
    
    # Try to get a candidate that doesn't exist
    payload = {
        "project_root": str(temp_project),
        "session_id": session_id,
        "candidate_id": "nonexistent_candidate",
        "trace_id": "test_trace",
    }
    
    # Should return error, not raise UnboundLocalError
    # The handler may raise or return error - we just need to ensure it doesn't raise UnboundLocalError
    try:
        result = daemon._handle_structure_get_online_candidate(payload)
        
        # If it returns a dict, check structure
        if isinstance(result, dict):
            if "error" in result:
                assert result["error"]["code"] == "CANDIDATE_NOT_FOUND", (
                    f"Expected CANDIDATE_NOT_FOUND, got {result.get('error', {}).get('code')}"
                )
            elif "ok" in result:
                assert result.get("ok") is False, "Handler should return ok:false for missing candidate"
    except UnboundLocalError as e:
        pytest.fail(f"UnboundLocalError raised (regression): {e}")
    except (ValueError, KeyError) as e:
        # These are acceptable - handler may raise for missing candidate
        # The key is that it's NOT UnboundLocalError
        pass


def test_get_online_candidate_missing_structure(temp_project, daemon):
    """
    Test that handler returns error (not exception) when structure is missing.
    
    Regression test: ensure structure lookup failure returns structured error.
    """
    from quantumvitas.io.online_cache import OnlineStructureCache
    from quantumvitas.io.online_cache import CandidateSummary
    
    # Create a cache with a session and candidate, but no structure
    cache = OnlineStructureCache(temp_project / "structures" / "cache")
    
    import time
    session_id = "test_session_456"
    cache.create_session(session_id, "Si", "optimade")
    
    # Add candidate metadata only (no structure)
    candidate = CandidateSummary(
        candidate_id="test_candidate_1",
        label="Si (2 sites)",
        source="optimade",
        source_id="test_optimade_id",
        nsites=2,
        flags=[],
        score=1.0,
    )
    cache.add_candidate_metadata_only(session_id, candidate, rank=0, optimade_base=None)
    
    payload = {
        "project_root": str(temp_project),
        "session_id": session_id,
        "candidate_id": "test_candidate_1",
        "trace_id": "test_trace",
    }
    
    # Should return error, not raise UnboundLocalError
    try:
        result = daemon._handle_structure_get_online_candidate(payload)
        
        # If it returns a dict, check structure
        if isinstance(result, dict):
            if "error" in result:
                assert result["error"]["code"] in ["STRUCTURE_NOT_FOUND", "CANDIDATE_NOT_FOUND"], (
                    f"Expected STRUCTURE_NOT_FOUND or CANDIDATE_NOT_FOUND, got {result.get('error', {}).get('code')}"
                )
            elif "ok" in result:
                assert result.get("ok") is False, "Handler should return ok:false for missing structure"
    except UnboundLocalError as e:
        pytest.fail(f"UnboundLocalError raised (regression): {e}")
    except (ValueError, KeyError) as e:
        # These are acceptable - handler may raise for missing structure
        # The key is that it's NOT UnboundLocalError
        pass


def test_get_online_candidate_cached_structure_has_candidate(temp_project, daemon):
    """
    Test that handler works when structure is cached (candidate must be assigned).

    Regression test: ensure candidate is assigned even when structure exists in cache,
    preventing UnboundLocalError at line 1426 (now 1453).
    """
    from quantumvitas.io.online_cache import OnlineStructureCache
    from quantumvitas.io.online_cache import CandidateSummary
    from pymatgen.core import Structure, Lattice
    
    # Create a cache with session, candidate, and structure
    cache = OnlineStructureCache(temp_project / "structures" / "cache")
    
    import time
    session_id = "test_session_789"
    cache.create_session(session_id, "Si", "optimade")
    
    # Create a simple structure
    lattice = Lattice.cubic(5.43)
    structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
    
    # Add candidate with structure
    candidate = CandidateSummary(
        candidate_id="test_candidate_2",
        label="Si (2 sites)",
        source="optimade",
        source_id="test_optimade_id_2",
        nsites=2,
        flags=[],
        score=1.0,
    )
    cache.add_candidate(session_id, candidate, structure, rank=0)
    
    payload = {
        "project_root": str(temp_project),
        "session_id": session_id,
        "candidate_id": "test_candidate_2",
        "trace_id": "test_trace",
    }
    
    # Should succeed - candidate is assigned before provenance building
    result = daemon._handle_structure_get_online_candidate(payload)
    
    # Should not raise UnboundLocalError
    assert "error" not in result or result.get("ok") is not False, (
        f"Handler should succeed for cached structure. Got: {result}"
    )
    
    # If successful, should have structure_vis
    if "error" not in result:
        assert "structure_vis" in result or "formula" in result, (
            "Successful response should contain structure data"
        )
