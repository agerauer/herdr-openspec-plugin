#!/usr/bin/env python3
"""Dependency-free terminal UI for reviewing active OpenSpec changes."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import curses
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import textwrap
import time
from typing import Any, Callable

# Vendored, pure-Python Markdown parser (see vendor/README.md). Bundled in-tree
# so the plugin keeps its zero-install-dependency launch (`python3 sidebar.py`);
# parsing is not hand-rolled, while the AST-to-terminal rendering lives below.
_VENDOR_DIR = Path(__file__).resolve().parent / "vendor"
if _VENDOR_DIR.is_dir() and str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))
import mistune  # noqa: E402  (imported after the vendor path bootstrap above)
from mistune.plugins.table import table as _mistune_table_plugin  # noqa: E402

# AST mode: calling the parser returns a nested list of token dicts, not HTML.
create_markdown = mistune.create_markdown
_MARKDOWN_PARSER = create_markdown(renderer=None, plugins=[_mistune_table_plugin])


CHECKBOX = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+", re.MULTILINE)
HEADING = re.compile(r"^#{1,6}\s+(.*)$")
DELTA_HEADING = re.compile(r"^##\s+(ADDED|MODIFIED|REMOVED|RENAMED)\s+Requirements?\s*$", re.I)
REQUIREMENT = re.compile(r"^###\s+Requirement:\s*(.+?)\s*$", re.I)
GIT_TIMEOUT_SECONDS = 1.5
OPENSPEC_SEARCH_DEPTH = 2
DISPLAY_SEPARATOR = " · "
SKIPPED_DIRECTORY_NAMES = frozenset(
    {
        "node_modules",
        "__pycache__",
        "venv",
        "dist",
        "build",
        "target",
        "coverage",
    }
)
VIEWER_CORE_TABS = (
    ("proposal", "Proposal"),
    ("design", "Design"),
    ("tasks", "Tasks"),
)
STANDARD_ARTIFACT_FILES = frozenset({"proposal.md", "design.md", "tasks.md"})
# Mouse events the pane captures. Motion reporting is intentionally excluded: it
# is unused and is the most disruptive to the terminal's own text selection.
MOUSE_MASK = curses.ALL_MOUSE_EVENTS
# Tab color groups (curses pair numbers, initialized in curses_main): the three
# standard artifacts, the non-standard change documents, and the specifications.
TAB_PAIR_STANDARD = 1  # cyan
TAB_PAIR_DOC = 3  # yellow
TAB_PAIR_SPEC = 2  # green
VIEWER_BACK_LABEL = " ‹ "
# ncurses reserves six bits per button. Some Python builds expose button 4
# constants but omit button 5 even though getmouse() still returns these bits.
NCURSES_BUTTON5_RELEASED = 1 << 24
NCURSES_BUTTON5_PRESSED = 1 << 25
NCURSES_BUTTON5_CLICKED = 1 << 26


@dataclass
class Artifact:
    key: str
    title: str
    path: Path | None
    required: bool = True
    content: str = ""

    @property
    def exists(self) -> bool:
        return self.path is not None and self.path.is_file()


@dataclass
class Change:
    name: str
    path: Path
    goal: str = ""
    schema: str = "spec-driven"
    artifacts: list[Artifact] = field(default_factory=list)
    deltas: dict[str, int] = field(default_factory=dict)
    tasks_done: int = 0
    tasks_total: int = 0
    worktree_touched: bool = False
    worktree_activity: int = 0
    validation: str | None = None
    validation_detail: str = ""
    folder_name: str = ""
    project: Path | None = None

    def __post_init__(self) -> None:
        if not self.folder_name:
            self.folder_name = self.name

    @property
    def missing_required(self) -> int:
        return sum(item.required and not item.exists for item in self.artifacts)

    @property
    def status(self) -> str:
        if self.validation == "invalid":
            return "INVALID"
        if self.missing_required:
            return "DRAFT"
        return "READY"

    @property
    def state(self) -> str:
        """State shown on the change card, derived from validity and task progress."""
        if self.validation == "invalid":
            return "INVALID"
        if self.tasks_total == 0 or self.missing_required:
            return "DRAFT"
        if self.tasks_done == 0:
            return "READY"
        if self.tasks_done < self.tasks_total:
            return "IN PROGRESS"
        return "DONE"


@dataclass(frozen=True)
class ListWindow:
    """A visible, selection-aware slice of a list."""

    start: int
    count: int

    @property
    def stop(self) -> int:
        return self.start + self.count


@dataclass(frozen=True)
class MainLayout:
    """Rows and the change-card window used to render the sidebar's main view."""

    changes: ListWindow
    change_row: int
    card_rows: int
    message_row: int
    footer_row: int


@dataclass(frozen=True)
class HitTarget:
    """A half-open screen rectangle mapped to a semantic action."""

    top: int
    left: int
    bottom: int
    right: int
    action: str
    index: int | None = None

    def contains(self, y: int, x: int) -> bool:
        return self.top <= y < self.bottom and self.left <= x < self.right


@dataclass(frozen=True)
class FooterSegment:
    label: str
    action: str
    left: int
    right: int


@dataclass(frozen=True)
class ViewerHeaderSegment:
    """A complete back control or artifact tab on the document-viewer title row."""

    label: str
    action: str
    left: int
    right: int
    selected: bool = False
    index: int | None = None


@dataclass(frozen=True)
class GitBase:
    ref: str
    merge_base: str


@dataclass(frozen=True)
class WorktreeSnapshot:
    base_ref: str
    merge_base: str
    head: str
    branch: str
    worktree_name: str
    changed_paths: tuple[str, ...]
    activity: tuple[tuple[str, int], ...]

    @property
    def identity(self) -> str:
        return "\n".join(
            (
                self.base_ref,
                self.merge_base,
                self.head,
                self.branch,
                self.worktree_name,
                *self.changed_paths,
                *(f"{name}:{timestamp}" for name, timestamp in self.activity),
            )
        )

    def activity_for(self, change_name: str) -> int:
        return next((timestamp for name, timestamp in self.activity if name == change_name), 0)


GitRunner = Callable[[Path, list[str]], str | None]


