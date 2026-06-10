import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

const { version } = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
const tag = `v${version}`;

function releaseExists(name) {
  try {
    execFileSync("gh", ["release", "view", name], { stdio: "ignore", cwd: root });
    return true;
  } catch {
    return false;
  }
}

// changesets/action runs the publish command on every push to main with no pending
// changesets, so skip when this version's release already exists.
if (releaseExists(tag)) {
  console.log(`Release ${tag} already exists; nothing to publish.`);
  process.exit(0);
}

const changelog = readFileSync(join(root, "CHANGELOG.md"), "utf8");
const lines = changelog.split("\n");
const start = lines.findIndex((line) => line.startsWith("## "));
if (start === -1) {
  throw new Error("release: no '## <version>' section found in CHANGELOG.md");
}
const rest = lines.slice(start + 1);
const end = rest.findIndex((line) => line.startsWith("## "));
const notes = (end === -1 ? rest : rest.slice(0, end)).join("\n").trim() || tag;

const notesPath = join(root, "dist", "release-notes.md");
mkdirSync(join(root, "dist"), { recursive: true });
writeFileSync(notesPath, `${notes}\n`);

const target = execFileSync("git", ["rev-parse", "HEAD"], { cwd: root }).toString().trim();
execFileSync(
  "gh",
  [
    "release",
    "create",
    tag,
    "dist/babelio.zip",
    "--title",
    tag,
    "--notes-file",
    notesPath,
    "--target",
    target,
  ],
  { cwd: root, stdio: "inherit" },
);
console.log(`Created release ${tag}`);
