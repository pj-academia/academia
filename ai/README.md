# Materiales de IA

Este directorio contiene los prompts, contratos y módulos independientes de IA. El proveedor de embeddings permite conectar OpenAI desde el servidor; sus pruebas usan un cliente simulado y no necesitan claves ni llamadas de pago.

## Estructura

- `prompts/`: prompts versionados para tutoría y extracción de memoria.
- `embeddings/`: adaptador comprobable para generar vectores con OpenAI.
- `memory/`: reglas de creación, actualización, recuperación y eliminación de memorias.
- `tutor/`: preparación de turnos que mantiene separadas las reglas, el contexto no confiable y la consulta del alumno.

El directorio `memory/` incluye también el núcleo ejecutable de recuperación y sus pruebas. Está separado de FastAPI y ChromaDB para poder verificar las reglas de aislamiento y relevancia antes de integrar servicios externos.

Los prompts son una parte del producto y deben revisarse mediante pull request. Cualquier cambio que afecte la evaluación debe registrar su versión en los resultados.

## Test de nivel inicial

`placement/service.py` contiene la lógica de servidor para publicar las preguntas sin sus soluciones y calcular la estimación de nivel. Todavía no es un endpoint ni guarda datos: Peio lo conectará a FastAPI cuando el backend esté creado.

Para verificarlo sin instalar dependencias:

```powershell
python -m unittest ai.placement.test_service
```
