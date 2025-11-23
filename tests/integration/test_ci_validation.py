"""
Validation script to ensure CI tests work correctly.

This can be run without pytest to verify test logic.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

def test_imports():
    """Test that all required imports work."""
    from quantumvitas.core.engines.qe_input import QEInputParser, QEInputGenerator
    print("✅ Core imports work")

def test_basic_parsing():
    """Test basic parsing (CI-friendly)."""
    from quantumvitas.core.engines.qe_input import QEInputParser
    
    content = """&control
    calculation = 'scf'
    prefix = 'test'
/
&system
    ibrav = 0
    nat = 2
    ntyp = 1
    ecutwfc = 30.0
/
"""
    qe_input = QEInputParser.parse_string(content)
    assert qe_input.get_namelist("control") is not None
    assert qe_input.get_namelist("system") is not None
    print("✅ Basic parsing works")

def test_stats_file():
    """Test that stats file can be loaded."""
    stats_file = Path(__file__).parent.parent.parent / "extended-tests" / "pw_test_stats.json"
    if stats_file.exists():
        import json
        with open(stats_file) as f:
            data = json.load(f)
        selected = data.get("selected_ci_tests", [])
        if selected:
            print(f"✅ Stats file loaded: {len(selected)} tests")
            print(f"   First test: {selected[0]['category']}/{selected[0]['test_file']}")
        else:
            print("⚠️  Stats file exists but no selected tests")
            # This is OK - file exists but no tests selected yet
    else:
        print("⚠️  Stats file not found (QE tests will skip in CI)")
        # This is OK for CI - file may not exist in all environments

def main():
    """Run all validation tests."""
    print("=" * 60)
    print("CI Test Validation")
    print("=" * 60)
    print()
    
    results = []
    all_passed = True
    
    # Test imports
    try:
        test_imports()
        results.append(("Imports", True))
    except Exception as e:
        print(f"❌ Import error: {e}")
        results.append(("Imports", False))
        all_passed = False
    
    # Test basic parsing
    try:
        test_basic_parsing()
        results.append(("Basic Parsing", True))
    except Exception as e:
        print(f"❌ Parsing error: {e}")
        results.append(("Basic Parsing", False))
        all_passed = False
    
    # Test stats file
    try:
        test_stats_file()
        results.append(("Stats File", True))
    except Exception as e:
        print(f"❌ Stats file error: {e}")
        results.append(("Stats File", False))
        all_passed = False
    
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name:20s}: {status}")
    
    print()
    if all_passed:
        print("✅ All validations passed - CI tests should work")
        return 0
    else:
        print("❌ Some validations failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

