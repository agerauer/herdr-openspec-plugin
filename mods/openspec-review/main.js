// OpenSpec Review: a Herdr pane beside your coding agent that lists every active
// OpenSpec change as a card, renders its documents, and hands the next step to
// the agent. Opened with `mod.open:openspec-review` (it splits itself in to the
// right of the focused pane) or `pane.split {direction, mod: "openspec-review", props: {folder}}`.
import { View, div } from "gpui-kit";
import { v_flex, h_flex, TextView } from "gpui-base";
import {
  exec, hc, readTextFile, watchFolder, spaces, panes, focused, agents, theme, run, props,
  closeOverlay, nextCommand, settings,
} from "herdr";
import * as M from "./model.js";

const MOD = "openspec-review";
const CARD_H = 90;
const HEAD_H = 22;
const LOAD_TIMEOUT = 45000;
const LINE_PX = 20;
const CHAR_PX = 7.4; // approximate width of one 13px UI character, for fitting card lines
// Reads write nothing under .git, so the folder watch doesn't see our own queries.
const READ = ["--no-optional-locks", "-c", "core.fsmonitor=false", "-c", "diff.autoRefreshIndex=false"];

// ---- Machine access -----------------------------------------------------------------

async function tryExec(cmd, args, options) {
  try { return await exec(cmd, args, options); } catch { return null; }
}
async function git(dir, args, on) {
  const r = await tryExec("git", ["-C", dir, ...READ, ...args], { on });
  return r && r.code === 0 ? r.stdout.trim() : null;
}
const lines = (text) => (text || "").split("\n").map((l) => l.trim()).filter(Boolean);

/** Git toplevel, else the highest ancestor with an `openspec/` child, else the folder. */
async function resolveSearchRoot(start, on) {
  const top = await git(start, ["rev-parse", "--show-toplevel"], on);
  if (top) return top;
  const r = await tryExec("sh", ["-c", 'd=$1; f=; while :; do [ -d "$d/openspec" ] && f=$d; [ "$d" = / ] && break; d=$(dirname "$d"); done; printf %s "${f:-$1}"', "sh", start], { on });
  return r?.stdout || start;
}

/** `openspec/` directories at the root and up to two levels below, skipping vendor and dot dirs. */
async function discoverProjects(root, on) {
  const skip = M.SKIPPED_DIRS.flatMap((name, i) => (i ? ["-o", "-name", name] : ["-name", name]));
  const r = await tryExec("find", [root, "-mindepth", "1", "-maxdepth", "3",
    "(", "-type", "d", "(", ...skip, "-o", "-name", ".*", ")", "-prune", ")", "-o",
    "(", "-type", "d", "-name", "openspec", "-print", "-prune", ")"], { on });
  return [...new Set(lines(r?.stdout).map(M.dirname))].sort();
}

/** One root's active changes, with their documents, task counts and summaries. */
async function loadProjectChanges(root, project, on) {
  const dir = `${project}/openspec/changes`;
  const r = await tryExec("find", [dir, "-mindepth", "1",
    "(", "-path", `${dir}/archive`, "-prune", ")", "-o", "(", "-type", "d", "-print", ")", "-o",
    "(", "-type", "f", "(", "-name", "*.md", "-o", "-name", ".openspec.yaml", ")", "-print", ")"], { on });
  const folders = M.groupChangeFiles(dir, lines(r?.stdout));
  const names = Object.keys(folders).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
  return Promise.all(names.map(async (folder) => {
    const files = folders[folder], path = `${dir}/${folder}`;
    const read = (name) => readTextFile(`${path}/${name}`, { on }).catch(() => null);
    const [yaml, proposal, tasks] = await Promise.all([
      files.yaml ? read(".openspec.yaml") : null,
      files.docs.includes("proposal.md") ? read("proposal.md") : null,
      files.docs.includes("tasks.md") ? read("tasks.md") : null,
    ]);
    const metadata = M.parseMetadata(yaml);
    const artifacts = M.buildArtifacts(path, files, metadata);
    const { done, total } = M.countTasks(tasks);
    return {
      name: M.displayChangeName(root, project, folder), folder, project, path, artifacts,
      tasksDone: done, tasksTotal: total,
      missingRequired: artifacts.filter((a) => a.required && !a.exists).length,
      goal: String(metadata.goal || "") || M.firstSummary(proposal),
      sig: JSON.stringify([files, proposal, tasks, yaml]),
      author: null, touched: false, activity: 0,
    };
  }));
}

/** Folder → creating commit for one root, plus who this checkout belongs to;
 *  null when it isn't a Git worktree or the query fails. */
async function loadAuthors(project, on) {
  if (await git(project, ["rev-parse", "--is-inside-work-tree"], on) !== "true") return null;
  const [out, email, name] = await Promise.all([
    git(project, ["log", "--diff-filter=A", "--format=C|%ae|%an", "--name-only", "--", "openspec/changes"], on),
    git(project, ["config", "user.email"], on),
    git(project, ["config", "user.name"], on),
  ]);
  return out === null ? null : { creators: M.parseChangeCreators(out), me: { email: email || "", name: name || "" } };
}

