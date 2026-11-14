import json
import tempfile
import unittest
from pathlib import Path

from ai.memory.extraction import MemoryExtractionService
from ai.memory.extraction_evaluation import (
    MemoryExtractionEvaluationError,
    evaluate_memory_extraction,
    load_memory_extraction_cases,
)


CASES_PATH = Path(__file__).with_name("extraction-evaluation-cases-v1.json")


class ScriptedGenerator:
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    def generate(self, interaction, **_options):
        self.calls += 1
        response = self.responses[interaction]
        if isinstance(response, Exception):
            raise response
        return response


def response_for(case):
    expected = case.expected
    if expected.action == "discard":
        return {
            "action": "discard",
            "target_memory_id": None,
            "memory_type": None,
            "content": None,
            "topic": None,
            "importance": None,
            "confidence": None,
            "reason": "No aporta memoria educativa segura.",
        }
    return {
        "action": expected.action,
        "target_memory_id": expected.target_memory_id,
        "memory_type": expected.memory_type,
        "content": " ".join(expected.content_terms),
        "topic": "English learning",
        "importance": 2,
        "confidence": 0.90,
        "reason": "Información educativa útil y explícita.",
    }


class MemoryExtractionEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.version, cls.cases = load_memory_extraction_cases(CASES_PATH)

    def test_v1_dataset_is_valid_and_covers_key_behaviours(self):
        self.assertEqual(self.version, "memory-extraction-evaluation-v1")
        self.assertEqual(len(self.cases), 8)
        self.assertEqual(
            {case.expected.action for case in self.cases},
            {"create", "update", "discard"},
        )
        self.assertTrue(any(case.source_blocked for case in self.cases))

    def test_perfect_script_scores_one_hundred_percent(self):
        responses = {
            case.interaction: response_for(case)
            for case in self.cases
            if not case.source_blocked
        }
        generator = ScriptedGenerator(responses)

        report = evaluate_memory_extraction(
            MemoryExtractionService(generator),
            self.cases,
            version=self.version,
        )

        self.assertEqual(report.action_accuracy, 1.0)
        self.assertEqual(report.exact_accuracy, 1.0)
        self.assertEqual(report.failures, ())
        self.assertEqual(generator.calls, 7)

    def test_mismatch_and_provider_error_are_reported_without_stopping(self):
        responses = {
            case.interaction: response_for(case)
            for case in self.cases
            if not case.source_blocked
        }
        responses[self.cases[0].interaction] = response_for(self.cases[1])
        responses[self.cases[1].interaction] = RuntimeError("provider unavailable")

        report = evaluate_memory_extraction(
            MemoryExtractionService(ScriptedGenerator(responses)),
            self.cases,
            version=self.version,
        )

        self.assertEqual(report.total_cases, 8)
        self.assertEqual(report.action_matches, 6)
        self.assertEqual(report.exact_matches, 6)
        self.assertEqual(len(report.failures), 2)
        self.assertIn("ME-01", report.failures[0])
        self.assertIn("RuntimeError", report.failures[1])

    def test_invalid_or_empty_dataset_is_rejected(self):
        invalid_payloads = (
            {"version": "v1", "cases": []},
            {"version": "v1", "cases": [{"id": "incomplete"}]},
            {
                "version": "v1",
                "cases": [
                    {
                        "id": "blocked-create",
                        "interaction": "Remember this",
                        "existing_memories": [],
                        "source_blocked": True,
                        "expected": {
                            "action": "create",
                            "memory_type": "progress",
                            "target_memory_id": None,
                            "content_terms": ["remember"],
                        },
                    }
                ],
            },
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "cases.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(MemoryExtractionEvaluationError):
                    load_memory_extraction_cases(path)

        with self.assertRaises(MemoryExtractionEvaluationError):
            evaluate_memory_extraction(
                MemoryExtractionService(ScriptedGenerator({})),
                (),
                version="v1",
            )


if __name__ == "__main__":
    unittest.main()
