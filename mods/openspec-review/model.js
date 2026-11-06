// Pure logic for the OpenSpec review mod: no Herdr or GPUI imports, so it can be
// unit-tested with plain Node (tests/mod/model.test.mjs). Ported from sidebar.py.

export const SEP = " · ";
export const LOCAL_AUTHOR = "local";
export const NOREPLY = "@users.noreply.github.com";
export const SKIPPED_DIRS = ["node_modules", "__pycache__", "venv", "dist", "build", "target", "coverage"];
export const STANDARD_FILES = ["proposal.md", "design.md", "tasks.md"];
const CHECKBOX = /^\s*[-*]\s+\[([ xX])\]\s+/gm;

// ---- Git-derived facts --------------------------------------------------------

/** The GitHub login in a noreply address, else the commit author's name. */
export function githubLoginOrName(email, name) {
  const address = (email || "").trim();
  if (address.toLowerCase().endsWith(NOREPLY)) {
    const local = address.slice(0, -NOREPLY.length);
    const login = local.slice(local.lastIndexOf("+") + 1);
    if (login) return login;
  }
  return (name || "").trim();
}

/** The active change folder a repo-relative path belongs to, or "". */
export function changeFolderFromPath(path) {
  const marker = "openspec/changes/";
  const index = path.indexOf(marker);
  if (index === -1) return "";
  const rest = path.slice(index + marker.length);
  const slash = rest.indexOf("/");
  if (slash === -1) return "";
  const folder = rest.slice(0, slash);
  return folder === "archive" ? "" : folder;
}

/** `git log --diff-filter=A --format=C|%ae|%an --name-only` → folder → creating commit's {email, name}.
 *  Git lists newest first, so later (older) entries overwrite: the creator wins. */
export function parseChangeCreators(output) {
  const creators = {};
  let creator = null;
  for (const raw of (output || "").split("\n")) {
    const line = raw.trim();
    if (!line) continue;
    if (line.startsWith("C|")) {
      const body = line.slice(2), bar = body.indexOf("|");
      creator = bar === -1 ? { email: body, name: "" } : { email: body.slice(0, bar), name: body.slice(bar + 1) };
      continue;
    }
    const folder = changeFolderFromPath(line);
    if (folder && creator) creators[folder] = creator;
  }
  return creators;
}

/** Folder → displayed creator (GitHub login or name). */
export function parseChangeAuthors(output) {
  const authors = {};
  for (const [folder, c] of Object.entries(parseChangeCreators(output))) {
    const author = githubLoginOrName(c.email, c.name);
    if (author) authors[folder] = author;
  }
  return authors;
}

/** Whether a change's creator is the person using this checkout (`git config user.*`):
 *  same email, same name, or the same GitHub login. */
export function isOwnCreator(creator, me) {
  if (!creator || !me) return false;
  const same = (a, b) => Boolean(a && b) && a.trim().toLowerCase() === b.trim().toLowerCase();
  return same(creator.email, me.email) || same(creator.name, me.name)
    || same(githubLoginOrName(creator.email, ""), githubLoginOrName(me.email, ""));
}

/** The person's own changes first, each group keeping its order. */
export const ownFirst = (changes) => [...changes.filter((c) => c.mine), ...changes.filter((c) => !c.mine)];

/** The displayed change identity for a Git-relative path, or null. */
export function changeIdentityFromPath(path) {
  const parts = path.split("/").filter((p) => p !== "" && p !== ".");
  const index = parts.indexOf("openspec");
  if (index === -1 || index + 2 >= parts.length || parts[index + 1] !== "changes") return null;
  const folder = parts[index + 2];
  if (folder === "archive" || folder.startsWith(".")) return null;
  const prefix = parts.slice(0, index).join(SEP);
  return prefix ? `${prefix}${SEP}${folder}` : folder;
}

/** `git log --format=%ct --name-only` → change identity → newest commit (seconds). */
export function parseCommitActivity(output) {
  const activity = {};
  let timestamp = 0;
  for (const raw of (output || "").split("\n")) {
    const line = raw.trim();
    if (/^\d+$/.test(line)) { timestamp = Number(line); continue; }
    if (!timestamp || !line) continue;
    const name = changeIdentityFromPath(line);
    if (name) activity[name] = Math.max(activity[name] ?? 0, timestamp);
  }
  return activity;
}