/** Which active changes differ from the default branch's merge base, and how recently. */
async function loadWorktree(root, projects, on) {
  if (await git(root, ["rev-parse", "--is-inside-work-tree"], on) !== "true") return null;
  const remote = await git(root, ["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"], on);
  let base = null;
  for (const ref of [...new Set([remote, "refs/remotes/origin/main", "refs/heads/main", "refs/remotes/origin/master", "refs/heads/master"])]) {
    if (!ref || !(await git(root, ["rev-parse", "--verify", "--quiet", `${ref}^{commit}`], on))) continue;
    const mergeBase = await git(root, ["merge-base", "HEAD", ref], on);
    if (mergeBase) { base = mergeBase; break; }
  }
  if (!base) return null;
  const specs = M.changePathspecs(root, projects);
  if (!specs.length) return null;
  const [branch, top, tracked, untracked, log] = await Promise.all([
    git(root, ["branch", "--show-current"], on),
    git(root, ["rev-parse", "--show-toplevel"], on),
    git(root, ["diff", "--name-only", "--relative", base, "--", ...specs], on),
    git(root, ["ls-files", "--others", "--exclude-standard", "--", ...specs], on),
    git(root, ["log", "--format=%ct", "--name-only", "--relative", `${base}..HEAD`, "--", ...specs], on),
  ]);
  if ([branch, top, tracked, untracked, log].includes(null)) return null;
  const paths = [...new Set([...lines(tracked), ...lines(untracked)])].filter((p) => M.changeIdentityFromPath(p)).sort();
  const mtimes = {};
  if (paths.length) {
    const r = await tryExec("sh", ["-c", 'cd "$1" || exit; shift; for f; do t=$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null) && printf "%s\\t%s\\n" "$t" "$f"; done', "sh", root, ...paths.slice(0, 400)], { on });
    for (const line of lines(r?.stdout)) { const tab = line.indexOf("\t"); mtimes[line.slice(tab + 1)] = Number(line.slice(0, tab)) || 0; }
  }
  return { branch, worktreeName: M.basename(top), activity: M.touchedActivity(paths, mtimes, M.parseCommitActivity(log)) };
}

async function loadWorkspace(start, on) {
  const root = await resolveSearchRoot(start, on);
  const projects = await discoverProjects(root, on);
  const [perProject, snapshot] = await Promise.all([
    Promise.all(projects.map(async (project) => {
      const [changes, authors] = await Promise.all([loadProjectChanges(root, project, on), loadAuthors(project, on)]);
      if (authors) for (const c of changes) {
        const creator = authors.creators[c.folder];
        c.author = creator ? M.githubLoginOrName(creator.email, creator.name) || M.LOCAL_AUTHOR : M.LOCAL_AUTHOR;
        c.mine = !creator || M.isOwnCreator(creator, authors.me); // uncommitted changes are yours
      }
      return changes;
    })),
    loadWorktree(root, projects, on),
  ]);
  const changes = perProject.flat();
  if (snapshot) for (const c of changes) {
    c.touched = c.name in snapshot.activity;
    c.activity = snapshot.activity[c.name] ?? 0;
  }
  return { root, projects, changes: M.ownFirst(M.sortChanges(changes, snapshot)) };
}

// ---- The pane ------------------------------------------------------------------------

const STATE_COLOR = { INVALID: "ansi1", DRAFT: "dim", READY: "ansi6", "IN PROGRESS": "ansi3", DONE: "ansi2" };
const GROUP_COLOR = { standard: "ansi6", doc: "ansi3", spec: "ansi2" };
/** A theme colour with alpha (0–1), for tinted backgrounds. */
const tint = (color, alpha) => /^#[0-9a-f]{6}$/i.test(color || "") ? color + Math.round(alpha * 255).toString(16).padStart(2, "0") : color;
const isClaude = (a) => a.program?.key === "claude" || a.app === "claude-code" || a.app === "claude";

export default class OpenSpecReview extends View {
  init(_props, cx) {
    if (props()?.overlay) return this.launch();
    this.all = []; this.changes = []; this.index = 0; this.projects = null; this.root = null; this.project = null; this.places = {};
    this.doc = null; this.offset = 0; this.docHeight = 0; this.viewHeight = 0; this.width = 0;
    this.validations = {}; this.message = ""; this.loading = false; this.first = true;
    this.handle = cx.focus_handle();
    this.listOffset = 0; this.listHeight = 0; this.reveal = true;
    const p = props() || {};
    // A layout block with `props.panel` (a side panel shared by every space) follows the
    // focused tab's folder instead of keeping the one it started with.
    this.panel = Boolean(p.panel);
    this.on = p.machine ?? null;
    this.start = p.folder || this.guessFolder();
    this.followedTab = focused()?.tab ?? null;
    this.reload(cx);
    cx.timer.every(10000, (cx) => this.reload(cx));
    if (this.panel) cx.timer.every(700, (cx) => this.follow(cx));
    cx.timer.every(3000, (cx) => { if (this.on) this.refreshDoc(cx); }); // no file watching on other machines
    cx.spawn(async (cx) => {
      for (;;) {
        const c = await nextCommand();
        if (c === "focus") this.handle.focus();
        else this.act(c, cx);
        cx.notify();
      }
    });
    // Take the keyboard only when Herdr just focused this pane (a fresh split), never on a
    // restart, tab switch or reload while someone is typing elsewhere.
    cx.timer.after(50, () => { const me = this.myPane(); if (me && focused()?.pane === me.pane) this.handle.focus(); });
  }

