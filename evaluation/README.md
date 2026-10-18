# Evaluación de IA, memoria y personalización

## Pregunta principal

¿La recuperación de memoria educativa produce una respuesta más adaptada que un tutor sin memoria, sin provocar filtraciones ni inventar antecedentes?

## Línea base

La misma consulta se ejecuta en dos condiciones:

1. **Sin memoria:** perfil mínimo y consulta actual.
2. **Con memoria:** mismo perfil, consulta y memorias relevantes recuperadas.

Se conserva versión del prompt, modelo, configuración, latencia y uso de tokens para cada ejecución.

## Métricas propuestas

| Métrica | Método | Objetivo inicial |
| --- | --- | --- |
| Recuperación relevante | Memoria esperada entre los tres primeros resultados | 80 % o más en el conjunto etiquetado |
| Personalización correcta | Revisión humana con rúbrica | Mejor resultado con memoria que sin memoria |
| Aislamiento | Pruebas de acceso cruzado | 100 % bloqueadas |
| Borrado | Memoria eliminada no reaparece en recuperación | 100 % de los casos |
| Operación | Latencia, errores, tokens y coste por solicitud | Medición; sin resultados inventados |

Los objetivos son criterios de preparación, no resultados obtenidos.

## Casos de prueba

El conjunto `datasets/memory-evaluation-v1.json` contiene casos positivos, negativos, de actualización y de eliminación. Antes de una evaluación real, se ampliará y revisará por los tres integrantes.
