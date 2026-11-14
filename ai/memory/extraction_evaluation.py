"""Evaluación reproducible de la extracción de memoria educativa."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ai.memory.extraction import (
    MEMORY_ACTIONS,
    MEMORY_TYPES,
    ExistingMemory,
    MemoryExtractionDecision,
    MemoryExtractionService,
)


class MemoryExtractionEvaluationError(ValueError):
    """El conjunto de evaluación no cumple su contrato."""


@dataclass(frozen=True)
class ExpectedMemory:
    action: str
    memory_type: str | None
    target_memory_id: str | None
    content_terms: tuple[str, ...]


@dataclass(frozen=True)
class MemoryExtractionCase:
    case_id: str
    interaction: str
    existing_memories: tuple[ExistingMemory, ...]
    source_blocked: bool
    expected: ExpectedMemory


MemoryContentReviewer = Callable[
    [MemoryExtractionCase, MemoryExtractionDecision], bool | None
]


@dataclass(frozen=True)
class MemoryExtractionEvaluationReport:
    """Métricas automáticas de estructura, sin afirmar fidelidad semántica.

    ``field_term_matches`` solo cuenta coincidencias de acción, tipo, destino
    y palabras clave. Todo contenido creado o actualizado requiere una
    revisión de significado, incluso cuando esos campos coinciden.
    """

    version: str
    total_cases: int
    action_matches: int
    field_term_matches: int
    pending_content_review: tuple[str, ...]
    accepted_content_reviews: tuple[str, ...]
    rejected_content_reviews: tuple[str, ...]
    failures: tuple[str, ...]

    @property
    def action_accuracy(self) -> float:
        return self.action_matches / self.total_cases

    @property
    def field_term_accuracy(self) -> float:
        return self.field_term_matches / self.total_cases


def load_memory_extraction_cases(
    path: Path,
) -> tuple[str, tuple[MemoryExtractionCase, ...]]:
    """Carga casos etiquetados y rechaza contratos ambiguos o incompletos."""
    try:
        with path.open(encoding="utf-8") as source:
            payload = json.load(source)
    except (OSError, json.JSONDecodeError) as error:
        raise MemoryExtractionEvaluationError(
            "No se pudo leer el conjunto de evaluación."
        ) from error

    if not isinstance(payload, dict) or set(payload) != {"version", "cases"}:
        raise MemoryExtractionEvaluationError("El conjunto tiene una estructura inválida.")
    version = _required_text(payload["version"], "version")
    raw_cases = payload["cases"]
    if not isinstance(raw_cases, list) or not raw_cases:
        raise MemoryExtractionEvaluationError("Debe existir al menos un caso.")

    cases = tuple(_parse_case(raw_case) for raw_case in raw_cases)
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise MemoryExtractionEvaluationError("Los IDs de caso deben ser únicos.")
    return version, cases


def evaluate_memory_extraction(
    service: MemoryExtractionService,
    cases: tuple[MemoryExtractionCase, ...],
    *,
    version: str,
    content_reviewer: MemoryContentReviewer | None = None,
) -> MemoryExtractionEvaluationReport:
    """Comprueba campos y términos y, opcionalmente, solicita revisión de contenido.

    El revisor recibe el caso y la decisión de esta ejecución. Devuelve True
    si el recuerdo es fiel, False si lo contradice o None si queda pendiente.
    Sin revisor nunca se afirma que el contenido generado sea correcto.
    """
    if not cases:
        raise MemoryExtractionEvaluationError("No hay casos que evaluar.")
    version = _required_text(version, "version")
    action_matches = 0
    field_term_matches = 0
    pending_content_review: list[str] = []
    accepted_content_reviews: list[str] = []
    rejected_content_reviews: list[str] = []
    failures: list[str] = []

    for case in cases:
        try:
            decision = service.propose(
                case.interaction,
                existing_memories=case.existing_memories,
                source_blocked=case.source_blocked,
            )
        except Exception as error:  # El informe debe conservar el resto de casos.
            failures.append(f"{case.case_id}: {type(error).__name__}")
            continue

        action_match = decision.action == case.expected.action
        if action_match:
            action_matches += 1
        content = (decision.content or "").casefold()
        field_term_match = (
            action_match
            and decision.memory_type == case.expected.memory_type
            and decision.target_memory_id == case.expected.target_memory_id
            and all(term.casefold() in content for term in case.expected.content_terms)
        )
        if field_term_match:
            field_term_matches += 1
        else:
            failures.append(f"{case.case_id}: resultado distinto del esperado")

        if decision.action in {"create", "update"}:
            try:
                review = content_reviewer(case, decision) if content_reviewer else None
                if review is not None and type(review) is not bool:
                    raise ValueError("El revisor debe devolver True, False o None.")
            except Exception as error:
                pending_content_review.append(case.case_id)
                failures.append(f"{case.case_id}: revisión {type(error).__name__}")
                continue
            if review is None:
                pending_content_review.append(case.case_id)
            elif review:
                accepted_content_reviews.append(case.case_id)
            else:
                rejected_content_reviews.append(case.case_id)
                failures.append(f"{case.case_id}: contenido no fiel a la interacción")

    return MemoryExtractionEvaluationReport(
        version=version,
        total_cases=len(cases),
        action_matches=action_matches,
        field_term_matches=field_term_matches,
        pending_content_review=tuple(pending_content_review),
        accepted_content_reviews=tuple(accepted_content_reviews),
        rejected_content_reviews=tuple(rejected_content_reviews),
        failures=tuple(failures),
    )


def _parse_case(raw_case: object) -> MemoryExtractionCase:
    expected_fields = {
        "id",
        "interaction",
        "existing_memories",
        "source_blocked",
        "expected",
    }
    if not isinstance(raw_case, dict) or set(raw_case) != expected_fields:
        raise MemoryExtractionEvaluationError("Un caso tiene campos inválidos.")

    case_id = _required_text(raw_case["id"], "id")
    interaction = _required_text(raw_case["interaction"], "interaction")
    if type(raw_case["source_blocked"]) is not bool:
        raise MemoryExtractionEvaluationError("source_blocked debe ser booleano.")

    raw_memories = raw_case["existing_memories"]
    if not isinstance(raw_memories, list):
        raise MemoryExtractionEvaluationError("existing_memories debe ser una lista.")
    memories = tuple(_parse_existing_memory(item) for item in raw_memories)
    memory_ids = [memory.memory_id for memory in memories]
    if len(memory_ids) != len(set(memory_ids)):
        raise MemoryExtractionEvaluationError("Un caso contiene memorias duplicadas.")

    expected = _parse_expected(
        raw_case["expected"], {memory.memory_id: memory for memory in memories}
    )
    if raw_case["source_blocked"] and expected.action != "discard":
        raise MemoryExtractionEvaluationError(
            "Una fuente bloqueada solo puede esperar discard."
        )
    return MemoryExtractionCase(
        case_id=case_id,
        interaction=interaction,
        existing_memories=memories,
        source_blocked=raw_case["source_blocked"],
        expected=expected,
    )


def _parse_existing_memory(raw_memory: object) -> ExistingMemory:
    fields = {"memory_id", "memory_type", "content"}
    if not isinstance(raw_memory, dict) or set(raw_memory) != fields:
        raise MemoryExtractionEvaluationError("Una memoria existente es inválida.")
    memory_type = raw_memory["memory_type"]
    if not isinstance(memory_type, str) or memory_type not in MEMORY_TYPES:
        raise MemoryExtractionEvaluationError("Una memoria tiene un tipo inválido.")
    return ExistingMemory(
        memory_id=_required_text(raw_memory["memory_id"], "memory_id"),
        memory_type=memory_type,
        content=_required_text(raw_memory["content"], "content"),
    )


def _parse_expected(
    raw_expected: object, existing_memories: dict[str, ExistingMemory]
) -> ExpectedMemory:
    fields = {"action", "memory_type", "target_memory_id", "content_terms"}
    if not isinstance(raw_expected, dict) or set(raw_expected) != fields:
        raise MemoryExtractionEvaluationError("El resultado esperado es inválido.")

    action = raw_expected["action"]
    if not isinstance(action, str) or action not in MEMORY_ACTIONS:
        raise MemoryExtractionEvaluationError("La acción esperada no es válida.")
    memory_type = raw_expected["memory_type"]
    target = raw_expected["target_memory_id"]
    terms = raw_expected["content_terms"]
    if not isinstance(terms, list) or any(
        not isinstance(term, str) or not term.strip() for term in terms
    ):
        raise MemoryExtractionEvaluationError("content_terms debe contener textos.")

    if action == "discard":
        if memory_type is not None or target is not None or terms:
            raise MemoryExtractionEvaluationError("discard debe esperar campos vacíos.")
    else:
        if (
            not isinstance(memory_type, str)
            or memory_type not in MEMORY_TYPES
            or not terms
        ):
            raise MemoryExtractionEvaluationError(
                "create y update necesitan tipo y términos esperados."
            )
        if action == "create" and target is not None:
            raise MemoryExtractionEvaluationError("create no puede esperar un destino.")
        if action == "update":
            target = _required_text(target, "target_memory_id")
            existing = existing_memories.get(target)
            if existing is None:
                raise MemoryExtractionEvaluationError(
                    "update debe apuntar a una memoria existente del caso."
                )
            if existing.memory_type != memory_type:
                raise MemoryExtractionEvaluationError(
                    "update debe conservar el tipo de la memoria destino."
                )

    return ExpectedMemory(
        action=action,
        memory_type=memory_type,
        target_memory_id=target,
        content_terms=tuple(term.strip() for term in terms),
    )


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MemoryExtractionEvaluationError(f"{field} debe ser un texto no vacío.")
    return value.strip()