  /** Opened as an overlay (mod.open): split this mod in beside the focused pane, then go. */
  launch() {
    this.launcher = true;
    const f = focused(), overlay = props().overlay;
    const space = spaces().find((s) => s.id === f?.space) ?? spaces().find((s) => s.active);
    const existing = panes().find((p) => p.mod === MOD && p.tab === f?.tab);
    if (existing) run("pane.focus", { pane: existing.pane });
    else {
      const source = f?.pane ? panes().find((p) => p.pane === f.pane) : null;
      run("pane.split", {
        direction: "right", ...(source ? { pane: source.pane } : {}), mod: MOD,
        props: { folder: source?.cwd || f?.cwd || space?.folder || "", machine: space?.machine ?? null, agent: source?.terminal ?? null },
      });
    }
    closeOverlay(overlay);
  }

  /** As a panel: follow the focused terminal's folder. Only a move to another repository
   *  (or machine) starts over; a `cd` inside the same one just keeps the list. */
  follow(cx) {
    if (!this.panel || props()?.folder) return;
    const f = focused();
    if (!f) return;
    // Focus on the panel itself (or another mod) says nothing new about where you work.
    if (!f.cwd && f.tab === this.followedTab && this.start) return;
    this.followedTab = f.tab;
    const space = spaces().find((s) => s.id === f.space);
    const on = space?.machine ?? null;
    const folder = f.cwd || this.tabFolder(f.tab) || space?.folder || "";
    if (!folder || (folder === this.followed && on === this.on)) return;
    const want = `${on ?? ""}\n${folder}`;
    if (this.following === want && Date.now() - this.followingSince < 5000) return; // resolving it
    this.following = want; this.followingSince = Date.now();
    const token = (this.followToken = (this.followToken || 0) + 1);
    cx.spawn(async (cx) => {
      const root = await resolveSearchRoot(folder, on);
      if (token !== this.followToken) return; // focus moved on meanwhile
      this.followed = folder; this.following = null;
      if (root === this.root && on === this.on) { this.start = folder; return; }
      this.on = on; this.start = folder;
      this.root = null; this.projects = null; this.all = []; this.changes = [];
      this.project = null; this.places = {}; this.index = 0; this.doc = null;
      this.listOffset = 0; this.first = true; this.error = null;
      cx.notify();
      this.reload(cx);
    });
  }

  /** The focused terminal's folder in a tab, else its first terminal's. */
  tabFolder(tab) {
    const inTab = panes().filter((p) => p.tab === tab && p.cwd);
    return (inTab.find((p) => p.focused) ?? inTab[0])?.cwd || "";
  }

  guessFolder() {
    const f = focused();
    const tab = (this.panel ? null : this.myPane()?.tab) ?? f?.tab;
    const space = spaces().find((s) => s.tabs.some((t) => t.id === tab)) ?? spaces().find((s) => s.active);
    this.on = this.on ?? space?.machine ?? null;
    const folder = (this.panel && f?.cwd) || this.tabFolder(tab) || space?.folder || "";
    this.followed = folder;
    return folder;
  }

  myPane() {
    const p = props() || {};
    if (p.pane) return panes().find((x) => x.pane === p.pane);
    const mine = panes().filter((x) => x.mod === MOD);
    return mine.find((x) => x.focused) ?? mine.find((x) => x.tab === focused()?.tab) ?? mine[0];
  }

  get change() { return this.changes[this.index] ?? null; }

  say(message, cx, ms = 4000) {
    this.message = message;
    const token = (this.messageToken = (this.messageToken || 0) + 1);
    cx.timer.after(ms, (cx) => { if (this.messageToken === token) { this.message = ""; cx.notify(); } });
    cx.notify();
  }

  // ---- Loading ----

  reload(cx) {
    if (!this.start) return;
    // One load at a time; a load that never came back (its task was dropped, or a command
    // hung) must not block the pane forever, so after a while a new one replaces it.
    if (this.loading && Date.now() - this.loadingSince < LOAD_TIMEOUT) { this.pending = true; return; }
    const gen = (this.loadGen = (this.loadGen || 0) + 1);
    this.loading = true; this.loadingSince = Date.now();
    const start = this.start, on = this.on;
    cx.spawn(async (cx) => {
      try {
        const { root, projects, changes } = await loadWorkspace(start, on);
        if (gen !== this.loadGen) return; // replaced by a newer load
        // The panel moved to another folder while this ran: drop it and load the new one.
        if (start !== this.start || on !== this.on) { this.pending = true; return; }
        const selected = this.change?.name;
        for (const c of changes) this.applyState(c);
        this.root = root; this.projects = projects; this.all = changes; this.error = null;
        // Start on the project holding the top-ranked change (the branch's), then stay put.
        if (this.first || !projects.includes(this.project)) this.project = (this.first && changes[0]?.project) || projects[0] || null;
        this.changes = changes.filter((c) => c.project === this.project);
        const kept = selected ? this.changes.findIndex((c) => c.name === selected) : -1;
        this.index = M.clamp(kept >= 0 ? kept : this.first ? 0 : this.index, 0, Math.max(0, this.changes.length - 1));
        if (this.first) { this.first = false; this.reveal = true; }
        if (this.doc) {
          const change = this.change, artifact = change?.artifacts.find((a) => a.key === this.doc.key);
          if (!change || change.name !== this.doc.change || !artifact?.exists) this.doc = null;
          else await this.refreshDoc(cx);
        }
        this.watch(projects, cx);
      } catch (e) { if (gen === this.loadGen) this.error = String(e); }
      finally {
        if (gen === this.loadGen) {
          this.loading = false; cx.notify();
          if (this.pending) { this.pending = false; this.reload(cx); }
        }
      }
    });
  }

