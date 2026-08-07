"""TheoremSearch MCP server - semantic search over ~9.27M mathematical theorems.

Wraps the public REST API of https://api.theoremsearch.com (UW Math AI Lab)
and exposes it as Model Context Protocol tools for coding / proving agents.

Exposed tools:
  - theorem_search   : POST /search                  main semantic search (with filters)
  - graph_search     : GET  /graph/embedding         search over full corpus (formal Lean + informal arXiv)
  - graph_statement  : GET  /graph/statement/{id}    walk a statement's dependency neighborhood
  - graph_paper      : GET  /graph/paper             all statements + dependency edges of a paper / Lean repo
  - paper_search     : GET  /paper-search            autocomplete over paper titles / arXiv IDs
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

try:
    from fastmcp import FastMCP
except ImportError:  # pragma: no cover - dependency lives in requirements.txt
    FastMCP = None  # type: ignore[assignment]

API_BASE = "https://api.theoremsearch.com"
# /graph/embedding with formality=formal (formal Lean corpus) is slow; keep generous.
REQUEST_TIMEOUT_SECONDS = 180

VALID_SOURCES = [
    "arXiv",
    "Stacks Project",
    "ProofWiki",
    "CRing Project",
    "HoTT Book",
    "Open Logic Project",
    "An Infinitely Large Napkin",
]

VALID_FORMALITY = ("informal", "formal", "both")
# /graph/statement rejects "both"; only informal/formal are accepted by the live API.
VALID_GRAPH_FORMALITY = ("informal", "formal")


def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.post(f"{API_BASE}{path}", json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    response = requests.get(f"{API_BASE}{path}", params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _range_pair(name: str, value: Optional[List[int]]) -> Optional[List[int]]:
    if value is None:
        return None
    if not (isinstance(value, (list, tuple)) and len(value) == 2):
        raise ValueError(f"{name} must be a [min, max] pair, e.g. [2015, 2023]")
    return [int(value[0]), int(value[1])]


def theorem_search(
    query: str,
    n_results: int = 10,
    sources: Optional[List[str]] = None,
    authors: Optional[List[str]] = None,
    types: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    paper_filter: Optional[str] = None,
    year_range: Optional[List[int]] = None,
    citation_range: Optional[List[int]] = None,
    include_unknown_citations: bool = True,
    citation_weight: float = 0.0,
    prompt: Optional[str] = None,
    db_top_k: Optional[int] = None,
) -> Dict[str, Any]:
    """Semantic search for theorems across ~9.27M statements.

    Backed by POST /search: Qwen3-Embedding-8B + HNSW ANN + exact-cosine rerank,
    with optional citation weighting.
    """
    if not query.strip():
        raise ValueError("query must be non-empty")
    if n_results <= 0:
        raise ValueError("n_results must be > 0")
    if sources:
        unknown = [s for s in sources if s not in VALID_SOURCES]
        if unknown:
            raise ValueError(f"unknown sources {unknown}; allowed: {VALID_SOURCES}")

    payload: Dict[str, Any] = {"query": query, "n_results": n_results}
    if sources:
        payload["sources"] = sources
    if authors:
        payload["authors"] = authors
    if types:
        payload["types"] = types
    if tags:
        payload["tags"] = tags
    if paper_filter:
        payload["paper_filter"] = paper_filter
    year = _range_pair("year_range", year_range)
    if year:
        payload["year_range"] = year
    cites = _range_pair("citation_range", citation_range)
    if cites:
        payload["citation_range"] = cites
        payload["include_unknown_citations"] = include_unknown_citations
    if citation_weight:
        payload["citation_weight"] = citation_weight
    if prompt:
        payload["prompt"] = prompt
    if db_top_k:
        payload["db_top_k"] = db_top_k

    return _post("/search", payload)


def graph_search(
    query: str,
    n_results: int = 10,
    formality: str = "both",
) -> Dict[str, Any]:
    """Semantic search over the full TheoremGraph corpus (formal Lean + informal arXiv)."""
    if not query.strip():
        raise ValueError("query must be non-empty")
    if formality not in VALID_FORMALITY:
        raise ValueError(f"formality must be one of {VALID_FORMALITY}")
    return _get(
        "/graph/embedding",
        params={"query": query, "n_results": n_results, "formality": formality},
    )


def graph_statement(
    statement_id: str,
    direction: str = "both",
    formality: str = "formal",
) -> Dict[str, Any]:
    """Return a statement and its dependency neighborhood.

    `direction`: "src" (what this statement uses), "dep" (what uses this statement),
    or "both". `formality`: "informal" or "formal" (the live API rejects "both"
    here, unlike /graph/embedding). Response shape: {"root", "nodes", "edges"}
    and where edges carry {"src_id", "dep_id"} plus optional metadata
    (e.g. "edge_type", "dep_key", "location", "methods").
    """
    if not statement_id.strip():
        raise ValueError("statement_id must be non-empty")
    if direction not in ("src", "dep", "both"):
        raise ValueError("direction must be 'src', 'dep' or 'both'")
    if formality not in VALID_GRAPH_FORMALITY:
        raise ValueError(f"formality must be one of {VALID_GRAPH_FORMALITY}")
    return _get(
        f"/graph/statement/{statement_id.strip()}",
        params={"direction": direction, "formality": formality},
    )


def graph_paper(
    external_id: Optional[str] = None,
    paper_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Return all statements + dependency edges of a paper or Lean repository.

    Provide either `external_id` (arXiv ID or Lean repo slug, e.g. "2403.05555"
    or "leanprover-community/mathlib4") or `paper_id` (UUID).
    Response shape: {"paper", "statements", "edges"}.
    """
    if not external_id and not paper_id:
        raise ValueError("provide either external_id (arXiv ID / repo slug) or paper_id (UUID)")
    params: Dict[str, Any] = {}
    if external_id:
        params["external_id"] = external_id
    if paper_id:
        path = f"/graph/paper/{paper_id}"
    else:
        path = "/graph/paper"
    return _get(path, params=params or None)


