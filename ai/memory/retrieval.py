"""Núcleo independiente para recuperar memorias educativas relevantes.

La búsqueda vectorial real se conectará más adelante a ChromaDB. Este módulo
define las reglas que deben cumplirse siempre, con independencia del adaptador:
aislamiento por alumno, exclusión de borrados, umbral y límite de resultados.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Collection, Iterable, Sequence


@dataclass(frozen=True)
class MemoryRecord:
    """Memoria candidata devuelta por el almacén vectorial."""

    memory_id: str
    user_id: str
    memory_type: str
    content: str
    embedding: tuple[float, ...]
    status: str = "active"
    importance: int = 1


@dataclass(frozen=True)
class RetrievedMemory:
    """Memoria autorizada junto con su similitud semántica."""

    memory: MemoryRecord
    similarity: float


def retrieve_memories(
    memories: Iterable[MemoryRecord],
    query_embedding: Sequence[float],
    *,
    user_id: str,
    top_k: int = 3,
    min_similarity: float = 0.70,
    memory_types: Collection[str] | None = None,
) -> list[RetrievedMemory]:
    """Selecciona memorias activas, autorizadas y suficientemente relevantes.

    El filtro de propietario se aplica antes de calcular similitudes. Esto evita
    que una memoria de otro alumno pueda aparecer o influir en los resultados.
    """
    if not user_id.strip():
        raise ValueError("user_id es obligatorio.")
    if top_k <= 0:
        raise ValueError("top_k debe ser mayor que cero.")
    if not -1.0 <= min_similarity <= 1.0:
        raise ValueError("min_similarity debe estar entre -1 y 1.")

    query_vector = _validate_vector(query_embedding, "query_embedding")
    allowed_types = set(memory_types) if memory_types is not None else None
    selected: list[RetrievedMemory] = []

    for memory in memories:
        if memory.user_id != user_id or memory.status != "active":
            continue
        if allowed_types is not None and memory.memory_type not in allowed_types:
            continue

        memory_vector = _validate_vector(
            memory.embedding,
            f"embedding de la memoria {memory.memory_id}",
        )
        if len(memory_vector) != len(query_vector):
            raise ValueError(
                f"La memoria {memory.memory_id} y la consulta tienen dimensiones distintas."
            )

        similarity = _cosine_similarity(query_vector, memory_vector)
        if similarity >= min_similarity:
            selected.append(RetrievedMemory(memory=memory, similarity=similarity))

    selected.sort(
        key=lambda result: (
            -result.similarity,
            -result.memory.importance,
            result.memory.memory_id,
        )
    )
    return selected[:top_k]


def _validate_vector(vector: Sequence[float], name: str) -> tuple[float, ...]:
    if not vector:
        raise ValueError(f"{name} no puede estar vacío.")

    values = tuple(float(value) for value in vector)
    if not all(isfinite(value) for value in values):
        raise ValueError(f"{name} solo puede contener números finitos.")
    if sqrt(sum(value * value for value in values)) == 0:
        raise ValueError(f"{name} no puede ser un vector cero.")
    return values


def _cosine_similarity(first: Sequence[float], second: Sequence[float]) -> float:
    numerator = sum(left * right for left, right in zip(first, second, strict=True))
    first_norm = sqrt(sum(value * value for value in first))
    second_norm = sqrt(sum(value * value for value in second))
    return numerator / (first_norm * second_norm)
