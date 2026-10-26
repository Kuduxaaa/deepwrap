import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from deepwrap.memory import MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.path = Path(self.directory.name) / "memory.db"
        self.memory = MemoryStore(self.path, namespace="project-a")
        self.stores = [self.memory]

    def open_store(self, namespace="project-a"):
        """Open an extra store that is closed before the directory is removed."""

        store = MemoryStore(self.path, namespace=namespace)
        self.stores.append(store)
        return store

    def tearDown(self):
        for store in self.stores:
            store.close()
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
        reopened = self.open_store()
        self.assertEqual(reopened.get(stored["id"])["content"], "Persistent value")

    def test_namespaces_are_isolated(self):
        self.memory.remember("Only project A")
        other = self.open_store("project-b")
        self.assertEqual(other.list(), [])

    def test_session_transcript_can_resume(self):
        session_id = self.memory.create_session("expert", title="Feature work")
        self.memory.add_turn(session_id, "user", "Build the API")
        self.memory.add_turn(session_id, "assistant", "The API is ready")
        self.memory.checkpoint(session_id, "API implementation completed")

        reopened = self.open_store()
        context = reopened.session_context(session_id)
        self.assertIn("API implementation completed", context)
        self.assertIn("Build the API", context)
        self.assertIn("The API is ready", context)

    def test_memory_tool_registry_is_complete(self):
        self.assertEqual(
            {tool.name for tool in self.memory.definitions},
            {"remember", "recall", "list_memories", "forget", "list_sessions"},
        )
    def test_priority_memories_and_turns(self):
        # 1. Test has_turns
        session_id = self.memory.create_session("expert")
        self.assertFalse(self.memory.has_turns(session_id))
        self.memory.add_turn(session_id, "user", "hi")
        self.assertTrue(self.memory.has_turns(session_id))

        # 2. Test get_priority_memories
        self.memory.remember("Low priority memory", importance=0.5)
        high1 = self.memory.remember("High priority memory 1", importance=0.9)
        high2 = self.memory.remember("High priority memory 2", importance=0.95)
        
        priority = self.memory.get_priority_memories(limit=10, min_importance=0.9)
        self.assertEqual(len(priority), 2)
        # Verify ordering is updated_at DESC (last inserted first)
        self.assertEqual(priority[0]["id"], high2["id"])
        self.assertEqual(priority[1]["id"], high1["id"])

    def test_client_memory_context_priority_load(self):
        from deepwrap.client import Client

        self.memory.remember("Low priority", importance=0.5)
        self.memory.remember("High priority 1", importance=0.9)
        self.memory.remember("High priority 2", importance=0.95)

        with Client(
            api_key="test-key",
            memory_path=self.path,
            memory_namespace="project-a",
        ) as client:
            session_id = client.memory.create_session("expert")

            # The first context load of a session carries the priority memories.
            context = client.memory_context("query", session_id)
            self.assertIn("[PRIORITY MEMORIES]", context)
            self.assertIn("High priority 1", context)
            self.assertIn("High priority 2", context)
            self.assertNotIn("Low priority", context)

            # Later loads of the same session must not repeat them.
            repeated = client.memory_context("query", session_id)
            self.assertNotIn("[PRIORITY MEMORIES]", repeated)


if __name__ == "__main__":
    unittest.main()
