import json
import unittest
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from unittest.mock import Mock

from ai.memory.chroma_store import ChromaMemoryStore, ChromaResultError
from ai.memory.retrieval import MemoryRecord


class FakeCollection:
    def __init__(self, query_result=None, *, configuration=None):
        self.configuration = (
            {"hnsw": {"space": "cosine"}}
            if configuration is None
            else configuration
        )
        self.query_result = query_result if query_result is not None else {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "embeddings": [[]],
        }
        self.upsert_request = None
        self.upsert_requests = []
        self.query_request = None
        self.delete_request = None

    def upsert(self, **kwargs):
        self.upsert_request = kwargs
        self.upsert_requests.append(kwargs)

    def query(self, **kwargs):
        self.query_request = kwargs
        return self.query_result

    def delete(self, **kwargs):
        self.delete_request = kwargs


def storage_id(user_id, memory_id):
    payload = json.dumps([user_id, memory_id], ensure_ascii=True).encode("utf-8")
    return "memory-" + sha256(payload).hexdigest()


def query_result(*records):
    metadatas = [dict(record[2], memory_id=record[0]) for record in records]
    return {
        "ids": [
            [storage_id(metadata["user_id"], metadata["memory_id"]) for metadata in metadatas]
        ],
        "documents": [[record[1] for record in records]],
        "metadatas": [metadatas],
        "embeddings": [[record[3] for record in records]],
    }


def sample_record():
    return (
        "memory-1",
        "Prefiere explicaciones en español.",
        {
            "user_id": "student-1",
            "memory_type": "preference",
            "status": "active",
            "importance": 2,
        },
        [1.0, 0.0],
    )


