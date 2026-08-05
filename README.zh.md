| [English](README.md) | 中文 |
| -------------------- | ---- |

# TheoremSearch-MCP

把 [TheoremSearch](https://www.theoremsearch.com/)（UW Math AI Lab，语义搜索约 **927 万条数学定理**，覆盖 arXiv + Stacks Project + ProofWiki 等 8 个来源）封装成 **agent 可调用的 MCP 工具**，用于在任意项目中体验和评估。

包含两种接入方式：

| 方式                             | 说明                                                 | 工具数                       |
| -------------------------------- | ---------------------------------------------------- | ---------------------------- |
| **A. 官方远程 MCP**              | 直接注册 `https://api.theoremsearch.com/mcp`，零代码 | 1 个（`theorem_search`）     |
| **B. 本地 MCP 包装器**（本仓库） | 自写 Python MCP server，内部调用 REST API            | 5 个（搜索 + 过滤 + 依赖图） |

---

## 快速体验（不需要配 MCP）

如果只是想先感受搜索结果质量，直接跑脚本（只需 `requests`）：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts\quick_test.py
```

它会依次演示：语义搜索、带过滤的搜索（来源/类型/年份）、全语料搜索（含 formal Lean）、论文补全、依赖图漫游。

也可以不装任何东西，直接 curl：

```powershell
curl -s -X POST https://api.theoremsearch.com/search -H "Content-Type: application/json" -d '{"query":"Any projective module over a local ring is free","n_results":3}'
```

---

## 方案 A：官方远程 MCP（最快体验）

### Codex

在目标项目的 `.codex/config.toml` 中加入：

```toml
[mcp_servers.theoremsearch_remote]
url = "https://api.theoremsearch.com/mcp"
tool_timeout_sec = 120
```

### VS Code（GitHub Copilot / 支持 MCP 的客户端）

在项目下放 `.vscode/mcp.json`：

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

在 `claude_desktop_config.json` 中加入：

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

> 官方远程 MCP 只有一个工具 `theorem_search`，参数与 `POST /search` 相同（含 `sources`、`types`、`year_range`、`citation_range`、`citation_weight` 等），支持 `initialize` / `tools/list` / `tools/call`。

---

## 方案 B：本地 MCP 包装器（本仓库，推荐）

封装了 5 个工具，比官方 MCP 多出依赖图检索能力：

| 工具              | 后端                        | 用途                                                                                                                                    |
| ----------------- | --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `theorem_search`  | `POST /search`              | 主搜索：语义检索 + 过滤（来源/作者/类型/年份/引用数）+ 可选引用加权                                                                     |
| `graph_search`    | `GET /graph/embedding`      | 全语料语义搜索（`formality` 可选 `informal`/`formal`/`both`，覆盖 Lean 形式化语句）。**注意：`formal` 语料很慢，可能超过 60s**          |
| `graph_statement` | `GET /graph/statement/{id}` | 给定 `statement_id`，沿依赖边漫游（`direction=src/dep/both`）。**注意：`formality` 只接受 `informal`/`formal`（线上 API 拒绝 `both`）** |
| `graph_paper`     | `GET /graph/paper`          | 取某篇论文/Lean 仓库的全部语句与依赖边（用 arXiv ID 或 repo slug 或 UUID）                                                              |
| `paper_search`    | `GET /paper-search`         | 论文标题 / arXiv ID 自动补全                                                                                                            |

### 安装与启动

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

在激活 venv 后，把以下配置放进目标项目的 `.codex/config.toml`：

```toml
[mcp_servers.theoremsearch]
command = "python"
args = ["-E", "./server.py"]
cwd = "./"
tool_timeout_sec = 120
```

> `-E` 忽略 PYTHONPATH，避免本地存在 `mcp/` 目录时遮蔽 fastmcp 依赖的官方 mcp SDK。

VS Code 则用 `.vscode/mcp.json`：

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

也可以直接以 stdio 方式手动启动验证：

```powershell
.venv\Scripts\python -E .\server.py
```

---

## 使用示例

以数学陈述作为 query（越接近完整命题效果越好）：

```
theorem_search(query="Any projective module over a local ring is free", n_results=5)
```

带过滤，找 Stacks Project 里 2010 年后的引理：

```
theorem_search(query="smooth DM stack has a dense open subscheme", sources=["Stacks Project"], types=["Lemma"], year_range=[2010, 2024])
```

按引用加权，找高被引的经典结论：

```
theorem_search(query="Hahn-Banach separation theorem", citation_weight=0.5, citation_range=[100, 5000])
```

依赖图两步走：先全语料检索拿 `statement_id`，再漫游其证明依赖（`graph_statement` 的 `formality` 用 `informal` 或 `formal`，不要用 `both`）：

```
graph_search(query="any projective module over a local ring is free", formality="both", n_results=1)
graph_statement(statement_id="<上一步返回的 statement_id>", direction="both", formality="informal")
```

---

## 注意事项

- 公共 API，文档示例无需 API key；作为生产服务，限流策略未公开，建议控制调用频率（例如全局 1 req/s 串行限速）。
- 请求超时默认 180s（`/graph/embedding` 的 `formality=formal` 实测可能超过 60s）；大 `n_results` / 大 `db_top_k` 会变慢。
- `year_range` / `citation_range` 传 `[min, max]` 二元列表。
- **线上 API 与官方文档有几处不一致（已按线上实测修正）**：`/graph/statement` 的 `formality` 只接受 `informal`/`formal`；其返回结构是 `{root, nodes, edges}` 而非文档的 `{statement, neighbors}`；`/graph/paper` 返回 `{paper, statements, edges}` 而非 `{..., dependencies}`。若官方更新接口，留意这些差异。
