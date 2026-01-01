"""
Oracle: Read-only semantic prerequisite queries.

Per ParamSpace Constitution:
- Oracle is read-only
- Oracle only returns small discrete values (bool / small enum)
- Oracle does NOT return preset IDs or parameter values
- Oracle only reads YAML truth (current in-memory state)
- Oracle does NOT access preset intention or detect results
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
        Initialize Oracle with current YAML state.
        
        Args:
            yaml_state: Current YAML state dict (section -> {key: value})
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

