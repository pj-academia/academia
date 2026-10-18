# MVP: tutor de inglés con memoria persistente

## Usuario inicial

Persona hispanohablante que quiere mejorar su inglés y necesita una práctica adaptada a su nivel, errores y forma preferida de aprender.

## Recorrido demostrable

1. El alumno crea una cuenta.
2. Realiza una prueba inicial breve de nivel.
3. El sistema estima un nivel inicial y propone un punto de partida.
4. El alumno conversa o responde un ejercicio.
5. El sistema guarda errores y preferencias educativas relevantes.
6. En una nueva sesión, recupera solo las memorias pertinentes y adapta la explicación.
7. El alumno consulta o elimina una memoria.
8. El progreso se actualiza con intentos y resultados reales.

## Alcance incluido

- Estimación inicial A1, A2, B1 o B2+; no es una certificación oficial.
- Prueba diagnóstica inicial de 12 preguntas de gramática, vocabulario y comprensión.
- Chat y ejercicios de inglés.
- Memoria semántica, episódica, de preferencias y de progreso.
- Recuperación semántica limitada al propietario de los datos.
- Panel de memorias y progreso.

## Fuera del MVP

- Certificaciones oficiales de idioma.
- Corrección de pronunciación o voz.
- Generación de imágenes.
- Fine-tuning de modelos propios.
- Agentes autónomos, Redis, Loki y Kubernetes como infraestructura.

## Criterios de aceptación iniciales

| ID | Criterio |
| --- | --- |
| AC-01 | Un alumno completa la prueba inicial y obtiene un nivel estimado explicable. |
| AC-02 | Dos alumnos no pueden consultar los datos, memorias o ejercicios del otro. |
| AC-03 | Una conversación se guarda y puede recuperarse después de cerrar sesión. |
| AC-04 | Una dificultad relevante, como confundir `past simple` y `present perfect`, puede convertirse en memoria con fuente. |
| AC-05 | En otra conversación, el sistema recupera esa memoria y adapta la respuesta sin inventar antecedentes. |
| AC-06 | El alumno puede eliminar una memoria y esta deja de recuperarse. |
| AC-07 | Un ejercicio y su resultado actualizan el progreso con evidencia trazable. |
| AC-08 | El entorno se levanta siguiendo instrucciones reproducibles y las pruebas críticas pasan. |
