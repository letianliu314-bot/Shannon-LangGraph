from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, List, Optional

from shannon.storage.qdrant.client import qdrant_client
from shannon.storage.qdrant.embedding import embedding_provider

# 中文注释：向量记忆存储（Qdrant + 本地回退）


class VectorStore:
    # 中文注释：函数 __init__ 的入口
    def __init__(self, default_collection: Optional[str] = None) -> None:
        self.default_collection = default_collection or os.getenv("QDRANT_COLLECTION", "task_memories")
        self.vector_size = int(os.getenv("QDRANT_VECTOR_SIZE", "1536") or 1536)
        qdrant_client.ensure_collection(self.default_collection, self.vector_size)

    # 中文注释：函数 _normalize_point 的入口
    def _normalize_point(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        point_id = payload.get("id") or str(uuid.uuid4())
        vector = payload.get("vector") if isinstance(payload.get("vector"), list) else None
        text = str(payload.get("text") or payload.get("content") or "")
        metadata = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}

        if vector is None:
            vector = embedding_provider.embed_text(text)

        enriched_payload = dict(metadata)
        enriched_payload.setdefault("text", text)
        enriched_payload.setdefault("timestamp", int(time.time()))

        return {
            "id": point_id,
            "vector": [float(v) for v in vector],
            "payload": enriched_payload,
        }

    # 中文注释：函数 upsert 的入口（兼容旧接口）
    def upsert(self, payload: Dict[str, Any], collection: Optional[str] = None) -> str:
        target_collection = collection or self.default_collection
        point = self._normalize_point(payload)
        qdrant_client.upsert(target_collection, [point])
        return str(point["id"])

    # 中文注释：函数 upsert_text 的入口
    def upsert_text(
        self,
        text: str,
        payload: Optional[Dict[str, Any]] = None,
        collection: Optional[str] = None,
        point_id: Optional[str] = None,
    ) -> str:
        target_collection = collection or self.default_collection
        point = {
            "id": point_id or str(uuid.uuid4()),
            "text": text,
            "payload": payload or {},
        }
        return self.upsert(point, collection=target_collection)

    # 中文注释：函数 search_by_vector 的入口
    def search_by_vector(
        self,
        query_vector: List[float],
        limit: int = 5,
        collection: Optional[str] = None,
        filter_payload: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        target_collection = collection or self.default_collection
        return qdrant_client.search(
            collection=target_collection,
            query_vector=[float(v) for v in query_vector],
            limit=max(1, int(limit)),
            filter_payload=filter_payload,
        )

    # 中文注释：函数 search_text 的入口
    def search_text(
        self,
        query: str,
        limit: int = 5,
        collection: Optional[str] = None,
        filter_payload: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        query_vector = embedding_provider.embed_text(query)
        return self.search_by_vector(
            query_vector=query_vector,
            limit=limit,
            collection=collection,
            filter_payload=filter_payload,
        )


# 中文注释：单例向量存储
vector_store = VectorStore()
