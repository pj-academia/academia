"""Registro redacted y reproducible de una ejecución del tutor."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from ai.tutor import TutorReply


EVALUATION_CONDITIONS = frozenset({"with_memory", "without_memory"})
EVALUATION_SCHEMA_VERSION = "tutor-turn-eval-v1"


@dataclass(frozen=True)
class TutorEvaluationRecord:
    run_id: str
    case_id: str
    condition: str
    model: str
    prompt_version: str
    response_id: str
    memory_ids: tuple[str, ...]
    refused: bool
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    latency_ms: float
    output_sha256: str
    output_text: str | None = None
    schema_version: str = EVALUATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        """Devuelve un objeto JSON sin datos privados del turno."""
        data: dict[str, object] = {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "condition": self.condition,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "response_id": self.response_id,
            "memory_ids": list(self.memory_ids),
            "refused": self.refused,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "output_sha256": self.output_sha256,
            "output_text_included": self.output_text is not None,
        }
        if self.output_text is not None:
            data["output_text"] = self.output_text
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)


def build_tutor_evaluation_record(
    *,
    run_id: str,
    case_id: str,
    condition: str,
    request: Mapping[str, object],
    reply: TutorReply,
    latency_ms: float,
    include_output_text: bool = False,
) -> TutorEvaluationRecord:
    """Resume un turno sin conservar alumno, consulta ni contenido de memoria."""
    safe_run_id = _identifier(run_id, "run_id")
    safe_case_id = _identifier(case_id, "case_id")
    if condition not in EVALUATION_CONDITIONS:
        raise ValueError("La condición de evaluación no es válida.")
    if not isinstance(request, Mapping):
        raise ValueError("La petición evaluada debe ser un mapeo.")
    if not isinstance(reply, TutorReply):
        raise ValueError("La respuesta evaluada no es un TutorReply.")
    if not isinstance(reply.text, str) or not reply.text.strip():
        raise ValueError("La respuesta evaluada no contiene texto válido.")
    if type(reply.refused) is not bool:
        raise ValueError("El indicador de negativa debe ser booleano.")
    if type(include_output_text) is not bool:
        raise ValueError("include_output_text debe ser booleano.")
    if (
        isinstance(latency_ms, bool)
        or not isinstance(latency_ms, (int, float))
        or not isfinite(latency_ms)
        or latency_ms < 0
    ):
        raise ValueError("latency_ms debe ser un número finito no negativo.")

    model = _request_text(request, "model")
    metadata = request.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("La petición no contiene metadatos válidos.")
    prompt_version = _request_text(metadata, "prompt_version")
    memory_ids = _memory_ids(request)
    if condition == "without_memory" and memory_ids:
        raise ValueError("La condición sin memoria no puede contener memorias.")

    for count in (reply.input_tokens, reply.output_tokens, reply.total_tokens):
        if count is not None and (type(count) is not int or count < 0):
            raise ValueError("La respuesta contiene métricas de tokens no válidas.")

    return TutorEvaluationRecord(
        run_id=safe_run_id,
        case_id=safe_case_id,
        condition=condition,
        model=model,
        prompt_version=prompt_version,
        response_id=_identifier(reply.response_id, "response_id"),
        memory_ids=memory_ids,
        refused=reply.refused,
        input_tokens=reply.input_tokens,
        output_tokens=reply.output_tokens,
        total_tokens=reply.total_tokens,
        latency_ms=float(latency_ms),
        output_sha256=hashlib.sha256(reply.text.encode("utf-8")).hexdigest(),
        output_text=reply.text if include_output_text else None,
    )


def _memory_ids(request: Mapping[str, object]) -> tuple[str, ...]:
    input_items = request.get("input")
    if not isinstance(input_items, list) or not input_items:
        raise ValueError("La petición no contiene el contexto del tutor.")
    context_item = input_items[0]
    if not isinstance(context_item, Mapping):
        raise ValueError("El contexto del tutor no es válido.")
    content = context_item.get("content")
    if not isinstance(content, str):
        raise ValueError("El contexto del tutor no contiene JSON.")
    try:
        context = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError("El contexto del tutor no contiene JSON válido.") from error
    if not isinstance(context, Mapping) or context.get("kind") != "untrusted_tutor_context":
        raise ValueError("El contexto del tutor no tiene el contrato esperado.")

    educational_memory = context.get("educational_memory")
    if (
        not isinstance(educational_memory, Mapping)
        or educational_memory.get("kind") != "untrusted_educational_memories"
    ):
        raise ValueError("El bloque de memoria no tiene el contrato esperado.")
    memories = educational_memory.get("memories")
    if not isinstance(memories, list):
        raise ValueError("El bloque de memoria no contiene una lista válida.")

    result: list[str] = []
    for memory in memories:
        if not isinstance(memory, Mapping):
            raise ValueError("La petición contiene una memoria no válida.")
        memory_id = _request_text(memory, "memory_id")
        if memory_id in result:
            raise ValueError("La petición contiene identificadores de memoria duplicados.")
        result.append(memory_id)
    return tuple(result)


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} es obligatorio.")
    result = value.strip()
    if len(result) > 200 or "\n" in result or "\r" in result:
        raise ValueError(f"{field} no es válido.")
    return result


def _request_text(source: Mapping[str, object], field: str) -> str:
    value = source.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"La petición no contiene {field} válido.")
    return value.strip()
