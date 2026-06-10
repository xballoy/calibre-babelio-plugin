import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

const { version } = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
const tag = `v${version}`;

function releaseExists(name) {
  try {
    execFileSync("gh", ["release", "view", name], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

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
writeFileSync(notesPath, `${notes}\n`);

execFileSync(
  "gh",
  ["release", "create", tag, "dist/babelio.zip", "--title", tag, "--notes-file", notesPath],
  { cwd: root, stdio: "inherit" },
);
console.log(`Created release ${tag}`);
