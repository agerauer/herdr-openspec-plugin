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
    format_card_name,
    format_card_status,
    truncate,
    CARD_ROWS,
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
    wrap_viewer_header,
    doc_artifact_title,
    non_standard_indexes,
    tab_group_pair,
    viewer_tab_items,
    TAB_PAIR_STANDARD,
    TAB_PAIR_DOC,
    TAB_PAIR_SPEC,
    MOUSE_MASK,
    visible_footer_segments,
    emphasis_attr,
    line_width,
    visible_width,
    render_inline,
    render_markdown,
    wrap_spans,
    create_markdown,
    HEADING_PAIRS,
    PAIR_CODE,
    PAIR_LINK,
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
        sidebar.italic_attr = curses.A_ITALIC
        sidebar._render_cache_key = None
        sidebar._render_cache_lines = []
        sidebar.mouse_enabled = True
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

    def test_left_click_on_a_card_selects_that_change(self):
        sidebar = self.make_sidebar()
        sidebar.change_index = 0
        sidebar.hit_targets = [HitTarget(4, 1, 7, 60, "select_change", 1)]

        sidebar.handle_mouse(10, 5, self.left_click())

        self.assertEqual(sidebar.change_index, 1)
        self.assertEqual(sidebar.focus, "changes")

    def test_left_click_on_empty_space_leaves_selection_unchanged(self):
        sidebar = self.make_sidebar()
        sidebar.change_index = 0
        sidebar.hit_targets = [HitTarget(4, 1, 7, 60, "select_change", 1)]

        sidebar.handle_mouse(10, 20, self.left_click())  # below the card

        self.assertEqual(sidebar.change_index, 0)

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
        self.assertEqual(target.top, 1)  # tab bar sits below the name heading on row 0
        self.assertTrue(target.contains(target.top, target.left))
        self.assertFalse(target.contains(target.top, target.right))

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
        sidebar.edit = unittest.mock.Mock()
        sidebar.reload = unittest.mock.Mock()

        self.assertTrue(sidebar.dispatch_action("open"))  # opens the Proposal
        self.assertTrue(sidebar.dispatch_action("edit"))
        sidebar.edit.assert_called_once_with()
        self.assertTrue(sidebar.dispatch_action("validate"))
        sidebar.validate.assert_called_once_with()
        self.assertTrue(sidebar.dispatch_action("refresh"))
        sidebar.reload.assert_called_once_with(force=True)
        self.assertFalse(sidebar.dispatch_action("close"))

    def test_main_footer_lists_all_shortcuts_with_clickable_docs_hint(self):
        sidebar = self.make_sidebar()

        with patch("sidebar.curses.color_pair", return_value=0):
            sidebar.draw_main()

        footer_text = " ".join(text for y, _x, text, _s in sidebar.screen.writes if y >= 28)
        for hint in (
            "↑↓ move",
            "↵ open",
            "p/d/t/s docs",
            "e folder",
            "v validate",
            "r refresh",
            "q close",
        ):
            self.assertIn(hint, footer_text)
        actions = {target.action for target in sidebar.hit_targets}
        self.assertIn("refresh", actions)  # single-action hints stay clickable
        self.assertNotIn("move", actions)  # the movement legend registers no target

        # The document-keys hint is clickable and opens the Proposal.
        dy, dx, _text, _s = next(
            write for write in sidebar.screen.writes if write[2] == "p/d/t/s docs"
        )
        self.assertTrue(
            any(t.action == "open" and t.top == dy and t.left == dx for t in sidebar.hit_targets)
        )

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

    def test_edit_opens_the_change_folder_from_the_viewer(self):
        artifact = Artifact("proposal", "Proposal", Path("/tmp/proposal.md"))
        sidebar = self.make_sidebar([artifact])
        sidebar.viewer = artifact  # a document is open
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
            ["/usr/local/bin/code", str(sidebar.change.path)],  # the folder, not the open file
            cwd=sidebar.project,
            check=False,
        )
        sidebar.screen.refresh.assert_called_once_with()
        sidebar.reload.assert_called_once_with(force=True)

    def test_edit_opens_the_change_folder_from_the_change_list(self):
        sidebar = self.make_sidebar()
        sidebar.viewer = None
        sidebar.change_index = 0
        sidebar.screen.refresh = Mock()
        sidebar.reload = Mock()

        with (
            patch("sidebar.shutil.which", return_value="/usr/local/bin/code") as which,
            patch("sidebar.curses.endwin"),
            patch("sidebar.subprocess.run") as run,
        ):
            sidebar.edit()

        which.assert_called_once_with("code")
        run.assert_called_once_with(
            ["/usr/local/bin/code", str(sidebar.change.path)],
            cwd=sidebar.project,
            check=False,
        )

    def test_edit_reports_when_code_is_unavailable_for_a_folder(self):
        sidebar = self.make_sidebar()
        sidebar.viewer = None

        with (
            patch("sidebar.shutil.which", return_value=None),
            patch("sidebar.subprocess.run") as run,
        ):
            sidebar.edit()

        run.assert_not_called()  # a directory is not opened with vi
        self.assertIn("code", sidebar.message)

    def test_enter_opens_the_proposal_from_the_change_list(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "proposal.md"
            path.write_text("# Proposal", encoding="utf-8")
            proposal = Artifact("proposal", "Proposal", path, content="# Proposal")
            sidebar = self.make_sidebar([proposal, Artifact("tasks", "Tasks", None)])

            sidebar.handle(curses.KEY_ENTER)
            self.assertIs(sidebar.viewer, proposal)

            # Escape in the main view is a harmless no-op now that there is no
            # separate artifact focus to return from.
            sidebar.dispatch_action("viewer_back")
            sidebar.handle(27)
            self.assertIsNone(sidebar.viewer)
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

    def test_viewer_header_places_back_and_all_tabs_on_one_wide_row(self):
        tabs = [(0, "Proposal"), (1, "Design"), (2, "Tasks"), (3, "auth")]
        rows = wrap_viewer_header(80, tabs, 0)
        segments = [segment for row in rows for segment in row]

        self.assertEqual(len(rows), 1)  # all fit one row when wide
        self.assertEqual(
            [segment.label.strip() for segment in segments],
            ["‹", "Proposal", "Design", "Tasks", "auth"],
        )
        self.assertEqual(segments[0].action, "back")
        self.assertTrue(segments[1].selected)
        self.assertFalse(any(segment.selected for segment in segments[2:]))

    def test_viewer_header_wraps_tabs_onto_more_rows_when_narrow(self):
        tabs = [(0, "Proposal"), (1, "Design"), (2, "Tasks"), (3, "auth")]
        rows = wrap_viewer_header(24, tabs, 0)

        self.assertGreater(len(rows), 1)  # wraps rather than clipping
        labels = [segment.label.strip() for row in rows for segment in row]
        self.assertEqual(labels, ["‹", "Proposal", "Design", "Tasks", "auth"])  # nothing dropped
        # Every tab is a mouse target.
        select = [s for row in rows for s in row if s.action == "select_tab"]
        self.assertEqual([s.index for s in select], [0, 1, 2, 3])

    def test_viewer_geometry_clips_tab_rows_in_a_short_pane(self):
        artifacts = [Artifact("proposal", "Proposal", Path("/tmp/p.md"))] + [
            Artifact(f"doc:d{i}.md", f"Doc {i}", Path(f"/tmp/d{i}.md")) for i in range(10)
        ]
        sidebar = self.make_sidebar(artifacts)
        width, height = 24, 9
        all_rows = wrap_viewer_header(width, viewer_tab_items(artifacts), 0)
        geo = sidebar.viewer_geometry(height, width, sidebar.change, artifacts[0])

        self.assertLess(len(geo["header_rows"]), len(all_rows))  # some tab rows omitted
        self.assertEqual(geo["header_rows"], all_rows[: len(geo["header_rows"])])
        self.assertGreaterEqual(geo["visible"], 1)  # content still shown

    def test_viewer_header_marks_selected_spec_tab_across_rows(self):
        tabs = [(0, "Proposal"), (1, "Design"), (2, "Tasks"), (3, "one"), (4, "two")]
        rows = wrap_viewer_header(28, tabs, 4)
        segments = [segment for row in rows for segment in row]

        self.assertIn("two", [segment.label.strip() for segment in segments])
        selected = next(segment for segment in segments if segment.selected)
        self.assertEqual(selected.label, "two")
        self.assertEqual(selected.index, 4)

    def test_draw_viewer_shows_name_heading_above_marked_tabs(self):
        proposal = Artifact("proposal", "Proposal", Path("/tmp/proposal.md"), content="proposal")
        spec = Artifact("spec:auth/spec.md", "Spec · auth", Path("/tmp/spec.md"), content="spec")
        sidebar = self.make_sidebar([proposal, spec])
        sidebar.viewer = proposal

        with patch("sidebar.curses.color_pair", return_value=0):
            sidebar.draw_viewer()
        # The change name heads row 0; tabs are on the row below it.
        self.assertTrue(any(y == 0 and sidebar.change.name in text for y, _, text, _ in sidebar.screen.writes))
        proposal_tab = next(
            target for target in sidebar.hit_targets
            if target.action == "select_tab" and target.index == 0
        )
        self.assertEqual(proposal_tab.top, 1)
        self.assertTrue(any(y == 1 and "Proposal" in text for y, _, text, _ in sidebar.screen.writes))
        self.assertTrue(proposal_tab.contains(1, proposal_tab.left))

        sidebar.screen.writes.clear()
        sidebar.hit_targets = []
        sidebar.viewer = spec
        with patch("sidebar.curses.color_pair", return_value=0):
            sidebar.draw_viewer()
        spec_tab = next(
            target for target in sidebar.hit_targets
            if target.action == "select_tab" and target.index == 1
        )
        self.assertTrue(any(y == 1 and "auth" in text for y, _, text, _ in sidebar.screen.writes))
        self.assertTrue(spec_tab.contains(1, spec_tab.left))

    def test_discovers_non_standard_markdown_as_doc_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            change_dir = root / "openspec" / "changes" / "add-thing"
            change_dir.mkdir(parents=True)
            (change_dir / ".openspec.yaml").write_text("", encoding="utf-8")
            (change_dir / "proposal.md").write_text("# Proposal", encoding="utf-8")
            (change_dir / "tasks.md").write_text("- [ ] 1.1 do it", encoding="utf-8")
            (change_dir / "research.md").write_text("# Research", encoding="utf-8")
            specs = change_dir / "specs" / "auth"
            specs.mkdir(parents=True)
            (specs / "spec.md").write_text("## ADDED Requirements", encoding="utf-8")

            change = discover_changes(root)[0]
            keys = [artifact.key for artifact in change.artifacts]

            self.assertIn("doc:research.md", keys)
            self.assertGreater(keys.index("doc:research.md"), keys.index("tasks"))
            self.assertLess(
                keys.index("doc:research.md"),
                min(index for index, key in enumerate(keys) if key.startswith("spec:")),
            )
            doc = next(a for a in change.artifacts if a.key == "doc:research.md")
            self.assertEqual(doc.title, "Research")

    def test_doc_artifact_title_prettifies_the_file_name(self):
        self.assertEqual(doc_artifact_title("research.md"), "Research")
        self.assertEqual(doc_artifact_title("release-notes.md"), "Release Notes")
        self.assertEqual(doc_artifact_title("open_questions.md"), "Open Questions")

    def test_viewer_tab_items_order_core_then_docs_then_specs(self):
        artifacts = [
            Artifact("proposal", "Proposal", Path("/tmp/p.md")),
            Artifact("tasks", "Tasks", Path("/tmp/t.md")),
            Artifact("doc:research.md", "Research", Path("/tmp/r.md")),
            Artifact("spec:auth/spec.md", "Spec · auth", Path("/tmp/s.md")),
        ]
        self.assertEqual(
            [label for _index, label in viewer_tab_items(artifacts)],
            ["Proposal", "Tasks", "Research", "auth"],
        )

    def test_tab_group_pair_classifies_by_key(self):
        self.assertEqual(tab_group_pair("proposal"), TAB_PAIR_STANDARD)
        self.assertEqual(tab_group_pair("tasks"), TAB_PAIR_STANDARD)
        self.assertEqual(tab_group_pair("doc:research.md"), TAB_PAIR_DOC)
        self.assertEqual(tab_group_pair("spec:auth/spec.md"), TAB_PAIR_SPEC)
        self.assertEqual(tab_group_pair("specs"), TAB_PAIR_SPEC)

    def test_draw_viewer_color_codes_tab_groups(self):
        artifacts = [
            Artifact("proposal", "Proposal", Path("/tmp/p.md"), content="p"),
            Artifact("design", "Design", Path("/tmp/d.md"), content="d"),
            Artifact("doc:research.md", "Research", Path("/tmp/r.md"), content="r"),
            Artifact("spec:auth/spec.md", "Spec · auth", Path("/tmp/s.md"), content="s"),
        ]
        sidebar = self.make_sidebar(artifacts)
        sidebar.viewer = artifacts[0]  # Proposal selected

        def color_pair(pair):
            return pair * 0x100

        with patch("sidebar.curses.color_pair", side_effect=color_pair):
            sidebar.draw_viewer()

        def style_of(label):
            return next(st for y, _x, text, st in sidebar.screen.writes if text == label and y >= 1)

        self.assertEqual(style_of("Design"), color_pair(TAB_PAIR_STANDARD))
        self.assertEqual(style_of("Research"), color_pair(TAB_PAIR_DOC))
        self.assertEqual(style_of("auth"), color_pair(TAB_PAIR_SPEC))
        self.assertEqual(style_of("Proposal"), curses.A_REVERSE | curses.A_BOLD)

    def test_viewer_footer_advertises_document_shortcuts(self):
        sidebar = self.make_sidebar([Artifact("proposal", "Proposal", Path("/tmp/p.md"), content="p")])
        sidebar.viewer = sidebar.change.artifacts[0]

        with patch("sidebar.curses.color_pair", return_value=0):
            sidebar.draw_viewer()

        labels = {text for _y, _x, text, _st in sidebar.screen.writes}
        self.assertIn("p/d/t/s docs", labels)
        self.assertIn("e folder", labels)
        self.assertIn("← back", labels)

    def test_tab_click_opens_existing_and_reports_missing_without_closing(self):
        with tempfile.TemporaryDirectory() as temporary:
            proposal_path = Path(temporary) / "proposal.md"
            design_path = Path(temporary) / "design.md"
            proposal_path.write_text("proposal", encoding="utf-8")
            design_path.write_text("design", encoding="utf-8")
            proposal = Artifact("proposal", "Proposal", proposal_path, content="proposal")
            design = Artifact("design", "Design", design_path, content="design")
            missing_design = Artifact("design", "Design", None)
            spec = Artifact(
                "spec:auth/spec.md",
                "Spec · auth",
                Path(temporary) / "spec.md",
                content="spec",
            )
            (Path(temporary) / "spec.md").write_text("spec", encoding="utf-8")
            sidebar = self.make_sidebar([proposal, design, spec])
            sidebar.viewer = proposal

            sidebar.dispatch_action("select_tab", 1)
            self.assertIs(sidebar.viewer, design)
            self.assertEqual(sidebar.artifact_index, 1)

            sidebar.changes[0].artifacts[1] = missing_design
            sidebar.viewer = proposal
            sidebar.artifact_index = 0
            sidebar.dispatch_action("select_tab", 1)
            self.assertIs(sidebar.viewer, proposal)
            self.assertEqual(sidebar.artifact_index, 1)
            self.assertEqual(sidebar.message, "Artifact does not exist yet")

            sidebar.artifact_index = 0
            sidebar.viewer = proposal
            sidebar.dispatch_action("select_tab", 2)
            self.assertIs(sidebar.viewer, spec)

            sidebar.viewer_offset = 4
            sidebar.dispatch_action("select_tab", 2)
            self.assertIs(sidebar.viewer, spec)
            self.assertEqual(sidebar.viewer_offset, 4)

    def test_viewer_shortcuts_switch_documents_and_ignore_artifact_list(self):
        with tempfile.TemporaryDirectory() as temporary:
            proposal_path = Path(temporary) / "proposal.md"
            design_path = Path(temporary) / "design.md"
            proposal_path.write_text("proposal", encoding="utf-8")
            design_path.write_text("design", encoding="utf-8")
            proposal = Artifact("proposal", "Proposal", proposal_path, content="proposal")
            design = Artifact("design", "Design", design_path, content="design")
            missing = Artifact("design", "Design", None)
            sidebar = self.make_sidebar([proposal, design])
            sidebar.viewer = proposal

            sidebar.handle(ord("d"))
            self.assertIs(sidebar.viewer, design)

            sidebar.changes[0].artifacts[1] = missing
            sidebar.viewer = proposal
            sidebar.artifact_index = 0
            sidebar.handle(ord("d"))
            self.assertIs(sidebar.viewer, proposal)
            self.assertEqual(sidebar.message, "Artifact does not exist yet")

            sidebar.viewer = None
            sidebar.focus = "artifacts"
            sidebar.artifact_index = 1
            sidebar.handle(ord("p"))
            self.assertEqual(sidebar.artifact_index, 1)
            self.assertIsNone(sidebar.viewer)

    def test_s_opens_and_cycles_specifications(self):
        with tempfile.TemporaryDirectory() as temporary:
            first_path = Path(temporary) / "one.md"
            second_path = Path(temporary) / "two.md"
            first_path.write_text("one", encoding="utf-8")
            second_path.write_text("two", encoding="utf-8")
            proposal = Artifact("proposal", "Proposal", Path(temporary) / "proposal.md", content="p")
            first = Artifact("spec:one/spec.md", "Spec · one", first_path, content="one")
            second = Artifact("spec:two/spec.md", "Spec · two", second_path, content="two")
            sidebar = self.make_sidebar([proposal, first, second])
            sidebar.focus = "changes"

            sidebar.handle(ord("s"))
            self.assertIs(sidebar.viewer, first)

            sidebar.handle(ord("s"))
            self.assertIs(sidebar.viewer, second)
            sidebar.handle(ord("s"))
            self.assertIs(sidebar.viewer, first)

            sidebar.viewer_offset = 2
            sidebar.handle(ord("s"))
            self.assertIs(sidebar.viewer, second)
            only = self.make_sidebar([proposal, first])
            only.viewer = first
            only.viewer_offset = 3
            only.handle(ord("s"))
            self.assertIs(only.viewer, first)
            self.assertEqual(only.viewer_offset, 3)

            empty = self.make_sidebar([proposal, Artifact("specs", "Specifications", None)])
            empty.viewer = proposal
            empty.handle(ord("s"))
            self.assertIs(empty.viewer, proposal)
            self.assertEqual(empty.message, "Artifact does not exist yet")

    def test_arrow_keys_switch_viewer_tabs_and_back_from_proposal(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = {
                name: Path(temporary) / f"{name}.md"
                for name in ("proposal", "design", "tasks", "one", "two")
            }
            for path in paths.values():
                path.write_text(path.stem, encoding="utf-8")
            proposal = Artifact("proposal", "Proposal", paths["proposal"], content="proposal")
            design = Artifact("design", "Design", paths["design"], content="design")
            tasks = Artifact("tasks", "Tasks", paths["tasks"], content="tasks")
            first = Artifact("spec:one/spec.md", "Spec · one", paths["one"], content="one")
            second = Artifact("spec:two/spec.md", "Spec · two", paths["two"], content="two")
            sidebar = self.make_sidebar([proposal, design, tasks, first, second])
            sidebar.viewer = proposal

            sidebar.handle(curses.KEY_RIGHT)
            self.assertIs(sidebar.viewer, design)
            sidebar.handle(curses.KEY_RIGHT)
            self.assertIs(sidebar.viewer, tasks)
            sidebar.handle(curses.KEY_RIGHT)
            self.assertIs(sidebar.viewer, first)
            sidebar.handle(curses.KEY_RIGHT)
            self.assertIs(sidebar.viewer, second)
            sidebar.handle(curses.KEY_RIGHT)
            self.assertIs(sidebar.viewer, second)

            sidebar.handle(curses.KEY_LEFT)
            self.assertIs(sidebar.viewer, first)
            sidebar.handle(curses.KEY_LEFT)
            self.assertIs(sidebar.viewer, tasks)

            sidebar.viewer = proposal
            sidebar.handle(curses.KEY_LEFT)
            self.assertIsNone(sidebar.viewer)

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

    def test_draw_main_renders_a_card_and_select_target_per_change(self):
        sidebar = self.make_sidebar()
        sidebar.changes = [
            Change("alpha", Path("/tmp/alpha"), goal="First change", tasks_done=0, tasks_total=3),
            Change("beta", Path("/tmp/beta"), goal="Second change"),
        ]
        sidebar.change_index = 0

        with patch("sidebar.curses.color_pair", return_value=0):
            sidebar.draw_main()

        texts = [text for _, _, text, _ in sidebar.screen.writes]
        self.assertTrue(any("alpha" in text for text in texts))  # name line
        self.assertTrue(any("READY · 0/3 · 0 Artifacts" in text for text in texts))  # status line
        self.assertTrue(any("First change" in text for text in texts))  # description line
        select_targets = [t for t in sidebar.hit_targets if t.action == "select_change"]
        self.assertEqual(sorted(t.index for t in select_targets), [0, 1])
        # The main-view artifact list is gone.
        self.assertEqual([t for t in sidebar.hit_targets if t.action == "open_artifact"], [])

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

        rendered = render_markdown("one\ntwo\nthree", 40)
        self.assertEqual(
            rendered, [[("one", 0, 0)], [("two", 0, 0)], [("three", 0, 0)]]
        )

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
        # Motion reporting is no longer part of the wheel mask (and no longer requested).
        motion = getattr(curses, "REPORT_MOUSE_POSITION", 0)
        if motion:
            self.assertEqual(mouse_wheel_direction(motion), 0)

    def test_unrecognized_mouse_state_does_not_scroll_document(self):
        sidebar = self.make_sidebar()
        sidebar.viewer = Artifact("proposal", "Proposal", Path("/tmp/proposal.md"))
        sidebar.scroll_viewer_lines = Mock()

        sidebar.handle_mouse(5, 5, 0)

        self.assertEqual(mouse_wheel_direction(0), 0)
        sidebar.scroll_viewer_lines.assert_not_called()

    def test_pressing_m_toggles_mouse_and_reapplies_the_mask(self):
        sidebar = self.make_sidebar()
        calls: list[int] = []

        with patch("sidebar.curses.mousemask", side_effect=lambda mask: calls.append(mask)):
            self.assertTrue(sidebar.handle(ord("m")))
            self.assertFalse(sidebar.mouse_enabled)  # released -> terminal can select/copy
            self.assertTrue(sidebar.handle(ord("m")))
            self.assertTrue(sidebar.mouse_enabled)  # restored -> in-pane mouse active

        self.assertEqual(calls, [0, MOUSE_MASK])

    def test_mouse_toggle_hint_appears_in_both_footers_and_reflects_state(self):
        proposal = Artifact("proposal", "Proposal", Path("/tmp/p.md"), content="body")
        sidebar = self.make_sidebar([proposal])

        with patch("sidebar.curses.color_pair", return_value=0):
            sidebar.draw_main()
        self.assertIn("m mouse on", {text for _y, _x, text, _s in sidebar.screen.writes})

        sidebar.screen.writes.clear()
        sidebar.hit_targets = []
        sidebar.viewer = proposal
        with patch("sidebar.curses.color_pair", return_value=0):
            sidebar.draw_viewer()
        self.assertIn("m mouse on", {text for _y, _x, text, _s in sidebar.screen.writes})

        sidebar.viewer = None
        sidebar.mouse_enabled = False
        sidebar.screen.writes.clear()
        sidebar.hit_targets = []
        with patch("sidebar.curses.color_pair", return_value=0):
            sidebar.draw_main()
        self.assertIn("m mouse off", {text for _y, _x, text, _s in sidebar.screen.writes})

    def test_layout_fills_height_with_no_fixed_card_cap(self):
        # A very tall pane shows more than 15 cards when enough changes exist.
        layout = calculate_main_layout(90, 30, 12)

        self.assertEqual(layout.card_rows, CARD_ROWS)
        self.assertGreater(layout.changes.count, 15)
        self.assertEqual(layout.changes.count, (90 - 1 - 1 - 4) // CARD_ROWS)
        self.assertLessEqual(
            layout.change_row + layout.changes.count * layout.card_rows, layout.message_row
        )

    def test_layout_fits_whole_cards_within_the_available_height(self):
        layout = calculate_main_layout(30, 25, 0)

        self.assertEqual(layout.changes.count, (30 - 6) // CARD_ROWS)
        self.assertLessEqual(
            layout.change_row + layout.changes.count * layout.card_rows, layout.message_row
        )

    def test_layout_reduces_cards_in_a_medium_pane(self):
        layout = calculate_main_layout(30, 25, 12)

        self.assertGreater(layout.changes.count, 1)
        self.assertLess(layout.changes.count, 15)
        self.assertEqual(layout.changes.count, (30 - 6) // CARD_ROWS)

    def test_layout_shows_one_card_at_minimum_height(self):
        layout = calculate_main_layout(12, 25, 12)

        self.assertEqual(layout.changes.count, 1)
        self.assertLess(layout.change_row, layout.message_row)
        self.assertLess(layout.message_row, layout.footer_row)

    def test_layout_keeps_change_selection_visible_across_the_list(self):
        beginning = calculate_main_layout(30, 25, 0).changes
        middle = calculate_main_layout(30, 25, 12).changes
        end = calculate_main_layout(30, 25, 24).changes

        self.assertEqual(beginning.start, 0)
        self.assertLessEqual(middle.start, 12)
        self.assertGreater(middle.stop, 12)
        self.assertEqual(end.stop, 25)

    def test_layout_scrolls_a_lower_selection_into_view(self):
        window = calculate_main_layout(30, 25, 20).changes

        self.assertLessEqual(window.start, 20)
        self.assertGreater(window.stop, 20)

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

    def test_card_status_shows_state_progress_and_artifacts(self):
        populated = Change(
            "add-login",
            Path("/tmp/add-login"),
            tasks_done=0,
            tasks_total=16,
            artifacts=[Artifact("proposal", "Proposal", None)] * 4,
        )
        # Required artifacts missing (openspec draft) folds into DRAFT.
        self.assertEqual(populated.state, "DRAFT")
        self.assertEqual(format_card_status(populated, 40), "DRAFT · 0/16 · 4 Artifacts")

        empty = Change("add-logout", Path("/tmp/add-logout"))  # 0/0 -> DRAFT
        self.assertEqual(format_card_status(empty, 40), "DRAFT · 0/0 · 0 Artifacts")

    def test_card_name_marks_selection_and_drops_worktree_glyph(self):
        untouched = Change("untouched", Path("/tmp/untouched"))
        touched = Change("touched", Path("/tmp/touched"), worktree_touched=True)

        self.assertTrue(format_card_name(untouched, 24).startswith("  "))
        self.assertTrue(format_card_name(untouched, 24, selected=True).startswith("› "))
        # Worktree-touched changes are indicated by color, not a glyph.
        self.assertNotIn("◆", format_card_name(touched, 24))
        self.assertNotIn("◆", format_card_name(touched, 24, selected=True))
        self.assertIn("touched", format_card_name(touched, 24))

    def test_card_status_reserves_state_and_progress_when_narrow(self):
        change = Change(
            "c",
            Path("/tmp/change"),
            tasks_done=12,
            tasks_total=123,
            artifacts=[Artifact("proposal", "Proposal", None)] * 4,
        )
        full = format_card_status(change, 60)
        self.assertEqual(full, "DRAFT · 12/123 · 4 Artifacts")
        # Narrow: the artifact count is dropped first; state + complete progress kept.
        narrow = format_card_status(change, 16)
        self.assertLessEqual(len(narrow), 16)
        self.assertTrue(narrow.endswith("12/123"))
        self.assertNotIn("Artifacts", narrow)

    def test_draw_main_colors_touched_card_names_without_a_glyph(self):
        sidebar = self.make_sidebar()
        sidebar.changes = [
            Change("first", Path("/tmp/first"), worktree_touched=True),
            Change("second", Path("/tmp/second"), worktree_touched=True),
            Change("third", Path("/tmp/third")),
        ]
        sidebar.change_index = 0
        accent = 1 << 22

        with patch("sidebar.curses.color_pair", side_effect=lambda pair: accent if pair == 1 else 0):
            sidebar.draw_main()

        # Card name lines land at rows 4, 8, 12 (one per card, CARD_ROWS apart).
        names = {
            y: (text, style)
            for y, x, text, style in sidebar.screen.writes
            if x == 1 and y in (4, 8, 12)
        }
        self.assertTrue(names[4][0].startswith("› first"))
        self.assertTrue(names[4][1] & accent)  # touched -> accent color
        self.assertTrue(names[4][1] & curses.A_REVERSE)  # selected
        self.assertTrue(names[8][0].startswith("  second"))
        self.assertTrue(names[8][1] & accent)
        self.assertFalse(names[12][1] & accent)  # untouched -> no accent
        self.assertNotIn("◆", names[4][0])
        self.assertNotIn("◆", names[8][0])
        self.assertEqual(
            [
                target.index
                for target in sidebar.hit_targets
                if target.action == "select_change"
            ],
            [0, 1, 2],
        )

    def test_card_name_truncates_long_names(self):
        change = Change("a-very-long-change-name", Path("/tmp/a-very-long-change-name"))

        wide = format_card_name(change, 40)
        narrow = format_card_name(change, 12)

        self.assertIn("a-very-long-change-name", wide)
        self.assertLessEqual(len(narrow), 12)
        self.assertIn("…", narrow)
        self.assertTrue(narrow.startswith("  "))

    def test_each_card_reflects_its_own_counts(self):
        first = Change("add-login", Path("/tmp/add-login"), tasks_done=1, tasks_total=4)
        second = Change("add-logout", Path("/tmp/add-logout"), tasks_done=2, tasks_total=2)

        self.assertEqual(format_card_status(first, 40), "IN PROGRESS · 1/4 · 0 Artifacts")
        self.assertEqual(format_card_status(second, 40), "DONE · 2/2 · 0 Artifacts")
        self.assertTrue(format_card_name(second, 24, selected=True).startswith("› "))

    def test_change_state_derives_from_validity_and_task_progress(self):
        def valid(done, total):
            return Change("c", Path("/tmp/c"), tasks_done=done, tasks_total=total)

        self.assertEqual(valid(0, 0).state, "DRAFT")  # no tasks
        self.assertEqual(valid(0, 8).state, "READY")
        self.assertEqual(valid(3, 8).state, "IN PROGRESS")
        self.assertEqual(valid(8, 8).state, "DONE")
        # A missing required artifact (openspec draft) folds into DRAFT despite progress.
        openspec_draft = Change(
            "c", Path("/tmp/c"), tasks_done=3, tasks_total=8,
            artifacts=[Artifact("proposal", "Proposal", None)],
        )
        self.assertEqual(openspec_draft.state, "DRAFT")
        # Failed validation overrides to INVALID regardless of counts.
        invalid = Change("c", Path("/tmp/c"), tasks_done=8, tasks_total=8, validation="invalid")
        self.assertEqual(invalid.state, "INVALID")

    def test_draw_card_colors_the_derived_state(self):
        sidebar = self.make_sidebar()
        sidebar.changes = [
            Change("prog", Path("/tmp/prog"), goal="g", tasks_done=3, tasks_total=8),  # IN PROGRESS
            Change("done", Path("/tmp/done"), goal="g", tasks_done=5, tasks_total=5),  # DONE
        ]
        sidebar.change_index = 0

        def color_pair(pair):
            return pair * 0x100

        with patch("sidebar.curses.color_pair", side_effect=color_pair):
            sidebar.draw_main()

        # The leading state word is overlaid at column 4 in its state color.
        styled = {
            text: style
            for _y, x, text, style in sidebar.screen.writes
            if x == 4 and text in ("IN PROGRESS", "DONE")
        }
        self.assertEqual(styled.get("IN PROGRESS"), curses.A_BOLD | color_pair(3))  # yellow
        self.assertEqual(styled.get("DONE"), curses.A_BOLD | color_pair(2))  # green

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


class MarkdownRenderingTests(unittest.TestCase):
    def all_text(self, lines):
        return "".join(text for line in lines for text, _a, _p in line)

    def leading_spaces(self, line):
        return len(line[0][0]) - len(line[0][0].lstrip(" ")) if line and line[0][0] else 0

    def test_parser_returns_ast_of_heading_then_paragraph(self):
        ast = create_markdown(renderer=None)("# H\n\ntext")
        types = [node["type"] for node in ast if node["type"] != "blank_line"]
        self.assertEqual(types, ["heading", "paragraph"])
        self.assertEqual(ast[0]["attrs"]["level"], 1)

    def test_visible_and_line_width_count_columns(self):
        self.assertEqual(visible_width("hello"), 5)
        self.assertEqual(line_width([("ab", curses.A_BOLD, 0), ("cde", 0, PAIR_CODE)]), 5)

    def test_wrap_spans_preserves_style_and_hangs_indent(self):
        spans = [("aaaa", curses.A_BOLD, 0), ("bbbb", curses.A_BOLD, 0), ("cccc", curses.A_BOLD, 0)]
        lines = wrap_spans(spans, 9, subsequent_indent=2)
        self.assertEqual(len(lines), 2)
        # The wrapped bold word keeps its attribute across the line break.
        self.assertIn(("cccc", curses.A_BOLD, 0), lines[1])
        # Continuation is indented under the text, not the margin.
        self.assertEqual(lines[1][0], ("  ", 0, 0))

    def test_emphasis_attr_falls_back_to_underline(self):
        self.assertEqual(emphasis_attr(True), curses.A_ITALIC)
        self.assertEqual(emphasis_attr(False), curses.A_UNDERLINE)

    def test_render_inline_styles_spans_without_markers_or_url(self):
        para = create_markdown(renderer=None)("Use **bold** and `code` and [label](http://x).")
        spans = render_inline(para[0]["children"], italic=curses.A_UNDERLINE)
        self.assertIn(("bold", curses.A_BOLD, 0), spans)
        self.assertIn(("code", 0, PAIR_CODE), spans)
        self.assertIn(("label", curses.A_UNDERLINE, PAIR_LINK), spans)
        joined = "".join(text for text, _a, _p in spans)
        for marker in ("*", "`", "[", "]", "(", "http"):
            self.assertNotIn(marker, joined)

    def test_headings_are_colored_by_level_and_keep_case(self):
        first = render_markdown("# Title Case", 80)[0]
        second = render_markdown("## Title Case", 80)[0]
        self.assertEqual(first[0], ("Title", curses.A_BOLD, HEADING_PAIRS[1]))
        self.assertEqual(second[0][2], HEADING_PAIRS[2])
        self.assertNotEqual(HEADING_PAIRS[1], HEADING_PAIRS[2])
        # Original case is preserved (not force-uppercased).
        self.assertIn("Title Case", self.all_text([first]))

    def test_lists_nest_and_wrap_with_hanging_indent(self):
        doc = "- alpha beta gamma delta epsilon zeta\n  - nested\n- last"
        lines = render_markdown(doc, 20)
        rendered = [self.all_text([line]) for line in lines]
        # First item starts with a bullet marker.
        self.assertTrue(rendered[0].lstrip().startswith("•"))
        # A wrapped continuation line is indented and carries no marker.
        continuation = next(
            line
            for line in lines
            if "epsilon" in self.all_text([line])
            and not self.all_text([line]).lstrip().startswith("•")
        )
        self.assertGreater(self.leading_spaces(continuation), 0)
        # The nested item is indented deeper than a top-level item.
        top = next(line for line in lines if self.all_text([line]).lstrip().startswith("• alpha"))
        nested = next(line for line in lines if "nested" in self.all_text([line]))
        self.assertGreater(self.leading_spaces(nested), self.leading_spaces(top))

    def test_fenced_code_preserves_indent_and_drops_fences(self):
        lines = render_markdown("```python\ndef f():\n    return 1\n```", 40)
        text = [self.all_text([line]) for line in lines]
        self.assertIn("def f():", text)
        self.assertIn("    return 1", text)  # indentation preserved, not reflowed
        self.assertFalse(any("```" in line for line in text))
        self.assertTrue(all(span[2] == PAIR_CODE for line in lines for span in line))

    def test_narrow_table_renders_aligned_columns(self):
        doc = "| Name | Qty |\n| --- | --- |\n| Apples | 3 |\n| Pears | 12 |"
        lines = render_markdown(doc, 40)
        texts = [self.all_text([line]) for line in lines if self.all_text([line]).strip()]
        borders = [t for t in texts if t.startswith("+")]
        body = [t for t in texts if t.startswith("│")]
        # Header, header/body divider, and closing border are all present.
        self.assertEqual(len(borders), 3)
        # Every grid row is the same width, so the columns line up.
        self.assertEqual(len({len(t) for t in borders + body}), 1)
        # The column separator sits at the same offset in every body row.
        self.assertEqual(len({t.index("│", 1) for t in body}), 1)

    def test_wide_table_shrinks_to_fit_without_dropping_text(self):
        doc = (
            "| Item | Description |\n"
            "| --- | --- |\n"
            "| Widget | a long description that must wrap across several lines |"
        )
        width = 30
        lines = render_markdown(doc, width)
        # Every rendered line fits the content width (width - 4).
        self.assertTrue(all(line_width(line) <= width - 4 for line in lines))
        # No cell word is dropped.
        joined = self.all_text(lines)
        for word in ("Widget", "description", "wrap", "across", "several", "lines"):
            self.assertIn(word, joined)


if __name__ == "__main__":
    unittest.main()
