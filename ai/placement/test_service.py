import unittest
from pathlib import Path

from ai.placement.service import (
    PlacementAnswerError,
    evaluate_answers,
    load_test,
    public_test,
)


TEST_PATH = Path(__file__).resolve().parents[2] / "content" / "placement-test-v1.json"


class PlacementServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test = load_test(TEST_PATH)
        cls.correct_answers = {
            item["id"]: item["correct_option"] for item in cls.test["items"]
        }

    def test_public_test_does_not_expose_answers_or_explanations(self):
        exposed = public_test(self.test)

        self.assertEqual(len(exposed["items"]), 12)
        for item in exposed["items"]:
            self.assertNotIn("correct_option", item)
            self.assertNotIn("explanation_es", item)

    def test_all_correct_answers_produce_b2_plus(self):
        result = evaluate_answers(self.test, self.correct_answers)

        self.assertEqual(result.score, 12)
        self.assertEqual(result.level, "B2+")

    def test_no_correct_answers_produce_a1(self):
        wrong_answers = {
            item["id"]: (item["correct_option"] + 1) % len(item["options"])
            for item in self.test["items"]
        }

        result = evaluate_answers(self.test, wrong_answers)

        self.assertEqual(result.score, 0)
        self.assertEqual(result.level, "A1")

    def test_incomplete_or_invalid_answers_are_rejected(self):
        incomplete_answers = dict(self.correct_answers)
        incomplete_answers.pop("PT-12")

        with self.assertRaises(PlacementAnswerError):
            evaluate_answers(self.test, incomplete_answers)

        invalid_answers = dict(self.correct_answers)
        invalid_answers["PT-01"] = 99
        with self.assertRaises(PlacementAnswerError):
            evaluate_answers(self.test, invalid_answers)


if __name__ == "__main__":
    unittest.main()
