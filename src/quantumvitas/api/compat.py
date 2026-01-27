"""
Compatibility layer for legacy QVService methods.

This module provides backward-compatibility wrappers for methods that were
removed from QVService during PR10 API slimming. These wrappers are intended
for test migration only and should NOT be imported by daemon or CLI code.

All functions in this module:
- Use lazy imports to avoid kernel imports at module level
- Return JSON-friendly data or DTOs
- Provide minimal semantics needed for legacy tests
- Will be gradually removed as tests migrate to new API

Gate tests enforce that daemon/cli do not import this module.
"""

from typing import Any
from pathlib import Path


class QVServiceCompat:
    """
    Compatibility wrapper class for legacy QVService static methods.
    
    This class should only be used in tests during migration.
    Do not import this in daemon or CLI code.
    """
    
    @staticmethod
    def init_step(
        project_root: Path | str,
        step_type: str,
        calculation_selector: str,
        **kwargs: Any,
    ) -> Any:
        """
        Create a new step in a calculation.
        
        This is a compatibility wrapper that delegates to the new API.
        Returns an object with StepDTO attributes plus absolute_path for backward compatibility.
        """
        try:
            from quantumvitas.api.service import QVService
            from quantumvitas.core.resolution import require_calculation, require_step
            
            project_root = Path(project_root).resolve()
            svc = QVService(project_root)
            
            # Add step using new API
            step_dto = svc.calculation.add_step(
                calc_selector=calculation_selector,
                step_type=step_type,
                **kwargs,
            )
            
            # Get step path for backward compatibility (tests expect absolute_path)
            # Resolve step to get its path
            try:
                step_resolved = require_step(
                    project_root,
                    calculation_selector,
                    step_dto.step_id,
                )
                # Create a simple wrapper that has both StepDTO attributes and absolute_path
                class StepCompatWrapper:
                    def __init__(self, dto: Any, path: Path):
                        self._dto = dto
                        self.absolute_path = path
                        # Forward all DTO attributes
                        for attr in dir(dto):
                            if not attr.startswith('_'):
                                setattr(self, attr, getattr(dto, attr))
                
                return StepCompatWrapper(step_dto, step_resolved.absolute_path)
            except Exception:
                # If resolution fails, return DTO as-is (some tests may not need absolute_path)
                return step_dto
            
        except Exception as e:
            # Map kernel exceptions to API exceptions
            from quantumvitas.api.service import map_kernel_exception
            raise map_kernel_exception(e)
    
    @staticmethod
    def add_step_to_calculation(
        project_root: Path | str,
        calculation_selector: str,
        step_type: str,
        **kwargs: Any,
    ) -> Any:
        """
        Add a step to a calculation.
        
        This is a compatibility wrapper that delegates to the new API.
        """
        try:
            from quantumvitas.api.service import QVService
            
            project_root = Path(project_root).resolve()
            svc = QVService(project_root)
            
            # Add step using new API
            step_dto = svc.calculation.add_step(
                calc_selector=calculation_selector,
                step_type=step_type,
                **kwargs,
            )
            
            return step_dto
        except Exception as e:
            from quantumvitas.api.service import map_kernel_exception
            raise map_kernel_exception(e)


# Module-level compatibility functions (for easier test migration)
def init_step(
    project_root: Path | str,
    step_type: str,
    calculation_selector: str,
    **kwargs: Any,
) -> Any:
    """Compatibility function for QVService.init_step()."""
    return QVServiceCompat.init_step(project_root, step_type, calculation_selector, **kwargs)


def add_step_to_calculation(
    project_root: Path | str,
    calculation_selector: str,
    step_type: str,
    **kwargs: Any,
) -> Any:
    """Compatibility function for QVService.add_step_to_calculation()."""
    return QVServiceCompat.add_step_to_calculation(project_root, calculation_selector, step_type, **kwargs)

