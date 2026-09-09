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
    """Rows and list windows used to render the sidebar's main view."""

    changes: ListWindow
    change_row: int
    status_row: int
    goal_row: int
    goal_count: int
    artifact_header_row: int
    artifacts: ListWindow
    artifact_row: int
    summary_row: int
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
        "REPORT_MOUSE_POSITION",
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


def calculate_main_layout(
    height: int,
    change_count: int,
    selected_change: int,
    artifact_count: int,
    selected_artifact: int,
    goal_line_count: int,
) -> MainLayout:
    """Allocate non-overlapping main-view regions from the pane height.

    A normal pane reserves two spacer rows, up to two goal rows, and four
    artifact rows before assigning as many as 15 rows to changes. Any space
    left after reaching that change target expands the artifact window. At
    the minimum supported height (12 rows), optional spacing and goal text
    yield so one change and one artifact remain usable.
    """
    footer_row = max(0, height - 1)
    message_row = max(0, height - 2)
    summary_row = max(0, height - 4)
    change_row = 4
    content_rows = max(0, summary_row - change_row)

    has_changes = change_count > 0
    has_artifacts = artifact_count > 0
    change_capacity = 1 if has_changes else 0
    artifact_capacity = 1 if has_artifacts else 0

    # Status and the artifact heading are the two required detail rows.
    spare = max(0, content_rows - change_capacity - artifact_capacity - 2)
    shown_goal_lines = min(max(0, goal_line_count), 2, spare)
    spare -= shown_goal_lines

    extra_artifacts = min(max(0, artifact_count - artifact_capacity), 3, spare)
    artifact_capacity += extra_artifacts
    spare -= extra_artifacts

    spacer_count = min(2, spare)
    spare -= spacer_count

    extra_changes = min(max(0, change_count - change_capacity), 15 - change_capacity, spare)
    change_capacity += extra_changes
    spare -= extra_changes

    surplus_artifacts = min(max(0, artifact_count - artifact_capacity), spare)
    artifact_capacity += surplus_artifacts

    change_window = centered_window(change_count, selected_change, change_capacity)
    row = change_row + change_window.count
    if spacer_count:
        row += 1
    status_row = row
    goal_row = status_row + 1
    row = goal_row + shown_goal_lines
    if spacer_count > 1:
        row += 1
    artifact_header_row = row
    artifact_row = artifact_header_row + 1
    artifact_window = centered_window(artifact_count, selected_artifact, artifact_capacity)

    return MainLayout(
        changes=change_window,
        change_row=change_row,
        status_row=status_row,
        goal_row=goal_row,
        goal_count=shown_goal_lines,
        artifact_header_row=artifact_header_row,
        artifacts=artifact_window,
        artifact_row=artifact_row,
        summary_row=summary_row,
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


def format_change_row(change: Change, width: int, selected: bool = False) -> str:
    """Render one fixed-width list row while keeping task progress visible."""
    if width <= 0:
        return ""
    progress = f"{change.tasks_done}/{change.tasks_total}"
    if width <= len(progress):
        return progress[-width:]

    selection_marker = "›" if selected else " "
    worktree_marker = "◆" if change.worktree_touched else " "
    prefix = f"{selection_marker}{worktree_marker} "
    name_width = width - len(prefix) - len(progress) - 1
    if name_width <= 0:
        marker_width = width - len(progress)
        if marker_width >= 2:
            compact_markers = selection_marker + worktree_marker
        elif marker_width == 1:
            compact_markers = worktree_marker if change.worktree_touched else selection_marker
        else:
            compact_markers = ""
        return (compact_markers + progress)[-width:]

    name = change.name
    if len(name) > name_width:
        name = "…" if name_width == 1 else name[: name_width - 1] + "…"
    return f"{prefix}{name:<{name_width}} {progress}"


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


def clean_markdown(markdown: str) -> list[str]:
    lines: list[str] = []
    in_fence = False
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        heading = HEADING.match(line.strip())
        if heading:
            title = heading.group(1).strip()
            lines.extend(([title.upper(), "─" * min(40, len(title))]))
            continue
        if not in_fence:
            line = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", line)
            line = re.sub(r"(?<!`)`([^`]+)`", r"\1", line)
            line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
        lines.append(("  " + line) if in_fence else line)
    return lines


def wrap_document(markdown: str, screen_width: int) -> list[str]:
    """Wrap cleaned Markdown into the visual lines used by the viewer."""
    wrapped: list[str] = []
    for line in clean_markdown(markdown):
        if not line:
            wrapped.append("")
        else:
            wrapped.extend(
                textwrap.wrap(line, max(8, screen_width - 4), replace_whitespace=False) or [""]
            )
    return wrapped


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

    def edit(self) -> None:
        if not self.viewer or not self.viewer.path:
            return
        editor = shutil.which("code") or "vi"
        try:
            curses.endwin()
            subprocess.run(
                [editor, str(self.viewer.path)],
                cwd=self.change.project if self.change and self.change.project else self.project,
                check=False,
            )
        finally:
            self.screen.refresh()
            self.reload(force=True)

    def viewer_dimensions(self) -> tuple[list[str], int]:
        height, width = self.screen.getmaxyx()
        content = self.viewer.content if self.viewer else ""
        return wrap_document(content, width), max(0, height - 5)

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

    def dispatch_action(self, action: str, index: int | None = None) -> bool:
        """Run one semantic action shared by keyboard and mouse input."""
        if action == "close":
            return False
        if action == "refresh":
            self.reload(force=True)
            self.say("Refreshed")
        elif action == "validate":
            self.validate()
        elif action == "edit" and self.viewer:
            self.edit()
        elif action == "viewer_back" and self.viewer:
            self.viewer = None
            self.viewer_offset = 0
        elif action == "focus_changes" and not self.viewer:
            self.focus = "changes"
        elif action == "back":
            return self.dispatch_action("viewer_back" if self.viewer else "focus_changes")
        elif action == "toggle_focus" and not self.viewer and self.change:
            self.focus = "artifacts" if self.focus == "changes" else "changes"
        elif action == "open":
            if self.focus == "changes" and self.change:
                self.focus = "artifacts"
            elif self.change and self.change.artifacts:
                self.open_selected_artifact()
        elif action == "select_change" and index is not None and 0 <= index < len(self.changes):
            self.change_index = index
            self.artifact_index = 0
            self.focus = "changes"
        elif action == "open_artifact" and self.change and index is not None:
            if 0 <= index < len(self.change.artifacts):
                self.artifact_index = index
                self.focus = "artifacts"
                self.open_selected_artifact()
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

    def draw_footer(self, row: int, actions: list[tuple[str, str]]) -> None:
        """Render and register each complete footer hint independently."""
        _, width = self.screen.getmaxyx()
        for segment in visible_footer_segments(width, actions):
            self.put(row, segment.left, segment.label, curses.A_DIM)
            self.register_hit_target(
                row,
                segment.left,
                row + 1,
                segment.right,
                segment.action,
            )

    def move(self, amount: int) -> None:
        if self.focus == "changes":
            self.change_index = max(0, min(len(self.changes) - 1, self.change_index + amount))
            self.artifact_index = 0
        elif self.change:
            self.artifact_index = max(
                0, min(len(self.change.artifacts) - 1, self.artifact_index + amount)
            )

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
        elif key == ord("e") and self.viewer:
            return self.dispatch_action("edit")
        elif not self.viewer and self.focus == "changes" and key in (
            ord("p"),
            ord("d"),
            ord("t"),
        ):
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
            return self.dispatch_action("back")
        elif key in (9, curses.KEY_RIGHT, ord("l")):
            return self.dispatch_action("toggle_focus")
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
        header_label = f" ‹ {artifact.title} "
        self.put(0, 1, header_label, curses.A_BOLD | curses.color_pair(1))
        self.register_hit_target(0, 1, 1, 1 + len(header_label), "back")
        self.put(1, 2, change.name, curses.A_DIM)
        self.put(2, 0, "─" * max(0, width - 1), curses.A_DIM)
        wrapped = wrap_document(artifact.content, width)
        visible = max(0, height - 5)
        max_offset = max(0, len(wrapped) - visible)
        self.viewer_offset = clamp_document_offset(self.viewer_offset, len(wrapped), visible)
        for row, line in enumerate(wrapped[self.viewer_offset : self.viewer_offset + visible], start=3):
            style = curses.A_BOLD if line.isupper() and line.strip("─ ") else 0
            self.put(row, 2, line, style)
        if max_offset:
            percent = round(100 * self.viewer_offset / max_offset) if max_offset else 100
            self.put(height - 2, max(1, width - 6), f"{percent:>3}%", curses.A_DIM)
        self.draw_footer(
            height - 1,
            [("← back", "back"), ("e edit", "edit"), ("q close", "close")],
        )

    def draw_main(self) -> None:
        height, width = self.screen.getmaxyx()
        self.put(0, 1, " OPENSPEC REVIEW ", curses.A_BOLD | curses.color_pair(1))
        self.put(1, 2, self.project.name, curses.A_DIM)
        if not self.changes:
            self.draw_empty()
            return

        change = self.change
        assert change is not None
        status_style = {
            "READY": curses.color_pair(3),
            "INVALID": curses.color_pair(4),
        }.get(change.status, curses.A_DIM)
        goal_lines = textwrap.wrap(change.goal, max(10, width - 4))[:2] if change.goal else []
        layout = calculate_main_layout(
            height,
            len(self.changes),
            self.change_index,
            len(change.artifacts),
            self.artifact_index,
            len(goal_lines),
        )
        self.put(3, 1, "CHANGES", curses.A_BOLD)
        row = layout.change_row
        for index in range(layout.changes.start, layout.changes.stop):
            item = self.changes[index]
            selected = index == self.change_index
            style = curses.A_REVERSE if selected and self.focus == "changes" else 0
            if item.worktree_touched:
                style |= curses.color_pair(2) | curses.A_BOLD
            rendered = format_change_row(item, max(0, width - 2), selected)
            self.put(row, 1, rendered, style | (curses.A_BOLD if selected else 0))
            self.register_hit_target(row, 1, row + 1, 1 + len(rendered), "select_change", index)
            row += 1

        self.put(layout.status_row, 1, change.status, curses.A_BOLD | status_style)
        for index, line in enumerate(goal_lines[: layout.goal_count]):
            self.put(layout.goal_row + index, 2, line, curses.A_DIM)
        self.put(
            layout.artifact_header_row,
            1,
            f"ARTIFACTS ({len(change.artifacts)})",
            curses.A_BOLD,
        )

        row = layout.artifact_row
        for index in range(layout.artifacts.start, layout.artifacts.stop):
            artifact = change.artifacts[index]
            selected = index == self.artifact_index
            if artifact.exists:
                icon, icon_style = "•", curses.color_pair(1)
            elif artifact.required:
                icon, icon_style = "!", curses.color_pair(4)
            else:
                icon, icon_style = "·", curses.A_DIM
            style = curses.A_REVERSE if selected and self.focus == "artifacts" else 0
            self.put(row, 2, icon, icon_style | style)
            self.put(row, 4, artifact.title, style | (curses.A_DIM if not artifact.exists else 0))
            self.register_hit_target(
                row,
                2,
                row + 1,
                4 + len(artifact.title),
                "open_artifact",
                index,
            )
            row += 1

        summary = format_delta_summary(change)
        if summary and height >= 12:
            self.put(layout.summary_row, 2, summary, curses.A_DIM)
        self.put(layout.message_row, 1, self.message if time.monotonic() < self.message_until else "", curses.A_BOLD)
        self.draw_footer(
            layout.footer_row,
            [("↵ open", "open"), ("v validate", "validate"), ("q close", "close")],
        )

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
    curses.use_default_colors()
    curses.start_color()
    curses.init_pair(1, curses.COLOR_CYAN, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_RED, -1)
    try:
        curses.mousemask(curses.ALL_MOUSE_EVENTS | getattr(curses, "REPORT_MOUSE_POSITION", 0))
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
