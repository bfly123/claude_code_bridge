import { fileURLToPath } from "node:url";
import { transform } from "esbuild";
import { bold } from "kleur/colors";
import MagicString from "magic-string";
import { loadEnv } from "vite";
const importMetaEnvOnlyRe = /\bimport\.meta\.env\b(?!\.)/;
const isValidIdentifierRe = /^[_$a-zA-Z][\w$]*$/;
const exportConstPrerenderRe = /\bexport\s+const\s+prerender\s*=\s*import\.meta\.env\.(.+?)\b/;
function getPrivateEnv(viteConfig, astroConfig) {
  let envPrefixes = ["PUBLIC_"];
  if (viteConfig.envPrefix) {
    envPrefixes = Array.isArray(viteConfig.envPrefix) ? viteConfig.envPrefix : [viteConfig.envPrefix];
  }
  const fullEnv = loadEnv(
    viteConfig.mode,
    viteConfig.envDir ?? fileURLToPath(astroConfig.root),
    ""
  );
  const privateEnv = {};
  for (const key in fullEnv) {
    if (isValidIdentifierRe.test(key) && envPrefixes.every((prefix) => !key.startsWith(prefix))) {
      if (typeof process.env[key] !== "undefined") {
        let value = process.env[key];
        if (typeof value !== "string") {
          value = `${value}`;
        }
        if (value === "0" || value === "1" || value === "true" || value === "false") {
          privateEnv[key] = value;
        } else {
          privateEnv[key] = `process.env.${key}`;
        }
      } else {
        privateEnv[key] = JSON.stringify(fullEnv[key]);
      }
    }
  }
  return privateEnv;
}
function getReferencedPrivateKeys(source, privateEnv) {
  const references = /* @__PURE__ */ new Set();
  for (const key in privateEnv) {
    if (source.includes(key)) {
      references.add(key);
    }
  }
  return references;
}
async function replaceDefine(code, id, define, config) {
  const replacementMarkers = {};
  const env = define["import.meta.env"];
  if (env) {
    const marker = `__astro_import_meta_env${"_".repeat(
      env.length - 23
    )}`;
    replacementMarkers[marker] = env;
    define = { ...define, "import.meta.env": marker };
  }
  const esbuildOptions = config.esbuild || {};
  const result = await transform(code, {
    loader: "js",
    charset: esbuildOptions.charset ?? "utf8",
    platform: "neutral",
    define,
    sourcefile: id,
    sourcemap: config.command === "build" ? !!config.build.sourcemap : true
  });
  for (const marker in replacementMarkers) {
    result.code = result.code.replaceAll(marker, replacementMarkers[marker]);
  }
  return {
    code: result.code,
    map: result.map || null
  };
}
function envVitePlugin({ settings, logger }) {
  let privateEnv;
  let defaultDefines;
  let isDev;
  let devImportMetaEnvPrepend;
  let viteConfig;
  const { config: astroConfig } = settings;
  return {
    name: "astro:vite-plugin-env",
    config(_, { command }) {
      isDev = command !== "build";
    },
    configResolved(resolvedConfig) {
      viteConfig = resolvedConfig;
      const viteDefinePluginIndex = resolvedConfig.plugins.findIndex(
        (p) => p.name === "vite:define"
      );
      if (viteDefinePluginIndex !== -1) {
        const myPluginIndex = resolvedConfig.plugins.findIndex(
          (p) => p.name === "astro:vite-plugin-env"
        );
        if (myPluginIndex !== -1) {
          const myPlugin = resolvedConfig.plugins[myPluginIndex];
          resolvedConfig.plugins.splice(viteDefinePluginIndex, 0, myPlugin);
          resolvedConfig.plugins.splice(myPluginIndex, 1);
        }
      }
    },
    transform(source, id, options) {
      if (!options?.ssr || !source.includes("import.meta.env")) {
        return;
      }
      privateEnv ??= getPrivateEnv(viteConfig, astroConfig);
      if (isDev) {
        const s = new MagicString(source);
        if (!devImportMetaEnvPrepend) {
          devImportMetaEnvPrepend = `Object.assign(import.meta.env,{`;
          for (const key in privateEnv) {
            devImportMetaEnvPrepend += `${key}:${privateEnv[key]},`;
          }
          devImportMetaEnvPrepend += "});";
        }
        s.prepend(devImportMetaEnvPrepend);
        let exportConstPrerenderStr;
        s.replace(exportConstPrerenderRe, (m, key) => {
          if (privateEnv[key] != null) {
            exportConstPrerenderStr = m;
            return `export const prerender = ${privateEnv[key]}`;
          } else {
            return m;
          }
        });
        if (exportConstPrerenderStr) {
          logger.warn(
            "router",
            `Exporting dynamic values from prerender is deprecated. Please use an integration with the "astro:route:setup" hook to update the route's \`prerender\` option instead. This allows for better treeshaking and bundling configuration in the future. See https://docs.astro.build/en/reference/integrations-reference/#astroroutesetup for a migration example.
Found \`${bold(exportConstPrerenderStr)}\` in ${bold(id)}.`
          );
        }
        return {
          code: s.toString(),
          map: s.generateMap({ hires: "boundary" })
        };
      }
      if (!defaultDefines) {
        defaultDefines = {};
        for (const key in privateEnv) {
          defaultDefines[`import.meta.env.${key}`] = privateEnv[key];
        }
      }
      let defines = defaultDefines;
      if (importMetaEnvOnlyRe.test(source)) {
        const references = getReferencedPrivateKeys(source, privateEnv);
        let replacement = `(Object.assign(import.meta.env,{`;
        for (const key of references.values()) {
          replacement += `${key}:${privateEnv[key]},`;
        }
        replacement += "}))";
        defines = {
          ...defaultDefines,
          "import.meta.env": replacement
        };
      }
      return replaceDefine(source, id, defines, viteConfig);
    }
  };
}
export {
  envVitePlugin as default
};
