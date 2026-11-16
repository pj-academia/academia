# Preparación de turnos del tutor

`TutorTurnService` une el servicio de memoria con la preparación de la llamada a OpenAI. Recibe el alumno autenticado, el mensaje, el nivel estimado y sus preferencias; recupera solo su contexto y devuelve argumentos compatibles con `client.responses.create(**request)`. `OpenAITutorResponder` ejecuta esos argumentos y devuelve un `TutorReply` con texto, identificador y métricas de tokens.

La petición mantiene tres zonas separadas:

1. `instructions`: reglas versionadas del tutor con autoridad de desarrollador.
2. Primer elemento de `input`: nivel, preferencias y memoria en JSON etiquetado como datos no confiables.
3. Segundo elemento de `input`: mensaje actual del alumno.

El identificador del alumno, los vectores y la similitud no se envían al modelo. La opción `store` se fija a `False`; la aplicación conservará el historial que necesite en sus propios sistemas. Las pruebas usan un cliente simulado, por lo que no necesitan API key ni consumen créditos.

```python
from ai.tutor import OpenAITutorResponder, TutorTurnService

tutor = TutorTurnService(memory_context_service, model=configured_chat_model)
request = tutor.prepare(
    "Can we practise the present perfect?",
    user_id=authenticated_user_id,
    estimated_level="B1",
    preferences=("Ejemplos breves",),
)
responder = OpenAITutorResponder(openai_client)
reply = responder.generate(request)
print(reply.text)
```

La estructura sigue la [referencia oficial de Responses para Python](https://developers.openai.com/api/reference/python/resources/responses/methods/create): `instructions` se interpreta como guía de desarrollador, `input` admite mensajes con rol y el SDK proporciona `output_text`. El adaptador exige estado `completed` e identificador de respuesta; acepta texto no vacío o una negativa de seguridad válida, que marca con `reply.refused`. Si existen métricas, valida que sean contadores no negativos. Los errores del SDK se propagan y el backend decidirá cómo registrarlos o traducirlos sin guardar el prompt.

Antes de una ejecución real faltan seleccionar el modelo de chat, añadir la dependencia oficial al entorno del backend y configurar `OPENAI_API_KEY` únicamente en el servidor. Ese recorrido real se probará de forma controlada cuando el equipo confirme la cuenta y el presupuesto.
