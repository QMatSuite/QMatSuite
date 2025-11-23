"""
Quantum ESPRESSO input file parser and generator.

This module provides bidirectional conversion between QE input files (.in)
and structured Python data (namelists and cards).

Supports multiple QE modules:
- pw.x: &CONTROL, &system, &ELECTRONS, &IONS, &CELL
  Documentation: https://www.quantum-espresso.org/Doc/INPUT_PW.html
- ph.x: &inputph
  Documentation: https://www.quantum-espresso.org/Doc/INPUT_PH.html
- q2r.x: &input
  Documentation: https://www.quantum-espresso.org/Doc/INPUT_Q2R.html
- matdyn.x: &input
  Documentation: https://www.quantum-espresso.org/Doc/INPUT_MATDYN.html
- pp.x: &inputpp
  Documentation: https://www.quantum-espresso.org/Doc/INPUT_PP.html
- gipaw.x: &inputgipaw
- neb.x: &PATH (plus embedded pw.x input)
  Documentation: https://www.quantum-espresso.org/Doc/INPUT_NEB.html
- cp.x: &CONTROL, &SYSTEM, &ELECTRONS, &IONS, &CELL (Car-Parrinello MD)
  Documentation: https://www.quantum-espresso.org/Doc/INPUT_CP.html
- ld1.x: &input (atomic calculations)
  Documentation: https://www.quantum-espresso.org/Doc/INPUT_LD1.html
- hp.x: &inputhp (Hubbard U parameters)
  Documentation: https://www.quantum-espresso.org/Doc/INPUT_HP.html
- pwcond.x: &cond (conductance calculations)
  Documentation: https://www.quantum-espresso.org/Doc/INPUT_PWCOND.html
- bands.x, dos.x, projwfc.x: Similar to pw.x
- And other QE modules

Workflow Note:
  Many QE workflows run modules sequentially where:
  - Previous step's OUTPUT determines next step's INPUT filename
  - Example: pw.x generates .save directory -> ph.x reads from .save
  - Example: ph.x generates dyn files -> q2r.x reads dyn files -> matdyn.x reads .fc file
  - The prefix/outdir from previous step's input determines output filenames
"""

import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum


class QEModule(Enum):
    """
    Quantum ESPRESSO modules.
    
    Official Documentation Links:
    - PW: https://www.quantum-espresso.org/Doc/INPUT_PW.html
    - PH: https://www.quantum-espresso.org/Doc/INPUT_PH.html
    - Q2R: https://www.quantum-espresso.org/Doc/INPUT_Q2R.html
    - MATDYN: https://www.quantum-espresso.org/Doc/INPUT_MATDYN.html
    - PP: https://www.quantum-espresso.org/Doc/INPUT_PP.html
    - NEB: https://www.quantum-espresso.org/Doc/INPUT_NEB.html
    - CP: https://www.quantum-espresso.org/Doc/INPUT_CP.html
    - LD1: https://www.quantum-espresso.org/Doc/INPUT_LD1.html
    - HP: https://www.quantum-espresso.org/Doc/INPUT_HP.html
    - PWCOND: https://www.quantum-espresso.org/Doc/INPUT_PWCOND.html
    - BANDS: https://www.quantum-espresso.org/Doc/INPUT_BANDS.html
    - DOS: https://www.quantum-espresso.org/Doc/INPUT_DOS.html
    - PROJWFC: https://www.quantum-espresso.org/Doc/INPUT_PROJWFC.html
    - POSTAHC: https://www.quantum-espresso.org/Doc/INPUT_POSTAHC.html
    - DYNMAT: https://www.quantum-espresso.org/Doc/INPUT_DYNMAT.html
    - OSCDFT_ET: https://www.quantum-espresso.org/Doc/INPUT_OSCDFT_ET.html
    - OSCDFT_PP: https://www.quantum-espresso.org/Doc/INPUT_OSCDFT_PP.html
    - BAND_INTERPOLATION: https://www.quantum-espresso.org/Doc/INPUT_BAND_INTERPOLATION.html
    - CPPP: https://www.quantum-espresso.org/Doc/INPUT_CPPP.html
    - D3HESS: https://www.quantum-espresso.org/Doc/INPUT_D3HESS.html
    - PPACF: https://www.quantum-espresso.org/Doc/INPUT_PPACF.html
    - PPRISM: https://www.quantum-espresso.org/Doc/INPUT_PPRISM.html
    """
    PW = "pw"  # pw.x - main DFT code
    PH = "ph"  # ph.x - phonon calculations
    Q2R = "q2r"  # q2r.x - q-point to real space conversion
    MATDYN = "matdyn"  # matdyn.x - phonon frequency calculation
    PP = "pp"  # pp.x - post-processing
    GIPAW = "gipaw"  # gipaw.x - NMR/EPR calculations
    NEB = "neb"  # neb.x - nudged elastic band
    CP = "cp"  # cp.x - Car-Parrinello molecular dynamics
    LD1 = "ld1"  # ld1.x - atomic calculations
    HP = "hp"  # hp.x - Hubbard U parameters
    PWCOND = "pwcond"  # pwcond.x - conductance calculations
    BANDS = "bands"  # bands.x - band structure
    DOS = "dos"  # dos.x - density of states
    PROJWFC = "projwfc"  # projwfc.x - projected wavefunctions
    POSTAHC = "postahc"  # postahc.x - post-processing for AHC
    DYNMAT = "dynmat"  # dynmat.x - dynamical matrix diagonalization
    OSCDFT_ET = "oscdft_et"  # oscdft_et.x - OSCDFT eigenvalue tracking
    OSCDFT_PP = "oscdft_pp"  # oscdft_pp.x - OSCDFT post-processing
    BAND_INTERPOLATION = "band_interpolation"  # band_interpolation.x - band interpolation
    CPPP = "cppp"  # cppp.x - CP post-processing
    D3HESS = "d3hess"  # d3hess.x - third-order force constants
    PPACF = "ppacf"  # ppacf.x - post-processing ACF
    PPRISM = "pprism"  # pprism.x - post-processing RISM
    UNKNOWN = "unknown"  # Unknown module


