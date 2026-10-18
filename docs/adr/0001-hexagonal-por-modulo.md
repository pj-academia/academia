# ADR 0001: Arquitectura hexagonal por módulo de dominio

- **Estado:** aceptada
- **Fecha:** 2026-10-18

## Decisión

El backend se organiza en **módulos por dominio** (`auth`, `chat`, `memory`, `progress`). Dentro de cada módulo, la profundidad de capas depende de sus dependencias externas:

| Módulo | Estructura | Motivo |
|---|---|---|
| `memory`, `chat` | Hexagonal completa: `domain`, `application` (casos de uso + puertos), `infrastructure` (adaptadores driven) y `api` (adaptador driving) | Dependen de proveedores externos: LLM, embeddings y ChromaDB |
| `auth`, `progress` | Ligera: `api`, `application` y repositorio | Son CRUD sobre PostgreSQL; más capas serían ceremonia |

## Reglas

1. **Las dependencias apuntan hacia dentro.** `domain` no importa nada externo; `application` solo importa `domain`; `api` e `infrastructure` no se importan entre sí.
2. **Los puertos son `typing.Protocol`** y viven en `application`.
3. **El cableado vive solo en `app/bootstrap.py`** (composition root). Los routers reciben sus casos de uso; nunca construyen adaptadores.
4. **`app/shared` es solo transversal** (configuración, logging, métricas) y no importa módulos de dominio.

Estas reglas se **verifican en el CI con `import-linter`** (contratos en `backend/pyproject.toml`). Si se rompen, el build falla.

## Consecuencias

- **A favor:** cambiar de proveedor de LLM o de base vectorial no toca los casos de uso. Los casos de uso se testean con fakes de los puertos, sin llamar a APIs de pago y de forma determinista.
- **A favor:** la estructura del árbol describe el producto, y cada módulo tiene un responsable claro, lo que facilita trazar la contribución individual.
- **En contra:** más archivos y algo de indirección en `memory` y `chat`. Se acepta porque es donde está la complejidad real del sistema.

## Alternativas descartadas

- **Capas técnicas globales** (`routers/`, `services/`, `models/`): ocultan el dominio y mezclan responsabilidades de todos los módulos.
- **Hexagonal completa en todos los módulos**: sobreingeniería para módulos CRUD en un proyecto de tres personas.
