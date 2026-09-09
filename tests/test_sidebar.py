import tempfile
import os
import curses
import subprocess
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from sidebar import (
    Artifact,
    Change,
    GitBase,
    HitTarget,
    Sidebar,
    WorktreeSnapshot,
    artifact_index_by_key,
    calculate_main_layout,
    change_name_affinity,
    change_sort_key,
    clamp_document_offset,
    clipped_hit_target,
    configured_project,
    collect_worktree_snapshot,
    delta_counts,
    discover_changes,
    discover_openspec_projects,
    display_change_name,
    find_project,
    format_change_row,
    format_delta_summary,
    hit_test,
    mouse_bits,
    mouse_wheel_direction,
    map_change_activity,
    parse_metadata,
    parse_commit_activity,
    paths_by_change,
    resolve_git_base,
    resolve_search_root,
    run_git,
    sort_changes,
    visible_footer_segments,
    wrap_document,
)
from scripts.open_sidebar import openspec_project, plugin_pane, project_token, split_path


class SidebarModelTests(unittest.TestCase):
    def test_change_affinity_covers_exact_containment_and_no_match(self):
        self.assertEqual(
            change_name_affinity("add-login", "feature/add-login", "other-worktree"),
            0,
        )
        self.assertEqual(
            change_name_affinity(
                "add-login",
                "feature/customer-add-login-preview",
                "other-worktree",
            ),
            1,
        )
        self.assertEqual(
            change_name_affinity("add-login", "feature/add-logout", "other-worktree"),
            2,
        )

    def test_touched_changes_rank_by_affinity_recency_and_name_before_untouched(self):
        snapshot = WorktreeSnapshot(
            "refs/heads/main",
            "base",
            "head",
            "feature/exact-change",
            "workspace-contained-change-preview",
            (),
            (),
        )
        changes = [
            Change("aaa-untouched", Path("/tmp/aaa")),
            Change("z-old", Path("/tmp/old"), worktree_touched=True, worktree_activity=10),
            Change("a-recent", Path("/tmp/recent"), worktree_touched=True, worktree_activity=20),
            Change(
                "contained-change",
                Path("/tmp/contained"),
                worktree_touched=True,
                worktree_activity=1,
            ),
            Change(
                "exact-change",
                Path("/tmp/exact"),
                worktree_touched=True,
                worktree_activity=1,
            ),
            Change("a-old", Path("/tmp/a-old"), worktree_touched=True, worktree_activity=10),
        ]

        ranked = sort_changes(changes, snapshot)

        self.assertEqual(
            [change.name for change in ranked],
            [
                "exact-change",
                "contained-change",
                "a-recent",
                "a-old",
                "z-old",
                "aaa-untouched",
            ],
        )
        self.assertLess(change_sort_key(ranked[0], snapshot), change_sort_key(ranked[-1], snapshot))

    @staticmethod
    def create_active_changes(root, *names):
        for name in names:
            directory = root / "openspec" / "changes" / name
            directory.mkdir(parents=True)
            (directory / "proposal.md").write_text(f"# {name}\n", encoding="utf-8")

    @staticmethod
    def snapshot_for(*names, branch="feature/unmatched", activity=1):
        paths = tuple(f"openspec/changes/{name}/proposal.md" for name in names)
        return WorktreeSnapshot(
            "refs/heads/main",
            "base",
            "head",
            branch,
            "worktree",
            paths,
            tuple((name, activity + index) for index, name in enumerate(names)),
        )

    def test_initial_load_selects_highest_ranked_touched_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.create_active_changes(root, "alpha", "feature-change", "zeta")
            snapshot = self.snapshot_for(
                "alpha", "feature-change", branch="feature/feature-change"
            )

            with patch("sidebar.collect_worktree_snapshot", return_value=snapshot):
                sidebar = Sidebar(Mock(), root)

            self.assertEqual([change.name for change in sidebar.changes], ["feature-change", "alpha", "zeta"])
            self.assertEqual(sidebar.change.name, "feature-change")

    def test_refresh_reorders_changes_but_preserves_existing_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.create_active_changes(root, "alpha", "beta", "gamma")
            first = self.snapshot_for("beta", branch="feature/beta")
            second = self.snapshot_for("gamma", branch="feature/gamma", activity=10)

            with patch("sidebar.collect_worktree_snapshot", side_effect=[first, second]):
                sidebar = Sidebar(Mock(), root)
                sidebar.change_index = next(
                    index for index, change in enumerate(sidebar.changes) if change.name == "alpha"
                )
                sidebar.reload()

            self.assertEqual(sidebar.changes[0].name, "gamma")
            self.assertEqual(sidebar.change.name, "alpha")

    def test_refresh_selects_new_first_change_when_selected_change_was_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.create_active_changes(root, "alpha", "beta")
            first = self.snapshot_for("beta", branch="feature/beta")
            second = self.snapshot_for("alpha", branch="feature/alpha")

            with patch("sidebar.collect_worktree_snapshot", side_effect=[first, second]):
                sidebar = Sidebar(Mock(), root)
                selected = root / "openspec/changes/beta/proposal.md"
                selected.unlink()
                selected.parent.rmdir()
                sidebar.reload()

            self.assertEqual(sidebar.change.name, "alpha")

    def test_git_unavailable_uses_normal_alphabetical_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.create_active_changes(root, "zeta", "alpha")

            with patch("sidebar.collect_worktree_snapshot", return_value=None):
                sidebar = Sidebar(Mock(), root)

            self.assertEqual([change.name for change in sidebar.changes], ["alpha", "zeta"])
            self.assertEqual(sidebar.change.name, "alpha")
            self.assertFalse(any(change.worktree_touched for change in sidebar.changes))
    @staticmethod
    def git(root, *args):
        return subprocess.run(
            ["git", "-C", str(root), *args],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()

    def test_snapshot_collects_all_change_sources_and_excludes_other_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.git(root, "init", "-b", "main")
            self.git(root, "config", "user.email", "test@example.com")
            self.git(root, "config", "user.name", "Test User")
            baseline = {
                "openspec/changes/unstaged-change/proposal.md": "old unstaged",
                "openspec/changes/staged-change/proposal.md": "old staged",
                "openspec/changes/untouched-change/proposal.md": "untouched",
                "openspec/changes/archive/old-change/proposal.md": "archived",
                "README.md": "baseline",
            }
            for relative, content in baseline.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            self.git(root, "add", ".")
            self.git(root, "commit", "-m", "baseline")
            self.git(root, "checkout", "-b", "feature/committed-change")

            committed = root / "openspec/changes/committed-change/proposal.md"
            committed.parent.mkdir(parents=True)
            committed.write_text("committed", encoding="utf-8")
            self.git(root, "add", str(committed.relative_to(root)))
            self.git(root, "commit", "-m", "add committed change")

            (root / "openspec/changes/staged-change/proposal.md").write_text(
                "new staged", encoding="utf-8"
            )
            self.git(root, "add", "openspec/changes/staged-change/proposal.md")
            (root / "openspec/changes/unstaged-change/proposal.md").write_text(
                "new unstaged", encoding="utf-8"
            )
            untracked = root / "openspec/changes/untracked-change/proposal.md"
            untracked.parent.mkdir(parents=True)
            untracked.write_text("untracked", encoding="utf-8")
            (root / "openspec/changes/archive/old-change/proposal.md").write_text(
                "changed archive", encoding="utf-8"
            )
            (root / "README.md").write_text("unrelated", encoding="utf-8")

            snapshot = collect_worktree_snapshot(root)

            self.assertIsNotNone(snapshot)
            self.assertEqual(
                set(snapshot.changed_paths),
                {
                    "openspec/changes/committed-change/proposal.md",
                    "openspec/changes/staged-change/proposal.md",
                    "openspec/changes/unstaged-change/proposal.md",
                    "openspec/changes/untracked-change/proposal.md",
                },
            )
            self.assertEqual(snapshot.branch, "feature/committed-change")

    def test_groups_nested_unique_paths_for_existing_active_changes(self):
        grouped = paths_by_change(
            [
                "openspec/changes/add-login/proposal.md",
                "openspec/changes/add-login/specs/auth/spec.md",
                "openspec/changes/add-login/specs/auth/spec.md",
                "openspec/changes/deleted-change/proposal.md",
                "openspec/changes/archive/old/proposal.md",
            ],
            {"add-login"},
        )

        self.assertEqual(
            grouped,
            {
                "add-login": (
                    "openspec/changes/add-login/proposal.md",
                    "openspec/changes/add-login/specs/auth/spec.md",
                )
            },
        )

    def test_maps_latest_file_and_commit_activity_deterministically(self):
        paths = (
            "openspec/changes/add-login/proposal.md",
            "openspec/changes/add-login/specs/auth/spec.md",
            "openspec/changes/add-logout/proposal.md",
        )
        commit_activity = parse_commit_activity(
            "20\n\nopenspec/changes/add-login/proposal.md\n"
            "10\n\nopenspec/changes/add-logout/proposal.md\n"
        )

        activity = map_change_activity(
            paths,
            {
                paths[0]: 15_000_000_000,
                paths[1]: 25_000_000_000,
                # The missing add-logout file deliberately has no filesystem timestamp.
            },
            commit_activity,
        )

        self.assertEqual(
            activity,
            (("add-login", 25_000_000_000), ("add-logout", 10_000_000_000)),
        )
    def test_resolves_remote_default_branch_and_merge_base(self):
        calls = []

        def runner(project, args):
            calls.append(args)
            values = {
                ("rev-parse", "--is-inside-work-tree"): "true",
                ("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"):
                    "refs/remotes/origin/trunk",
                ("rev-parse", "--verify", "--quiet", "refs/remotes/origin/trunk^{commit}"):
                    "default-head",
                ("merge-base", "HEAD", "refs/remotes/origin/trunk"): "common-base",
            }
            return values.get(tuple(args))

        self.assertEqual(
            resolve_git_base(Path("/project"), runner),
            GitBase("refs/remotes/origin/trunk", "common-base"),
        )
        self.assertNotIn(
            ["rev-parse", "--verify", "--quiet", "refs/heads/main^{commit}"],
            calls,
        )

    def test_resolves_main_then_master_fallbacks(self):
        def fallback(existing_ref):
            def runner(project, args):
                if args == ["rev-parse", "--is-inside-work-tree"]:
                    return "true"
                if args == [
                    "rev-parse", "--verify", "--quiet", f"{existing_ref}^{{commit}}"
                ]:
                    return "head"
                if args == ["merge-base", "HEAD", existing_ref]:
                    return "base"
                return None

            return runner

        self.assertEqual(
            resolve_git_base(Path("/project"), fallback("refs/heads/main")),
            GitBase("refs/heads/main", "base"),
        )
        self.assertEqual(
            resolve_git_base(Path("/project"), fallback("refs/heads/master")),
            GitBase("refs/heads/master", "base"),
        )

    def test_git_base_resolution_falls_back_for_non_repository_or_command_failure(self):
        self.assertIsNone(resolve_git_base(Path("/project"), lambda project, args: None))
        self.assertIsNone(
            resolve_git_base(
                Path("/project"),
                lambda project, args: "true"
                if args == ["rev-parse", "--is-inside-work-tree"]
                else None,
            )
        )

    def test_bounded_git_query_returns_none_on_failure_and_timeout(self):
        failed = Mock(returncode=2, stdout="", stderr="failure")
        with patch("sidebar.subprocess.run", return_value=failed) as invoked:
            self.assertIsNone(run_git(Path("/project"), ["status"]))
            self.assertEqual(invoked.call_args.kwargs["timeout"], 1.5)

        with patch(
            "sidebar.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["git"], 1.5),
        ):
            self.assertIsNone(run_git(Path("/project"), ["status"]))

    def make_sidebar(self, artifacts=None):
        class Screen:
            def __init__(self):
                self.writes = []

            @staticmethod
            def getmaxyx():
                return (30, 60)

            def addnstr(self, y, x, text, available, style):
                self.writes.append((y, x, text[:available], style))

            def erase(self):
                self.writes.clear()

            def refresh(self):
                return None

        sidebar = Sidebar.__new__(Sidebar)
        sidebar.screen = Screen()
        sidebar.project = Path("/tmp/project")
        sidebar.openspec_projects = [sidebar.project]
        sidebar.changes = [
            Change("first", Path("/tmp/first"), artifacts=list(artifacts or [])),
            Change("second", Path("/tmp/second"), artifacts=[]),
        ]
        sidebar.change_index = 0
        sidebar.artifact_index = 0
        sidebar.focus = "changes"
        sidebar.viewer = None
        sidebar.viewer_offset = 0
        sidebar.hit_targets = []
        sidebar.message = ""
        sidebar.message_until = 0.0
        return sidebar

    @staticmethod
    def left_click():
        return getattr(curses, "BUTTON1_CLICKED", 0) or getattr(curses, "BUTTON1_PRESSED", 0)

    def test_hit_targets_match_inside_and_miss_outside(self):
        target = clipped_hit_target(4, 1, 5, 20, 30, 40, "select_change", 3)

        self.assertIsNotNone(target)
        self.assertIs(hit_test([target], 4, 10), target)
        self.assertIsNone(hit_test([target], 3, 10))
        self.assertIsNone(hit_test([target], 5, 10))

    def test_adjacent_hit_target_boundaries_do_not_overlap(self):
        first = clipped_hit_target(10, 1, 11, 8, 30, 40, "back")
        second = clipped_hit_target(10, 8, 11, 18, 30, 40, "edit")

        self.assertIs(hit_test([first, second], 10, 7), first)
        self.assertIs(hit_test([first, second], 10, 8), second)

    def test_hit_targets_are_clipped_to_drawable_pane_width(self):
        target = clipped_hit_target(2, 8, 3, 30, 10, 12, "close")
        omitted = clipped_hit_target(2, 12, 3, 20, 10, 12, "hidden")

        self.assertEqual((target.left, target.right), (8, 11))
        self.assertIs(hit_test([target], 2, 10), target)
        self.assertIsNone(hit_test([target], 2, 11))
        self.assertIsNone(omitted)

    def test_left_click_selects_a_change_row(self):
        sidebar = self.make_sidebar()
        sidebar.hit_targets = [HitTarget(4, 1, 5, 30, "select_change", 1)]

        sidebar.handle_mouse(5, 4, self.left_click())

        self.assertEqual(sidebar.change_index, 1)
        self.assertEqual(sidebar.focus, "changes")

    def test_left_click_opens_an_existing_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "proposal.md"
            path.write_text("# Proposal", encoding="utf-8")
            artifact = Artifact("proposal", "Proposal", path, content="# Proposal")
            sidebar = self.make_sidebar([artifact])
            sidebar.hit_targets = [HitTarget(10, 2, 11, 20, "open_artifact", 0)]

            sidebar.handle_mouse(5, 10, self.left_click())

            self.assertIs(sidebar.viewer, artifact)
            self.assertEqual(sidebar.focus, "artifacts")

    def test_left_click_reports_a_missing_artifact(self):
        artifact = Artifact("tasks", "Tasks", None)
        sidebar = self.make_sidebar([artifact])
        sidebar.hit_targets = [HitTarget(10, 2, 11, 20, "open_artifact", 0)]

        sidebar.handle_mouse(5, 10, self.left_click())

        self.assertIsNone(sidebar.viewer)
        self.assertEqual(sidebar.message, "Artifact does not exist yet")
        self.assertEqual(sidebar.artifact_index, 0)

    def test_viewer_header_back_label_is_clickable_and_clipped(self):
        artifact = Artifact(
            "proposal",
            "Proposal",
            Path("/tmp/proposal.md"),
            content="\n".join(f"line {index}" for index in range(100)),
        )
        sidebar = self.make_sidebar([artifact])
        sidebar.viewer = artifact

        with patch("sidebar.curses.color_pair", return_value=0):
            sidebar.draw_viewer()

        target = next(target for target in sidebar.hit_targets if target.action == "back")
        self.assertTrue(target.contains(0, 1))
        self.assertFalse(target.contains(0, target.right))

        sidebar.handle_mouse(target.left, target.top, self.left_click())
        self.assertIsNone(sidebar.viewer)

    def test_click_elsewhere_in_viewer_header_preserves_document(self):
        artifact = Artifact(
            "proposal",
            "Proposal",
            Path("/tmp/proposal.md"),
            content="\n".join(f"line {index}" for index in range(100)),
        )
        sidebar = self.make_sidebar([artifact])
        sidebar.viewer = artifact
        sidebar.viewer_offset = 3

        with patch("sidebar.curses.color_pair", return_value=0):
            sidebar.draw_viewer()

        sidebar.handle_mouse(40, 0, self.left_click())

        self.assertIs(sidebar.viewer, artifact)
        self.assertEqual(sidebar.viewer_offset, 3)

    def test_click_outside_targets_preserves_view_state(self):
        sidebar = self.make_sidebar()
        sidebar.hit_targets = [HitTarget(4, 1, 5, 30, "select_change", 1)]
        before = (sidebar.change_index, sidebar.artifact_index, sidebar.focus, sidebar.viewer)

        sidebar.handle_mouse(40, 20, self.left_click())

        self.assertEqual(
            (sidebar.change_index, sidebar.artifact_index, sidebar.focus, sidebar.viewer),
            before,
        )

    def test_all_main_footer_hints_dispatch_their_keyboard_actions(self):
        sidebar = self.make_sidebar([Artifact("proposal", "Proposal", None)])
        sidebar.validate = unittest.mock.Mock()

        self.assertTrue(sidebar.dispatch_action("open"))
        self.assertEqual(sidebar.focus, "artifacts")
        self.assertTrue(sidebar.dispatch_action("validate"))
        sidebar.validate.assert_called_once_with()
        self.assertFalse(sidebar.dispatch_action("close"))

    def test_all_viewer_footer_hints_dispatch_their_keyboard_actions(self):
        sidebar = self.make_sidebar()
        artifact = Artifact("proposal", "Proposal", Path("/tmp/proposal.md"))
        sidebar.viewer = artifact
        sidebar.edit = unittest.mock.Mock()

        self.assertTrue(sidebar.dispatch_action("edit"))
        sidebar.edit.assert_called_once_with()
        self.assertTrue(sidebar.dispatch_action("back"))
        self.assertIsNone(sidebar.viewer)
        self.assertFalse(sidebar.dispatch_action("close"))

    def test_edit_prefers_code_and_restores_sidebar(self):
        artifact = Artifact("proposal", "Proposal", Path("/tmp/proposal.md"))
        sidebar = self.make_sidebar([artifact])
        sidebar.viewer = artifact
        sidebar.screen.refresh = Mock()
        sidebar.reload = Mock()

        with (
            patch("sidebar.shutil.which", return_value="/usr/local/bin/code") as which,
            patch("sidebar.curses.endwin") as endwin,
            patch("sidebar.subprocess.run") as run,
        ):
            sidebar.edit()

        which.assert_called_once_with("code")
        endwin.assert_called_once_with()
        run.assert_called_once_with(
            ["/usr/local/bin/code", "/tmp/proposal.md"],
            cwd=sidebar.project,
            check=False,
        )
        sidebar.screen.refresh.assert_called_once_with()
        sidebar.reload.assert_called_once_with(force=True)

    def test_edit_falls_back_to_vi_when_code_is_unavailable(self):
        artifact = Artifact("tasks", "Tasks", Path("/tmp/tasks.md"))
        sidebar = self.make_sidebar([artifact])
        sidebar.viewer = artifact
        sidebar.screen.refresh = Mock()
        sidebar.reload = Mock()

        with (
            patch("sidebar.shutil.which", return_value=None),
            patch("sidebar.curses.endwin"),
            patch("sidebar.subprocess.run") as run,
        ):
            sidebar.edit()

        run.assert_called_once_with(
            ["vi", "/tmp/tasks.md"],
            cwd=sidebar.project,
            check=False,
        )
        sidebar.screen.refresh.assert_called_once_with()
        sidebar.reload.assert_called_once_with(force=True)

    def test_enter_then_escape_returns_focus_to_selected_change(self):
        sidebar = self.make_sidebar([Artifact("proposal", "Proposal", None)])

        sidebar.handle(curses.KEY_ENTER)
        self.assertEqual(sidebar.focus, "artifacts")
        sidebar.handle(27)

        self.assertEqual(sidebar.focus, "changes")
        self.assertEqual(sidebar.change_index, 0)

        sidebar.handle(27)
        self.assertEqual(sidebar.focus, "changes")
        self.assertEqual(sidebar.change_index, 0)

    def test_escape_from_viewer_retains_selected_artifact(self):
        artifacts = [
            Artifact("proposal", "Proposal", Path("/tmp/proposal.md")),
            Artifact("tasks", "Tasks", Path("/tmp/tasks.md")),
        ]
        sidebar = self.make_sidebar(artifacts)
        sidebar.focus = "artifacts"
        sidebar.artifact_index = 1
        sidebar.viewer = artifacts[1]

        sidebar.handle(27)

        self.assertIsNone(sidebar.viewer)
        self.assertEqual(sidebar.focus, "artifacts")
        self.assertEqual(sidebar.artifact_index, 1)

    def test_core_shortcuts_open_existing_artifacts_from_change_focus(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifacts = []
            for key, title in (("proposal", "Proposal"), ("design", "Design"), ("tasks", "Tasks")):
                path = root / f"{key}.md"
                path.write_text(title, encoding="utf-8")
                artifacts.append(Artifact(key, title, path))
            sidebar = self.make_sidebar(artifacts)

            for key, expected_index in ((ord("p"), 0), (ord("d"), 1), (ord("t"), 2)):
                sidebar.viewer = None
                sidebar.focus = "changes"
                sidebar.handle(key)
                self.assertEqual(sidebar.artifact_index, expected_index)
                self.assertIs(sidebar.viewer, artifacts[expected_index])

    def test_core_shortcut_selects_missing_artifact_and_reports_it(self):
        artifacts = [
            Artifact("proposal", "Proposal", None),
            Artifact("design", "Design", None, required=False),
            Artifact("tasks", "Tasks", None),
        ]
        sidebar = self.make_sidebar(artifacts)

        sidebar.handle(ord("d"))

        self.assertEqual(sidebar.artifact_index, 1)
        self.assertIsNone(sidebar.viewer)
        self.assertEqual(sidebar.message, "Artifact does not exist yet")

    def test_core_shortcuts_are_ignored_outside_change_focus(self):
        artifacts = [
            Artifact("proposal", "Proposal", Path("/tmp/proposal.md")),
            Artifact("design", "Design", Path("/tmp/design.md")),
        ]
        sidebar = self.make_sidebar(artifacts)
        sidebar.focus = "artifacts"
        sidebar.artifact_index = 1

        sidebar.handle(ord("p"))
        self.assertEqual(sidebar.artifact_index, 1)
        self.assertIsNone(sidebar.viewer)

        sidebar.focus = "changes"
        sidebar.viewer = artifacts[1]
        sidebar.handle(ord("p"))
        self.assertEqual(sidebar.artifact_index, 1)
        self.assertIs(sidebar.viewer, artifacts[1])

    def test_footer_layout_omits_clipped_hints_and_their_targets(self):
        actions = [("↵ open", "open"), ("v validate", "validate"), ("q close", "close")]

        wide = visible_footer_segments(40, actions)
        narrow = visible_footer_segments(18, actions)

        self.assertEqual([segment.action for segment in wide], ["open", "validate", "close"])
        self.assertEqual([segment.action for segment in narrow], ["open"])
        self.assertTrue(all(segment.right < 18 for segment in narrow))

    def test_each_rendered_footer_hint_is_mouse_clickable(self):
        sidebar = self.make_sidebar()
        actions = [("↵ open", "open"), ("v validate", "validate"), ("q close", "close")]
        sidebar.draw_footer(29, actions)
        sidebar.dispatch_action = Mock(return_value=True)

        for target in sidebar.hit_targets:
            sidebar.handle_mouse(target.left, target.top, self.left_click())

        self.assertEqual(
            [call.args[0] for call in sidebar.dispatch_action.call_args_list],
            ["open", "validate", "close"],
        )

    def test_artifact_heading_shows_total_without_changing_row_targets(self):
        artifacts = [
            Artifact("proposal", "Proposal", Path("/tmp/proposal.md")),
            Artifact("design", "Design", None, required=False),
            Artifact("tasks", "Tasks", None),
            Artifact("spec:one/spec.md", "Spec · one", Path("/tmp/spec.md")),
            Artifact("spec:two/spec.md", "Spec · two", Path("/tmp/spec-two.md")),
        ]
        sidebar = self.make_sidebar(artifacts)

        with patch("sidebar.curses.color_pair", return_value=0):
            sidebar.draw_main()

        self.assertTrue(
            any(text == "ARTIFACTS (5)" for _, _, text, _ in sidebar.screen.writes)
        )
        targets = [target for target in sidebar.hit_targets if target.action == "open_artifact"]
        self.assertEqual([target.index for target in targets], list(range(5)))

    def test_viewer_scrolls_by_one_line_and_one_visible_page(self):
        sidebar = self.make_sidebar()
        sidebar.viewer = Artifact(
            "proposal",
            "Proposal",
            Path("/tmp/proposal.md"),
            content="\n".join(f"line {index}" for index in range(100)),
        )

        sidebar.scroll_viewer_lines(1)
        self.assertEqual(sidebar.viewer_offset, 1)
        sidebar.scroll_viewer_pages(1)
        self.assertEqual(sidebar.viewer_offset, 26)
        sidebar.scroll_viewer_pages(-1)
        self.assertEqual(sidebar.viewer_offset, 1)

    def test_viewer_scroll_clamps_at_both_document_boundaries(self):
        self.assertEqual(clamp_document_offset(-10, 100, 25), 0)
        self.assertEqual(clamp_document_offset(500, 100, 25), 75)
        self.assertEqual(clamp_document_offset(10, 3, 25), 0)

        wrapped = wrap_document("one\ntwo\nthree", 40)
        self.assertEqual(wrapped, ["one", "two", "three"])

    def test_viewer_arrow_and_page_keys_use_distinct_scroll_paths(self):
        sidebar = self.make_sidebar()
        sidebar.viewer = Artifact("proposal", "Proposal", Path("/tmp/proposal.md"))
        sidebar.scroll_viewer_lines = Mock()
        sidebar.scroll_viewer_pages = Mock()

        sidebar.handle(curses.KEY_UP)
        sidebar.handle(curses.KEY_DOWN)
        sidebar.handle(curses.KEY_PPAGE)
        sidebar.handle(curses.KEY_NPAGE)

        self.assertEqual(
            [call.args[0] for call in sidebar.scroll_viewer_lines.call_args_list],
            [-1, 1],
        )
        self.assertEqual(
            [call.args[0] for call in sidebar.scroll_viewer_pages.call_args_list],
            [-1, 1],
        )

    def test_viewer_mouse_wheel_uses_one_line_scroll_path(self):
        sidebar = self.make_sidebar()
        sidebar.viewer = Artifact("proposal", "Proposal", Path("/tmp/proposal.md"))
        sidebar.scroll_viewer_lines = Mock()

        sidebar.handle_mouse(5, 5, mouse_bits("BUTTON4_PRESSED"))
        sidebar.handle_mouse(5, 5, 1 << 25)

        self.assertEqual(
            [call.args[0] for call in sidebar.scroll_viewer_lines.call_args_list],
            [-1, 1],
        )

    def test_mouse_wheel_direction_covers_exposed_and_raw_states(self):
        self.assertEqual(mouse_wheel_direction(mouse_bits("BUTTON4_PRESSED")), -1)
        self.assertEqual(mouse_wheel_direction(mouse_bits("BUTTON4_CLICKED")), -1)
        self.assertEqual(mouse_wheel_direction(mouse_bits("BUTTON4_RELEASED")), 1)
        self.assertEqual(mouse_wheel_direction(1 << 24), 1)
        self.assertEqual(mouse_wheel_direction(1 << 25), 1)
        self.assertEqual(mouse_wheel_direction(1 << 26), 1)
        self.assertEqual(
            mouse_wheel_direction(getattr(curses, "REPORT_MOUSE_POSITION", 0)),
            1,
        )

    def test_unrecognized_mouse_state_does_not_scroll_document(self):
        sidebar = self.make_sidebar()
        sidebar.viewer = Artifact("proposal", "Proposal", Path("/tmp/proposal.md"))
        sidebar.scroll_viewer_lines = Mock()

        sidebar.handle_mouse(5, 5, 0)

        self.assertEqual(mouse_wheel_direction(0), 0)
        sidebar.scroll_viewer_lines.assert_not_called()

    def test_layout_shows_fifteen_changes_in_a_tall_pane(self):
        layout = calculate_main_layout(40, 25, 12, 6, 0, 2)

        self.assertEqual(layout.changes.count, 15)
        self.assertEqual(layout.artifacts.count, 6)
        self.assertEqual(layout.goal_count, 2)
        self.assertLess(layout.artifact_row + layout.artifacts.count, layout.summary_row + 1)

    def test_layout_uses_surplus_height_for_more_than_four_artifacts(self):
        layout = calculate_main_layout(46, 25, 12, 12, 10, 2)

        self.assertEqual(layout.changes.count, 15)
        self.assertGreater(layout.artifacts.count, 4)
        self.assertLessEqual(layout.artifacts.start, 10)
        self.assertGreater(layout.artifacts.stop, 10)
        self.assertLessEqual(layout.artifact_row + layout.artifacts.count, layout.summary_row)

    def test_layout_reduces_change_rows_in_a_medium_pane(self):
        layout = calculate_main_layout(24, 25, 12, 6, 0, 2)

        self.assertGreater(layout.changes.count, 1)
        self.assertLess(layout.changes.count, 15)
        self.assertEqual(layout.artifacts.count, 4)
        self.assertLessEqual(layout.artifact_row + layout.artifacts.count, layout.summary_row)

    def test_layout_degrades_to_one_change_and_artifact_at_minimum_height(self):
        layout = calculate_main_layout(12, 25, 12, 6, 3, 2)

        self.assertEqual(layout.changes.count, 1)
        self.assertEqual(layout.artifacts.count, 1)
        self.assertEqual(layout.goal_count, 0)
        self.assertLess(layout.status_row, layout.artifact_header_row)
        self.assertLess(layout.artifact_row, layout.summary_row)

    def test_layout_keeps_change_selection_visible_across_the_list(self):
        beginning = calculate_main_layout(24, 25, 0, 6, 0, 2).changes
        middle = calculate_main_layout(24, 25, 12, 6, 0, 2).changes
        end = calculate_main_layout(24, 25, 24, 6, 0, 2).changes

        self.assertEqual(beginning.start, 0)
        self.assertLessEqual(middle.start, 12)
        self.assertGreater(middle.stop, 12)
        self.assertEqual(end.stop, 25)

    def test_layout_keeps_artifact_selection_visible_across_the_list(self):
        beginning = calculate_main_layout(30, 10, 0, 12, 0, 1).artifacts
        middle = calculate_main_layout(30, 10, 0, 12, 6, 1).artifacts
        end = calculate_main_layout(30, 10, 0, 12, 11, 1).artifacts

        self.assertEqual(beginning.start, 0)
        self.assertLessEqual(middle.start, 6)
        self.assertGreater(middle.stop, 6)
        self.assertEqual(end.stop, 12)

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

    def test_change_rows_show_independent_selection_and_worktree_markers(self):
        untouched = Change("untouched", Path("/tmp/untouched"))
        touched = Change("touched", Path("/tmp/touched"), worktree_touched=True)

        self.assertTrue(format_change_row(untouched, 24).startswith("   "))
        self.assertTrue(format_change_row(untouched, 24, selected=True).startswith("›  "))
        self.assertTrue(format_change_row(touched, 24).startswith(" ◆ "))
        self.assertTrue(format_change_row(touched, 24, selected=True).startswith("›◆ "))

    def test_touched_rows_preserve_task_count_at_long_and_minimum_widths(self):
        change = Change(
            "a-very-long-worktree-change",
            Path("/tmp/change"),
            tasks_done=12,
            tasks_total=123,
            worktree_touched=True,
        )

        normal = format_change_row(change, 24, selected=True)
        minimum = format_change_row(change, 8, selected=True)

        self.assertEqual(len(normal), 24)
        self.assertTrue(normal.startswith("›◆ "))
        self.assertIn("…", normal)
        self.assertTrue(normal.endswith("12/123"))
        self.assertEqual(minimum, "›◆12/123")

    def test_draw_main_accents_every_touched_row_and_preserves_selection_and_hits(self):
        sidebar = self.make_sidebar()
        sidebar.changes = [
            Change("first", Path("/tmp/first"), worktree_touched=True),
            Change("second", Path("/tmp/second"), worktree_touched=True),
            Change("third", Path("/tmp/third")),
        ]
        sidebar.change_index = 0
        accent = 1 << 22

        with patch("sidebar.curses.color_pair", side_effect=lambda pair: accent if pair == 2 else 0):
            sidebar.draw_main()

        change_writes = {
            y: (text, style)
            for y, x, text, style in sidebar.screen.writes
            if y in (4, 5, 6) and x == 1
        }
        self.assertTrue(change_writes[4][0].startswith("›◆ "))
        self.assertTrue(change_writes[4][1] & accent)
        self.assertTrue(change_writes[4][1] & curses.A_REVERSE)
        self.assertTrue(change_writes[5][0].startswith(" ◆ "))
        self.assertTrue(change_writes[5][1] & accent)
        self.assertFalse(change_writes[6][1] & accent)
        self.assertEqual(
            [
                target.index
                for target in sidebar.hit_targets
                if target.action == "select_change"
            ],
            [0, 1, 2],
        )

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
            second_spec = change / "specs" / "z-profile" / "spec.md"
            second_spec.parent.mkdir(parents=True)
            second_spec.write_text(
                "## MODIFIED Requirements\n### Requirement: Profile\n#### Scenario: Update\n",
                encoding="utf-8",
            )
            (change / "tasks.md").write_text("- [x] Model\n- [ ] UI\n", encoding="utf-8")
            found = discover_changes(root)
            self.assertEqual(len(found), 1)
            self.assertEqual(
                [artifact.key for artifact in found[0].artifacts],
                [
                    "proposal",
                    "design",
                    "tasks",
                    "spec:auth/spec.md",
                    "spec:z-profile/spec.md",
                ],
            )
            self.assertFalse(found[0].artifacts[1].exists)
            self.assertEqual(found[0].tasks_done, 1)
            self.assertEqual(found[0].tasks_total, 2)
            self.assertEqual(found[0].deltas, {"ADDED": 1, "MODIFIED": 1})
            self.assertEqual(found[0].missing_required, 0)

    def test_no_spec_placeholder_follows_core_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            change = root / "openspec" / "changes" / "missing-spec"
            change.mkdir(parents=True)

            found = discover_changes(root)

            self.assertEqual(
                [artifact.key for artifact in found[0].artifacts],
                ["proposal", "design", "tasks", "specs"],
            )

    def test_artifact_key_lookup_uses_model_order(self):
        artifacts = [
            Artifact("proposal", "Proposal", None),
            Artifact("design", "Design", None),
            Artifact("tasks", "Tasks", None),
        ]

        self.assertEqual(artifact_index_by_key(artifacts, "design"), 1)
        self.assertIsNone(artifact_index_by_key(artifacts, "missing"))

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


class NestedOpenspecDiscoveryTests(unittest.TestCase):
    @staticmethod
    def git(root, *args):
        return subprocess.run(
            ["git", "-C", str(root), *args],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()

    @staticmethod
    def write_change(project: Path, name: str, body: str = "") -> Path:
        directory = project / "openspec" / "changes" / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "proposal.md").write_text(
            body or f"# {name}\nGoal for {name}.\n",
            encoding="utf-8",
        )
        return directory

    def test_search_root_prefers_git_toplevel_from_nested_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.git(root, "init", "-b", "main")
            (root / "openspec" / "changes").mkdir(parents=True)
            nested = root / "nxt" / "src"
            nested.mkdir(parents=True)
            (root / "nxt" / "openspec" / "changes").mkdir(parents=True)

            self.assertEqual(resolve_search_root(nested), root.resolve())

    def test_search_root_without_git_uses_highest_openspec_ancestor(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "openspec" / "changes").mkdir(parents=True)
            nested = root / "nxt" / "src"
            nested.mkdir(parents=True)
            (root / "nxt" / "openspec" / "changes").mkdir(parents=True)

            self.assertEqual(resolve_search_root(nested), root.resolve())

    def test_search_root_without_openspec_ancestors_returns_start(self):
        with tempfile.TemporaryDirectory() as temporary:
            start = Path(temporary) / "workspace" / "src"
            start.mkdir(parents=True)

            self.assertEqual(resolve_search_root(start), start.resolve())

    def test_discovers_root_first_level_and_second_level_openspec_projects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "openspec" / "changes").mkdir(parents=True)
            (root / "nxt" / "openspec" / "changes").mkdir(parents=True)
            (root / "apps" / "nxt" / "openspec" / "changes").mkdir(parents=True)
            (root / "apps" / "nxt" / "web" / "openspec" / "changes").mkdir(parents=True)
            (root / "node_modules" / "openspec" / "changes").mkdir(parents=True)
            (root / ".hidden" / "openspec" / "changes").mkdir(parents=True)
            (root / "openspec" / "nested" / "openspec" / "changes").mkdir(parents=True)

            found = {path.relative_to(root).as_posix() for path in discover_openspec_projects(root)}

            self.assertEqual(found, {".", "nxt", "apps/nxt"})

    def test_discovers_subdirectory_only_openspec_projects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "nxt" / "openspec" / "changes").mkdir(parents=True)
            (root / "web" / "openspec" / "changes").mkdir(parents=True)

            found = {path.relative_to(root).as_posix() for path in discover_openspec_projects(root)}

            self.assertEqual(found, {"nxt", "web"})

    def test_discovery_does_not_follow_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            target = root / "real" / "openspec" / "changes"
            target.mkdir(parents=True)
            linked = root / "linked"
            linked.symlink_to(root / "real")

            found = {path.relative_to(root).as_posix() for path in discover_openspec_projects(root)}

            self.assertEqual(found, {"real"})

    def test_open_sidebar_uses_git_toplevel_from_nested_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.git(root, "init", "-b", "main")
            (root / "openspec" / "changes").mkdir(parents=True)
            nested = root / "nxt" / "src"
            nested.mkdir(parents=True)
            (root / "nxt" / "openspec" / "changes").mkdir(parents=True)

            self.assertEqual(openspec_project(nested), root.resolve())

    def test_display_names_prefix_nested_projects_with_middle_dot(self):
        root = Path("/workspace")
        self.assertEqual(display_change_name(root, root, "add-login"), "add-login")
        self.assertEqual(
            display_change_name(root, root / "nxt", "add-login"),
            "nxt · add-login",
        )
        self.assertEqual(
            display_change_name(root, root / "apps" / "nxt", "add-login"),
            "apps · nxt · add-login",
        )

    def test_merges_prefixed_changes_and_omits_too_deep_trees(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_change(root, "add-login")
            self.write_change(root / "nxt", "add-login")
            self.write_change(root / "nxt", "add-api")
            self.write_change(root / "apps" / "nxt", "add-login")
            self.write_change(root / "apps" / "nxt" / "web", "too-deep")

            found = discover_changes(root)

            self.assertEqual(
                [change.name for change in found],
                ["add-login", "apps · nxt · add-login", "nxt · add-api", "nxt · add-login"],
            )
            nested = next(change for change in found if change.name == "nxt · add-login")
            self.assertEqual(nested.folder_name, "add-login")
            self.assertEqual(nested.project, (root / "nxt").resolve())
            self.assertTrue((nested.path / "proposal.md").is_file())

    def test_lists_nested_change_when_root_tree_is_empty(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "openspec" / "changes").mkdir(parents=True)
            self.write_change(root / "nxt", "add-api")

            found = discover_changes(root)

            self.assertEqual([change.name for change in found], ["nxt · add-api"])

    def test_untouched_merged_list_orders_by_displayed_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_change(root, "zeta")
            self.write_change(root, "add-login")
            self.write_change(root / "nxt", "add-api")

            with patch("sidebar.collect_worktree_snapshot", return_value=None):
                sidebar = Sidebar(Mock(), root)

            self.assertEqual(
                [change.name for change in sidebar.changes],
                ["add-login", "nxt · add-api", "zeta"],
            )

    def test_snapshot_identifies_nested_changes_and_ignores_nested_archives(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.git(root, "init", "-b", "main")
            self.git(root, "config", "user.email", "test@example.com")
            self.git(root, "config", "user.name", "Test User")
            self.write_change(root, "root-change")
            self.write_change(root / "nxt", "add-login")
            archive = root / "nxt" / "openspec" / "changes" / "archive" / "old"
            archive.mkdir(parents=True)
            (archive / "proposal.md").write_text("archived", encoding="utf-8")
            self.git(root, "add", ".")
            self.git(root, "commit", "-m", "baseline")
            self.git(root, "checkout", "-b", "feature/add-login")

            nested = root / "nxt" / "openspec" / "changes" / "add-login" / "proposal.md"
            nested.write_text("touched nested", encoding="utf-8")
            (archive / "proposal.md").write_text("changed archive", encoding="utf-8")

            snapshot = collect_worktree_snapshot(root)

            self.assertIsNotNone(snapshot)
            self.assertEqual(
                set(snapshot.changed_paths),
                {"nxt/openspec/changes/add-login/proposal.md"},
            )
            found = discover_changes(root, snapshot)
            nested_change = next(change for change in found if change.name == "nxt · add-login")
            self.assertTrue(nested_change.worktree_touched)
            self.assertFalse(any(change.name.endswith("old") for change in found))

    def test_ranks_prefixed_change_by_folder_name_affinity(self):
        snapshot = WorktreeSnapshot(
            "refs/heads/main",
            "base",
            "head",
            "feature/add-login",
            "worktree",
            ("nxt/openspec/changes/add-login/proposal.md",),
            (("nxt · add-login", 1), ("zeta", 20)),
        )
        changes = [
            Change(
                "zeta",
                Path("/tmp/zeta"),
                worktree_touched=True,
                worktree_activity=20,
                folder_name="zeta",
            ),
            Change(
                "nxt · add-login",
                Path("/tmp/nxt/add-login"),
                worktree_touched=True,
                worktree_activity=1,
                folder_name="add-login",
            ),
            Change("aaa-untouched", Path("/tmp/aaa"), folder_name="aaa-untouched"),
        ]

        ranked = sort_changes(changes, snapshot)

        self.assertEqual(
            [change.name for change in ranked],
            ["nxt · add-login", "zeta", "aaa-untouched"],
        )

    def test_refresh_preserves_nested_selection_when_folder_names_collide(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_change(root, "add-login")
            self.write_change(root / "nxt", "add-login")
            snapshot = WorktreeSnapshot(
                "refs/heads/main",
                "base",
                "head",
                "feature/other",
                "worktree",
                (),
                (),
            )

            with patch("sidebar.collect_worktree_snapshot", return_value=snapshot):
                sidebar = Sidebar(Mock(), root)
                sidebar.change_index = next(
                    index
                    for index, change in enumerate(sidebar.changes)
                    if change.name == "nxt · add-login"
                )
                sidebar.reload()

            self.assertEqual(sidebar.change.name, "nxt · add-login")

    def test_validates_nested_change_with_folder_name_and_originating_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_change(root / "nxt", "add-login")
            sidebar = self.make_nested_sidebar(root, "nxt · add-login")
            sidebar.draw = Mock()
            completed = Mock(returncode=0, stdout="ok", stderr="")

            with patch("sidebar.subprocess.run", return_value=completed) as invoked:
                sidebar.validate()

            args, kwargs = invoked.call_args
            self.assertEqual(args[0], ["openspec", "validate", "add-login", "--no-interactive"])
            self.assertEqual(Path(kwargs["cwd"]).resolve(), (root / "nxt").resolve())

    def test_opens_nested_proposal_from_originating_change_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = self.write_change(root / "nxt", "add-login", "# Nested proposal\n")
            found = discover_changes(root)
            change = found[0]
            sidebar = self.make_nested_sidebar(root, change.name, found)

            sidebar.open_artifact_by_key("proposal")

            self.assertEqual(sidebar.viewer.path.resolve(), (directory / "proposal.md").resolve())
            self.assertIn("Nested proposal", sidebar.viewer.content)

    def test_empty_state_distinguishes_missing_project_from_empty_changes(self):
        missing = self.make_empty_sidebar(Path("/tmp/missing"), [])
        empty_roots = self.make_empty_sidebar(Path("/tmp/empty"), [Path("/tmp/empty")])

        with patch("sidebar.curses.color_pair", return_value=0):
            missing.draw_empty()
            empty_roots.draw_empty()

        missing_text = " ".join(text for _, _, text, _ in missing.screen.writes)
        empty_text = " ".join(text for _, _, text, _ in empty_roots.screen.writes)
        self.assertIn("No OpenSpec project", missing_text)
        self.assertIn("No active changes", empty_text)

    def make_nested_sidebar(self, root: Path, selected: str, changes=None):
        sidebar = SidebarModelTests.make_sidebar(self)
        sidebar.project = root
        sidebar.openspec_projects = discover_openspec_projects(root)
        sidebar.changes = changes or discover_changes(root)
        sidebar.change_index = next(
            index for index, change in enumerate(sidebar.changes) if change.name == selected
        )
        return sidebar

    def make_empty_sidebar(self, project: Path, openspec_projects: list[Path]):
        sidebar = SidebarModelTests.make_sidebar(self)
        sidebar.project = project
        sidebar.openspec_projects = openspec_projects
        sidebar.changes = []
        return sidebar


if __name__ == "__main__":
    unittest.main()