class QECardType(Enum):
    """Types of QE input cards."""
    ATOMIC_SPECIES = "ATOMIC_SPECIES"
    ATOMIC_POSITIONS = "ATOMIC_POSITIONS"
    K_POINTS = "K_POINTS"
    CELL_PARAMETERS = "CELL_PARAMETERS"
    CONSTRAINTS = "CONSTRAINTS"
    OCCUPATIONS = "OCCUPATIONS"
    ATOMIC_FORCES = "ATOMIC_FORCES"
    CLIMBING_IMAGES = "CLIMBING_IMAGES"
    HUBBARD = "HUBBARD"
    END = "END"


@dataclass
class QENamelist:
    """A QE namelist (e.g., &control, &system)."""
    name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    parameter_comments: Dict[str, str] = field(default_factory=dict)  # Comments for each parameter
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a parameter value."""
        return self.parameters.get(key, default)
    
    def set(self, key: str, value: Any, comment: Optional[str] = None):
        """Set a parameter value."""
        self.parameters[key] = value
        if comment:
            self.parameter_comments[key] = comment
    
    def get_comment(self, key: str) -> Optional[str]:
        """Get comment for a parameter."""
        return self.parameter_comments.get(key)


@dataclass
class QECard:
    """A QE input card (e.g., ATOMIC_SPECIES, K_POINTS)."""
    card_type: QECardType
    option: Optional[str] = None  # e.g., "(alat)" in ATOMIC_POSITIONS (alat)
    data: List[Union[str, List[Any]]] = field(default_factory=list)  # Card data lines
    
    def add_line(self, line: Union[str, List[Any]]):
        """Add a data line to the card."""
        self.data.append(line)


@dataclass
class QEInput:
    """Complete QE input file structure."""
    namelists: List[QENamelist] = field(default_factory=list)
    cards: List[QECard] = field(default_factory=list)
    comments: List[Tuple[int, str]] = field(default_factory=list)  # (line_number, comment)
    module: Optional[QEModule] = None  # Detected QE module
    
    def get_namelist(self, name: str) -> Optional[QENamelist]:
        """Get a namelist by name (without &)."""
        for nl in self.namelists:
            if nl.name.lower() == name.lower():
                return nl
        return None
    
    def get_card(self, card_type: QECardType) -> Optional[QECard]:
        """Get the first card of a given type."""
        for card in self.cards:
            if card.card_type == card_type:
                return card
        return None
    
    def get_cards(self, card_type: QECardType) -> List[QECard]:
        """Get all cards of a given type."""
        return [card for card in self.cards if card.card_type == card_type]
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert QEInput to dictionary format for comparison.
        
        Returns:
            Dictionary representation of the input
        """
        # Normalize parameters for comparison (handle float precision)
        def normalize_value(v):
            """Normalize values for comparison."""
            if isinstance(v, float):
                # Round to avoid precision issues
                return round(v, 12)
            elif isinstance(v, (list, tuple)):
                return [normalize_value(item) for item in v]
            else:
                return v
        
        normalized_namelists = {}
        for nl in self.namelists:
            normalized_params = {k: normalize_value(v) for k, v in nl.parameters.items()}
            normalized_namelists[nl.name] = normalized_params
        
        return {
            'namelists': normalized_namelists,
            'cards': [
                {
                    'type': card.card_type.value,
                    'option': card.option,
                    'data': card.data
                }
                for card in self.cards
            ],
            'module': self.module.value if self.module else None
        }
    
    def detect_module(self) -> QEModule:
        """
        Detect QE module from namelist names.
        
        Detection order:
        1. ph.x: &inputph namelist
           Documentation: https://www.quantum-espresso.org/Doc/INPUT_PH.html
        2. hp.x: &inputhp namelist
           Documentation: https://www.quantum-espresso.org/Doc/INPUT_HP.html
        3. pp.x: &inputpp namelist
           Documentation: https://www.quantum-espresso.org/Doc/INPUT_PP.html
        4. gipaw.x: &inputgipaw namelist
        5. neb.x: &PATH namelist
           Documentation: https://www.quantum-espresso.org/Doc/INPUT_NEB.html
        6. pwcond.x: &cond namelist
           Documentation: https://www.quantum-espresso.org/Doc/INPUT_PWCOND.html
        7. q2r.x: &input namelist (but check for q2r-specific parameters)
           Documentation: https://www.quantum-espresso.org/Doc/INPUT_Q2R.html
        8. matdyn.x: &input namelist (but check for matdyn-specific parameters)
           Documentation: https://www.quantum-espresso.org/Doc/INPUT_MATDYN.html
        9. ld1.x: &input namelist (atomic calculations, check for ld1-specific parameters)
           Documentation: https://www.quantum-espresso.org/Doc/INPUT_LD1.html
        10. cp.x: &CONTROL, &SYSTEM, &ELECTRONS (similar to pw.x but for MD)
            Documentation: https://www.quantum-espresso.org/Doc/INPUT_CP.html
        11. bands.x: &BANDS namelist
            Documentation: https://www.quantum-espresso.org/Doc/INPUT_BANDS.html
        12. dos.x: &DOS namelist
            Documentation: https://www.quantum-espresso.org/Doc/INPUT_DOS.html
        13. projwfc.x: &PROJWFC namelist
            Documentation: https://www.quantum-espresso.org/Doc/INPUT_PROJWFC.html
        14. pw.x: &CONTROL, &system, &ELECTRONS (default for these namelists)
            Documentation: https://www.quantum-espresso.org/Doc/INPUT_PW.html
        
        Returns:
            Detected QE module
        """
        namelist_names = {nl.name.lower() for nl in self.namelists}
        
        # Module-specific namelist detection
        if 'inputph' in namelist_names:
            return QEModule.PH
        elif 'inputhp' in namelist_names:
            return QEModule.HP
        elif 'inputpp' in namelist_names:
            # Both pp.x and cppp.x, pprism.x use &inputpp
            # Check for module-specific indicators
            inputpp_nl = self.get_namelist('inputpp')
            if inputpp_nl:
                # cppp.x and pprism.x may have specific parameters
                # For now, check if there are other indicators
                if 'plot' in namelist_names:
                    # pprism.x uses both &inputpp and &plot
                    return QEModule.PPRISM
            # Default to pp.x
            return QEModule.PP
        elif 'inputgipaw' in namelist_names:
            return QEModule.GIPAW
        elif 'path' in namelist_names:
            return QEModule.NEB
        elif 'cond' in namelist_names:
            return QEModule.PWCOND
        elif 'oscdft_et_namelist' in namelist_names:
            return QEModule.OSCDFT_ET
        elif 'oscdft_pp_namelist' in namelist_names:
            return QEModule.OSCDFT_PP
        elif 'interpolation' in namelist_names:
            return QEModule.BAND_INTERPOLATION
        elif 'plot' in namelist_names:
            # ppacf.x uses &plot namelist
            if 'ppacf' in str(self).lower() or any('ppacf' in str(card) for card in self.cards):
                return QEModule.PPACF
            # Could be other plot modules, but ppacf is the main one
            return QEModule.PPACF
        elif 'input' in namelist_names:
            # q2r.x, matdyn.x, ld1.x, postahc.x, dynmat.x, d3hess.x all use &input namelist
            # Check for module-specific parameters
            input_nl = self.get_namelist('input')
            if input_nl:
                # Check for ld1.x specific parameters (atomic calculations)
                # ld1.x typically has atom, zed, xmin, dx, etc.
                if input_nl.get('atom') is not None or input_nl.get('zed') is not None:
                    return QEModule.LD1
                
                # Check for postahc.x, dynmat.x, d3hess.x specific parameters
                # These modules are typically used after ph.x calculations
                # postahc.x: typically has fildyn, filq, etc.
                # dynmat.x: typically has fildyn, asr, etc.
                # d3hess.x: typically has fildyn, etc.
                # For now, we'll need additional context to distinguish them
                # Default to dynmat.x if we can't determine
                
                # q2r.x typically has flfrc parameter (force constant file)
                # matdyn.x typically has flfrc parameter too, but also has dos, flfrq, etc.
                if input_nl.get('flfrc') is not None:
                    # Check for matdyn-specific parameters
                    if input_nl.get('dos') is not None or input_nl.get('flfrq') is not None:
                        return QEModule.MATDYN
                    # q2r.x typically has fildyn parameter (dynamical matrix file)
                    elif input_nl.get('fildyn') is not None:
                        return QEModule.Q2R
                    # Default to q2r if we have flfrc but no matdyn indicators
                    # (q2r writes .fc file that matdyn reads)
                    return QEModule.Q2R
            # If we have &input but can't determine, check for ld1-specific cards
            # ld1.x may have ATOMIC_SPECIES or other atomic-specific cards
            if any(card.card_type == QECardType.ATOMIC_SPECIES for card in self.cards):
                # Could be ld1.x or pw.x, but if we have &input, more likely ld1.x
                return QEModule.LD1
            # Default to q2r for &input namelist (most common)
            return QEModule.Q2R
        elif 'bands' in namelist_names:
            # bands.x uses &BANDS namelist
            return QEModule.BANDS
        elif 'dos' in namelist_names:
            # dos.x uses &DOS namelist
            return QEModule.DOS
        elif 'projwfc' in namelist_names:
            # projwfc.x uses &PROJWFC namelist
            return QEModule.PROJWFC
        elif any(name in namelist_names for name in ['control', 'system', 'electrons']):
            # pw.x, cp.x use these namelists
            # Check for module-specific indicators
            control = self.get_namelist('control')
            if control:
                calculation = control.get('calculation', '').lower()
                # cp.x uses 'cp' or 'cp-wf' calculation type
                if 'cp' in calculation:
                    return QEModule.CP
            # Default to pw.x for standard namelists
            return QEModule.PW
        
        return QEModule.UNKNOWN