  applyState(change) {
    const v = this.validations[change.name];
    change.validation = v && v.sig === change.sig ? v.result : null;
    change.state = M.deriveState(change);
  }

  watch(projects, cx) {
    const key = projects.join("\n");
    if (this.on || this.watchKey === key) return;
    this.watchKey = key;
    for (const project of projects) {
      cx.spawn(async (cx) => {
        try {
          while (this.watchKey === key) {
            await watchFolder(`${project}/openspec`);
            if (this.watchKey !== key) return;
            await this.refreshDoc(cx);
            const token = (this.watchToken = (this.watchToken || 0) + 1);
            cx.timer.after(250, (cx) => { if (this.watchToken === token) this.reload(cx); });
          }
        } catch { if (this.watchKey === key) this.watchKey = null; }
      });
    }
  }

  // ---- Documents ----

  artifact(key, change = this.change) { return change?.artifacts.find((a) => a.key === key) ?? null; }

  /** Re-reads the open document; an unchanged file changes nothing, a removed one shows empty. */
  async refreshDoc(cx) {
    const doc = this.doc;
    if (!doc) return;
    const text = (await readTextFile(doc.path, { on: this.on }).catch(() => null)) ?? "";
    if (this.doc === doc && text !== doc.text) { doc.text = text; cx.notify(); }
  }

  open(key, cx) {
    const change = this.change;
    if (!change) return;
    const artifact = this.artifact(key);
    if (!artifact || !artifact.exists) {
      this.say(`${artifact?.title ?? "That document"} does not exist yet`, cx);
      return;
    }
    const same = this.doc && this.doc.change === change.name && this.doc.key === key;
    const doc = same ? this.doc : { change: change.name, key, path: artifact.path, text: "", loaded: false };
    if (!same) { this.offset = 0; this.docHeight = 0; }
    this.doc = doc;
    this.handle.focus();
    cx.spawn(async (cx) => {
      const text = (await readTextFile(doc.path, { on: this.on }).catch(() => null)) ?? "";
      if (this.doc === doc) { doc.text = text; doc.loaded = true; cx.notify(); }
    });
    cx.notify();
  }

  openSpec(cx) {
    const specs = this.change?.artifacts.filter((a) => a.key.startsWith("spec:")) ?? [];
    if (!specs.length) return this.say("Specs do not exist yet", cx);
    const at = this.doc ? specs.findIndex((a) => a.key === this.doc.key) : -1;
    this.open(specs[at < 0 ? 0 : (at + 1) % specs.length].key, cx);
  }

  step(direction, cx) {
    const order = M.documentOrder(this.change?.artifacts ?? []);
    const at = order.indexOf(this.doc?.key);
    const next = at + direction;
    if (direction < 0 && next < 0) return this.back(cx);
    if (next >= 0 && next < order.length) this.open(order[next], cx);
  }

  back(cx) { this.doc = null; this.handle.focus(); this.reveal = true; cx.notify(); }

  scrollBy(px, cx) {
    const max = Math.max(0, this.docHeight - this.viewHeight);
    const offset = M.clamp(this.offset + px, 0, max);
    if (offset !== this.offset) { this.offset = offset; cx.notify(); }
  }

  // ---- Actions ----

  select(index, cx) {
    if (!this.changes.length) return;
    this.index = M.clamp(index, 0, this.changes.length - 1);
    this.reveal = true;
    this.handle.focus();
    cx.notify();
  }

  /** Shows another project's changes, keeping each project's selection. */
  showProject(project, cx) {
    if (!this.projects?.includes(project) || project === this.project) return;
    if (this.change) this.places[this.project] = this.change.name;
    this.project = project; this.doc = null; this.listOffset = 0;
    this.changes = this.all.filter((c) => c.project === project);
    const kept = this.changes.findIndex((c) => c.name === this.places[project]);
    this.index = Math.max(0, kept); this.reveal = true;
    this.handle.focus();
    cx.notify();
  }

  stepProject(delta, cx) {
    const list = this.projects || [];
    if (list.length < 2) return;
    const i = list.indexOf(this.project);
    this.showProject(list[(i + delta + list.length) % list.length], cx);
  }

  projectLabel(project) {
    return project === this.root ? M.basename(project) : M.relativeTo(this.root, project);
  }

  validate(cx) {
    const change = this.change;
    if (!change) return;
    this.say("Validating…", cx, 30000);
    cx.spawn(async (cx) => {
      const r = await tryExec("openspec", ["validate", change.folder, "--no-interactive"], { cwd: change.project, on: this.on });
      const valid = r?.code === 0;
      this.validations[change.name] = { result: valid ? "valid" : "invalid", sig: change.sig };
      for (const c of this.all) this.applyState(c);
      const detail = r ? lines(valid ? r.stdout : r.stderr || r.stdout)[0] : "";
      this.say(!r ? "Could not run openspec validate" : valid ? "Valid OpenSpec change" : `Validation failed${detail ? ` — ${detail}` : ""}`, cx, 6000);
    });
  }

