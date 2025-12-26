"""
K_POINTS view model conversion.

Converts between raw QE K_POINTS card text and structured view model.
This module is responsible for parsing and formatting, following the
Common Cards Contract: UI never parses raw text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class KPointsAutomatic:
    """Automatic mode parameters."""
    nk1: int
    nk2: int
    nk3: int
    sk1: int
    sk2: int
    sk3: int


@dataclass
class KPointsPoint:
    """Single k-point (for list-based modes)."""
    x: float
    y: float
    z: float
    w: float


@dataclass
class KPointsViewModel:
    """
    View model for K_POINTS card.
    
    Fields:
        raw: Original raw QE text (as stored in YAML)
        mode: Parsed mode - "gamma" | "automatic" | "tpiba" | "crystal" | "tpiba_b" | "crystal_b" | "tpiba_c" | "crystal_c" | "custom"
        automatic: Grid parameters for automatic mode
        points: K-point list for list-based modes
        parse_ok: True if parsing succeeded (mode is not "custom" due to parse failure)
        canonical_raw: Backend-formatted canonical raw text (for display/debug)
        warnings: Non-fatal warnings (e.g., unusual values)
        errors: Fatal parsing errors
        summary: Human-readable summary for display
    """
    raw: str
    mode: str
    automatic: Optional[KPointsAutomatic] = None
    points: Optional[List[KPointsPoint]] = None
    parse_ok: bool = True
    canonical_raw: Optional[str] = None
    warnings: Optional[List[str]] = None
    errors: Optional[List[str]] = None
    summary: Optional[str] = None


def _make_summary(mode: str, automatic: Optional[KPointsAutomatic] = None, points: Optional[List[KPointsPoint]] = None) -> str:
    """Generate human-readable summary."""
    if mode == "gamma":
        return "Gamma point only"
    elif mode == "automatic" and automatic:
        grid = f"{automatic.nk1}×{automatic.nk2}×{automatic.nk3}"
        shift = f"shift {automatic.sk1} {automatic.sk2} {automatic.sk3}"
        return f"Automatic {grid} {shift}"
    elif mode in ("tpiba", "crystal", "tpiba_b", "crystal_b", "tpiba_c", "crystal_c"):
        npts = len(points) if points else 0
        return f"{mode} ({npts} points)"
    else:
        return "Custom (raw)"


def parse_k_points(raw: str) -> KPointsViewModel:
    """
    Parse raw K_POINTS card text into view model.
    
    Args:
        raw: Raw QE K_POINTS card text (e.g., "automatic\\n8 8 8 0 0 0")
        
    Returns:
        KPointsViewModel with parsed structure, parse_ok, and canonical_raw
    """
    lines = [line.strip() for line in raw.strip().split('\n') if line.strip()]
    
    if not lines:
        return KPointsViewModel(
            raw=raw,
            mode="custom",
            parse_ok=False,
            errors=["Empty K_POINTS card"],
            summary="Custom (raw)"
        )
    
    # First line is the mode/option
    first_line = lines[0].upper()
    
    # Check for gamma
    if "gamma" in first_line.lower() or first_line == "K_POINTS":
        # Gamma mode: just "K_POINTS gamma" or "K_POINTS"
        vm = KPointsViewModel(
            raw=raw,
            mode="gamma",
            parse_ok=True,
            summary=_make_summary("gamma")
        )
        vm.canonical_raw = format_k_points(vm)
        return vm
    
    # Check for automatic
    if "automatic" in first_line.lower():
        if len(lines) < 2:
            return KPointsViewModel(
                raw=raw,
                mode="automatic",
                parse_ok=False,
                warnings=["Automatic mode missing grid parameters"],
                summary="Automatic (incomplete)"
            )
        
        try:
            parts = lines[1].split()
            if len(parts) >= 6:
                nk1, nk2, nk3, sk1, sk2, sk3 = [int(float(x)) for x in parts[:6]]
                auto = KPointsAutomatic(nk1=nk1, nk2=nk2, nk3=nk3, sk1=sk1, sk2=sk2, sk3=sk3)
                vm = KPointsViewModel(
                    raw=raw,
                    mode="automatic",
                    automatic=auto,
                    parse_ok=True,
                    summary=_make_summary("automatic", auto)
                )
                vm.canonical_raw = format_k_points(vm)
                return vm
            else:
                return KPointsViewModel(
                    raw=raw,
                    mode="automatic",
                    parse_ok=False,
                    warnings=[f"Automatic mode requires 6 values, got {len(parts)}"],
                    summary="Automatic (incomplete)"
                )
        except (ValueError, IndexError) as e:
            return KPointsViewModel(
                raw=raw,
                mode="automatic",
                parse_ok=False,
                warnings=[f"Failed to parse automatic mode: {e}"],
                summary="Automatic (parse error)"
            )
    
    # Check for list-based modes (tpiba, crystal, etc.)
    first_lower = first_line.lower()
    mode = "custom"
    if "tpiba" in first_lower:
        mode = "tpiba"
        if "_b" in first_lower:
            mode = "tpiba_b"
        elif "_c" in first_lower:
            mode = "tpiba_c"
    elif "crystal" in first_lower:
        mode = "crystal"
        if "_b" in first_lower:
            mode = "crystal_b"
        elif "_c" in first_lower:
            mode = "crystal_c"
    
    # Parse list of k-points
    points: List[KPointsPoint] = []
    warnings: List[str] = []
    
    # Skip first line (mode), parse remaining
    data_lines = lines[1:]
    
    if not data_lines:
        return KPointsViewModel(
            raw=raw,
            mode=mode,
            parse_ok=False,
            warnings=["List mode missing k-point data"],
            summary=f"{mode} (empty)"
        )
    
    # First data line might be count (for crystal_b, tpiba_b, etc.)
    start_idx = 0
    if mode in ("crystal_b", "crystal_c", "tpiba_b", "tpiba_c"):
        # First line is count, skip it
        if data_lines:
            try:
                _ = int(data_lines[0])
                start_idx = 1
            except ValueError:
                warnings.append("Expected count line for band path mode")
    
    # Parse k-points
    for i, line in enumerate(data_lines[start_idx:], start=start_idx):
        parts = line.split()
        if len(parts) >= 4:
            try:
                x, y, z, w = [float(p) for p in parts[:4]]
                points.append(KPointsPoint(x=x, y=y, z=z, w=w))
            except ValueError:
                warnings.append(f"Failed to parse k-point line {i+1}: {line}")
        elif len(parts) > 0:
            warnings.append(f"K-point line {i+1} has {len(parts)} values, expected 4: {line}")
    
    if not points and not warnings:
        warnings.append("No valid k-points found")
    
    parse_ok = len(points) > 0
    vm = KPointsViewModel(
        raw=raw,
        mode=mode,
        points=points if points else None,
        parse_ok=parse_ok,
        warnings=warnings if warnings else None,
        summary=_make_summary(mode, points=points)
    )
    if parse_ok:
        vm.canonical_raw = format_k_points(vm)
    return vm


def format_k_points(view_model: KPointsViewModel) -> str:
    """
    Format view model to canonical QE K_POINTS card text.
    
    Args:
        view_model: KPointsViewModel to format
        
    Returns:
        Canonical QE K_POINTS card text (string)
    """
    lines: List[str] = []
    
    if view_model.mode == "gamma":
        return "K_POINTS gamma"
    
    if view_model.mode == "automatic":
        if view_model.automatic:
            lines.append("K_POINTS automatic")
            lines.append(f"{view_model.automatic.nk1} {view_model.automatic.nk2} {view_model.automatic.nk3} "
                        f"{view_model.automatic.sk1} {view_model.automatic.sk2} {view_model.automatic.sk3}")
        else:
            # Fallback: use default
            lines.append("K_POINTS automatic")
            lines.append("1 1 1 0 0 0")
        return "\n".join(lines)
    
    # List-based modes
    mode_str = view_model.mode.upper()
    if mode_str in ("TPIBA", "CRYSTAL"):
        lines.append(f"K_POINTS {{{mode_str.lower()}}}")
    elif mode_str in ("TPIBA_B", "CRYSTAL_B", "TPIBA_C", "CRYSTAL_C"):
        # Band path modes need count line
        lines.append(f"K_POINTS {{{mode_str.lower()}}}")
        if view_model.points:
            # Count segments (for band paths, each segment might be multiple points)
            # For now, count as number of points
            n_segments = len(view_model.points)
            lines.append(str(n_segments))
    else:
        # Custom mode: use raw or default
        if view_model.raw and view_model.raw.strip():
            return view_model.raw
        lines.append("K_POINTS")
    
    # Add k-points
    if view_model.points:
        for point in view_model.points:
            lines.append(f"  {point.x:.10f} {point.y:.10f} {point.z:.10f} {point.w:.10f}")
    else:
        # Empty list mode
        lines.append("  0")
    
    return "\n".join(lines)


def k_points_from_card_data(card_data: Dict[str, Any]) -> str:
    """
    Convert card data dict (from YAML) to raw QE text.
    
    Args:
        card_data: Dict with "option" and "data" keys (from step.yaml)
        
    Returns:
        Raw QE K_POINTS card text
    """
    from quantumvitas.io.generator.qe_generator import QEInputGenerator
    from quantumvitas.io.model import QECard, QECardType
    
    option = card_data.get("option", "")
    data = card_data.get("data", [])
    
    card = QECard(card_type=QECardType.K_POINTS, option=option)
    for line in data:
        card.add_line(line)
    
    # Generate raw text
    raw = QEInputGenerator.generate_card(card)
    return raw


def k_points_to_card_data(raw: str) -> Dict[str, Any]:
    """
    Convert raw QE text to card data dict (for YAML storage).
    
    Args:
        raw: Raw QE K_POINTS card text
        
    Returns:
        Dict with "option" and "data" keys (for step.yaml)
    """
    from quantumvitas.io.parser.qe_parser import QEInputParser
    
    # Parse raw text into QECard
    lines = raw.strip().split('\n')
    if not lines:
        return {"option": "", "data": []}
    
    # Find K_POINTS line
    k_points_idx = None
    for i, line in enumerate(lines):
        if line.strip().upper().startswith("K_POINTS"):
            k_points_idx = i
            break
    
    if k_points_idx is None:
        return {"option": "", "data": []}
    
    # Parse card
    try:
        card, _ = QEInputParser.parse_card(lines, k_points_idx)
        return {
            "option": card.option or "",
            "data": card.data
        }
    except Exception:
        # Fallback: return raw as single data line
        return {
            "option": "",
            "data": [raw]
        }

