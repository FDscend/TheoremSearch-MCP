| English | [中文](README.zh.md) |
| ------- | -------------------- |

# TheoremSearch-MCP

An MCP wrapper for [TheoremSearch](https://www.theoremsearch.com/) (UW Math AI Lab), which semantically searches about **9.27 million mathematical statements** across 8 sources including arXiv, Stacks Project, and ProofWiki.

This repository provides two integration paths:

| Path                                 | Description                                                      | Tools                              |
| ------------------------------------ | ---------------------------------------------------------------- | ---------------------------------- |
| **A. Official Remote MCP**           | Register `https://api.theoremsearch.com/mcp` directly, zero code | 1 tool (`theorem_search`)          |
| **B. Local MCP Wrapper** (this repo) | Python MCP server that calls TheoremSearch REST APIs             | 5 tools (search + filters + graph) |

---

## Quick Test (No MCP Setup Needed)

If you just want to evaluate search quality first, run the script (only `requests` is required):

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts\quick_test.py
```

It demonstrates semantic search, filtered search (source/type/year), whole-corpus graph search (including formal Lean), paper autocomplete, and dependency graph traversal.

You can also call the API directly with curl:

```powershell
curl -s -X POST https://api.theoremsearch.com/search -H "Content-Type: application/json" -d '{"query":"Any projective module over a local ring is free","n_results":3}'
```

---

## Path A: Official Remote MCP (Fastest)

### Codex

Add this to `.codex/config.toml` in your target project:

```toml
[mcp_servers.theoremsearch_remote]
url = "https://api.theoremsearch.com/mcp"
tool_timeout_sec = 120
```

### VS Code (GitHub Copilot / MCP-capable clients)

Create `.vscode/mcp.json` in the project:

```json
{
  "servers": {
    "theoremsearch-remote": {
      "type": "http",
      "url": "https://api.theoremsearch.com/mcp"
    }
  }
}
```

### Claude Desktop

Add this to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "theoremsearch-remote": {
      "type": "http",
      "url": "https://api.theoremsearch.com/mcp"
    }
  }
}
```

> The official remote MCP exposes a single tool, `theorem_search`, with parameters matching `POST /search` (including `sources`, `types`, `year_range`, `citation_range`, `citation_weight`, etc.), and supports `initialize` / `tools/list` / `tools/call`.

---

## Path B: Local MCP Wrapper (This Repo, Recommended)

This wrapper provides 5 tools, adding graph capabilities beyond the official MCP:

| Tool              | Backend                     | Purpose                                                                                                                                                              |
| ----------------- | --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `theorem_search`  | `POST /search`              | Main semantic search with filters (source/author/type/year/citations) and optional citation weighting                                                                |
| `graph_search`    | `GET /graph/embedding`      | Whole-corpus semantic search (`formality`: `informal`/`formal`/`both`, including Lean-formalized content). **Note: `formal` can be slow (>60s).**                    |
| `graph_statement` | `GET /graph/statement/{id}` | Traverse dependency edges from a `statement_id` (`direction=src/dep/both`). **Note: `formality` only accepts `informal`/`formal` (`both` is rejected by live API).** |
| `graph_paper`     | `GET /graph/paper`          | Retrieve all statements and dependency edges for a paper/Lean repo (via arXiv ID, repo slug, or UUID)                                                                |
| `paper_search`    | `GET /paper-search`         | Paper title / arXiv ID autocomplete                                                                                                                                  |

### Install and Run

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

After activating your virtual environment, add this to `.codex/config.toml` in the target project:

```toml
[mcp_servers.theoremsearch]
command = "python"
args = ["-E", "./server.py"]
cwd = "./"
tool_timeout_sec = 120
```

> `-E` ignores `PYTHONPATH`, preventing a local `mcp/` directory from shadowing the official MCP SDK required by `fastmcp`.

For VS Code, use `.vscode/mcp.json`:

```json
{
  "servers": {
    "theoremsearch-local": {
      "type": "stdio",
      "command": "python",
      "args": ["-E", "${workspaceFolder}/server.py"]
    }
  }
}
```

You can also manually run the server in stdio mode for validation:

```powershell
.venv\Scripts\python -E .\server.py
```

---

## Usage Examples

Use theorem-like statements as queries (more complete statements usually work better):

```
theorem_search(query="Any projective module over a local ring is free", n_results=5)
```

Filtered search example (lemmas in Stacks Project after 2010):

```
theorem_search(query="smooth DM stack has a dense open subscheme", sources=["Stacks Project"], types=["Lemma"], year_range=[2010, 2024])
```

Citation-weighted search example (highly cited classical results):

```
theorem_search(query="Hahn-Banach separation theorem", citation_weight=0.5, citation_range=[100, 5000])
```

Two-step dependency-graph workflow: first get a `statement_id` from whole-corpus graph search, then traverse dependencies (`graph_statement` accepts `informal` or `formal`, not `both`):

```
graph_search(query="any projective module over a local ring is free", formality="both", n_results=1)
graph_statement(statement_id="<statement_id from previous step>", direction="both", formality="informal")
```

---

## Notes

- Public API examples do not require an API key, but production rate limits are not publicly specified. Control request frequency (for example, global serialized 1 req/s).
- Default request timeout is 180s (`/graph/embedding` with `formality=formal` can exceed 60s in practice). Large `n_results` or `db_top_k` increases latency.
- `year_range` and `citation_range` should be 2-item arrays: `[min, max]`.
- **There are a few live-API vs doc mismatches (corrected here based on observed behavior):** `/graph/statement` accepts only `informal`/`formal`; response shape is `{root, nodes, edges}` instead of documented `{statement, neighbors}`; `/graph/paper` returns `{paper, statements, edges}` instead of `{..., dependencies}`. Recheck if upstream APIs change.
