"""
Gate: Supported Gen Steps Subset Check (§10.2)

Constitution §10.2: For every engine recipe, SUPPORTED_GEN_STEPS ⊆ GenStepRegistry.GEN_STEPS

This gate ensures engines only declare support for registered gen steps.
"""

import pytest
from qmatsuite.workflow.gen_steps import GenStepRegistry


def get_all_engine_supported_steps():
    """Get SUPPORTED_GEN_STEPS from all engine drivers."""
    supported_steps_by_engine = {}
    
    try:
        # Import all drivers
        from qmatsuite.drivers.qe.driver import QEDriver
        from qmatsuite.drivers.vasp.driver import VASPDriver
        from qmatsuite.drivers.pyscf.driver import PySCFDriver
        from qmatsuite.drivers.orca.driver import ORCADriver
        from qmatsuite.drivers.cp2k.driver import CP2KDriver
        from qmatsuite.drivers.lammps.driver import LAMMPSDriver
        from qmatsuite.drivers.w90.driver import W90Driver
        
        drivers = [
            QEDriver(),
            VASPDriver(),
            PySCFDriver(),
            ORCADriver(),
            CP2KDriver(),
            LAMMPSDriver(),
            W90Driver(),
        ]
        
        for driver in drivers:
            if hasattr(driver, 'SUPPORTED_GEN_STEPS'):
                engine = driver.engine_family
                supported_steps_by_engine[engine] = driver.SUPPORTED_GEN_STEPS
    except ImportError as e:
        pytest.skip(f"Could not import drivers: {e}")
    
    return supported_steps_by_engine


class TestSupportedSubset:
    """Gate: SUPPORTED_GEN_STEPS ⊆ GenStepRegistry.GEN_STEPS."""

    def test_all_supported_steps_in_registry(self):
        """All engine SUPPORTED_GEN_STEPS must be in GenStepRegistry."""
        gen_registry = GenStepRegistry.GEN_STEPS
        supported_steps_by_engine = get_all_engine_supported_steps()
        
        violations = []
        for engine, supported_steps in supported_steps_by_engine.items():
            for step in supported_steps:
                if step not in gen_registry:
                    violations.append(f"Engine '{engine}' declares '{step}' but it's not in GenStepRegistry")
        
        if violations:
            report = "\n\n=== SUPPORTED STEPS SUBSET VIOLATIONS ===\n"
            report += f"Found {len(violations)} violation(s):\n\n"
            report += "\n".join(f"  - {v}" for v in violations)
            report += "\n\n=== END VIOLATIONS ===\n"
            report += "\nFix: Add missing gen steps to GenStepRegistry.GEN_STEPS.\n"
            pytest.fail(report)

