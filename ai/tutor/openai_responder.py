"""Adaptador mínimo para ejecutar turnos con la Responses API de OpenAI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol


class ResponsesEndpoint(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class OpenAIClient(Protocol):
    responses: ResponsesEndpoint


class TutorResponseError(RuntimeError):
    """La API respondió, pero el resultado no cumple el contrato del tutor."""


@dataclass(frozen=True)
class TutorReply:
    response_id: str
    text: str
    refused: bool = False
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class OpenAITutorResponder:
    """Ejecuta una petición ya preparada y devuelve solo datos seguros."""

    client: OpenAIClient

    @classmethod
    def from_environment(cls) -> OpenAITutorResponder:
        """Crea el cliente oficial, que lee ``OPENAI_API_KEY`` del entorno."""
        try:
            from openai import OpenAI
        except ImportError as error:
            raise RuntimeError(
                "El paquete oficial 'openai' no está instalado en este entorno."
            ) from error
        return cls(client=OpenAI())

    def generate(self, request: Mapping[str, object]) -> TutorReply:
        """Llama a Responses y valida el texto y las métricas devueltas.

        Los errores del SDK se propagan para que la capa HTTP decida si debe
        reintentar, registrar o traducir el fallo. No se registra el prompt.
        """
        payload = self._validate_request(request)
        response = self.client.responses.create(**payload)

        status = getattr(response, "status", None)
        if status != "completed":
            raise TutorResponseError(
                f"La respuesta del tutor no terminó correctamente: {status!r}."
            )

        response_id = getattr(response, "id", None)
        if not isinstance(response_id, str) or not response_id.strip():
            raise TutorResponseError("OpenAI no devolvió un identificador de respuesta.")

        text, refused = self._extract_text(response)

        usage = getattr(response, "usage", None)
        input_tokens = self._optional_token_count(usage, "input_tokens")
        output_tokens = self._optional_token_count(usage, "output_tokens")
        total_tokens = self._optional_token_count(usage, "total_tokens")

        return TutorReply(
            response_id=response_id.strip(),
            text=text,
            refused=refused,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

    @staticmethod
    def _validate_request(request: Mapping[str, object]) -> dict[str, object]:
        if not isinstance(request, Mapping):
            raise ValueError("La petición del tutor debe ser un mapeo.")

        payload = dict(request)
        model = payload.get("model")
        instructions = payload.get("instructions")
        input_items = payload.get("input")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("La petición no contiene un modelo válido.")
        if not isinstance(instructions, str) or not instructions.strip():
            raise ValueError("La petición no contiene instrucciones válidas.")
        if not isinstance(input_items, list) or not input_items:
            raise ValueError("La petición no contiene mensajes de entrada.")
        if payload.get("store") is not False:
            raise ValueError("La petición del tutor debe desactivar store.")
        if "api_key" in payload:
            raise ValueError("La clave API no debe formar parte de la petición.")
        return payload

    @staticmethod
    def _extract_text(response: object) -> tuple[str, bool]:
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip(), False

        refusals: list[str] = []
        output = getattr(response, "output", None)
        if isinstance(output, list):
            for item in output:
                content = getattr(item, "content", None)
                if not isinstance(content, list):
                    continue
                for part in content:
                    if getattr(part, "type", None) != "refusal":
                        continue
                    refusal = getattr(part, "refusal", None)
                    if isinstance(refusal, str) and refusal.strip():
                        refusals.append(refusal.strip())
        if refusals:
            return "\n".join(refusals), True
        raise TutorResponseError("OpenAI no devolvió texto ni una negativa válida.")

    @staticmethod
    def _optional_token_count(usage: object, attribute: str) -> int | None:
        if usage is None:
            return None
        value = getattr(usage, attribute, None)
        if value is None:
            return None
        if type(value) is not int or value < 0:
            raise TutorResponseError("OpenAI devolvió métricas de uso no válidas.")
        return value
