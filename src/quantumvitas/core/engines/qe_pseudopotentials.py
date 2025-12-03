"""
Quantum ESPRESSO pseudopotential management.

This module provides functions for downloading, locating, and managing
QE pseudopotential files.
"""

import urllib.request
import urllib.error
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Set, Dict

from quantumvitas.io import QEInputParser, QECardType


def download_pseudopotential(
    pp_name: str,
    pseudo_dir: Path,
    network_url: str = "https://pseudopotentials.quantum-espresso.org/upf_files/"
) -> bool:
    """
    Download pseudopotential file if not present.
    
    Args:
        pp_name: Pseudopotential filename
        pseudo_dir: Directory to store pseudopotentials
        network_url: URL base for downloading pseudopotentials
        
    Returns:
        True if file exists or was successfully downloaded
    """
    pseudo_dir.mkdir(parents=True, exist_ok=True)
    pp_path = pseudo_dir / pp_name
    
    # Check if already exists
    if pp_path.exists():
        return True
    
    # Try to download with timeout and retry
    download_url = network_url + pp_name
    max_retries = 3
    timeout = 30  # 30 seconds timeout per attempt
    
    for attempt in range(max_retries):
        try:
            print(f"  Downloading {pp_name}... (attempt {attempt + 1}/{max_retries})")
            # Use urlretrieve with timeout
            socket.setdefaulttimeout(timeout)
            urllib.request.urlretrieve(download_url, pp_path)
            socket.setdefaulttimeout(None)  # Reset timeout
            if pp_path.exists() and pp_path.stat().st_size > 0:
                print(f"  ✓ Successfully downloaded {pp_name}")
                return True
            else:
                print(f"  Warning: Downloaded file is empty or missing")
        except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout, Exception) as e:
            socket.setdefaulttimeout(None)  # Reset timeout
            if attempt < max_retries - 1:
                print(f"  Warning: Attempt {attempt + 1} failed: {e}, retrying...")
                time.sleep(2)  # Wait 2 seconds before retry
            else:
                print(f"  Error: Failed to download {pp_name} after {max_retries} attempts: {e}")
                return False
    
    return False


