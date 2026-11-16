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

    def test_matching_script_scores_fields_but_requires_content_review(self):
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
        self.assertEqual(report.field_term_accuracy, 1.0)
        self.assertEqual(
            report.pending_content_review,
            ("ME-02", "ME-03", "ME-05", "ME-06", "ME-08"),
        )
        self.assertEqual(report.failures, ())
        self.assertEqual(report.accepted_content_reviews, ())
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
        self.assertEqual(report.field_term_matches, 6)
        self.assertEqual(len(report.failures), 2)
        self.assertIn("ME-01", report.failures[0])
        self.assertIn("RuntimeError", report.failures[1])

    def test_keyword_matches_do_not_claim_contradictory_memories_are_correct(self):
        responses = {
            case.interaction: response_for(case)
            for case in self.cases
            if not case.source_blocked
        }
        responses[self.cases[1].interaction]["content"] = (
            "Domina present perfect y past simple sin dificultades."
        )
        responses[self.cases[4].interaction]["content"] = (
            "Prefiere español; NO desea explicaciones en inglés."
        )

        report = evaluate_memory_extraction(
            MemoryExtractionService(ScriptedGenerator(responses)),
            self.cases,
            version=self.version,
        )

        # La presencia de términos sigue siendo mecánicamente comprobable,
        # pero no se publica como exactitud ni como fidelidad del recuerdo.
        self.assertEqual(report.field_term_matches, 8)
        self.assertIn("ME-02", report.pending_content_review)
        self.assertIn("ME-05", report.pending_content_review)
        self.assertFalse(hasattr(report, "exact_accuracy"))
        self.assertFalse(hasattr(report, "exact_matches"))

        reviewed_decisions = []

        def reviewer(case, decision):
            reviewed_decisions.append((case.case_id, decision.content))
            if case.case_id in {"ME-02", "ME-05"}:
                return False
            return None

        reviewed_report = evaluate_memory_extraction(
            MemoryExtractionService(ScriptedGenerator(responses)),
            self.cases,
            version=self.version,
            content_reviewer=reviewer,
        )

        self.assertEqual(reviewed_report.rejected_content_reviews, ("ME-02", "ME-05"))
        self.assertEqual(reviewed_report.accepted_content_reviews, ())
        self.assertEqual(
            reviewed_report.pending_content_review, ("ME-03", "ME-06", "ME-08")
        )
        self.assertEqual(len(reviewed_report.failures), 2)
        self.assertIn(
            ("ME-02", responses[self.cases[1].interaction]["content"]),
            reviewed_decisions,
        )

    def test_content_review_records_acceptance_and_isolates_review_errors(self):
        responses = {
            case.interaction: response_for(case)
            for case in self.cases
            if not case.source_blocked
        }

        def reviewer(case, decision):
            if case.case_id == "ME-02":
                return True
            if case.case_id == "ME-03":
                raise RuntimeError("review unavailable")
            if case.case_id == "ME-05":
                return "yes"
            return None

        report = evaluate_memory_extraction(
            MemoryExtractionService(ScriptedGenerator(responses)),
            self.cases,
            version=self.version,
            content_reviewer=reviewer,
        )

        self.assertEqual(report.accepted_content_reviews, ("ME-02",))
        self.assertEqual(report.rejected_content_reviews, ())
        self.assertEqual(
            report.pending_content_review, ("ME-03", "ME-05", "ME-06", "ME-08")
        )
        self.assertEqual(report.field_term_matches, 8)
        self.assertEqual(len(report.failures), 2)
        self.assertIn("ME-03: revisión RuntimeError", report.failures)
        self.assertIn("ME-05: revisión ValueError", report.failures)

    def test_update_labels_reject_wrong_target_type_and_malformed_ids(self):
        invalid_expectations = (
            {"memory_type": "progress"},
            {"target_memory_id": []},
            {"target_memory_id": {}},
            {"target_memory_id": 1},
            {"target_memory_id": None},
            {"target_memory_id": "   "},
            {"target_memory_id": "unknown-memory"},
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cases.json"
            for changes in invalid_expectations:
                with self.subTest(changes=changes):
                    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
                    payload["cases"][4]["expected"].update(changes)
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.assertRaises(MemoryExtractionEvaluationError):
                        load_memory_extraction_cases(path)

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
