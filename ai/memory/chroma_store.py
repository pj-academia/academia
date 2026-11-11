"""Adaptador de ChromaDB para memorias educativas con aislamiento obligatorio."""

from __future__ import annotations

import json
from hashlib import sha256
from math import hypot, isfinite
from typing import Any, Collection, Mapping, Protocol, Sequence

from ai.memory.retrieval import MemoryRecord, RetrievedMemory, retrieve_memories

MEMORY_TYPES = frozenset({"semantic", "episodic", "preference", "progress"})


class ChromaCollection(Protocol):
    """Métodos de Collection utilizados por el adaptador."""

    @property
    def configuration(self) -> Mapping[str, Any]: ...

    def upsert(self, **kwargs: Any) -> Any: ...

    def query(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def delete(self, **kwargs: Any) -> Any: ...


class ChromaResultError(ValueError):
    """Chroma devolvió datos incompletos o que incumplen el aislamiento."""


class ChromaMemoryStore:
    """Guarda y recupera memorias mediante una colección ya configurada."""

    def __init__(self, collection: ChromaCollection):
        configuration = collection.configuration
        hnsw = configuration.get("hnsw") if isinstance(configuration, Mapping) else None
        if not isinstance(hnsw, Mapping) or hnsw.get("space") != "cosine":
            raise ValueError("La colección debe usar distancia cosine en su índice HNSW.")
        self.collection = collection

    @classmethod
    def from_client(cls, client: Any, *, collection_name: str) -> ChromaMemoryStore:
        """Abre o crea una colección local/servidor con embeddings externos."""
        cls._require_text(collection_name, "collection_name")
        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
        )
        # get_or_create no reconfigura una colección existente: comprobarla.
        return cls(collection)

    def upsert_memory(self, memory: MemoryRecord, *, user_id: str) -> None:
        """Guarda una memoria del alumno autenticado con ID físico por propietario."""
        self._require_text(user_id, "user_id")
        self._validate_memory(memory)
        if memory.user_id != user_id:
            raise ValueError("La memoria no pertenece al alumno autenticado.")
        if memory.status != "active":
            raise ValueError("Para borrar una memoria debe usarse delete_memory.")
        self.collection.upsert(
            ids=[self._storage_id(user_id, memory.memory_id)],
            embeddings=[list(memory.embedding)],
            documents=[memory.content],
            metadatas=[
                {
                    "memory_id": memory.memory_id,
                    "user_id": memory.user_id,
                    "memory_type": memory.memory_type,
                    "status": memory.status,
                    "importance": memory.importance,
                }
            ],
        )

    def query_candidates(
        self,
        query_embedding: Sequence[float],
        *,
        user_id: str,
        n_results: int = 12,
        memory_types: Collection[str] | None = None,
    ) -> list[MemoryRecord]:
        """Consulta Chroma aplicando filtros de propietario y estado activo."""
        self._require_text(user_id, "user_id")
        if type(n_results) is not int or n_results <= 0:
            raise ValueError("n_results debe ser mayor que cero.")

        query_vector = self._validate_vector(query_embedding, "query_embedding")
        filters: list[dict[str, Any]] = [
            {"user_id": {"$eq": user_id}},
            {"status": {"$eq": "active"}},
        ]
        selected_types = self._validate_types(memory_types)
        if selected_types is not None:
            if not selected_types:
                return []
            filters.append({"memory_type": {"$in": selected_types}})

        result = self.collection.query(
            query_embeddings=[list(query_vector)],
            n_results=n_results,
            where={"$and": filters},
            include=["documents", "metadatas", "embeddings"],
        )
        memories = self._map_query_result(result, expected_user_id=user_id)
        if len(memories) > n_results:
            raise ChromaResultError("Chroma devolvió más resultados de los solicitados.")
        if any(len(memory.embedding) != len(query_vector) for memory in memories):
            raise ChromaResultError("La dimensión de las memorias no coincide con la consulta.")
        if selected_types is not None and any(
            memory.memory_type not in selected_types for memory in memories
        ):
            raise ChromaResultError("Chroma devolvió un tipo de memoria no solicitado.")
        return memories

    def retrieve(
        self,
        query_embedding: Sequence[float],
        *,
        user_id: str,
        top_k: int = 3,
        min_similarity: float = 0.70,
        memory_types: Collection[str] | None = None,
    ) -> list[RetrievedMemory]:
        """Recupera candidatas de Chroma y aplica las reglas locales finales."""
        if type(top_k) is not int or top_k <= 0:
            raise ValueError("top_k debe ser mayor que cero.")
        if not -1.0 <= min_similarity <= 1.0:
            raise ValueError("min_similarity debe estar entre -1 y 1.")

        candidates = self.query_candidates(
            query_embedding,
            user_id=user_id,
            n_results=max(top_k * 4, 12),
            memory_types=memory_types,
        )
        return retrieve_memories(
            candidates,
            query_embedding,
            user_id=user_id,
            top_k=top_k,
            min_similarity=min_similarity,
            memory_types=memory_types,
        )

    def delete_memory(self, memory_id: str, *, user_id: str) -> None:
        """Elimina de Chroma una memoria concreta perteneciente al alumno."""
        self._require_text(memory_id, "memory_id")
        self._require_text(user_id, "user_id")
        self.collection.delete(
            ids=[self._storage_id(user_id, memory_id)],
            where={"user_id": {"$eq": user_id}},
        )

    @classmethod
    def _map_query_result(
        cls,
        result: Mapping[str, Any],
        *,
        expected_user_id: str,
    ) -> list[MemoryRecord]:
        try:
            columns = [result[key] for key in ("ids", "documents", "metadatas", "embeddings")]
            if any(len(column) != 1 for column in columns):
                raise ChromaResultError("Chroma debe devolver un único lote de consulta.")
            ids, documents, metadatas, embeddings = [column[0] for column in columns]
            if not (len(ids) == len(documents) == len(metadatas) == len(embeddings)):
                raise ChromaResultError("Las columnas devueltas por Chroma no coinciden.")
            if len(set(ids)) != len(ids):
                raise ChromaResultError("Chroma devolvió identificadores duplicados.")
        except (KeyError, IndexError, TypeError) as error:
            raise ChromaResultError("Respuesta de Chroma incompleta.") from error

        memories: list[MemoryRecord] = []
        for memory_id, document, metadata, embedding in zip(
            ids,
            documents,
            metadatas,
            embeddings,
            strict=True,
        ):
            if not isinstance(metadata, Mapping):
                raise ChromaResultError("Una memoria no contiene metadatos válidos.")
            if metadata.get("user_id") != expected_user_id:
                raise ChromaResultError("Chroma devolvió una memoria de otro alumno.")
            if metadata.get("status") != "active":
                raise ChromaResultError("Chroma devolvió una memoria no activa.")

            try:
                memory = MemoryRecord(
                    memory_id=metadata["memory_id"],
                    user_id=metadata["user_id"],
                    memory_type=metadata["memory_type"],
                    content=document,
                    embedding=cls._validate_vector(
                        embedding,
                        f"embedding de {memory_id}",
                    ),
                    status="active",
                    importance=metadata["importance"],
                )
                cls._validate_memory(memory)
                if memory_id != cls._storage_id(expected_user_id, memory.memory_id):
                    raise ValueError("El identificador físico de la memoria no coincide.")
            except (KeyError, TypeError, ValueError) as error:
                raise ChromaResultError(
                    f"La memoria {memory_id} tiene datos inválidos."
                ) from error
            memories.append(memory)

        return memories

    @classmethod
    def _validate_memory(cls, memory: MemoryRecord) -> None:
        required_text = (
            memory.memory_id,
            memory.user_id,
            memory.memory_type,
            memory.content,
        )
        if any(not isinstance(value, str) or not value.strip() for value in required_text):
            raise ValueError("La memoria contiene campos obligatorios vacíos.")
        if memory.memory_type not in MEMORY_TYPES:
            raise ValueError("El tipo de memoria no es válido.")
        if memory.status not in {"active", "deleted"}:
            raise ValueError("El estado de la memoria no es válido.")
        if type(memory.importance) is not int or not 1 <= memory.importance <= 3:
            raise ValueError("La importancia debe estar entre 1 y 3.")
        cls._validate_vector(memory.embedding, "embedding de la memoria")

    @staticmethod
    def _storage_id(user_id: str, memory_id: str) -> str:
        payload = json.dumps([user_id, memory_id], ensure_ascii=True).encode("utf-8")
        return "memory-" + sha256(payload).hexdigest()

    @staticmethod
    def _require_text(value: str, name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} es obligatorio.")

    @staticmethod
    def _validate_types(memory_types: Collection[str] | None) -> list[str] | None:
        if memory_types is None:
            return None
        if isinstance(memory_types, str):
            raise ValueError("memory_types debe ser una colección de tipos.")
        if any(item not in MEMORY_TYPES for item in memory_types):
            raise ValueError("El filtro contiene un tipo de memoria no válido.")
        return sorted(set(memory_types))

    @staticmethod
    def _validate_vector(vector: Sequence[float], name: str) -> tuple[float, ...]:
        if isinstance(vector, (str, bytes)):
            raise ValueError(f"{name} debe ser un vector numérico.")
        values = tuple(float(value) for value in vector)
        if not values:
            raise ValueError(f"{name} no puede estar vacío.")
        if not all(isfinite(value) for value in values):
            raise ValueError(f"{name} solo puede contener números finitos.")
        norm = hypot(*values)
        if not isfinite(norm) or norm == 0:
            raise ValueError(f"{name} no puede ser un vector cero.")
        return values
