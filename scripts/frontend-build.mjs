// A source fingerprint prevents the local launcher from serving an older UI.
import { createHash } from "node:crypto";
import { readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const frontend = path.join(root, "frontend");
const files = [
  "index.html",
  "package.json",
  "package-lock.json",
  "tsconfig.json",
  "vite.config.ts",
];
async function collect(dir) {
  for (const entry of await readdir(path.join(frontend, dir), {
    withFileTypes: true,
  })) {
    const relative = `${dir}/${entry.name}`;
    if (entry.isDirectory()) await collect(relative);
    else if (entry.isFile()) files.push(relative);
  }
}
await collect("src");
const hash = createHash("sha256");
for (const relative of files.sort()) {
  hash.update(relative + "\0");
  hash.update(
    (await readFile(path.join(frontend, relative), "utf8")).replace(
      /\r\n/g,
      "\n",
    ),
  );
  hash.update("\0");
}
const { version } = JSON.parse(
  await readFile(path.join(frontend, "package.json"), "utf8"),
);
await writeFile(
  path.join(frontend, "dist", "portal-release.json"),
  JSON.stringify({ version, source_sha256: hash.digest("hex") }, null, 2) +
    "\n",
);
console.log(`NOM Monitor v${version}: interfaz compilada e identificada.`);
