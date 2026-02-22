"""Backward-compatibility re-export for QE metadata (moved to drivers/qe/data/)."""

# Import all public and private functions/classes for backward compatibility
from qmatsuite.drivers.qe.data.qe_metadata import (
    # Public API
    get_doc_url_pattern,
    get_module_doc_url,
    get_module_namelists,
    get_module_param_sections,
    get_module_card_sections,
    get_ui_parameters,
    get_metadata_file_info,
    get_qe_metadata_debug_info,
    list_supported_modules,
    safe_load_metadata,
    reload_metadata,
    validate_ui_parameters,
    QEUIParam,
    # Private helpers (needed by some code)
    _iter_params,
    _load_raw_metadata,
    _load_ui_parameters,
    _load_qe_parameter_map,
    _update_qe_metadata_load_state,
    # Module-level state
    QE_METADATA_LOAD_STATE,
)