def run_git(project: Path, args: list[str]) -> str | None:
    """Run one bounded, read-only Git query and return None on any failure."""
    try:
        result = subprocess.run(
            ["git", "-C", str(project), *args],
            text=True,
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def resolve_git_base(project: Path, runner: GitRunner = run_git) -> GitBase | None:
    """Resolve the default-branch ref and its merge base with HEAD."""
    if runner(project, ["rev-parse", "--is-inside-work-tree"]) != "true":
        return None

    remote_default = runner(
        project,
        ["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"],
    )
    candidates = [
        remote_default,
        "refs/remotes/origin/main",
        "refs/heads/main",
        "refs/remotes/origin/master",
        "refs/heads/master",
    ]
    seen: set[str] = set()
    for ref in candidates:
        if not ref or ref in seen:
            continue
        seen.add(ref)
        commit = runner(project, ["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"])
        if not commit:
            continue
        merge_base = runner(project, ["merge-base", "HEAD", ref])
        if merge_base:
            return GitBase(ref, merge_base)
    return None


def change_identity_from_path(path: str) -> str | None:
    """Return the displayed change identity for a Git-relative path."""
    parts = Path(path).parts
    try:
        index = parts.index("openspec")
    except ValueError:
        return None
    if index + 2 >= len(parts) or parts[index + 1] != "changes":
        return None
    folder = parts[index + 2]
    if folder == "archive" or folder.startswith("."):
        return None
    prefix = DISPLAY_SEPARATOR.join(parts[:index])
    return f"{prefix}{DISPLAY_SEPARATOR}{folder}" if prefix else folder


def active_change_path(path: str) -> bool:
    """Return whether a relative Git path belongs to an active change."""
    return change_identity_from_path(path) is not None


def paths_by_change(
    paths: list[str] | tuple[str, ...],
    active_names: set[str] | None = None,
) -> dict[str, tuple[str, ...]]:
    """Group unique nested paths by displayed active change identity."""
    grouped: dict[str, set[str]] = {}
    for path in paths:
        name = change_identity_from_path(path)
        if name is None:
            continue
        if active_names is not None and name not in active_names:
            continue
        grouped.setdefault(name, set()).add(path)
    return {name: tuple(sorted(values)) for name, values in sorted(grouped.items())}


def parse_commit_activity(log_output: str) -> dict[str, int]:
    """Map change identities to their newest timestamp from one name-only Git log."""
    activity: dict[str, int] = {}
    timestamp = 0
    for raw in log_output.splitlines():
        line = raw.strip()
        if line.isdigit():
            timestamp = int(line) * 1_000_000_000
            continue
        if timestamp:
            name = change_identity_from_path(line)
            if name:
                activity[name] = max(activity.get(name, 0), timestamp)
    return activity


def map_change_activity(
    paths: list[str] | tuple[str, ...],
    file_activity: dict[str, int],
    commit_activity: dict[str, int],
    active_names: set[str] | None = None,
) -> tuple[tuple[str, int], ...]:
    """Combine file and commit timestamps deterministically per active change."""
    grouped = paths_by_change(paths, active_names)
    return tuple(
        (
            name,
            max(
                commit_activity.get(name, 0),
                *(file_activity.get(path, 0) for path in grouped_paths),
            ),
        )
        for name, grouped_paths in grouped.items()
    )


def normalized_name(value: str) -> str:
    """Normalize a branch leaf, directory, or change name for affinity checks."""
    leaf = value.rsplit("/", 1)[-1]
    return re.sub(r"[^a-z0-9]+", "-", leaf.lower()).strip("-")


def change_name_affinity(change_name: str, branch: str, worktree_name: str) -> int:
    """Return 0 for exact, 1 for bounded containment, and 2 for no affinity."""
    change = normalized_name(change_name)
    contexts = {normalized_name(branch), normalized_name(worktree_name)} - {""}
    if change in contexts:
        return 0
    bounded_change = f"-{change}-"
    if change and any(bounded_change in f"-{context}-" for context in contexts):
        return 1
    return 2


def change_sort_key(change: Change, snapshot: WorktreeSnapshot | None) -> tuple[Any, ...]:
    """Sort touched changes by intent signals, followed by untouched names."""
    if not change.worktree_touched or not snapshot:
        return (1, change.name.lower())
    return (
        0,
        change_name_affinity(change.folder_name, snapshot.branch, snapshot.worktree_name),
        -change.worktree_activity,
        change.name.lower(),
    )


def sort_changes(
    changes: list[Change],
    snapshot: WorktreeSnapshot | None,
) -> list[Change]:
    return sorted(changes, key=lambda change: change_sort_key(change, snapshot))


def collect_worktree_snapshot(
    project: Path,
    runner: GitRunner = run_git,
    openspec_projects: list[Path] | None = None,
) -> WorktreeSnapshot | None:
    """Collect one consistent, scoped view of worktree-touched change paths."""
    base = resolve_git_base(project, runner)
    if not base:
        return None
    projects = openspec_projects if openspec_projects is not None else discover_openspec_projects(project)
    pathspecs = change_pathspecs(project, projects)
    if not pathspecs:
        return None
    head = runner(project, ["rev-parse", "--verify", "HEAD"])
    root = runner(project, ["rev-parse", "--show-toplevel"])
    branch = runner(project, ["branch", "--show-current"])
    tracked = runner(
        project,
        [
            "diff",
            "--name-only",
            "--relative",
            base.merge_base,
            "--",
            *pathspecs,
        ],
    )
    untracked = runner(
        project,
        [
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            *pathspecs,
        ],
    )
    commit_log = runner(
        project,
        [
            "log",
            "--format=%ct",
            "--name-only",
            "--relative",
            f"{base.merge_base}..HEAD",
            "--",
            *pathspecs,
        ],
    )
    if (
        head is None
        or root is None
        or branch is None
        or tracked is None
        or untracked is None
        or commit_log is None
    ):
        return None
    paths = tuple(
        sorted(
            {
                line.strip()
                for output in (tracked, untracked)
                for line in output.splitlines()
                if line.strip() and active_change_path(line.strip())
            }
        )
    )
    file_activity: dict[str, int] = {}
    for path in paths:
        try:
            file_activity[path] = (project / path).stat().st_mtime_ns
        except OSError:
            pass
    activity = map_change_activity(paths, file_activity, parse_commit_activity(commit_log))
    return WorktreeSnapshot(
        base.ref,
        base.merge_base,
        head,
        branch,
        Path(root).name,
        paths,
        activity,
    )


def visible_footer_segments(
    screen_width: int,
    actions: list[tuple[str, str]],
    left: int = 1,
) -> list[FooterSegment]:
    """Lay out only complete footer hints that fit the drawable width."""
    segments: list[FooterSegment] = []
    cursor = left
    limit = max(0, screen_width - 1)
    for label, action in actions:
        right = cursor + len(label)
        if right > limit:
            break
        segments.append(FooterSegment(label, action, cursor, right))
        cursor = right + 2
    return segments


def wrap_footer_segments(
    screen_width: int,
    actions: list[tuple[str, str]],
    left: int = 1,
) -> list[list[FooterSegment]]:
    """Lay out footer hints across as many rows as the width needs.

    Unlike visible_footer_segments, hints that do not fit the current row wrap
    onto the next row instead of being dropped, so the full shortcut set stays
    visible in a narrow pane.
    """
    limit = max(0, screen_width - 1)
    rows: list[list[FooterSegment]] = []
    current: list[FooterSegment] = []
    cursor = left
    for label, action in actions:
        right = cursor + len(label)
        if right > limit and current:
            rows.append(current)
            current = []
            cursor = left
            right = cursor + len(label)
        current.append(FooterSegment(label, action, cursor, right))
        cursor = right + 2
    if current:
        rows.append(current)
    return rows


def spec_tab_label(artifact: Artifact) -> str:
    """Return a short tab label for a specification artifact."""
    prefix = "Spec · "
    if artifact.title.startswith(prefix):
        return artifact.title[len(prefix):]
    if artifact.key.startswith("spec:"):
        relative = artifact.key[5:]
        if relative.endswith("/spec.md"):
            return relative[: -len("/spec.md")] or relative
        return relative
    return artifact.title or "Specs"


def doc_artifact_title(filename: str) -> str:
    """Human title for a non-standard document, derived from its file name."""
    stem = filename[:-3] if filename.endswith(".md") else filename
    return stem.replace("-", " ").replace("_", " ").strip().title() or filename


def non_standard_indexes(artifacts: list[Artifact]) -> list[int]:
    """Return model indexes of non-standard (`doc:`) documents in list order."""
    return [index for index, artifact in enumerate(artifacts) if artifact.key.startswith("doc:")]


def tab_group_pair(key: str) -> int:
    """Color-pair number for a tab, chosen by its artifact group."""
    if key.startswith("spec:") or key == "specs":
        return TAB_PAIR_SPEC
    if key.startswith("doc:"):
        return TAB_PAIR_DOC
    return TAB_PAIR_STANDARD


def viewer_tab_items(artifacts: list[Artifact]) -> list[tuple[int, str]]:
    """Return (artifact index, label): core tabs, then non-standard docs, then specs."""
    items: list[tuple[int, str]] = []
    for key, label in VIEWER_CORE_TABS:
        index = artifact_index_by_key(artifacts, key)
        if index is not None:
            items.append((index, label))
    for index in non_standard_indexes(artifacts):
        items.append((index, artifacts[index].title))
    spec_indexes = specification_indexes(artifacts)
    for index in spec_indexes:
        items.append((index, spec_tab_label(artifacts[index])))
    if not spec_indexes:
        specs_index = artifact_index_by_key(artifacts, "specs")
        if specs_index is not None:
            items.append((specs_index, "Specs"))
    return items


def wrap_viewer_header(
    screen_width: int,
    tabs: list[tuple[int, str]],
    selected_index: int | None,
    left: int = 1,
) -> list[list[ViewerHeaderSegment]]:
    """Lay out the back control plus every tab across as many rows as needed.

    Tabs that do not fit the current row wrap onto the next row instead of being
    clipped, so all tabs stay visible. The caller draws only the rows that fit
    the header's available height.
    """
    limit = max(0, screen_width - 1)
    cursor = left
    back_right = cursor + len(VIEWER_BACK_LABEL)
    if back_right > limit:
        return []
    current: list[ViewerHeaderSegment] = [
        ViewerHeaderSegment(VIEWER_BACK_LABEL, "back", cursor, back_right)
    ]
    cursor = back_right + 2
    rows: list[list[ViewerHeaderSegment]] = []
    for artifact_index, label in tabs:
        right = cursor + len(label)
        if right > limit and current:
            rows.append(current)
            current = []
            cursor = left
            right = cursor + len(label)
        current.append(
            ViewerHeaderSegment(
                label,
                "select_tab",
                cursor,
                right,
                artifact_index == selected_index,
                artifact_index,
            )
        )
        cursor = right + 2
    if current:
        rows.append(current)
    return rows


def specification_indexes(artifacts: list[Artifact]) -> list[int]:
    """Return model indexes of specification documents in list order."""
    return [index for index, artifact in enumerate(artifacts) if artifact.key.startswith("spec:")]


def viewer_document_indexes(artifacts: list[Artifact]) -> list[int]:
    """Return existing core documents then specifications in tab order."""
    indexes: list[int] = []
    for key in ("proposal", "design", "tasks"):
        index = artifact_index_by_key(artifacts, key)
        if index is not None and artifacts[index].exists:
            indexes.append(index)
    indexes.extend(index for index in non_standard_indexes(artifacts) if artifacts[index].exists)
    indexes.extend(specification_indexes(artifacts))
    return indexes


def clipped_hit_target(
    top: int,
    left: int,
    bottom: int,
    right: int,
    screen_height: int,
    screen_width: int,
    action: str,
    index: int | None = None,
) -> HitTarget | None:
    """Clip a target to the drawable screen, or omit it if nothing is visible."""
    clipped_top = max(0, top)
    clipped_left = max(0, left)
    clipped_bottom = min(max(0, screen_height), bottom)
    # curses avoids the terminal's bottom-right cell, matching ``put``.
    clipped_right = min(max(0, screen_width - 1), right)
    if clipped_top >= clipped_bottom or clipped_left >= clipped_right:
        return None
    return HitTarget(
        clipped_top,
        clipped_left,
        clipped_bottom,
        clipped_right,
        action,
        index,
    )


def hit_test(targets: list[HitTarget], y: int, x: int) -> HitTarget | None:
    """Return the first rendered target containing the coordinate."""
    return next((target for target in targets if target.contains(y, x)), None)


def mouse_bits(*names: str) -> int:
    """Combine available curses mouse flags across ncurses versions."""
    bits = 0
    for name in names:
        bits |= getattr(curses, name, 0)
    return bits


def mouse_wheel_direction(button_state: int) -> int:
    """Return -1 for wheel up, 1 for wheel down, or 0 when unrecognized."""
    wheel_up = mouse_bits("BUTTON4_PRESSED", "BUTTON4_CLICKED")
    wheel_down = mouse_bits(
        "BUTTON5_RELEASED",
        "BUTTON5_PRESSED",
        "BUTTON5_CLICKED",
        "BUTTON4_RELEASED",
    ) | NCURSES_BUTTON5_RELEASED | NCURSES_BUTTON5_PRESSED | NCURSES_BUTTON5_CLICKED
    if button_state & wheel_up:
        return -1
    if button_state & wheel_down:
        return 1
    return 0


def centered_window(total: int, selected: int, capacity: int) -> ListWindow:
    """Return a bounded window that keeps the selected item visible."""
    count = min(max(0, capacity), max(0, total))
    if count == 0:
        return ListWindow(0, 0)
    selected = max(0, min(total - 1, selected))
    start = max(0, min(selected - count // 2, total - count))
    return ListWindow(start, count)


CARD_ROWS = 4  # name, status, description, and a blank spacer between cards


def calculate_main_layout(
    height: int,
    change_count: int,
    selected_change: int,
    footer_rows: int = 1,
) -> MainLayout:
    """Allocate the main view as a window of fixed-height change cards.

    Each change is a multi-line card (name, status line, description) with a
    blank spacer, so a given height fits far fewer changes than single-line
    rows did. As many whole cards as the height fits are shown (no fixed cap),
    reduced to keep the message and footer rows usable; at least one card is
    shown whenever any room remains, and the selected card stays in view.
    """
    footer_rows = max(1, footer_rows)
    footer_row = max(0, height - footer_rows)  # top row of the footer block
    message_row = max(0, footer_row - 1)
    change_row = 4
    content_rows = max(0, message_row - change_row)

    capacity = content_rows // CARD_ROWS
    if capacity == 0 and change_count > 0 and content_rows >= 3:
        capacity = 1  # show one card even when its spacer would be clipped
    change_capacity = min(max(0, capacity), change_count)
    change_window = centered_window(change_count, selected_change, change_capacity)

    return MainLayout(
        changes=change_window,
        change_row=change_row,
        card_rows=CARD_ROWS,
        message_row=message_row,
        footer_row=footer_row,
    )


def find_project(start: Path) -> Path:
    start = start.resolve()
    for candidate in (start, *start.parents):
        if (candidate / "openspec").is_dir():
            return candidate
    return start


def resolve_search_root(start: Path, runner: GitRunner = run_git) -> Path:
    """Resolve the workspace root used to discover OpenSpec projects."""
    start = start.resolve()
    toplevel = runner(start, ["rev-parse", "--show-toplevel"])
    if toplevel:
        return Path(toplevel).resolve()
    found: Path | None = None
    for candidate in (start, *start.parents):
        if (candidate / "openspec").is_dir():
            found = candidate
    return found if found is not None else start


def configured_project() -> Path:
    """Resolve the target project independently from the plugin process cwd."""
    configured = os.environ.get("OPENSPEC_PROJECT")
    start = Path(configured).expanduser() if configured else Path.cwd()
    return resolve_search_root(start)


def is_skipped_directory(path: Path) -> bool:
    name = path.name
    return name.startswith(".") or name in SKIPPED_DIRECTORY_NAMES


def discover_openspec_projects(
    search_root: Path,
    max_depth: int = OPENSPEC_SEARCH_DEPTH,
) -> list[Path]:
    """Return OpenSpec project directories at most *max_depth* levels below the search root."""
    search_root = search_root.resolve()
    projects: list[Path] = []
    seen: set[Path] = set()

    def consider(directory: Path) -> None:
        openspec = directory / "openspec"
        try:
            if not openspec.is_dir() or openspec.is_symlink():
                return
        except OSError:
            return
        resolved = directory.resolve()
        if resolved not in seen:
            seen.add(resolved)
            projects.append(resolved)

    def walk(directory: Path, depth: int) -> None:
        consider(directory)
        if depth >= max_depth:
            return
        try:
            entries = list(directory.iterdir())
        except OSError:
            return
        for entry in entries:
            try:
                if (
                    not entry.is_dir()
                    or entry.is_symlink()
                    or is_skipped_directory(entry)
                    or entry.name == "openspec"
                ):
                    continue
            except OSError:
                continue
            walk(entry, depth + 1)

    walk(search_root, 0)
    return projects


def change_pathspecs(search_root: Path, projects: list[Path]) -> list[str]:
    """Return Git pathspecs for each discovered OpenSpec changes tree."""
    pathspecs: list[str] = []
    search_root = search_root.resolve()
    for project in projects:
        changes = project / "openspec" / "changes"
        try:
            pathspecs.append(changes.relative_to(search_root).as_posix())
        except ValueError:
            pathspecs.append(changes.as_posix())
    return pathspecs


def display_change_name(search_root: Path, project: Path, folder_name: str) -> str:
    """Build the list identity for a change, prefixing nested OpenSpec projects."""
    search_root = search_root.resolve()
    project = project.resolve()
    if project == search_root:
        return folder_name
    try:
        relative = project.relative_to(search_root)
    except ValueError:
        relative = Path(project.name)
    parts = [part for part in relative.parts if part not in (".", "")]
    prefix = DISPLAY_SEPARATOR.join(parts)
    return f"{prefix}{DISPLAY_SEPARATOR}{folder_name}" if prefix else folder_name


def parse_metadata(path: Path) -> dict[str, Any]:
    """Read the small scalar/list subset used by .openspec.yaml without PyYAML."""
    if not path.is_file():
        return {}
    result: dict[str, Any] = {}
    active_list: str | None = None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if active_list and re.match(r"^\s+-\s+", line):
            result.setdefault(active_list, []).append(re.sub(r"^\s+-\s+", "", line).strip(" '\""))
            continue
        active_list = None
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        value = value.strip()
        if not value:
            result[key] = []
            active_list = key
        elif value.lower() in ("true", "false"):
            result[key] = value.lower() == "true"
        else:
            result[key] = value.strip(" '\"")
    return result


def read_artifact(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def first_summary(markdown: str) -> str:
    paragraphs: list[str] = []
    current: list[str] = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            if current:
                break
            continue
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                break
            continue
        current.append(re.sub(r"[*_`]", "", line))
    if current and not paragraphs:
        paragraphs.append(" ".join(current))
    return paragraphs[0] if paragraphs else ""


def delta_counts(contents: list[str]) -> dict[str, int]:
    counts = {name: 0 for name in ("ADDED", "MODIFIED", "REMOVED", "RENAMED")}
    operation: str | None = None
    for content in contents:
        for line in content.splitlines():
            match = DELTA_HEADING.match(line.strip())
            if match:
                operation = match.group(1).upper()
            elif REQUIREMENT.match(line.strip()) and operation:
                counts[operation] += 1
    return {key: value for key, value in counts.items() if value}


def truncate(text: str, width: int) -> str:
    """Clip text to width, marking a cut with a single ellipsis."""
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    return "…" if width == 1 else text[: width - 1] + "…"


def format_card_name(change: Change, width: int, selected: bool = False) -> str:
    """The first card line: a selection marker and the (possibly clipped) name."""
    marker = "›" if selected else " "
    prefix = f"{marker} "
    return prefix + truncate(change.name, max(0, width - len(prefix)))


def format_card_status(change: Change, width: int) -> str:
    """The card status line `STATE · done/total · N Artifacts`.

    The prominent state and the complete task progress are reserved: when the
    line does not fit, the artifact count is dropped first, and only at extreme
    widths is anything before the complete `done/total` trimmed.
    """
    if width <= 0:
        return ""
    progress = f"{change.tasks_done}/{change.tasks_total}"
    artifacts = f"{len(change.artifacts)} Artifacts"
    head = f"{change.state} · {progress}"
    full = f"{head} · {artifacts}"
    if len(full) <= width:
        return full
    if len(head) <= width:
        return head  # drop the artifact count first
    if len(progress) <= width:
        return head[-width:]  # keep the complete progress at the right
    return progress[-width:]


def format_delta_summary(change: Change) -> str:
    labels = {"ADDED": "+", "MODIFIED": "~", "REMOVED": "−", "RENAMED": "→"}
    return "  ".join(f"{labels[key]}{count}" for key, count in change.deltas.items())


def artifact_index_by_key(artifacts: list[Artifact], key: str) -> int | None:
    """Return the stable model index for an artifact key."""
    return next((index for index, artifact in enumerate(artifacts) if artifact.key == key), None)


def discover_project_changes(
    search_root: Path,
    project: Path,
) -> list[Change]:
    changes_dir = project / "openspec" / "changes"
    if not changes_dir.is_dir():
        return []
    changes: list[Change] = []
    directories = [
        directory
        for directory in changes_dir.iterdir()
        if directory.is_dir() and not directory.name.startswith(".") and directory.name != "archive"
    ]
    for directory in sorted(directories, key=lambda item: item.name.lower()):
        metadata = parse_metadata(directory / ".openspec.yaml")
        artifacts: list[Artifact] = []

        def append(key: str, title: str, path: Path, required: bool = True) -> None:
            content = read_artifact(path)
            item = Artifact(key, title, path, required, content)
            artifacts.append(item)

        append("proposal", "Proposal", directory / "proposal.md")
        append("design", "Design", directory / "design.md", required=False)
        append("tasks", "Tasks", directory / "tasks.md")
        # Non-standard artifacts: any other top-level Markdown document. Shown as
        # tabs after the standard three and before specifications.
        for doc_path in sorted(directory.glob("*.md")):
            if doc_path.name in STANDARD_ARTIFACT_FILES:
                continue
            append(f"doc:{doc_path.name}", doc_artifact_title(doc_path.name), doc_path, required=False)
        spec_paths = sorted((directory / "specs").glob("**/*.md")) if (directory / "specs").is_dir() else []
        if spec_paths:
            for spec_path in spec_paths:
                relative = spec_path.relative_to(directory / "specs")
                label = relative.parent.as_posix() if relative.name == "spec.md" else relative.as_posix()
                append(f"spec:{relative.as_posix()}", f"Spec · {label}", spec_path)
        else:
            artifacts.append(
                Artifact("specs", "Specifications", None, not bool(metadata.get("skip_specs")))
            )

        task_index = artifact_index_by_key(artifacts, "tasks")
        task_content = artifacts[task_index].content if task_index is not None else ""
        checks = CHECKBOX.findall(task_content)
        name = display_change_name(search_root, project, directory.name)
        change = Change(
            name=name,
            path=directory,
            goal=str(metadata.get("goal", "")),
            schema=str(metadata.get("schema", "spec-driven")),
            artifacts=artifacts,
            deltas=delta_counts([item.content for item in artifacts if item.key.startswith("spec:")]),
            tasks_done=sum(value.lower() == "x" for value in checks),
            tasks_total=len(checks),
            folder_name=directory.name,
            project=project,
        )
        if not change.goal:
            proposal = next((item.content for item in artifacts if item.key == "proposal"), "")
            change.goal = first_summary(proposal)
        changes.append(change)
    return changes


def discover_changes(
    project: Path,
    snapshot: WorktreeSnapshot | None = None,
    openspec_projects: list[Path] | None = None,
) -> list[Change]:
    projects = openspec_projects if openspec_projects is not None else discover_openspec_projects(project)
    changes: list[Change] = []
    for openspec_project in projects:
        changes.extend(discover_project_changes(project, openspec_project))
    if snapshot:
        active_names = {change.name for change in changes}
        touched_names = set(paths_by_change(snapshot.changed_paths, active_names))
        for change in changes:
            change.worktree_touched = change.name in touched_names
            change.worktree_activity = snapshot.activity_for(change.name)
    return sort_changes(changes, snapshot)


# --- Markdown rendering -------------------------------------------------------
#
# A rendered document is a list of StyledLine; each StyledLine is exactly one
# visual row and is a list of Span = (text, attr, pair). `attr` holds curses
# attribute bits (A_BOLD/A_ITALIC/A_UNDERLINE) - plain integers usable without a
# screen - while `pair` is a color-pair NUMBER resolved with curses.color_pair()
# only at draw time, because color_pair() requires an initialized screen. Keeping
# color out of the pure layer lets the renderer be unit-tested without curses.

Span = tuple  # (text: str, attr: int, pair: int)
StyledLine = list  # list[Span]

PAIR_CODE = 5
PAIR_LINK = 6
# Heading level -> existing color pair (1 cyan, 3 yellow, 2 green). Deeper levels
# keep the default color and stay bold. Pairs are set up in curses_main().
HEADING_PAIRS = {1: 1, 2: 3, 3: 2}
BLANK_LINE: StyledLine = [("", 0, 0)]
TABLE_MIN_COL = 3
_BREAKS = frozenset({"softbreak", "linebreak", "break"})


def visible_width(text: str) -> int:
    """Columns a string occupies. len() approximates - wide glyphs are a known gap."""
    return len(text)


def line_width(line: StyledLine) -> int:
    return sum(visible_width(text) for text, _attr, _pair in line)


def _is_blank(line: StyledLine) -> bool:
    return all((not text.strip()) and attr == 0 and pair == 0 for text, attr, pair in line)


def emphasis_attr(supports_italic: bool) -> int:
    """Italic when the terminal renders it; underline as a visible fallback."""
    return curses.A_ITALIC if supports_italic else curses.A_UNDERLINE


def render_inline(nodes, attr: int = 0, pair: int = 0, *, italic: int | None = None) -> list:
    """Flatten mistune inline nodes into spans, OR-composing styles while descending."""
    if italic is None:
        italic = curses.A_ITALIC
    spans: list = []
    for node in nodes or []:
        kind = node.get("type")
        if kind == "text":
            spans.append((node.get("raw", ""), attr, pair))
        elif kind == "strong":
            spans.extend(render_inline(node.get("children"), attr | curses.A_BOLD, pair, italic=italic))
        elif kind == "emphasis":
            spans.extend(render_inline(node.get("children"), attr | italic, pair, italic=italic))
        elif kind == "codespan":
            spans.append((node.get("raw", ""), attr, PAIR_CODE))
        elif kind == "link":
            spans.extend(render_inline(node.get("children"), attr | curses.A_UNDERLINE, PAIR_LINK, italic=italic))
        elif kind in _BREAKS:
            spans.append((" ", attr, pair))
        elif node.get("children"):
            spans.extend(render_inline(node.get("children"), attr, pair, italic=italic))
        elif "raw" in node:
            spans.append((node["raw"], attr, pair))
    return spans


def wrap_spans(spans, width: int, subsequent_indent: int = 0) -> list:
    """Word-wrap spans on visible columns, keeping each word's style and giving
    continuation lines a hanging indent."""
    width = max(1, width)
    words = [(word, attr, pair) for text, attr, pair in spans for word in text.split()]
    if not words:
        return [list(BLANK_LINE)]
    lines: list = []
    current: list = []
    current_width = 0
    for word, attr, pair in words:
        word_width = visible_width(word)
        gap = 1 if current else 0
        if current and current_width + gap + word_width > width:
            lines.append(current)
            current = []
            current_width = 0
            if subsequent_indent:
                current.append((" " * subsequent_indent, 0, 0))
                current_width = subsequent_indent
            gap = 0
        if gap:
            current.append((" ", 0, 0))
            current_width += 1
        current.append((word, attr, pair))
        current_width += word_width
    lines.append(current)
    return lines


def _collapse_blank_lines(lines: list) -> list:
    """Drop leading, trailing, and repeated blank separators."""
    out: list = []
    for line in lines:
        if _is_blank(line):
            if out and not _is_blank(out[-1]):
                out.append(list(BLANK_LINE))
        else:
            out.append(line)
    while out and _is_blank(out[-1]):
        out.pop()
    return out


def _render_paragraph(children, width, out, italic, attr=0, pair=0) -> None:
    segments: list = [[]]
    for node in children or []:
        if node.get("type") in _BREAKS:
            segments.append([])
        else:
            segments[-1].append(node)
    for segment in segments:
        out.extend(wrap_spans(render_inline(segment, attr, pair, italic=italic), width))


def _render_heading(token, width, out, italic) -> None:
    level = token.get("attrs", {}).get("level", 1)
    pair = HEADING_PAIRS.get(level, 0)
    spans = render_inline(token.get("children"), curses.A_BOLD, pair, italic=italic)
    out.extend(wrap_spans(spans, width))
    rule = min(40, max(1, min(width, line_width(spans))))
    out.append([("─" * rule, curses.A_DIM, pair)])


def _render_code(raw, out) -> None:
    for code_line in (raw.rstrip("\n").split("\n") if raw else [""]):
        out.append([(code_line, 0, PAIR_CODE)])


def _render_quote(token, width, out, italic) -> None:
    inner: list = []
    _render_blocks(token.get("children"), max(1, width - 2), inner, italic)
    for line in _collapse_blank_lines(inner):
        out.append([("│ ", curses.A_DIM, 0), *line])


def _render_list(token, width, out, italic, base_indent) -> None:
    ordered = token.get("attrs", {}).get("ordered", False)
    number = token.get("attrs", {}).get("start", 1) or 1
    for item in token.get("children") or []:
        if item.get("type") != "list_item":
            continue
        marker = f"{number}." if ordered else "•"
        number += 1
        prefix = " " * base_indent + marker + " "
        cont = len(prefix)
        text_width = max(1, width - cont)
        first = True
        for child in item.get("children") or []:
            ckind = child.get("type")
            if ckind in ("block_text", "paragraph"):
                item_lines: list = []
                _render_paragraph(child.get("children"), text_width, item_lines, italic)
                for index, line in enumerate(item_lines):
                    lead = prefix if (first and index == 0) else " " * cont
                    out.append([(lead, 0, 0), *line])
                first = False
            elif ckind == "list":
                _render_list(child, width, out, italic, cont)
            elif ckind == "block_code":
                block: list = []
                _render_code(child.get("raw", ""), block)
                for line in block:
                    out.append([(" " * cont, 0, 0), *line])
            else:
                block = []
                _render_blocks([child], text_width, block, italic)
                for line in _collapse_blank_lines(block):
                    out.append([(" " * cont, 0, 0), *line])
                first = False


def _render_table(token, width, out, italic) -> None:
    header: list = []
    rows: list = []
    for section in token.get("children") or []:
        stype = section.get("type")
        if stype == "table_head":
            header = [render_inline(c.get("children"), italic=italic) for c in section.get("children") or []]
        elif stype == "table_body":
            for row in section.get("children") or []:
                rows.append([render_inline(c.get("children"), italic=italic) for c in row.get("children") or []])
    ncols = max([len(header)] + [len(r) for r in rows])
    if not ncols:
        return

    def pad(cells):
        return list(cells) + [[] for _ in range(ncols - len(cells))]

    header = pad(header)
    rows = [pad(r) for r in rows]
    widths = [1] * ncols
    for cells in [header] + rows:
        for i, cell in enumerate(cells):
            widths[i] = max(widths[i], line_width(cell))

    def grid_width(ws):
        return sum(ws) + 3 * ncols + 1

    # Chosen overflow policy: shrink the widest column until the grid fits, then
    # wrap cell text. No column shrinks below TABLE_MIN_COL, so cells wrap rather
    # than vanish and no content is dropped (see design.md).
    while grid_width(widths) > width and any(w > TABLE_MIN_COL for w in widths):
        widest = max(range(ncols), key=lambda j: widths[j])
        widths[widest] -= 1

    border = [("+" + "+".join("─" * (w + 2) for w in widths) + "+", curses.A_DIM, 0)]
    out.append(border)
    _emit_table_row(header, widths, out, header=True)
    out.append(border)
    for row in rows:
        _emit_table_row(row, widths, out, header=False)
    out.append(border)


def _emit_table_row(cells, widths, out, header) -> None:
    rendered = []
    height = 1
    for i, cell in enumerate(cells):
        wrapped = wrap_spans(cell, widths[i]) if cell else [list(BLANK_LINE)]
        if header:
            wrapped = [[(t, a | curses.A_BOLD, p) for t, a, p in line] for line in wrapped]
        rendered.append(wrapped)
        height = max(height, len(wrapped))
    for k in range(height):
        line: list = [("│", curses.A_DIM, 0)]
        for i in range(len(widths)):
            cell_line = rendered[i][k] if k < len(rendered[i]) else list(BLANK_LINE)
            gap = widths[i] - line_width(cell_line)
            line.append((" ", 0, 0))
            line.extend(cell_line)
            if gap > 0:
                line.append((" " * gap, 0, 0))
            line.append((" ", 0, 0))
            line.append(("│", curses.A_DIM, 0))
        out.append(line)


def _render_blocks(tokens, width, out, italic) -> None:
    for token in tokens or []:
        kind = token.get("type")
        if kind == "heading":
            _render_heading(token, width, out, italic)
        elif kind == "paragraph":
            _render_paragraph(token.get("children"), width, out, italic)
        elif kind == "block_code":
            _render_code(token.get("raw", ""), out)
        elif kind == "block_quote":
            _render_quote(token, width, out, italic)
        elif kind == "list":
            _render_list(token, width, out, italic, 0)
        elif kind == "thematic_break":
            out.append([("─" * min(width, 24), curses.A_DIM, 0)])
        elif kind == "table":
            _render_table(token, width, out, italic)
        elif token.get("children"):
            _render_blocks(token.get("children"), width, out, italic)
        else:
            continue
        out.append(list(BLANK_LINE))


def render_markdown(markdown: str, width: int, *, italic: int | None = None) -> list:
    """Render Markdown into styled visual lines that fit `width` columns.

    Replaces the old plain-text clean_markdown/wrap_document pipeline. Each
    returned StyledLine is one visual row, so the viewer's scroll offset,
    percentage, and clamp math are unchanged.
    """
    if italic is None:
        italic = curses.A_ITALIC
    content_width = max(8, width - 4)
    lines: list = []
    _render_blocks(_MARKDOWN_PARSER(markdown or ""), content_width, lines, italic)
    return _collapse_blank_lines(lines)


def clamp_document_offset(offset: int, line_count: int, visible_lines: int) -> int:
    """Clamp a viewer offset to its current wrapped document range."""
    max_offset = max(0, line_count - max(0, visible_lines))
    return max(0, min(offset, max_offset))


def report_identity(project: Path) -> None:
    """Make this pane discoverable without relying on private process metadata."""
    pane_id = os.environ.get("HERDR_PANE_ID")
    herdr = os.environ.get("HERDR_BIN_PATH", "herdr")
    if not pane_id or os.environ.get("HERDR_ENV") != "1":
        return
    token = sha256(str(project.resolve()).encode()).hexdigest()[:16]
    subprocess.run(
        [
            herdr,
            "pane",
            "report-metadata",
            pane_id,
            "--source",
            "plugin:herdr.openspec-review",
            "--title",
            f"OpenSpec Review · {project.name}",
            "--token",
            f"openspec_review={token}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


class Sidebar:
    def __init__(self, screen, project: Path):
        self.screen = screen
        self.project = project
        self.changes: list[Change] = []
        self.change_index = 0
        self.artifact_index = 0
        self.focus = "changes"
        self.viewer: Artifact | None = None
        self.viewer_offset = 0
        # Italic is unevenly supported; fall back to underline when the terminal
        # has no italic capability. tigetstr needs an initialized terminal, so
        # guard for tests that construct the Sidebar without curses.
        try:
            self.italic_attr = curses.A_ITALIC if curses.tigetstr("sitm") else curses.A_UNDERLINE
        except (curses.error, TypeError, ValueError):
            self.italic_attr = curses.A_ITALIC
        self._render_cache_key: tuple | None = None
        self._render_cache_lines: list = []
        self.mouse_enabled = True
        self.hit_targets: list[HitTarget] = []
        self.message = ""
        self.message_until = 0.0
        self.last_scan = 0.0
        self.last_fingerprint = ""
        self.worktree_snapshot: WorktreeSnapshot | None = None
        self.openspec_projects: list[Path] = []
        self.reload(force=True)

    @property
    def change(self) -> Change | None:
        return self.changes[self.change_index] if self.changes else None

    def fingerprint(self, snapshot: WorktreeSnapshot | None = None) -> str:
        projects = self.openspec_projects or discover_openspec_projects(self.project)
        if not projects:
            return f"missing:{snapshot.identity if snapshot else 'unavailable'}"
        parts = []
        for project in projects:
            root = project / "openspec" / "changes"
            if not root.exists():
                continue
            try:
                for path in root.glob("**/*"):
                    if path.is_file():
                        stat = path.stat()
                        parts.append(f"{path}:{stat.st_mtime_ns}:{stat.st_size}")
            except OSError:
                pass
        parts.append(f"worktree:{snapshot.identity if snapshot else 'unavailable'}")
        return sha256("\n".join(sorted(parts)).encode()).hexdigest()

    def reload(self, force: bool = False) -> None:
        self.openspec_projects = discover_openspec_projects(self.project)
        snapshot = collect_worktree_snapshot(self.project, openspec_projects=self.openspec_projects)
        fingerprint = self.fingerprint(snapshot)
        if not force and fingerprint == self.last_fingerprint:
            return
        selected_name = self.change.name if self.change else None
        viewer_key = self.viewer.key if self.viewer else None
        self.worktree_snapshot = snapshot
        self.changes = discover_changes(
            self.project,
            snapshot,
            openspec_projects=self.openspec_projects,
        )
        if selected_name:
            self.change_index = next(
                (index for index, change in enumerate(self.changes) if change.name == selected_name), 0
            )
        self.change_index = min(self.change_index, max(0, len(self.changes) - 1))
        self.artifact_index = min(
            self.artifact_index,
            max(0, len(self.change.artifacts) - 1) if self.change else 0,
        )
        if viewer_key and self.change:
            self.viewer = next(
                (artifact for artifact in self.change.artifacts if artifact.key == viewer_key),
                None,
            )
            if self.viewer and not self.viewer.exists:
                self.viewer = None
        elif viewer_key:
            self.viewer = None
        self.last_fingerprint = fingerprint
        self.last_scan = time.monotonic()

    def say(self, message: str, seconds: float = 3) -> None:
        self.message = message
        self.message_until = time.monotonic() + seconds

    def validate(self) -> None:
        change = self.change
        if not change:
            return
        self.say("Validating…", 30)
        self.draw()
        try:
            result = subprocess.run(
                ["openspec", "validate", change.folder_name, "--no-interactive"],
                cwd=change.project or self.project,
                text=True,
                capture_output=True,
                timeout=12,
                check=False,
            )
            change.validation = "valid" if result.returncode == 0 else "invalid"
            detail = (result.stdout if result.returncode == 0 else result.stderr or result.stdout).strip()
            change.validation_detail = detail
            self.say("Valid OpenSpec change" if result.returncode == 0 else "Validation failed", 4)
        except (OSError, subprocess.TimeoutExpired) as error:
            change.validation = "invalid"
            change.validation_detail = str(error)
            self.say("Could not run openspec validate", 4)

    def apply_mouse_mask(self) -> None:
        """Enable or release mouse capture to match self.mouse_enabled.

        Released (mask 0), the terminal's native selection/copy works over the
        pane; enabled, in-pane clicks and wheel scrolling work.
        """
        try:
            curses.mousemask(MOUSE_MASK if self.mouse_enabled else 0)
        except curses.error:
            pass

    def toggle_mouse(self) -> None:
        self.mouse_enabled = not self.mouse_enabled
        self.apply_mouse_mask()
        self.say(
            "Mouse on — clicks and wheel active"
            if self.mouse_enabled
            else "Mouse off — select and copy with the terminal, press m to restore"
        )

    def edit(self) -> None:
        """Open the selected change's folder in VS Code, from any context."""
        change = self.change
        if not change:
            return
        code = shutil.which("code")
        if not code:
            # A directory is not something vi can usefully open.
            self.say("Install `code` on PATH to open the change folder")
            return
        try:
            curses.endwin()
            subprocess.run(
                [code, str(change.path)],
                cwd=change.project if change.project else self.project,
                check=False,
            )
        finally:
            self.screen.refresh()
            self.reload(force=True)

    def render_viewer(self, content: str, width: int) -> list:
        """Render (and cache) the open document's styled lines for a given width."""
        key = (content, width, self.italic_attr)
        if key != self._render_cache_key:
            self._render_cache_lines = render_markdown(content, width, italic=self.italic_attr)
            self._render_cache_key = key
        return self._render_cache_lines

    def draw_styled_line(self, row: int, x: int, line: list, width: int) -> None:
        """Draw one StyledLine span by span, advancing x and clipping at the edge."""
        for text, attr, pair in line:
            if x >= width - 1 or not text:
                if x >= width - 1:
                    break
                continue
            style = attr
            if pair:
                try:
                    style |= curses.color_pair(pair)
                except curses.error:
                    pass
            self.put(row, x, text, style)
            x += visible_width(text)

    def mouse_hint(self) -> tuple[str, str]:
        return (f"m mouse {'on' if self.mouse_enabled else 'off'}", "toggle_mouse")

    def viewer_footer_actions(self) -> list[tuple[str, str]]:
        return [
            ("← back", "back"),
            ("p/d/t/s docs", ""),
            ("e folder", "edit"),
            self.mouse_hint(),
            ("q close", "close"),
        ]

    def viewer_geometry(self, height: int, width: int, change: "Change", artifact: Artifact) -> dict:
        """Rows for the viewer's variable-height header/content/footer.

        The change name heads row 0; the tab bar wraps across the rows below it;
        a separator, the scrollable content, a percentage row, and the (possibly
        wrapped) footer follow. Both drawing and scroll math read this so the
        offset stays correct as the header grows.
        """
        tabs = viewer_tab_items(change.artifacts)
        selected_index = artifact_index_by_key(change.artifacts, artifact.key)
        header_rows = wrap_viewer_header(width, tabs, selected_index)
        footer_rows = max(1, len(wrap_footer_segments(width, self.viewer_footer_actions())))
        # Reserve the name row, a separator, one content row, and the percent row.
        max_tab_rows = max(0, height - footer_rows - 4)
        drawn_header_rows = header_rows[:max_tab_rows]
        content_top = 1 + len(drawn_header_rows) + 1  # name + tab rows + separator
        footer_top = max(0, height - footer_rows)
        percent_row = max(content_top, footer_top - 1)
        visible = max(0, percent_row - content_top)
        return {
            "selected_index": selected_index,
            "header_rows": drawn_header_rows,
            "separator_row": 1 + len(drawn_header_rows),
            "content_top": content_top,
            "visible": visible,
            "percent_row": percent_row,
            "footer_top": footer_top,
        }

    def tab_segment_style(self, segment: ViewerHeaderSegment, change: "Change") -> int:
        if segment.action == "back":
            return curses.A_BOLD | curses.color_pair(TAB_PAIR_STANDARD)
        if segment.selected:
            return curses.A_REVERSE | curses.A_BOLD
        key = ""
        if segment.index is not None and 0 <= segment.index < len(change.artifacts):
            key = change.artifacts[segment.index].key
        return curses.color_pair(tab_group_pair(key))

    def viewer_dimensions(self) -> tuple[list, int]:
        height, width = self.screen.getmaxyx()
        content = self.viewer.content if self.viewer else ""
        lines = self.render_viewer(content, width)
        if not self.viewer or not self.change:
            return lines, max(0, height - 5)
        return lines, self.viewer_geometry(height, width, self.change, self.viewer)["visible"]

    def scroll_viewer_lines(self, amount: int) -> None:
        wrapped, visible = self.viewer_dimensions()
        self.viewer_offset = clamp_document_offset(
            self.viewer_offset + amount,
            len(wrapped),
            visible,
        )

    def scroll_viewer_pages(self, amount: int) -> None:
        _, visible = self.viewer_dimensions()
        self.scroll_viewer_lines(amount * max(1, visible))

    def open_selected_artifact(self) -> None:
        change = self.change
        if not change or not change.artifacts:
            return
        artifact = change.artifacts[self.artifact_index]
        if artifact.exists:
            if self.viewer is not artifact:
                self.viewer = artifact
                self.viewer_offset = 0
        else:
            self.say("Artifact does not exist yet")

    def open_artifact_by_key(self, key: str) -> None:
        change = self.change
        if not change:
            return
        index = artifact_index_by_key(change.artifacts, key)
        if index is None:
            return
        self.artifact_index = index
        self.open_selected_artifact()

    def open_or_cycle_specification(self) -> None:
        change = self.change
        if not change:
            return
        indexes = specification_indexes(change.artifacts)
        if not indexes:
            specs_index = artifact_index_by_key(change.artifacts, "specs")
            if specs_index is not None:
                self.artifact_index = specs_index
            self.say("Artifact does not exist yet")
            return
        current = None
        if self.viewer and self.viewer.key.startswith("spec:"):
            current = artifact_index_by_key(change.artifacts, self.viewer.key)
        if current in indexes:
            if len(indexes) == 1:
                return
            position = indexes.index(current)
            self.artifact_index = indexes[(position + 1) % len(indexes)]
        else:
            self.artifact_index = indexes[0]
        self.open_selected_artifact()

    def select_viewer_tab(self, index: int) -> None:
        change = self.change
        if not change or index < 0 or index >= len(change.artifacts):
            return
        self.artifact_index = index
        self.open_selected_artifact()

    def move_viewer_tab(self, direction: int) -> None:
        """Move to the next or previous existing document, or back from the first."""
        change = self.change
        if not change or not self.viewer:
            return
        indexes = viewer_document_indexes(change.artifacts)
        current = artifact_index_by_key(change.artifacts, self.viewer.key)
        if not indexes or current not in indexes:
            if direction < 0:
                self.dispatch_action("viewer_back")
            return
        position = indexes.index(current) + direction
        if position < 0:
            self.dispatch_action("viewer_back")
            return
        if position >= len(indexes):
            return
        self.artifact_index = indexes[position]
        self.open_selected_artifact()

    def dispatch_action(self, action: str, index: int | None = None) -> bool:
        """Run one semantic action shared by keyboard and mouse input."""
        if action == "close":
            return False
        if action == "refresh":
            self.reload(force=True)
            self.say("Refreshed")
        elif action == "validate":
            self.validate()
        elif action == "edit":
            self.edit()
        elif action == "toggle_mouse":
            self.toggle_mouse()
        elif action == "viewer_back" and self.viewer:
            self.viewer = None
            self.viewer_offset = 0
        elif action == "focus_changes" and not self.viewer:
            self.focus = "changes"
        elif action == "back":
            return self.dispatch_action("viewer_back" if self.viewer else "focus_changes")
        elif action == "open" and not self.viewer and self.change:
            self.open_artifact_by_key("proposal")
        elif action == "select_change" and index is not None and 0 <= index < len(self.changes):
            self.change_index = index
            self.artifact_index = 0
            self.focus = "changes"
        elif action == "select_tab" and index is not None:
            self.select_viewer_tab(index)
        elif action == "viewer_tab" and index is not None:
            self.move_viewer_tab(index)
        return True

    def register_hit_target(
        self,
        top: int,
        left: int,
        bottom: int,
        right: int,
        action: str,
        index: int | None = None,
    ) -> None:
        height, width = self.screen.getmaxyx()
        target = clipped_hit_target(
            top, left, bottom, right, height, width, action, index
        )
        if target:
            self.hit_targets.append(target)

    def handle_mouse(self, x: int, y: int, button_state: int) -> bool:
        wheel_direction = mouse_wheel_direction(button_state) if self.viewer else 0
        if wheel_direction:
            self.scroll_viewer_lines(wheel_direction)
            return True
        left_click = mouse_bits("BUTTON1_CLICKED", "BUTTON1_PRESSED")
        if not button_state & left_click:
            return True
        target = hit_test(self.hit_targets, y, x)
        if target:
            return self.dispatch_action(target.action, target.index)
        return True

    def draw_footer(self, top_row: int, actions: list[tuple[str, str]]) -> None:
        """Render footer hints, wrapping onto further rows below top_row."""
        _, width = self.screen.getmaxyx()
        for offset, segments in enumerate(wrap_footer_segments(width, actions)):
            row = top_row + offset
            for segment in segments:
                self.put(row, segment.left, segment.label, curses.A_DIM)
                if not segment.action:
                    continue  # display-only legend (e.g. movement keys), not clickable
                self.register_hit_target(
                    row,
                    segment.left,
                    row + 1,
                    segment.right,
                    segment.action,
                )

    def move(self, amount: int) -> None:
        self.change_index = max(0, min(len(self.changes) - 1, self.change_index + amount))
        self.artifact_index = 0

    def handle(self, key: int) -> bool:
        if key in (ord("q"), ord("Q")):
            return self.dispatch_action("close")
        if key == curses.KEY_RESIZE:
            return True
        if key == curses.KEY_MOUSE:
            try:
                _, x, y, _, button_state = curses.getmouse()
            except curses.error:
                return True
            return self.handle_mouse(x, y, button_state)
        if key in (ord("r"), ord("R")):
            return self.dispatch_action("refresh")
        elif key in (ord("v"), ord("V")):
            return self.dispatch_action("validate")
        elif key == ord("e"):
            return self.dispatch_action("edit")
        elif key in (ord("m"), ord("M")):
            return self.dispatch_action("toggle_mouse")
        elif key in (ord("p"), ord("d"), ord("t"), ord("s")) and (
            self.viewer or self.focus == "changes"
        ):
            if key == ord("s"):
                self.open_or_cycle_specification()
            else:
                self.open_artifact_by_key(
                    {ord("p"): "proposal", ord("d"): "design", ord("t"): "tasks"}[key]
                )
        elif key in (curses.KEY_UP, ord("k")):
            if self.viewer:
                self.scroll_viewer_lines(-1)
            else:
                self.move(-1)
        elif key in (curses.KEY_DOWN, ord("j")):
            if self.viewer:
                self.scroll_viewer_lines(1)
            else:
                self.move(1)
        elif key == curses.KEY_PPAGE:
            if self.viewer:
                self.scroll_viewer_pages(-1)
            else:
                self.move(-1)
        elif key == curses.KEY_NPAGE:
            if self.viewer:
                self.scroll_viewer_pages(1)
            else:
                self.move(1)
        elif key == 27:
            return self.dispatch_action("viewer_back" if self.viewer else "focus_changes")
        elif key in (curses.KEY_LEFT, ord("h")):
            if self.viewer:
                return self.dispatch_action("viewer_tab", -1)
            return self.dispatch_action("back")
        elif key in (curses.KEY_RIGHT, ord("l")):
            if self.viewer:
                return self.dispatch_action("viewer_tab", 1)
            return self.dispatch_action("open")
        elif key in (10, 13, curses.KEY_ENTER):
            return self.dispatch_action("open")
        return True

    def put(self, y: int, x: int, text: str, style: int = 0) -> None:
        height, width = self.screen.getmaxyx()
        if y < 0 or y >= height or x >= width:
            return
        available = max(0, width - x - 1)
        try:
            self.screen.addnstr(y, x, text, available, style)
        except curses.error:
            pass

    def draw_empty(self) -> None:
        _, width = self.screen.getmaxyx()
        self.put(0, 1, " OPENSPEC REVIEW ", curses.A_BOLD | curses.color_pair(1))
        if not self.openspec_projects:
            title = "No OpenSpec project"
            help_text = "Run  openspec init  in this workspace, then press r."
        else:
            title = "No active changes"
            help_text = "Create one with  openspec new change <name>  then press r."
        self.put(3, 2, title, curses.A_BOLD)
        for index, line in enumerate(textwrap.wrap(help_text, max(10, width - 4))):
            self.put(5 + index, 2, line, curses.A_DIM)

    def draw_viewer(self) -> None:
        artifact = self.viewer
        change = self.change
        if not artifact or not change:
            return
        height, width = self.screen.getmaxyx()
        geo = self.viewer_geometry(height, width, change, artifact)
        # Change name heads the viewer, styled distinctly from the tabs.
        self.put(0, 1, truncate(change.name, max(0, width - 2)), curses.A_BOLD | curses.color_pair(TAB_PAIR_STANDARD))
        # Color-coded, wrapped tab bar beneath the name.
        for offset, row_segments in enumerate(geo["header_rows"]):
            row = 1 + offset
            for segment in row_segments:
                self.put(row, segment.left, segment.label, self.tab_segment_style(segment, change))
                self.register_hit_target(
                    row, segment.left, row + 1, segment.right, segment.action, segment.index
                )
        self.put(geo["separator_row"], 0, "─" * max(0, width - 1), curses.A_DIM)
        wrapped = self.render_viewer(artifact.content, width)
        visible = geo["visible"]
        max_offset = max(0, len(wrapped) - visible)
        self.viewer_offset = clamp_document_offset(self.viewer_offset, len(wrapped), visible)
        for row, line in enumerate(
            wrapped[self.viewer_offset : self.viewer_offset + visible], start=geo["content_top"]
        ):
            self.draw_styled_line(row, 2, line, width)
        if max_offset:
            percent = round(100 * self.viewer_offset / max_offset)
            self.put(geo["percent_row"], max(1, width - 6), f"{percent:>3}%", curses.A_DIM)
        self.draw_footer(geo["footer_top"], self.viewer_footer_actions())

    def draw_change_card(self, top: int, width: int, change: Change, selected: bool) -> None:
        """Draw one change's three-line card: name, status line, description."""
        state = change.state
        state_color = {
            "INVALID": curses.color_pair(4),
            "DRAFT": curses.A_DIM,
            "READY": curses.color_pair(1),
            "IN PROGRESS": curses.color_pair(3),
            "DONE": curses.color_pair(2),
        }.get(state, curses.A_DIM)

        name_style = curses.A_BOLD
        if change.worktree_touched:
            name_style |= curses.color_pair(1)
        if selected:
            name_style |= curses.A_REVERSE
        self.put(top, 1, format_card_name(change, max(0, width - 2), selected), name_style)

        status_line = format_card_status(change, max(0, width - 5))
        self.put(top + 1, 4, status_line, curses.A_DIM)
        if status_line.startswith(state):  # color the prominent leading state
            self.put(top + 1, 4, state, curses.A_BOLD | state_color)

        if change.goal:
            self.put(top + 2, 4, truncate(change.goal, max(0, width - 5)), curses.A_DIM)

    def draw_main(self) -> None:
        height, width = self.screen.getmaxyx()
        self.put(0, 1, " OPENSPEC REVIEW ", curses.A_BOLD | curses.color_pair(1))
        self.put(1, 2, self.project.name, curses.A_DIM)
        if not self.changes:
            self.draw_empty()
            return

        footer_actions = [
            ("↑↓ move", ""),
            ("↵ open", "open"),
            ("p/d/t/s docs", "open"),
            ("e folder", "edit"),
            ("v validate", "validate"),
            ("r refresh", "refresh"),
            self.mouse_hint(),
            ("q close", "close"),
        ]
        footer_row_count = len(wrap_footer_segments(width, footer_actions))
        layout = calculate_main_layout(
            height, len(self.changes), self.change_index, footer_rows=footer_row_count
        )
        self.put(3, 1, "CHANGES", curses.A_BOLD)
        for offset, index in enumerate(range(layout.changes.start, layout.changes.stop)):
            top = layout.change_row + offset * layout.card_rows
            item = self.changes[index]
            selected = index == self.change_index
            self.draw_change_card(top, width, item, selected)
            self.register_hit_target(top, 1, top + 3, max(1, width), "select_change", index)

        self.put(layout.message_row, 1, self.message if time.monotonic() < self.message_until else "", curses.A_BOLD)
        self.draw_footer(layout.footer_row, footer_actions)

    def draw(self) -> None:
        self.hit_targets = []
        self.screen.erase()
        if self.viewer:
            self.draw_viewer()
        else:
            self.draw_main()
        self.screen.refresh()

    def run(self) -> None:
        self.screen.timeout(250)
        while True:
            if time.monotonic() - self.last_scan > 2:
                self.reload()
                self.last_scan = time.monotonic()
            self.draw()
            key = self.screen.getch()
            if key != -1 and not self.handle(key):
                break


def curses_main(screen) -> None:
    curses.curs_set(0)
    # Escape is the lead byte of arrow/function-key sequences, so ncurses waits
    # ESCDELAY (long by default) before delivering a lone Escape. Shorten it so
    # leaving the document viewer with Escape is as prompt as Left.
    try:
        curses.set_escdelay(25)
    except (curses.error, AttributeError):
        pass
    curses.use_default_colors()
    curses.start_color()
    curses.init_pair(1, curses.COLOR_CYAN, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_RED, -1)
    curses.init_pair(PAIR_CODE, curses.COLOR_MAGENTA, -1)
    curses.init_pair(PAIR_LINK, curses.COLOR_BLUE, -1)
    try:
        curses.mousemask(MOUSE_MASK)
        curses.mouseinterval(0)
    except curses.error:
        pass
    screen.keypad(True)
    project = configured_project()
    report_identity(project)
    Sidebar(screen, project).run()


def main() -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("OpenSpec Review needs an interactive terminal.", file=sys.stderr)
        return 1
    curses.wrapper(curses_main)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
