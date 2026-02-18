import { extname } from "node:path";
import { bold } from "kleur/colors";
import { normalizePath } from "vite";
import { isEndpoint, isPage, isServerLikeOutput } from "../core/util.js";
import { rootRelativePath } from "../core/viteUtils.js";
import { runHookRouteSetup } from "../integrations/hooks.js";
import { getPrerenderDefault } from "../prerender/utils.js";
import { scan } from "./scan.js";
const KNOWN_FILE_EXTENSIONS = [".astro", ".js", ".ts"];
function astroScannerPlugin({
  settings,
  logger
}) {
  return {
    name: "astro:scanner",
    enforce: "post",
    async transform(code, id, options) {
      if (!options?.ssr) return;
      const filename = normalizePath(id);
      let fileURL;
      try {
        fileURL = new URL(`file://${filename}`);
      } catch {
        return;
      }
      const fileIsPage = isPage(fileURL, settings);
      const fileIsEndpoint = isEndpoint(fileURL, settings);
      if (!(fileIsPage || fileIsEndpoint)) return;
      const pageOptions = await getPageOptions(code, id, fileURL, settings, logger);
      if (!pageOptions.prerender && isServerLikeOutput(settings.config) && code.includes("getStaticPaths") && // this should only be valid for `.astro`, `.js` and `.ts` files
      KNOWN_FILE_EXTENSIONS.includes(extname(filename))) {
        logger.warn(
          "router",
          `getStaticPaths() ignored in dynamic page ${bold(
            rootRelativePath(settings.config.root, fileURL, true)
          )}. Add \`export const prerender = true;\` to prerender the page as static HTML during the build process.`
        );
      }
      const { meta = {} } = this.getModuleInfo(id) ?? {};
      return {
        code,
        map: null,
        meta: {
          ...meta,
          astro: {
            ...meta.astro ?? { hydratedComponents: [], clientOnlyComponents: [], scripts: [] },
            pageOptions
          }
        }
      };
    }
  };
}
async function getPageOptions(code, id, fileURL, settings, logger) {
  const fileUrlStr = fileURL.toString();
  const injectedRoute = settings.resolvedInjectedRoutes.find(
    (route2) => route2.resolvedEntryPoint && fileUrlStr === route2.resolvedEntryPoint.toString()
  );
  const pageOptions = injectedRoute?.prerender != null ? { prerender: injectedRoute.prerender } : await scan(code, id, settings);
  const route = {
    component: rootRelativePath(settings.config.root, fileURL, false),
    prerender: pageOptions.prerender
  };
  await runHookRouteSetup({ route, settings, logger });
  pageOptions.prerender = route.prerender;
  if (typeof pageOptions.prerender === "undefined") {
    pageOptions.prerender = getPrerenderDefault(settings.config);
  }
  return pageOptions;
}
export {
  astroScannerPlugin as default
};
