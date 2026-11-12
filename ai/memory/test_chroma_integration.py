"""Pruebas opcionales con Chroma real en memoria, sin modelos ni red."""

import importlib.util
import unittest
from dataclasses import replace
from uuid import uuid4

from ai.memory.chroma_store import ChromaMemoryStore
from ai.memory.retrieval import MemoryRecord
from ai.memory.service import MemoryContextService


@unittest.skipUnless(
    importlib.util.find_spec("chromadb") is not None,
    "Instala requirements-chroma.txt para ejecutar la integración real.",
)
class ChromaIntegrationTests(unittest.TestCase):
    def setUp(self):
        import chromadb
        from chromadb.config import Settings

        self.client = chromadb.EphemeralClient(Settings(anonymized_telemetry=False))
        self.name = "test-memory-" + uuid4().hex
        self.store = ChromaMemoryStore.from_client(
            self.client, collection_name=self.name
        )
        self.memory = MemoryRecord(
            memory_id="same-id",
            user_id="student-1",
            memory_type="progress",
            content="Confunde present perfect y past simple.",
            embedding=(0.95, 0.05),
            importance=3,
        )

    def tearDown(self):
        # Solo la colección temporal creada por esta prueba.
        self.client.delete_collection(self.name)

    def test_upsert_update_and_delete_preserve_other_student(self):
        self.store.upsert_memory(self.memory, user_id="student-1")
        other = replace(
            self.memory, user_id="student-2", content="Otra memoria independiente."
        )
        self.store.upsert_memory(other, user_id="student-2")
        updated = replace(self.memory, content="Acierta 4 de 5 ejercicios.")
        self.store.upsert_memory(updated, user_id="student-1")

        self.assertEqual(self.store.collection.count(), 2)
        results = self.store.retrieve((1.0, 0.0), user_id="student-1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].memory.memory_id, "same-id")
        self.assertEqual(results[0].memory.content, updated.content)

        self.store.delete_memory("same-id", user_id="student-1")
        self.assertEqual(self.store.retrieve((1.0, 0.0), user_id="student-1"), [])
        remaining = self.store.retrieve((1.0, 0.0), user_id="student-2")
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].memory.content, other.content)

    def test_deletion_cannot_target_another_students_memory(self):
        self.store.upsert_memory(self.memory, user_id="student-1")

        self.store.delete_memory("same-id", user_id="student-2")

        self.assertEqual(self.store.collection.count(), 1)
        self.assertEqual(len(self.store.retrieve((1.0, 0.0), user_id="student-1")), 1)

    def test_cosine_and_type_filters_work_with_real_vectors(self):
        self.assertEqual(self.store.retrieve((1.0, 0.0), user_id="student-1"), [])
        relevant = replace(self.memory, embedding=(100.0, 0.1))
        less_relevant = replace(
            self.memory, memory_id="less-relevant", embedding=(1.0, 1.0)
        )
        preference = replace(
            self.memory,
            memory_id="preference",
            memory_type="preference",
            embedding=(1.0, 0.0),
        )
        for memory in (relevant, less_relevant, preference):
            self.store.upsert_memory(memory, user_id="student-1")

        results = self.store.retrieve(
            (1.0, 0.0), user_id="student-1", top_k=1, memory_types={"progress"}
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].memory.memory_id, relevant.memory_id)
        self.assertGreater(results[0].similarity, 0.99)

    def test_existing_l2_collection_is_rejected(self):
        # Una colección existente no cambia de métrica mediante get_or_create.
        l2_name = "test-l2-" + uuid4().hex
        self.client.create_collection(
            l2_name, embedding_function=None, configuration={"hnsw": {"space": "l2"}}
        )
        try:
            with self.assertRaisesRegex(ValueError, "cosine"):
                ChromaMemoryStore.from_client(self.client, collection_name=l2_name)
        finally:
            self.client.delete_collection(l2_name)

    def test_text_query_recovers_context_and_observes_deletion_between_calls(self):
        class ExampleEmbeddings:
            def __init__(self):
                self.queries = []

            def embed_text(self, text):
                self.queries.append(text)
                return (1.0, 0.0)

        provider = ExampleEmbeddings()
        self.store.upsert_memory(self.memory, user_id="student-1")
        next_session = MemoryContextService(
            provider,
            ChromaMemoryStore.from_client(self.client, collection_name=self.name),
        )

        before = next_session.recall("Help with present perfect", user_id="student-1")
        self.assertEqual(len(before.items), 1)
        self.assertEqual(before.items[0].content, self.memory.content)

        self.store.delete_memory(self.memory.memory_id, user_id="student-1")
        after = next_session.recall("Help with present perfect", user_id="student-1")

        self.assertEqual(after.items, ())
        self.assertEqual(len(provider.queries), 2)


if __name__ == "__main__":
    unittest.main()
