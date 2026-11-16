# Recuperación de memoria

`retrieval.py` implementa el núcleo independiente de recuperación que utiliza el adaptador de ChromaDB:

- filtra obligatoriamente por `user_id`;
- ignora memorias que no estén activas;
- permite limitar tipos de memoria;
- aplica similitud coseno, umbral mínimo y `top_k`;
- devuelve resultados ordenados de forma estable.

El módulo recibe embeddings ya calculados. El proveedor de `ai/embeddings/` generará los vectores y `chroma_store.py` proporciona las candidatas desde Chroma. La autorización se validará en el backend usando el alumno de la sesión autenticada.

El adaptador guarda contenido, vector, ID lógico, propietario, tipo, estado e importancia. Deriva el ID físico de la pareja `(user_id, memory_id)` para que dos alumnos puedan tener el mismo ID lógico sin sobrescribirse. El guardado exige que el propietario coincida con el alumno autenticado. La recuperación filtra por alumno y estado activo y comprueba de nuevo los datos recibidos. El borrado elimina contenido y vector de Chroma usando conjuntamente ID físico y propietario.

La interfaz sigue la documentación oficial de [colecciones](https://docs.trychroma.com/reference/python/collection), [configuración](https://docs.trychroma.com/docs/collections/configure) y [filtros](https://docs.trychroma.com/docs/querying-collections/metadata-filtering). `from_client` crea o abre la colección con distancia coseno y sin generación implícita de embeddings. Rechaza colecciones existentes que utilicen otra métrica, para que la búsqueda inicial y la selección final usen el mismo criterio.

## Uso desde el backend

```python
from ai.memory import ChromaMemoryStore, MemoryRecord

# client puede ser HttpClient o PersistentClient de Chroma.
store = ChromaMemoryStore.from_client(client, collection_name="academy_memories")
memory = MemoryRecord(
    memory_id="memory-1",
    user_id=authenticated_user_id,
    memory_type="progress",
    content="Confunde present perfect y past simple.",
    embedding=embedding_provider.embed_text("Confunde present perfect y past simple."),
    importance=3,
)
store.upsert_memory(memory, user_id=authenticated_user_id)
query_vector = embedding_provider.embed_text("Can we practise present perfect?")
results = store.retrieve(query_vector, user_id=authenticated_user_id)
store.delete_memory("memory-1", user_id=authenticated_user_id)
```

El backend debe obtener `authenticated_user_id` de la sesión, comprobar la propiedad en PostgreSQL y conservar allí fuente, fechas y confianza. Tras un borrado registrará la fuente bloqueada para evitar recrear automáticamente la memoria desde el mismo mensaje. Esa coordinación con PostgreSQL queda pendiente de la integración de Peio; el adaptador solo modifica el índice vectorial.

Cada colección debe usar un único modelo y dimensión de embeddings. Si se cambia el modelo, se crea otra colección y se reindexa; no deben mezclarse vectores de modelos distintos aunque tengan igual dimensión. La búsqueda de Chroma es aproximada: el umbral y los resultados se calibrarán con el conjunto de evaluación.

## Verificación

### Servicio de contexto

`service.py` conecta el proveedor de embeddings con el almacén: recibe la consulta como texto y el alumno autenticado, pide un vector y recupera memorias. Devuelve un `MemoryContext` sin vectores ni identificadores de usuario. Mantiene ID lógico, tipo, contenido y similitud para la integración; la similitud no se incluye en el JSON para el tutor porque no representa confianza ni progreso.

```python
from ai.memory import MemoryContextService

service = MemoryContextService(embedding_provider, store)
context = service.recall(student_message, user_id=authenticated_user_id)
# Comprobar estos IDs en PostgreSQL y completar fuente/fecha antes del tutor.
memory_ids = [item.memory_id for item in context.items]
retrieved_memories = context.to_json()
```

Por defecto admite 3 memorias, una similitud mínima de 0.70, consultas de hasta 4000 caracteres, resúmenes de hasta 600 caracteres y un JSON de contexto de hasta 1800 caracteres, incluidos metadatos y escapes. Son límites en caracteres, no en tokens. Pueden ajustarse con `MemoryContextPolicy`; el máximo de memorias está limitado a 10. Los resúmenes que no caben se omiten enteros para no alterar hechos al cortar frases.

Las consultas inválidas y los filtros de tipos vacíos se resuelven antes de llamar al proveedor de embeddings. Los errores de proveedor o almacén se propagan y no se presentan como búsquedas sin resultados. El servicio no conserva una caché de memorias entre llamadas: vuelve a consultar el índice y respeta los borrados posteriores.

`to_json()` etiqueta el contenido como datos educativos no confiables y mantiene el texto dentro de campos JSON. `TutorTurnService` aplica las reglas versionadas y conserva este bloque separado del mensaje actual; `OpenAITutorResponder` valida la respuesta del proveedor. Serializar como JSON no elimina por sí solo las instrucciones maliciosas. La autorización definitiva en PostgreSQL y el cableado con los endpoints del backend siguen pendientes.

### Pruebas

Las pruebas unitarias funcionan sin instalar Chroma:

```powershell
python -m unittest discover -s ai -t . -v
```

Para ejecutar también la integración con `chromadb==1.5.9` en memoria, desde la raíz del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-chroma.txt
.\.venv\Scripts\python.exe -m unittest discover -s ai -t . -v
```

Estas pruebas usan vectores de ejemplo, desactivan la telemetría de Chroma y no descargan modelos ni llaman a OpenAI. Comprueban guardar, actualizar, recuperar, filtrar y borrar; también que el mismo ID en dos alumnos permanezca aislado. Sin la dependencia opcional, la integración se marca explícitamente como omitida. En VS Code puede seleccionarse `.venv\Scripts\python.exe` como intérprete.

### Demo para el equipo

Desde la terminal integrada de VS Code, con las dependencias opcionales instaladas:

```powershell
.\.venv\Scripts\python.exe -m ai.memory.demo
```

La demo guarda ejemplos de dos alumnos, abre otra instancia del servicio, consulta la dificultad del primero, la borra y vuelve a consultar. La memoria del segundo se conserva. Chroma funciona realmente en memoria; el proveedor utiliza vectores fijos y solo admite los textos de ejemplo. Esto permite comprobar el recorrido y el aislamiento sin API key. No evalúa la calidad semántica de OpenAI ni la personalización del tutor. Los datos desaparecen al terminar la ejecución.
