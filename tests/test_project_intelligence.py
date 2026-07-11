import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from deepwrap.project_intelligence import ProjectIntelligence


class ProjectIntelligenceTests(unittest.TestCase):
    def test_indexes_symbols_imports_references_and_changes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "app.py"
            source.write_text(
                "import json\n\nclass Service:\n    def run(self):\n        return helper()\n\ndef helper():\n    return json.dumps({})\n"
            )
            graph = ProjectIntelligence(root, root / "index.json")
            first = graph.index_project()
            second = graph.index_project()

            self.assertEqual(first["changed"], 1)
            self.assertEqual(second["changed"], 0)
            self.assertEqual(graph.find_symbol("Service")[0]["line"], 3)
            self.assertEqual(graph.references("helper")[0]["path"], "app.py")
            self.assertIn("json", graph.overview()["imports"])

    def test_removes_deleted_files_from_index(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "old.py"
            source.write_text("value = 1\n")
            graph = ProjectIntelligence(root, root / "index.json")
            graph.index_project()
            source.unlink()
            result = graph.index_project()
            self.assertEqual(result["removed"], ["old.py"])


if __name__ == "__main__":
    unittest.main()
