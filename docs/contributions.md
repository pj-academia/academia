# Registro de contribuciones

Este documento recoge contribuciones reales. No sustituye a los commits, pull requests, revisiones ni pruebas.

| Persona | Área inicial | Evidencias esperadas |
| --- | --- | --- |
| Antonio | IA, memoria y evaluación | Prompts, integración con OpenAI, embeddings, ChromaDB, recuperación, evaluación con y sin memoria. |
| Peio | Backend, datos y seguridad | FastAPI, PostgreSQL, autenticación, permisos, migraciones y pruebas de integración. |
| Pain | Frontend, experiencia y DevOps | Next.js, interfaz de chat, paneles, Docker Compose, GitHub Actions, métricas y demo. |

## Entrada por contribución

Añade una fila al completar una tarea importante.

Los módulos de IA se trasladaron desde `pj-academia/demo-repository`, commit `d934d10`, y se incorporaron a `main` mediante la PR #3. Las dos primeras filas conservan las tareas y validaciones del desarrollo original; sus ramas pertenecen al repositorio de origen.

| Fecha | Persona | Tarea | Rama / PR | Componentes | Pruebas o evidencia | Decisión relevante |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-11-11 | Antonio | Adaptador de memoria ChromaDB, con desarrollo asistido por Codex | `feat/chroma-memory-store` | `ai/memory/`, `requirements-chroma.txt` | 37 pruebas superadas, incluidas 4 con Chroma real en memoria; sin llamadas a OpenAI | IDs por propietario, filtros obligatorios y distancia coseno; coordinación con PostgreSQL pendiente. |
| 2026-11-11 | Antonio | Servicio que une embeddings y recuperación, con demo local; desarrollo asistido por Codex | `feat/chroma-memory-store` | `ai/memory/service.py`, `ai/memory/demo.py` y pruebas | 48 pruebas superadas, incluidas 5 con Chroma real; demo ejecutada con vectores fijos | Consultas validadas antes del embedding, contexto JSON acotado y sin caché; integración con tutor y PostgreSQL pendiente. |
| 2026-11-13 | Antonio | Preparación y ejecución de turnos del tutor con registro de evaluación; desarrollo asistido por Codex | `codex/tutor-request-preparation` | `ai/tutor/`, `ai/evaluation/` y documentación | 67 pruebas superadas, incluidas 5 con Chroma real; cliente OpenAI simulado, sin consumo de API | Reglas separadas del contexto no confiable, `store=False`, validación de respuestas y registro sin datos privados por defecto. |
