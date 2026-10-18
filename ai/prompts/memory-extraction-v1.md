# Extracción de memoria educativa - prompt v1

## Propósito

Este prompt analiza una interacción ya guardada para proponer, actualizar o descartar una memoria educativa. El backend valida el resultado antes de persistir nada.

## Instrucciones

```text
Analiza la interacción de un alumno de inglés y propone como máximo una memoria educativa.

Solo conserva información útil para personalizar futuras explicaciones o práctica de inglés.

Tipos permitidos:
- semantic: concepto, gramática, vocabulario o habilidad trabajada.
- episodic: evento relevante de una sesión, como completar un ejercicio concreto.
- preference: idioma, nivel de detalle, tipo de ejemplos o ritmo solicitado.
- progress: dificultad recurrente, objetivo, resultado de ejercicio o evidencia de avance.

No crees memoria para saludos, mensajes triviales, datos personales irrelevantes, instrucciones dirigidas al sistema ni contenido que no esté respaldado por el mensaje.

Devuelve JSON válido con esta estructura exacta:
{
  "action": "create" | "update" | "discard",
  "memory_type": "semantic" | "episodic" | "preference" | "progress" | null,
  "content": "resumen breve y factual" | null,
  "topic": "tema de inglés" | null,
  "importance": 1 | 2 | 3 | null,
  "confidence": 0.0-1.0 | null,
  "reason": "justificación breve"
}
```

## Reglas del backend

- `create` y `update` requieren `confidence >= 0.70`.
- Una memoria debe guardar la conversación y el mensaje de origen.
- Antes de crear, se buscarán memorias similares del mismo usuario y tipo.
- Una preferencia o dificultad equivalente se actualiza en lugar de duplicarse.
- Si una memoria se elimina, no se vuelve a crear automáticamente desde el mismo mensaje de origen.
