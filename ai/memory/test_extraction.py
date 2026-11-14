import json
import unittest
from unittest.mock import Mock

from ai.memory.extraction import (
    MEMORY_EXTRACTION_PROMPT_VERSION,
    ExistingMemory,
    MemoryExtractionError,
    MemoryExtractionGenerator,
    MemoryExtractionService,
    parse_memory_extraction,
)


def proposal(**changes):
    value = {
        "action": "create",
        "target_memory_id": None,
        "memory_type": "progress",
        "content": "Confunde present perfect y past simple.",
        "topic": "present perfect",
        "importance": 2,
        "confidence": 0.91,
        "reason": "Dificultad explícita y útil para futuras prácticas.",
    }
    value.update(changes)
    return value


class MemoryExtractionParsingTests(unittest.TestCase):
    def test_valid_create_update_and_discard_are_parsed(self):
        created = parse_memory_extraction(json.dumps(proposal()))
        updated = parse_memory_extraction(
            proposal(action="update", target_memory_id="memory-1")
        )
        discarded = parse_memory_extraction(
            {
                "action": "discard",
                "target_memory_id": None,
                "memory_type": None,
                "content": None,
                "topic": None,
                "importance": None,
                "confidence": None,
                "reason": "Es un saludo sin valor educativo.",
            }
        )

        self.assertEqual(created.action, "create")
        self.assertEqual(created.confidence, 0.91)
        self.assertEqual(updated.target_memory_id, "memory-1")
        self.assertEqual(discarded.action, "discard")
        self.assertIsNone(discarded.content)

    def test_invalid_json_shape_or_action_is_rejected(self):
        cases = (
            "not-json",
            "[]",
            '{"action":"create","action":"discard"}',
            "x" * 5001,
            None,
            {**proposal(), "extra": "field"},
            {key: value for key, value in proposal().items() if key != "reason"},
            proposal(action="merge"),
            proposal(reason=""),
            proposal(reason="x" * 301),
        )
        for raw in cases:
            with self.subTest(raw=raw):
                with self.assertRaises(MemoryExtractionError):
                    parse_memory_extraction(raw)

    def test_create_or_update_requires_complete_high_confidence_memory(self):
        cases = (
            proposal(memory_type="unknown"),
            proposal(content=""),
            proposal(content="x" * 601),
            proposal(topic=""),
            proposal(topic="x" * 121),
            proposal(importance=0),
            proposal(importance=4),
            proposal(importance=True),
            proposal(confidence=0.69),
            proposal(confidence=-1),
            proposal(confidence=1.1),
            proposal(confidence=True),
            proposal(confidence=float("nan")),
            proposal(target_memory_id="memory-1"),
            proposal(action="update", target_memory_id=None),
            proposal(action="update", target_memory_id=""),
        )
        for raw in cases:
            with self.subTest(raw=raw):
                with self.assertRaises(MemoryExtractionError):
                    parse_memory_extraction(raw)

    def test_discard_requires_all_educational_fields_to_be_null(self):
        base = {
            "action": "discard",
            "target_memory_id": None,
            "memory_type": None,
            "content": None,
            "topic": None,
            "importance": None,
            "confidence": None,
            "reason": "No aporta valor educativo.",
        }
        for field in (
            "target_memory_id",
            "memory_type",
            "content",
            "topic",
            "importance",
            "confidence",
        ):
            with self.subTest(field=field):
                invalid = dict(base)
                invalid[field] = "unexpected"
                with self.assertRaises(MemoryExtractionError):
                    parse_memory_extraction(invalid)

    def test_extreme_confidence_values_raise_controlled_validation_errors(self):
        for confidence in (10**400, -(10**400), float("inf"), float("-inf")):
            with self.subTest(confidence=confidence):
                invalid = proposal(confidence=confidence)
                for raw in (invalid, json.dumps(invalid)):
                    with self.assertRaisesRegex(MemoryExtractionError, "confidence"):
                        parse_memory_extraction(raw)


class MemoryExtractionServiceTests(unittest.TestCase):
    def setUp(self):
        self.generator = Mock(spec=MemoryExtractionGenerator)
        self.generator.generate.return_value = proposal()
        self.service = MemoryExtractionService(self.generator)

    def test_service_passes_only_validated_context_to_generator(self):
        existing = ExistingMemory(
            memory_id="memory-1",
            memory_type="progress",
            content="Necesita practicar verbos irregulares.",
        )

        result = self.service.propose(
            "  I always confuse present perfect and past simple.  ",
            existing_memories=[existing],
        )

        self.generator.generate.assert_called_once_with(
            "I always confuse present perfect and past simple.",
            existing_memories=(existing,),
            prompt_version=MEMORY_EXTRACTION_PROMPT_VERSION,
        )
        self.assertEqual(result.action, "create")

    def test_blocked_source_is_discarded_without_model_call(self):
        result = self.service.propose(
            "I struggle with articles.",
            source_blocked=True,
        )

        self.assertEqual(result.action, "discard")
        self.assertIn("bloqueada", result.reason)
        self.generator.generate.assert_not_called()

    def test_exact_duplicate_is_converted_to_update(self):
        existing = ExistingMemory(
            memory_id="memory-1",
            memory_type="progress",
            content="Confunde   PRESENT perfect y past simple.",
        )

        result = self.service.propose(
            "I confuse both tenses.",
            existing_memories=[existing],
        )

        self.assertEqual(result.action, "update")
        self.assertEqual(result.target_memory_id, "memory-1")
        self.assertIn("duplicarse", result.reason)

    def test_update_requires_existing_target_with_same_type(self):
        existing = ExistingMemory("memory-1", "progress", "Old progress.")
        for generated in (
            proposal(action="update", target_memory_id="missing"),
            proposal(
                action="update",
                target_memory_id="memory-1",
                memory_type="preference",
            ),
        ):
            with self.subTest(generated=generated):
                self.generator.generate.return_value = generated
                with self.assertRaises(MemoryExtractionError):
                    self.service.propose("New evidence", existing_memories=[existing])

    def test_invalid_inputs_do_not_call_generator(self):
        service = MemoryExtractionService(
            self.generator,
            max_interaction_chars=10,
            max_existing_memories=1,
        )
        invalid_memory = ExistingMemory("", "progress", "content")
        duplicate = ExistingMemory("same", "progress", "content")
        cases = (
            {"interaction": ""},
            {"interaction": None},
            {"interaction": "x" * 11},
            {"existing_memories": "memory"},
            {"existing_memories": [invalid_memory]},
            {"existing_memories": [duplicate, duplicate]},
            {"source_blocked": 1},
        )
        for changed in cases:
            with self.subTest(changed=changed):
                arguments = {
                    "interaction": "valid",
                    "existing_memories": (),
                    "source_blocked": False,
                    **changed,
                }
                with self.assertRaises(ValueError):
                    service.propose(**arguments)
        self.generator.generate.assert_not_called()

    def test_invalid_service_configuration_is_rejected(self):
        for options in (
            {"max_interaction_chars": 0},
            {"max_interaction_chars": True},
            {"max_existing_memories": -1},
            {"max_existing_memories": 1.5},
        ):
            with self.subTest(options=options):
                with self.assertRaises(ValueError):
                    MemoryExtractionService(self.generator, **options)

    def test_duplicate_ids_are_rejected_within_the_memory_count_limit(self):
        memories = [
            ExistingMemory("same", "progress", "First difficulty."),
            ExistingMemory(" same ", "progress", "Second difficulty."),
        ]

        with self.assertRaisesRegex(ValueError, "IDs duplicados"):
            self.service.propose("New evidence", existing_memories=memories)

        self.generator.generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
