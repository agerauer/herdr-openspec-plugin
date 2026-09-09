import tempfile
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from sidebar import (
    Change,
    configured_project,
    delta_counts,
    discover_changes,
    find_project,
    format_change_row,
    format_delta_summary,
    parse_metadata,
)
from scripts.open_sidebar import plugin_pane, project_token, split_path


class SidebarModelTests(unittest.TestCase):
    def test_finds_project_from_nested_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "openspec" / "changes").mkdir(parents=True)
            nested = root / "src" / "feature"
            nested.mkdir(parents=True)
            self.assertEqual(find_project(nested), root.resolve())

    def test_uses_project_from_environment_not_process_cwd(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "openspec" / "changes").mkdir(parents=True)
            nested = root / "packages" / "api"
            nested.mkdir(parents=True)
            with patch.dict(os.environ, {"OPENSPEC_PROJECT": str(nested)}):
                self.assertEqual(configured_project(), root.resolve())

    def test_parses_change_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / ".openspec.yaml"
            path.write_text(
                "schema: spec-driven\ngoal: Add safer sessions\nskip_specs: false\n"
                "affected_areas:\n  - auth\n  - api\n",
                encoding="utf-8",
            )
            metadata = parse_metadata(path)
            self.assertEqual(metadata["goal"], "Add safer sessions")
            self.assertEqual(metadata["affected_areas"], ["auth", "api"])
            self.assertFalse(metadata["skip_specs"])

    def test_counts_deltas(self):
        content = """## ADDED Requirements
### Requirement: Login
### Requirement: Logout
## REMOVED Requirements
### Requirement: Password hint
"""
        self.assertEqual(delta_counts([content]), {"ADDED": 2, "REMOVED": 1})

    def test_formats_populated_and_empty_task_counts(self):
        populated = Change("add-login", Path("/tmp/add-login"), tasks_done=3, tasks_total=5)
        empty = Change("add-logout", Path("/tmp/add-logout"))

        populated_row = format_change_row(populated, 24)
        empty_row = format_change_row(empty, 24)

        self.assertEqual(len(populated_row), 24)
        self.assertTrue(populated_row.endswith("3/5"))
        self.assertIn("add-login", populated_row)
        self.assertTrue(empty_row.endswith("0/0"))

    def test_truncates_name_before_task_count_at_supported_widths(self):
        change = Change(
            "a-very-long-change-name",
            Path("/tmp/a-very-long-change-name"),
            tasks_done=12,
            tasks_total=123,
        )

        normal_row = format_change_row(change, 24, selected=True)
        minimum_row = format_change_row(change, 16, selected=True)

        self.assertEqual(len(normal_row), 24)
        self.assertEqual(len(minimum_row), 16)
        self.assertTrue(normal_row.startswith("› "))
        self.assertIn("…", minimum_row)
        self.assertTrue(normal_row.endswith("12/123"))
        self.assertTrue(minimum_row.endswith("12/123"))

    def test_rows_keep_counts_associated_with_their_changes(self):
        changes = [
            Change("add-login", Path("/tmp/add-login"), tasks_done=1, tasks_total=4),
            Change("add-logout", Path("/tmp/add-logout"), tasks_done=2, tasks_total=2),
        ]

        rows = [format_change_row(change, 24, index == 1) for index, change in enumerate(changes)]

        self.assertIn("add-login", rows[0])
        self.assertTrue(rows[0].endswith("1/4"))
        self.assertIn("add-logout", rows[1])
        self.assertTrue(rows[1].startswith("› "))
        self.assertTrue(rows[1].endswith("2/2"))

    def test_delta_summary_does_not_include_task_progress(self):
        change = Change(
            "add-login",
            Path("/tmp/add-login"),
            deltas={"ADDED": 2, "REMOVED": 1},
            tasks_done=3,
            tasks_total=5,
        )

        self.assertEqual(format_delta_summary(change), "+2  −1")

    def test_discovers_artifacts_tasks_and_deltas(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            change = root / "openspec" / "changes" / "add-login"
            spec = change / "specs" / "auth" / "spec.md"
            spec.parent.mkdir(parents=True)
            (change / ".openspec.yaml").write_text(
                "schema: spec-driven\ngoal: Add login\n", encoding="utf-8"
            )
            (change / "proposal.md").write_text("# Proposal\nLogin safely.\n", encoding="utf-8")
            spec.write_text(
                "## ADDED Requirements\n### Requirement: Login\n#### Scenario: Success\n",
                encoding="utf-8",
            )
            (change / "tasks.md").write_text("- [x] Model\n- [ ] UI\n", encoding="utf-8")
            found = discover_changes(root)
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].tasks_done, 1)
            self.assertEqual(found[0].tasks_total, 2)
            self.assertEqual(found[0].deltas, {"ADDED": 1})
            self.assertEqual(found[0].missing_required, 0)

    def test_finds_sidebar_identity_in_pane_list(self):
        project = Path("/tmp/example-project")
        response = {
            "result": {
                "panes": [
                    {"pane_id": "w1:p1", "workspace_id": "w1"},
                    {
                        "pane_id": "w1:p2",
                        "workspace_id": "w1",
                        "cwd": "/a/separate/plugin/checkout",
                        "tokens": {"openspec_review": project_token(project)},
                    },
                ]
            }
        }
        self.assertEqual(plugin_pane(response, "w1", project), "w1:p2")

    def test_finds_nested_layout_split_path(self):
        layout = {
            "type": "split",
            "first": {"type": "pane", "pane_id": "w1:p1"},
            "second": {
                "type": "split",
                "first": {"type": "pane", "pane_id": "w1:p2"},
                "second": {"type": "pane", "pane_id": "w1:p3"},
            },
        }
        self.assertEqual(split_path(layout, "w1:p1"), ([], False))
        self.assertEqual(split_path(layout, "w1:p2"), ([True], False))
        self.assertEqual(split_path(layout, "w1:p3"), ([True], True))


if __name__ == "__main__":
    unittest.main()
