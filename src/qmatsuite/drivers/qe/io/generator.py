"""
QE input generator producing text from QEInput objects.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Union

from qmatsuite.drivers.qe.io.model import QECard, QECardType, QEInput, QENamelist

__all__ = ["QEInputGenerator"]


class QEInputGenerator:
    """Generator for Quantum ESPRESSO input files."""

    @staticmethod
    def format_value(value: Any) -> str:
        if isinstance(value, bool):
            return ".true." if value else ".false."
        if isinstance(value, str):
            # Defensive normalization: emit Fortran logical tokens unquoted even if
            # they arrive as strings (e.g., ".true.", "'.false.'").
            stripped = value.strip()
            unquoted = stripped.strip("'\"").lower()
            if unquoted in {".true.", "true", "t", ".t."}:
                return ".true."
            if unquoted in {".false.", "false", "f", ".f."}:
                return ".false."
            return f"'{value}'"
        if isinstance(value, (list, tuple)):
            formatted = ", ".join(
                str(QEInputGenerator.format_value(v)).strip("'\"") for v in value
            )
            return f"({formatted})"
        return str(value)

    @staticmethod
    def generate_namelist(namelist: QENamelist, indent: str = "    ") -> str:
        lines = [f"&{namelist.name}"]
        for key, value in namelist.parameters.items():
            formatted_value = QEInputGenerator.format_value(value)
            comment = namelist.get_comment(key)
            if comment:
                lines.append(f"{indent}{key} = {formatted_value}  {comment}")
            else:
                lines.append(f"{indent}{key} = {formatted_value}")
        lines.append("/")
        return "\n".join(lines)

    @staticmethod
    def generate_card(card: QECard) -> str:
        lines = []
        header = card.card_type.value
        if card.option:
            if card.card_type == QECardType.K_POINTS:
                header += f" {{{card.option}}}"
            else:
                header += f" ({card.option})"
        lines.append(header)

        data = card.data
        
        # For QE list-style K_POINTS modes (all except automatic/gamma),
        # ensure the count line is present (first line should be a single integer).
        if card.card_type == QECardType.K_POINTS and card.option:
            opt_lower = card.option.strip().lower()
            needs_count = opt_lower in {
                "tpiba",
                "crystal",
                "tpiba_b",
                "crystal_b",
                "tpiba_c",
                "crystal_c",
            }
            if needs_count and data:
                # Check if first row is already a count (single integer), including
                # string forms (e.g., "64") commonly found in YAML.
                first_row = data[0]
                first_value: Any | None = None
                if isinstance(first_row, list) and len(first_row) == 1:
                    first_value = first_row[0]
                elif isinstance(first_row, (int, float, str)):
                    first_value = first_row

                is_count_line = False
                if isinstance(first_value, (int, float)):
                    is_count_line = True
                elif isinstance(first_value, str):
                    try:
                        int(first_value.strip())
                        is_count_line = True
                    except ValueError:
                        pass
                
                if not is_count_line:
                    # Need to add count line - count explicit k-point rows
                    # (rows with at least kx, ky, kz, w/npts columns).
                    n_points = sum(
                        1 for row in data if isinstance(row, (list, tuple)) and len(row) >= 4
                    )
                    data = [[n_points]] + list(data)
                # else: count line is already present, use it as-is

        for line_data in data:
            if isinstance(line_data, list):
                lines.append("  " + " ".join(str(x) for x in line_data))
            else:
                lines.append("  " + str(line_data))
        return "\n".join(lines)

    @classmethod
    def generate(cls, qe_input: QEInput) -> str:
        lines = []
        used_extra_lines = set()

        for i, namelist in enumerate(qe_input.namelists):
            lines.append(cls.generate_namelist(namelist))
            if namelist.name.lower() == "inputph":
                q_point_pattern = re.compile(r"^\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)")
                for data_line in qe_input.extra_data_lines:
                    if data_line not in used_extra_lines and q_point_pattern.match(
                        data_line.strip()
                    ):
                        lines.append(data_line)
                        used_extra_lines.add(data_line)
                        break
            if i < len(qe_input.namelists) - 1 or qe_input.cards:
                lines.append("")

        for card in qe_input.cards:
            lines.append(cls.generate_card(card))
            lines.append("")

        for data_line in qe_input.extra_data_lines:
            if data_line not in used_extra_lines:
                lines.append(data_line)

        while lines and not lines[-1].strip():
            lines.pop()

        content = "\n".join(lines)
        if content and not content.endswith("\n"):
            # dynmat.x (and a few others) require inputs to end with a newline.
            content += "\n"
        return content

    @classmethod
    def write_file(cls, qe_input: QEInput, filepath: Union[str, Path]) -> None:
        path = Path(filepath)
        content = cls.generate(qe_input)
        path.write_text(content)
