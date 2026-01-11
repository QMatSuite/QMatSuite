"""
IR (Intermediate Representation) module.

IR is a minimal rename/indirection layer that mediates between ParamSpace
and engine-specific parameter keys. In v0, IR is QE-equivalent (mostly same
names as QE keys) and exists ONLY to mediate ParamSpace ↔ QE parameter keys.

IR is NOT directly exposed to users in v0 (no user-facing editing or API);
it is an internal mediation layer.
"""

