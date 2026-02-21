"""BM25 search index over engine parameter tags.

Provides a lightweight, stdlib-only BM25 ranking for the ~1000 parameter
documents across all 11 engines that have tag metadata. The index is
built lazily on first search and cached as a module-level singleton.
"""

from __future__ import annotations

import math
import re
from typing import Any


# ---------------------------------------------------------------------------
# Document type
# ---------------------------------------------------------------------------

class TagDoc:
    """A single parameter/tag document in the search index."""

    __slots__ = ("engine", "tag_name", "type", "default", "category", "section", "description", "enum", "tokens")

    def __init__(
        self,
        engine: str,
        tag_name: str,
        type_: str | None,
        default: Any,
        category: str | None,
        description: str | None,
        section: str | None = None,
        enum: list | None = None,
    ):
        self.engine = engine
        self.tag_name = tag_name
        self.type = type_ or ""
        self.default = str(default) if default is not None else ""
        self.category = category or ""
        self.section = section or ""
        self.description = description or ""
        self.enum = enum
        # Pre-tokenize for BM25 (include enum values for discoverability)
        enum_text = " ".join(str(v) for v in enum) if enum else ""
        text = f"{tag_name} {self.description} {self.category} {enum_text}".lower()
        self.tokens = _tokenize(text)


_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


# ---------------------------------------------------------------------------
# BM25 scorer
# ---------------------------------------------------------------------------

class BM25Index:
    """Simple BM25 index (Okapi variant, k1=1.5, b=0.75)."""

    def __init__(self, docs: list[TagDoc]):
        self.docs = docs
        self.k1 = 1.5
        self.b = 0.75

        # Compute stats
        self.N = len(docs)
        self.avgdl = sum(len(d.tokens) for d in docs) / max(self.N, 1)

        # df[term] = number of docs containing term
        self.df: dict[str, int] = {}
        for doc in docs:
            seen: set[str] = set()
            for token in doc.tokens:
                if token not in seen:
                    self.df[token] = self.df.get(token, 0) + 1
                    seen.add(token)

    def score(self, query_tokens: list[str], doc: TagDoc) -> float:
        """BM25 score for a single document against query tokens."""
        dl = len(doc.tokens)
        tf_map: dict[str, int] = {}
        for t in doc.tokens:
            tf_map[t] = tf_map.get(t, 0) + 1

        s = 0.0
        for qt in query_tokens:
            df = self.df.get(qt, 0)
            if df == 0:
                continue
            idf = math.log((self.N - df + 0.5) / (df + 0.5) + 1.0)
            tf = tf_map.get(qt, 0)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            s += idf * numerator / denominator
        return s

    def search(
        self,
        query: str,
        *,
        engine: str = "",
        category: str = "",
        max_results: int = 5,
    ) -> list[tuple[TagDoc, float]]:
        """Search the index. Returns (doc, score) pairs sorted by relevance."""
        qtokens = _tokenize(query.lower())
        if not qtokens:
            return []

        results: list[tuple[TagDoc, float]] = []
        for doc in self.docs:
            if engine and doc.engine != engine:
                continue
            if category and doc.category.lower() != category.lower():
                continue
            sc = self.score(qtokens, doc)
            if sc > 0:
                results.append((doc, sc))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:max_results]


# ---------------------------------------------------------------------------
# Corpus loader
# ---------------------------------------------------------------------------

def _load_all_tag_docs() -> list[TagDoc]:
    """Load tag documents from all engines that have metadata."""
    docs: list[TagDoc] = []

    # QE: module-structured
    try:
        from quantumvitas.drivers.qe.data.qe_metadata import (
            _iter_params,
            list_supported_modules,
        )
        for mod in list_supported_modules():
            for p in _iter_params(mod):
                namelist = p.get("namelist", "")
                docs.append(TagDoc(
                    engine="qe",
                    tag_name=p.get("name", ""),
                    type_=p.get("type"),
                    default=p.get("default"),
                    category=namelist,
                    description=p.get("description"),
                    section=namelist,
                    enum=p.get("enum"),
                ))
    except Exception:
        pass

    # Standard "tags" engines
    for eng in ("vasp", "abinit", "cp2k", "w90", "xtb", "yambo", "qmcpack"):
        try:
            meta_mod = __import__(
                f"quantumvitas.drivers.{eng}.data.{eng}_metadata",
                fromlist=["safe_load_metadata"],
            )
            data = meta_mod.safe_load_metadata()
            for name, info in data.get("tags", {}).items():
                docs.append(TagDoc(
                    engine=eng,
                    tag_name=name,
                    type_=info.get("type"),
                    default=info.get("default"),
                    category=info.get("category", ""),
                    description=info.get("description"),
                    section=info.get("section", ""),
                    enum=info.get("enum"),
                ))
        except Exception:
            pass

    # "keywords" engines
    for eng in ("orca", "gaussian"):
        try:
            meta_mod = __import__(
                f"quantumvitas.drivers.{eng}.data.{eng}_metadata",
                fromlist=["safe_load_metadata"],
            )
            data = meta_mod.safe_load_metadata()
            # Keywords (! line for ORCA, # route for Gaussian)
            section_label = "keyword_line" if eng == "orca" else "route"
            for name, info in data.get("keywords", {}).items():
                docs.append(TagDoc(
                    engine=eng,
                    tag_name=name,
                    type_=info.get("type"),
                    default=info.get("default"),
                    category=info.get("category", ""),
                    description=info.get("description"),
                    section=section_label,
                    enum=info.get("enum"),
                ))
            # Block parameters (ORCA %block...end sections)
            for block_name, block_info in data.get("blocks", {}).items():
                block_section = f"block:{block_name}"
                for param_name, param_info in block_info.get("parameters", {}).items():
                    # ORCA uses "values" for enums in block params
                    block_enum = param_info.get("enum") or param_info.get("values")
                    docs.append(TagDoc(
                        engine=eng,
                        tag_name=param_name,
                        type_=param_info.get("type"),
                        default=param_info.get("default"),
                        category=block_name,
                        description=param_info.get("description"),
                        section=block_section,
                        enum=block_enum if isinstance(block_enum, list) else None,
                    ))
        except Exception:
            pass

    # "commands" engines
    for eng in ("lammps",):
        try:
            meta_mod = __import__(
                f"quantumvitas.drivers.{eng}.data.{eng}_metadata",
                fromlist=["safe_load_metadata"],
            )
            data = meta_mod.safe_load_metadata()
            for name, info in data.get("commands", {}).items():
                docs.append(TagDoc(
                    engine=eng,
                    tag_name=name,
                    type_=info.get("type"),
                    default=info.get("default"),
                    category=info.get("category", ""),
                    description=info.get("description"),
                    enum=info.get("enum"),
                ))
        except Exception:
            pass

    return docs


# ---------------------------------------------------------------------------
# Lazy singleton
# ---------------------------------------------------------------------------

_INDEX: BM25Index | None = None


def get_search_index() -> BM25Index:
    """Return the lazily-built BM25 search index (singleton)."""
    global _INDEX
    if _INDEX is None:
        import quantumvitas.drivers  # noqa: F401 — trigger registration
        docs = _load_all_tag_docs()
        _INDEX = BM25Index(docs)
    return _INDEX


def reset_search_index() -> None:
    """Clear the singleton (for testing)."""
    global _INDEX
    _INDEX = None
