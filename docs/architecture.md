# Arquitectura propuesta

## Objetivo

Construir un MVP reproducible y comprensible que demuestre IA generativa, embeddings, base vectorial, memoria persistente, seguridad y prácticas DevOps sin añadir servicios que no resuelvan una necesidad concreta.

## Componentes

| Componente | Tecnología propuesta | Responsabilidad |
| --- | --- | --- |
| Frontend | Next.js + TypeScript | Prueba de nivel, chat, historial, memorias y progreso. |
| Backend | Python + FastAPI | API, validación, autorización, lógica educativa y conexión con proveedores. |
| Datos relacionales | PostgreSQL | Usuarios, sesiones, conversaciones, ejercicios, resultados y metadatos. |
| Datos vectoriales | ChromaDB | Embeddings y búsqueda semántica de memorias y materiales educativos. |
| IA generativa | OpenAI API | Respuestas, ejercicios, evaluación estructurada y embeddings. |
| Operación | Docker Compose + GitHub Actions | Entorno local, pruebas, construcción y automatización. |

## Flujo de una consulta

1. FastAPI identifica al alumno mediante sesión autenticada.
2. Guarda la consulta en PostgreSQL.
3. Genera su embedding mediante el proveedor configurado.
4. Consulta ChromaDB filtrando obligatoriamente por `user_id` y tipo de memoria.
5. Limita el contexto recuperado y construye un prompt educativo.
6. Solicita la respuesta al modelo de OpenAI.
7. Guarda la respuesta y analiza si existe una memoria nueva, actualizable o descartable.
8. Actualiza progreso solo con ejercicios o evidencias explícitas.

## Datos y privacidad

- PostgreSQL es la fuente de autoridad para propiedad y autorización.
- ChromaDB almacena identificadores, embeddings y metadatos mínimos; no decide permisos por sí solo.
- Cada memoria incluye usuario, tipo, contenido, fuente, conversación, mensaje de origen, importancia, confianza y fechas.
- El borrado debe impedir recuperaciones futuras y registrar la operación sin conservar el contenido eliminado.
- No se guardan claves de OpenAI ni contraseñas en código o logs.

## Decisiones pendientes de implementación

- Modelo concreto de OpenAI y límites de gasto.
- Mecanismo de sesión final.
- Esquema exacto de evaluación de la prueba diagnóstica.
- Material educativo inicial y licencias de sus fuentes.
- Despliegue en Azure y presupuesto disponible.
