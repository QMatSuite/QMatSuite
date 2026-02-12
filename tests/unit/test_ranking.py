"""
Unit tests for candidate ranking.

PR2: Tests for ranking/scoring of candidates.
"""

import pytest

from quantumvitas.io.providers.optimade import (
    ProviderConfig,
    Candidate,
    AggregatedCandidate,
    score_candidate,
    rank_candidates,
)


class TestRanking:
    """Test candidate ranking and scoring."""
    
    def test_score_provider_trust_weight(self):
        """Test that provider trust weight affects score."""
        provider_cod = ProviderConfig(provider_key="cod", name="COD", base_url="https://cod.example.com", enabled=True, trust_weight=1.0)
        provider_mp = ProviderConfig(provider_key="mp", name="MP", base_url="https://mp.example.com", enabled=True, trust_weight=0.9)
        
        candidate = Candidate(
            entry_id="test-123",
            provider_id="cod",
            reduced_formula="Si",
            nsites=2,
        )
        
        score_cod = score_candidate(candidate, provider_cod, "Si")
        score_mp = score_candidate(candidate, provider_mp, "Si")
        
        # COD should score higher (experimental > computed)
        assert score_cod > score_mp
    
    def test_score_formula_match(self):
        """Test that exact formula match increases score."""
        provider = ProviderConfig(provider_key="test", name="Test", base_url="https://test.example.com", enabled=True, trust_weight=0.8)
        
        candidate_match = Candidate(
            entry_id="test-123",
            provider_id="test",
            reduced_formula="Si",
            nsites=2,
        )
        candidate_mismatch = Candidate(
            entry_id="test-456",
            provider_id="test",
            reduced_formula="SiO2",
            nsites=3,
        )
        
        score_match = score_candidate(candidate_match, provider, "Si")
        score_mismatch = score_candidate(candidate_mismatch, provider, "Si")
        
        # Exact match should score higher
        assert score_match > score_mismatch
    
    def test_score_partial_occupancy_penalty(self):
        """Test that partial occupancy reduces score."""
        provider = ProviderConfig(provider_key="test", name="Test", base_url="https://test.example.com", enabled=True, trust_weight=0.8)
        
        candidate_normal = Candidate(
            entry_id="test-123",
            provider_id="test",
            reduced_formula="Si",
            nsites=2,
            has_partial_occupancy=False,
        )
        candidate_partial = Candidate(
            entry_id="test-456",
            provider_id="test",
            reduced_formula="Si",
            nsites=2,
            has_partial_occupancy=True,
        )
        
        score_normal = score_candidate(candidate_normal, provider, "Si")
        score_partial = score_candidate(candidate_partial, provider, "Si")
        
        # Partial occupancy should score lower
        assert score_normal > score_partial
    
    def test_score_size_bonus(self):
        """Test that small structures get bonus points."""
        provider = ProviderConfig(provider_key="test", name="Test", base_url="https://test.example.com", enabled=True, trust_weight=0.8)
        
        candidate_small = Candidate(
            entry_id="test-123",
            provider_id="test",
            reduced_formula="Si",
            nsites=10,  # Small
        )
        candidate_medium = Candidate(
            entry_id="test-456",
            provider_id="test",
            reduced_formula="Si",
            nsites=100,  # Medium
        )
        candidate_large = Candidate(
            entry_id="test-789",
            provider_id="test",
            reduced_formula="Si",
            nsites=300,  # Large (>200)
        )
        
        score_small = score_candidate(candidate_small, provider, "Si")
        score_medium = score_candidate(candidate_medium, provider, "Si")
        score_large = score_candidate(candidate_large, provider, "Si")
        
        # Small structures should score higher
        assert score_small > score_medium
        assert score_medium > score_large
    
    def test_score_space_group_bonus(self):
        """Test that known space group increases score."""
        provider = ProviderConfig(provider_key="test", name="Test", base_url="https://test.example.com", enabled=True, trust_weight=0.8)
        
        candidate_known = Candidate(
            entry_id="test-123",
            provider_id="test",
            reduced_formula="Si",
            nsites=2,
            space_group_number=227,
        )
        candidate_unknown = Candidate(
            entry_id="test-456",
            provider_id="test",
            reduced_formula="Si",
            nsites=2,
            space_group_number=None,
        )
        
        score_known = score_candidate(candidate_known, provider, "Si")
        score_unknown = score_candidate(candidate_unknown, provider, "Si")
        
        # Known space group should score slightly higher
        assert score_known > score_unknown
    
    def test_rank_candidates(self):
        """Test ranking of aggregated candidates."""
        providers = [
            ProviderConfig(provider_key="cod", name="COD", base_url="https://cod.example.com", enabled=True, trust_weight=1.0),
            ProviderConfig(provider_key="mp", name="MP", base_url="https://mp.example.com", enabled=True, trust_weight=0.9),
        ]
        
        # Create candidates with different scores
        candidate_high = Candidate(
            entry_id="cod-123",
            provider_id="cod",
            reduced_formula="Si",
            nsites=2,
            space_group_number=227,
        )
        candidate_low = Candidate(
            entry_id="mp-456",
            provider_id="mp",
            reduced_formula="Si",
            nsites=100,  # Large, should score lower
        )
        
        aggregated = [
            AggregatedCandidate(primary_candidate=candidate_low, providers=["mp"]),
            AggregatedCandidate(primary_candidate=candidate_high, providers=["cod"]),
        ]
        
        ranked = rank_candidates(aggregated, "Si", providers)
        
        # Higher-scoring candidate should be first
        assert ranked[0].primary_candidate.provider_id == "cod"
        assert ranked[0].primary_candidate.score > ranked[1].primary_candidate.score
    
    def test_rank_candidates_tie_breaker(self):
        """Test ranking with tie-breaking (nsites, then provider)."""
        providers = [
            ProviderConfig(provider_key="mp", name="MP", base_url="https://mp.example.com", enabled=True, trust_weight=0.9),
        ]
        
        # Same score, different nsites
        candidate_small = Candidate(
            entry_id="mp-123",
            provider_id="mp",
            reduced_formula="Si",
            nsites=10,
        )
        candidate_large = Candidate(
            entry_id="mp-456",
            provider_id="mp",
            reduced_formula="Si",
            nsites=100,
        )
        
        aggregated = [
            AggregatedCandidate(primary_candidate=candidate_large, providers=["mp"]),
            AggregatedCandidate(primary_candidate=candidate_small, providers=["mp"]),
        ]
        
        ranked = rank_candidates(aggregated, "Si", providers)
        
        # Smaller nsites should come first (tie-breaker)
        assert ranked[0].primary_candidate.nsites < ranked[1].primary_candidate.nsites