  edit(cx) {
    const change = this.change;
    if (!change) return;
    cx.spawn(async (cx) => {
      const r = await tryExec("code", [change.path], { on: this.on });
      if (!r) this.say("Install `code` on PATH to open the change folder", cx);
      else if (r.code !== 0) this.say(`code failed: ${lines(r.stderr)[0] ?? r.code}`, cx);
    });
  }

  /** Hands the change's next step to the Claude agent this pane was opened beside. */
  send(change, cx) {
    const command = M.agentCommandFor(change), action = M.actionForState(change.state);
    if (!command) return;
    const me = this.myPane(), tab = me?.tab ?? focused()?.tab;
    const inTab = agents().filter((a) => a.tab === tab);
    const opener = props()?.agent;
    const target = inTab.find((a) => a.address === opener || a.address.endsWith(`/${opener}`)) ?? inTab.find(isClaude) ?? inTab[0];
    if (!target) return this.say("No agent in this tab to send to", cx);
    if (!isClaude(target)) return this.say(`${target.program?.name ?? "That agent"} is not a Claude Code agent — nothing sent`, cx);
    if (target.status === "blocked") return this.say("The agent is busy — waiting on its own input", cx);
    this.say(`Sending ${action}…`, cx, 30000);
    cx.spawn(async (cx) => {
      let r = null;
      try { r = await hc(["send", target.address, command]); } catch {}
      if (!r || r.code !== 0) return this.say(`Could not send to the agent${r ? ` — ${lines(r.stderr)[0] ?? ""}` : ""}`, cx);
      this.say(`Sent ${action} → ${target.title || target.program?.name || target.address}`, cx);
      run("pane.focus", { pane: target.pane });
    });
  }

  closePane() {
    // A panel isn't a pane: hide its column (the layout's "panel"), never close a split pane.
    if (this.panel) return run("layout.hide", { id: "panel" });
    const me = this.myPane();
    if (me) run("pane.close", { pane: me.pane });
  }

  /** Every keyboard and footer action, by name. */
  act(name, cx) {
    const change = this.change;
    switch (name) {
      case "up": return this.doc ? this.scrollBy(-LINE_PX, cx) : this.select(this.index - 1, cx);
      case "down": return this.doc ? this.scrollBy(LINE_PX, cx) : this.select(this.index + 1, cx);
      case "pageup": return this.doc ? this.scrollBy(-Math.max(LINE_PX, this.viewHeight - LINE_PX), cx) : this.select(this.index - 5, cx);
      case "pagedown": return this.doc ? this.scrollBy(Math.max(LINE_PX, this.viewHeight - LINE_PX), cx) : this.select(this.index + 5, cx);
      case "left": return this.doc ? this.step(-1, cx) : undefined;
      case "right": return this.doc ? this.step(1, cx) : this.open("proposal", cx);
      case "open": case "proposal": return this.open("proposal", cx);
      case "design": return this.open("design", cx);
      case "tasks": return this.open("tasks", cx);
      case "spec": return this.openSpec(cx);
      case "back": return this.doc ? this.back(cx) : undefined;
      case "send": return change && this.send(change, cx);
      case "validate": return this.validate(cx);
      case "edit": return this.edit(cx);
      case "nextproject": return this.stepProject(1, cx);
      case "prevproject": return this.stepProject(-1, cx);
      case "refresh": this.say("Refreshing…", cx, 1500); return this.reload(cx);
      case "close": return this.closePane();
    }
  }

  onKey(e, cx) {
    if (e.modifiers.control || e.modifiers.platform || e.modifiers.alt) return;
    const name = {
      up: "up", k: "up", down: "down", j: "down", pageup: "pageup", pagedown: "pagedown",
      left: "left", h: "left", right: "right", l: "right", enter: "open", escape: "back",
      p: "proposal", d: "design", t: "tasks", s: "spec", a: "send", v: "validate", e: "edit", r: "refresh", q: "close",
      home: "home", end: "end", "]": "nextproject", "[": "prevproject",
      tab: e.modifiers.shift ? "prevproject" : "nextproject",
    }[e.key];
    if (!name) return;
    cx.stop_propagation();
    if (name === "home") return this.doc ? this.scrollBy(-this.offset, cx) : this.select(0, cx);
    if (name === "end") return this.doc ? this.scrollBy(this.docHeight, cx) : this.select(this.changes.length - 1, cx);
    this.act(name, cx);
  }

  // ---- Drawing ----

  render(cx) {
    // Follow a tab switch right away rather than at the next tick (follow() records the tab).
    const tab = focused()?.tab ?? null;
    if (this.panel && !this.launcher && tab !== this.followedTab && tab !== this.renderedTab) {
      this.renderedTab = tab;
      cx.timer.after(0, (cx) => { this.follow(cx); cx.notify(); });
    }
    if (this.launcher) return div();
    const t = theme();
    const body = this.doc && this.change ? this.renderViewer(t) : this.renderList(t);
    return v_flex().id("osr").size_full().min_h(0).overflow_hidden().bg(t.background).text_color(t.foreground).text_size(13)
      .track_focus(this.handle)
      .on_key_down((e, cx) => this.onKey(e, cx))
      .on_mouse_down("left", () => this.handle.focus())
      .on_size_change((size, cx) => { if (Math.abs(size.width - this.width) > 1) { this.width = size.width; cx.notify(); } })
      .child(body)
      .when(Boolean(this.message), (el) => el.child(div().flex_none().px(14).py(5).border_t(1).border_color(t.border).text_size(12).text_color(t.muted).truncate().child(this.message)))
      .child(this.renderFooter(t));
  }

