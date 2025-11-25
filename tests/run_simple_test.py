#!/usr/bin/env python3
"""
Simple test script to verify QE input parsing and generation works.

This can be run without pytest to quickly verify functionality.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from quantumvitas.core.engines.qe_input import QEInputParser, QEInputGenerator


def test_simple_parse_generate():
    """Test simple parse and generate."""
    print("Testing simple QE input parsing and generation...")
    
    content = """&control
    calculation = 'scf'
    prefix = 'si'
    pseudo_dir = '/path/to/pseudo'
/
&system
    ibrav=2, celldm(1) =10.20, 
    nat=2, ntyp=1,
    ecutwfc=20.0
/
&electrons
/
ATOMIC_SPECIES
 Si  28.086  Si.pz-vbc.UPF
ATOMIC_POSITIONS (alat)
 Si 0.00 0.00 0.00
 Si 0.25 0.25 0.25
K_POINTS (automatic)
  6 6 6 0 0 0
"""
    
    # Parse
    print("1. Parsing input...")
    qe_input = QEInputParser.parse_string(content)
    print(f"   ✓ Parsed {len(qe_input.namelists)} namelists")
    print(f"   ✓ Parsed {len(qe_input.cards)} cards")
    
    # Check namelists
    control = qe_input.get_namelist('control')
    assert control is not None, "Control namelist not found"
    assert control.get('calculation') == 'scf', "Calculation type mismatch"
    print("   ✓ Control namelist parsed correctly")
    
    system = qe_input.get_namelist('system')
    assert system is not None, "System namelist not found"
    assert system.get('nat') == 2, "Number of atoms mismatch"
    print("   ✓ System namelist parsed correctly")
    
    # Generate
    print("2. Generating output...")
    generated = QEInputGenerator.generate(qe_input)
    print(f"   ✓ Generated {len(generated.splitlines())} lines")
    
    # Verify key content
    assert '&control' in generated, "Control namelist missing in output"
    assert "calculation = 'scf'" in generated, "Calculation parameter missing"
    assert 'ATOMIC_SPECIES' in generated, "ATOMIC_SPECIES card missing"
    print("   ✓ Generated file contains expected content")
    
    # Roundtrip test
    print("3. Testing roundtrip conversion...")
    qe_input2 = QEInputParser.parse_string(generated)
    control2 = qe_input2.get_namelist('control')
    assert control2.get('calculation') == 'scf', "Roundtrip failed"
    print("   ✓ Roundtrip conversion successful")
    
    print("\n✅ All tests passed!")


def test_real_example():
    """Test with a real example file if available."""
    # Use local test file instead of downloading
    from pathlib import Path
    project_root = Path(__file__).parent.parent
    # Try local test file first
    example_file = project_root / "tests" / "integration" / "ci_test_data" / "pw_scf" / "scf-cg.in"
    
    # Fallback: check if tutorial examples already downloaded (don't trigger download)
    if not example_file.exists():
        tutorial_dir = project_root / "temp" / "downloads" / "qe_tutorial_examples"
        if tutorial_dir.exists():
            example_file = tutorial_dir / "0_Si_scf" / "si.scf.in"
    
    if not example_file.exists():
        print("\n⚠️  Real example file not found, skipping real example test")
        return
    
    print("\nTesting with real example file...")
    print(f"   File: {example_file}")
    
    # Parse
    qe_input = QEInputParser.parse_file(example_file)
    print(f"   ✓ Parsed {len(qe_input.namelists)} namelists")
    print(f"   ✓ Parsed {len(qe_input.cards)} cards")
    
    # Generate
    output_file = Path(__file__).parent / "test_output.in"
    QEInputGenerator.write_file(qe_input, output_file)
    print(f"   ✓ Generated output file: {output_file}")
    
    # Verify roundtrip
    qe_input2 = QEInputParser.parse_file(output_file)
    control1 = qe_input.get_namelist('control')
    control2 = qe_input2.get_namelist('control')
    if control1 and control2:
        assert control1.get('calculation') == control2.get('calculation')
        print("   ✓ Roundtrip conversion successful")
    
    # Cleanup
    output_file.unlink()
    print("   ✓ Cleaned up test output file")


if __name__ == "__main__":
    try:
        test_simple_parse_generate()
        test_real_example()
        print("\n🎉 All tests completed successfully!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

