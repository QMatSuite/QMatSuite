"""
Quantum ESPRESSO input file parser and generator.

This module provides bidirectional conversion between QE input files (.in)
and structured Python data (namelists and cards).

Supports multiple QE modules:
- pw.x: &CONTROL, &system, &ELECTRONS, &IONS, &CELL
- ph.x: &inputph
- pp.x: &inputpp
- gipaw.x: &inputgipaw
- neb.x: &PATH (plus embedded pw.x input)
- bands.x, dos.x, projwfc.x: Similar to pw.x
- And other QE modules
"""

import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum


class QEModule(Enum):
    """Quantum ESPRESSO modules."""
    PW = "pw"  # pw.x - main DFT code
    PH = "ph"  # ph.x - phonon calculations
    PP = "pp"  # pp.x - post-processing
    GIPAW = "gipaw"  # gipaw.x - NMR/EPR calculations
    NEB = "neb"  # neb.x - nudged elastic band
    BANDS = "bands"  # bands.x - band structure
    DOS = "dos"  # dos.x - density of states
    PROJWFC = "projwfc"  # projwfc.x - projected wavefunctions
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
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a parameter value."""
        return self.parameters.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set a parameter value."""
        self.parameters[key] = value


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
    
    def detect_module(self) -> QEModule:
        """
        Detect QE module from namelist names.
        
        Returns:
            Detected QE module
        """
        namelist_names = {nl.name.lower() for nl in self.namelists}
        
        # Module-specific namelist detection
        if 'inputph' in namelist_names:
            return QEModule.PH
        elif 'inputpp' in namelist_names:
            return QEModule.PP
        elif 'inputgipaw' in namelist_names:
            return QEModule.GIPAW
        elif 'path' in namelist_names:
            return QEModule.NEB
        elif any(name in namelist_names for name in ['control', 'system', 'electrons']):
            # pw.x, bands.x, dos.x, projwfc.x all use these namelists
            # Check for module-specific indicators
            control = self.get_namelist('control')
            if control:
                calculation = control.get('calculation', '').lower()
                if 'bands' in calculation:
                    return QEModule.BANDS
                elif 'dos' in calculation:
                    return QEModule.DOS
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
        
        # Try to parse as number
        try:
            if '.' in value_str:
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
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Remove comments
            comment_match = QEInputParser.COMMENT_PATTERN.search(line)
            if comment_match:
                line = line[:comment_match.start()].strip()
            
            # Check for namelist end
            if QEInputParser.NAMELIST_END_PATTERN.match(line):
                # Parse any remaining parameters in current_line
                if current_line:
                    QEInputParser._parse_parameters(current_line, namelist)
                break
            
            # Accumulate line (parameters can span multiple lines)
            if current_line:
                current_line += " " + line
            else:
                current_line = line
            
            # Try to parse parameters if line ends with comma or we have complete statements
            if current_line and (current_line.endswith(',') or '=' in current_line):
                QEInputParser._parse_parameters(current_line, namelist)
                current_line = ""
            
            i += 1
        
        return namelist, i + 1
    
    @staticmethod
    def _parse_parameters(line: str, namelist: QENamelist):
        """Parse parameter assignments from a line."""
        # Remove trailing comma
        line = line.rstrip(',').strip()
        if not line:
            return
        
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
        for part in parts:
            match = QEInputParser.KEY_VALUE_PATTERN.match(part)
            if match:
                key = match.group(1)
                value_str = match.group(2)
                value = QEInputParser.parse_value(value_str)
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
            # Always quote strings in QE input
            return f"'{value}'"
        elif isinstance(value, (list, tuple)):
            # For arrays, format each element and join
            formatted = ', '.join(str(QEInputGenerator.format_value(v)).strip("'\"") for v in value)
            return f'({formatted})'
        else:
            return str(value)
    
    @staticmethod
    def generate_namelist(namelist: QENamelist, indent: str = "    ") -> str:
        """Generate namelist string."""
        lines = [f"&{namelist.name}"]
        
        for key, value in namelist.parameters.items():
            formatted_value = QEInputGenerator.format_value(value)
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