  header(t, ...children) {
    return h_flex().flex_none().min_h(38).px(12).gap(8).items_center().border_b(1).border_color(t.border).children(children);
  }

  /** The list's rows: "Yours" / "Others" headings (when you own any change here) and cards, with their tops. */
  listRows() {
    const rows = [], tops = [];
    const sections = this.changes.some((c) => c.mine);
    let y = 6;
    this.changes.forEach((c, i) => {
      const prev = this.changes[i - 1];
      if (sections && (i === 0 || prev.mine !== c.mine)) {
        const count = this.changes.filter((x) => x.mine === c.mine).length;
        rows.push({ head: c.mine ? "Yours" : "Others", count, first: i === 0 }); y += i === 0 ? HEAD_H : HEAD_H + 8;
      }
      rows.push({ index: i }); tops[i] = y; y += CARD_H;
    });
    return { rows, tops, height: y };
  }

  /** Keeps the selected card on screen (after a selection change or resize) and the offset in range. */
  fitList() {
    const { tops, height } = this.listRows();
    const max = Math.max(0, height - this.listHeight);
    if (this.reveal && this.listHeight > 0) {
      const top = Math.max(0, (tops[this.index] ?? 0) - (this.index === 0 ? 6 + HEAD_H : HEAD_H)), bottom = (tops[this.index] ?? 0) + CARD_H;
      if (top < this.listOffset) this.listOffset = top;
      else if (bottom > this.listOffset + this.listHeight) this.listOffset = bottom - this.listHeight;
      this.reveal = false;
    }
    this.listOffset = M.clamp(this.listOffset, 0, max);
  }

  scrollList(px, cx) {
    const before = this.listOffset;
    this.listOffset += px; this.fitList();
    if (this.listOffset !== before) cx.notify();
  }

  renderList(t) {
    this.fitList();
    const tabbed = (this.projects?.length ?? 0) > 1;
    const where = this.project ? this.projectLabel(this.project) : this.root ? M.basename(this.root) : "";
    const head = v_flex().flex_none().child(this.header(t,
      div().font_semibold().child("OpenSpec"),
      div().flex_1().min_w(0).truncate().text_color(t.dim).child(tabbed ? (this.root ? M.basename(this.root) : "") : where),
      div().when(this.changes.length > 0, (e) => e.px(6).py(1).rounded(4).border_1().border_color(t.border).text_size(11).text_color(t.muted).child(`${this.changes.length} active`))))
      .when(tabbed, (e) => e.child(this.renderProjectTabs(t)));
    if (!this.changes.length) {
      const none = this.projects && !this.projects.length;
      const [title, hint] = this.error ? ["Could not read OpenSpec changes", this.error]
        : !this.projects ? ["Loading…", ""]
        : none ? ["No OpenSpec project here", "Run `openspec init` in this workspace, then press r."]
        : ["No active changes", "Create one with `openspec new change <name>`, then press r."];
      return v_flex().flex_1().min_h(0).child(head)
        .child(v_flex().p(16).gap(6).child(div().font_semibold().child(title)).child(div().text_color(t.dim).child(hint)));
    }
    return v_flex().flex_1().min_h(0).child(head)
      .child(div().id("osr-list").flex_1().min_h(0).relative().overflow_hidden()
        .on_size_change((size, cx) => { if (Math.abs(size.height - this.listHeight) > 1) { this.listHeight = size.height; this.reveal = true; cx.notify(); } })
        .on_scroll_wheel((e, cx) => this.scrollList(-(e.delta_lines ? e.delta_lines.y * CARD_H / 2 : e.delta.y), cx))
        .child(v_flex().absolute().left(0).right(0).top(6 - this.listOffset)
          .children(this.listRows().rows.map((r) => r.head
            ? h_flex().id(`osr-sec-${r.head}`).h(r.first ? HEAD_H : HEAD_H + 8).px(12).pt(r.first ? 0 : 8).gap(6).items_center().text_size(11)
              .child(div().font_semibold().text_color(t.muted).child(r.head.toUpperCase()))
              .child(div().text_color(t.dim).child(String(r.count)))
              .child(div().flex_1().h(1).bg(t.border))
            : this.card(this.changes[r.index], r.index, t)))));
  }

  renderProjectTabs(t) {
    return h_flex().flex_none().flex_wrap().px(12).py(7).gap(6).border_b(1).border_color(t.border).children(this.projects.map((project, i) => {
      const changes = this.all.filter((c) => c.project === project), on = project === this.project;
      const color = changes.some((c) => c.touched) ? t.accent : t.foreground;
      return h_flex().id(`osr-proj-${i}`).gap(5).px(8).py(2).rounded(6).text_size(12).cursor_pointer().items_center()
        .border_1().border_color(on ? t.accent : "#00000000")
        .when(on, (e) => e.bg(t.selected).font_semibold())
        .hover((s) => s.bg(t.hover))
        .on_click((_e, cx) => this.showProject(project, cx))
        .child(div().text_color(changes.length ? color : t.dim).child(this.projectLabel(project)))
        .child(div().text_size(11).text_color(t.dim).child(String(changes.length)));
    }));
  }

