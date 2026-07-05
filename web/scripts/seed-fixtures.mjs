#!/usr/bin/env node
/**
 * Seeds web/public/data/ from web/src/fixtures/ IF AND ONLY IF public/data/meta.json
 * doesn't already exist. This lets a fresh clone run `npm run dev`/`npm run build`
 * before the Python pipeline has ever produced real data, without ever
 * clobbering a real `make export` output that's already there.
 *
 * Runs automatically via package.json's "predev"/"prebuild" scripts.
 */
import { existsSync, mkdirSync, cpSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const fixturesDir = join(webRoot, "src", "fixtures");
const publicDataDir = join(webRoot, "public", "data");
const marker = join(publicDataDir, "meta.json");

if (existsSync(marker)) {
  console.log("[seed-fixtures] web/public/data/meta.json ya existe (datos reales del pipeline) -- no se toca.");
} else {
  mkdirSync(publicDataDir, { recursive: true });
  cpSync(fixturesDir, publicDataDir, { recursive: true });
  console.log("[seed-fixtures] No hay datos reales aun -- se copiaron los fixtures sinteticos a web/public/data/.");
}
