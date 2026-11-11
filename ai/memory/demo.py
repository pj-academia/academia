"""Demo local: consulta de texto -> vector de ejemplo -> Chroma -> contexto."""

from uuid import uuid4

from ai.memory.chroma_store import ChromaMemoryStore
from ai.memory.retrieval import MemoryRecord
from ai.memory.service import MemoryContextService


QUERY = "Can we practise present perfect?"
DIFFICULTY = "Confunde present perfect y past simple."
OTHER_LEARNER = "Otro alumno practica present perfect para una entrevista."
TRAVEL = "Practicó vocabulario de viajes."


class DemoEmbeddingProvider:
    """Vectores fijos para este ejemplo; no implementa comprensión semántica."""

    def embed_text(self, text: str) -> tuple[float, ...]:
        return {
            QUERY: (1.0, 0.0),
            DIFFICULTY: (0.95, 0.05),
            OTHER_LEARNER: (1.0, 0.0),
            TRAVEL: (0.0, 1.0),
        }[text]


def main() -> None:
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        raise SystemExit("Instala requirements-chroma.txt en el entorno del proyecto.")

    print("Demo técnica: Chroma real en memoria y embeddings simulados.")
    print("Usa vectores fijos; no llama a OpenAI ni evalúa calidad semántica.\n")
    client = chromadb.EphemeralClient(Settings(anonymized_telemetry=False))
    name = "demo-memory-" + uuid4().hex
    store = ChromaMemoryStore.from_client(client, collection_name=name)
    provider = DemoEmbeddingProvider()
    try:
        for memory_id, user_id, content in (
            ("difficulty", "demo-student-1", DIFFICULTY),
            ("travel", "demo-student-1", TRAVEL),
            ("difficulty", "demo-student-2", OTHER_LEARNER),
        ):
            store.upsert_memory(
                MemoryRecord(
                    memory_id=memory_id,
                    user_id=user_id,
                    memory_type="progress" if memory_id == "difficulty" else "episodic",
                    content=content,
                    embedding=provider.embed_text(content),
                ),
                user_id=user_id,
            )

        # Otra instancia representa una nueva petición/sesión del backend.
        next_session = MemoryContextService(
            provider, ChromaMemoryStore.from_client(client, collection_name=name)
        )
        context = next_session.recall(QUERY, user_id="demo-student-1")
        print("1. Consulta del alumno 1:", QUERY)
        print(context.to_json())

        store.delete_memory("difficulty", user_id="demo-student-1")
        after_delete = next_session.recall(QUERY, user_id="demo-student-1")
        print("\n2. Misma consulta después de borrar la dificultad del alumno 1:")
        print(after_delete.to_json())

        other_context = next_session.recall(QUERY, user_id="demo-student-2")
        print("\n3. La memoria independiente del alumno 2 se conserva:")
        print(other_context.to_json())
        print("\nLos datos de esta demo viven solo durante la ejecución.")
    finally:
        client.delete_collection(name)


if __name__ == "__main__":
    main()
