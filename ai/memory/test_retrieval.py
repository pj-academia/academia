import unittest

from ai.memory.retrieval import MemoryRecord, retrieve_memories


class MemoryRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.memories = [
            MemoryRecord(
                memory_id="relevant",
                user_id="student-1",
                memory_type="progress",
                content="Confunde present perfect y past simple.",
                embedding=(0.95, 0.05),
                importance=3,
            ),
            MemoryRecord(
                memory_id="irrelevant",
                user_id="student-1",
                memory_type="semantic",
                content="Practicó vocabulario sobre viajes.",
                embedding=(0.0, 1.0),
            ),
            MemoryRecord(
                memory_id="other-user",
                user_id="student-2",
                memory_type="progress",
                content="Prepara una entrevista de trabajo.",
                embedding=(1.0,),
                importance=3,
            ),
            MemoryRecord(
                memory_id="deleted",
                user_id="student-1",
                memory_type="progress",
                content="Memoria que el alumno eliminó.",
                embedding=(0.0, 0.0),
                status="deleted",
                importance=3,
            ),
        ]

    def test_retrieves_only_relevant_active_memory_for_current_user(self):
        results = retrieve_memories(
            self.memories,
            (1.0, 0.0),
            user_id="student-1",
            min_similarity=0.70,
        )

        self.assertEqual([item.memory.memory_id for item in results], ["relevant"])

    def test_cross_user_and_deleted_memories_never_appear(self):
        results = retrieve_memories(
            self.memories,
            (1.0, 0.0),
            user_id="student-1",
            min_similarity=-1.0,
        )

        ids = {item.memory.memory_id for item in results}
        self.assertNotIn("other-user", ids)
        self.assertNotIn("deleted", ids)

    def test_type_filter_and_top_k_are_enforced(self):
        candidates = [
            MemoryRecord(
                memory_id="preference-low",
                user_id="student-1",
                memory_type="preference",
                content="Prefiere ejemplos cortos.",
                embedding=(1.0, 0.0),
                importance=1,
            ),
            MemoryRecord(
                memory_id="preference-high",
                user_id="student-1",
                memory_type="preference",
                content="Prefiere explicaciones en español.",
                embedding=(1.0, 0.0),
                importance=3,
            ),
            MemoryRecord(
                memory_id="progress",
                user_id="student-1",
                memory_type="progress",
                content="Ha mejorado en pasado simple.",
                embedding=(1.0, 0.0),
                importance=3,
            ),
        ]

        results = retrieve_memories(
            candidates,
            (1.0, 0.0),
            user_id="student-1",
            top_k=1,
            memory_types={"preference"},
        )

        self.assertEqual(results[0].memory.memory_id, "preference-high")

    def test_invalid_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            retrieve_memories([], (1.0, 0.0), user_id="", top_k=3)
        with self.assertRaises(ValueError):
            retrieve_memories([], (1.0, 0.0), user_id="student-1", top_k=0)
        with self.assertRaises(ValueError):
            retrieve_memories([], (), user_id="student-1")
        with self.assertRaises(ValueError):
            retrieve_memories([], (float("nan"), 1.0), user_id="student-1")


if __name__ == "__main__":
    unittest.main()