@dataclass
class PseudoManager:
    """
    Central manager for QE pseudopotentials.

    This class encapsulates the logic for:
    - Detecting required pseudopotentials from a QE input
    - Locating them in a base pseudo directory or optional test-suite dirs
    - Checking the quantumvitas global pseudo directory
    - Downloading missing files when allowed
    - Copying them into the project pseudo directory for self-containment

    The design ensures projects are self-contained:
    1. First check quantumvitas_root/pseudo (global cache)
    2. If found, copy to project/pseudo
    3. If not found, download to BOTH locations
    4. Always copy to working directory for execution

    Public API remains the function-level `ensure_pseudopotentials`; tests and
    engine code can continue to use it unchanged. This manager is primarily
    an internal structuring and caching helper.
    """

    base_pseudo_dir: Path  # Project's pseudo directory (project/pseudo)
    global_pseudo_dir: Optional[Path] = None  # Global quantumvitas pseudo directory
    test_suite_dir: Optional[Path] = None
    network_url: str = "https://pseudopotentials.quantum-espresso.org/upf_files/"
    _resolved_cache: Dict[str, Path] = field(default_factory=dict)

    def ensure_for_input(self, input_file: Path, working_dir: Path) -> bool:
        """Ensure all pseudopotentials for a given input file are available."""
        qe_input = QEInputParser.parse_file(input_file)
        atomic_species = qe_input.get_card(QECardType.ATOMIC_SPECIES)

        if not atomic_species or not atomic_species.data:
            return True  # No pseudopotentials needed

        required_pps: List[str] = []
        for line in atomic_species.data:
            if len(line) >= 3:
                required_pps.append(line[2])

        self.base_pseudo_dir.mkdir(parents=True, exist_ok=True)
        working_dir.mkdir(parents=True, exist_ok=True)

        all_available = True
        for pp_name in required_pps:
            if not self._ensure_single(pp_name, working_dir):
                all_available = False

        return all_available

    def _ensure_single(self, pp_name: str, working_dir: Path) -> bool:
        """
        Ensure a single pseudopotential is available and copied into working_dir.

        Resolution order:
        1. Check project pseudo_dir (base_pseudo_dir)
        2. Check global quantumvitas pseudo_dir, copy to project if found
        3. Check test-suite related directories
        4. Download, save to both global and project directories

        Uses a small in-memory cache to avoid repeating filesystem checks and
        downloads within the lifetime of this manager instance.
        """
        # Already resolved in this manager instance
        if pp_name in self._resolved_cache:
            src = self._resolved_cache[pp_name]
            (working_dir / pp_name).write_bytes(src.read_bytes())
            return True

        pseudo_dir = self.base_pseudo_dir
        pp_path = pseudo_dir / pp_name

        # 1) Check in project pseudo_dir (base_pseudo_dir)
        if pp_path.exists():
            (working_dir / pp_name).write_bytes(pp_path.read_bytes())
            self._resolved_cache[pp_name] = pp_path
            return True

        # 2) Check in global quantumvitas pseudo_dir
        if self.global_pseudo_dir and self.global_pseudo_dir.exists():
            global_pp = self.global_pseudo_dir / pp_name
            if global_pp.exists():
                # Copy to project pseudo_dir for self-containment
                pseudo_dir.mkdir(parents=True, exist_ok=True)
                pp_path.write_bytes(global_pp.read_bytes())
                (working_dir / pp_name).write_bytes(global_pp.read_bytes())
                self._resolved_cache[pp_name] = pp_path
                return True

        # 3) Check in test-suite related pseudo directories (if provided)
        if self.test_suite_dir:
            search_dirs = [
                self.test_suite_dir.parent / "pseudo",
                self.test_suite_dir / "pseudo",
                self.test_suite_dir.parent.parent / "pseudo",
            ]
            for search_dir in search_dirs:
                candidate = search_dir / pp_name
                if candidate.exists():
                    pseudo_dir.mkdir(parents=True, exist_ok=True)
                    pp_path.write_bytes(candidate.read_bytes())
                    (working_dir / pp_name).write_bytes(candidate.read_bytes())
                    self._resolved_cache[pp_name] = pp_path
                    return True

        # 4) Download into both global and project pseudo_dir
        download_target = pseudo_dir  # Download to project first
        if download_pseudopotential(pp_name, download_target, self.network_url):
            # Also copy to global pseudo_dir for future use
            if self.global_pseudo_dir and self.global_pseudo_dir != pseudo_dir:
                self.global_pseudo_dir.mkdir(parents=True, exist_ok=True)
                global_pp = self.global_pseudo_dir / pp_name
                if not global_pp.exists():
                    global_pp.write_bytes(pp_path.read_bytes())
            (working_dir / pp_name).write_bytes(pp_path.read_bytes())
            self._resolved_cache[pp_name] = pp_path
            return True

        print(f"  Error: Pseudopotential {pp_name} not found and download failed")
        return False


def _find_quantumvitas_root() -> Optional[Path]:
    """
    Find the quantumvitas root directory (containing src/quantumvitas).
    
    Returns None if not found.
    """
    # Try to find from this file's location
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "src" / "quantumvitas").exists():
            return current
        current = current.parent
    return None


def ensure_pseudopotentials(
    input_file: Path,
    working_dir: Path,
    pseudo_dir: Optional[Path] = None,
    test_suite_dir: Optional[Path] = None,
) -> bool:
    """
    Ensure all required pseudopotentials are available.

    This is the public API used by tests and engine code. It preserves the
    original behavior while delegating the internal logic to `PseudoManager`.
    
    Resolution order:
    1. Check pseudo_dir (project's pseudo directory)
    2. Check global quantumvitas_root/pseudo, copy to project if found
    3. Check test-suite directories
    4. Download to project (and global) if all else fails
    
    This ensures projects are self-contained with their own pseudo directory.
    """
    # Use provided pseudo_dir or try to find project_root/pseudo
    if pseudo_dir is None:
        current = Path(input_file).parent
        project_root = None
        while current != current.parent:
            if (current / "pseudo").exists() or (current / "project.qv.yml").exists():
                project_root = current
                break
            current = current.parent
        if project_root:
            pseudo_dir = project_root / "pseudo"
        else:
            pseudo_dir = working_dir / "pseudo"

    # Find global quantumvitas pseudo directory
    qv_root = _find_quantumvitas_root()
    global_pseudo_dir = qv_root / "pseudo" if qv_root else None

    manager = PseudoManager(
        base_pseudo_dir=pseudo_dir,
        global_pseudo_dir=global_pseudo_dir,
        test_suite_dir=test_suite_dir,
    )
    return manager.ensure_for_input(input_file, working_dir)

