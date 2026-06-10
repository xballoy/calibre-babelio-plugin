import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

const { version } = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(version);
if (!match) {
  throw new Error(
    `package.json version "${version}" must be a plain X.Y.Z version ` +
      "(pre-release/build metadata is unsupported)",
  );
}
const [, major, minor, patch] = match;

function rewrite(relPath, pattern, replacement) {
  const path = join(root, relPath);
  const before = readFileSync(path, "utf8");
  const globalPattern = new RegExp(pattern.source, `${pattern.flags.replace("g", "")}g`);
  const hits = before.match(globalPattern)?.length ?? 0;
  if (hits !== 1) {
    throw new Error(`sync-version: expected exactly one version match in ${relPath}, found ${hits}`);
  }
  writeFileSync(path, before.replace(pattern, replacement));
}

rewrite("pyproject.toml", /^version = "[^"]*"$/m, `version = "${version}"`);
rewrite(
  "src/calibre_babelio/__init__.py",
  /^( *)version = \(\d+, \d+, \d+\)$/m,
  `$1version = (${major}, ${minor}, ${patch})`,
);

// pyproject's version feeds uv.lock, so refresh the lock in the same step or it ships stale.
execFileSync("uv", ["lock"], { cwd: root, stdio: "inherit" });

console.log(`Synced version ${version} into pyproject.toml, __init__.py, and uv.lock`);