def paper_search(q: str, limit: int = 8) -> Dict[str, Any]:
    """Autocomplete over paper titles and arXiv external IDs."""
    if not q.strip():
        raise ValueError("q must be non-empty")
    if limit <= 0:
        raise ValueError("limit must be > 0")
    return _get("/paper-search", params={"q": q, "limit": limit})


def build_mcp_app() -> Optional[Any]:
    if FastMCP is None:
        return None

    app = FastMCP("theoremsearch")

    @app.tool(
        name="theorem_search",
        description=(
            "Semantic search for theorems across ~9.27M statements. "
            "Backed by POST /search: Qwen3-Embedding-8B + HNSW ANN + exact-cosine "
            "rerank, with optional citation weighting."
        ),
    )
    def _tool_theorem_search(
        query: str,
        n_results: int = 10,
        sources: Optional[List[str]] = None,
        authors: Optional[List[str]] = None,
        types: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        paper_filter: Optional[str] = None,
        year_range: Optional[List[int]] = None,
        citation_range: Optional[List[int]] = None,
        include_unknown_citations: bool = True,
        citation_weight: float = 0.0,
        prompt: Optional[str] = None,
        db_top_k: Optional[int] = None,
    ) -> Dict[str, Any]:
        return theorem_search(
            query=query,
            n_results=n_results,
            sources=sources,
            authors=authors,
            types=types,
            tags=tags,
            paper_filter=paper_filter,
            year_range=year_range,
            citation_range=citation_range,
            include_unknown_citations=include_unknown_citations,
            citation_weight=citation_weight,
            prompt=prompt,
            db_top_k=db_top_k,
        )

    @app.tool(
        name="graph_search",
        description=(
            "Semantic search over the full TheoremGraph corpus "
            "(formal Lean + informal arXiv)."
        ),
    )
    def _tool_graph_search(
        query: str,
        n_results: int = 10,
        formality: str = "both",
    ) -> Dict[str, Any]:
        return graph_search(query=query, n_results=n_results, formality=formality)

    @app.tool(
        name="graph_statement",
        description=(
            "Return a statement and its dependency neighborhood, walking the "
            "direction src/dep/both with formality informal or formal."
        ),
    )
    def _tool_graph_statement(
        statement_id: str,
        direction: str = "both",
        formality: str = "formal",
    ) -> Dict[str, Any]:
        return graph_statement(
            statement_id=statement_id,
            direction=direction,
            formality=formality,
        )

    @app.tool(
        name="graph_paper",
        description=(
            "Return all statements and dependency edges of a paper or Lean "
            "repository, by arXiv ID / repo slug (external_id) or UUID (paper_id)."
        ),
    )
    def _tool_graph_paper(
        external_id: Optional[str] = None,
        paper_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return graph_paper(external_id=external_id, paper_id=paper_id)

    @app.tool(
        name="paper_search",
        description="Autocomplete over paper titles and arXiv external IDs.",
    )
    def _tool_paper_search(q: str, limit: int = 8) -> Dict[str, Any]:
        return paper_search(q=q, limit=limit)

    return app


APP = build_mcp_app()


def main() -> None:
    if APP is None:
        raise SystemExit("fastmcp is not installed. Run: pip install -r requirements.txt")
    APP.run()


if __name__ == "__main__":
    main()
