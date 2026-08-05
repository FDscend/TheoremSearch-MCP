"""Quick hands-on test of the TheoremSearch API (no MCP setup required).

Run:
    .venv\\Scripts\\python scripts\\quick_test.py

Only requires `requests`. Demonstrates the search quality of each endpoint.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server import graph_search, graph_statement, paper_search, theorem_search  # noqa: E402


def _show(title: str, data: object) -> None:
    print("=" * 70)
    print(title)
    print("=" * 70)
    print(json.dumps(data, ensure_ascii=False, indent=2)[:3500])
    print()


def main() -> None:
    _show(
        "1) theorem_search: 经典代数结论",
        theorem_search(query="Any projective module over a local ring is free", n_results=3),
    )

    _show(
        "2) theorem_search: 过滤（Stacks Project + ProofWiki, 2010-2024, Lemma）",
        theorem_search(
            query="smooth DM stack has a dense open subscheme",
            n_results=3,
            sources=["Stacks Project", "ProofWiki"],
            types=["Lemma"],
            year_range=[2010, 2024],
        ),
    )

    _show(
        "3) graph_search: 全语料（含 formal Lean）",
        graph_search(query="fundamental theorem of calculus", n_results=3, formality="both"),
    )

    _show(
        "4) paper_search: 论文自动补全",
        paper_search(q="derived categories", limit=3),
    )

    # 5) 演示两步流程：先拿到 statement_id，再沿依赖边漫游。
    #    注意：/graph/statement 的 formality 只接受 informal/formal（线上 API 拒绝 both），
    #    这里用 informal 保持快速（formal 语料检索可能超过 60s）。
    embedding = graph_search(
        query="any projective module over a local ring is free",
        n_results=1,
        formality="informal",
    )
    results = embedding.get("results", [])
    if results:
        sid = results[0]["statement_id"]
        _show(
            f"5) graph_statement: 沿依赖图查看 '{sid}' 的邻域",
            graph_statement(sid, direction="both", formality="informal"),
        )
    else:
        print("5) graph_statement: 未取到 statement_id，跳过")


if __name__ == "__main__":
    main()
