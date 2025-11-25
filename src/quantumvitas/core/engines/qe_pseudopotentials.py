"""
Quantum ESPRESSO pseudopotential management.

This module provides functions for downloading, locating, and managing
QE pseudopotential files.
"""

import urllib.request
import urllib.error
import socket
import time
from pathlib import Path
from typing import Optional, List

from .qe_input import QEInputParser, QECardType


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


def ensure_pseudopotentials(
    input_file: Path,
    working_dir: Path,
    pseudo_dir: Optional[Path] = None,
    test_suite_dir: Optional[Path] = None
) -> bool:
    """
    Ensure all required pseudopotentials are available.
    
    This function:
    1. Parses the input file to find required pseudopotentials
    2. Checks if they exist in the specified pseudo_dir (usually project_root/pseudo)
    3. If not found, searches in test_suite_dir (if provided) as fallback
    4. If still not found, attempts to download from network
    5. Copies found/downloaded pseudopotentials to working_dir
    
    Args:
        input_file: QE input file path
        working_dir: Working directory for calculation (where pseudopotentials will be copied)
        pseudo_dir: Directory to search/store pseudopotentials (default: project_root/pseudo)
        test_suite_dir: Optional test suite directory (for finding pseudo directory as fallback)
        
    Returns:
        True if all pseudopotentials are available
    """
    # Parse input to find required pseudopotentials
    qe_input = QEInputParser.parse_file(input_file)
    atomic_species = qe_input.get_card(QECardType.ATOMIC_SPECIES)
    
    if not atomic_species or not atomic_species.data:
        return True  # No pseudopotentials needed
    
    # Use provided pseudo_dir or try to find project_root/pseudo
    if pseudo_dir is None:
        # Try to find project root
        current = Path(input_file).parent
        project_root = None
        while current != current.parent:
            if (current / "pseudo").exists() or (current / "src" / "quantumvitas").exists():
                project_root = current
                break
            current = current.parent
        if project_root:
            pseudo_dir = project_root / "pseudo"
        else:
            pseudo_dir = working_dir / "pseudo"
    pseudo_dir.mkdir(parents=True, exist_ok=True)
    
    # Network URL for downloading
    network_url = "https://pseudopotentials.quantum-espresso.org/upf_files/"
    
    # Collect all required pseudopotentials
    required_pps: List[str] = []
    for line in atomic_species.data:
        if len(line) >= 3:
            required_pps.append(line[2])  # Pseudopotential filename
    
    # Check and download each pseudopotential
    all_available = True
    for pp_name in required_pps:
        found = False
        
        # First check in specified pseudo_dir
        pp_path = pseudo_dir / pp_name
        if pp_path.exists():
            # Copy to working directory
            (working_dir / pp_name).write_bytes(pp_path.read_bytes())
            found = True
        else:
            # Check in test suite directory structure (if available)
            if test_suite_dir:
                search_dirs = [
                    test_suite_dir.parent / "pseudo",
                    test_suite_dir / "pseudo",
                    test_suite_dir.parent.parent / "pseudo",
                ]
                
                for search_dir in search_dirs:
                    pp_file = search_dir / pp_name
                    if pp_file.exists():
                        # Copy to pseudo_dir first, then to working directory
                        pp_path.write_bytes(pp_file.read_bytes())
                        (working_dir / pp_name).write_bytes(pp_file.read_bytes())
                        found = True
                        break
            
            # If not found, try downloading to pseudo_dir
            if not found:
                if download_pseudopotential(pp_name, pseudo_dir, network_url):
                    # Copy to working directory
                    (working_dir / pp_name).write_bytes(pp_path.read_bytes())
                    found = True
        
        if not found:
            print(f"  Error: Pseudopotential {pp_name} not found and download failed")
            all_available = False
    
    return all_available

