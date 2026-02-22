"""
Oracle: Read-only semantic prerequisite queries.

Per ParamSpace Constitution:
- Oracle is read-only
- Oracle only returns small discrete values (bool / small enum)
- Oracle does NOT return preset IDs or parameter values
- Oracle only reads IR YAML truth (current in-memory IR state; IR is SSOT)
- Oracle does NOT access preset intention or detect results

Oracle operates on IR YAML (IR is SSOT). In v0, IR keys == QE keys due to 1:1 mapping,
but conceptually Oracle only knows about IR keys.
"""

from typing import Any, Dict


class Oracle:
    """
    Read-only helper for semantic prerequisite queries.
    
    Oracle functions answer "is this applicable now?" based on current YAML state.
    They do NOT make decisions about presets or values.
    """
    
    def __init__(self, yaml_state: Dict[str, Dict[str, Any]]):
        """
        Initialize Oracle with current IR YAML state.
        
        Args:
            yaml_state: Current IR YAML state dict (section -> {key: value})
                IR is SSOT; in v0, IR keys == QE keys due to 1:1 mapping.
        """
        self.yaml_state = yaml_state
    
    def degauss_applicability(self) -> bool:
        """
        Check if degauss is applicable based on current YAML state.
        
        Returns True iff occupations indicate smearing.
        
        Reads:
        - SYSTEM.occupations (must be "smearing" for degauss to be applicable)
        
        Returns:
            True if degauss is applicable (smearing is active), False otherwise
        """
        system = self.yaml_state.get("SYSTEM", {})
        occupations = system.get("occupations")
        
        if occupations is None:
            return False
        
        # Normalize to lowercase for comparison
        occupations_str = str(occupations).lower().strip()
        
        # degauss is only applicable when using smearing
        return occupations_str == "smearing"

