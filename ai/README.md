# Materiales de IA

Estos archivos definen los contratos funcionales de la IA antes de conectar la aplicación con OpenAI. No contienen claves, llamadas a la API ni resultados generados.

## Estructura

- `prompts/`: prompts versionados para tutoría y extracción de memoria.
- `memory/`: reglas de creación, actualización, recuperación y eliminación de memorias.

Los prompts son una parte del producto y deben revisarse mediante pull request. Cualquier cambio que afecte la evaluación debe registrar su versión en los resultados.

## Test de nivel inicial

`placement/service.py` contiene la lógica de servidor para publicar las preguntas sin sus soluciones y calcular la estimación de nivel. Todavía no es un endpoint ni guarda datos: Peio lo conectará a FastAPI cuando el backend esté creado.

Para verificarlo sin instalar dependencias:

```powershell
python -m unittest ai.placement.test_service
```
