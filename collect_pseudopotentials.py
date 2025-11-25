#!/usr/bin/env python3
"""
Collect pseudopotentials from QE test-suite or download from network.
All pseudopotentials will be stored in project_root/pseudo/
"""
import sys
from pathlib import Path
import shutil
import urllib.request
import urllib.error
import socket

# Project root
project_root = Path(__file__).parent
pseudo_dir = project_root / "pseudo"
pseudo_dir.mkdir(exist_ok=True)

# Required pseudopotentials from test files
required_pps = {
    # ph_1d
    "H.pz-vbc.UPF": None,
    "C.pz-rrkjus.UPF": None,
    # ph_2d
    "B-PBE.upf": None,
    "N-PBE.upf": None,
    # 4_Si_DOS, 7_Si_bandStructure
    "Si.pbe-n-rrkjus_psl.1.0.0.UPF": None,
    # pw_scf, pw_plugins, pw_twochem
    "Si.pz-vbc.UPF": None,
    # pw_metal
    "Al.pz-vbc.UPF": None,
    # pw_uspp
    "H.pbe-rrkjus.UPF": None,
    "C.pbe-rrkjus.UPF": None,
    # pw_atom
    "O.pz-rrkjus.UPF": None,
}

# Try to find QE test-suite
qe_test_suite_dirs = [
    Path.home() / "src" / "q-e-qe-7.5" / "test-suite",
    Path("/usr/share/quantum-espresso/test-suite"),
    Path("/opt/quantum-espresso/test-suite"),
]

qe_pseudo_dirs = []
for test_suite_dir in qe_test_suite_dirs:
    if test_suite_dir.exists():
        possible_pseudo = [
            test_suite_dir.parent / "pseudo",
            test_suite_dir / "pseudo",
            test_suite_dir.parent.parent / "pseudo",
        ]
        for pp_dir in possible_pseudo:
            if pp_dir.exists() and pp_dir.is_dir():
                qe_pseudo_dirs.append(pp_dir)
                break

print(f"Found {len(qe_pseudo_dirs)} QE pseudo directories:")
for d in qe_pseudo_dirs:
    print(f"  - {d}")

# Network URL
network_url = "https://pseudopotentials.quantum-espresso.org/upf_files/"

def download_pp(pp_name, target_path):
    """Download pseudopotential from network."""
    download_url = network_url + pp_name
    try:
        print(f"  Downloading {pp_name}...")
        socket.setdefaulttimeout(30)
        urllib.request.urlretrieve(download_url, target_path)
        socket.setdefaulttimeout(None)
        if target_path.exists() and target_path.stat().st_size > 0:
            print(f"  ✓ Downloaded {pp_name}")
            return True
    except Exception as e:
        socket.setdefaulttimeout(None)
        print(f"  ✗ Download failed: {e}")
    return False

# Collect pseudopotentials
for pp_name in required_pps:
    target_path = pseudo_dir / pp_name
    
    if target_path.exists():
        print(f"✓ {pp_name} already exists")
        continue
    
    found = False
    
    # First try QE test-suite
    for qe_pseudo_dir in qe_pseudo_dirs:
        source_path = qe_pseudo_dir / pp_name
        if source_path.exists():
            print(f"✓ Copying {pp_name} from {qe_pseudo_dir}")
            shutil.copy2(source_path, target_path)
            found = True
            break
    
    # If not found, try downloading
    if not found:
        if download_pp(pp_name, target_path):
            found = True
    
    if not found:
        print(f"✗ Failed to obtain {pp_name}")

print(f"\nPseudopotentials collected in: {pseudo_dir}")
print(f"Total files: {len(list(pseudo_dir.glob('*')))}")
