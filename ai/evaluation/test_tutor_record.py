import hashlib
import json
import unittest
from dataclasses import replace
from unittest.mock import Mock

from ai.evaluation.tutor_record import build_tutor_evaluation_record
from ai.memory.service import MemoryContext, MemoryContextItem
from ai.tutor import TutorReply
from ai.tutor.service import MemoryContextProvider, TutorTurnService


class TutorEvaluationRecordTests(unittest.TestCase):
    def setUp(self):
        self.memory_service = Mock(spec=MemoryContextProvider)
        self.memory_service.recall.return_value = MemoryContext(
            items=(
                MemoryContextItem(
                    memory_id="memory-1",
                    memory_type="progress",
                    content="Confunde present perfect y past simple.",
                    similarity=0.92,
                ),
            )
        )
        self.request = TutorTurnService(
            self.memory_service,
            model="configured-chat-model",
        ).prepare(
            "Can we practise present perfect?",
            user_id="student-private-id",
            estimated_level="B1",
        )
        self.reply = TutorReply(
            response_id="response-1",
            text="Let's contrast present perfect with past simple.",
            input_tokens=100,
            output_tokens=30,
            total_tokens=130,
        )

    def test_record_keeps_evidence_without_private_turn_content(self):
        record = build_tutor_evaluation_record(
            run_id="run-2026-11-13",
            case_id="MEM-01",
            condition="with_memory",
            request=self.request,
            reply=self.reply,
            latency_ms=125.5,
        )

        payload = record.to_dict()
        serialized = record.to_json()
        self.assertEqual(payload["memory_ids"], ["memory-1"])
        self.assertEqual(payload["model"], "configured-chat-model")
        self.assertEqual(payload["prompt_version"], "tutor-system-v1")
        self.assertEqual(payload["latency_ms"], 125.5)
        self.assertEqual(
            payload["output_sha256"],
            hashlib.sha256(self.reply.text.encode("utf-8")).hexdigest(),
        )
        self.assertFalse(payload["output_text_included"])
        self.assertNotIn("output_text", payload)
        for private_value in (
            "student-private-id",
            "Can we practise present perfect?",
            "Confunde present perfect y past simple.",
            self.reply.text,
        ):
            self.assertNotIn(private_value, serialized)

    def test_synthetic_run_can_explicitly_include_output_text(self):
        record = build_tutor_evaluation_record(
            run_id="synthetic-run",
            case_id="MEM-01",
            condition="with_memory",
            request=self.request,
            reply=self.reply,
            latency_ms=10,
            include_output_text=True,
        )

        self.assertTrue(record.to_dict()["output_text_included"])
        self.assertEqual(record.to_dict()["output_text"], self.reply.text)

    def test_without_memory_condition_requires_an_empty_memory_list(self):
        with self.assertRaises(ValueError):
            build_tutor_evaluation_record(
                run_id="run-1",
                case_id="MEM-01",
                condition="without_memory",
                request=self.request,
                reply=self.reply,
                latency_ms=10,
            )

        self.memory_service.recall.return_value = MemoryContext()
        empty_request = TutorTurnService(
            self.memory_service,
            model="configured-chat-model",
        ).prepare("Hello", user_id="student-1", estimated_level="A1")
        record = build_tutor_evaluation_record(
            run_id="run-1",
            case_id="MEM-01",
            condition="without_memory",
            request=empty_request,
            reply=self.reply,
            latency_ms=10,
        )

        self.assertEqual(record.memory_ids, ())

    def test_malformed_context_or_duplicate_memory_ids_are_rejected(self):
        cases = []
        for content in ("not-json", "{}"):
            request = dict(self.request)
            request["input"] = [{"role": "user", "content": content}]
            cases.append(request)

        duplicate = json.loads(self.request["input"][0]["content"])
        duplicate["educational_memory"]["memories"].append(
            dict(duplicate["educational_memory"]["memories"][0])
        )
        duplicate_request = dict(self.request)
        duplicate_request["input"] = [
            {"role": "user", "content": json.dumps(duplicate)},
        ]
        cases.append(duplicate_request)

        for request in cases:
            with self.subTest(request=request):
                with self.assertRaises(ValueError):
                    build_tutor_evaluation_record(
                        run_id="run-1",
                        case_id="MEM-01",
                        condition="with_memory",
                        request=request,
                        reply=self.reply,
                        latency_ms=10,
                    )

    def test_invalid_metadata_metrics_or_identifiers_are_rejected(self):
        invalid_request = dict(self.request)
        invalid_request["metadata"] = {}
        cases = (
            {"run_id": ""},
            {"case_id": ""},
            {"condition": "unknown"},
            {"latency_ms": -1},
            {"latency_ms": float("nan")},
            {"latency_ms": True},
            {"include_output_text": 1},
            {"request": invalid_request},
            {"request": None},
            {"reply": None},
            {"reply": replace(self.reply, input_tokens=-1)},
            {"reply": replace(self.reply, text="")},
            {"reply": replace(self.reply, text=None)},
            {"reply": replace(self.reply, refused=1)},
        )
        for changed in cases:
            with self.subTest(changed=changed):
                arguments = {
                    "run_id": "run-1",
                    "case_id": "MEM-01",
                    "condition": "with_memory",
                    "request": self.request,
                    "reply": self.reply,
                    "latency_ms": 10,
                    **changed,
                }
                with self.assertRaises(ValueError):
                    build_tutor_evaluation_record(**arguments)


if __name__ == "__main__":
    unittest.main()
