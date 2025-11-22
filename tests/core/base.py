"""
Base classes for test framework.

Defines the interface for different types of test suites.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import time


class TestStatus(Enum):
    """Test execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestResult:
    """Result of a single test execution."""
    name: str
    status: TestStatus
    message: str = ""
    error: Optional[str] = None
    time_taken: float = 0.0
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}
    
    @property
    def success(self) -> bool:
        """Check if test passed."""
        return self.status == TestStatus.PASSED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "error": self.error,
            "time_taken": self.time_taken,
            "success": self.success,
            "details": self.details
        }


class TestCase(ABC):
    """
    Base class for a single test case.
    
    Each test case represents one unit of testing (e.g., one input file,
    one test category, etc.).
    """
    
    def __init__(self, name: str, **kwargs):
        """
        Initialize test case.
        
        Args:
            name: Test case name/identifier
            **kwargs: Additional test-specific parameters
        """
        self.name = name
        self.params = kwargs
        self.result: Optional[TestResult] = None
    
    @abstractmethod
    def run(self) -> TestResult:
        """
        Execute the test case.
        
        Returns:
            TestResult object with test outcome
        """
        pass
    
    def setup(self) -> None:
        """Setup before test execution (optional)."""
        pass
    
    def teardown(self) -> None:
        """Cleanup after test execution (optional)."""
        pass


class TestSuite(ABC):
    """
    Base class for a test suite.
    
    A test suite is a collection of related tests (e.g., all tests for a specific
    module, all bidirectional conversion tests, etc.).
    """
    
    def __init__(self, name: str, description: str = ""):
        """
        Initialize test suite.
        
        Args:
            name: Suite name
            description: Suite description
        """
        self.name = name
        self.description = description
        self.test_cases: List[TestCase] = []
        self.results: List[TestResult] = []
    
    @abstractmethod
    def discover_tests(self) -> List[TestCase]:
        """
        Discover and create test cases for this suite.
        
        Returns:
            List of TestCase objects
        """
        pass
    
    def add_test(self, test_case: TestCase) -> None:
        """Add a test case to the suite."""
        self.test_cases.append(test_case)
    
    def run_all(self, timeout: Optional[float] = None) -> List[TestResult]:
        """
        Run all tests in the suite.
        
        Args:
            timeout: Optional timeout per test in seconds
        
        Returns:
            List of TestResult objects
        """
        if not self.test_cases:
            self.test_cases = self.discover_tests()
        
        results = []
        for test_case in self.test_cases:
            try:
                test_case.setup()
                start_time = time.time()
                result = test_case.run()
                result.time_taken = time.time() - start_time
                test_case.teardown()
                results.append(result)
            except Exception as e:
                result = TestResult(
                    name=test_case.name,
                    status=TestStatus.ERROR,
                    error=str(e),
                    time_taken=time.time() - start_time if 'start_time' in locals() else 0.0
                )
                results.append(result)
            finally:
                test_case.result = result if 'result' in locals() else None
        
        self.results = results
        return results
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics for the suite."""
        if not self.results:
            return {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "error": 0
            }
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAILED)
        skipped = sum(1 for r in self.results if r.status == TestStatus.SKIPPED)
        error = sum(1 for r in self.results if r.status == TestStatus.ERROR)
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "error": error,
            "pass_rate": passed / total if total > 0 else 0.0
        }
    
    def print_summary(self) -> None:
        """Print summary of test results."""
        summary = self.get_summary()
        print(f"\n{'='*60}")
        print(f"Test Suite: {self.name}")
        if self.description:
            print(f"Description: {self.description}")
        print(f"{'='*60}")
        print(f"Total: {summary['total']}")
        print(f"Passed: {summary['passed']} ({summary['pass_rate']*100:.1f}%)")
        print(f"Failed: {summary['failed']}")
        print(f"Skipped: {summary['skipped']}")
        print(f"Error: {summary['error']}")

