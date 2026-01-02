"""
QuantumVITAS Workflow Module.

Provides:
- StepTypeRegistry: Centralized step type semantics
- WorkflowService: Workflow detection and instantiation
- Step factory: Centralized step creation with Journal integration
"""

from quantumvitas.workflow.registry import (
    StepTypeSpec,
    StepTypeRegistry,
    get_registry,
)
from quantumvitas.workflow.templates import (
    WorkflowTemplate,
    WorkflowMatch,
    WorkflowService,
    get_workflow_service,
)
from quantumvitas.workflow.step_factory import (
    create_step_doc,
    save_step_doc,
)

__all__ = [
    # Registry
    "StepTypeSpec",
    "StepTypeRegistry",
    "get_registry",
    # Workflows
    "WorkflowTemplate",
    "WorkflowMatch",
    "WorkflowService",
    "get_workflow_service",
    # Step factory
    "create_step_doc",
    "save_step_doc",
]

