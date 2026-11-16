# Decisiones y plan de Academia IA

Este documento resume las decisiones vigentes del proyecto. Los detalles de arquitectura se conservan en los [ADR](adr/) y el alcance funcional en [MVP](mvp.md).

## Decisiones confirmadas

| Área | Decisión | Motivo |
| --- | --- | --- |
| Producto | Tutor de inglés para estudiantes hispanohablantes | Alcance acordado por el equipo; permite demostrar personalización y memoria con un dominio concreto. |
| Nivel inicial | Estimación orientativa A1, A2, B1 o B2+ | Sirve para adaptar la experiencia sin presentarse como certificación oficial. |
| IA | OpenAI mediante adaptadores propios | Evita acoplar la lógica educativa al SDK y permite pruebas deterministas con clientes simulados. |
| Memoria vectorial | ChromaDB con distancia coseno | Permite recuperar memorias relevantes y filtrar obligatoriamente por propietario. |
| Autoridad de datos | PostgreSQL | Mantendrá propiedad, fuente, fechas, confianza y estado; ChromaDB será un índice auxiliar. |
| Backend | FastAPI con arquitectura hexagonal por módulo | Separa dominio, casos de uso, adaptadores y API; la regla está descrita en el ADR 0001. |
| Entorno | Docker Compose y GitHub Actions | Proporciona ejecución reproducible y una barrera automática de calidad. |
| Privacidad del modelo | `store=False` y contexto mínimo | No se envían identificadores de alumno, vectores ni similitudes al proveedor. |

## Estado verificado a 13 de noviembre de 2026

- Test diagnóstico de 12 preguntas y estimación de nivel implementados como lógica independiente.
- Proveedor de embeddings, recuperación, adaptador Chroma y borrado probados.
- Preparación de turnos y validación de respuestas de OpenAI probadas con cliente simulado.
- Registro minimizado para comparar ejecuciones con y sin memoria.
- 67 pruebas de IA superadas localmente, incluidas 5 con ChromaDB real en memoria.
- CI de backend, frontend, Docker y pre-commit en funcionamiento; la rama actual añade las pruebas de IA como trabajo obligatorio.

Estos puntos verifican módulos independientes. No significan que el recorrido completo del alumno esté conectado todavía.

## Pendiente antes del MVP integrado

1. Conectar `ai/` con los puertos y casos de uso del backend sin romper el ADR 0001.
2. Implementar autenticación y usar siempre el alumno de la sesión como propietario.
3. Persistir conversaciones, fuentes y metadatos de memoria en PostgreSQL.
4. Seleccionar el modelo de OpenAI, acordar presupuesto y configurar la clave solo en el servidor.
5. Exponer endpoints para prueba inicial, chat, memoria y borrado.
6. Conectar el frontend y completar el recorrido entre sesiones.
7. Ejecutar los ocho casos sintéticos con y sin memoria y aplicar la rúbrica humana.

## Plan y criterio de avance

El orden de integración será `autenticación -> prueba inicial -> chat -> memoria -> nueva sesión -> respuesta adaptada`. Cada bloque debe entrar mediante pull request, con CI en verde, al menos una aprobación y evidencia registrada en [contribuciones](contributions.md). Las fechas objetivo están en el [roadmap](roadmap.md).

## Decisiones aún abiertas

- Modelo de chat, límites de tokens y presupuesto máximo.
- Mecanismo final de sesión y autorización.
- Despliegue en Azure y presupuesto disponible.
- Material educativo inicial y licencias de las fuentes.
- Umbrales definitivos de recuperación después de ejecutar la evaluación.
