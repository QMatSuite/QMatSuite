"""
QE Tutorial Examples test suite.

Tests based on examples from the QuantumNerd YouTube tutorial.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "extended-tests"))

from tests.core.base import TestSuite, TestCase
from utils.download_tutorial_examples import ensure_tutorial_examples


class QETutorialExamplesSuite(TestSuite):
    """
    Test suite for QE tutorial examples.
    
    Examples are downloaded from:
    https://github.com/quantumNerd/Quantum-Espresso-Tutorial-2019-Projects
    """
    
    def __init__(self, description: str = ""):
        """Initialize tutorial examples test suite."""
        super().__init__(
            "QE Tutorial Examples",
            description or "Tests based on QuantumNerd tutorial examples"
        )
        self.tutorial_dir = None
    
    def discover_tests(self):
        """Discover test cases from tutorial examples."""
        # Ensure tutorial examples are downloaded
        self.tutorial_dir = ensure_tutorial_examples()
        
        if not self.tutorial_dir or not self.tutorial_dir.exists():
            return []
        
        # Find all .in files
        test_cases = []
        for input_file in self.tutorial_dir.rglob("*.in"):
            # Skip files in reference_output directories
            if "reference" in str(input_file):
                continue
            
            # Create test case
            test_case = QETutorialTestCase(
                name=input_file.stem,
                input_file=input_file,
                tutorial_dir=self.tutorial_dir
            )
            test_cases.append(test_case)
        
        return test_cases


class QETutorialTestCase(TestCase):
    """Test case for a single tutorial example."""
    
    def __init__(self, name: str, input_file: Path, tutorial_dir: Path):
        """Initialize tutorial test case."""
        super().__init__(name, input_file=str(input_file))
        self.input_file = input_file
        self.tutorial_dir = tutorial_dir
    
    def run(self):
        """Run the tutorial test."""
        from tests.core.base import TestResult, TestStatus
        
        try:
            # Parse input file
            from qmatsuite.io import QEInputParser
            qe_input = QEInputParser.parse_file(self.input_file)
            
            # Basic validation
            if not qe_input.namelists:
                return TestResult(
                    name=self.name,
                    status=TestStatus.FAILED,
                    error="No namelists found in input file"
                )
            
            return TestResult(
                name=self.name,
                status=TestStatus.PASSED,
                message="Input file parsed successfully"
            )
        except Exception as e:
            return TestResult(
                name=self.name,
                status=TestStatus.ERROR,
                error=str(e)
            )

