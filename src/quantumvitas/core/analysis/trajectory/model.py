"""
Trajectory data model.

Frame: Single snapshot
Trajectory: Collection of frames with metadata
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple

import numpy as np

from quantumvitas.core.analysis.base import AnalysisObjectMeta
from quantumvitas.core.analysis.primitives import (
    GeometryFrame,
    GeometryFrames,
    Series1D,
)


@dataclass
class Frame:
    """
    A single trajectory frame.
    
    Positions are UNWRAPPED Cartesian coordinates in Å.
    Cell can be None for molecular systems without a box.
    """
    # Required
    frame_index: int
    positions: np.ndarray              # (N, 3) UNWRAPPED Cartesian Å
    species: List[str]                 # N element symbols
    cell: Optional[np.ndarray]         # (3, 3) or None
    pbc: Tuple[bool, bool, bool]       # Periodic boundary conditions
    
    # Time/iteration axis
    time: Optional[float] = None       # fs (for MD)
    iteration: Optional[int] = None    # (for relax/NEB)
    
    # Observables
    energy: Optional[float] = None             # eV (potential energy)
    forces: Optional[np.ndarray] = None        # (N, 3) eV/Å
    temperature: Optional[float] = None        # K
    pressure: Optional[float] = None           # GPa
    stress: Optional[np.ndarray] = None        # (3, 3) GPa, positive=tensile
    kinetic_energy: Optional[float] = None     # eV
    velocities: Optional[np.ndarray] = None    # (N, 3) Å/fs
    momenta: Optional[np.ndarray] = None       # (N, 3) amu·Å/fs
    
    # NEB
    image_index: Optional[int] = None
    
    # Atom identity
    atom_ids: Optional[List[str]] = None
    
    def __post_init__(self):
        """Validate frame data."""
        # Validate cell/pbc
        if any(self.pbc) and self.cell is None:
            raise ValueError("PBC requires cell to be provided")
        if self.cell is not None and self.cell.shape != (3, 3):
            raise ValueError(f"Cell must be (3, 3), got {self.cell.shape}")
        
        # Validate positions shape
        if self.positions.shape[1] != 3:
            raise ValueError(f"Positions must be (N, 3), got {self.positions.shape}")
        
        # Validate species count
        if len(self.species) != len(self.positions):
            raise ValueError(f"Species count ({len(self.species)}) != atoms ({len(self.positions)})")
    
    @property
    def n_atoms(self) -> int:
        return len(self.species)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result = {
            "frame_index": self.frame_index,
            "positions": self.positions.tolist(),
            "species": self.species,
            "cell": self.cell.tolist() if self.cell is not None else None,
            "pbc": list(self.pbc),
            "time": self.time,
            "iteration": self.iteration,
            "energy": self.energy,
            "temperature": self.temperature,
            "pressure": self.pressure,
            "kinetic_energy": self.kinetic_energy,
            "image_index": self.image_index,
            "atom_ids": self.atom_ids,
        }
        # Optional arrays
        if self.forces is not None:
            result["forces"] = self.forces.tolist()
        if self.stress is not None:
            result["stress"] = self.stress.tolist()
        if self.velocities is not None:
            result["velocities"] = self.velocities.tolist()
        if self.momenta is not None:
            result["momenta"] = self.momenta.tolist()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Frame":
        """Create from dict."""
        return cls(
            frame_index=data["frame_index"],
            positions=np.array(data["positions"]),
            species=data["species"],
            cell=np.array(data["cell"]) if data.get("cell") is not None else None,
            pbc=tuple(data["pbc"]),
            time=data.get("time"),
            iteration=data.get("iteration"),
            energy=data.get("energy"),
            forces=np.array(data["forces"]) if data.get("forces") else None,
            temperature=data.get("temperature"),
            pressure=data.get("pressure"),
            stress=np.array(data["stress"]) if data.get("stress") else None,
            kinetic_energy=data.get("kinetic_energy"),
            velocities=np.array(data["velocities"]) if data.get("velocities") else None,
            momenta=np.array(data["momenta"]) if data.get("momenta") else None,
            image_index=data.get("image_index"),
            atom_ids=data.get("atom_ids"),
        )


@dataclass
class Trajectory:
    """
    Canonical trajectory representation.
    
    Supports MD, relax (optimization), and NEB trajectories.
    """
    meta: AnalysisObjectMeta
    frames: List[Frame]
    trajectory_type: str              # "md" | "relax" | "neb"
    n_images: Optional[int] = None    # For NEB
    
    @property
    def n_frames(self) -> int:
        return len(self.frames)
    
    @property
    def n_atoms(self) -> int:
        return self.frames[0].n_atoms if self.frames else 0
    
    def __len__(self) -> int:
        return self.n_frames
    
    def __getitem__(self, index: int) -> Frame:
        return self.frames[index]
    
    def __iter__(self) -> Iterator[Frame]:
        return iter(self.frames)
    
    def get_observable_series(self, name: str) -> Optional[Series1D]:
        """Extract time series of an observable."""
        if not self.frames:
            return None
        
        # Determine x-axis based on trajectory type
        if self.trajectory_type == "md":
            x = np.array([f.time for f in self.frames if f.time is not None])
            x_label = "Time"
            x_unit = "fs"
        else:
            x = np.array([f.iteration or f.frame_index for f in self.frames])
            x_label = "Iteration"
            x_unit = ""
        
        if len(x) != len(self.frames):
            # Fall back to frame index
            x = np.arange(len(self.frames))
            x_label = "Frame"
            x_unit = ""
        
        if name == "energy":
            values = [f.energy for f in self.frames]
            if all(v is not None for v in values):
                return Series1D(
                    x=x,
                    y=np.array(values),
                    x_label=x_label,
                    y_label="Energy",
                    x_unit=x_unit,
                    y_unit="eV",
                    name="Total Energy",
                )
        elif name == "temperature":
            values = [f.temperature for f in self.frames]
            if all(v is not None for v in values):
                return Series1D(
                    x=x,
                    y=np.array(values),
                    x_label=x_label,
                    y_label="Temperature",
                    x_unit=x_unit,
                    y_unit="K",
                    name="Temperature",
                )
        elif name == "pressure":
            values = [f.pressure for f in self.frames]
            if all(v is not None for v in values):
                return Series1D(
                    x=x,
                    y=np.array(values),
                    x_label=x_label,
                    y_label="Pressure",
                    x_unit=x_unit,
                    y_unit="GPa",
                    name="Pressure",
                )
        elif name == "max_force":
            values = []
            for f in self.frames:
                if f.forces is not None:
                    values.append(np.max(np.linalg.norm(f.forces, axis=1)))
                else:
                    return None
            return Series1D(
                x=x,
                y=np.array(values),
                x_label=x_label,
                y_label="Max Force",
                x_unit=x_unit,
                y_unit="eV/Å",
                name="Max Force",
            )
        
        return None
    
    def get_available_observables(self) -> List[str]:
        """Get list of available observables."""
        if not self.frames:
            return []
        
        observables = []
        sample = self.frames[0]
        
        if sample.energy is not None:
            observables.append("energy")
        if sample.temperature is not None:
            observables.append("temperature")
        if sample.pressure is not None:
            observables.append("pressure")
        if sample.forces is not None:
            observables.append("max_force")
        if sample.kinetic_energy is not None:
            observables.append("kinetic_energy")
        
        return observables
    
    def to_visual_primitives(self) -> Dict[str, Any]:
        """Convert to visualization primitives (data only, no style)."""
        primitives: Dict[str, Any] = {}
        
        # Geometry frames
        primitives["geometry"] = GeometryFrames(
            frames=[
                GeometryFrame(
                    positions=f.positions,
                    species=f.species,
                    cell=f.cell,
                    pbc=f.pbc,
                    forces=f.forces,
                    velocities=f.velocities,
                )
                for f in self.frames
            ],
            time=np.array([f.time for f in self.frames]) if self.frames and self.frames[0].time else None,
            iteration=np.array([f.iteration or f.frame_index for f in self.frames]),
            image_indices=np.array([f.image_index for f in self.frames]) if self.frames and self.frames[0].image_index is not None else None,
        )
        
        # Observable series
        for obs in self.get_available_observables():
            series = self.get_observable_series(obs)
            if series:
                primitives[f"series_{obs}"] = series
        
        return primitives
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "meta": self.meta.to_dict(),
            "frames": [f.to_dict() for f in self.frames],
            "trajectory_type": self.trajectory_type,
            "n_images": self.n_images,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Trajectory":
        """Create from dict."""
        return cls(
            meta=AnalysisObjectMeta.from_dict(data["meta"]),
            frames=[Frame.from_dict(f) for f in data["frames"]],
            trajectory_type=data["trajectory_type"],
            n_images=data.get("n_images"),
        )

