"""
QE input generator producing text from QEInput objects.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Union

from quantumvitas.io.model import QECard, QECardType, QEInput, QENamelist

__all__ = ["QEInputGenerator"]


class QEInputGenerator:
    """Generator for Quantum ESPRESSO input files."""

    @staticmethod
    def format_value(value: Any) -> str:
        if isinstance(value, bool):
            return ".true." if value else ".false."
        if isinstance(value, str):
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

        for line_data in card.data:
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
