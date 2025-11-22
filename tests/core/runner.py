"""
Test runner for executing multiple test suites.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import argparse
import json

from .base import TestSuite, TestResult


class TestRunner:
    """
    Main test runner that can execute multiple test suites.
    
    Provides unified interface for running different types of tests.
    """
    
    def __init__(self):
        """Initialize test runner."""
        self.suites: List[TestSuite] = []
        self.results: Dict[str, List[TestResult]] = {}
    
    def register_suite(self, suite: TestSuite) -> None:
        """Register a test suite."""
        self.suites.append(suite)
    
    def run_suite(self, suite_name: str, timeout: Optional[float] = None) -> List[TestResult]:
        """
        Run a specific test suite by name.
        
        Args:
            suite_name: Name of the suite to run
            timeout: Optional timeout per test
        
        Returns:
            List of test results
        """
        suite = next((s for s in self.suites if s.name == suite_name), None)
        if not suite:
            raise ValueError(f"Test suite '{suite_name}' not found")
        
        print(f"Running test suite: {suite.name}")
        results = suite.run_all(timeout=timeout)
        suite.print_summary()
        self.results[suite_name] = results
        return results
    
    def run_all(self, timeout: Optional[float] = None) -> Dict[str, List[TestResult]]:
        """
        Run all registered test suites.
        
        Args:
            timeout: Optional timeout per test
        
        Returns:
            Dictionary mapping suite names to their results
        """
        all_results = {}
        for suite in self.suites:
            print(f"\n{'='*60}")
            print(f"Running test suite: {suite.name}")
            print(f"{'='*60}")
            results = suite.run_all(timeout=timeout)
            suite.print_summary()
            all_results[suite.name] = results
        
        self.results = all_results
        return all_results
    
    def get_overall_summary(self) -> Dict[str, Any]:
        """Get summary across all test suites."""
        total = 0
        passed = 0
        failed = 0
        skipped = 0
        error = 0
        
        for suite_results in self.results.values():
            for result in suite_results:
                total += 1
                if result.status.value == "passed":
                    passed += 1
                elif result.status.value == "failed":
                    failed += 1
                elif result.status.value == "skipped":
                    skipped += 1
                elif result.status.value == "error":
                    error += 1
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "error": error,
            "pass_rate": passed / total if total > 0 else 0.0
        }
    
    def print_overall_summary(self) -> None:
        """Print overall summary across all suites."""
        summary = self.get_overall_summary()
        print(f"\n{'='*60}")
        print("OVERALL TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total tests: {summary['total']}")
        print(f"Passed: {summary['passed']} ({summary['pass_rate']*100:.1f}%)")
        print(f"Failed: {summary['failed']}")
        print(f"Skipped: {summary['skipped']}")
        print(f"Error: {summary['error']}")
    
    def export_results(self, output_file: Path, format: str = "json") -> None:
        """
        Export test results to file.
        
        Args:
            output_file: Output file path
            format: Export format ("json" or "text")
        """
        if format == "json":
            data = {
                "suites": {
                    name: [r.to_dict() for r in results]
                    for name, results in self.results.items()
                },
                "summary": self.get_overall_summary()
            }
            output_file.write_text(json.dumps(data, indent=2))
        else:
            # Text format
            lines = ["Test Results Summary", "=" * 60, ""]
            for suite_name, results in self.results.items():
                lines.append(f"Suite: {suite_name}")
                lines.append("-" * 60)
                for result in results:
                    status_symbol = "✓" if result.success else "✗"
                    lines.append(f"{status_symbol} {result.name}: {result.status.value}")
                    if result.message:
                        lines.append(f"  {result.message}")
                    if result.error:
                        lines.append(f"  Error: {result.error}")
                lines.append("")
            output_file.write_text("\n".join(lines))
    
    @classmethod
    def create_cli(cls) -> argparse.ArgumentParser:
        """Create CLI argument parser."""
        parser = argparse.ArgumentParser(description="QuantumVITAS Test Runner")
        parser.add_argument(
            "--suite",
            type=str,
            help="Run specific test suite (default: run all)"
        )
        parser.add_argument(
            "--timeout",
            type=float,
            help="Timeout per test in seconds"
        )
        parser.add_argument(
            "--output",
            type=Path,
            help="Export results to file"
        )
        parser.add_argument(
            "--format",
            choices=["json", "text"],
            default="json",
            help="Output format for export"
        )
        return parser

