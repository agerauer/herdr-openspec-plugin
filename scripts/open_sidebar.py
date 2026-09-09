#!/usr/bin/env python3
"""Open (or focus) the OpenSpec review pane beside the invoking pane."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from typing import Any, Iterable


PLUGIN_ID = "herdr.openspec-review"
ENTRYPOINT = "review"


def project_token(project: Path) -> str:
    import hashlib

    return hashlib.sha256(str(project.resolve()).encode()).hexdigest()[:16]


def run_json(args: list[str]) -> Any:
    completed = subprocess.run(args, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Herdr returned invalid JSON: {error}") from error


def dictionaries(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from dictionaries(child)
    elif isinstance(value, list):
        for child in value:
            yield from dictionaries(child)


def value_for(value: Any, key: str) -> str | None:
    for item in dictionaries(value):
        candidate = item.get(key)
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def pane_cwd(herdr: str, pane_id: str, context: Any) -> Path:
    try:
        pane = run_json([herdr, "pane", "get", pane_id])
    except RuntimeError:
        pane = {}

    for source in (pane, context):
        for key in ("foreground_cwd", "focused_pane_cwd", "workspace_cwd", "cwd", "root", "path"):
            candidate = value_for(source, key)
            if candidate:
                path = Path(candidate).expanduser()
                if path.is_dir():
                    return path.resolve()
    return Path.cwd().resolve()


def openspec_project(path: Path) -> Path:
    for candidate in (path, *path.parents):
        if (candidate / "openspec").is_dir():
            return candidate
    return path


def plugin_pane(value: Any, workspace_id: str, project: Path) -> str | None:
    expected_token = project_token(project)
    for item in dictionaries(value):
        pane_id = item.get("pane_id")
        if not isinstance(pane_id, str):
            continue
        if item.get("workspace_id") not in (None, workspace_id):
            continue
        tokens = item.get("tokens", {})
        if not isinstance(tokens, dict) or tokens.get("openspec_review") != expected_token:
            continue
        return pane_id
    return None


def subtree_contains(node: Any, pane_id: str) -> bool:
    return any(item.get("pane_id") == pane_id for item in dictionaries(node))


def split_path(node: Any, pane_id: str, path: list[bool] | None = None):
    path = path or []
    if not isinstance(node, dict):
        return None
    first, second = node.get("first"), node.get("second")
    if first is not None and second is not None:
        if subtree_contains(first, pane_id) and subtree_contains(second, pane_id):
            return path, None
        if subtree_contains(first, pane_id):
            nested = split_path(first, pane_id, [*path, False])
            return nested or (path, False)
        if subtree_contains(second, pane_id):
            nested = split_path(second, pane_id, [*path, True])
            return nested or (path, True)
    for child in node.values():
        found = split_path(child, pane_id, path)
        if found:
            return found
    return None


def socket_request(method: str, params: dict[str, Any]) -> Any:
    socket_path = os.environ.get("HERDR_SOCKET_PATH")
    if not socket_path or os.name == "nt":
        return None
    request = {"id": "openspec-review-layout", "method": method, "params": params}
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(2)
        client.connect(socket_path)
        client.sendall((json.dumps(request) + "\n").encode())
        response = bytearray()
        while b"\n" not in response:
            chunk = client.recv(65536)
            if not chunk:
                break
            response.extend(chunk)
        return json.loads(bytes(response).split(b"\n", 1)[0]) if response else None


def resize_sidebar(herdr: str, pane_id: str) -> None:
    """Make the new right-hand pane roughly 30% wide when layout data permits."""
    try:
        response = socket_request("layout.export", {"pane_id": pane_id})
        tab_id = value_for(response, "tab_id")
        root = next(
            (item["root"] for item in dictionaries(response) if isinstance(item.get("root"), dict)),
            None,
        )
        found = split_path(root, pane_id)
        if not tab_id or not found:
            return
        path, in_second = found
        ratio = 0.70 if in_second is not False else 0.30
        socket_request("layout.set_split_ratio", {"tab_id": tab_id, "path": path, "ratio": ratio})
    except (OSError, RuntimeError, StopIteration, ValueError, json.JSONDecodeError):
        return


def notify(herdr: str, message: str) -> None:
    subprocess.run(
        [herdr, "notification", "show", "OpenSpec Review", "--body", message[:220]],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def main() -> int:
    if os.environ.get("HERDR_ENV") != "1":
        print("This action must run inside Herdr.", file=sys.stderr)
        return 1

    herdr = os.environ.get("HERDR_BIN_PATH", "herdr")
    pane_id = os.environ.get("HERDR_PANE_ID")
    workspace_id = os.environ.get("HERDR_WORKSPACE_ID", "")
    if not pane_id:
        notify(herdr, "No invoking pane was provided by Herdr.")
        return 1

    try:
        context = json.loads(os.environ.get("HERDR_PLUGIN_CONTEXT_JSON", "{}"))
    except json.JSONDecodeError:
        context = {}

    project = openspec_project(pane_cwd(herdr, pane_id, context))
    plugin_root = Path(
        os.environ.get("HERDR_PLUGIN_ROOT", Path(__file__).resolve().parents[1])
    ).resolve()
    try:
        panes = run_json([herdr, "pane", "list", "--workspace", workspace_id])
        existing = plugin_pane(panes, workspace_id, project)
        if existing:
            run_json([herdr, "plugin", "pane", "focus", existing])
            return 0

        response = run_json(
            [
                herdr,
                "plugin",
                "pane",
                "open",
                "--plugin",
                PLUGIN_ID,
                "--entrypoint",
                ENTRYPOINT,
                "--placement",
                "split",
                "--target-pane",
                pane_id,
                "--direction",
                "right",
                "--cwd",
                str(plugin_root),
                "--env",
                f"OPENSPEC_PROJECT={project}",
                "--focus",
            ]
        )
        opened = plugin_pane(response, workspace_id, project)
        for _ in range(20):
            if opened:
                break
            time.sleep(0.05)
            opened = plugin_pane(
                run_json([herdr, "pane", "list", "--workspace", workspace_id]),
                workspace_id,
                project,
            )
        if opened:
            resize_sidebar(herdr, opened)
        return 0
    except RuntimeError as error:
        notify(herdr, str(error) or "Could not open the review pane.")
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
