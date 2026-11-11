"""Coordina embeddings y búsqueda para preparar contexto educativo acotado."""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import isfinite
from typing import Collection, Protocol, Sequence

from ai.memory.chroma_store import MEMORY_TYPES
from ai.memory.retrieval import RetrievedMemory


class EmbeddingProvider(Protocol):
    def embed_text(self, text: str) -> tuple[float, ...]: ...


class MemoryRetriever(Protocol):
    def retrieve(
        self,
        query_embedding: Sequence[float],
        *,
        user_id: str,
        top_k: int,
        min_similarity: float,
        memory_types: Collection[str] | None,
    ) -> list[RetrievedMemory]: ...


class MemoryContextError(ValueError):
    """El almacén devolvió recuerdos que no cumplen el contrato del contexto."""


@dataclass(frozen=True)
class MemoryContextPolicy:
    top_k: int = 3
    min_similarity: float = 0.70
    max_query_chars: int = 4000
    max_memory_chars: int = 600
    max_context_chars: int = 1800

    def __post_init__(self) -> None:
        limits = (
            self.top_k,
            self.max_query_chars,
            self.max_memory_chars,
            self.max_context_chars,
        )
        if any(type(value) is not int or value <= 0 for value in limits):
            raise ValueError("Los límites del contexto deben ser enteros positivos.")
        if self.top_k > 10:
            raise ValueError("El contexto admite un máximo de 10 memorias.")
        if self.max_context_chars < len(MemoryContext().to_json()):
            raise ValueError("El presupuesto debe permitir al menos el JSON de contexto vacío.")
        if (
            isinstance(self.min_similarity, bool)
            or not isinstance(self.min_similarity, (int, float))
            or not isfinite(self.min_similarity)
            or not -1 <= self.min_similarity <= 1
        ):
            raise ValueError("min_similarity debe ser un número finito entre -1 y 1.")


@dataclass(frozen=True)
class MemoryContextItem:
    memory_id: str
    memory_type: str
    content: str
    similarity: float


@dataclass(frozen=True)
class MemoryContext:
    items: tuple[MemoryContextItem, ...] = ()

    def to_json(self) -> str:
        """Serializa los recuerdos como datos; no es un mensaje de sistema.

        Se excluye la similitud: sirve para búsqueda, no es confianza educativa.
        El constructor del prompt deberá mantener la regla de tratar este JSON
        como referencia no confiable y comprobar la autorización en PostgreSQL.
        """
        return json.dumps(
            {
                "kind": "untrusted_educational_memories",
                "memories": [
                    {
                        "memory_id": item.memory_id,
                        "memory_type": item.memory_type,
                        "content": item.content,
                    }
                    for item in self.items
                ],
            },
            ensure_ascii=False,
        )


class MemoryContextService:
    """Una consulta de texto entra; un contexto sin vectores sale."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        store: MemoryRetriever,
        *,
        policy: MemoryContextPolicy | None = None,
    ):
        self.embedding_provider = embedding_provider
        self.store = store
        self.policy = policy if policy is not None else MemoryContextPolicy()

    def recall(
        self,
        query: str,
        *,
        user_id: str,
        memory_types: Collection[str] | None = None,
    ) -> MemoryContext:
        """Obtiene el contexto de una consulta sin guardar ni cachear recuerdos.

        El backend debe proporcionar el propietario de la sesión autenticada.
        Los errores del proveedor/almacén se propagan: un error no se confunde
        con una búsqueda correcta sin resultados.
        """
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id es obligatorio.")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("La consulta no puede estar vacía.")
        if len(query) > self.policy.max_query_chars:
            raise ValueError("La consulta supera la longitud máxima permitida.")

        selected_types = None
        if memory_types is not None:
            if isinstance(memory_types, (str, bytes)):
                raise ValueError("memory_types debe ser una colección de tipos.")
            if any(not isinstance(item, str) or item not in MEMORY_TYPES for item in memory_types):
                raise ValueError("El filtro contiene un tipo de memoria no válido.")
            selected_types = tuple(sorted(set(memory_types)))
            if not selected_types:
                return MemoryContext()

        vector = self.embedding_provider.embed_text(query.strip())
        matches = self.store.retrieve(
            vector,
            user_id=user_id,
            top_k=self.policy.top_k,
            min_similarity=self.policy.min_similarity,
            memory_types=selected_types,
        )
        if len(matches) > self.policy.top_k:
            raise MemoryContextError("El almacén devolvió más recuerdos de los permitidos.")

        items: list[MemoryContextItem] = []
        seen_ids: set[str] = set()
        for match in matches:
            memory = match.memory
            if memory.user_id != user_id or memory.status != "active":
                raise MemoryContextError("El almacén devolvió una memoria no autorizada.")
            if (
                memory.memory_type not in MEMORY_TYPES
                or selected_types is not None and memory.memory_type not in selected_types
                or not isinstance(memory.memory_id, str)
                or not memory.memory_id.strip()
                or memory.memory_id in seen_ids
                or not isinstance(memory.content, str)
                or not memory.content.strip()
                or isinstance(match.similarity, bool)
                or not isinstance(match.similarity, (int, float))
                or not isfinite(match.similarity)
                or match.similarity < self.policy.min_similarity
            ):
                raise MemoryContextError("El almacén devolvió una memoria inválida.")
            seen_ids.add(memory.memory_id)
            # Omitir resúmenes demasiado largos; no cortar frases ni alterar hechos.
            if len(memory.content) > self.policy.max_memory_chars:
                continue
            item = MemoryContextItem(
                memory_id=memory.memory_id,
                memory_type=memory.memory_type,
                content=memory.content,
                similarity=match.similarity,
            )
            candidate = MemoryContext(items=(*items, item))
            # Contar también metadatos y escapes JSON, no solo los resúmenes.
            if len(candidate.to_json()) <= self.policy.max_context_chars:
                items.append(item)
        return MemoryContext(items=tuple(items))