class ChromaMemoryStoreTests(unittest.TestCase):
    def test_upsert_stores_vector_content_and_minimal_metadata(self):
        collection = FakeCollection()
        store = ChromaMemoryStore(collection)
        memory = MemoryRecord(
            memory_id="memory-1",
            user_id="student-1",
            memory_type="progress",
            content="Confunde present perfect y past simple.",
            embedding=(0.9, 0.1),
            importance=3,
        )

        store.upsert_memory(memory, user_id="student-1")

        self.assertEqual(
            collection.upsert_request,
            {
                "ids": [storage_id("student-1", "memory-1")],
                "embeddings": [[0.9, 0.1]],
                "documents": ["Confunde present perfect y past simple."],
                "metadatas": [
                    {
                        "memory_id": "memory-1",
                        "user_id": "student-1",
                        "memory_type": "progress",
                        "status": "active",
                        "importance": 3,
                    }
                ],
            },
        )

    def test_query_always_filters_owner_status_and_optional_types(self):
        collection = FakeCollection(
            query_result(
                (
                    "memory-1",
                    "Prefiere explicaciones en español.",
                    {
                        "user_id": "student-1",
                        "memory_type": "preference",
                        "status": "active",
                        "importance": 2,
                    },
                    [1.0, 0.0],
                )
            )
        )
        store = ChromaMemoryStore(collection)

        memories = store.query_candidates(
            (1.0, 0.0),
            user_id="student-1",
            n_results=5,
            memory_types={"preference", "progress"},
        )

        self.assertEqual([memory.memory_id for memory in memories], ["memory-1"])
        self.assertEqual(
            collection.query_request,
            {
                "query_embeddings": [[1.0, 0.0]],
                "n_results": 5,
                "where": {
                    "$and": [
                        {"user_id": {"$eq": "student-1"}},
                        {"status": {"$eq": "active"}},
                        {
                            "memory_type": {
                                "$in": ["preference", "progress"]
                            }
                        },
                    ]
                },
                "include": ["documents", "metadatas", "embeddings"],
            },
        )

    def test_unexpected_cross_user_or_deleted_result_is_rejected(self):
        for metadata in (
            {
                "user_id": "student-2",
                "memory_type": "progress",
                "status": "active",
            },
            {
                "user_id": "student-1",
                "memory_type": "progress",
                "status": "deleted",
            },
        ):
            with self.subTest(metadata=metadata):
                collection = FakeCollection(
                    query_result(("unsafe", "Do not expose", metadata, [1.0, 0.0]))
                )
                with self.assertRaises(ChromaResultError):
                    ChromaMemoryStore(collection).query_candidates(
                        (1.0, 0.0),
                        user_id="student-1",
                    )

    def test_retrieve_applies_local_similarity_threshold(self):
        collection = FakeCollection(
            query_result(
                (
                    "relevant",
                    "Dificultad con present perfect.",
                    {
                        "user_id": "student-1",
                        "memory_type": "progress",
                        "status": "active",
                        "importance": 3,
                    },
                    [0.95, 0.05],
                ),
                (
                    "irrelevant",
                    "Vocabulario de viajes.",
                    {
                        "user_id": "student-1",
                        "memory_type": "semantic",
                        "status": "active",
                        "importance": 1,
                    },
                    [0.0, 1.0],
                ),
            )
        )

        results = ChromaMemoryStore(collection).retrieve(
            (1.0, 0.0),
            user_id="student-1",
            min_similarity=0.70,
        )

        self.assertEqual([result.memory.memory_id for result in results], ["relevant"])

    def test_delete_requires_owner_filter(self):
        collection = FakeCollection()
        store = ChromaMemoryStore(collection)

        store.delete_memory("memory-1", user_id="student-1")

        self.assertEqual(
            collection.delete_request,
            {
                "ids": [storage_id("student-1", "memory-1")],
                "where": {"user_id": {"$eq": "student-1"}},
            },
        )

    def test_same_logical_id_for_two_users_has_distinct_storage_ids(self):
        collection = FakeCollection()
        store = ChromaMemoryStore(collection)
        first = MemoryRecord("shared-id", "student-1", "progress", "Pasado simple.", (1.0, 0.0))
        second = replace(first, user_id="student-2", content="Entrevistas.")

        store.upsert_memory(first, user_id="student-1")
        store.upsert_memory(second, user_id="student-2")

        self.assertNotEqual(
            collection.upsert_requests[0]["ids"],
            collection.upsert_requests[1]["ids"],
        )
        self.assertEqual(
            collection.upsert_requests[1]["ids"],
            [storage_id("student-2", "shared-id")],
        )
        # El borrado de un alumno utiliza únicamente su espacio de identificadores.
        store.delete_memory("shared-id", user_id="student-1")
        self.assertEqual(
            collection.delete_request["ids"],
            collection.upsert_requests[0]["ids"],
        )
        self.assertNotEqual(
            collection.delete_request["ids"],
            collection.upsert_requests[1]["ids"],
        )

    def test_authenticated_user_cannot_upsert_another_users_memory(self):
        collection = FakeCollection()
        store = ChromaMemoryStore(collection)
        memory = MemoryRecord("memory-1", "student-2", "progress", "Pasado simple.", (1.0, 0.0))

        with self.assertRaises(ValueError):
            store.upsert_memory(memory, user_id="student-1")

        self.assertIsNone(collection.upsert_request)

    def test_invalid_or_deleted_memory_is_rejected_before_upsert(self):
        memory = MemoryRecord("memory-1", "student-1", "progress", "Pasado simple.", (1.0, 0.0))
        changes = (
            {"content": None},
            {"content": "  "},
            {"memory_type": "untrusted-type"},
            {"importance": 1.5},
            {"importance": True},
            {"status": "deleted"},
            {"embedding": (0.0, 0.0)},
        )
        for change in changes:
            with self.subTest(change=change):
                collection = FakeCollection()
                with self.assertRaises(ValueError):
                    ChromaMemoryStore(collection).upsert_memory(
                        replace(memory, **change), user_id="student-1"
                    )
                self.assertIsNone(collection.upsert_request)

    def test_invalid_returned_content_type_or_importance_is_rejected(self):
        valid = query_result(sample_record())
        for field, value in (
            ("document", None),
            ("document", 42),
            ("importance", 1.5),
            ("importance", True),
            ("memory_type", "untrusted-type"),
            ("memory_id", None),
        ):
            with self.subTest(field=field, value=value):
                result = deepcopy(valid)
                if field == "document":
                    result["documents"][0][0] = value
                else:
                    result["metadatas"][0][0][field] = value
                with self.assertRaises(ChromaResultError):
                    ChromaMemoryStore(FakeCollection(result)).query_candidates(
                        (1.0, 0.0), user_id="student-1"
                    )

    def test_incomplete_columns_or_duplicate_ids_are_rejected(self):
        valid = query_result(sample_record())
        malformed = [{}]
        for field in ("ids", "documents", "metadatas", "embeddings"):
            for invalid_column in (None, [None], [], [[], []]):
                result = deepcopy(valid)
                result[field] = invalid_column
                malformed.append(result)
        duplicates = query_result(sample_record(), sample_record())
        malformed.append(duplicates)
        wrong_length = deepcopy(valid)
        wrong_length["documents"][0] = []
        malformed.append(wrong_length)

        for result in malformed:
            with self.subTest(result=result):
                with self.assertRaises(ChromaResultError):
                    ChromaMemoryStore(FakeCollection(result)).query_candidates(
                        (1.0, 0.0), user_id="student-1"
                    )

    def test_storage_id_must_match_owner_and_logical_id(self):
        result = query_result(sample_record())
        result["ids"][0][0] = storage_id("student-2", "memory-1")

        with self.assertRaises(ChromaResultError):
            ChromaMemoryStore(FakeCollection(result)).query_candidates(
                (1.0, 0.0), user_id="student-1"
            )

    def test_returned_types_and_dimensions_must_match_query(self):
        valid = query_result(sample_record())
        wrong_type = deepcopy(valid)
        wrong_type["metadatas"][0][0]["memory_type"] = "semantic"
        wrong_dimension = deepcopy(valid)
        wrong_dimension["embeddings"][0][0] = [1.0, 0.0, 0.0]
        for result in (wrong_type, wrong_dimension):
            with self.subTest(result=result):
                with self.assertRaises(ChromaResultError):
                    ChromaMemoryStore(FakeCollection(result)).query_candidates(
                        (1.0, 0.0), user_id="student-1", memory_types={"preference"}
                    )

    def test_more_results_than_requested_are_rejected(self):
        first = sample_record()
        second = ("memory-2", first[1], first[2], first[3])
        with self.assertRaises(ChromaResultError):
            ChromaMemoryStore(FakeCollection(query_result(first, second))).query_candidates(
                (1.0, 0.0), user_id="student-1", n_results=1
            )

    def test_invalid_query_arguments_do_not_call_sdk(self):
        for arguments in (
            {"user_id": ""},
            {"user_id": None},
            {"n_results": 0},
            {"n_results": True},
            {"n_results": 1.5},
            {"memory_types": "progress"},
            {"memory_types": {"unknown"}},
        ):
            with self.subTest(arguments=arguments):
                collection = FakeCollection()
                options = {"user_id": "student-1", **arguments}
                with self.assertRaises(ValueError):
                    ChromaMemoryStore(collection).query_candidates((1.0, 0.0), **options)
                self.assertIsNone(collection.query_request)

    def test_invalid_query_vectors_do_not_call_sdk(self):
        for vector in ((), (0.0, 0.0), (float("nan"), 1.0), (float("inf"), 0.0), "12"):
            with self.subTest(vector=vector):
                collection = FakeCollection()
                with self.assertRaises(ValueError):
                    ChromaMemoryStore(collection).query_candidates(vector, user_id="student-1")
                self.assertIsNone(collection.query_request)

    def test_invalid_retrieval_arguments_do_not_call_sdk(self):
        for arguments in (
            {"top_k": 0},
            {"top_k": True},
            {"top_k": 1.5},
            {"min_similarity": 1.01},
            {"min_similarity": float("nan")},
        ):
            with self.subTest(arguments=arguments):
                collection = FakeCollection()
                with self.assertRaises(ValueError):
                    ChromaMemoryStore(collection).retrieve(
                        (1.0, 0.0), user_id="student-1", **arguments
                    )
                self.assertIsNone(collection.query_request)

    def test_empty_type_filter_returns_no_results_without_sdk_call(self):
        collection = FakeCollection()
        results = ChromaMemoryStore(collection).query_candidates(
            (1.0, 0.0), user_id="student-1", memory_types=set()
        )
        self.assertEqual(results, [])
        self.assertIsNone(collection.query_request)

    def test_invalid_delete_arguments_do_not_call_sdk(self):
        for memory_id, user_id in (("", "student-1"), ("memory-1", ""), (None, "student-1")):
            with self.subTest(memory_id=memory_id, user_id=user_id):
                collection = FakeCollection()
                with self.assertRaises(ValueError):
                    ChromaMemoryStore(collection).delete_memory(memory_id, user_id=user_id)
                self.assertIsNone(collection.delete_request)

    def test_existing_collection_requires_cosine_metric(self):
        for configuration in ({}, {"hnsw": {"space": "l2"}}, {"hnsw": None}):
            with self.subTest(configuration=configuration):
                with self.assertRaises(ValueError):
                    ChromaMemoryStore(FakeCollection(configuration=configuration))

    def test_from_client_configures_cosine_without_implicit_embedding_model(self):
        collection = FakeCollection()
        client = Mock()
        client.get_or_create_collection.return_value = collection

        store = ChromaMemoryStore.from_client(client, collection_name="academy_memories")

        self.assertIs(store.collection, collection)
        client.get_or_create_collection.assert_called_once_with(
            name="academy_memories",
            embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
        )


if __name__ == "__main__":
    unittest.main()
