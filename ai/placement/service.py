"""Contrato de servidor para el test diagnóstico inicial.

Este módulo no depende todavía de FastAPI. Peio podrá importarlo desde un
endpoint cuando se construya el backend. Las soluciones se mantienen siempre
en el servidor: ``public_test`` nunca las devuelve.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class PlacementAnswerError(ValueError):
    """Una respuesta no corresponde con las preguntas publicadas."""


@dataclass(frozen=True)
class PlacementResult:
    """Resultado orientativo y no certificador de la prueba inicial."""

    score: int
    level: str
    total_items: int
    message_es: str


def load_test(path: Path) -> dict[str, Any]:
    """Carga y valida el contrato de contenido del test."""
    with path.open(encoding="utf-8") as source:
        test = json.load(source)

    items = test.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("El test debe contener al menos una pregunta.")

    ids = [item.get("id") for item in items]
    if len(ids) != len(set(ids)) or any(not isinstance(item_id, str) for item_id in ids):
        raise ValueError("Cada pregunta debe tener un identificador único.")

    for item in items:
        options = item.get("options")
        correct = item.get("correct_option")
        if not isinstance(options, list) or len(options) < 2:
            raise ValueError(f"La pregunta {item['id']} no tiene opciones válidas.")
        if not isinstance(correct, int) or not 0 <= correct < len(options):
            raise ValueError(f"La solución de {item['id']} no es válida.")

    return test


def public_test(test: Mapping[str, Any]) -> dict[str, Any]:
    """Prepara el contenido seguro para el frontend, sin claves de respuesta."""
    return {
        "version": test["version"],
        "purpose": test["purpose"],
        "items": [
            {
                "id": item["id"],
                "target_band": item["target_band"],
                "skill": item["skill"],
                "question": item["question"],
                "options": item["options"],
            }
            for item in test["items"]
        ],
    }


def evaluate_answers(
    test: Mapping[str, Any], answers: Mapping[str, int]
) -> PlacementResult:
    """Calcula la estimación inicial a partir de respuestas completas.

    La API deberá asociar estas respuestas al usuario autenticado. Este módulo
    no recibe ni persiste identificadores personales.
    """
    items_by_id = {item["id"]: item for item in test["items"]}

    unknown_ids = set(answers) - set(items_by_id)
    missing_ids = set(items_by_id) - set(answers)
    if unknown_ids or missing_ids:
        raise PlacementAnswerError(
            "Las respuestas deben corresponder exactamente con las preguntas publicadas."
        )

    for item_id, selected_option in answers.items():
        if not isinstance(selected_option, int) or isinstance(selected_option, bool):
            raise PlacementAnswerError(f"La respuesta de {item_id} debe ser un número entero.")
        if not 0 <= selected_option < len(items_by_id[item_id]["options"]):
            raise PlacementAnswerError(f"La opción seleccionada en {item_id} no existe.")

    score = sum(
        answers[item_id] == item["correct_option"]
        for item_id, item in items_by_id.items()
    )
    level = level_for_score(test["scoring"], score)

    return PlacementResult(
        score=score,
        level=level,
        total_items=len(items_by_id),
        message_es=(
            f"Tu nivel inicial estimado es {level}. No es una certificación; "
            "lo ajustaremos con tus ejercicios y conversaciones."
        ),
    )


def level_for_score(scoring: Mapping[str, str], score: int) -> str:
    """Convierte los rangos declarados en JSON al nivel correspondiente."""
    for score_range, level in scoring.items():
        if score_range == "note":
            continue
        start, end = (int(value) for value in score_range.split("-", maxsplit=1))
        if start <= score <= end:
            return level
    raise ValueError(f"No hay nivel configurado para la puntuación {score}.")
