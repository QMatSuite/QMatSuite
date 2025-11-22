#!/usr/bin/env python3
"""
Check which QE modules are available in the installation.

This script checks which executables exist and reports which tests can be run.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig


def check_module(engine, executable_name, module_name):
    """Check if a module executable exists."""
    if engine.detect_executable(executable_name):
        exe_path = engine.get_executable_path(executable_name)
        return True, exe_path
    return False, None


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Check which QE modules are available"
    )
    parser.add_argument(
        "--qe-path",
        type=Path,
        default=Path.home() / "src" / "q-e-qe-7.5" / "bin",
        help="Path to QE bin directory"
    )
    
    args = parser.parse_args()
    
    # Setup engine
    config = EngineConfig(name="qe", executable_path=args.qe_path)
    engine = QuantumEspressoEngine(config)
    
    print("=" * 70)
    print("QE Module Availability Check")
    print("=" * 70)
    print(f"QE bin directory: {args.qe_path}")
    print()
    
    # Check all modules
    modules = {
        "pw": ["pw.x"],
        "ph": ["pw.x", "ph.x"],
        "pp": ["pw.x", "pp.x"],
        "cp": ["cp.x"],
        "hp": ["pw.x", "hp.x"],
        "epw": ["pw.x", "ph.x", "epw.x"],
        "kcw": ["pw.x", "kcw.x"],
        "tddfpt": ["pw.x", "turbo_lanczos.x", "turbo_spectrum.x", "turbo_eels.x"],
        "zg": ["pw.x", "ZG.x"],
        "all_currents": ["pw.x", "all_currents.x"],
        "xsd_pw": []  # No executables needed
    }
    
    available = []
    partially_available = []
    unavailable = []
    
    for module_name, executables in modules.items():
        if not executables:
            # No executables needed
            available.append((module_name, []))
            continue
        
        found = []
        missing = []
        
        for exe in executables:
            exists, path = check_module(engine, exe, module_name)
            if exists:
                found.append(exe)
            else:
                missing.append(exe)
        
        if len(missing) == 0:
            available.append((module_name, found))
        elif len(found) > 0:
            partially_available.append((module_name, found, missing))
        else:
            unavailable.append((module_name, missing))
    
    # Print results
    print("✅ Fully Available Modules:")
    for module_name, execs in available:
        if execs:
            print(f"   {module_name:15s} - {', '.join(execs)}")
        else:
            print(f"   {module_name:15s} - (no executables needed)")
    
    print()
    print("⚠️  Partially Available Modules:")
    for module_name, found, missing in partially_available:
        print(f"   {module_name:15s} - Found: {', '.join(found)}")
        print(f"   {'':15s}   Missing: {', '.join(missing)}")
    
    print()
    print("❌ Unavailable Modules:")
    for module_name, missing in unavailable:
        print(f"   {module_name:15s} - Missing: {', '.join(missing)}")
    
    print()
    print("=" * 70)
    print(f"Summary: {len(available)} available, {len(partially_available)} partial, {len(unavailable)} unavailable")
    print("=" * 70)


if __name__ == "__main__":
    main()

