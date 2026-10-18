# Diseño del test inicial de inglés

## Objetivo y límite

La prueba inicial de Academia IA dura pocos minutos y solo estima el punto de partida entre A1, A2, B1 y B2+. No es un examen Cambridge, no concede certificaciones y no sustituye una prueba completa. Después, las actividades escritas y la conversación con el tutor aportarán evidencia para ajustar el nivel.

No se copian preguntas, respuestas ni textos de exámenes comerciales. Cada ítem del repositorio es original y se revisará antes de mostrarlo a alumnado real.

## Referencias de diseño

- [Cambridge A2 Key: preparación y pruebas de ejemplo](https://www.cambridgeenglish.org/exams-and-tests/qualifications/key/preparation/): combina comprensión lectora y escrita con listening y speaking. Sirve para orientar las tareas de A2.
- [Cambridge B1 Preliminary: formato](https://www.cambridgeenglish.org/exams-and-tests/preliminary/exam-format/?level=basic&skill=reading): incluye mensajes cortos, lectura detallada, cloze y vocabulario/estructura. Estas son referencias para las tareas B1.
- [Cambridge B2 First: formato](https://www.cambridgeenglish.org/exams-and-tests/qualifications/first/format/?rows=24): integra Reading and Use of English y evalúa control de gramática y vocabulario en contexto. Orienta los ítems B2.
- [British Council: gramática A1-A2](https://learnenglish.britishcouncil.org/free-resources/grammar/a1-a2): aporta áreas de contenido iniciales, como artículos, pasado simple y continuo, cuantificadores y comparativos.
- [British Council: estructura de Grammar and Vocabulary](https://www.britishcouncil.org/exam/english/english-assessment-schools/secondary-english-test-prepare): usa elección múltiple contextual, definiciones, sinónimos, uso de palabra y colocaciones.

## Estructura del MVP

| Bloque | Ítems | Evidencia buscada | Referencia de formato |
| --- | ---: | --- | --- |
| A1 | 1-3 | estructuras básicas, vocabulario cotidiano y comprensión de un mensaje corto | gramática y vocabulario inicial |
| A2 | 4-6 | pasado simple, situaciones funcionales y mensaje/señal breve | A2 Key |
| B1 | 7-9 | condicionales, idea principal e inferencia, vocabulario en contexto | B1 Preliminary |
| B2 | 10-12 | Use of English, colocaciones y reformulación controlada | B2 First |

Todos los ítems serán originales, de respuesta cerrada y con cuatro opciones en el MVP. El backend conserva las respuestas correctas y el frontend recibe únicamente el enunciado y las opciones.

## Evolución prevista

Cuando el flujo básico esté funcionando, se añadirá una microtarea escrita opcional y se usará una rúbrica explícita para valorar gramática, vocabulario y adecuación. La primera versión no afirmará medir listening ni speaking, porque no incluye audio ni una evaluación oral validada.
