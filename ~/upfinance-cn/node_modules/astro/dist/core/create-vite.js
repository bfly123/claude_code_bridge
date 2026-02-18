import nodeFs from "node:fs";
import { fileURLToPath } from "node:url";
import glob from "fast-glob";
import * as vite from "vite";
import { crawlFrameworkPkgs } from "vitefu";
import { vitePluginActions, vitePluginUserActions } from "../actions/plugins.js";
import { getAssetsPrefix } from "../assets/utils/getAssetsPrefix.js";
import astroAssetsPlugin from "../assets/vite-plugin-assets.js";
import astroContainer from "../container/vite-plugin-container.js";
import {
  astroContentAssetPropagationPlugin,
  astroContentImportPlugin,
  astroContentVirtualModPlugin
} from "../content/index.js";
import { astroEnv } from "../env/vite-plugin-env.js";
import astroInternationalization from "../i18n/vite-plugin-i18n.js";
import astroPrefetch from "../prefetch/vite-plugin-prefetch.js";
import astroDevToolbar from "../toolbar/vite-plugin-dev-toolbar.js";
import astroTransitions from "../transitions/vite-plugin-transitions.js";
import astroPostprocessVitePlugin from "../vite-plugin-astro-postprocess/index.js";
import { vitePluginAstroServer } from "../vite-plugin-astro-server/index.js";
import astroVitePlugin from "../vite-plugin-astro/index.js";
import configAliasVitePlugin from "../vite-plugin-config-alias/index.js";
import envVitePlugin from "../vite-plugin-env/index.js";
import vitePluginFileURL from "../vite-plugin-fileurl/index.js";
import astroHeadPlugin from "../vite-plugin-head/index.js";
import htmlVitePlugin from "../vite-plugin-html/index.js";
import astroIntegrationsContainerPlugin from "../vite-plugin-integrations-container/index.js";
import astroLoadFallbackPlugin from "../vite-plugin-load-fallback/index.js";
import markdownVitePlugin from "../vite-plugin-markdown/index.js";
import mdxVitePlugin from "../vite-plugin-mdx/index.js";
import astroScannerPlugin from "../vite-plugin-scanner/index.js";
import astroScriptsPlugin from "../vite-plugin-scripts/index.js";
import astroScriptsPageSSRPlugin from "../vite-plugin-scripts/page-ssr.js";
import { vitePluginSSRManifest } from "../vite-plugin-ssr-manifest/index.js";
import { createViteLogger } from "./logger/vite.js";
import { vitePluginMiddleware } from "./middleware/vite-plugin.js";
import { joinPaths } from "./path.js";
import { vitePluginServerIslands } from "./server-islands/vite-plugin-server-islands.js";
import { isObject } from "./util.js";
const ALWAYS_NOEXTERNAL = [
  // This is only because Vite's native ESM doesn't resolve "exports" correctly.
  "astro",
  // Vite fails on nested `.astro` imports without bundling
  "astro/components",
  // Handle recommended nanostores. Only @nanostores/preact is required from our testing!
  // Full explanation and related bug report: https://github.com/withastro/astro/pull/3667
  "@nanostores/preact",
  // fontsource packages are CSS that need to be processed
  "@fontsource/*"
];
const ONLY_DEV_EXTERNAL = [
  // Imported by `@astrojs/prism` which exposes `<Prism/>` that is processed by Vite
  "prismjs/components/index.js",
  // Imported by `astro/assets` -> `packages/astro/src/core/logger/core.ts`
  "string-width",
  // Imported by `astro:transitions` -> packages/astro/src/runtime/server/transition.ts
  "cssesc"
];
async function createVite(commandConfig, { settings, logger, mode, command, fs = nodeFs, sync }) {
  const astroPkgsConfig = await crawlFrameworkPkgs({
    root: fileURLToPath(settings.config.root),
    isBuild: mode === "build",
    viteUserConfig: settings.config.vite,
    isFrameworkPkgByJson(pkgJson) {
      if (pkgJson?.astro?.external === true) {
        return false;
      }
      return (
        // Attempt: package relies on `astro`. ✅ Definitely an Astro package
        pkgJson.peerDependencies?.astro || pkgJson.dependencies?.astro || // Attempt: package is tagged with `astro` or `astro-component`. ✅ Likely a community package
        pkgJson.keywords?.includes("astro") || pkgJson.keywords?.includes("astro-component") || // Attempt: package is named `astro-something` or `@scope/astro-something`. ✅ Likely a community package
        /^(?:@[^/]+\/)?astro-/.test(pkgJson.name)
      );
    },
    isFrameworkPkgByName(pkgName) {
      const isNotAstroPkg = isCommonNotAstro(pkgName);
      if (isNotAstroPkg) {
        return false;
      } else {
        return void 0;
      }
    }
  });
  const srcDirPattern = glob.convertPathToPattern(fileURLToPath(settings.config.srcDir));
  const commonConfig = {
    // Tell Vite not to combine config from vite.config.js with our provided inline config
    configFile: false,
    cacheDir: fileURLToPath(new URL("./node_modules/.vite/", settings.config.root)),
    // using local caches allows Astro to be used in monorepos, etc.
    clearScreen: false,
    // we want to control the output, not Vite
    customLogger: createViteLogger(logger, settings.config.vite.logLevel),
    appType: "custom",
    optimizeDeps: {
      // Scan for component code within `srcDir`
      entries: [`${srcDirPattern}**/*.{jsx,tsx,vue,svelte,html,astro}`],
      exclude: ["astro", "node-fetch"]
    },
    plugins: [
      configAliasVitePlugin({ settings }),
      astroLoadFallbackPlugin({ fs, root: settings.config.root }),
      astroVitePlugin({ settings, logger }),
      astroScriptsPlugin({ settings }),
      // The server plugin is for dev only and having it run during the build causes
      // the build to run very slow as the filewatcher is triggered often.
      mode !== "build" && vitePluginAstroServer({ settings, logger, fs }),
      envVitePlugin({ settings, logger }),
      astroEnv({ settings, mode, fs, sync }),
      markdownVitePlugin({ settings, logger }),
      htmlVitePlugin(),
      mdxVitePlugin(),
      astroPostprocessVitePlugin(),
      astroIntegrationsContainerPlugin({ settings, logger }),
      astroScriptsPageSSRPlugin({ settings }),
      astroHeadPlugin(),
      astroScannerPlugin({ settings, logger }),
      astroContentVirtualModPlugin({ fs, settings }),
      astroContentImportPlugin({ fs, settings, logger }),
      astroContentAssetPropagationPlugin({ mode, settings }),
      vitePluginMiddleware({ settings }),
      vitePluginSSRManifest(),
      astroAssetsPlugin({ settings, logger, mode }),
      astroPrefetch({ settings }),
      astroTransitions({ settings }),
      astroDevToolbar({ settings, logger }),
      vitePluginFileURL(),
      astroInternationalization({ settings }),
      vitePluginActions({ fs, settings }),
      vitePluginUserActions({ settings }),
      settings.config.experimental.serverIslands && vitePluginServerIslands({ settings }),
      astroContainer()
    ],
    publicDir: fileURLToPath(settings.config.publicDir),
    root: fileURLToPath(settings.config.root),
    envPrefix: settings.config.vite?.envPrefix ?? "PUBLIC_",
    define: {
      "import.meta.env.SITE": stringifyForDefine(settings.config.site),
      "import.meta.env.BASE_URL": stringifyForDefine(settings.config.base),
      "import.meta.env.ASSETS_PREFIX": stringifyForDefine(settings.config.build.assetsPrefix)
    },
    server: {
      hmr: process.env.NODE_ENV === "test" || process.env.NODE_ENV === "production" ? false : void 0,
      // disable HMR for test
      watch: {
        // Prevent watching during the build to speed it up
        ignored: mode === "build" ? ["**"] : void 0
      }
    },
    resolve: {
      alias: [
        {
          // This is needed for Deno compatibility, as the non-browser version
          // of this module depends on Node `crypto`
          find: "randombytes",
          replacement: "randombytes/browser"
        },
        {
          // Typings are imported from 'astro' (e.g. import { Type } from 'astro')
          find: /^astro$/,
          replacement: fileURLToPath(new URL("../@types/astro.js", import.meta.url))
        },
        {
          find: "astro:middleware",
          replacement: "astro/virtual-modules/middleware.js"
        },
        {
          find: "astro:schema",
          replacement: "astro/zod"
        },
        {
          find: "astro:components",
          replacement: "astro/components"
        }
      ],
      conditions: ["astro"],
      // Astro imports in third-party packages should use the same version as root
      dedupe: ["astro"]
    },
    ssr: {
      noExternal: [...ALWAYS_NOEXTERNAL, ...astroPkgsConfig.ssr.noExternal],
      external: [...mode === "dev" ? ONLY_DEV_EXTERNAL : [], ...astroPkgsConfig.ssr.external]
    },
    build: { assetsDir: settings.config.build.assets }
  };
  const assetsPrefix = settings.config.build.assetsPrefix;
  if (assetsPrefix) {
    commonConfig.experimental = {
      renderBuiltUrl(filename, { type, hostType }) {
        if (type === "asset") {
          return joinPaths(getAssetsPrefix(`.${hostType}`, assetsPrefix), filename);
        }
      }
    };
  }
  let result = commonConfig;
  if (command && settings.config.vite?.plugins) {
    let { plugins, ...rest } = settings.config.vite;
    const applyToFilter = command === "build" ? "serve" : "build";
    const applyArgs = [
      { ...settings.config.vite, mode },
      { command: command === "dev" ? "serve" : command, mode }
    ];
    plugins = plugins.flat(Infinity).filter((p) => {
      if (!p || p?.apply === applyToFilter) {
        return false;
      }
      if (typeof p.apply === "function") {
        return p.apply(applyArgs[0], applyArgs[1]);
      }
      return true;
    });
    result = vite.mergeConfig(result, { ...rest, plugins });
  } else {
    result = vite.mergeConfig(result, settings.config.vite || {});
  }
  result = vite.mergeConfig(result, commandConfig);
  return result;
}
const COMMON_DEPENDENCIES_NOT_ASTRO = [
  "autoprefixer",
  "react",
  "react-dom",
  "preact",
  "preact-render-to-string",
  "vue",
  "svelte",
  "solid-js",
  "lit",
  "cookie",
  "dotenv",
  "esbuild",
  "eslint",
  "jest",
  "postcss",
  "prettier",
  "astro",
  "tslib",
  "typescript",
  "vite"
];
const COMMON_PREFIXES_NOT_ASTRO = [
  "@webcomponents/",
  "@fontsource/",
  "@postcss-plugins/",
  "@rollup/",
  "@astrojs/renderer-",
  "@types/",
  "@typescript-eslint/",
  "eslint-",
  "jest-",
  "postcss-plugin-",
  "prettier-plugin-",
  "remark-",
  "rehype-",
  "rollup-plugin-",
  "vite-plugin-"
];
function isCommonNotAstro(dep) {
  return COMMON_DEPENDENCIES_NOT_ASTRO.includes(dep) || COMMON_PREFIXES_NOT_ASTRO.some(
    (prefix) => prefix.startsWith("@") ? dep.startsWith(prefix) : dep.substring(dep.lastIndexOf("/") + 1).startsWith(prefix)
    // check prefix omitting @scope/
  );
}
function stringifyForDefine(value) {
  return typeof value === "string" || isObject(value) ? JSON.stringify(value) : "undefined";
}
export {
  createVite
};
