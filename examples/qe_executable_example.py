#!/usr/bin/env python3
"""
Example: Using QE executable detection and command building.

This example demonstrates how to:
1. Configure QE engine with installation path
2. Detect QE executables
3. Build commands for running calculations
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig


def main():
    """Main example function."""
    print("QE Executable Detection Example")
    print("=" * 60)
    
    # Example 1: Specify QE bin directory
    print("\n1. Using QE bin directory:")
    qe_bin = Path.home() / "src" / "q-e-qe-7.5" / "bin"
    print(f"   Path: {qe_bin}")
    
    config1 = EngineConfig(name="qe", executable_path=qe_bin)
    engine1 = QuantumEspressoEngine(config1)
    
    if engine1.detect_executable("pw.x"):
        pw_path = engine1.get_executable_path("pw.x")
        print(f"   ✓ Found pw.x at: {pw_path}")
    else:
        print("   ✗ pw.x not found")
    
    # Example 2: Specify QE root (automatically checks bin subdirectory)
    print("\n2. Using QE root directory:")
    qe_root = Path.home() / "src" / "q-e-qe-7.5"
    print(f"   Path: {qe_root}")
    
    config2 = EngineConfig(name="qe", executable_path=qe_root)
    engine2 = QuantumEspressoEngine(config2)
    
    if engine2.detect_executable("pw.x"):
        pw_path = engine2.get_executable_path("pw.x")
        print(f"   ✓ Found pw.x at: {pw_path}")
    else:
        print("   ✗ pw.x not found")
    
    # Example 3: Use system PATH
    print("\n3. Using system PATH:")
    config3 = EngineConfig(name="qe")
    engine3 = QuantumEspressoEngine(config3)
    
    if engine3.detect_executable("pw.x"):
        pw_path = engine3.get_executable_path("pw.x")
        print(f"   ✓ Found pw.x at: {pw_path}")
    else:
        print("   ✗ pw.x not found in PATH")
    
    # Example 4: Build command
    print("\n4. Building command for SCF calculation:")
    if engine1.detect_executable("pw.x"):
        input_file = Path("scf.in")
        working_dir = Path(".")
        
        command = engine1.build_command("scf", input_file, working_dir)
        print(f"   Command: {' '.join(command)}")
    
    # Example 5: Error handling
    print("\n5. Error handling (nonexistent path):")
    config4 = EngineConfig(name="qe", executable_path=Path("/nonexistent/path"))
    engine4 = QuantumEspressoEngine(config4)
    
    try:
        engine4.get_executable_path("pw.x")
        print("   ERROR: Should have raised FileNotFoundError")
    except FileNotFoundError as e:
        print(f"   ✓ Correctly raised FileNotFoundError")
        print(f"   Error: {str(e)[:80]}...")


if __name__ == "__main__":
    main()