  card(change, index, t) {
    const selected = index === this.index;
    const action = M.actionForState(change.state);
    const room = Math.max(0, (this.width || 400) - 60) / CHAR_PX; // characters a card line holds
    const showAuthor = change.author && change.folder.length + 3 + change.author.length <= room;
    const progress = `${change.tasksDone}/${change.tasksTotal}`;
    const statusChars = change.state.length + 3 + progress.length + (action ? action.length + 6 : 0);
    const artifacts = statusChars + 14 <= room ? ` · ${change.artifacts.length} Artifacts` : "";
    const stateColor = t[STATE_COLOR[change.state]] ?? t.dim;
    return div().id(`osr-card-${index}`).w_full().h(CARD_H).px(8).pb(6).child(
      v_flex().id(`osr-cardbody-${index}`).size_full().px(10).py(7).gap(3).rounded(8).border_1()
        .border_color(selected ? t.accent : t.border).bg(selected ? t.selected : t.surface)
        .cursor_pointer().hover((s) => s.bg(selected ? t.selected : t.hover))
        .on_click((_e, cx) => this.select(index, cx))
        .child(h_flex().min_w(0).items_center()
          .child(div().w(12).flex_none().text_color(t.accent).child(selected ? "›" : ""))
          .child(div().id(`osr-name-${index}`).min_w(0).truncate().font_semibold()
            .text_color(change.touched ? t.accent : t.foreground).hover((s) => s.underline())
            .on_click((_e, cx) => { cx.stop_propagation(); this.select(index, cx); this.open("proposal", cx); })
            .child(change.folder))
          .when(Boolean(showAuthor), (e) => e.child(div().flex_none().text_color(t.dim).child(`${M.SEP}${change.author}`))))
        .child(h_flex().pl(12).min_w(0).items_center().text_size(12)
          .child(div().flex_none().font_semibold().text_color(stateColor).child(change.state))
          .child(div().min_w(0).truncate().text_color(t.muted).child(` · ${progress}${artifacts}`))
          .when(Boolean(action), (e) => e.child(div().flex_none().text_color(t.dim).child(" · ")).child(
            div().id(`osr-act-${index}`).flex_none().px(7).rounded(5).border_1().border_color(stateColor).text_color(stateColor).text_size(11)
              .hover((s) => s.bg(t.hover)).cursor_pointer()
              .on_click((_e, cx) => { cx.stop_propagation(); this.select(index, cx); this.send(change, cx); })
              .child(action))))
        .child(div().pl(12).min_w(0).truncate().text_size(12).text_color(t.dim).child(change.goal || " ")));
  }

  renderViewer(t) {
    const change = this.change, doc = this.doc;
    const tabs = change.artifacts.filter((a) => a.group !== "spec" || a.key.startsWith("spec:") || !change.artifacts.some((x) => x.key.startsWith("spec:")));
    const max = Math.max(0, this.docHeight - this.viewHeight);
    if (this.offset > max && this.docHeight) this.offset = max;
    const thumb = this.docHeight > this.viewHeight && this.viewHeight > 0
      ? { h: Math.max(24, (this.viewHeight * this.viewHeight) / this.docHeight), top: 0 } : null;
    if (thumb) thumb.top = max ? (this.offset / max) * (this.viewHeight - thumb.h) : 0;
    return v_flex().flex_1().min_h(0)
      .child(this.header(t,
        div().id("osr-back").flex_none().px(6).rounded(5).text_color(t.muted).cursor_pointer().hover((s) => s.bg(t.hover).text_color(t.foreground))
          .on_click((_e, cx) => this.back(cx)).child("‹"),
        div().flex_1().min_w(0).truncate().font_semibold().text_size(14).text_color(change.touched ? t.accent : t.foreground).child(change.folder)))
      .child(h_flex().flex_none().flex_wrap().px(12).py(7).gap(6).border_b(1).border_color(t.border).children(tabs.map((a, i) => {
        const color = t[GROUP_COLOR[a.group]] ?? t.foreground, on = a.key === doc.key;
        return div().id(`osr-tab-${i}`).px(8).py(2).rounded(6).text_size(12).cursor_pointer()
          .text_color(a.exists ? color : t.dim).border_1().border_color(on ? color : "#00000000")
          .when(on, (e) => e.bg(t.selected).font_semibold())
          .hover((s) => s.bg(t.hover))
          .on_click((_e, cx) => this.open(a.key, cx))
          .child(a.title);
      })))
      .child(div().id("osr-doc").flex_1().min_h(0).relative().overflow_hidden()
        .on_size_change((size, cx) => { if (Math.abs(size.height - this.viewHeight) > 1) { this.viewHeight = size.height; cx.notify(); } })
        .on_scroll_wheel((e, cx) => this.scrollBy(-(e.delta_lines ? e.delta_lines.y * LINE_PX : e.delta.y), cx))
        .child(div().id("osr-doc-content").absolute().left(0).right(0).top(-this.offset).px(16).py(12)
          .on_size_change((size, cx) => { if (Math.abs(size.height - this.docHeight) > 1) { this.docHeight = size.height; cx.notify(); } })
          .child(doc.text
            ? this.renderMarkdown(`osr-md-${change.name}-${doc.key}`, doc.text, t)
            : div().text_color(t.dim).child(doc.loaded ? "(empty)" : "Loading…")))
        .when(Boolean(thumb), (e) => e.child(div().absolute().right(2).w(4).rounded(2).bg(t.border).top(thumb.top).h(thumb.h))));
  }

