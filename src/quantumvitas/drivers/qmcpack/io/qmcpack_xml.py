"""QMCPACK XML input parser and writer.

Pure stdlib module — no kernel or inputformat imports.
Handles the QMCPACK F6 (XML) syntax family:
  <simulation> root, <parameter name="key">value</parameter> convention.

Parser extracts structured params + structure from XML.
Writer reconstructs XML from params + structure, using preserved XML subtrees
for wavefunction/hamiltonian when available (lossless roundtrip).
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from typing import Any


# ---------------------------------------------------------------------------
# Helpers: parse numeric arrays from XML text
# ---------------------------------------------------------------------------

def _parse_pos_array(text: str) -> list[list[float]]:
    """Parse a posArray text block into a list of [x, y, z] triples."""
    tokens = text.split()
    coords = []
    for i in range(0, len(tokens) - 2, 3):
        coords.append([float(tokens[i]), float(tokens[i + 1]), float(tokens[i + 2])])
    return coords


def _parse_lattice_text(text: str) -> list[list[float]]:
    """Parse lattice parameter text into 3x3 list."""
    return _parse_pos_array(text)


def _parse_string_array(text: str) -> list[str]:
    """Parse a stringArray text block into a list of strings."""
    return text.split()


# ---------------------------------------------------------------------------
# Helpers: find and parse ion particleset
# ---------------------------------------------------------------------------

def _find_ion_particleset(root: ET.Element) -> ET.Element | None:
    """Find the ion particleset (not the electron set 'e')."""
    for pset in root.iter("particleset"):
        name = pset.get("name", "")
        if name == "e":
            continue
        # Check if it has groups with positive charge or atomicnumber
        groups = pset.findall("group")
        if groups:
            for g in groups:
                for p in g.findall("parameter"):
                    if p.get("name") in ("charge", "atomicnumber"):
                        val = (p.text or "").strip()
                        try:
                            if float(val) > 0:
                                return pset
                        except ValueError:
                            pass
        # Also accept if it has position attrib (even without charge info)
        for attr in pset.findall("attrib"):
            if attr.get("name") == "position":
                return pset
    return None


def _parse_ion_particleset(
    pset: ET.Element,
) -> tuple[list[str], list[list[float]], bool]:
    """Parse ion particleset into (species, coords, is_fractional).

    Handles two QMCPACK position layouts:
    - Flat: <attrib name="position"> at particleset level, with optional
      <attrib name="ionid"> for species assignment
    - Grouped: positions inside individual <group> elements (rare for ions)

    Returns is_fractional=True if condition="1" on position attrib.
    """
    groups = pset.findall("group")
    group_names = [g.get("name", "") for g in groups]

    # Check for flat position attrib at particleset level
    pos_attrib = None
    ionid_attrib = None
    is_fractional = False
    for attr in pset.findall("attrib"):
        aname = attr.get("name", "")
        if aname == "position":
            pos_attrib = attr
            is_fractional = attr.get("condition", "0") == "1"
        elif aname == "ionid":
            ionid_attrib = attr

    if pos_attrib is not None:
        coords = _parse_pos_array(pos_attrib.text or "")
        if ionid_attrib is not None:
            species = _parse_string_array(ionid_attrib.text or "")
        elif len(group_names) == 1:
            # Single species: all positions belong to that group
            species = [group_names[0]] * len(coords)
        else:
            # Multiple groups without ionid: assign by group order and size
            species = []
            for g in groups:
                pass
            # Fallback: assign round-robin (shouldn't normally happen)
            if not species:
                species = [group_names[i % len(group_names)] for i in range(len(coords))]
        return species, coords, is_fractional

    # Grouped positions: each group has its own position attrib
    species: list[str] = []
    coords: list[list[float]] = []
    for g in groups:
        gname = g.get("name", "")
        for attr in g.findall("attrib"):
            if attr.get("name") == "position":
                is_fractional = attr.get("condition", "0") == "1"
                group_coords = _parse_pos_array(attr.text or "")
                species.extend([gname] * len(group_coords))
                coords.extend(group_coords)

    return species, coords, is_fractional


# ---------------------------------------------------------------------------
# Helpers: parse QMC block
# ---------------------------------------------------------------------------

def _parse_qmc_block(qmc_el: ET.Element) -> dict[str, Any]:
    """Parse a <qmc> element into a dict."""
    block: dict[str, Any] = {}
    # Attributes
    for attr_name in ("method", "move", "target", "checkpoint"):
        val = qmc_el.get(attr_name)
        if val is not None:
            block[attr_name] = val
    # Parameters
    for p in qmc_el.findall("parameter"):
        name = p.get("name", "")
        if name:
            block[name] = (p.text or "").strip()
    # Cost elements (optimization)
    costs = {}
    for cost in qmc_el.findall("cost"):
        cname = cost.get("name", "")
        if cname:
            costs[cname] = (cost.text or "").strip()
    if costs:
        block["_costs"] = costs
    # Estimators inside qmc block
    estimators = []
    for est in qmc_el.findall("estimator"):
        est_info: dict[str, str] = {}
        for k, v in est.attrib.items():
            est_info[k] = v
        estimators.append(est_info)
    if estimators:
        block["_estimators"] = estimators
    return block


# ---------------------------------------------------------------------------
# Helpers: extract resource refs (hrefs)
# ---------------------------------------------------------------------------

def _extract_resource_refs(root: ET.Element) -> dict[str, list[str]]:
    """Extract external file references from QMCPACK XML."""
    refs: dict[str, list[str]] = {
        "wavefunction_hrefs": [],
        "pseudopotential_hrefs": [],
        "include_hrefs": [],
    }
    # Wavefunction HDF5 hrefs (determinantset href)
    for ds in root.iter("determinantset"):
        href = ds.get("href")
        if href:
            refs["wavefunction_hrefs"].append(href)
    # Pseudopotential hrefs
    for pseudo in root.iter("pseudo"):
        href = pseudo.get("href")
        if href:
            refs["pseudopotential_hrefs"].append(href)
    # Include hrefs
    for inc in root.iter("include"):
        href = inc.get("href")
        if href:
            refs["include_hrefs"].append(href)
    return refs


# ---------------------------------------------------------------------------
# Parser: XML text -> {"params": {...}, "structure": {...}}
# ---------------------------------------------------------------------------

def parse_qmcpack_text(text: str) -> dict[str, Any]:
    """Parse QMCPACK XML input text into combined params + structure.

    Returns a dict with keys "params" and optionally "structure",
    following the content_role="combined" convention.
    """
    root = ET.fromstring(text)
    params: dict[str, Any] = {}
    structure: dict[str, Any] | None = None

    # --- Project ---
    project = root.find("project")
    if project is not None:
        if project.get("id"):
            params["qmc_project_id"] = project.get("id")
        params["series"] = project.get("series", "0")
        for p in project.findall("parameter"):
            name = p.get("name", "")
            if name:
                params[name] = (p.text or "").strip()

    # --- Random seed ---
    random_el = root.find("random")
    if random_el is not None and random_el.get("seed"):
        params["random_seed"] = random_el.get("seed")

    # --- Simulationcell ---
    simcell = root.find(".//simulationcell")
    lattice_vectors: list[list[float]] | None = None
    if simcell is not None:
        for p in simcell.findall("parameter"):
            name = p.get("name", "")
            ptext = (p.text or "").strip()
            if name == "lattice":
                lattice_vectors = _parse_lattice_text(p.text or "")
            elif name == "bconds":
                params["bconds"] = ptext
            elif name == "LR_dim_cutoff":
                params["LR_dim_cutoff"] = ptext
            elif name == "rs":
                params["rs"] = ptext
                cond = p.get("condition")
                if cond:
                    params["rs_condition"] = cond
            else:
                params[f"cell_{name}"] = ptext

    # --- Ion particleset -> structure ---
    ion_pset = _find_ion_particleset(root)
    if ion_pset is not None:
        species, coords, is_fractional = _parse_ion_particleset(ion_pset)
        if species:
            structure = {"species": species}
            if is_fractional:
                structure["frac_coords"] = coords
            else:
                structure["cart_coords"] = coords
            if lattice_vectors:
                structure["lattice"] = lattice_vectors
            structure["comment"] = params.get("qmc_project_id", "")
            # Preserve ion particleset name for roundtrip
            ion_name = ion_pset.get("name", "ion0")
            if ion_name != "ion0":
                params["_ion_particleset_name"] = ion_name
    elif lattice_vectors:
        # No ions but have lattice (e.g., HEG)
        structure = {"lattice": lattice_vectors, "species": [], "frac_coords": []}

    # --- Electron particleset ---
    e_pset = root.find(".//particleset[@name='e']")
    if e_pset is not None:
        electrons: dict[str, int] = {}
        for group in e_pset.findall("group"):
            gname = group.get("name", "")
            gsize = group.get("size", "0")
            try:
                electrons[gname] = int(gsize)
            except ValueError:
                pass
        if electrons:
            params["electrons"] = electrons

    # --- Wavefunction (preserve XML + extract key semantic fields) ---
    wf = root.find(".//wavefunction")
    if wf is not None:
        params["_wavefunction_xml"] = ET.tostring(wf, encoding="unicode")
        wf_info: dict[str, Any] = {}
        if wf.get("name"):
            wf_info["name"] = wf.get("name")
        if wf.get("target"):
            wf_info["target"] = wf.get("target")
        ds = wf.find(".//determinantset")
        if ds is not None:
            ds_info: dict[str, str] = {}
            for k in ("type", "key", "href", "source", "transform",
                       "tilematrix", "twistnum", "twist", "meshfactor", "precision"):
                v = ds.get(k)
                if v is not None:
                    ds_info[k] = v
            wf_info["determinantset"] = ds_info
        sc = wf.find(".//sposet_collection")
        if sc is not None:
            sc_info: dict[str, str] = {}
            for k in ("type", "name", "source", "transform"):
                v = sc.get(k)
                if v is not None:
                    sc_info[k] = v
            wf_info["sposet_collection"] = sc_info
        jastrows: list[dict[str, str]] = []
        for j in wf.findall("jastrow"):
            j_info: dict[str, str] = {}
            for k in ("name", "type", "function", "source", "print", "optimize"):
                v = j.get(k)
                if v is not None:
                    j_info[k] = v
            jastrows.append(j_info)
        if jastrows:
            wf_info["jastrow"] = jastrows
        params["wavefunction"] = wf_info

    # --- Hamiltonian (preserve XML + extract key semantic fields) ---
    ham = root.find(".//hamiltonian")
    if ham is not None:
        params["_hamiltonian_xml"] = ET.tostring(ham, encoding="unicode")
        ham_info: dict[str, Any] = {}
        if ham.get("name"):
            ham_info["name"] = ham.get("name")
        pairpots: list[dict[str, Any]] = []
        for pp in ham.findall("pairpot"):
            pp_info: dict[str, Any] = {
                "name": pp.get("name", ""),
                "type": pp.get("type", ""),
            }
            pseudos = []
            for pseudo in pp.findall("pseudo"):
                pseudos.append({
                    "elementType": pseudo.get("elementType", ""),
                    "href": pseudo.get("href", ""),
                })
            if pseudos:
                pp_info["pseudos"] = pseudos
            pairpots.append(pp_info)
        if pairpots:
            ham_info["pairpots"] = pairpots
        constants: list[dict[str, str]] = []
        for c in ham.findall("constant"):
            constants.append({
                "name": c.get("name", ""),
                "type": c.get("type", ""),
            })
        if constants:
            ham_info["constants"] = constants
        estimators: list[dict[str, str]] = []
        for est in ham.findall("estimator"):
            est_info: dict[str, str] = {}
            for k, v in est.attrib.items():
                est_info[k] = v
            estimators.append(est_info)
        if estimators:
            ham_info["estimators"] = estimators
        params["hamiltonian"] = ham_info

    # --- QMC blocks (including those inside loop wrappers) ---
    qmc_blocks: list[dict[str, Any]] = []
    for child in root:
        if child.tag == "qmc":
            qmc_blocks.append(_parse_qmc_block(child))
        elif child.tag == "loop":
            loop_max = child.get("max", "1")
            for qmc_el in child.findall("qmc"):
                block = _parse_qmc_block(qmc_el)
                block["_loop_max"] = loop_max
                qmc_blocks.append(block)
    if qmc_blocks:
        params["qmc"] = qmc_blocks

    # --- Resource refs ---
    resource_refs = _extract_resource_refs(root)
    if any(resource_refs.values()):
        params["_resource_refs"] = resource_refs

    result: dict[str, Any] = {"params": params}
    if structure is not None:
        result["structure"] = structure
    return result


# ---------------------------------------------------------------------------
# Writer: {"params": ..., "structure": ...} -> XML text
# ---------------------------------------------------------------------------

def write_qmcpack_text(fragment: dict[str, Any]) -> str:
    """Write QMCPACK XML input text from combined params + structure.

    If preserved XML subtrees (_wavefunction_xml, _hamiltonian_xml) are present
    in params, they are re-inserted for lossless roundtrip. Otherwise, minimal
    placeholders are generated from structured params.
    """
    params = fragment.get("params") or {}
    structure = fragment.get("structure") or {}

    root = ET.Element("simulation")

    # --- Project ---
    project_id = params.get("qmc_project_id", "qmcpack_calc")
    series = params.get("series", "0")
    proj = ET.SubElement(root, "project", id=project_id, series=series)
    driver_version = params.get("driver_version")
    if driver_version:
        dv = ET.SubElement(proj, "parameter", name="driver_version")
        dv.text = driver_version

    # --- Random seed ---
    random_seed = params.get("random_seed")
    if random_seed:
        ET.SubElement(root, "random", seed=str(random_seed))

    # --- Simulationcell ---
    lattice = structure.get("lattice", [])
    has_cell = lattice or params.get("bconds") or params.get("rs")
    if has_cell:
        qmcsystem = ET.SubElement(root, "qmcsystem")
        sc = ET.SubElement(qmcsystem, "simulationcell")
        if lattice:
            lat_el = ET.SubElement(sc, "parameter", name="lattice")
            lat_el.text = "\n" + "\n".join(
                f"      {v[0]:14.8f} {v[1]:14.8f} {v[2]:14.8f}"
                for v in lattice
            ) + "\n    "
        rs = params.get("rs")
        if rs:
            rs_el = ET.SubElement(sc, "parameter", name="rs")
            rs_cond = params.get("rs_condition")
            if rs_cond:
                rs_el.set("condition", rs_cond)
            rs_el.text = str(rs)
        bconds = params.get("bconds")
        if bconds:
            bc_el = ET.SubElement(sc, "parameter", name="bconds")
            bc_el.text = bconds
        lr_cut = params.get("LR_dim_cutoff")
        if lr_cut:
            lr_el = ET.SubElement(sc, "parameter", name="LR_dim_cutoff")
            lr_el.text = str(lr_cut)

    # --- Ion particleset ---
    species = structure.get("species", [])
    coords = structure.get("frac_coords") or structure.get("cart_coords", [])
    is_fractional = "frac_coords" in structure
    ion_pset_name = params.get("_ion_particleset_name", "ion0")
    if species and coords:
        ions = ET.SubElement(root, "particleset", name=ion_pset_name,
                             size=str(len(coords)))
        # Group definitions
        unique_species: list[str] = []
        for sp in species:
            if sp not in unique_species:
                unique_species.append(sp)
        for sp in unique_species:
            ET.SubElement(ions, "group", name=sp)
        # Flat position attrib
        pos_el = ET.SubElement(ions, "attrib", name="position",
                               datatype="posArray")
        if is_fractional:
            pos_el.set("condition", "1")
        pos_el.text = "\n" + "\n".join(
            f"      {c[0]:.10e}  {c[1]:.10e}  {c[2]:.10e}"
            for c in coords
        ) + "\n    "
        # Ionid attrib
        if len(unique_species) > 1 or len(species) > 1:
            ionid_el = ET.SubElement(ions, "attrib", name="ionid",
                                     datatype="stringArray")
            ionid_el.text = " " + " ".join(species) + " "

    # --- Electron particleset ---
    electrons = params.get("electrons", {})
    if electrons:
        e_pset = ET.SubElement(root, "particleset", name="e", random="yes")
        if species and coords:
            e_pset.set("randomsrc", ion_pset_name)
        for gname, gsize in electrons.items():
            group = ET.SubElement(e_pset, "group", name=gname, size=str(gsize))
            charge_el = ET.SubElement(group, "parameter", name="charge")
            charge_el.text = "-1"

    # --- Wavefunction ---
    wf_xml = params.get("_wavefunction_xml")
    if wf_xml:
        wf_el = ET.fromstring(wf_xml)
        root.append(wf_el)

    # --- Hamiltonian ---
    ham_xml = params.get("_hamiltonian_xml")
    if ham_xml:
        ham_el = ET.fromstring(ham_xml)
        root.append(ham_el)

    # --- QMC blocks ---
    qmc_blocks = params.get("qmc", [])
    for block in qmc_blocks:
        loop_max = block.get("_loop_max")
        parent = root
        if loop_max:
            loop_el = ET.SubElement(root, "loop", max=str(loop_max))
            parent = loop_el

        qmc_attrs: dict[str, str] = {}
        for attr_name in ("method", "move", "target", "checkpoint"):
            val = block.get(attr_name)
            if val is not None:
                qmc_attrs[attr_name] = str(val)
        qmc_el = ET.SubElement(parent, "qmc", **qmc_attrs)

        # Estimators inside qmc
        for est in block.get("_estimators", []):
            ET.SubElement(qmc_el, "estimator", **est)

        # Parameters
        skip_keys = {"method", "move", "target", "checkpoint",
                     "_loop_max", "_costs", "_estimators"}
        for pname, pval in block.items():
            if pname in skip_keys:
                continue
            p_el = ET.SubElement(qmc_el, "parameter", name=pname)
            p_el.text = str(pval)

        # Cost elements (optimization)
        for cname, cval in block.get("_costs", {}).items():
            cost_el = ET.SubElement(qmc_el, "cost", name=cname)
            cost_el.text = str(cval)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")

    buf = io.StringIO()
    tree.write(buf, xml_declaration=True, encoding="unicode")
    return buf.getvalue() + "\n"
