"""
QE input data structures (modules, namelists, cards).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union


class QEModule(Enum):
    """
    Quantum ESPRESSO modules.

    Documentation references:
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
    - DOS: https://www.quantum-espresso.org/Doc/INPUT_DOS.html
    - BANDS: https://www.quantum-espresso.org/Doc/INPUT_BANDS.html
    - PROJWFC: https://www.quantum-espresso.org/Doc/INPUT_PROJWFC.html
    - DYNMAT: https://www.quantum-espresso.org/Doc/INPUT_DYNMAT.html
    - PPACF: https://www.quantum-espresso.org/Doc/INPUT_PPACF.html
    - PPRISM: https://www.quantum-espresso.org/Doc/INPUT_PPRISM.html
    - CPPP: https://www.quantum-espresso.org/Doc/INPUT_CPPP.html
    """

    PW = "pw"
    PH = "ph"
    Q2R = "q2r"
    MATDYN = "matdyn"
    PP = "pp"
    GIPAW = "gipaw"
    NEB = "neb"
    CP = "cp"
    LD1 = "ld1"
    HP = "hp"
    PWCOND = "pwcond"
    BANDS = "bands"
    DOS = "dos"
    PROJWFC = "projwfc"
    POSTAHC = "postahc"
    DYNMAT = "dynmat"
    OSCDFT_ET = "oscdft_et"
    OSCDFT_PP = "oscdft_pp"
    BAND_INTERPOLATION = "band_interpolation"
    CPPP = "cppp"
    D3HESS = "d3hess"
    PPACF = "ppacf"
    PPRISM = "pprism"
    UNKNOWN = "unknown"


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
    """QE namelist such as &control, &system."""

    name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    parameter_comments: Dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.parameters.get(key, default)

    def set(self, key: str, value: Any, comment: Optional[str] = None) -> None:
        self.parameters[key] = value
        if comment:
            self.parameter_comments[key] = comment

    def get_comment(self, key: str) -> Optional[str]:
        return self.parameter_comments.get(key)


@dataclass
class QECard:
    """QE card such as ATOMIC_SPECIES, K_POINTS."""

    card_type: QECardType
    option: Optional[str] = None
    data: List[Union[str, List[Any]]] = field(default_factory=list)

    def add_line(self, line: Any) -> None:
        self.data.append(line)


@dataclass
class QEInput:
    """
    Complete QE input object (namelists + cards + metadata).
    """

    namelists: List[QENamelist] = field(default_factory=list)
    cards: List[QECard] = field(default_factory=list)
    comments: List[tuple[int, str]] = field(default_factory=list)
    extra_data_lines: List[str] = field(default_factory=list)
    module: Optional[QEModule] = None

    def get_namelist(self, name: str) -> Optional[QENamelist]:
        for nl in self.namelists:
            if nl.name.lower() == name.lower():
                return nl
        return None

    def get_card(self, card_type: QECardType) -> Optional[QECard]:
        for card in self.cards:
            if card.card_type == card_type:
                return card
        return None

    def get_cards(self, card_type: QECardType) -> List[QECard]:
        return [card for card in self.cards if card.card_type == card_type]

    def to_dict(self) -> Dict[str, Any]:
        def normalize(value: Any) -> Any:
            if isinstance(value, float):
                return round(value, 12)
            if isinstance(value, (list, tuple)):
                return [normalize(item) for item in value]
            return value

        return {
            "namelists": {
                nl.name: {k: normalize(v) for k, v in nl.parameters.items()}
                for nl in self.namelists
            },
            "cards": [
                {"type": card.card_type.value, "option": card.option, "data": card.data}
                for card in self.cards
            ],
            "module": self.module.value if self.module else None,
        }

    def detect_module(self) -> QEModule:
        """
        Detect the QE module based on the available namelists/cards.
        """

        namelist_names = {nl.name.lower() for nl in self.namelists}

        if "inputph" in namelist_names:
            return QEModule.PH
        if "inputhp" in namelist_names:
            return QEModule.HP
        if "inputpp" in namelist_names:
            return self._detect_pp_family_module(namelist_names)
        if "inputgipaw" in namelist_names:
            return QEModule.GIPAW
        if "path" in namelist_names:
            return QEModule.NEB
        if "cond" in namelist_names:
            return QEModule.PWCOND
        if "oscdft_et_namelist" in namelist_names:
            return QEModule.OSCDFT_ET
        if "oscdft_pp_namelist" in namelist_names:
            return QEModule.OSCDFT_PP
        if "interpolation" in namelist_names:
            return QEModule.BAND_INTERPOLATION
        if "plot" in namelist_names:
            if "ppacf" in str(self).lower() or any("ppacf" in str(card) for card in self.cards):
                return QEModule.PPACF
            return QEModule.PPACF
        if "input" in namelist_names:
            module = self._detect_from_input_namelist()
            if module is not None:
                return module
        if "bands" in namelist_names:
            return QEModule.BANDS
        if "dos" in namelist_names:
            return QEModule.DOS
        if "projwfc" in namelist_names:
            return QEModule.PROJWFC
        if any(name in namelist_names for name in ["control", "system", "electrons"]):
            control = self.get_namelist("control")
            if control:
                calculation = str(control.get("calculation", "")).lower()
                if "cp" in calculation:
                    return QEModule.CP
            return QEModule.PW

        return QEModule.UNKNOWN

    def _detect_pp_family_module(self, namelist_names: set[str]) -> QEModule:
        inputpp_nl = self.get_namelist("inputpp")
        if inputpp_nl and "plot" in namelist_names:
            return QEModule.PPRISM
        return QEModule.PP

    def _detect_from_input_namelist(self) -> Optional[QEModule]:
        input_nl = self.get_namelist("input")
        if not input_nl:
            return None

        if input_nl.get("atom") is not None or input_nl.get("zed") is not None:
            return QEModule.LD1

        has_fildyn = input_nl.get("fildyn") is not None
        has_flfrc = input_nl.get("flfrc") is not None

        if has_fildyn and has_flfrc:
            return QEModule.Q2R
        if has_flfrc and not has_fildyn:
            return QEModule.MATDYN
        if has_fildyn and not has_flfrc:
            return QEModule.DYNMAT
        if any(card.card_type == QECardType.ATOMIC_SPECIES for card in self.cards):
            return QEModule.LD1
        return QEModule.Q2R