  /** Markdown as styled blocks: coloured headings and OpenSpec labels, task checkboxes, list
   *  markers, code, quotes. Inline Markdown in each block still goes through TextView. */
  renderMarkdown(id, text, t) {
    if (this.mdCache?.text !== text) this.mdCache = { text, blocks: M.markdownBlocks(text) };
    const inline = (key, md) => TextView.markdown(`${id}-${key}`, md).selectable();
    const mono = settings()?.font_family || "Menlo";
    const HEAD = {
      1: { size: 21, color: t.ansi6 }, 2: { size: 17, color: t.ansi3 }, 3: { size: 15, color: t.ansi2 },
      4: { size: 14, color: t.ansi5 }, 5: { size: 13, color: t.ansi4 }, 6: { size: 13, color: t.muted },
    };
    const DELTA = { ADDED: t.ansi2, MODIFIED: t.ansi3, REMOVED: t.ansi1, RENAMED: t.ansi5 };
    const LABEL = { requirement: t.ansi6, scenario: t.ansi5 };
    const badge = (label, color) => div().flex_none().px(6).py(0).rounded(4).text_size(10).font_semibold()
      .bg(tint(color, 0.18)).text_color(color).child(label.toUpperCase());
    const blocks = this.mdCache.blocks.map((b, i) => {
      if (b.type === "heading") {
        const h = HEAD[b.level], parts = M.headingParts(b.text);
        if (parts.delta) {
          const color = DELTA[parts.delta];
          return h_flex().mt(i ? 10 : 0).px(10).py(5).gap(8).items_center().rounded(6).border_l(3).border_color(color).bg(tint(color, 0.1))
            .child(div().text_size(h.size).font_semibold().text_color(color).child(parts.text));
        }
        const labelColor = parts.label && (LABEL[parts.label.toLowerCase()] ?? h.color);
        return h_flex().mt(i ? (b.level <= 2 ? 12 : 6) : 0).gap(8).items_center()
          .when(b.level === 1, (e) => e.pb(6).border_b(1).border_color(tint(h.color, 0.4)))
          .when(Boolean(parts.label), (e) => e.child(badge(parts.label, labelColor)))
          .child(div().min_w(0).text_size(h.size).font_semibold().text_color(h.color).child(parts.text));
      }
      if (b.type === "para") return inline(i, b.text);
      if (b.type === "rule") return div().my(4).h(1).bg(t.border);
      if (b.type === "table") return inline(i, b.text);
      if (b.type === "quote") return div().pl(12).py(2).border_l(3).border_color(t.ansi5).bg(tint(t.ansi5, 0.07)).text_color(t.muted).child(inline(i, b.text));
      if (b.type === "code") {
        return v_flex().px(12).py(8).rounded(6).border_l(3).border_color(t.ansi4).bg(t.surface).font_family(mono).text_size(12)
          .when(Boolean(b.lang), (e) => e.child(div().text_size(10).text_color(t.dim).child(b.lang)))
          .children(b.text.split("\n").map((l, j) => div().id(`${id}-${i}-l${j}`).min_h(17).text_color(t.foreground).whitespace_nowrap().child(l.replace(/\t/g, "    ") || " ")));
      }
      return v_flex().gap(3).children(b.items.map((it, j) => {
        const mark = it.checked === true ? div().text_color(t.ansi2).font_semibold().child("✓")
          : it.checked === false ? div().text_color(t.ansi3).child("○")
          : it.ordered ? div().text_color(t.ansi3).font_semibold().child(it.marker)
          : div().text_color(it.depth ? t.ansi5 : t.ansi6).child(it.depth ? "◦" : "•");
        return h_flex().items_start().gap(8).pl(it.depth * 18)
          .child(div().flex_none().min_w(14).child(mark))
          .child(div().flex_1().min_w(0).child(inline(`${i}-${j}`, it.text)));
      }));
    });
    return v_flex().gap(8).children(blocks);
  }

  renderFooter(t) {
    const hints = this.doc
      ? [["‹ esc", "back", "back"], ["← →", "prev/next", null], ["p d t s", "docs", "proposal"], ["↑↓ pg", "scroll", null], ["e", "edit", "edit"], ["q", "close", "close"]]
      : [["↑↓", "move", null], ...((this.projects?.length ?? 0) > 1 ? [["[ ]", "project", "nextproject"]] : []), ["⏎", "open", "open"], ["p d t s", "docs", "proposal"], ["a", "send", "send"], ["v", "validate", "validate"], ["e", "edit", "edit"], ["r", "refresh", "refresh"], ["q", "close", "close"]];
    return h_flex().flex_none().flex_wrap().px(10).py(6).gap(4).border_t(1).border_color(t.border).text_size(11)
      .children(hints.map(([keys, label, action], i) =>
        h_flex().id(`osr-hint-${i}`).gap(4).px(5).py(1).rounded(5).items_center()
          .when(Boolean(action), (e) => e.cursor_pointer().hover((s) => s.bg(t.hover)).on_click((_e, cx) => this.act(action, cx)))
          .child(div().text_color(t.foreground).child(keys))
          .child(div().text_color(t.dim).child(label))));
  }
}
