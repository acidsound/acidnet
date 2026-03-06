from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(slots=True)
class SearchHit:
    doc_id: str
    score: float


class NullVectorStore:
    def upsert_memory(self, doc_id: str, vector: list[float]) -> None:
        return None

    def search(self, vector: list[float], topk: int = 5) -> list[SearchHit]:
        return []


class ZvecVectorStore:
    def __init__(self, path: str, dimensions: int) -> None:
        if sys.platform.startswith("win"):
            raise RuntimeError("zvec currently documents Linux/macOS support, so Windows should use SQLite-only mode for now.")
        import zvec

        self._zvec = zvec
        self._collection = zvec.create_and_open(
            path=path,
            schema=zvec.CollectionSchema(
                name="acidnet_memory",
                vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, dimensions),
            ),
        )

    def upsert_memory(self, doc_id: str, vector: list[float]) -> None:
        self._collection.insert([self._zvec.Doc(id=doc_id, vectors={"embedding": vector})])

    def search(self, vector: list[float], topk: int = 5) -> list[SearchHit]:
        return [
            SearchHit(doc_id=result["id"], score=float(result["score"]))
            for result in self._collection.query(self._zvec.VectorQuery("embedding", vector=vector), topk=topk)
        ]
