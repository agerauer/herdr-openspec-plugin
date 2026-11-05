// Unit tests for the Herdr app mod's pure logic: node --test tests/mod
import test from "node:test";
import assert from "node:assert/strict";
import * as M from "../../mods/openspec-review/model.js";

test("noreply addresses resolve to the GitHub login", () => {
  assert.equal(M.githubLoginOrName("20586+agerauer@users.noreply.github.com", "Andi"), "agerauer");
  assert.equal(M.githubLoginOrName("agerauer@users.noreply.github.com", "Andi"), "agerauer");
  assert.equal(M.githubLoginOrName("andi@example.com", "Andi G"), "Andi G");
});

test("the creating commit's author wins over later editors", () => {
  const log = [
    "C|bob@example.com|Bob", "openspec/changes/add-login/tasks.md",
    "C|1+alice@users.noreply.github.com|Alice", "openspec/changes/add-login/proposal.md",
    "openspec/changes/archive/old/proposal.md",
  ].join("\n");
  assert.deepEqual(M.parseChangeAuthors(log), { "add-login": "alice" });
});

test("nested paths map to prefixed change identities; archive is ignored", () => {
  assert.equal(M.changeIdentityFromPath("openspec/changes/add-login/proposal.md"), "add-login");
  assert.equal(M.changeIdentityFromPath("apps/nxt/openspec/changes/add-login/x.md"), "apps · nxt · add-login");
  assert.equal(M.changeIdentityFromPath("openspec/changes/archive/old/x.md"), null);
  assert.equal(M.changeIdentityFromPath("src/main.py"), null);
});

test("display names prefix nested projects", () => {
  assert.equal(M.displayChangeName("/r", "/r", "add-login"), "add-login");
  assert.equal(M.displayChangeName("/r", "/r/nxt", "add-login"), "nxt · add-login");
  assert.equal(M.displayChangeName("/r", "/r/apps/nxt", "add-login"), "apps · nxt · add-login");
  assert.deepEqual(M.changePathspecs("/r", ["/r", "/r/nxt"]), ["openspec/changes", "nxt/openspec/changes"]);
});

test("states derive from validity, drafts and task progress", () => {
  const s = (o) => M.deriveState({ validation: null, missingRequired: 0, tasksDone: 0, tasksTotal: 0, ...o });
  assert.equal(s({}), "DRAFT");
  assert.equal(s({ missingRequired: 1, tasksDone: 1, tasksTotal: 2 }), "DRAFT");
  assert.equal(s({ tasksTotal: 16 }), "READY");
  assert.equal(s({ tasksDone: 3, tasksTotal: 5 }), "IN PROGRESS");
  assert.equal(s({ tasksDone: 5, tasksTotal: 5 }), "DONE");
  assert.equal(s({ validation: "invalid", tasksDone: 5, tasksTotal: 5 }), "INVALID");
});

test("each state offers at most one agent action", () => {
  assert.equal(M.agentCommandFor({ state: "READY", folder: "x" }), "/opsx:apply x");
  assert.equal(M.agentCommandFor({ state: "DONE", folder: "x" }), "/opsx:archive x");
  assert.match(M.agentCommandFor({ state: "IN PROGRESS", folder: "x", tasksDone: 1, tasksTotal: 3 }), /'x' \(1\/3 tasks complete\)/);
  assert.equal(M.agentCommandFor({ state: "DRAFT", folder: "x" }), null);
  assert.equal(M.agentCommandFor({ state: "INVALID", folder: "x" }), null);
});

test("tasks are counted from checkboxes", () => {
  assert.deepEqual(M.countTasks("- [x] a\n- [ ] b\n  * [X] c\ntext [x]\n"), { done: 2, total: 3 });
  assert.deepEqual(M.countTasks(null), { done: 0, total: 0 });
});

