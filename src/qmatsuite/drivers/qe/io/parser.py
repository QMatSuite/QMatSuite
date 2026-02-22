"""
QE input parser converting raw text into QEInput objects.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from qmatsuite.drivers.qe.io.model import (
    QECard,
    QECardType,
    QEInput,
    QEModule,
    QENamelist,
)
from qmatsuite.drivers.qe.io.generator import QEInputGenerator

__all__ = ["QEInputParser"]


class QEInputParser:
    """Parser for Quantum ESPRESSO input files."""

    NAMELIST_PATTERN = re.compile(r"^\s*&(\w+)", re.IGNORECASE)
    NAMELIST_END_PATTERN = re.compile(r"/\s*$")
    CARD_PATTERN = re.compile(r"^\s*([A-Z_]+)\s*(\([^)]+\))?", re.IGNORECASE)
    COMMENT_PATTERN = re.compile(r"!.*$")
    KEY_VALUE_PATTERN = re.compile(
        r"(\w+(?:\([^)]+\))?)\s*=\s*(.+?)(?:\s*,\s*|$)"
    )
    PARAMETER_PATTERN = re.compile(
        r"(\w+(?:\([^)]+\))?)\s*=\s*("
        r"'(?:[^'\\]|\\.)*'|"
        r'"(?:[^"\\]|\\.)*"|'
        r"[^,\s]+(?:\([^)]+\))?|"
        r"[^,\s]+"
        r")(?:\s*,\s*|\s+|$)",
        re.IGNORECASE,
    )
    SEPARATOR_PATTERN = re.compile(r"^---+\s*$")
    @classmethod
    def _is_card_header(cls, line: str) -> bool:
        """Return True if the line starts with a known QE card."""
        match = cls.CARD_PATTERN.match(line.strip())
        if not match:
            return False
        card_name = match.group(1).upper()
        return card_name in QECardType.__members__


    @staticmethod
    def _strip_inline_comment(line: str) -> str:
        match = QEInputParser.COMMENT_PATTERN.search(line)
        if match:
            return line[: match.start()].rstrip()
        return line

    @staticmethod
    def parse_value(value_str: str) -> Any:
        value_str = value_str.strip()
        if value_str.endswith(","):
            value_str = value_str[:-1]

        if value_str.startswith("'") and value_str.endswith("'"):
            return value_str[1:-1]
        if value_str.startswith('"') and value_str.endswith('"'):
            return value_str[1:-1]

        lower = value_str.lower()
        if lower in [".true.", "true", "t"]:
            return True
        if lower in [".false.", "false", "f"]:
            return False

        if value_str.startswith("(") and value_str.endswith(")"):
            array_str = value_str[1:-1]
            values = []
            for item in array_str.split(","):
                item = item.strip()
                try:
                    values.append(float(item) if "." in item else int(item))
                except ValueError:
                    values.append(item)
            return values

        if "d" in lower:
            try:
                return float(lower.replace("d", "e"))
            except ValueError:
                pass
        try:
            if "e" in lower:
                return float(value_str)
            if "." in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            return value_str

    @staticmethod
    def parse_namelist(lines: List[str], start_idx: int) -> Tuple[QENamelist, int]:
        match = QEInputParser.NAMELIST_PATTERN.match(lines[start_idx])
        if not match:
            raise ValueError(f"Invalid namelist at line {start_idx + 1}")

        name = match.group(1)
        namelist = QENamelist(name=name)

        i = start_idx + 1
        parameter_lines: List[str] = []

        while i < len(lines):
            original_line = lines[i]
            stripped_line = QEInputParser._strip_inline_comment(original_line).strip()

            if "/" in stripped_line:
                in_string = False
                string_char = None
                slash_pos = -1

                for j, char in enumerate(original_line):
                    if char in ["'", '"'] and not in_string:
                        in_string = True
                        string_char = char
                    elif char == string_char and in_string:
                        in_string = False
                        string_char = None
                    elif char == "/" and not in_string:
                        slash_pos = j
                        break

                if slash_pos >= 0:
                    before_slash = original_line[:slash_pos].strip()
                    before_slash = QEInputParser._strip_inline_comment(before_slash)
                    if before_slash:
                        parameter_lines.append(before_slash)
                    i += 1
                    break

            if not stripped_line:
                i += 1
                continue

            parameter_lines.append(stripped_line)
            i += 1

        if parameter_lines:
            QEInputParser._parse_parameters(parameter_lines, namelist)

        return namelist, i

    @staticmethod
    def _parse_parameters(parameter_lines: List[str], namelist: QENamelist) -> None:
        for line in parameter_lines:
            if not line.strip():
                continue
            parts = QEInputParser._split_by_commas(line)
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                match = QEInputParser.KEY_VALUE_PATTERN.match(part)
                if match:
                    key = match.group(1)
                    value_str = match.group(2).strip()
                    value = QEInputParser.parse_value(value_str)
                    namelist.set(key, value)

    @staticmethod
    def _split_by_commas(line: str) -> List[str]:
        parts: List[str] = []
        current = ""
        in_string = False
        string_char = None
        paren_depth = 0

        i = 0
        while i < len(line):
            char = line[i]
            if char in ["'", '"'] and not in_string:
                in_string = True
                string_char = char
                current += char
            elif char == string_char and in_string:
                in_string = False
                string_char = None
                current += char
            elif char == "(" and not in_string:
                paren_depth += 1
                current += char
            elif char == ")" and not in_string:
                paren_depth -= 1
                current += char
            elif char == "," and not in_string and paren_depth == 0:
                if current.strip():
                    parts.append(current.strip())
                current = ""
            else:
                current += char
            i += 1

        if current.strip():
            parts.append(current.strip())
        return parts

    @classmethod
    def parse_card(cls, lines: List[str], start_idx: int) -> Tuple[QECard, int]:
        line = cls._strip_inline_comment(lines[start_idx]).strip()
        match = cls.CARD_PATTERN.match(line)
        if not match:
            raise ValueError(f"Invalid card at line {start_idx + 1}: {line}")

        card_name = match.group(1).upper()
        option = match.group(2)
        if option:
            option = option.strip("(){}")
        else:
            remaining = line[match.end() :].strip()
            if remaining and not remaining.startswith("!"):
                if remaining.startswith("{") and remaining.endswith("}"):
                    option = remaining[1:-1].strip()
                else:
                    parts = remaining.split()
                    if len(parts) == 1 and not parts[0].startswith("!"):
                        option = parts[0]

        try:
            card_type = QECardType[card_name]
        except KeyError as exc:
            raise ValueError(f"Unknown card type: {card_name}") from exc

        card = QECard(card_type=card_type, option=option)
        i = start_idx + 1

        if card_type == QECardType.K_POINTS:
            i = cls._parse_k_points(lines, i, card)
        elif card_type == QECardType.ATOMIC_SPECIES:
            i = cls._parse_atomic_species(lines, i, card)
        elif card_type == QECardType.ATOMIC_POSITIONS:
            i = cls._parse_atomic_positions(lines, i, card)
        elif card_type == QECardType.CELL_PARAMETERS:
            i = cls._parse_cell_parameters(lines, i, card)
        else:
            while i < len(lines):
                data_line = cls._strip_inline_comment(lines[i]).strip()
                if not data_line:
                    i += 1
                    continue
                if data_line.startswith("&") or cls._is_card_header(data_line):
                    break
                card.add_line(data_line)
                i += 1

        return card, i

    @classmethod
    def _parse_k_points(cls, lines: List[str], idx: int, card: QECard) -> int:
        i = idx
        option = card.option or ""
        if "gamma" in option.lower():
            return i
        if "automatic" in option.lower():
            if i < len(lines):
                line = cls._strip_inline_comment(lines[i]).strip()
                if line:
                    card.add_line(line.split())
                    i += 1
            return i
        if any(opt in option.lower() for opt in ["crystal", "crystal_b", "tpiba"]):
            if i < len(lines):
                try:
                    n_points = int(lines[i].strip())
                    card.add_line([n_points])
                    i += 1
                    for _ in range(n_points):
                        if i >= len(lines):
                            break
                        k_line = cls._strip_inline_comment(lines[i]).strip()
                        if not k_line:
                            i += 1
                            continue
                        if cls._is_card_header(k_line):
                            break
                        card.add_line(k_line.split())
                        i += 1
                except ValueError:
                    pass
            return i
        # Generic handling
        if i < len(lines):
            first_line = cls._strip_inline_comment(lines[i]).strip()
            if first_line:
                parts = first_line.split()
                if len(parts) == 1:
                    try:
                        n_points = int(parts[0])
                        card.add_line([n_points])
                        i += 1
                        for _ in range(n_points):
                            if i >= len(lines):
                                break
                            k_line = cls._strip_inline_comment(lines[i]).strip()
                            if not k_line:
                                i += 1
                                continue
                            if cls._is_card_header(k_line):
                                break
                            card.add_line(k_line.split())
                            i += 1
                        return i
                    except ValueError:
                        pass
                card.add_line(parts)
                i += 1
        return i

    @classmethod
    def _parse_atomic_species(cls, lines: List[str], idx: int, card: QECard) -> int:
        i = idx
        while i < len(lines):
            data_line = cls._strip_inline_comment(lines[i]).strip()
            if not data_line:
                i += 1
                continue
            if data_line.startswith("&"):
                break
            if cls._is_card_header(data_line):
                break
            card.add_line(data_line.split())
            i += 1
        return i

    @classmethod
    def _parse_atomic_positions(cls, lines: List[str], idx: int, card: QECard) -> int:
        i = idx
        while i < len(lines):
            data_line = cls._strip_inline_comment(lines[i]).strip()
            if not data_line:
                i += 1
                continue
            if data_line.startswith("&"):
                break
            if cls._is_card_header(data_line):
                break
            parts = data_line.split()
            if len(parts) >= 4:
                card.add_line(parts)
            i += 1
        return i

    @classmethod
    def _parse_cell_parameters(cls, lines: List[str], idx: int, card: QECard) -> int:
        i = idx
        for _ in range(3):
            if i >= len(lines):
                break
            data_line = cls._strip_inline_comment(lines[i]).strip()
            if not data_line:
                i += 1
                continue
            if data_line.startswith("&") or cls._is_card_header(data_line):
                break
            card.add_line([float(x) for x in data_line.split()])
            i += 1
        return i

    @classmethod
    def parse_file(cls, filepath: Path) -> QEInput:
        return cls.parse_string(Path(filepath).read_text())

    @classmethod
    def parse_string(cls, content: str) -> QEInput:
        qe_input = QEInput()
        lines = content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or cls.SEPARATOR_PATTERN.match(line):
                i += 1
                continue
            if line.startswith("&"):
                namelist, next_idx = cls.parse_namelist(lines, i)
                qe_input.namelists.append(namelist)
                i = next_idx
                continue
            if cls._is_card_header(line):
                card, next_idx = cls.parse_card(lines, i)
                qe_input.cards.append(card)
                i = next_idx
                continue
            qe_input.extra_data_lines.append(line)
            i += 1

        if qe_input.namelists:
            qe_input.module = qe_input.detect_module()
        else:
            qe_input.module = QEModule.UNKNOWN
        return qe_input

    @classmethod
    def roundtrip_file(
        cls,
        input_file: Path,
        output_file: Optional[Path] = None,
    ) -> QEInput:
        """
        Parse a QE input file and immediately regenerate it.

        Args:
            input_file: Source QE input file.
            output_file: Destination file. If omitted, overwrites the source.

        Returns:
            QEInput: Parsed representation of the input.
        """
        input_path = Path(input_file)
        qe_input = cls.parse_file(input_path)
        target = Path(output_file) if output_file else input_path
        QEInputGenerator.write_file(qe_input, target)
        return qe_input

