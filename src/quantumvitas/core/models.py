"""
Core data models for QuantumVITAS.

This module defines the fundamental data structures:
- Project: Container for calculations and structures
- Structure: Atomic structure (geometry)
- Workflow: A sequence of calculation steps
- Step: Individual calculation step in a workflow
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime


class CalculationType(Enum):
    """Types of calculations supported."""
    SCF = "scf"
    OPT = "opt"
    DOS = "dos"
    BANDS = "bands"
    MD = "md"
    TDDFT = "tddft"
    PHONON = "phonon"
    NEB = "neb"


class StepType(Enum):
    """Types of calculation steps."""
    # Geometry
    GEO = "geo"
    # SCF-related
    SCF = "scf"
    NSCF = "nscf"
    # Structure optimization
    OPT = "opt"
    # DOS
    DOS = "dos"
    PROJWFC = "projwfc"
    SUMPDOS = "sumpdos"
    # Bands
    BANDS = "bands"
    BANDSPP = "bands_pp"
    # Molecular dynamics
    MD = "md"
    # TDDFT
    TDDFT_LANCZOS = "tddft_lanczos"
    TDDFT_SPECTRUM = "tddft_spectrum"
    # Phonon
    PH = "ph"
    Q2R = "q2r"
    MATDYN = "matdyn"
    # NEB
    NEB = "neb"


@dataclass
class Structure:
    """Atomic structure (geometry)."""
    name: str
    atoms: Any = None  # Will use ASE Atoms or pymatgen Structure
    cell: Optional[List[List[float]]] = None
    alat: Optional[float] = None  # Lattice parameter in Bohr
    path: Optional[Path] = None  # Path to structure file if loaded from disk
    
    def __post_init__(self):
        if self.atoms is None:
            # Will be initialized with ASE or pymatgen
            pass


@dataclass
class Step:
    """A single calculation step in a workflow."""
    name: str
    step_type: StepType
    engine: str  # e.g., "qe", "wannier90", "lammps"
    input_data: Dict[str, Any] = field(default_factory=dict)
    input_file: Optional[Path] = None
    output_file: Optional[Path] = None
    status: str = "pending"  # pending, running, completed, failed
    dependencies: List[str] = field(default_factory=list)  # Names of steps this depends on
    
    def __post_init__(self):
        """Validate step configuration."""
        if not self.name:
            raise ValueError("Step name cannot be empty")


@dataclass
class Workflow:
    """A workflow consisting of multiple calculation steps."""
    name: str
    calc_type: CalculationType
    steps: List[Step] = field(default_factory=list)
    structure: Optional[Structure] = None
    working_dir: Optional[Path] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def add_step(self, step: Step) -> None:
        """Add a step to the workflow."""
        if any(s.name == step.name for s in self.steps):
            raise ValueError(f"Step with name '{step.name}' already exists")
        self.steps.append(step)
        self.updated_at = datetime.now()
    
    def get_step(self, name: str) -> Optional[Step]:
        """Get a step by name."""
        for step in self.steps:
            if step.name == name:
                return step
        return None
    
    def get_ordered_steps(self) -> List[Step]:
        """Get steps in execution order (respecting dependencies)."""
        # Simple topological sort - can be enhanced later
        ordered = []
        remaining = list(self.steps)
        
        while remaining:
            # Find steps with no unsatisfied dependencies
            ready = [
                s for s in remaining
                if all(dep in [st.name for st in ordered] for dep in s.dependencies)
            ]
            if not ready:
                # Circular dependency or missing dependency
                break
            ordered.extend(ready)
            remaining = [s for s in remaining if s not in ready]
        
        return ordered


@dataclass
class Project:
    """A project containing multiple workflows and structures."""
    name: str
    workspace_dir: Path
    workflows: Dict[str, Workflow] = field(default_factory=dict)
    structures: Dict[str, Structure] = field(default_factory=dict)
    active_workflow: Optional[str] = None
    active_structure: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    @property
    def project_dir(self) -> Path:
        """Get the project directory."""
        return self.workspace_dir / self.name
    
    def add_workflow(self, workflow: Workflow) -> None:
        """Add a workflow to the project."""
        if workflow.name in self.workflows:
            raise ValueError(f"Workflow '{workflow.name}' already exists")
        self.workflows[workflow.name] = workflow
        self.updated_at = datetime.now()
    
    def get_workflow(self, name: str) -> Optional[Workflow]:
        """Get a workflow by name."""
        return self.workflows.get(name)
    
    def add_structure(self, structure: Structure) -> None:
        """Add a structure to the project."""
        if structure.name in self.structures:
            raise ValueError(f"Structure '{structure.name}' already exists")
        self.structures[structure.name] = structure
        self.updated_at = datetime.now()
    
    def get_structure(self, name: str) -> Optional[Structure]:
        """Get a structure by name."""
        return self.structures.get(name)
    
    def save(self) -> None:
        """Save project to disk."""
        # TODO: Implement serialization (JSON/YAML)
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.updated_at = datetime.now()
    
    @classmethod
    def load(cls, workspace_dir: Path, name: str) -> "Project":
        """Load project from disk."""
        # TODO: Implement deserialization
        project = cls(name=name, workspace_dir=workspace_dir)
        project_dir = project.project_dir
        if project_dir.exists():
            # Load workflows and structures
            pass
        return project