test("touched changes sort first by branch affinity, then activity, then name", () => {
  const c = (name, folder, touched, activity = 0) => ({ name, folder, touched, activity });
  const sorted = M.sortChanges([
    c("zeta", "zeta", false), c("add-login", "add-login", false), c("nxt · add-api", "add-api", false),
    c("old", "old", true, 5), c("new", "new", true, 9), c("nxt · fix-thing", "fix-thing", true, 1),
  ], { branch: "feature/fix-thing", worktreeName: "ws" });
  assert.deepEqual(sorted.map((x) => x.name), ["nxt · fix-thing", "new", "old", "add-login", "nxt · add-api", "zeta"]);
  assert.equal(M.changeNameAffinity("login", "feature/fix-login-flow", ""), 1);
  assert.equal(M.changeNameAffinity("log", "feature/fix-login", ""), 2);
});

test("change folders group their documents and specs, skipping archive and dot folders", () => {
  const d = "/r/openspec/changes";
  const grouped = M.groupChangeFiles(d, [
    `${d}/a`, `${d}/a/proposal.md`, `${d}/a/notes.md`, `${d}/a/.openspec.yaml`, `${d}/a/specs`, `${d}/a/specs/auth`,
    `${d}/a/specs/auth/spec.md`, `${d}/empty`, `${d}/.hidden`, `${d}/.hidden/proposal.md`,
  ]);
  assert.deepEqual(Object.keys(grouped).sort(), ["a", "empty"]);
  assert.deepEqual(grouped.a, { docs: ["notes.md", "proposal.md"], specs: ["auth/spec.md"], yaml: true });
  const arts = M.buildArtifacts(`${d}/a`, grouped.a);
  assert.deepEqual(arts.map((x) => x.key), ["proposal", "design", "tasks", "doc:notes.md", "spec:auth/spec.md"]);
  assert.equal(arts.find((x) => x.key === "doc:notes.md").title, "Notes");
  assert.equal(arts.at(-1).title, "auth");
  assert.deepEqual(M.documentOrder(arts), ["proposal", "doc:notes.md", "spec:auth/spec.md"]);
  const bare = M.buildArtifacts(`${d}/empty`, grouped.empty, { skip_specs: true });
  assert.deepEqual(bare.at(-1), { key: "specs", title: "Specs", group: "spec", path: null, required: false, exists: false });
});

test("summaries and metadata parse like the curses app", () => {
  assert.equal(M.firstSummary("# T\n\n## Why\n\nMakes **login** `fast`. See [docs](http://x).\nMore.\n\nNext"), "Makes login fast. See docs. More.");
  assert.deepEqual(M.parseMetadata("schema: spec-driven\nskip_specs: true\ntags:\n  - a\n  - 'b'\n"), { schema: "spec-driven", skip_specs: true, tags: ["a", "b"] });
});

test("own changes are recognised by email, name or GitHub login, and grouped first", () => {
  const log = ["C|bob@example.com|Bob", "openspec/changes/a/tasks.md", "C|1+andi@users.noreply.github.com|Andi", "openspec/changes/a/proposal.md", "openspec/changes/b/proposal.md"].join("\n");
  assert.deepEqual(M.parseChangeCreators(log), { a: { email: "1+andi@users.noreply.github.com", name: "Andi" }, b: { email: "1+andi@users.noreply.github.com", name: "Andi" } });
  const creator = { email: "1+andi@users.noreply.github.com", name: "Andi" };
  assert.equal(M.isOwnCreator(creator, { email: "1+ANDI@users.noreply.github.com", name: "" }), true);
  assert.equal(M.isOwnCreator(creator, { email: "andi@work.com", name: "andi" }), true);
  assert.equal(M.isOwnCreator(creator, { email: "2+andi@users.noreply.github.com", name: "A. G." }), true);
  assert.equal(M.isOwnCreator(creator, { email: "bob@example.com", name: "Bob" }), false);
  assert.equal(M.isOwnCreator(creator, { email: "", name: "" }), false);
  const c = (name, mine) => ({ name, mine });
  assert.deepEqual(M.ownFirst([c("x", false), c("y", true), c("z", false), c("w", true)]).map((x) => x.name), ["y", "w", "x", "z"]);
});
