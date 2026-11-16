import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from ai.memory.extraction_demo import main, run_demo
from ai.memory.openai_extractor import OpenAIMemoryExtractionGenerator


class MemoryExtractionDemoTests(unittest.TestCase):
    def test_creation_deduplication_and_preference_update_preserve_identity(self):
        report = run_demo()
        steps = {step.scenario: step for step in report.steps}

        created = steps["create-difficulty"]
        duplicated = steps["deduplicate-difficulty"]
        self.assertEqual(created.action, "create")
        self.assertEqual(created.memory_id, "demo-memory-1")
        self.assertEqual(duplicated.action, "update")
        self.assertEqual(duplicated.memory_id, created.memory_id)
        self.assertEqual(duplicated.active_memory_ids, created.active_memory_ids)
        self.assertEqual(len(duplicated.active_memory_ids), 1)

        preference = steps["create-preference"]
        updated = steps["update-preference"]
        self.assertEqual(preference.action, "create")
        self.assertEqual(preference.memory_id, "demo-memory-2")
        self.assertEqual(updated.action, "update")
        self.assertEqual(updated.memory_id, preference.memory_id)
        self.assertEqual(updated.active_memory_ids, preference.active_memory_ids)
        self.assertNotEqual(updated.content, preference.content)
        self.assertEqual(updated.content, "Prefiere explicaciones solo en inglés.")
        self.assertEqual(len(updated.active_memory_ids), 2)
        self.assertEqual(len(report.remaining_memories), 1)
        self.assertEqual(report.remaining_memories[0].memory_id, updated.memory_id)
        self.assertEqual(report.remaining_memories[0].memory_type, "preference")
        self.assertEqual(report.remaining_memories[0].content, updated.content)

    def test_discard_and_invalid_proposal_do_not_change_any_memory(self):
        report = run_demo()
        steps = {step.scenario: step for step in report.steps}
        previous = steps["update-preference"]

        greeting = steps["discard-greeting"]
        rejected = steps["reject-invalid"]
        self.assertEqual(greeting.action, "discard")
        self.assertEqual(greeting.active_memory_ids, previous.active_memory_ids)
        self.assertEqual(greeting.active_memories, previous.active_memories)
        self.assertEqual(rejected.action, "rejected")
        self.assertEqual(rejected.active_memory_ids, previous.active_memory_ids)
        self.assertEqual(rejected.active_memories, previous.active_memories)
        self.assertEqual(rejected.provider_calls, 1)
        self.assertEqual(
            {memory.memory_type for memory in rejected.active_memories},
            {"progress", "preference"},
        )
        self.assertEqual(
            next(
                memory.content
                for memory in rejected.active_memories
                if memory.memory_id == "demo-memory-2"
            ),
            "Prefiere explicaciones solo en inglés.",
        )

    def test_deleted_source_is_not_recreated_and_skips_the_provider(self):
        report = run_demo()
        blocked = next(step for step in report.steps if step.scenario == "blocked-source")

        self.assertEqual(blocked.action, "discard")
        self.assertEqual(blocked.provider_calls, 0)
        self.assertEqual(blocked.active_memory_ids, ("demo-memory-2",))
        self.assertNotIn("demo-memory-1", blocked.active_memory_ids)
        self.assertEqual(report.total_provider_calls, 6)
        self.assertEqual(sum(step.provider_calls for step in report.steps), 6)

    def test_repeated_runs_are_independent_and_do_not_create_a_real_client(self):
        with patch.object(
            OpenAIMemoryExtractionGenerator,
            "from_environment",
            side_effect=AssertionError("La demo no debe crear un cliente real."),
        ) as create_real_client:
            first = run_demo()
            second = run_demo()

        create_real_client.assert_not_called()
        self.assertEqual(first, second)
        self.assertEqual(first.total_provider_calls, 6)
        self.assertEqual(second.total_provider_calls, 6)

    def test_json_command_returns_a_complete_machine_readable_report(self):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["--json"])
        payload = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["mode"], "scripted-demo")
        report = payload["report"]
        self.assertEqual(len(report["steps"]), 7)
        self.assertEqual(report["total_provider_calls"], 6)
        self.assertEqual(
            report["remaining_memories"][0]["content"],
            "Prefiere explicaciones solo en inglés.",
        )
        self.assertEqual(report["steps"][-1]["provider_calls"], 0)


if __name__ == "__main__":
    unittest.main()
