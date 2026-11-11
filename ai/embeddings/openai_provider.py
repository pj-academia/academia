"""Adaptador de embeddings compatible con el cliente oficial de OpenAI."""

from __future__ import annotations

import os
from dataclasses import dataclass
from math import isfinite
from typing import Any, Protocol, Sequence


MAX_BATCH_SIZE = 2048


class EmbeddingsEndpoint(Protocol):
    """Parte mínima del SDK oficial que utiliza este adaptador."""

    def create(self, **kwargs: Any) -> Any: ...


class OpenAIClient(Protocol):
    embeddings: EmbeddingsEndpoint


@dataclass(frozen=True)
class OpenAIEmbeddingProvider:
    """Genera vectores sin acoplar la lógica de memoria al SDK completo."""

    client: OpenAIClient
    model: str
    dimensions: int | None = None

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("El modelo de embeddings es obligatorio.")
        if self.dimensions is not None and self.dimensions <= 0:
            raise ValueError("dimensions debe ser mayor que cero.")

    @classmethod
    def from_environment(cls) -> OpenAIEmbeddingProvider:
        """Crea el proveedor con la configuración local del backend.

        El cliente oficial lee ``OPENAI_API_KEY`` del entorno. La clave nunca
        se recibe, almacena ni registra dentro de este módulo.
        """
        model = os.getenv("OPENAI_EMBEDDING_MODEL", "").strip()
        if not model:
            raise ValueError("Falta OPENAI_EMBEDDING_MODEL en el entorno.")

        raw_dimensions = os.getenv("OPENAI_EMBEDDING_DIMENSIONS", "").strip()
        try:
            dimensions = int(raw_dimensions) if raw_dimensions else None
        except ValueError as error:
            raise ValueError(
                "OPENAI_EMBEDDING_DIMENSIONS debe ser un número entero."
            ) from error

        try:
            from openai import OpenAI
        except ImportError as error:
            raise RuntimeError(
                "El paquete oficial 'openai' no está instalado en este entorno."
            ) from error

        return cls(client=OpenAI(), model=model, dimensions=dimensions)

    def embed_text(self, text: str) -> tuple[float, ...]:
        """Genera el embedding de un único texto."""
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        """Genera un lote de embeddings y conserva el orden de entrada."""
        normalized = [text.strip() for text in texts]
        if not normalized:
            raise ValueError("Debe proporcionarse al menos un texto.")
        if len(normalized) > MAX_BATCH_SIZE:
            raise ValueError(f"El lote no puede superar {MAX_BATCH_SIZE} textos.")
        if any(not text for text in normalized):
            raise ValueError("Los textos para embeddings no pueden estar vacíos.")

        request: dict[str, Any] = {
            "input": normalized,
            "model": self.model,
            "encoding_format": "float",
        }
        if self.dimensions is not None:
            request["dimensions"] = self.dimensions

        response = self.client.embeddings.create(**request)
        data = sorted(response.data, key=lambda item: item.index)
        if len(data) != len(normalized):
            raise ValueError("OpenAI devolvió un número inesperado de embeddings.")
        if [item.index for item in data] != list(range(len(normalized))):
            raise ValueError("OpenAI devolvió índices de embeddings inesperados.")

        embeddings = [self._validate_embedding(item.embedding) for item in data]
        expected_size = len(embeddings[0])
        if any(len(embedding) != expected_size for embedding in embeddings):
            raise ValueError("OpenAI devolvió embeddings con dimensiones distintas.")
        if self.dimensions is not None and expected_size != self.dimensions:
            raise ValueError("OpenAI devolvió una dimensión distinta a la solicitada.")
        return embeddings

    @staticmethod
    def _validate_embedding(values: Sequence[float]) -> tuple[float, ...]:
        embedding = tuple(float(value) for value in values)
        if not embedding:
            raise ValueError("OpenAI devolvió un embedding vacío.")
        if not all(isfinite(value) for value in embedding):
            raise ValueError("OpenAI devolvió un embedding no finito.")
        return embedding
