#!/usr/bin/env python3
"""Dependency-free terminal UI for reviewing active OpenSpec changes."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import curses
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import textwrap
import time
from typing import Any


CHECKBOX = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+", re.MULTILINE)
HEADING = re.compile(r"^#{1,6}\s+(.*)$")
DELTA_HEADING = re.compile(r"^##\s+(ADDED|MODIFIED|REMOVED|RENAMED)\s+Requirements?\s*$", re.I)
REQUIREMENT = re.compile(r"^###\s+Requirement:\s*(.+?)\s*$", re.I)


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
    validation: str | None = None
    validation_detail: str = ""

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


def find_project(start: Path) -> Path:
    start = start.resolve()
    for candidate in (start, *start.parents):
        if (candidate / "openspec").is_dir():
            return candidate
    return start


def configured_project() -> Path:
    """Resolve the target project independently from the plugin process cwd."""
    configured = os.environ.get("OPENSPEC_PROJECT")
    return find_project(Path(configured).expanduser() if configured else Path.cwd())


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

    prefix = "› " if selected else "  "
    name_width = width - len(prefix) - len(progress) - 1
    if name_width <= 0:
        return (" " * (width - len(progress)) + progress)[-width:]

    name = change.name
    if len(name) > name_width:
        name = "…" if name_width == 1 else name[: name_width - 1] + "…"
    return f"{prefix}{name:<{name_width}} {progress}"


def format_delta_summary(change: Change) -> str:
    labels = {"ADDED": "+", "MODIFIED": "~", "REMOVED": "−", "RENAMED": "→"}
    return "  ".join(f"{labels[key]}{count}" for key, count in change.deltas.items())


def discover_changes(project: Path) -> list[Change]:
    changes_dir = project / "openspec" / "changes"
    if not changes_dir.is_dir():
        return []
    changes: list[Change] = []
    for directory in sorted(changes_dir.iterdir(), key=lambda item: item.name.lower()):
        if not directory.is_dir() or directory.name.startswith(".") or directory.name == "archive":
            continue
        metadata = parse_metadata(directory / ".openspec.yaml")
        artifacts: list[Artifact] = []

        def append(key: str, title: str, path: Path, required: bool = True) -> None:
            content = read_artifact(path)
            item = Artifact(key, title, path, required, content)
            artifacts.append(item)

        append("proposal", "Proposal", directory / "proposal.md")
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
        append("design", "Design", directory / "design.md", required=False)
        append("tasks", "Tasks", directory / "tasks.md")

        task_content = next((item.content for item in artifacts if item.key == "tasks"), "")
        checks = CHECKBOX.findall(task_content)
        change = Change(
            name=directory.name,
            path=directory,
            goal=str(metadata.get("goal", "")),
            schema=str(metadata.get("schema", "spec-driven")),
            artifacts=artifacts,
            deltas=delta_counts([item.content for item in artifacts if item.key.startswith("spec:")]),
            tasks_done=sum(value.lower() == "x" for value in checks),
            tasks_total=len(checks),
        )
        if not change.goal:
            proposal = next((item.content for item in artifacts if item.key == "proposal"), "")
            change.goal = first_summary(proposal)
        changes.append(change)
    return changes


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
        self.message = ""
        self.message_until = 0.0
        self.last_scan = 0.0
        self.last_fingerprint = ""
        self.reload(force=True)

    @property
    def change(self) -> Change | None:
        return self.changes[self.change_index] if self.changes else None

    def fingerprint(self) -> str:
        root = self.project / "openspec" / "changes"
        if not root.exists():
            return "missing"
        parts = []
        try:
            for path in root.glob("**/*"):
                if path.is_file():
                    stat = path.stat()
                    parts.append(f"{path}:{stat.st_mtime_ns}:{stat.st_size}")
        except OSError:
            pass
        return sha256("\n".join(sorted(parts)).encode()).hexdigest()

    def reload(self, force: bool = False) -> None:
        fingerprint = self.fingerprint()
        if not force and fingerprint == self.last_fingerprint:
            return
        selected_name = self.change.name if self.change else None
        viewer_key = self.viewer.key if self.viewer else None
        self.changes = discover_changes(self.project)
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
                ["openspec", "validate", change.name, "--no-interactive"],
                cwd=self.project,
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
        editor = os.environ.get("EDITOR", "vi")
        try:
            curses.endwin()
            subprocess.run([*shlex.split(editor), str(self.viewer.path)], cwd=self.project, check=False)
        finally:
            self.screen.refresh()
            self.reload(force=True)

    def move(self, amount: int) -> None:
        if self.viewer:
            height, _ = self.screen.getmaxyx()
            self.viewer_offset = max(0, self.viewer_offset + amount * max(1, height - 5))
        elif self.focus == "changes":
            self.change_index = max(0, min(len(self.changes) - 1, self.change_index + amount))
            self.artifact_index = 0
        elif self.change:
            self.artifact_index = max(
                0, min(len(self.change.artifacts) - 1, self.artifact_index + amount)
            )

    def handle(self, key: int) -> bool:
        if key in (ord("q"), ord("Q")):
            return False
        if key == curses.KEY_RESIZE:
            return True
        if key in (ord("r"), ord("R")):
            self.reload(force=True)
            self.say("Refreshed")
        elif key in (ord("v"), ord("V")):
            self.validate()
        elif key == ord("e") and self.viewer:
            self.edit()
        elif key in (curses.KEY_UP, ord("k")):
            self.move(-1)
        elif key in (curses.KEY_DOWN, ord("j")):
            self.move(1)
        elif key == curses.KEY_PPAGE:
            self.move(-1)
        elif key == curses.KEY_NPAGE:
            self.move(1)
        elif key in (curses.KEY_LEFT, ord("h"), 27):
            if self.viewer:
                self.viewer = None
                self.viewer_offset = 0
            else:
                self.focus = "changes"
        elif key in (9, curses.KEY_RIGHT, ord("l")):
            if not self.viewer and self.change:
                self.focus = "artifacts" if self.focus == "changes" else "changes"
        elif key in (10, 13, curses.KEY_ENTER):
            if self.focus == "changes" and self.change:
                self.focus = "artifacts"
            elif self.change and self.change.artifacts:
                artifact = self.change.artifacts[self.artifact_index]
                if artifact.exists:
                    self.viewer = artifact
                    self.viewer_offset = 0
                else:
                    self.say("Artifact does not exist yet")
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
        if not (self.project / "openspec").is_dir():
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
        self.put(0, 1, f" ‹ {artifact.title} ", curses.A_BOLD | curses.color_pair(1))
        self.put(1, 2, change.name, curses.A_DIM)
        self.put(2, 0, "─" * max(0, width - 1), curses.A_DIM)
        wrapped: list[str] = []
        for line in clean_markdown(artifact.content):
            if not line:
                wrapped.append("")
            else:
                wrapped.extend(textwrap.wrap(line, max(8, width - 4), replace_whitespace=False) or [""])
        visible = max(0, height - 5)
        max_offset = max(0, len(wrapped) - visible)
        self.viewer_offset = min(self.viewer_offset, max_offset)
        for row, line in enumerate(wrapped[self.viewer_offset : self.viewer_offset + visible], start=3):
            style = curses.A_BOLD if line.isupper() and line.strip("─ ") else 0
            self.put(row, 2, line, style)
        if max_offset:
            percent = round(100 * self.viewer_offset / max_offset) if max_offset else 100
            self.put(height - 2, max(1, width - 6), f"{percent:>3}%", curses.A_DIM)
        self.put(height - 1, 1, "← back  e edit  q close", curses.A_DIM)

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
        self.put(3, 1, "CHANGES", curses.A_BOLD)
        max_changes = max(1, min(5, height // 4))
        start = max(0, min(self.change_index - max_changes // 2, len(self.changes) - max_changes))
        row = 4
        for index in range(start, min(len(self.changes), start + max_changes)):
            item = self.changes[index]
            selected = index == self.change_index
            style = curses.A_REVERSE if selected and self.focus == "changes" else 0
            rendered = format_change_row(item, max(0, width - 2), selected)
            self.put(row, 1, rendered, style | (curses.A_BOLD if selected else 0))
            row += 1

        row += 1
        self.put(row, 1, change.status, curses.A_BOLD | status_style)
        if change.goal:
            goal_lines = textwrap.wrap(change.goal, max(10, width - 4))[:2]
            for line in goal_lines:
                row += 1
                self.put(row, 2, line, curses.A_DIM)
        row += 2
        self.put(row, 1, "ARTIFACTS", curses.A_BOLD)
        row += 1

        remaining = max(0, height - row - 5)
        artifact_start = max(
            0,
            min(self.artifact_index - remaining // 2, len(change.artifacts) - remaining),
        )
        for index in range(artifact_start, min(len(change.artifacts), artifact_start + remaining)):
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
            row += 1

        summary = format_delta_summary(change)
        if summary and height >= 12:
            self.put(height - 4, 2, summary, curses.A_DIM)
        self.put(height - 2, 1, self.message if time.monotonic() < self.message_until else "", curses.A_BOLD)
        self.put(height - 1, 1, "↵ open  v validate  q close", curses.A_DIM)

    def draw(self) -> None:
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