class QEInputParser:
    """Parser for Quantum ESPRESSO input files."""
    
    # Regex patterns
    NAMELIST_PATTERN = re.compile(r'^\s*&(\w+)', re.IGNORECASE)  # Allow leading whitespace
    NAMELIST_END_PATTERN = re.compile(r'/\s*$')
    CARD_PATTERN = re.compile(r'^\s*([A-Z_]+)\s*(\([^)]+\))?', re.IGNORECASE)  # Allow leading whitespace
    COMMENT_PATTERN = re.compile(r'!.*$')
    KEY_VALUE_PATTERN = re.compile(r'(\w+(?:\([^)]+\))?)\s*=\s*(.+?)(?:\s*,\s*|$)')
    SEPARATOR_PATTERN = re.compile(r'^---+\s*$')  # Separator lines like "---"
    
    @staticmethod
    def parse_value(value_str: str) -> Any:
        """
        Parse a QE parameter value.
        
        Handles:
        - Strings: 'value' or "value"
        - Numbers: integers and floats
        - Arrays: (1, 2, 3) or 1, 2, 3
        - Booleans: .true., .false., true, false
        """
        value_str = value_str.strip()
        
        # Remove trailing comma
        if value_str.endswith(','):
            value_str = value_str[:-1]
        
        # String values
        if value_str.startswith("'") and value_str.endswith("'"):
            return value_str[1:-1]
        if value_str.startswith('"') and value_str.endswith('"'):
            return value_str[1:-1]
        
        # Boolean values
        if value_str.lower() in ['.true.', 'true', 't']:
            return True
        if value_str.lower() in ['.false.', 'false', 'f']:
            return False
        
        # Array values
        if value_str.startswith('(') and value_str.endswith(')'):
            # Parse array like (1, 2, 3) or (1.0, 2.0, 3.0)
            array_str = value_str[1:-1]
            values = []
            for item in array_str.split(','):
                item = item.strip()
                try:
                    if '.' in item:
                        values.append(float(item))
                    else:
                        values.append(int(item))
                except ValueError:
                    values.append(item)
            return values
        
        # Handle Fortran double precision format (1.0d-8 -> 1.0e-8)
        # Also handle uppercase D
        if 'd' in value_str.lower():
            try:
                # Replace 'd' or 'D' with 'e' for Python float parsing
                float_str = value_str.lower().replace('d', 'e')
                return float(float_str)
            except ValueError:
                pass
        
        # Try to parse as number (including scientific notation like 1e-08)
        try:
            # Check if it looks like a number (including scientific notation)
            if 'e' in value_str.lower() or 'E' in value_str:
                return float(value_str)
            elif '.' in value_str:
                return float(value_str)
            else:
                return int(value_str)
        except ValueError:
            # Return as string if all else fails
            return value_str
    
    @staticmethod
    def parse_namelist(lines: List[str], start_idx: int) -> Tuple[QENamelist, int]:
        """
        Parse a namelist starting at start_idx.
        
        Returns:
            Tuple of (QENamelist, next_line_index)
        """
        # Extract namelist name
        match = QEInputParser.NAMELIST_PATTERN.match(lines[start_idx])
        if not match:
            raise ValueError(f"Invalid namelist at line {start_idx + 1}")
        
        name = match.group(1)
        namelist = QENamelist(name=name)
        
        # Parse parameters
        i = start_idx + 1
        current_line = ""
        current_comment = ""
        
        while i < len(lines):
            line = lines[i].strip()
            original_line = lines[i]  # Keep original for comment extraction
            
            # Extract inline comments (preserve them)
            comment_match = QEInputParser.COMMENT_PATTERN.search(line)
            inline_comment = ""
            if comment_match:
                inline_comment = comment_match.group(0).strip()  # Keep the '!' and comment text
                line = line[:comment_match.start()].strip()
            
            # Check for namelist end
            if QEInputParser.NAMELIST_END_PATTERN.match(line):
                # Parse any remaining parameters in current_line
                if current_line:
                    QEInputParser._parse_parameters(current_line, namelist, comment=inline_comment)
                break
            
            # Accumulate line (parameters can span multiple lines)
            if current_line:
                current_line += " " + line
            else:
                current_line = line
            
            # Try to parse parameters if line ends with comma or we have complete statements
            if current_line and (current_line.endswith(',') or '=' in current_line):
                # Pass inline comment to parameter parser
                QEInputParser._parse_parameters(current_line, namelist, comment=inline_comment)
                current_line = ""
                inline_comment = ""  # Reset after parsing
            
            i += 1
        
        return namelist, i + 1
    
    @staticmethod
    def _parse_parameters(line: str, namelist: QENamelist, comment: str = ""):
        """Parse parameter assignments from a line.
        
        Args:
            line: Line containing parameter assignments
            namelist: QENamelist to add parameters to
            comment: Optional inline comment to associate with the last parameter
        """
        # Remove trailing comma
        line = line.rstrip(',').strip()
        if not line:
            return
        
        # Extract inline comment if present
        comment_match = QEInputParser.COMMENT_PATTERN.search(line)
        inline_comment = ""
        if comment_match:
            inline_comment = comment_match.group(0).strip()  # Keep '!' and comment text
            line = line[:comment_match.start()].strip()
        
        # Use provided comment if no inline comment found
        if not inline_comment and comment:
            inline_comment = comment
        
        # Split by commas, but be careful with arrays and strings
        parts = []
        current = ""
        in_string = False
        string_char = None
        paren_depth = 0
        
        for char in line:
            if char in ["'", '"'] and not in_string:
                in_string = True
                string_char = char
                current += char
            elif char == string_char and in_string:
                in_string = False
                string_char = None
                current += char
            elif char == '(' and not in_string:
                paren_depth += 1
                current += char
            elif char == ')' and not in_string:
                paren_depth -= 1
                current += char
            elif char == ',' and not in_string and paren_depth == 0:
                if current.strip():
                    parts.append(current.strip())
                current = ""
            else:
                current += char
        
        if current.strip():
            parts.append(current.strip())
        
        # Parse each part
        for i, part in enumerate(parts):
            match = QEInputParser.KEY_VALUE_PATTERN.match(part)
            if match:
                key = match.group(1)
                value_str = match.group(2)
                value = QEInputParser.parse_value(value_str)
                # Associate comment with the last parameter (most common case)
                if i == len(parts) - 1 and inline_comment:
                    namelist.set(key, value, comment=inline_comment)
                else:
                    namelist.set(key, value)
    
    @staticmethod
    def parse_card(lines: List[str], start_idx: int) -> Tuple[QECard, int]:
        """
        Parse a card starting at start_idx.
        
        Returns:
            Tuple of (QECard, next_line_index)
        """
        line = lines[start_idx].strip()
        
        # Remove comments
        comment_match = QEInputParser.COMMENT_PATTERN.search(line)
        if comment_match:
            line = line[:comment_match.start()].strip()
        
        match = QEInputParser.CARD_PATTERN.match(line)
        if not match:
            raise ValueError(f"Invalid card at line {start_idx + 1}: {line}")
        
        card_name = match.group(1).upper()
        option = match.group(2)
        if option:
            # Remove brackets but remember the type for K_POINTS
            option = option.strip('(){}')
        else:
            # Check if option is on the same line after card name (e.g., "ATOMIC_POSITIONS alat")
            remaining = line[match.end():].strip()
            if remaining and not remaining.startswith('!'):
                # Check if it's in {} format (for K_POINTS)
                if remaining.startswith('{') and remaining.endswith('}'):
                    option = remaining[1:-1].strip()
                else:
                    # Treat remaining text as option if it's a single word
                    parts = remaining.split()
                    if len(parts) == 1 and not parts[0].startswith('!'):
                        option = parts[0]
        
        # Map card name to enum
        try:
            card_type = QECardType[card_name]
        except KeyError:
            # For unknown card types, we'll need to handle them dynamically
            # For now, raise an error to catch missing card types
            raise ValueError(f"Unknown card type: {card_name}. Please add to QECardType enum.")
        
        card = QECard(card_type=card_type, option=option)
        
        # Parse card data
        i = start_idx + 1
        
        # Special handling for different card types
        if card_type == QECardType.K_POINTS:
            # K_POINTS can be automatic, crystal/crystal_b, gamma, or without option
            if option and 'gamma' in option.lower():
                # Gamma point - no data lines needed, but check next line for new card
                if i < len(lines):
                    next_line = lines[i].strip()
                    if next_line:
                        card_match = QEInputParser.CARD_PATTERN.match(next_line)
                        if card_match:
                            card_name = card_match.group(1).upper()
                            try:
                                QECardType[card_name]
                                # This is a new card, don't read data - i stays the same
                                pass
                            except KeyError:
                                pass
            elif option and 'automatic' in option.lower():
                # Format: nk1 nk2 nk3 k1 k2 k3
                if i < len(lines):
                    data_line = lines[i].strip()
                    if data_line:
                        # Check if this is actually a new card
                        card_match = QEInputParser.CARD_PATTERN.match(data_line)
                        if card_match:
                            card_name = card_match.group(1).upper()
                            try:
                                QECardType[card_name]
                                # This is a new card, don't read data - i stays the same
                                pass
                            except KeyError:
                                card.add_line(data_line.split())
                                i += 1
                        else:
                            card.add_line(data_line.split())
                            i += 1
            elif option and ('crystal' in option.lower() or 'tpiba' in option.lower()):
                # Format: n_points, then n_points lines of k-points
                if i < len(lines):
                    try:
                        n_points = int(lines[i].strip())
                        card.add_line([n_points])
                        i += 1
                        for _ in range(n_points):
                            if i < len(lines):
                                k_line = lines[i].strip()
                                if not k_line:
                                    i += 1
                                    continue
                                # Remove comments but keep the line
                                comment_match = QEInputParser.COMMENT_PATTERN.search(k_line)
                                if comment_match:
                                    k_line = k_line[:comment_match.start()].strip()
                                if k_line:
                                    card.add_line(k_line.split())
                                i += 1
                    except (ValueError, IndexError):
                        # If first line is not a number, treat as k-point coordinates
                        pass
            else:
                # No option or unknown option - try to parse as either format
                if i < len(lines):
                    first_line = lines[i].strip()
                    if first_line:
                        # Check if this is actually a new card
                        card_match = QEInputParser.CARD_PATTERN.match(first_line)
                        if card_match:
                            card_name = card_match.group(1).upper()
                            try:
                                QECardType[card_name]
                                # This is a new card, don't read data - i stays the same
                                # The outer loop will handle it
                                pass
                            except KeyError:
                                pass
                        
                        parts = first_line.split()
                        # Check if first line is a single number (n_points format)
                        if len(parts) == 1:
                            try:
                                n_points = int(parts[0])
                                card.add_line([n_points])
                                i += 1
                                # Read n_points lines of k-points
                                for _ in range(n_points):
                                    if i >= len(lines):
                                        break
                                    k_line = lines[i].strip()
                                    if not k_line:
                                        i += 1
                                        continue
                                    # Check if this is a new card
                                    card_match = QEInputParser.CARD_PATTERN.match(k_line)
                                    if card_match:
                                        card_name = card_match.group(1).upper()
                                        try:
                                            QECardType[card_name]
                                            # This is a new card, stop reading
                                            break
                                        except KeyError:
                                            pass
                                    # Remove comments but keep the line
                                    comment_match = QEInputParser.COMMENT_PATTERN.search(k_line)
                                    if comment_match:
                                        k_line = k_line[:comment_match.start()].strip()
                                    if k_line:
                                        card.add_line(k_line.split())
                                    i += 1
                            except ValueError:
                                # Not a number, treat as automatic format
                                card.add_line(parts)
                                i += 1
                        elif len(parts) >= 3:
                            # Multiple numbers (likely automatic format: nk1 nk2 nk3 k1 k2 k3)
                            card.add_line(parts)
                            i += 1
                        else:
                            # Try to read as n_points format anyway
                            try:
                                n_points = int(parts[0])
                                card.add_line([n_points])
                                i += 1
                                for _ in range(n_points):
                                    if i >= len(lines):
                                        break
                                    k_line = lines[i].strip()
                                    if not k_line:
                                        i += 1
                                        continue
                                    # Check if this is a new card
                                    card_match = QEInputParser.CARD_PATTERN.match(k_line)
                                    if card_match:
                                        card_name = card_match.group(1).upper()
                                        try:
                                            QECardType[card_name]
                                            # This is a new card, stop reading
                                            break
                                        except KeyError:
                                            pass
                                    comment_match = QEInputParser.COMMENT_PATTERN.search(k_line)
                                    if comment_match:
                                        k_line = k_line[:comment_match.start()].strip()
                                    if k_line:
                                        card.add_line(k_line.split())
                                    i += 1
                            except (ValueError, IndexError):
                                # Fallback: just add the line
                                card.add_line(parts)
                                i += 1
        elif card_type == QECardType.ATOMIC_SPECIES:
            # Format: element mass pseudopotential_file
            while i < len(lines):
                data_line = lines[i].strip()
                if not data_line:
                    i += 1
                    continue
                # Check if this is a new namelist or card (but not a single letter which could be element)
                if data_line.startswith('&'):
                    break
                # Check if this is a known card type (not just any uppercase word)
                card_match = QEInputParser.CARD_PATTERN.match(data_line)
                if card_match:
                    card_name = card_match.group(1).upper()
                    try:
                        QECardType[card_name]
                        # This is a real card, stop reading data
                        break
                    except KeyError:
                        # Not a known card, treat as data line
                        pass
                # Remove comments
                comment_match = QEInputParser.COMMENT_PATTERN.search(data_line)
                if comment_match:
                    data_line = data_line[:comment_match.start()].strip()
                if data_line:
                    card.add_line(data_line.split())
                i += 1
        elif card_type == QECardType.ATOMIC_POSITIONS:
            # Format: element x y z [if_pos(1) if_pos(2) if_pos(3)]
            while i < len(lines):
                data_line = lines[i].strip()
                if not data_line:
                    i += 1
                    continue
                # Check if this is a new namelist
                if data_line.startswith('&'):
                    break
                # Check if this is a known card type (not just any uppercase word)
                card_match = QEInputParser.CARD_PATTERN.match(data_line)
                if card_match:
                    card_name = card_match.group(1).upper()
                    try:
                        QECardType[card_name]
                        # This is a real card, stop reading data
                        break
                    except KeyError:
                        # Not a known card, treat as data line
                        pass
                # Remove comments
                comment_match = QEInputParser.COMMENT_PATTERN.search(data_line)
                if comment_match:
                    data_line = data_line[:comment_match.start()].strip()
                if data_line:
                    parts = data_line.split()
                    if len(parts) >= 4:
                        card.add_line(parts)
                i += 1
        elif card_type == QECardType.CELL_PARAMETERS:
            # Format: 3 lines of cell vectors
            for _ in range(3):
                if i < len(lines):
                    data_line = lines[i].strip()
                    if not data_line or data_line.startswith('&') or QEInputParser.CARD_PATTERN.match(data_line):
                        break
                    # Remove comments
                    comment_match = QEInputParser.COMMENT_PATTERN.search(data_line)
                    if comment_match:
                        data_line = data_line[:comment_match.start()].strip()
                    if data_line:
                        card.add_line([float(x) for x in data_line.split()])
                    i += 1
        else:
            # Generic card - read until next namelist or card
            while i < len(lines):
                data_line = lines[i].strip()
                if not data_line:
                    i += 1
                    continue
                if data_line.startswith('&') or QEInputParser.CARD_PATTERN.match(data_line):
                    break
                # Remove comments
                comment_match = QEInputParser.COMMENT_PATTERN.search(data_line)
                if comment_match:
                    data_line = data_line[:comment_match.start()].strip()
                if data_line:
                    card.add_line(data_line)
                i += 1
        
        return card, i
    
    @classmethod
    def parse_file(cls, filepath: Union[str, Path]) -> QEInput:
        """
        Parse a QE input file.
        
        Args:
            filepath: Path to QE input file
            
        Returns:
            QEInput object
        """
        filepath = Path(filepath)
        content = filepath.read_text()
        return cls.parse_string(content)
    
    @classmethod
    def parse_string(cls, content: str) -> QEInput:
        """
        Parse QE input from string.
        
        Args:
            content: QE input file content as string
            
        Returns:
            QEInput object
        """
        qe_input = QEInput()
        lines = content.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i]
            line_stripped = line.strip()
            
            # Skip empty lines
            if not line_stripped:
                i += 1
                continue
            
            # Check for separator lines (---)
            if cls.SEPARATOR_PATTERN.match(line_stripped):
                qe_input.comments.append((i, line_stripped))
                i += 1
                continue
            
            # Check for comments
            if line_stripped.startswith('!'):
                qe_input.comments.append((i, line_stripped))
                i += 1
                continue
            
            # Check for namelist (match on original line to preserve position)
            if cls.NAMELIST_PATTERN.match(line):
                namelist, next_idx = cls.parse_namelist(lines, i)
                qe_input.namelists.append(namelist)
                i = next_idx
                continue
            
            # Check for card (match on original line to preserve position)
            # Use stripped line for matching to handle leading whitespace
            card_match = cls.CARD_PATTERN.match(line_stripped)
            if card_match:
                card_name = card_match.group(1).upper()
                # Only parse if it's a known card type
                try:
                    QECardType[card_name]
                    # Use original line for parsing to preserve exact format
                    card, next_idx = cls.parse_card(lines, i)
                    qe_input.cards.append(card)
                    i = next_idx
                    continue
                except KeyError:
                    # Not a card, might be data line - continue
                    pass
            
            # Unrecognized line - might be continuation or comment
            i += 1
        
        # Detect module type
        qe_input.module = qe_input.detect_module()
        
        return qe_input


