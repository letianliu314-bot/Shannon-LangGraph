from __future__ import annotations

from typing import Dict, List, Optional

from shannon.storage.qdrant.vector_store import vector_store

# 中文注释：语义检索接口（RAG-like）


def semantic_search(
    query: str,
    limit: int = 5,
    collection: Optional[str] = None,
    filter_payload: Optional[Dict[str, object]] = None,
) -> List[Dict[str, object]]:
    # 中文注释：按 query 文本做向量检索
    return vector_store.search_text(
        query=query,
        limit=limit,
        collection=collection,
        filter_payload=filter_payload,
    )
