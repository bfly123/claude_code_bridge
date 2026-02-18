import { createHash } from "node:crypto";
import fsMod from "node:fs";
import { fileURLToPath } from "node:url";
import glob from "fast-glob";
import pLimit from "p-limit";
import { normalizePath } from "vite";
import { CONTENT_RENDER_FLAG, PROPAGATED_ASSET_FLAG } from "../../../content/consts.js";
import { hasContentFlag } from "../../../content/utils.js";
import {
  generateContentEntryFile,
  generateLookupMap
} from "../../../content/vite-plugin-content-virtual-mod.js";
import { configPaths } from "../../config/index.js";
import { emptyDir } from "../../fs/index.js";
import {
  appendForwardSlash,
  joinPaths,
  removeFileExtension,
  removeLeadingForwardSlash
} from "../../path.js";
import { isContentCollectionsCacheEnabled } from "../../util.js";
import { addRollupInput } from "../add-rollup-input.js";
import { CHUNKS_PATH, CONTENT_PATH } from "../consts.js";
import { copyFiles } from "../static-build.js";
import { encodeName } from "../util.js";
import { extendManualChunks } from "./util.js";
const CONTENT_CACHE_DIR = "./" + CONTENT_PATH;
const CONTENT_MANIFEST_FILE = "./manifest.json";
const CONTENT_MANIFEST_VERSION = 1;
const virtualEmptyModuleId = `virtual:empty-content`;
const resolvedVirtualEmptyModuleId = `\0${virtualEmptyModuleId}`;
const NO_MANIFEST_VERSION = -1;
function createContentManifest() {
  return {
    version: NO_MANIFEST_VERSION,
    entries: [],
    serverEntries: [],
    clientEntries: [],
    lockfiles: "",
    configs: ""
  };
}
const getContentRoot = (config) => new URL("./content/", config.outDir);
const getContentCacheDir = (config) => new URL(CONTENT_CACHE_DIR, config.cacheDir);
const getCacheTmp = (contentCacheDir) => new URL("./.tmp/", contentCacheDir);
function vitePluginContent(opts, lookupMap, internals, cachedBuildOutput) {
  const { config } = opts.settings;
  const distContentRoot = getContentRoot(config);
  const contentCacheDir = getContentCacheDir(config);
  const contentManifestFile = new URL(CONTENT_MANIFEST_FILE, contentCacheDir);
  let oldManifest = createContentManifest();
  let newManifest = createContentManifest();
  let entries;
  let injectedEmptyFile = false;
  let currentManifestState = "valid";
  if (fsMod.existsSync(contentManifestFile)) {
    try {
      const data = fsMod.readFileSync(contentManifestFile, { encoding: "utf8" });
      oldManifest = JSON.parse(data);
    } catch {
    }
  }
  return {
    name: "@astro/plugin-build-content",
    async options(options) {
      let newOptions = Object.assign({}, options);
      newManifest = await generateContentManifest(opts, lookupMap);
      entries = getEntriesFromManifests(oldManifest, newManifest);
      currentManifestState = manifestState(oldManifest, newManifest);
      if (currentManifestState === "valid") {
        internals.cachedClientEntries = oldManifest.clientEntries;
      } else {
        let logReason = "";
        switch (currentManifestState) {
          case "config-mismatch":
            logReason = "Astro config has changed";
            break;
          case "lockfile-mismatch":
            logReason = "Lockfiles have changed";
            break;
          case "no-entries":
            logReason = "No content collections entries cached";
            break;
          case "version-mismatch":
            logReason = "The cache manifest version has changed";
            break;
          case "no-manifest":
            logReason = "No content manifest was found in the cache";
            break;
        }
        opts.logger.info("build", `Cache invalid, rebuilding from source. Reason: ${logReason}.`);
      }
      for (const { type, entry } of entries.buildFromSource) {
        const fileURL = encodeURI(joinPaths(opts.settings.config.root.toString(), entry));
        const input = fileURLToPath(fileURL);
        const inputs = [`${input}?${collectionTypeToFlag(type)}`];
        if (type === "content") {
          inputs.push(`${input}?${CONTENT_RENDER_FLAG}`);
        }
        newOptions = addRollupInput(newOptions, inputs);
      }
      if (currentManifestState === "valid") {
        for (const { cached, dist } of cachedBuildOutput) {
          if (fsMod.existsSync(cached)) {
            await copyFiles(cached, dist, true);
          }
        }
        const cacheExists = fsMod.existsSync(contentCacheDir);
        if (cacheExists) {
          await copyFiles(contentCacheDir, distContentRoot, false);
        }
      }
      if (entries.buildFromSource.length === 0) {
        newOptions = addRollupInput(newOptions, [virtualEmptyModuleId]);
        injectedEmptyFile = true;
      }
      return newOptions;
    },
    outputOptions(outputOptions) {
      const rootPath = normalizePath(fileURLToPath(opts.settings.config.root));
      const srcPath = normalizePath(fileURLToPath(opts.settings.config.srcDir));
      const entryCache = /* @__PURE__ */ new Map();
      extendManualChunks(outputOptions, {
        before(id, meta) {
          if (id.startsWith(srcPath) && id.slice(srcPath.length).startsWith("content")) {
            const info = meta.getModuleInfo(id);
            if (info?.dynamicImporters.length === 1 && hasContentFlag(info.dynamicImporters[0], PROPAGATED_ASSET_FLAG)) {
              const [srcRelativePath2] = id.replace(rootPath, "/").split("?");
              const resultId = encodeName(
                `${removeLeadingForwardSlash(removeFileExtension(srcRelativePath2))}.render.mjs`
              );
              return resultId;
            }
            const [srcRelativePath, flag] = id.replace(rootPath, "/").split("?");
            const collectionEntry = findEntryFromSrcRelativePath(
              lookupMap,
              srcRelativePath,
              entryCache
            );
            if (collectionEntry) {
              let suffix = ".mjs";
              if (flag === PROPAGATED_ASSET_FLAG) {
                suffix = ".entry.mjs";
              }
              id = removeLeadingForwardSlash(
                removeFileExtension(encodeName(id.replace(srcPath, "/")))
              ) + suffix;
              return id;
            }
          }
        }
      });
    },
    resolveId(id) {
      if (id === virtualEmptyModuleId) {
        return resolvedVirtualEmptyModuleId;
      }
    },
    async load(id) {
      if (id === resolvedVirtualEmptyModuleId) {
        return {
          code: `// intentionally left empty!
export default {}`
        };
      }
    },
    async generateBundle(_options, bundle) {
      const code = await generateContentEntryFile({
        settings: opts.settings,
        fs: fsMod,
        lookupMap,
        IS_DEV: false,
        IS_SERVER: false,
        isClient: false
      });
      this.emitFile({
        type: "prebuilt-chunk",
        code,
        fileName: "content/entry.mjs"
      });
      if (!injectedEmptyFile) return;
      Object.keys(bundle).forEach((key) => {
        const mod = bundle[key];
        if (mod.type === "asset") return;
        if (mod.facadeModuleId === resolvedVirtualEmptyModuleId) {
          delete bundle[key];
        }
      });
    },
    async writeBundle() {
      const clientComponents = /* @__PURE__ */ new Set([
        ...oldManifest.clientEntries,
        ...internals.discoveredHydratedComponents.keys(),
        ...internals.discoveredClientOnlyComponents.keys(),
        ...internals.discoveredScripts
      ]);
      const serverComponents = /* @__PURE__ */ new Set([
        ...oldManifest.serverEntries,
        ...internals.discoveredHydratedComponents.keys()
      ]);
      newManifest.serverEntries = Array.from(serverComponents);
      newManifest.clientEntries = Array.from(clientComponents);
      const cacheExists = fsMod.existsSync(contentCacheDir);
      if (cacheExists && currentManifestState !== "valid") {
        emptyDir(contentCacheDir);
      }
      await fsMod.promises.mkdir(contentCacheDir, { recursive: true });
      await fsMod.promises.writeFile(contentManifestFile, JSON.stringify(newManifest), {
        encoding: "utf8"
      });
    }
  };
}
function findEntryFromSrcRelativePath(lookupMap, srcRelativePath, entryCache) {
  let value = entryCache.get(srcRelativePath);
  if (value) return value;
  for (const collection of Object.values(lookupMap)) {
    for (const entry of Object.values(collection)) {
      for (const entryFile of Object.values(entry)) {
        if (entryFile === srcRelativePath) {
          value = entryFile;
          entryCache.set(srcRelativePath, entryFile);
          return value;
        }
      }
    }
  }
}
function getEntriesFromManifests(oldManifest, newManifest) {
  const { entries: oldEntries } = oldManifest;
  const { entries: newEntries } = newManifest;
  let entries = { restoreFromCache: [], buildFromSource: [] };
  const newEntryMap = new Map(newEntries);
  if (manifestState(oldManifest, newManifest) !== "valid") {
    entries.buildFromSource = Array.from(newEntryMap.keys());
    return entries;
  }
  const oldEntryHashMap = new Map(
    oldEntries.map(([key, hash]) => [hash, key])
  );
  for (const [entry, hash] of newEntryMap) {
    if (oldEntryHashMap.has(hash)) {
      entries.restoreFromCache.push(entry);
    } else {
      entries.buildFromSource.push(entry);
    }
  }
  return entries;
}
function manifestState(oldManifest, newManifest) {
  if (oldManifest.version === NO_MANIFEST_VERSION) {
    return "no-manifest";
  }
  if (oldManifest.version !== newManifest.version) {
    return "version-mismatch";
  }
  if (oldManifest.entries.length === 0) {
    return "no-entries";
  }
  if (oldManifest.lockfiles !== newManifest.lockfiles || newManifest.lockfiles === "") {
    return "lockfile-mismatch";
  }
  if (oldManifest.configs !== newManifest.configs) {
    return "config-mismatch";
  }
  return "valid";
}
async function generateContentManifest(opts, lookupMap) {
  let manifest = createContentManifest();
  manifest.version = CONTENT_MANIFEST_VERSION;
  const limit = pLimit(10);
  const promises = [];
  for (const [collection, { type, entries }] of Object.entries(lookupMap)) {
    for (const entry of Object.values(entries)) {
      const key = { collection, type, entry };
      const fileURL = new URL(encodeURI(joinPaths(opts.settings.config.root.toString(), entry)));
      promises.push(
        limit(async () => {
          const data = await fsMod.promises.readFile(fileURL, { encoding: "utf8" });
          manifest.entries.push([key, checksum(data, fileURL.toString())]);
        })
      );
    }
  }
  const [lockfiles, configs] = await Promise.all([
    lockfilesHash(opts.settings.config.root),
    configHash(opts.settings.config.root)
  ]);
  manifest.lockfiles = lockfiles;
  manifest.configs = configs;
  await Promise.all(promises);
  return manifest;
}
async function pushBufferInto(fileURL, buffers) {
  try {
    const handle = await fsMod.promises.open(fileURL, "r");
    const data = await handle.readFile();
    buffers.push(data);
    await handle.close();
  } catch {
  }
}
async function lockfilesHash(root) {
  const lockfiles = ["package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb"];
  const datas = [];
  const promises = [];
  for (const lockfileName of lockfiles) {
    const fileURL = new URL(`./${lockfileName}`, root);
    promises.push(pushBufferInto(fileURL, datas));
  }
  await Promise.all(promises);
  return checksum(...datas);
}
async function configHash(root) {
  const configFileNames = configPaths;
  for (const configPath of configFileNames) {
    try {
      const fileURL = new URL(`./${configPath}`, root);
      const data = await fsMod.promises.readFile(fileURL);
      const hash = checksum(data);
      return hash;
    } catch {
    }
  }
  return checksum(`export default {}`);
}
function checksum(...datas) {
  const hash = createHash("sha1");
  datas.forEach((data) => hash.update(data));
  return hash.digest("base64");
}
function collectionTypeToFlag(type) {
  const name = type[0].toUpperCase() + type.slice(1);
  return `astro${name}CollectionEntry`;
}
async function copyContentToCache(opts) {
  const { config } = opts.settings;
  const distContentRoot = getContentRoot(config);
  const contentCacheDir = getContentCacheDir(config);
  const cacheTmp = getCacheTmp(contentCacheDir);
  await fsMod.promises.mkdir(cacheTmp, { recursive: true });
  await copyFiles(distContentRoot, cacheTmp, true);
  await copyFiles(cacheTmp, contentCacheDir);
  let files = [];
  await Promise.all([
    glob(`**/*.{mjs,json}`, {
      cwd: fileURLToPath(cacheTmp)
    }).then((f) => files.push(...f.map((file) => CONTENT_PATH + file))),
    glob(`**/*.{mjs,json}`, {
      cwd: fileURLToPath(new URL("./" + CHUNKS_PATH, config.outDir))
    }).then((f) => files.push(...f.map((file) => CHUNKS_PATH + file)))
  ]);
  await fsMod.promises.rm(cacheTmp, { recursive: true, force: true });
  return files;
}
function pluginContent(opts, internals) {
  const { cacheDir, outDir } = opts.settings.config;
  const chunksFolder = "./" + CHUNKS_PATH;
  const assetsFolder = "./" + appendForwardSlash(opts.settings.config.build.assets);
  const cachedBuildOutput = [
    { cached: new URL(chunksFolder, cacheDir), dist: new URL(chunksFolder, outDir) },
    { cached: new URL(assetsFolder, cacheDir), dist: new URL(assetsFolder, outDir) }
  ];
  return {
    targets: ["server"],
    hooks: {
      async "build:before"() {
        if (!isContentCollectionsCacheEnabled(opts.settings.config)) {
          return { vitePlugin: void 0 };
        }
        const lookupMap = await generateLookupMap({ settings: opts.settings, fs: fsMod });
        return {
          vitePlugin: vitePluginContent(opts, lookupMap, internals, cachedBuildOutput)
        };
      },
      async "build:post"() {
        if (!isContentCollectionsCacheEnabled(opts.settings.config)) {
          return;
        }
        const promises = [];
        for (const { cached, dist } of cachedBuildOutput) {
          if (fsMod.existsSync(dist)) {
            promises.push(copyFiles(dist, cached, true));
          }
        }
        if (promises.length) await Promise.all(promises);
      }
    }
  };
}
export {
  copyContentToCache,
  pluginContent
};
