"""
Test cases for QE test suite (extended tests).
"""

import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "extended-tests"))

from tests.core.base import TestCase, TestResult, TestStatus
from tests.core.qe_test_utils import run_test_category_workflow


class QECategoryTestCase(TestCase):
    """
    Test case for a QE test category.
    
    Runs all tests in a single category from the QE test-suite.
    """
    
    def __init__(
        self,
        name: str,
        category: str,
        test_files: List[Tuple[str, str]],
        test_suite_dir: Path,
        qe_home: Path,
        executable_map: Dict[str, str] = None,
        timeout: int = 60
    ):
        """
        Initialize QE category test case.
        
        Args:
            name: Test case name
            category: Category name (e.g., "pw_atom")
            test_files: List of (input_file, args) tuples
            test_suite_dir: Test suite root directory
            qe_home: QE home directory (contains bin/ and test-suite/)
            executable_map: Maps step args to executable names
            timeout: Timeout per test
        """
        super().__init__(name, category=category, test_files=test_files)
        self.category = category
        self.test_files = test_files
        self.test_suite_dir = test_suite_dir
        self.qe_home = qe_home
        self.executable_map = executable_map or {"default": "pw.x"}
        self.timeout = timeout
    
    def run(self) -> TestResult:
        """Run the test category."""
        from quantumvitas.core.engines.qe import QuantumEspressoEngine
        from quantumvitas.core.engines.base import EngineConfig
        
        try:
            # Setup engine
            config = EngineConfig(name="qe", executable_path=self.qe_home)
            engine = QuantumEspressoEngine(config)
            
            # Run tests in category using centralized calculation system
            results = run_test_category_workflow(
                self.category,
                self.test_files,
                self.test_suite_dir,
                engine,
                self.executable_map,
                self.timeout
            )
            
            # Determine overall status
            all_passed = all(r.get("success", False) for r in results)
            passed_count = sum(1 for r in results if r.get("success", False))
            total_count = len(results)
            
            if all_passed:
                status = TestStatus.PASSED
                message = f"All {total_count} tests passed"
            else:
                status = TestStatus.FAILED
                message = f"{passed_count}/{total_count} tests passed"
            
            return TestResult(
                name=self.name,
                status=status,
                message=message,
                details={"results": results}
            )
            
        except Exception as e:
            return TestResult(
                name=self.name,
                status=TestStatus.ERROR,
                error=str(e)
            )


class QESingleTestCase(TestCase):
    """
    Test case for a single QE test file.
    
    Runs a single input file test.
    """
    
    def __init__(
        self,
        name: str,
        input_file: Path,
        qe_home: Path,
        executable_name: str = "pw.x",
        timeout: int = 60
    ):
        """
        Initialize single QE test case.
        
        Args:
            name: Test case name
            input_file: Input file path
            qe_home: QE home directory (contains bin/ and test-suite/)
            executable_name: QE executable to run
            timeout: Timeout in seconds
        """
        super().__init__(name, input_file=str(input_file))
        self.input_file = input_file
        self.qe_home = qe_home
        self.executable_name = executable_name
        self.timeout = timeout
    
    def run(self) -> TestResult:
        """Run the single test."""
        from quantumvitas.core.engines.qe import QuantumEspressoEngine
        from quantumvitas.core.engines.base import EngineConfig
        from tests.core.qe_step_runner import run_and_verify_step
        import tempfile
        
        try:
            config = EngineConfig(name="qe", executable_path=self.qe_home)
            engine = QuantumEspressoEngine(config)
            
            working_dir = Path(tempfile.mkdtemp(prefix="qe_test_"))
            step_result, success, message = run_and_verify_step(
                input_file=self.input_file,
                qe_engine=engine,
                working_dir=working_dir,
                reference_file=None,
                category=None,
                timeout=self.timeout,
                step_type=None  # Auto-detect from input
            )
            
            if success:
                status = TestStatus.PASSED
                msg = message or "Test passed"
            else:
                status = TestStatus.FAILED
                msg = step_result.error or message or "Test failed"
            
            result = {
                "success": success,
                "run_success": step_result.success,
                "verify_success": success,
                "output_file": str(step_result.output_file) if step_result.output_file else None,
                "time_taken": step_result.time_taken or 0,
                "message": msg,
                "error": step_result.error
            }
            
            return TestResult(
                name=self.name,
                status=status,
                message=msg,
                details=result
            )
            
        except Exception as e:
            return TestResult(
                name=self.name,
                status=TestStatus.ERROR,
                error=str(e)
            )

