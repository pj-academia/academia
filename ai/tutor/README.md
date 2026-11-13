# Preparación de turnos del tutor

`TutorTurnService` une el servicio de memoria con la futura llamada a OpenAI sin realizar todavía esa llamada. Recibe el alumno autenticado, el mensaje, el nivel estimado y sus preferencias; recupera solo su contexto y devuelve argumentos compatibles con `client.responses.create(**request)`.

La petición mantiene tres zonas separadas:

1. `instructions`: reglas versionadas del tutor con autoridad de desarrollador.
2. Primer elemento de `input`: nivel, preferencias y memoria en JSON etiquetado como datos no confiables.
3. Segundo elemento de `input`: mensaje actual del alumno.

El identificador del alumno, los vectores y la similitud no se envían al modelo. La opción `store` se fija a `False`; la aplicación conservará el historial que necesite en sus propios sistemas. La respuesta todavía no se genera y no se necesita API key para probar este módulo.

```python
from ai.tutor import TutorTurnService

tutor = TutorTurnService(memory_context_service, model=configured_chat_model)
request = tutor.prepare(
    "Can we practise the present perfect?",
    user_id=authenticated_user_id,
    estimated_level="B1",
    preferences=("Ejemplos breves",),
)
# Futuro paso del backend, no ejecutado por este módulo:
# response = openai_client.responses.create(**request)
```

La estructura sigue la [referencia oficial de Responses](https://developers.openai.com/api/reference/resources/responses/methods/create): `instructions` se interpreta como guía de desarrollador y `input` admite mensajes con rol. Antes de la integración real faltan seleccionar el modelo de chat, conectar el cliente en el backend y probar el recorrido con una clave configurada únicamente en el servidor.
