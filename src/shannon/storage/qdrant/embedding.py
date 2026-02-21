from __future__ import annotations

import hashlib
import os
from typing import List

# 中文注释：向量嵌入提供器（优先 OpenAI embeddings，失败回退哈希向量）


class EmbeddingProvider:
    # 中文注释：函数 __init__ 的入口
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        self.vector_size = int(os.getenv("QDRANT_VECTOR_SIZE", "1536") or 1536)

    # 中文注释：函数 _hash_embedding 的入口
    def _hash_embedding(self, text: str) -> List[float]:
        # 中文注释：稳定可复现哈希向量，避免依赖外部模型时不可用
        dim = self.vector_size
        if dim <= 0:
            dim = 1536

        source = (text or "").encode("utf-8", errors="ignore")
        values: List[float] = []
        counter = 0
        while len(values) < dim:
            digest = hashlib.sha256(source + f":{counter}".encode("utf-8")).digest()
            for idx in range(0, len(digest), 2):
                if len(values) >= dim:
                    break
                chunk = digest[idx : idx + 2]
                number = int.from_bytes(chunk, byteorder="big", signed=False)
                # 中文注释：映射到 [-1, 1] 区间
                value = (number / 65535.0) * 2.0 - 1.0
                values.append(value)
            counter += 1
        return values

    # 中文注释：函数 embed_text 的入口
    def embed_text(self, text: str) -> List[float]:
        if not self.api_key:
            return self._hash_embedding(text)

        try:
            from openai import OpenAI  # type: ignore

            client = OpenAI(api_key=self.api_key)
            response = client.embeddings.create(model=self.model, input=[text or ""])
            embedding = response.data[0].embedding
            return [float(v) for v in embedding]
        except Exception:
            return self._hash_embedding(text)


# 中文注释：单例 Embedding 提供器
embedding_provider = EmbeddingProvider()