/** Touched change identities and their newest activity (file mtime or commit time, seconds). */
export function touchedActivity(paths, fileMtimes, commitActivity) {
  const result = {};
  for (const path of paths) {
    const name = changeIdentityFromPath(path);
    if (!name) continue;
    result[name] = Math.max(result[name] ?? 0, commitActivity[name] ?? 0, fileMtimes[path] ?? 0);
  }
  return result;
}

export function normalizedName(value) {
  const leaf = (value || "").split("/").pop();
  return leaf.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

/** 0 exact, 1 hyphen-bounded containment, 2 no affinity. */
export function changeNameAffinity(changeName, branch, worktreeName) {
  const change = normalizedName(changeName);
  const contexts = [normalizedName(branch), normalizedName(worktreeName)].filter(Boolean);
  if (contexts.includes(change)) return 0;
  if (change && contexts.some((c) => `-${c}-`.includes(`-${change}-`))) return 1;
  return 2;
}

const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

/** Touched first (affinity, newest activity, name); untouched by name. */
export function sortChanges(changes, snapshot) {
  const key = (c) => !c.touched || !snapshot
    ? [1, 0, 0, c.name.toLowerCase()]
    : [0, changeNameAffinity(c.folder, snapshot.branch, snapshot.worktreeName), -(c.activity || 0), c.name.toLowerCase()];
  return [...changes].sort((a, b) => {
    const ka = key(a), kb = key(b);
    for (let i = 0; i < ka.length; i++) { const d = cmp(ka[i], kb[i]); if (d) return d; }
    return 0;
  });
}

// ---- Paths and names ------------------------------------------------------------

export const basename = (p) => p.replace(/\/+$/, "").split("/").pop();
export const dirname = (p) => { const s = p.replace(/\/+$/, ""); const i = s.lastIndexOf("/"); return i <= 0 ? "/" : s.slice(0, i); };

/** A project's path below the search root, or its folder name when outside it. */
export function relativeTo(root, path) {
  if (path === root) return "";
  if (path.startsWith(root.endsWith("/") ? root : root + "/")) return path.slice(root.replace(/\/+$/, "").length + 1);
  return basename(path);
}

export function displayChangeName(searchRoot, project, folder) {
  const prefix = relativeTo(searchRoot, project).split("/").filter(Boolean).join(SEP);
  return prefix ? `${prefix}${SEP}${folder}` : folder;
}

/** The `openspec/changes` pathspec of each project, relative to the search root. */
export function changePathspecs(searchRoot, projects) {
  return projects.map((p) => {
    const rel = relativeTo(searchRoot, p);
    return rel === "" ? "openspec/changes" : p.startsWith(searchRoot) ? `${rel}/openspec/changes` : `${p}/openspec/changes`;
  });
}

// ---- Documents ------------------------------------------------------------------

/** The scalar/list subset of .openspec.yaml the pane uses. */
export function parseMetadata(text) {
  const result = {};
  let list = null;
  for (const raw of (text || "").split("\n")) {
    const line = raw.replace(/\s+$/, "");
    if (!line.trim() || line.trimStart().startsWith("#")) continue;
    if (list && /^\s+-\s+/.test(line)) { result[list].push(line.replace(/^\s+-\s+/, "").replace(/^['" ]+|['" ]+$/g, "")); continue; }
    list = null;
    const m = /^([A-Za-z_][\w-]*):\s*(.*)$/.exec(line);
    if (!m) continue;
    const [, key, value] = m, v = value.trim();
    if (!v) { result[key] = []; list = key; }
    else if (v.toLowerCase() === "true" || v.toLowerCase() === "false") result[key] = v.toLowerCase() === "true";
    else result[key] = v.replace(/^['" ]+|['" ]+$/g, "");
  }
  return result;
}

/** The first paragraph after any leading headings, with emphasis markers removed. */
export function firstSummary(markdown) {
  const current = [];
  for (const raw of (markdown || "").split("\n")) {
    const line = raw.trim();
    if (line.startsWith("#")) { if (current.length) break; continue; }
    if (!line) { if (current.length) break; continue; }
    current.push(line.replace(/\[([^\]]*)\]\([^)]*\)/g, "$1").replace(/[*_`]/g, ""));
  }
  return current.join(" ");
}

export function countTasks(markdown) {
  let done = 0, total = 0;
  for (const m of (markdown || "").matchAll(CHECKBOX)) { total++; if (m[1].toLowerCase() === "x") done++; }
  return { done, total };
}

export function docTitle(filename) {
  const stem = filename.endsWith(".md") ? filename.slice(0, -3) : filename;
  const words = stem.replace(/[-_]/g, " ").trim();
  return words ? words.replace(/\S+/g, (w) => w[0].toUpperCase() + w.slice(1).toLowerCase()) : filename;
}

/** Groups `find` output under one `openspec/changes` dir into active change folders. */
export function groupChangeFiles(changesDir, lines) {
  const prefix = changesDir.replace(/\/+$/, "") + "/";
  const folders = {};
  for (const line of lines) {
    if (!line.startsWith(prefix)) continue;
    const rel = line.slice(prefix.length), parts = rel.split("/");
    const folder = parts[0];
    if (!folder || folder === "archive" || folder.startsWith(".")) continue;
    const entry = folders[folder] ??= { docs: [], specs: [], yaml: false };
    if (parts.length === 1) continue; // the folder itself
    if (parts.length === 2 && parts[1] === ".openspec.yaml") entry.yaml = true;
    else if (parts.length === 2 && parts[1].endsWith(".md")) entry.docs.push(parts[1]);
    else if (parts[1] === "specs" && parts.length > 2 && rel.endsWith(".md") && !parts.slice(2).some((p) => p.startsWith("."))) entry.specs.push(parts.slice(2).join("/"));
  }
  for (const entry of Object.values(folders)) { entry.docs.sort(); entry.specs.sort(); }
  return folders;
}

/** The change's documents in tab order: Proposal, Design, Tasks, other docs, specs. */
export function buildArtifacts(dir, files, metadata = {}) {
  const has = (name) => files.docs.includes(name);
  const artifacts = [
    { key: "proposal", title: "Proposal", group: "standard", path: `${dir}/proposal.md`, required: true, exists: has("proposal.md") },
    { key: "design", title: "Design", group: "standard", path: `${dir}/design.md`, required: false, exists: has("design.md") },
    { key: "tasks", title: "Tasks", group: "standard", path: `${dir}/tasks.md`, required: true, exists: has("tasks.md") },
  ];
  for (const name of files.docs) {
    if (STANDARD_FILES.includes(name)) continue;
    artifacts.push({ key: `doc:${name}`, title: docTitle(name), group: "doc", path: `${dir}/${name}`, required: false, exists: true });
  }
  if (files.specs.length) {
    for (const rel of files.specs) {
      const label = rel.endsWith("/spec.md") ? rel.slice(0, -"/spec.md".length) : rel;
      artifacts.push({ key: `spec:${rel}`, title: label, group: "spec", path: `${dir}/specs/${rel}`, required: true, exists: true });
    }
  } else {
    artifacts.push({ key: "specs", title: "Specs", group: "spec", path: null, required: !metadata.skip_specs, exists: false });
  }
  return artifacts;
}

// ---- State and actions -------------------------------------------------------------

export function deriveState({ validation, missingRequired, tasksDone, tasksTotal }) {
  if (validation === "invalid") return "INVALID";
  if (tasksTotal === 0 || missingRequired > 0) return "DRAFT";
  if (tasksDone === 0) return "READY";
  if (tasksDone < tasksTotal) return "IN PROGRESS";
  return "DONE";
}

const ACTIONS = { READY: "apply", "IN PROGRESS": "investigate", DONE: "archive" };
export const actionForState = (state) => ACTIONS[state] ?? null;

/** What the neighbouring agent is sent for a change's next action. */
export function agentCommandFor(change) {
  const action = actionForState(change.state);
  if (action === "apply") return `/opsx:apply ${change.folder}`;
  if (action === "archive") return `/opsx:archive ${change.folder}`;
  if (action === "investigate") {
    return `Investigate the open tasks in the OpenSpec change '${change.folder}' (${change.tasksDone}/${change.tasksTotal} tasks complete) and tell me what is left to finish it.`;
  }
  return null;
}

/** Viewer navigation order: existing core docs, other docs, then specs. */
export function documentOrder(artifacts) {
  return artifacts.filter((a) => a.exists && (a.group !== "spec" || a.key.startsWith("spec:"))).map((a) => a.key);
}

/** Clamps value to [lo, hi]. */
export const clamp = (value, lo, hi) => Math.max(lo, Math.min(hi, value));

// ---- Markdown blocks ----------------------------------------------------------------

const FENCE = /^\s*(`{3,}|~{3,})\s*([\w+-]*)/;
const HEADING = /^(#{1,6})\s+(.*?)\s*#*\s*$/;
const RULE = /^\s{0,3}([-*_])(\s*\1){2,}\s*$/;
const ITEM = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
const TABLE_RULE = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;
const CHECK = /^\[([ xX])\]\s+/;

/** Splits Markdown into the blocks the viewer styles itself. Inline Markdown stays in each
 *  block's text. Blocks: heading {level, text}, para {text}, list {items: [{depth, marker,
 *  ordered, checked, text}]}, code {lang, text}, quote {text}, table {text}, rule. */
export function markdownBlocks(markdown) {
  const src = (markdown || "").replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  let i = 0;
  const blank = (l) => !l || !l.trim();
  const starts = (l, next) => HEADING.test(l) || FENCE.test(l) || RULE.test(l) || ITEM.test(l) || /^\s*>/.test(l)
    || (l.includes("|") && next !== undefined && TABLE_RULE.test(next));
  while (i < src.length) {
    const line = src[i];
    if (blank(line)) { i++; continue; }
    let m;
    if ((m = FENCE.exec(line))) {
      const close = m[1][0], body = [];
      for (i++; i < src.length && !new RegExp(`^\\s*\\${close}{${m[1].length},}\\s*$`).test(src[i]); i++) body.push(src[i]);
      i++;
      blocks.push({ type: "code", lang: m[2] || "", text: body.join("\n") });
    } else if ((m = HEADING.exec(line))) {
      blocks.push({ type: "heading", level: m[1].length, text: m[2] }); i++;
    } else if (RULE.test(line)) {
      blocks.push({ type: "rule" }); i++;
    } else if (line.includes("|") && src[i + 1] !== undefined && TABLE_RULE.test(src[i + 1])) {
      const rows = [];
      while (i < src.length && !blank(src[i]) && src[i].includes("|")) rows.push(src[i++]);
      blocks.push({ type: "table", text: rows.join("\n") });
    } else if (/^\s*>/.test(line)) {
      const body = [];
      while (i < src.length && /^\s*>/.test(src[i])) body.push(src[i++].replace(/^\s*>\s?/, ""));
      blocks.push({ type: "quote", text: body.join("\n") });
    } else if (ITEM.test(line)) {
      const items = [], indents = [];
      while (i < src.length) {
        const l = src[i];
        if (blank(l)) {
          let j = i + 1; while (j < src.length && blank(src[j])) j++;
          if (j < src.length && (ITEM.test(src[j]) || /^\s{2,}\S/.test(src[j]))) { i = j; continue; }
          break;
        }
        const it = ITEM.exec(l);
        if (it) {
          const indent = it[1].replace(/\t/g, "    ").length;
          while (indents.length && indents.at(-1) > indent) indents.pop();
          if (!indents.length || indents.at(-1) < indent) indents.push(indent);
          const check = CHECK.exec(it[3]);
          items.push({
            depth: indents.length - 1, marker: it[2], ordered: /\d/.test(it[2]),
            checked: check ? check[1] !== " " : null, text: check ? it[3].slice(check[0].length) : it[3],
          });
          i++;
        } else if (/^\s+\S/.test(l) || !starts(l, src[i + 1])) {
          if (!items.length || (!/^\s/.test(l) && starts(l, src[i + 1]))) break;
          items.at(-1).text += "\n" + l.trim(); i++;
        } else break;
      }
      blocks.push({ type: "list", items });
    } else {
      const body = [];
      while (i < src.length && !blank(src[i]) && !(body.length && starts(src[i], src[i + 1]))) body.push(src[i++]);
      blocks.push({ type: "para", text: body.join("\n") });
    }
  }
  return blocks;
}

/** Heading text with inline markers removed, and an OpenSpec label split off:
 *  "Requirement: X" → {label: "Requirement", text: "X"}; "ADDED Requirements" → {delta: "ADDED"}. */
export function headingParts(text) {
  const plain = text.replace(/\[([^\]]*)\]\([^)]*\)/g, "$1").replace(/[*_`]/g, "").trim();
  const delta = /^(ADDED|MODIFIED|REMOVED|RENAMED)\s+Requirements?$/i.exec(plain);
  if (delta) return { delta: delta[1].toUpperCase(), text: plain };
  const labelled = /^(Requirement|Scenario|Purpose|Why|What Changes|Impact|Context|Goals|Non-Goals|Decisions|Risks)\s*:\s*(.+)$/i.exec(plain);
  if (labelled) return { label: labelled[1], text: labelled[2] };
  return { text: plain };
}
