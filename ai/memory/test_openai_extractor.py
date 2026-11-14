import json
import unittest
from dataclasses import dataclass
from unittest.mock import patch

from ai.memory.extraction import (
    MEMORY_EXTRACTION_PROMPT_VERSION,
    ExistingMemory,
    MemoryExtractionError,
    MemoryExtractionService,
)
from ai.memory.openai_extractor import (
    MAX_OUTPUT_TOKENS,
    MEMORY_EXTRACTION_FORMAT,
    MEMORY_EXTRACTION_INSTRUCTIONS_V2,
    MemoryExtractionProviderError,
    OpenAIMemoryExtractionGenerator,
)


@dataclass
class FakeResponse:
    status: object = "completed"
    output_text: object = ""


class FakeResponsesEndpoint:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.last_request = None
        self.call_count = 0

    def create(self, **kwargs):
        self.call_count += 1
        self.last_request = kwargs
        if self.error is not None:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, response=None, error=None):
        self.responses = FakeResponsesEndpoint(response=response, error=error)


def valid_proposal():
    return {
        "action": "create",
        "target_memory_id": None,
        "memory_type": "progress",
        "content": "Confunde present perfect y past simple.",
        "topic": "present perfect",
        "importance": 2,
        "confidence": 0.91,
        "reason": "Dificultad explícita y útil.",
    }


class OpenAIMemoryExtractionGeneratorTests(unittest.TestCase):
    def test_service_and_generator_share_a_valid_contract(self):
        client = FakeClient(
            response=FakeResponse(output_text=json.dumps(valid_proposal()))
        )
        generator = OpenAIMemoryExtractionGenerator(client, "configured-memory-model")
        service = MemoryExtractionService(generator)

        decision = service.propose(
            "  I confuse present perfect and past simple.  ",
            existing_memories=[
                ExistingMemory("memory-1", "preference", "Prefiere ejemplos breves.")
            ],
        )

        self.assertEqual(decision.action, "create")
        request = client.responses.last_request
        self.assertEqual(request["model"], "configured-memory-model")
        self.assertEqual(request["instructions"], MEMORY_EXTRACTION_INSTRUCTIONS_V2)
        self.assertEqual(request["text"], {"format": MEMORY_EXTRACTION_FORMAT})
        self.assertEqual(request["max_output_tokens"], MAX_OUTPUT_TOKENS)
        self.assertIs(request["store"], False)
        self.assertEqual(
            request["metadata"],
            {"prompt_version": MEMORY_EXTRACTION_PROMPT_VERSION},
        )

        dynamic_input = json.loads(request["input"][0]["content"])
        self.assertEqual(dynamic_input["kind"], "untrusted_memory_extraction_input")
        self.assertEqual(
            dynamic_input["interaction"],
            "I confuse present perfect and past simple.",
        )
        self.assertEqual(dynamic_input["existing_memories"][0]["memory_id"], "memory-1")

    def test_invalid_inputs_do_not_call_openai(self):
        cases = (
            {"interaction": ""},
            {"interaction": None},
            {"interaction": "x" * 4001},
            {"existing_memories": "memory"},
            {"existing_memories": [object()]},
            {"existing_memories": [ExistingMemory("", "progress", "content")]},
            {
                "existing_memories": [
                    ExistingMemory("same", "progress", "content"),
                    ExistingMemory("same", "progress", "other content"),
                ]
            },
            {"prompt_version": "memory-extraction-v999"},
        )
        for changed in cases:
            with self.subTest(changed=changed):
                client = FakeClient(response=FakeResponse())
                generator = OpenAIMemoryExtractionGenerator(client, "model")
                arguments = {
                    "interaction": "valid interaction",
                    "existing_memories": (),
                    "prompt_version": MEMORY_EXTRACTION_PROMPT_VERSION,
                    **changed,
                }
                with self.assertRaises(ValueError):
                    generator.generate(**arguments)
                self.assertEqual(client.responses.call_count, 0)

    def test_invalid_configuration_is_rejected(self):
        client = FakeClient(response=FakeResponse())
        for model in ("", "   ", None, "line\nbreak", "x" * 201):
            with self.subTest(model=model):
                with self.assertRaises(ValueError):
                    OpenAIMemoryExtractionGenerator(client, model)

    def test_incomplete_empty_or_oversized_response_is_rejected(self):
        cases = (
            FakeResponse(status="incomplete", output_text="{}"),
            FakeResponse(status="failed", output_text="{}"),
            FakeResponse(status=None, output_text="{}"),
            FakeResponse(output_text=""),
            FakeResponse(output_text=None),
            FakeResponse(output_text="x" * 5001),
        )
        for response in cases:
            with self.subTest(response=response):
                generator = OpenAIMemoryExtractionGenerator(
                    FakeClient(response=response), "model"
                )
                with self.assertRaises(MemoryExtractionProviderError):
                    generator.generate(
                        "valid interaction",
                        existing_memories=(),
                        prompt_version=MEMORY_EXTRACTION_PROMPT_VERSION,
                    )

    def test_malformed_structured_output_is_still_rejected_by_our_validator(self):
        generator = OpenAIMemoryExtractionGenerator(
            FakeClient(response=FakeResponse(output_text='{"action":"create"}')),
            "model",
        )

        with self.assertRaises(MemoryExtractionError):
            MemoryExtractionService(generator).propose("valid interaction")

    def test_sdk_error_is_propagated(self):
        failure = RuntimeError("API unavailable")
        generator = OpenAIMemoryExtractionGenerator(
            FakeClient(error=failure),
            "model",
        )

        with self.assertRaises(RuntimeError) as raised:
            generator.generate(
                "valid interaction",
                existing_memories=(),
                prompt_version=MEMORY_EXTRACTION_PROMPT_VERSION,
            )

        self.assertIs(raised.exception, failure)

    def test_environment_requires_configured_model_before_sdk_use(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "OPENAI_MEMORY_MODEL"):
                OpenAIMemoryExtractionGenerator.from_environment()


if __name__ == "__main__":
    unittest.main()
