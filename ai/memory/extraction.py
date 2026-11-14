"""Validación determinista de propuestas de memoria generadas por un modelo."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from math import isfinite
from typing import Mapping, Protocol, Sequence


MEMORY_EXTRACTION_PROMPT_VERSION = "memory-extraction-v2"
MEMORY_ACTIONS = frozenset({"create", "update", "discard"})
MEMORY_TYPES = frozenset({"semantic", "episodic", "preference", "progress"})
MIN_MEMORY_CONFIDENCE = 0.70
MAX_PROPOSAL_JSON_CHARS = 5000
EXPECTED_FIELDS = frozenset(
    {
        "action",
        "target_memory_id",
        "memory_type",
        "content",
        "topic",
        "importance",
        "confidence",
        "reason",
    }
)


class MemoryExtractionError(ValueError):
    """La propuesta generada no cumple la política de memoria."""


@dataclass(frozen=True)
class ExistingMemory:
    memory_id: str
    memory_type: str
    content: str


@dataclass(frozen=True)
class MemoryExtractionDecision:
    action: str
    target_memory_id: str | None
    memory_type: str | None
    content: str | None
    topic: str | None
    importance: int | None
    confidence: float | None
    reason: str
    prompt_version: str = MEMORY_EXTRACTION_PROMPT_VERSION


class MemoryExtractionGenerator(Protocol):
    def generate(
        self,
        interaction: str,
        *,
        existing_memories: Sequence[ExistingMemory],
        prompt_version: str,
    ) -> str | Mapping[str, object]: ...


class MemoryExtractionService:
    """Solicita una propuesta y aplica reglas que el modelo no puede decidir."""

    def __init__(
        self,
        generator: MemoryExtractionGenerator,
        *,
        max_interaction_chars: int = 4000,
        max_existing_memories: int = 20,
    ) -> None:
        if type(max_interaction_chars) is not int or max_interaction_chars <= 0:
            raise ValueError("max_interaction_chars debe ser un entero positivo.")
        if type(max_existing_memories) is not int or max_existing_memories <= 0:
            raise ValueError("max_existing_memories debe ser un entero positivo.")
        self.generator = generator
        self.max_interaction_chars = max_interaction_chars
        self.max_existing_memories = max_existing_memories

    def propose(
        self,
        interaction: str,
        *,
        existing_memories: Sequence[ExistingMemory] = (),
        source_blocked: bool = False,
    ) -> MemoryExtractionDecision:
        message = self._validate_interaction(interaction)
        memories = self._validate_existing_memories(existing_memories)
        if type(source_blocked) is not bool:
            raise ValueError("source_blocked debe ser booleano.")
        if source_blocked:
            return MemoryExtractionDecision(
                action="discard",
                target_memory_id=None,
                memory_type=None,
                content=None,
                topic=None,
                importance=None,
                confidence=None,
                reason="La fuente está bloqueada y no puede recrear una memoria.",
            )

        raw_proposal = self.generator.generate(
            message,
            existing_memories=memories,
            prompt_version=MEMORY_EXTRACTION_PROMPT_VERSION,
        )
        decision = parse_memory_extraction(raw_proposal)
        return self._resolve_against_existing(decision, memories)

    def _validate_interaction(self, interaction: str) -> str:
        if not isinstance(interaction, str) or not interaction.strip():
            raise ValueError("La interacción no puede estar vacía.")
        message = interaction.strip()
        if len(message) > self.max_interaction_chars:
            raise ValueError("La interacción supera la longitud máxima.")
        return message

    def _validate_existing_memories(
        self, existing_memories: Sequence[ExistingMemory]
    ) -> tuple[ExistingMemory, ...]:
        if isinstance(existing_memories, (str, bytes)) or not isinstance(
            existing_memories, Sequence
        ):
            raise ValueError("existing_memories debe ser una secuencia.")
        if len(existing_memories) > self.max_existing_memories:
            raise ValueError("Hay demasiadas memorias existentes.")

        result: list[ExistingMemory] = []
        seen_ids: set[str] = set()
        for memory in existing_memories:
            if not isinstance(memory, ExistingMemory):
                raise ValueError("La lista contiene una memoria no válida.")
            memory_id = _required_text(memory.memory_id, "memory_id", 200)
            memory_type = _memory_type(memory.memory_type)
            content = _required_text(memory.content, "content", 600)
            if memory_id in seen_ids:
                raise ValueError("Las memorias existentes contienen IDs duplicados.")
            seen_ids.add(memory_id)
            result.append(ExistingMemory(memory_id, memory_type, content))
        return tuple(result)

    @staticmethod
    def _resolve_against_existing(
        decision: MemoryExtractionDecision,
        existing_memories: tuple[ExistingMemory, ...],
    ) -> MemoryExtractionDecision:
        by_id = {memory.memory_id: memory for memory in existing_memories}
        if decision.action == "update":
            target = by_id.get(decision.target_memory_id)
            if target is None:
                raise MemoryExtractionError(
                    "La actualización apunta a una memoria no autorizada o inexistente."
                )
            if target.memory_type != decision.memory_type:
                raise MemoryExtractionError(
                    "Una actualización no puede cambiar el tipo de memoria."
                )
            return decision

        if decision.action == "create":
            normalized = _normalize_content(decision.content)
            for memory in existing_memories:
                if (
                    memory.memory_type == decision.memory_type
                    and _normalize_content(memory.content) == normalized
                ):
                    return replace(
                        decision,
                        action="update",
                        target_memory_id=memory.memory_id,
                        reason=(
                            "La propuesta coincide con una memoria activa y se actualiza "
                            "en lugar de duplicarse."
                        ),
                    )
        return decision


def parse_memory_extraction(
    raw_proposal: str | Mapping[str, object],
) -> MemoryExtractionDecision:
    """Convierte JSON no confiable en una decisión estrictamente validada."""
    if isinstance(raw_proposal, str):
        if len(raw_proposal) > MAX_PROPOSAL_JSON_CHARS:
            raise MemoryExtractionError("La respuesta JSON supera la longitud máxima.")
        try:
            payload = json.loads(raw_proposal, object_pairs_hook=_unique_json_object)
        except json.JSONDecodeError as error:
            raise MemoryExtractionError("El modelo no devolvió JSON válido.") from error
    elif isinstance(raw_proposal, Mapping):
        payload = dict(raw_proposal)
    else:
        raise MemoryExtractionError("La propuesta debe ser JSON u objeto.")

    if not isinstance(payload, dict):
        raise MemoryExtractionError("La propuesta debe ser un objeto JSON.")
    if set(payload) != EXPECTED_FIELDS:
        raise MemoryExtractionError("La propuesta no contiene las claves exactas.")

    action = payload["action"]
    if not isinstance(action, str) or action not in MEMORY_ACTIONS:
        raise MemoryExtractionError("La acción de memoria no es válida.")
    reason = _required_text(payload["reason"], "reason", 300)

    if action == "discard":
        nullable_fields = EXPECTED_FIELDS - {"action", "reason"}
        if any(payload[field] is not None for field in nullable_fields):
            raise MemoryExtractionError(
                "Una propuesta discard debe dejar los campos educativos en null."
            )
        return MemoryExtractionDecision(
            action=action,
            target_memory_id=None,
            memory_type=None,
            content=None,
            topic=None,
            importance=None,
            confidence=None,
            reason=reason,
        )

    memory_type = _memory_type(payload["memory_type"])
    content = _required_text(payload["content"], "content", 600)
    topic = _required_text(payload["topic"], "topic", 120)
    importance = payload["importance"]
    if type(importance) is not int or importance not in {1, 2, 3}:
        raise MemoryExtractionError("importance debe ser 1, 2 o 3.")
    confidence = payload["confidence"]
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not isfinite(confidence)
        or not 0 <= confidence <= 1
    ):
        raise MemoryExtractionError("confidence debe estar entre 0 y 1.")
    if confidence < MIN_MEMORY_CONFIDENCE:
        raise MemoryExtractionError("La propuesta no alcanza la confianza mínima.")

    target_memory_id = payload["target_memory_id"]
    if action == "create":
        if target_memory_id is not None:
            raise MemoryExtractionError("create no puede indicar target_memory_id.")
    else:
        target_memory_id = _required_text(target_memory_id, "target_memory_id", 200)

    return MemoryExtractionDecision(
        action=action,
        target_memory_id=target_memory_id,
        memory_type=memory_type,
        content=content,
        topic=topic,
        importance=importance,
        confidence=float(confidence),
        reason=reason,
    )


def _memory_type(value: object) -> str:
    if not isinstance(value, str) or value not in MEMORY_TYPES:
        raise MemoryExtractionError("El tipo de memoria no es válido.")
    return value


def _required_text(value: object, field: str, max_chars: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MemoryExtractionError(f"{field} debe ser un texto no vacío.")
    result = value.strip()
    if len(result) > max_chars:
        raise MemoryExtractionError(f"{field} supera la longitud máxima.")
    return result


def _normalize_content(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.casefold().split())


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MemoryExtractionError("La propuesta contiene claves JSON duplicadas.")
        result[key] = value
    return result
