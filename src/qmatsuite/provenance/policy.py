"""
Artifact capture policies for engines.

Each engine defines its own ArtifactPolicy to control which files
are captured into the CAS after step execution.

Per Law P9: Policies are defined in recipes, applied by Runner.
Scanner implementations are ONLY in provenance/scanner.py.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import List, Literal, Tuple, Optional


@dataclass(frozen=True)
class ArtifactPolicy:
    """
    Engine-specific artifact capture policy.

    Defined in recipe.py, applied by Runner's ArtifactScanner.

    Attributes:
        mode: "blacklist" (capture all except listed) or "whitelist" (capture only listed)
        blacklist_dirs: Directories to exclude (relative to calc/raw/)
        blacklist_patterns: File patterns to exclude (glob syntax)
        whitelist_patterns: File patterns to include (whitelist mode)
        force_capture_patterns: Always capture these (overrides blacklist)
        tier3_patterns: Large files that get rolling-window retention
        tier2_max_size: Max size for Tier-2 files (-1 = no limit)
        tier3_max_size: Max size for Tier-3 files (-1 = no limit)
    """

    mode: Literal["blacklist", "whitelist"] = "blacklist"

    # Blacklist mode: capture everything EXCEPT these
    blacklist_dirs: Tuple[str, ...] = field(default_factory=tuple)
    blacklist_patterns: Tuple[str, ...] = field(default_factory=tuple)

    # Whitelist mode: capture ONLY these (plus force_capture_patterns)
    whitelist_patterns: Tuple[str, ...] = field(default_factory=tuple)

    # Always capture these (overrides blacklist)
    force_capture_patterns: Tuple[str, ...] = field(default_factory=tuple)

    # Tier-3: large files that get rolling-window retention
    tier3_patterns: Tuple[str, ...] = field(default_factory=tuple)

    # Size limits
    tier2_max_size: int = -1  # -1 = no limit
    tier3_max_size: int = -1  # -1 = no limit

    def should_capture(
        self, rel_path: str, size_bytes: int
    ) -> Tuple[bool, int, Optional[str]]:
        """
        Determine if a file should be captured.

        Args:
            rel_path: Relative path from calc/raw/
            size_bytes: File size in bytes

        Returns:
            Tuple of (should_capture, tier, skip_reason)
            - should_capture: True if file should be stored in CAS
            - tier: Storage tier (2 or 3)
            - skip_reason: Reason for skipping (if not captured)
        """
        # Check if in blacklisted directory
        for dir_pattern in self.blacklist_dirs:
            # Handle both "dir/" and "dir" patterns
            normalized = dir_pattern.rstrip("/")
            if rel_path.startswith(normalized + "/") or rel_path == normalized:
                # Check if force-captured
                if self._matches_any(rel_path, self.force_capture_patterns):
                    return (True, 2, None)
                return (False, 0, f"blacklisted_dir:{dir_pattern}")

        # Determine tier
        tier = 3 if self._matches_any(rel_path, self.tier3_patterns) else 2

        # Check size limits
        if tier == 2 and self.tier2_max_size > 0 and size_bytes > self.tier2_max_size:
            return (False, tier, f"exceeds_tier2_max:{self.tier2_max_size}")
        if tier == 3 and self.tier3_max_size > 0 and size_bytes > self.tier3_max_size:
            return (False, tier, f"exceeds_tier3_max:{self.tier3_max_size}")

        # Force capture patterns always win
        if self._matches_any(rel_path, self.force_capture_patterns):
            return (True, tier, None)

        if self.mode == "blacklist":
            # Blacklist mode: capture unless blacklisted
            if self._matches_any(rel_path, self.blacklist_patterns):
                return (False, tier, "blacklisted_pattern")
            return (True, tier, None)

        else:
            # Whitelist mode: only capture if whitelisted
            if self._matches_any(rel_path, self.whitelist_patterns):
                return (True, tier, None)
            return (False, tier, "not_whitelisted")

    def _matches_any(self, path: str, patterns: Tuple[str, ...]) -> bool:
        """Check if path matches any pattern."""
        for pattern in patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
            # Also check basename for patterns without /
            if "/" not in pattern and fnmatch.fnmatch(path.split("/")[-1], pattern):
                return True
        return False


# =============================================================================
# Default policies for common engines
# =============================================================================


DEFAULT_POLICY = ArtifactPolicy(
    mode="blacklist",
    force_capture_patterns=("*.out", "*.log", "*.xml", "*.json"),
)


QE_POLICY = ArtifactPolicy(
    mode="blacklist",
    blacklist_dirs=("outdir/", "tmp/"),
    blacklist_patterns=("*.wfc*", "*.hub*", "*.mix*"),
    force_capture_patterns=("*.out", "*.xml", "*.json", "*.log"),
    tier3_patterns=("*.save/",),
)


VASP_POLICY = ArtifactPolicy(
    mode="blacklist",
    force_capture_patterns=("*.out", "OUTCAR", "vasprun.xml", "*.log"),
    tier3_patterns=("WAVECAR", "CHGCAR"),
)


ORCA_POLICY = ArtifactPolicy(
    mode="blacklist",
    blacklist_patterns=("*.tmp", "*.gbw.bak*"),
    force_capture_patterns=("*.out", "*.log", "*.json"),
    tier3_patterns=("*.gbw",),
)


GAUSSIAN_POLICY = ArtifactPolicy(
    mode="blacklist",
    blacklist_patterns=("*.rwf",),
    force_capture_patterns=("*.out", "*.log"),
    tier3_patterns=("*.chk",),
)


XTB_POLICY = ArtifactPolicy(
    mode="blacklist",
    force_capture_patterns=("*.out", "*.log", "*.json"),
)


LAMMPS_POLICY = ArtifactPolicy(
    mode="blacklist",
    force_capture_patterns=("*.out", "log.*", "*.log"),
    tier3_patterns=("*.restart",),
)
