"""Offline tests for the Skill registration boundary."""

import tempfile
import unittest
from pathlib import Path
import json

import register_skills as registry


class RegistryTests(unittest.TestCase):
    def test_ensure_triggers_adds_manager_compatible_empty_list(self):
        content = "---\nname: fix-example\ndescription: Use when an example fails.\n---\n# Example\n"
        normalized = registry.ensure_triggers(content, [])
        self.assertIn("triggers: []", normalized)
        self.assertEqual(normalized.count("---"), 2)

    def test_ensure_triggers_preserves_existing_frontmatter(self):
        content = "---\nname: fix-example\ndescription: Use when an example fails.\ntriggers:\n  - \"ERR42\"\n---\n# Example\n"
        self.assertEqual(registry.ensure_triggers(content, ["other"]), content)

    def test_source_index_path_uses_logical_primary_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "C-skill-index.jsonl").write_text("{}\n", encoding="utf-8")
            self.assertEqual(registry.source_index_path(root, "C"), root / "C-skill-index.jsonl")

    def test_build_corpus_matches_current_manager_contract_for_35_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            rows = []
            for index in range(35):
                name = f"fix-example-{index}"
                path = source / "skills" / name / "SKILL.md"
                path.parent.mkdir(parents=True)
                path.write_text(
                    f"---\nname: {name}\ndescription: Use when example {index} fails.\n---\n# Example {index}\n",
                    encoding="utf-8")
                rows.append({"name": name, "group_id": f"native-code-{index}",
                             "error_key": f"example:E{index}", "model": "fixture-model",
                             "status": "candidate_needs_review", "markdown_path": str(path),
                             "source_files": [{"session_id": f"session-{index}"}]})
            (source / "C-skill-index.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            manager_config = (Path(__file__).resolve().parents[2] /
                              "skill-management" / "skill-management-system" / "config.json")
            manager_corpus, _ = registry.load_manager_modules(manager_config)
            _, index_path, skills = registry.build_corpus(source, rows, root / "batch", [], manager_corpus)
            self.assertEqual(len(skills), 35)
            self.assertEqual(len(index_path.read_text(encoding="utf-8").splitlines()), 35)
            self.assertEqual(skills[0].triggers, ())


if __name__ == "__main__":
    unittest.main()
