"""Demo sin red: respuestas guionizadas -> adaptador -> validación -> estado efímero."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from types import SimpleNamespace
from typing import Any, Sequence

from ai.memory.extraction import (
    ExistingMemory,
    MemoryExtractionError,
    MemoryExtractionService,
)
from ai.memory.openai_extractor import OpenAIMemoryExtractionGenerator


DIFFICULTY_MESSAGE = "I always confuse the present perfect with the past simple."
REPEATED_DIFFICULTY_MESSAGE = "I still confuse present perfect and past simple."
SPANISH_PREFERENCE_MESSAGE = "Explícame la gramática paso a paso y en español."
ENGLISH_PREFERENCE_MESSAGE = "A partir de ahora, explícame todo solo en inglés."
GREETING_MESSAGE = "Hello! How are you?"
INVALID_PROPOSAL_MESSAGE = "Example with an intentionally invalid proposal."
SCENARIO_TITLES = {
    "create-difficulty": "Crear una dificultad",
    "deduplicate-difficulty": "Repetir la dificultad sin duplicarla",
    "create-preference": "Crear una preferencia",
    "update-preference": "Cambiar la preferencia conservando su ID",
    "discard-greeting": "Descartar un saludo",
    "reject-invalid": "Rechazar una propuesta inválida",
    "blocked-source": "Borrar la dificultad y bloquear su fuente (simulado)",
}


@dataclass(frozen=True)
class DemoStep:
    scenario: str
    action: str
    memory_id: str | None
    content: str | None
    active_memory_ids: tuple[str, ...]
    active_memories: tuple[ExistingMemory, ...]
    provider_calls: int
    detail: str


@dataclass(frozen=True)
class DemoReport:
    steps: tuple[DemoStep, ...]
    remaining_memories: tuple[ExistingMemory, ...]
    total_provider_calls: int


def _proposal(
    content: str,
    *,
    memory_type: str = "progress",
    action: str = "create",
    target_memory_id: str | None = None,
    confidence: float = 0.91,
) -> dict[str, object]:
    return {
        "action": action,
        "target_memory_id": target_memory_id,
        "memory_type": memory_type,
        "content": content,
        "topic": "English learning",
        "importance": 2,
        "confidence": confidence,
        "reason": "Ejemplo educativo sintético para esta demostración.",
    }


class _ScriptedResponsesEndpoint:
    """Solo reconoce las frases de la demo; no tiene capacidad de llamar a una API."""

    def __init__(self) -> None:
        self.call_count = 0
        self.proposals = {
            DIFFICULTY_MESSAGE: _proposal("Confunde present perfect y past simple."),
            REPEATED_DIFFICULTY_MESSAGE: _proposal(
                "Confunde   PRESENT perfect y past simple."
            ),
            SPANISH_PREFERENCE_MESSAGE: _proposal(
                "Prefiere explicaciones paso a paso y en español.",
                memory_type="preference",
            ),
            ENGLISH_PREFERENCE_MESSAGE: _proposal(
                "Prefiere explicaciones solo en inglés.",
                memory_type="preference",
                action="update",
                target_memory_id="demo-memory-2",
            ),
            GREETING_MESSAGE: {
                "action": "discard",
                "target_memory_id": None,
                "memory_type": None,
                "content": None,
                "topic": None,
                "importance": None,
                "confidence": None,
                "reason": "Es un saludo sin valor educativo duradero.",
            },
            INVALID_PROPOSAL_MESSAGE: _proposal(
                "Este contenido no debe guardarse.", confidence=0.4
            ),
        }

    def create(self, **request: Any) -> SimpleNamespace:
        self.call_count += 1
        dynamic_input = json.loads(request["input"][0]["content"])
        interaction = dynamic_input["interaction"]
        if interaction not in self.proposals:
            raise ValueError("La demo solo admite sus frases guionizadas.")
        return SimpleNamespace(
            status="completed",
            output_text=json.dumps(self.proposals[interaction], ensure_ascii=False),
        )


def run_demo() -> DemoReport:
    """Demuestra reglas reales con propuestas y almacenamiento simulados.

    El diccionario representa únicamente el estado de esta ejecución. El
    backend real deberá autorizar datos, persistir fuentes y ejecutar el
    borrado y el bloqueo. Esta función nunca lee credenciales ni usa el SDK.
    """
    endpoint = _ScriptedResponsesEndpoint()
    client = SimpleNamespace(responses=endpoint)
    service = MemoryExtractionService(
        OpenAIMemoryExtractionGenerator(client=client, model="demo-model-no-network")
    )
    memories: dict[str, ExistingMemory] = {}
    steps: list[DemoStep] = []
    next_memory_number = 1

    def turn(scenario: str, interaction: str, *, source_blocked: bool = False) -> None:
        nonlocal next_memory_number
        calls_before = endpoint.call_count
        memory_id = None
        content = None
        try:
            decision = service.propose(
                interaction,
                existing_memories=tuple(memories.values()),
                source_blocked=source_blocked,
            )
            action = decision.action
            content = decision.content
            detail = decision.reason
            if action in {"create", "update"}:
                if action == "create":
                    memory_id = f"demo-memory-{next_memory_number}"
                    next_memory_number += 1
                else:
                    memory_id = decision.target_memory_id
                if memory_id is None or decision.memory_type is None or content is None:
                    raise RuntimeError("El validador devolvió una decisión incompleta.")
                memories[memory_id] = ExistingMemory(
                    memory_id=memory_id,
                    memory_type=decision.memory_type,
                    content=content,
                )
        except MemoryExtractionError as error:
            action = "rejected"
            detail = str(error)

        steps.append(
            DemoStep(
                scenario=scenario,
                action=action,
                memory_id=memory_id,
                content=content,
                active_memory_ids=tuple(memories),
                active_memories=tuple(memories.values()),
                provider_calls=endpoint.call_count - calls_before,
                detail=detail,
            )
        )

    turn("create-difficulty", DIFFICULTY_MESSAGE)
    turn("deduplicate-difficulty", REPEATED_DIFFICULTY_MESSAGE)
    turn("create-preference", SPANISH_PREFERENCE_MESSAGE)
    turn("update-preference", ENGLISH_PREFERENCE_MESSAGE)
    turn("discard-greeting", GREETING_MESSAGE)
    turn("reject-invalid", INVALID_PROPOSAL_MESSAGE)

    # Borrado local y señal de bloqueo que deberá proporcionar el backend.
    del memories["demo-memory-1"]
    turn("blocked-source", DIFFICULTY_MESSAGE, source_blocked=True)

    return DemoReport(
        steps=tuple(steps),
        remaining_memories=tuple(memories.values()),
        total_provider_calls=endpoint.call_count,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Imprime el informe como JSON.")
    args = parser.parse_args(argv)
    report = run_demo()
    if args.json:
        print(
            json.dumps({"mode": "scripted-demo", "report": asdict(report)}, ensure_ascii=False)
        )
        return 0

    print("Demo de extracción con respuestas guionizadas, sin API ni créditos.")
    print("La validación es real; el estado y el bloqueo son simulados y efímeros.\n")
    for number, step in enumerate(report.steps, start=1):
        print(f"{number}. {SCENARIO_TITLES[step.scenario]}: {step.action}")
        print(
            f"   Memorias activas: {len(step.active_memory_ids)}; "
            f"llamadas simuladas: {step.provider_calls}"
        )
        if step.memory_id is not None:
            print(f"   ID: {step.memory_id}; contenido: {step.content}")
        print(f"   {step.detail}")
    print(f"\nTotal de llamadas simuladas: {report.total_provider_calls}.")
    print("Los datos desaparecen al terminar. Esta demo no mide calidad semántica.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
