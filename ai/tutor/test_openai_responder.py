import unittest
from dataclasses import dataclass
from unittest.mock import Mock

from ai.memory.service import MemoryContext
from ai.tutor.openai_responder import (
    OpenAITutorResponder,
    TutorResponseError,
)
from ai.tutor.service import MemoryContextProvider, TutorTurnService


@dataclass
class FakeUsage:
    input_tokens: int | None = 20
    output_tokens: int | None = 10
    total_tokens: int | None = 30


@dataclass
class FakeResponse:
    id: object = "response-1"
    status: object = "completed"
    output_text: object = "  Great! Let's practise.  "
    usage: object = None
    output: object = None


@dataclass
class FakeContent:
    type: str
    refusal: object = None


@dataclass
class FakeMessage:
    content: object


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


def valid_request():
    return {
        "model": "configured-chat-model",
        "instructions": "Tutor rules",
        "input": [{"role": "user", "content": "Hello"}],
        "store": False,
        "metadata": {"prompt_version": "tutor-system-v1"},
    }


class OpenAITutorResponderTests(unittest.TestCase):
    def test_request_builder_and_responder_share_the_same_contract(self):
        memory_service = Mock(spec=MemoryContextProvider)
        memory_service.recall.return_value = MemoryContext()
        request = TutorTurnService(
            memory_service,
            model="configured-chat-model",
        ).prepare(
            "Can you correct this sentence?",
            user_id="student-1",
            estimated_level="A2",
        )
        client = FakeClient(response=FakeResponse())

        reply = OpenAITutorResponder(client).generate(request)

        self.assertEqual(client.responses.last_request, request)
        self.assertEqual(reply.text, "Great! Let's practise.")

    def test_generate_calls_responses_and_returns_text_and_usage(self):
        response = FakeResponse(usage=FakeUsage())
        client = FakeClient(response=response)
        responder = OpenAITutorResponder(client)
        request = valid_request()

        reply = responder.generate(request)

        self.assertEqual(client.responses.last_request, request)
        self.assertEqual(reply.response_id, "response-1")
        self.assertEqual(reply.text, "Great! Let's practise.")
        self.assertFalse(reply.refused)
        self.assertEqual(reply.input_tokens, 20)
        self.assertEqual(reply.output_tokens, 10)
        self.assertEqual(reply.total_tokens, 30)

    def test_missing_usage_is_allowed(self):
        responder = OpenAITutorResponder(FakeClient(response=FakeResponse()))

        reply = responder.generate(valid_request())

        self.assertIsNone(reply.input_tokens)
        self.assertIsNone(reply.output_tokens)
        self.assertIsNone(reply.total_tokens)

    def test_valid_refusal_is_returned_as_a_controlled_reply(self):
        response = FakeResponse(
            output_text="",
            output=[
                FakeMessage(
                    content=[
                        FakeContent(type="refusal", refusal="I cannot help with that.")
                    ]
                )
            ],
        )

        reply = OpenAITutorResponder(FakeClient(response=response)).generate(
            valid_request()
        )

        self.assertEqual(reply.text, "I cannot help with that.")
        self.assertTrue(reply.refused)

    def test_invalid_request_does_not_call_api(self):
        cases = (
            None,
            {},
            {**valid_request(), "model": ""},
            {**valid_request(), "instructions": ""},
            {**valid_request(), "input": []},
            {**valid_request(), "input": "Hello"},
            {**valid_request(), "store": True},
            {**valid_request(), "store": None},
            {**valid_request(), "api_key": "must-not-be-here"},
        )
        for request in cases:
            with self.subTest(request=request):
                client = FakeClient(response=FakeResponse())
                with self.assertRaises(ValueError):
                    OpenAITutorResponder(client).generate(request)
                self.assertEqual(client.responses.call_count, 0)

    def test_incomplete_empty_or_malformed_response_is_rejected(self):
        cases = (
            FakeResponse(status="incomplete"),
            FakeResponse(status="failed"),
            FakeResponse(status=None),
            FakeResponse(id=""),
            FakeResponse(id=None),
            FakeResponse(output_text=""),
            FakeResponse(output_text=None),
            FakeResponse(usage=FakeUsage(input_tokens=-1)),
            FakeResponse(usage=FakeUsage(output_tokens=True)),
            FakeResponse(usage=FakeUsage(total_tokens="30")),
        )
        for response in cases:
            with self.subTest(response=response):
                with self.assertRaises(TutorResponseError):
                    OpenAITutorResponder(FakeClient(response=response)).generate(
                        valid_request()
                    )

    def test_sdk_error_is_propagated(self):
        failure = RuntimeError("API unavailable")
        responder = OpenAITutorResponder(FakeClient(error=failure))

        with self.assertRaises(RuntimeError) as raised:
            responder.generate(valid_request())

        self.assertIs(raised.exception, failure)


if __name__ == "__main__":
    unittest.main()
