import fs from "node:fs";
import path, { extname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { teardown } from "@astrojs/compiler";
import glob from "fast-glob";
import { bgGreen, bgMagenta, black, green } from "kleur/colors";
import * as vite from "vite";
import { PROPAGATED_ASSET_FLAG } from "../../content/consts.js";
import {
  getSymlinkedContentCollections,
  hasAnyContentFlag,
  reverseSymlink
} from "../../content/utils.js";
import {
  createBuildInternals,
  getPageDatasWithPublicKey
} from "../../core/build/internal.js";
import { emptyDir, removeEmptyDirs } from "../../core/fs/index.js";
import { appendForwardSlash, prependForwardSlash, removeFileExtension } from "../../core/path.js";
import { isModeServerWithNoAdapter, isServerLikeOutput } from "../../core/util.js";
import { runHookBuildSetup } from "../../integrations/hooks.js";
import { getOutputDirectory } from "../../prerender/utils.js";
import { PAGE_SCRIPT_ID } from "../../vite-plugin-scripts/index.js";
import { AstroError, AstroErrorData } from "../errors/index.js";
import { routeIsRedirect } from "../redirects/index.js";
import { getOutDirWithinCwd } from "./common.js";
import { CHUNKS_PATH } from "./consts.js";
import { generatePages } from "./generate.js";
import { trackPageData } from "./internal.js";
import { createPluginContainer } from "./plugin.js";
import { registerAllPlugins } from "./plugins/index.js";
import { copyContentToCache } from "./plugins/plugin-content.js";
import { RESOLVED_SSR_MANIFEST_VIRTUAL_MODULE_ID } from "./plugins/plugin-manifest.js";
import { ASTRO_PAGE_RESOLVED_MODULE_ID } from "./plugins/plugin-pages.js";
import { RESOLVED_RENDERERS_MODULE_ID } from "./plugins/plugin-renderers.js";
import { RESOLVED_SPLIT_MODULE_ID, RESOLVED_SSR_VIRTUAL_MODULE_ID } from "./plugins/plugin-ssr.js";
import { ASTRO_PAGE_EXTENSION_POST_PATTERN } from "./plugins/util.js";
import { encodeName, getTimeStat, viteBuildReturnToRollupOutputs } from "./util.js";
async function viteBuild(opts) {
  const { allPages, settings, logger } = opts;
  if (isModeServerWithNoAdapter(opts.settings)) {
    throw new AstroError(AstroErrorData.NoAdapterInstalled);
  }
  settings.timer.start("SSR build");
  const pageInput = /* @__PURE__ */ new Set();
  const internals = createBuildInternals();
  for (const pageData of Object.values(allPages)) {
    const astroModuleURL = new URL("./" + pageData.component, settings.config.root);
    const astroModuleId = prependForwardSlash(pageData.component);
    trackPageData(internals, pageData.component, pageData, astroModuleId, astroModuleURL);
    if (!routeIsRedirect(pageData.route)) {
      pageInput.add(astroModuleId);
    }
  }
  if (settings.config?.vite?.build?.emptyOutDir !== false) {
    emptyDir(settings.config.outDir, new Set(".git"));
  }
  const container = createPluginContainer(opts, internals);
  registerAllPlugins(container);
  const ssrTime = performance.now();
  opts.logger.info("build", `Building ${settings.config.output} entrypoints...`);
  const ssrOutput = await ssrBuild(opts, internals, pageInput, container, logger);
  opts.logger.info("build", green(`\u2713 Completed in ${getTimeStat(ssrTime, performance.now())}.`));
  settings.timer.end("SSR build");
  settings.timer.start("Client build");
  const rendererClientEntrypoints = settings.renderers.map((r) => r.clientEntrypoint).filter((a) => typeof a === "string");
  const clientInput = /* @__PURE__ */ new Set([
    ...internals.cachedClientEntries,
    ...internals.discoveredHydratedComponents.keys(),
    ...internals.discoveredClientOnlyComponents.keys(),
    ...rendererClientEntrypoints,
    ...internals.discoveredScripts
  ]);
  if (settings.scripts.some((script) => script.stage === "page")) {
    clientInput.add(PAGE_SCRIPT_ID);
  }
  const clientOutput = await clientBuild(opts, internals, clientInput, container);
  const ssrOutputs = viteBuildReturnToRollupOutputs(ssrOutput);
  const clientOutputs = viteBuildReturnToRollupOutputs(clientOutput ?? []);
  await runPostBuildHooks(container, ssrOutputs, clientOutputs);
  settings.timer.end("Client build");
  internals.ssrEntryChunk = void 0;
  if (opts.teardownCompiler) {
    teardown();
  }
  const ssrOutputChunkNames = [];
  for (const output of ssrOutputs) {
    for (const chunk of output.output) {
      if (chunk.type === "chunk") {
        ssrOutputChunkNames.push(chunk.fileName);
      }
    }
  }
  return { internals, ssrOutputChunkNames };
}
async function staticBuild(opts, internals, ssrOutputChunkNames) {
  const { settings } = opts;
  if (settings.config.output === "static") {
    settings.timer.start("Static generate");
    await generatePages(opts, internals);
    await cleanServerOutput(opts, ssrOutputChunkNames, internals);
    settings.timer.end("Static generate");
  } else if (isServerLikeOutput(settings.config)) {
    settings.timer.start("Server generate");
    await generatePages(opts, internals);
    await cleanStaticOutput(opts, internals);
    await ssrMoveAssets(opts);
    settings.timer.end("Server generate");
  }
}
async function ssrBuild(opts, internals, input, container, logger) {
  const buildID = Date.now().toString();
  const { allPages, settings, viteConfig } = opts;
  const ssr = isServerLikeOutput(settings.config);
  const out = getOutputDirectory(settings.config);
  const routes = Object.values(allPages).flatMap((pageData) => pageData.route);
  const isContentCache = !ssr && settings.config.experimental.contentCollectionCache;
  const { lastVitePlugins, vitePlugins } = await container.runBeforeHook("server", input);
  const contentDir = new URL("./src/content", settings.config.root);
  const symlinks = await getSymlinkedContentCollections({ contentDir, logger, fs });
  const viteBuildConfig = {
    ...viteConfig,
    mode: viteConfig.mode || "production",
    logLevel: viteConfig.logLevel ?? "error",
    build: {
      target: "esnext",
      // Vite defaults cssMinify to false in SSR by default, but we want to minify it
      // as the CSS generated are used and served to the client.
      cssMinify: viteConfig.build?.minify == null ? true : !!viteConfig.build?.minify,
      ...viteConfig.build,
      emptyOutDir: false,
      manifest: false,
      outDir: fileURLToPath(out),
      copyPublicDir: !ssr,
      rollupOptions: {
        ...viteConfig.build?.rollupOptions,
        // Setting as `exports-only` allows us to safely delete inputs that are only used during prerendering
        preserveEntrySignatures: "exports-only",
        input: [],
        output: {
          hoistTransitiveImports: isContentCache,
          format: "esm",
          minifyInternalExports: !isContentCache,
          // Server chunks can't go in the assets (_astro) folder
          // We need to keep these separate
          chunkFileNames(chunkInfo) {
            const { name } = chunkInfo;
            let prefix = CHUNKS_PATH;
            let suffix = "_[hash].mjs";
            if (isContentCache) {
              prefix += `${buildID}/`;
              suffix = ".mjs";
              if (name.includes("/content/")) {
                const parts = name.split("/");
                if (parts.at(1) === "content") {
                  return encodeName(parts.slice(1).join("/"));
                }
              }
            }
            if (name.includes(ASTRO_PAGE_EXTENSION_POST_PATTERN)) {
              const [sanitizedName] = name.split(ASTRO_PAGE_EXTENSION_POST_PATTERN);
              return [prefix, sanitizedName, suffix].join("");
            }
            if (name.startsWith("pages/")) {
              const sanitizedName = name.split(".")[0];
              return [prefix, sanitizedName, suffix].join("");
            }
            const encoded = encodeName(name);
            return [prefix, encoded, suffix].join("");
          },
          assetFileNames: `${settings.config.build.assets}/[name].[hash][extname]`,
          ...viteConfig.build?.rollupOptions?.output,
          entryFileNames(chunkInfo) {
            if (chunkInfo.facadeModuleId?.startsWith(ASTRO_PAGE_RESOLVED_MODULE_ID)) {
              return makeAstroPageEntryPointFileName(
                ASTRO_PAGE_RESOLVED_MODULE_ID,
                chunkInfo.facadeModuleId,
                routes
              );
            } else if (chunkInfo.facadeModuleId?.startsWith(RESOLVED_SPLIT_MODULE_ID)) {
              return makeSplitEntryPointFileName(chunkInfo.facadeModuleId, routes);
            } else if (chunkInfo.facadeModuleId === RESOLVED_SSR_VIRTUAL_MODULE_ID) {
              return opts.settings.config.build.serverEntry;
            } else if (chunkInfo.facadeModuleId === RESOLVED_RENDERERS_MODULE_ID) {
              return "renderers.mjs";
            } else if (chunkInfo.facadeModuleId === RESOLVED_SSR_MANIFEST_VIRTUAL_MODULE_ID) {
              return "manifest_[hash].mjs";
            } else if (chunkInfo.facadeModuleId === settings.adapter?.serverEntrypoint) {
              return "adapter_[hash].mjs";
            } else if (settings.config.experimental.contentCollectionCache && chunkInfo.facadeModuleId && hasAnyContentFlag(chunkInfo.facadeModuleId)) {
              const moduleId = reverseSymlink({
                symlinks,
                entry: chunkInfo.facadeModuleId,
                contentDir
              });
              const [srcRelative, flag] = moduleId.split("/src/")[1].split("?");
              if (flag === PROPAGATED_ASSET_FLAG) {
                return encodeName(`${removeFileExtension(srcRelative)}.entry.mjs`);
              }
              return encodeName(`${removeFileExtension(srcRelative)}.mjs`);
            } else {
              return "[name].mjs";
            }
          }
        }
      },
      ssr: true,
      ssrEmitAssets: true,
      // improve build performance
      minify: false,
      modulePreload: { polyfill: false },
      reportCompressedSize: false
    },
    plugins: [...vitePlugins, ...viteConfig.plugins || [], ...lastVitePlugins],
    envPrefix: viteConfig.envPrefix ?? "PUBLIC_",
    base: settings.config.base
  };
  const updatedViteBuildConfig = await runHookBuildSetup({
    config: settings.config,
    pages: getPageDatasWithPublicKey(internals.pagesByKeys),
    vite: viteBuildConfig,
    target: "server",
    logger: opts.logger
  });
  return await vite.build(updatedViteBuildConfig);
}
async function clientBuild(opts, internals, input, container) {
  const { settings, viteConfig } = opts;
  const ssr = isServerLikeOutput(settings.config);
  const out = ssr ? settings.config.build.client : getOutDirWithinCwd(settings.config.outDir);
  if (!input.size) {
    if (ssr) {
      await copyFiles(settings.config.publicDir, out, true);
    }
    return null;
  }
  const { lastVitePlugins, vitePlugins } = await container.runBeforeHook("client", input);
  opts.logger.info("SKIP_FORMAT", `
${bgGreen(black(" building client (vite) "))}`);
  const viteBuildConfig = {
    ...viteConfig,
    mode: viteConfig.mode || "production",
    build: {
      target: "esnext",
      ...viteConfig.build,
      emptyOutDir: false,
      outDir: fileURLToPath(out),
      copyPublicDir: ssr,
      rollupOptions: {
        ...viteConfig.build?.rollupOptions,
        input: Array.from(input),
        output: {
          format: "esm",
          entryFileNames: `${settings.config.build.assets}/[name].[hash].js`,
          chunkFileNames: `${settings.config.build.assets}/[name].[hash].js`,
          assetFileNames: `${settings.config.build.assets}/[name].[hash][extname]`,
          ...viteConfig.build?.rollupOptions?.output
        },
        preserveEntrySignatures: "exports-only"
      }
    },
    plugins: [...vitePlugins, ...viteConfig.plugins || [], ...lastVitePlugins],
    envPrefix: viteConfig.envPrefix ?? "PUBLIC_",
    base: settings.config.base
  };
  await runHookBuildSetup({
    config: settings.config,
    pages: getPageDatasWithPublicKey(internals.pagesByKeys),
    vite: viteBuildConfig,
    target: "client",
    logger: opts.logger
  });
  const buildResult = await vite.build(viteBuildConfig);
  return buildResult;
}
async function runPostBuildHooks(container, ssrOutputs, clientOutputs) {
  const mutations = await container.runPostHook(ssrOutputs, clientOutputs);
  const config = container.options.settings.config;
  const build = container.options.settings.config.build;
  for (const [fileName, mutation] of mutations) {
    const root = isServerLikeOutput(config) ? mutation.targets.includes("server") ? build.server : build.client : getOutDirWithinCwd(config.outDir);
    const fullPath = path.join(fileURLToPath(root), fileName);
    const fileURL = pathToFileURL(fullPath);
    await fs.promises.mkdir(new URL("./", fileURL), { recursive: true });
    await fs.promises.writeFile(fileURL, mutation.code, "utf-8");
  }
}
async function cleanStaticOutput(opts, internals) {
  const ssr = isServerLikeOutput(opts.settings.config);
  const out = ssr ? opts.settings.config.build.server : getOutDirWithinCwd(opts.settings.config.outDir);
  await Promise.all(
    internals.prerenderOnlyChunks.map(async (chunk) => {
      const url = new URL(chunk.fileName, out);
      try {
        if (chunk.isEntry || chunk.isDynamicEntry) {
          await fs.promises.writeFile(
            url,
            "// Contents removed by Astro as it's used for prerendering only",
            "utf-8"
          );
        } else {
          await fs.promises.unlink(url);
        }
      } catch {
      }
    })
  );
}
async function cleanServerOutput(opts, ssrOutputChunkNames, internals) {
  const out = getOutDirWithinCwd(opts.settings.config.outDir);
  const files = ssrOutputChunkNames.filter((f) => f.endsWith(".mjs"));
  if (internals.manifestFileName) {
    files.push(internals.manifestFileName);
  }
  if (files.length) {
    await Promise.all(
      files.map(async (filename) => {
        const url = new URL(filename, out);
        const map = new URL(url + ".map");
        await Promise.all([fs.promises.rm(url), fs.promises.rm(new URL(map)).catch(() => {
        })]);
      })
    );
    removeEmptyDirs(out);
  }
  if (out.toString() !== opts.settings.config.outDir.toString()) {
    const fileNames = await fs.promises.readdir(out);
    await Promise.all(
      fileNames.filter((fileName) => fileName.endsWith(".d.ts")).map((fileName) => fs.promises.rm(new URL(fileName, out)))
    );
    await copyFiles(out, opts.settings.config.outDir, true);
    await fs.promises.rm(out, { recursive: true });
    return;
  }
}
async function copyFiles(fromFolder, toFolder, includeDotfiles = false) {
  const files = await glob("**/*", {
    cwd: fileURLToPath(fromFolder),
    dot: includeDotfiles
  });
  if (files.length === 0) return;
  return await Promise.all(
    files.map(async function copyFile(filename) {
      const from = new URL(filename, fromFolder);
      const to = new URL(filename, toFolder);
      const lastFolder = new URL("./", to);
      return fs.promises.mkdir(lastFolder, { recursive: true }).then(async function fsCopyFile() {
        const p = await fs.promises.copyFile(from, to, fs.constants.COPYFILE_FICLONE);
        return p;
      });
    })
  );
}
async function ssrMoveAssets(opts) {
  opts.logger.info("build", "Rearranging server assets...");
  const serverRoot = opts.settings.config.output === "static" ? opts.settings.config.build.client : opts.settings.config.build.server;
  const clientRoot = opts.settings.config.build.client;
  const assets = opts.settings.config.build.assets;
  const serverAssets = new URL(`./${assets}/`, appendForwardSlash(serverRoot.toString()));
  const clientAssets = new URL(`./${assets}/`, appendForwardSlash(clientRoot.toString()));
  const files = await glob(`**/*`, {
    cwd: fileURLToPath(serverAssets)
  });
  if (files.length > 0) {
    await Promise.all(
      files.map(async function moveAsset(filename) {
        const currentUrl = new URL(filename, appendForwardSlash(serverAssets.toString()));
        const clientUrl = new URL(filename, appendForwardSlash(clientAssets.toString()));
        const dir = new URL(path.parse(clientUrl.href).dir);
        if (!fs.existsSync(dir)) await fs.promises.mkdir(dir, { recursive: true });
        return fs.promises.rename(currentUrl, clientUrl);
      })
    );
    removeEmptyDirs(serverAssets);
  }
}
function makeAstroPageEntryPointFileName(prefix, facadeModuleId, routes) {
  const pageModuleId = facadeModuleId.replace(prefix, "").replace(ASTRO_PAGE_EXTENSION_POST_PATTERN, ".");
  const route = routes.find((routeData) => routeData.component === pageModuleId);
  const name = route?.route ?? pageModuleId;
  return `pages${name.replace(/\/$/, "/index").replaceAll(/[[\]]/g, "_").replaceAll("...", "---")}.astro.mjs`;
}
function makeSplitEntryPointFileName(facadeModuleId, routes) {
  const filePath = `${makeAstroPageEntryPointFileName(
    RESOLVED_SPLIT_MODULE_ID,
    facadeModuleId,
    routes
  )}`;
  const pathComponents = filePath.split(path.sep);
  const lastPathComponent = pathComponents.pop();
  if (lastPathComponent) {
    const extension = extname(lastPathComponent);
    if (extension.length > 0) {
      const newFileName = `entry.${lastPathComponent}`;
      return [...pathComponents, newFileName].join(path.sep);
    }
  }
  return filePath;
}
export {
  copyFiles,
  makeAstroPageEntryPointFileName,
  makeSplitEntryPointFileName,
  staticBuild,
  viteBuild
};
