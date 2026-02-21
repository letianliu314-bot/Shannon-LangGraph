#!/usr/bin/env python3
from __future__ import annotations

import os

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

# 中文注释：创建 Qdrant 向量集合（参考 Shannon-1 migrations/qdrant）

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
VECTOR_SIZE = int(os.getenv("QDRANT_VECTOR_SIZE", "1536") or 1536)

COLLECTIONS = [
    "task_memories",
    "task_embeddings",
    "document_chunks",
    "summaries",
]


def ensure_collections() -> None:
    client = QdrantClient(url=QDRANT_URL)
    existing = {item.name for item in client.get_collections().collections}

    for name in COLLECTIONS:
        if name in existing:
            print(f"[skip] {name} already exists")
            continue

        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"[ok] created {name}")


if __name__ == "__main__":
    ensure_collections()