class QEInputGenerator:
    """Generator for Quantum ESPRESSO input files."""
    
    @staticmethod
    def format_value(value: Any) -> str:
        """Format a Python value as QE input value."""
        if isinstance(value, bool):
            return '.true.' if value else '.false.'
        elif isinstance(value, str):
            # For paths (like pseudo_dir), QE typically uses quoted strings
            # However, some paths like './' or '../../pseudo' may work without quotes
            # To be safe, always quote strings unless they are simple relative paths
            # Special case: simple relative paths like './' should be quoted for consistency
            # Actually, QE accepts both, but let's use quotes for safety
            return f"'{value}'"
        elif isinstance(value, (list, tuple)):
            # For arrays, format each element and join
            formatted = ', '.join(str(QEInputGenerator.format_value(v)).strip("'\"") for v in value)
            return f'({formatted})'
        else:
            return str(value)
    
    @staticmethod
    def generate_namelist(namelist: QENamelist, indent: str = "    ") -> str:
        """Generate namelist string, preserving inline comments."""
        lines = [f"&{namelist.name}"]
        
        for key, value in namelist.parameters.items():
            formatted_value = QEInputGenerator.format_value(value)
            # Add inline comment if present
            comment = namelist.get_comment(key)
            if comment:
                lines.append(f"{indent}{key} = {formatted_value}  {comment}")
            else:
                lines.append(f"{indent}{key} = {formatted_value}")
        
        lines.append("/")
        return '\n'.join(lines)
    
    @staticmethod
    def generate_card(card: QECard) -> str:
        """Generate card string."""
        lines = []
        
        # Card header
        header = card.card_type.value
        if card.option:
            # Use {} for K_POINTS options like {gamma}, {automatic}, {crystal_b}
            # Use () for other cards like ATOMIC_POSITIONS (alat)
            if card.card_type == QECardType.K_POINTS:
                header += f" {{{card.option}}}"
            else:
                header += f" ({card.option})"
        lines.append(header)
        
        # Card data
        if card.data:
            for line_data in card.data:
                if isinstance(line_data, list):
                    # Join list elements with spaces
                    lines.append("  " + " ".join(str(x) for x in line_data))
                else:
                    # For string data, add as-is
                    lines.append("  " + str(line_data))
        else:
            # Empty card - just the header
            pass
        
        return '\n'.join(lines)
    
    @classmethod
    def generate(cls, qe_input: QEInput) -> str:
        """
        Generate QE input file string from QEInput object.
        
        Args:
            qe_input: QEInput object
            
        Returns:
            QE input file content as string
        """
        lines = []
        
        # Generate namelists
        for namelist in qe_input.namelists:
            lines.append(cls.generate_namelist(namelist))
            lines.append("")  # Empty line between sections
        
        # Generate cards
        for card in qe_input.cards:
            lines.append(cls.generate_card(card))
            lines.append("")  # Empty line between sections
        
        # Remove trailing empty lines
        while lines and not lines[-1].strip():
            lines.pop()
        
        return '\n'.join(lines)
    
    @classmethod
    def write_file(cls, qe_input: QEInput, filepath: Union[str, Path]):
        """
        Write QE input to file.
        
        Args:
            qe_input: QEInput object
            filepath: Output file path
        """
        filepath = Path(filepath)
        content = cls.generate(qe_input)
        filepath.write_text(content)

