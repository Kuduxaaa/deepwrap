import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from deepwrap.memory import MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.path = Path(self.directory.name) / "memory.db"
        self.memory = MemoryStore(self.path, namespace="project-a")

    def tearDown(self):
        self.directory.cleanup()

    def test_remember_recall_and_forget(self):
        stored = self.memory.remember(
            "The project uses pytest for all tests.",
            tags=["project", "testing"],
            importance=0.9,
        )
        recalled = self.memory.recall("pytest")
        self.assertEqual(recalled[0]["id"], stored["id"])
        self.assertEqual(recalled[0]["tags"], ["project", "testing"])

        self.memory.forget(stored["id"])
        self.assertEqual(self.memory.recall("pytest"), [])

    def test_memories_persist_across_store_instances(self):
        stored = self.memory.remember("Persistent value")
        reopened = MemoryStore(self.path, namespace="project-a")
        self.assertEqual(reopened.get(stored["id"])["content"], "Persistent value")

    def test_namespaces_are_isolated(self):
        self.memory.remember("Only project A")
        other = MemoryStore(self.path, namespace="project-b")
        self.assertEqual(other.list(), [])

    def test_session_transcript_can_resume(self):
        session_id = self.memory.create_session("expert", title="Feature work")
        self.memory.add_turn(session_id, "user", "Build the API")
        self.memory.add_turn(session_id, "assistant", "The API is ready")
        self.memory.checkpoint(session_id, "API implementation completed")

        reopened = MemoryStore(self.path, namespace="project-a")
        context = reopened.session_context(session_id)
        self.assertIn("API implementation completed", context)
        self.assertIn("Build the API", context)
        self.assertIn("The API is ready", context)

    def test_memory_tool_registry_is_complete(self):
        self.assertEqual(
            {tool.name for tool in self.memory.definitions},
            {"remember", "recall", "list_memories", "forget", "list_sessions"},
        )
        self.assertEqual(
            {tool.name for tool in self.memory.definitions},
            set(self.memory.functions),
        )


if __name__ == "__main__":
    unittest.main()
