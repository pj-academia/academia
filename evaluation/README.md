# Evaluación de IA, memoria y personalización

## Pregunta principal

¿La recuperación de memoria educativa produce una respuesta más adaptada que un tutor sin memoria, sin provocar filtraciones ni inventar antecedentes?

## Línea base

La misma consulta se ejecuta en dos condiciones:

1. **Sin memoria:** perfil mínimo y consulta actual.
2. **Con memoria:** mismo perfil, consulta y memorias relevantes recuperadas.

Se conserva versión del prompt, modelo, latencia y uso de tokens para cada ejecución. La evaluación real deberá registrar también la configuración de recuperación (`top_k`, umbral, modelo y dimensión de embeddings) para que la comparación sea completamente reproducible.

## Métricas propuestas

| Métrica | Método | Objetivo inicial |
| --- | --- | --- |
| Recuperación relevante | Memoria esperada entre los tres primeros resultados | 80 % o más en el conjunto etiquetado |
| Personalización correcta | Revisión humana con rúbrica | Mejor resultado con memoria que sin memoria |
| Aislamiento | Pruebas de acceso cruzado | 100 % bloqueadas |
| Borrado | Memoria eliminada no reaparece en recuperación | 100 % de los casos |
| Operación | Latencia, errores, tokens y coste por solicitud | Medición; sin resultados inventados |

Los objetivos son criterios de preparación, no resultados obtenidos.

## Registro reproducible de cada ejecución

`ai/evaluation/tutor_record.py` genera el contrato `tutor-turn-eval-v1`. Registra condición, caso, modelo, versión del prompt, IDs de las memorias recuperadas, latencia, tokens, negativa de seguridad, identificador de respuesta y una huella SHA-256 del resultado.

Por defecto no guarda `user_id`, consulta, contenido de memorias ni texto de respuesta. El texto solo puede incluirse de forma explícita para el conjunto sintético revisado por el equipo. La condición `without_memory` rechaza cualquier ejecución que contenga memorias, evitando mezclar accidentalmente la línea base con el tratamiento.

## Casos de prueba

El conjunto `datasets/memory-evaluation-v1.json` contiene casos positivos, negativos, de actualización y de eliminación. Actualmente es un conjunto manual: todavía falta el ejecutor que lance cada caso en ambas condiciones y aplique la rúbrica humana. Antes de esa evaluación real, se ampliará y revisará por los tres integrantes.
