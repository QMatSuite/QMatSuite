"""ORCA input file compiler - single-job chain fusion."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


# Canonical orbital file name for QC chains (immutable)
CANONICAL_GBW_FILE = "scf.gbw"


class MoleculeLike(Protocol):
    """Protocol for molecule-like objects."""
    atoms: str
    charge: int
    multiplicity: int


class ORCAInputCompiler:
    """
    Compiles a QCChain into a single ORCA input file.

    MVP: No $new_job, single job with fused keywords/blocks.
    All steps in a chain are combined into one ORCA input.

    Wavefunction reuse:
    - Non-SCF subchains use MORead + %moinp to load orbitals from scf.gbw
    - This allows reusing SCF orbitals without copying/linking files
    """

    def compile(
        self,
        chain: Any,  # QCChain
        molecule: MoleculeLike,
        fresh: bool = False,
        nprocs: Optional[int] = None,
        moread_file: Optional[str] = None,
    ) -> str:
        """
        Compile chain to ORCA input string.

        Args:
            chain: QCChain to compile
            molecule: Molecule with atoms, charge, multiplicity
            fresh: If True, add NoAutoStart to force fresh calculation
            nprocs: Number of processors (overrides step params)
            moread_file: Path to .gbw file for MORead (wavefunction reuse)
                         If provided, adds MORead keyword and %moinp block

        Returns:
            ORCA input file content as string
        """
        keywords: List[str] = []
        blocks: Dict[str, str] = {}

        # Process SCF root
        scf_params = chain.scf_root.parameters
        self._process_scf_step(chain.scf_root, keywords, blocks)
        if chain.scf_root.step_type_gen == "relax":
            self._append_keyword(keywords, "Opt")
            self._process_relax_step(chain.scf_root, blocks)

        # Process downstream steps
        for step in chain.downstream:
            if step.step_type_gen == "td":
                self._process_td_step(step, blocks)
            elif step.step_type_gen == "relax":
                # Add Opt keyword for geometry optimization
                self._append_keyword(keywords, "Opt")
                # Process relax-specific parameters (e.g., MaxIter, convergence)
                self._process_relax_step(step, blocks)
            # Future: freq, nmr, mp2, etc.

        # Add common keywords
        # SCF macro is handled in _process_scf_step
        if fresh:
            self._append_keyword(keywords, "NoAutoStart")

        # Handle MORead for wavefunction reuse
        # When moread_file is provided, add MORead keyword and %moinp block
        # This allows non-SCF subchains to reuse orbitals from a previous SCF
        if moread_file:
            self._append_keyword(keywords, "MORead")
            blocks["moinp"] = f'"{moread_file}"'

        # Handle nprocs
        effective_nprocs = nprocs or scf_params.get("nprocs")
        if effective_nprocs:
            blocks["pal"] = f"nprocs {effective_nprocs}"

        charge = self._get_explicit_charge(chain)
        multiplicity = self._get_explicit_multiplicity(chain)

        # Format final input
        return self._format_input(
            chain_key=chain.key,
            keywords=keywords,
            blocks=blocks,
            molecule=molecule,
            charge=charge,
            multiplicity=multiplicity,
        )

    def _process_scf_step(
        self,
        step: Any,
        keywords: List[str],
        blocks: Dict[str, str],
    ) -> None:
        """Process SCF/HF step parameters into keywords and blocks."""
        params = step.parameters

        explicit_keywords = params.get("keyword_line")
        if explicit_keywords:
            if isinstance(explicit_keywords, str):
                explicit_keywords = explicit_keywords.split()
            for keyword in explicit_keywords:
                self._append_keyword(keywords, keyword)
            return

        # Method/functional
        if step.step_type_gen == "hf":
            self._append_keyword(keywords, "HF")
        else:
            # DFT functional
            functional = params.get("functional", "B3LYP")
            self._append_keyword(keywords, functional)

        # Basis set
        basis = params.get("basis", "def2-SVP")
        self._append_keyword(keywords, basis)

        # Additional SCF keywords
        if params.get("ri", False):
            self._append_keyword(keywords, "RI")
        if params.get("rijcosx", False):
            self._append_keyword(keywords, "RIJCOSX")

        # Grid settings
        grid = params.get("grid")
        if grid:
            self._append_keyword(keywords, grid)

        # Dispersion correction
        dispersion = params.get("dispersion")
        if dispersion:
            self._append_keyword(keywords, dispersion)

        # ORCA SCF macro (from engine-specific preset patch)
        # Read from engine.orca.scf.macro in step parameters
        orca_macro = self._get_orca_scf_macro(params)
        if orca_macro:
            orca_keyword = self._map_macro_to_keyword(orca_macro)
            if orca_keyword:
                self._append_keyword(keywords, orca_keyword)

    def _append_keyword(self, keywords: List[str], keyword: Any) -> None:
        """Append a keyword once while preserving user order."""
        if keyword is None:
            return
        value = str(keyword).strip()
        if not value:
            return
        value_folded = value.upper()
        existing = {str(item).strip().upper() for item in keywords}
        if value_folded in existing:
            return
        keywords.append(value)

    def _get_explicit_charge(self, chain: Any) -> Optional[int]:
        """Return the first explicit molecular charge override found in chain params."""
        for step in [chain.scf_root, *chain.downstream]:
            params = getattr(step, "parameters", {}) or {}
            if "charge" in params and params["charge"] is not None:
                return int(params["charge"])
        return None

    def _get_explicit_multiplicity(self, chain: Any) -> Optional[int]:
        """Return the first explicit spin multiplicity override found in chain params."""
        for step in [chain.scf_root, *chain.downstream]:
            params = getattr(step, "parameters", {}) or {}
            if "multiplicity" in params and params["multiplicity"] is not None:
                return int(params["multiplicity"])
            if "spin_multiplicity" in params and params["spin_multiplicity"] is not None:
                return int(params["spin_multiplicity"])
        return None

    def _get_orca_scf_macro(self, params: Dict[str, Any]) -> Optional[str]:
        """
        Extract ORCA SCF macro from step parameters.
        
        Looks for engine.orca.scf.macro in nested structure:
        params["engine"]["orca"]["scf"]["macro"]
        
        Args:
            params: Step parameters dict
            
        Returns:
            Macro value (lower-case string) or None if not found
        """
        # Try nested structure first
        if "engine" in params:
            engine = params["engine"]
            if isinstance(engine, dict) and "orca" in engine:
                orca = engine["orca"]
                if isinstance(orca, dict) and "scf" in orca:
                    scf = orca["scf"]
                    if isinstance(scf, dict) and "macro" in scf:
                        macro = scf["macro"]
                        if isinstance(macro, str):
                            # Validate lower-case
                            if macro != macro.lower():
                                raise ValueError(
                                    f"ORCA SCF macro must be lower-case, got: {macro}"
                                )
                            return macro.lower()
        return None

    def _map_macro_to_keyword(self, macro: str) -> Optional[str]:
        """
        Map ORCA SCF macro value to ORCA keyword.
        
        Mapping:
        - "tightscf" → "TightSCF"
        - "normal" → None (no extra keyword)
        - "loose" → "LooseSCF"
        
        Args:
            macro: Lower-case macro value
            
        Returns:
            ORCA keyword string or None if no keyword should be added
        """
        macro_lower = macro.lower()
        if macro_lower == "tightscf":
            return "TightSCF"
        elif macro_lower == "loose":
            return "LooseSCF"
        elif macro_lower == "normal":
            return None  # No extra keyword for normal
        else:
            raise ValueError(
                f"Unknown ORCA SCF macro: {macro}. "
                f"Supported values: 'tightscf', 'normal', 'loose'"
            )

    def _process_td_step(
        self,
        step: Any,
        blocks: Dict[str, str],
    ) -> None:
        """Process TDDFT step parameters into %tddft block."""
        params = step.parameters

        lines = []
        nroots = params.get("nroots", 5)
        lines.append(f"  NRoots {nroots}")

        tda = params.get("tda", True)
        lines.append(f"  TDA {'true' if tda else 'false'}")

        if "triplets" in params:
            lines.append(f"  Triplets {'true' if params['triplets'] else 'false'}")

        if "maxdim" in params:
            lines.append(f"  MaxDim {params['maxdim']}")

        if "etol" in params:
            lines.append(f"  ETol {params['etol']}")

        if "rtol" in params:
            lines.append(f"  RTol {params['rtol']}")

        blocks["tddft"] = "\n".join(lines)

    def _process_relax_step(
        self,
        step: Any,
        blocks: Dict[str, str],
    ) -> None:
        """Process relax step parameters into %geom block."""
        params = step.parameters
        
        # Build %geom block
        lines: List[str] = []
        
        # MaxIter (default: 100)
        max_iter = params.get("max_iter", params.get("MaxIter", 100))
        lines.append(f"  MaxIter {max_iter}")
        
        # Convergence criteria (optional)
        if "convergence" in params:
            conv = params["convergence"]
            if conv == "tight":
                lines.append("  TightOpt")
            elif conv == "verytight":
                lines.append("  VeryTightOpt")
        
        # Coordinate system (optional, default: redundant)
        coordsys = params.get("coordsys", params.get("coordinate_system"))
        if coordsys:
            lines.append(f"  coordsys {coordsys}")
        
        # Constraints (optional)
        if "constraints" in params:
            constraints = params["constraints"]
            if constraints:
                lines.append("  Constraints")
                for constraint in constraints:
                    lines.append(f"    {constraint}")
                lines.append("  end")
        
        if lines:
            blocks["geom"] = "\n".join(lines)

    def _format_input(
        self,
        chain_key: str,
        keywords: List[str],
        blocks: Dict[str, str],
        molecule: MoleculeLike,
        charge: Optional[int] = None,
        multiplicity: Optional[int] = None,
    ) -> str:
        """Format final ORCA input string."""
        lines: List[str] = []

        # Header comment
        lines.append(f"# Chain: {chain_key}")
        lines.append("# Generated by QMatSuite")
        lines.append("")

        # Keywords line
        keyword_str = " ".join(keywords)
        lines.append(f"! {keyword_str}")
        lines.append("")

        # PAL block (special single-line format)
        if "pal" in blocks:
            lines.append(f"%pal {blocks['pal']} end")
            lines.append("")

        # MOINP block (special single-line format for MORead)
        # %moinp "scf.gbw"
        if "moinp" in blocks:
            lines.append(f"%moinp {blocks['moinp']}")
            lines.append("")

        # Other blocks (multi-line format)
        for block_name, block_content in blocks.items():
            if block_name in ("pal", "moinp"):
                continue
            lines.append(f"%{block_name}")
            lines.append(block_content)
            lines.append("end")
            lines.append("")

        # Coordinates
        final_charge = molecule.charge if charge is None else charge
        final_multiplicity = molecule.multiplicity if multiplicity is None else multiplicity
        lines.append(f"* xyz {final_charge} {final_multiplicity}")
        lines.append(molecule.atoms)
        lines.append("*")

        return "\n".join(lines)


def compile_chain_input(
    chain: Any,  # QCChain
    molecule: MoleculeLike,
    fresh: bool = False,
    nprocs: Optional[int] = None,
    moread_file: Optional[str] = None,
) -> str:
    """
    Convenience function to compile a chain to ORCA input.

    Args:
        chain: QCChain to compile
        molecule: Molecule object
        fresh: Force fresh calculation (NoAutoStart)
        nprocs: Number of processors
        moread_file: Path to .gbw file for MORead (wavefunction reuse)

    Returns:
        ORCA input file content
    """
    compiler = ORCAInputCompiler()
    return compiler.compile(
        chain, molecule, fresh=fresh, nprocs=nprocs, moread_file=moread_file
    )
