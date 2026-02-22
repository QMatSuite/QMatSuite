"""
Unit tests for candidate deduplication.

PR2: Tests for deduplication across multiple providers.
"""

import pytest

from qmatsuite.io.providers.optimade import (
    ProviderResult,
    Candidate,
    AggregatedCandidate,
    deduplicate_candidates,
    compute_dedup_key,
)


class TestDeduplication:
    """Test candidate deduplication."""
    
    def test_compute_dedup_key(self):
        """Test deduplication key computation."""
        candidate1 = Candidate(
            entry_id="mp-123",
            provider_id="mp",
            reduced_formula="Si",
            nsites=2,
            space_group_number=227,
        )
        candidate2 = Candidate(
            entry_id="cod-456",
            provider_id="cod",
            reduced_formula="Si",
            nsites=2,
            space_group_number=227,
        )
        candidate3 = Candidate(
            entry_id="mp-789",
            provider_id="mp",
            reduced_formula="Si",
            nsites=4,  # Different nsites
            space_group_number=227,
        )
        
        key1 = compute_dedup_key(candidate1)
        key2 = compute_dedup_key(candidate2)
        key3 = compute_dedup_key(candidate3)
        
        # Same formula, space group, nsites -> same key
        assert key1 == key2
        # Different nsites -> different key
        assert key1 != key3
    
    def test_deduplicate_same_structure(self):
        """Test deduplication of same structure from multiple providers."""
        # Same structure from MP and COD
        candidate_mp = Candidate(
            entry_id="mp-123",
            provider_id="mp",
            reduced_formula="Si",
            nsites=2,
            space_group_number=227,
        )
        candidate_cod = Candidate(
            entry_id="cod-456",
            provider_id="cod",
            reduced_formula="Si",
            nsites=2,
            space_group_number=227,
        )
        
        provider_results = [
            ProviderResult(provider_id="mp", provider_name="MP", candidates=[candidate_mp]),
            ProviderResult(provider_id="cod", provider_name="COD", candidates=[candidate_cod]),
        ]
        
        aggregated = deduplicate_candidates(provider_results)
        
        # Should have one aggregated candidate
        assert len(aggregated) == 1
        assert "mp" in aggregated[0].providers
        assert "cod" in aggregated[0].providers
        # COD should be primary (higher trust weight)
        assert aggregated[0].primary_candidate.provider_id == "cod"
    
    def test_deduplicate_different_structures(self):
        """Test that different structures are not deduplicated."""
        candidate1 = Candidate(
            entry_id="mp-123",
            provider_id="mp",
            reduced_formula="Si",
            nsites=2,
            space_group_number=227,
        )
        candidate2 = Candidate(
            entry_id="mp-456",
            provider_id="mp",
            reduced_formula="SiO2",
            nsites=3,
            space_group_number=182,
        )
        
        provider_results = [
            ProviderResult(provider_id="mp", provider_name="MP", candidates=[candidate1, candidate2]),
        ]
        
        aggregated = deduplicate_candidates(provider_results)
        
        # Should have two aggregated candidates (different structures)
        assert len(aggregated) == 2
    
    def test_deduplicate_ignore_errors(self):
        """Test that error/timeout results are ignored."""
        candidate = Candidate(
            entry_id="mp-123",
            provider_id="mp",
            reduced_formula="Si",
            nsites=2,
        )
        
        provider_results = [
            ProviderResult(provider_id="mp", provider_name="MP", candidates=[candidate]),
            ProviderResult(provider_id="error", provider_name="Error", error="HTTP 500"),
            ProviderResult(provider_id="timeout", provider_name="Timeout", timed_out=True),
        ]
        
        aggregated = deduplicate_candidates(provider_results)
        
        # Should only have one aggregated candidate (from successful provider)
        assert len(aggregated) == 1
        assert aggregated[0].primary_candidate.provider_id == "mp"
    
    def test_deduplicate_unknown_space_group(self):
        """Test deduplication with unknown space group (None -> 0)."""
        candidate1 = Candidate(
            entry_id="mp-123",
            provider_id="mp",
            reduced_formula="Si",
            nsites=2,
            space_group_number=None,
        )
        candidate2 = Candidate(
            entry_id="cod-456",
            provider_id="cod",
            reduced_formula="Si",
            nsites=2,
            space_group_number=None,
        )
        
        provider_results = [
            ProviderResult(provider_id="mp", provider_name="MP", candidates=[candidate1]),
            ProviderResult(provider_id="cod", provider_name="COD", candidates=[candidate2]),
        ]
        
        aggregated = deduplicate_candidates(provider_results)
        
        # Should deduplicate (both have space_group_number=None -> 0 in key)
        assert len(aggregated) == 1

