# Academia IA

Tutor de tecnología basado en IA generativa que recuerda las dificultades y preferencias de cada alumno entre sesiones para adaptar sus explicaciones. Proyecto Júpiter (TFM) del Máster en IA, Cloud Computing y DevOps.

> Las decisiones técnicas y su justificación están en [`docs/decisiones-y-plan.md`](docs/decisiones-y-plan.md). Las decisiones de arquitectura se registran en [`docs/adr/`](docs/adr/).

## Arranque rápido

**Requisitos:** Docker, [`uv`](https://docs.astral.sh/uv/), Node 22 con `pnpm` y [`mprocs`](https://github.com/pvolok/mprocs) **0.7.3** (`npm install -g mprocs@0.7.3`).

```bash
cp .env.example .env
(cd backend && uv sync)
(cd frontend && pnpm install)
mprocs
```

`mprocs` levanta la infraestructura en contenedores y las aplicaciones en nativo con recarga en caliente. Cada proceso tiene su panel de logs y puede reiniciarse por separado.

| Servicio | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend (API) | http://localhost:8010 · documentación en `/docs` |
| Estado del backend | http://localhost:8010/health |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 (dashboard "Backend HTTP") |
| ChromaDB | http://localhost:8001 |

## Modos de ejecución

| Modo | Comando | Uso |
|---|---|---|
| Desarrollo diario | `mprocs` | Infraestructura en contenedores, apps en nativo con recarga en caliente |
| Solo infraestructura | `docker compose up` | Si prefieres lanzar backend y frontend a mano |
| Sistema completo | `docker compose --profile app up --build` | Probar "como en producción"; es lo que construye el CI |

## Configuración de hooks (una vez por persona)

```bash
uv tool install pre-commit
pre-commit install
```

Los hooks formatean y lintean antes de cada commit y validan que el mensaje siga [Conventional Commits](https://www.conventionalcommits.org/es/). Son feedback rápido: la barrera de calidad real es el CI.

## Comandos habituales

| Área | Comando (desde la carpeta indicada) |
|---|---|
| Backend · tests unitarios | `backend/` → `uv run pytest` |
| Backend · tests de integración | raíz → `docker compose up -d --wait postgres chromadb`; `backend/` → `uv run pytest -m integration` |
| Backend · lint y formato | `backend/` → `uv run ruff check . && uv run ruff format .` |
| Backend · tipos (domain/application) | `backend/` → `uv run mypy` |
| Backend · arquitectura | `backend/` → `uv run lint-imports` |
| Frontend · tests | `frontend/` → `pnpm test` |
| Frontend · lint, tipos y formato | `frontend/` → `pnpm lint && pnpm typecheck && pnpm format` |

## Estructura

```
backend/     API FastAPI organizada por módulos de dominio (hexagonal en memory y chat)
frontend/    Next.js organizado por features (container/presentational)
infra/       Configuración de Prometheus y Grafana
docs/        Decisiones, plan y ADRs
```

## Flujo de trabajo

1. Cada tarea parte de un issue.
2. Una rama por tarea y una pull request que enlaza el issue (`Closes #N`).
3. El título de la PR sigue Conventional Commits: con squash merge se convierte en el commit de `main`.
4. Para mergear: CI en verde y una aprobación. Nadie hace push directo a `main`.

## Problemas conocidos

- **Error de certificados TLS con `uv`** (`invalid peer certificate: UnknownIssuer`): ocurre con proxies o antivirus que inspeccionan el tráfico. Define `UV_SYSTEM_CERTS=1` para usar el almacén de certificados del sistema.
- **Tests del frontend fallan con Node 20**: Vitest y jsdom requieren Node 22.12 o superior.
