import { normalizePath } from "vite";
import { hasSpecialQueries, normalizeFilename } from "../vite-plugin-utils/index.js";
import { compileAstro } from "./compile.js";
import { handleHotUpdate } from "./hmr.js";
import { parseAstroRequest } from "./query.js";
import { loadId } from "./utils.js";
import { getAstroMetadata } from "./metadata.js";
const astroFileToCompileMetadataWeakMap = /* @__PURE__ */ new WeakMap();
function astro({ settings, logger }) {
  const { config } = settings;
  let server;
  let compile;
  let astroFileToCompileMetadata = /* @__PURE__ */ new Map();
  const srcRootWeb = config.srcDir.pathname.slice(config.root.pathname.length - 1);
  const isBrowserPath = (path) => path.startsWith(srcRootWeb) && srcRootWeb !== "/";
  const prePlugin = {
    name: "astro:build",
    enforce: "pre",
    // run transforms before other plugins can
    configResolved(viteConfig) {
      compile = (code, filename) => {
        return compileAstro({
          compileProps: {
            astroConfig: config,
            viteConfig,
            preferences: settings.preferences,
            filename,
            source: code
          },
          astroFileToCompileMetadata,
          logger
        });
      };
    },
    configureServer(_server) {
      server = _server;
      server.watcher.on("unlink", (filename) => {
        astroFileToCompileMetadata.delete(filename);
      });
    },
    buildStart() {
      astroFileToCompileMetadata = /* @__PURE__ */ new Map();
      if (astroFileToCompileMetadataWeakMap.has(config)) {
        astroFileToCompileMetadata = astroFileToCompileMetadataWeakMap.get(config);
      } else {
        astroFileToCompileMetadataWeakMap.set(config, astroFileToCompileMetadata);
      }
    },
    async load(id, opts) {
      const parsedId = parseAstroRequest(id);
      const query = parsedId.query;
      if (!query.astro) {
        return null;
      }
      const filename = normalizePath(normalizeFilename(parsedId.filename, config.root));
      let compileMetadata = astroFileToCompileMetadata.get(filename);
      if (!compileMetadata) {
        if (server) {
          const code = await loadId(server.pluginContainer, filename);
          if (code != null) await compile(code, filename);
        } else if (config.experimental.contentCollectionCache) {
          await this.load({
            id: filename,
            resolveDependencies: false
          });
        }
        compileMetadata = astroFileToCompileMetadata.get(filename);
      }
      if (!compileMetadata) {
        throw new Error(
          `No cached compile metadata found for "${id}". The main Astro module "${filename}" should have compiled and filled the metadata first, before its virtual modules can be requested.`
        );
      }
      switch (query.type) {
        case "style": {
          if (typeof query.index === "undefined") {
            throw new Error(`Requests for Astro CSS must include an index.`);
          }
          const result = compileMetadata.css[query.index];
          if (!result) {
            throw new Error(`No Astro CSS at index ${query.index}`);
          }
          result.dependencies?.forEach((dep) => this.addWatchFile(dep));
          return {
            code: result.code,
            // This metadata is used by `cssScopeToPlugin` to remove this module from the bundle
            // if the `filename` default export (the Astro component) is unused.
            meta: result.isGlobal ? void 0 : {
              astroCss: {
                cssScopeTo: {
                  [filename]: ["default"]
                }
              }
            }
          };
        }
        case "script": {
          if (typeof query.index === "undefined") {
            throw new Error(`Requests for hoisted scripts must include an index`);
          }
          if (opts?.ssr) {
            return {
              code: `/* client hoisted script, empty in SSR: ${id} */`
            };
          }
          const hoistedScript = compileMetadata.scripts[query.index];
          if (!hoistedScript) {
            throw new Error(`No hoisted script at index ${query.index}`);
          }
          if (hoistedScript.type === "external") {
            const src = hoistedScript.src;
            if (src.startsWith("/") && !isBrowserPath(src)) {
              const publicDir = config.publicDir.pathname.replace(/\/$/, "").split("/").pop() + "/";
              throw new Error(
                `

<script src="${src}"> references an asset in the "${publicDir}" directory. Please add the "is:inline" directive to keep this asset from being bundled.

File: ${id}`
              );
            }
          }
          const result = {
            code: "",
            meta: {
              vite: {
                lang: "ts"
              }
            }
          };
          switch (hoistedScript.type) {
            case "inline": {
              const { code, map } = hoistedScript;
              result.code = appendSourceMap(code, map);
              break;
            }
            case "external": {
              const { src } = hoistedScript;
              result.code = `import "${src}"`;
              break;
            }
          }
          return result;
        }
        case "custom":
        case "template":
        case void 0:
        default:
          return null;
      }
    },
    async transform(source, id) {
      if (hasSpecialQueries(id)) return;
      const parsedId = parseAstroRequest(id);
      if (!parsedId.filename.endsWith(".astro") || parsedId.query.astro) {
        return;
      }
      const filename = normalizePath(parsedId.filename);
      const transformResult = await compile(source, filename);
      const astroMetadata = {
        clientOnlyComponents: transformResult.clientOnlyComponents,
        hydratedComponents: transformResult.hydratedComponents,
        serverComponents: transformResult.serverComponents,
        scripts: transformResult.scripts,
        containsHead: transformResult.containsHead,
        propagation: transformResult.propagation ? "self" : "none",
        pageOptions: {}
      };
      return {
        code: transformResult.code,
        map: transformResult.map,
        meta: {
          astro: astroMetadata,
          vite: {
            // Setting this vite metadata to `ts` causes Vite to resolve .js
            // extensions to .ts files.
            lang: "ts"
          }
        }
      };
    },
    async handleHotUpdate(ctx) {
      return handleHotUpdate(ctx, { logger, astroFileToCompileMetadata });
    }
  };
  const normalPlugin = {
    name: "astro:build:normal",
    resolveId(id) {
      const parsedId = parseAstroRequest(id);
      if (parsedId.query.astro) {
        return id;
      }
    }
  };
  return [prePlugin, normalPlugin];
}
function appendSourceMap(content, map) {
  if (!map) return content;
  return `${content}
//# sourceMappingURL=data:application/json;charset=utf-8;base64,${Buffer.from(
    map
  ).toString("base64")}`;
}
export {
  astro as default,
  getAstroMetadata
};
