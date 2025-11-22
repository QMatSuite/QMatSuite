"""
QE Official Test Suite implementation for extended tests.
"""

import sys
from pathlib import Path
import configparser

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

from tests.core.base import TestSuite, TestCase
from .cases import QECategoryTestCase


class QETestSuite(TestSuite):
    """
    Test suite for QE official test-suite.
    
    Discovers and runs tests from the QE test-suite jobconfig.
    """
    
    def __init__(
        self,
        test_suite_dir: Path,
        qe_bin_dir: Path,
        module_prefix: str = "pw_",
        description: str = ""
    ):
        """
        Initialize QE test suite.
        
        Args:
            test_suite_dir: Path to QE test-suite directory
            qe_bin_dir: Path to QE bin directory
            module_prefix: Module prefix to filter tests (e.g., "pw_", "ph_")
            description: Suite description
        """
        name = f"QE Test Suite ({module_prefix.rstrip('_')})"
        super().__init__(name, description or f"QE official test-suite for {module_prefix.rstrip('_')} module")
        self.test_suite_dir = test_suite_dir
        self.qe_bin_dir = qe_bin_dir
        self.module_prefix = module_prefix
        self.jobconfig_path = test_suite_dir / "jobconfig"
    
    def discover_tests(self):
        """Discover test categories from jobconfig."""
        if not self.jobconfig_path.exists():
            return []
        
        config = configparser.ConfigParser()
        config.read(self.jobconfig_path)
        
        test_cases = []
        for section in config.sections():
            section_name = section.rstrip('/')
            if section_name.startswith(self.module_prefix):
                if 'inputs_args' in config[section]:
                    try:
                        inputs = eval(config[section]['inputs_args'])
                        if inputs:
                            test_case = QECategoryTestCase(
                                name=section_name,
                                category=section_name,
                                test_files=inputs,
                                test_suite_dir=self.test_suite_dir,
                                qe_bin_dir=self.qe_bin_dir
                            )
                            test_cases.append(test_case)
                    except Exception:
                        pass
        
        return test_cases

