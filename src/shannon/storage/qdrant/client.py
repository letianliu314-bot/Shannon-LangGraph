from __future__ import annotations

import os
import threading
import uuid
from typing import Any, Dict, List, Optional

# 中文注释：Qdrant 客户端（优先真实连接，失败回退内存）


class InMemoryQdrant:
    # 中文注释：内存回退向量库
    def __init__(self) -> None:
        self.collections: dict[str, list[dict[str, Any]]] = {}
        self.vector_size: dict[str, int] = {}
        self._lock = threading.RLock()

    def ensure_collection(self, name: str, vector_size: int) -> None:
        with self._lock:
            self.collections.setdefault(name, [])
            self.vector_size[name] = int(vector_size)

    def upsert(self, collection: str, points: List[Dict[str, Any]]) -> None:
        with self._lock:
            bucket = self.collections.setdefault(collection, [])
            existing_index = {str(point.get("id")): idx for idx, point in enumerate(bucket)}
            for point in points:
                pid = str(point.get("id") or str(uuid.uuid4()))
                candidate = {
                    "id": pid,
                    "vector": list(point.get("vector") or []),
                    "payload": dict(point.get("payload") or {}),
                }
                if pid in existing_index:
                    bucket[existing_index[pid]] = candidate
                else:
                    bucket.append(candidate)

    def search(
        self,
        collection: str,
        query_vector: List[float],
        limit: int = 5,
        filter_payload: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        import math

        with self._lock:
            points = list(self.collections.get(collection, []))

        def cosine(a: List[float], b: List[float]) -> float:
            if not a or not b:
                return 0.0
            n = min(len(a), len(b))
            if n == 0:
                return 0.0
            a2 = a[:n]
            b2 = b[:n]
            dot = sum(x * y for x, y in zip(a2, b2))
            na = math.sqrt(sum(x * x for x in a2))
            nb = math.sqrt(sum(y * y for y in b2))
            if na == 0 or nb == 0:
                return 0.0
            return dot / (na * nb)

        def match_filter(payload: Dict[str, Any]) -> bool:
            if not filter_payload:
                return True
            for key, value in filter_payload.items():
                if payload.get(key) != value:
                    return False
            return True

        scored: List[Dict[str, Any]] = []
        for point in points:
            payload = point.get("payload") if isinstance(point.get("payload"), dict) else {}
            if not match_filter(payload):
                continue
            score = cosine(query_vector, list(point.get("vector") or []))
            scored.append({"id": point.get("id"), "score": score, "payload": payload})

        scored.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
        return scored[: max(1, int(limit))]


class QdrantClientWrapper:
    # 中文注释：函数 __init__ 的入口
    def __init__(self) -> None:
        self.url = os.getenv("QDRANT_URL", "").strip()
        self.default_collection = os.getenv("QDRANT_COLLECTION", "task_memories")
        self.vector_size = int(os.getenv("QDRANT_VECTOR_SIZE", "1536") or 1536)
        self._memory = InMemoryQdrant()
        self._client = None
        self._available = False
        self._init_driver()

    # 中文注释：函数 _init_driver 的入口
    def _init_driver(self) -> None:
        if not self.url:
            self._client = None
            self._available = False
            return

        try:
            from qdrant_client import QdrantClient  # type: ignore

            client = QdrantClient(url=self.url, timeout=5.0)
            client.get_collections()
            self._client = client
            self._available = True
        except Exception:
            self._client = None
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    # 中文注释：函数 ensure_collection 的入口
    def ensure_collection(self, name: Optional[str] = None, vector_size: Optional[int] = None) -> str:
        collection = name or self.default_collection
        dim = int(vector_size or self.vector_size)

        if self.available and self._client is not None:
            from qdrant_client.models import Distance, VectorParams  # type: ignore

            collections = self._client.get_collections().collections
            if not any(item.name == collection for item in collections):
                self._client.create_collection(
                    collection_name=collection,
                    vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
                )
            return collection

        self._memory.ensure_collection(collection, dim)
        return collection

    # 中文注释：函数 upsert 的入口
    def upsert(self, collection: str, points: List[Dict[str, Any]]) -> None:
        target_collection = self.ensure_collection(collection)
        if self.available and self._client is not None:
            from qdrant_client.models import PointStruct  # type: ignore

            packed_points = []
            for point in points:
                packed_points.append(
                    PointStruct(
                        id=point.get("id") or str(uuid.uuid4()),
                        vector=list(point.get("vector") or []),
                        payload=dict(point.get("payload") or {}),
                    )
                )
            self._client.upsert(collection_name=target_collection, points=packed_points)
            return

        self._memory.upsert(target_collection, points)

    # 中文注释：函数 search 的入口
    def search(
        self,
        collection: str,
        query_vector: List[float],
        limit: int = 5,
        filter_payload: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        target_collection = self.ensure_collection(collection)

        if self.available and self._client is not None:
            if filter_payload:
                from qdrant_client.models import FieldCondition, Filter, MatchValue  # type: ignore

                conditions = [FieldCondition(key=key, match=MatchValue(value=value)) for key, value in filter_payload.items()]
                qfilter = Filter(must=conditions)
            else:
                qfilter = None

            hits = self._client.search(
                collection_name=target_collection,
                query_vector=query_vector,
                limit=max(1, int(limit)),
                query_filter=qfilter,
            )
            return [
                {
                    "id": hit.id,
                    "score": float(hit.score),
                    "payload": dict(hit.payload or {}),
                }
                for hit in hits
            ]

        return self._memory.search(
            collection=target_collection,
            query_vector=query_vector,
            limit=limit,
            filter_payload=filter_payload,
        )


# 中文注释：单例 Qdrant 客户端
qdrant_client = QdrantClientWrapper()
