import fs from "node:fs";
import os from "node:os";
import { bgGreen, black, blue, bold, dim, green, magenta, red } from "kleur/colors";
import PLimit from "p-limit";
import PQueue from "p-queue";
import {
  generateImagesForPath,
  getStaticImageList,
  prepareAssetsGenerationEnv
} from "../../assets/build/generate.js";
import { hasPrerenderedPages } from "../../core/build/internal.js";
import {
  isRelativePath,
  joinPaths,
  removeLeadingForwardSlash,
  removeTrailingForwardSlash
} from "../../core/path.js";
import { toFallbackType, toRoutingStrategy } from "../../i18n/utils.js";
import { runHookBuildGenerated } from "../../integrations/hooks.js";
import { getOutputDirectory } from "../../prerender/utils.js";
import { NoPrerenderedRoutesWithDomains } from "../errors/errors-data.js";
import { AstroError, AstroErrorData } from "../errors/index.js";
import { NOOP_MIDDLEWARE_FN } from "../middleware/noop-middleware.js";
import { getRedirectLocationOrThrow, routeIsRedirect } from "../redirects/index.js";
import { RenderContext } from "../render-context.js";
import { callGetStaticPaths } from "../render/route-cache.js";
import { createRequest } from "../request.js";
import { matchRoute } from "../routing/match.js";
import { stringifyParams } from "../routing/params.js";
import { getOutputFilename, isServerLikeOutput } from "../util.js";
import { getOutDirWithinCwd, getOutFile, getOutFolder } from "./common.js";
import { cssOrder, mergeInlineCss } from "./internal.js";
import { BuildPipeline } from "./pipeline.js";
import { getTimeStat, shouldAppendForwardSlash } from "./util.js";
function createEntryURL(filePath, outFolder) {
  return new URL("./" + filePath + `?time=${Date.now()}`, outFolder);
}
async function generatePages(options, internals) {
  const generatePagesTimer = performance.now();
  const ssr = isServerLikeOutput(options.settings.config);
  let manifest;
  if (ssr) {
    manifest = await BuildPipeline.retrieveManifest(options, internals);
  } else {
    const baseDirectory = getOutputDirectory(options.settings.config);
    const renderersEntryUrl = new URL("renderers.mjs", baseDirectory);
    const renderers = await import(renderersEntryUrl.toString());
    const middleware = internals.middlewareEntryPoint ? await import(internals.middlewareEntryPoint.toString()).then((mod) => mod.onRequest) : NOOP_MIDDLEWARE_FN;
    manifest = createBuildManifest(
      options.settings,
      internals,
      renderers.renderers,
      middleware,
      options.key
    );
  }
  const pipeline = BuildPipeline.create({ internals, manifest, options });
  const { config, logger } = pipeline;
  const outFolder = ssr ? options.settings.config.build.server : getOutDirWithinCwd(options.settings.config.outDir);
  if (ssr && !hasPrerenderedPages(internals)) {
    delete globalThis?.astroAsset?.addStaticImage;
    return;
  }
  const verb = ssr ? "prerendering" : "generating";
  logger.info("SKIP_FORMAT", `
${bgGreen(black(` ${verb} static routes `))}`);
  const builtPaths = /* @__PURE__ */ new Set();
  const pagesToGenerate = pipeline.retrieveRoutesToGenerate();
  if (ssr) {
    for (const [pageData, filePath] of pagesToGenerate) {
      if (pageData.route.prerender) {
        if (config.i18n?.domains && Object.keys(config.i18n.domains).length > 0) {
          throw new AstroError({
            ...NoPrerenderedRoutesWithDomains,
            message: NoPrerenderedRoutesWithDomains.message(pageData.component)
          });
        }
        const ssrEntryPage = await pipeline.retrieveSsrEntry(pageData.route, filePath);
        if (options.settings.adapter?.adapterFeatures?.functionPerRoute) {
          const ssrEntry = ssrEntryPage?.pageModule;
          if (ssrEntry) {
            await generatePage(pageData, ssrEntry, builtPaths, pipeline);
          } else {
            const ssrEntryURLPage = createEntryURL(filePath, outFolder);
            throw new Error(
              `Unable to find the manifest for the module ${ssrEntryURLPage.toString()}. This is unexpected and likely a bug in Astro, please report.`
            );
          }
        } else {
          const ssrEntry = ssrEntryPage;
          await generatePage(pageData, ssrEntry, builtPaths, pipeline);
        }
      }
    }
  } else {
    for (const [pageData, filePath] of pagesToGenerate) {
      const entry = await pipeline.retrieveSsrEntry(pageData.route, filePath);
      await generatePage(pageData, entry, builtPaths, pipeline);
    }
  }
  logger.info(
    null,
    green(`\u2713 Completed in ${getTimeStat(generatePagesTimer, performance.now())}.
`)
  );
  const staticImageList = getStaticImageList();
  if (staticImageList.size) {
    logger.info("SKIP_FORMAT", `${bgGreen(black(` generating optimized images `))}`);
    const totalCount = Array.from(staticImageList.values()).map((x) => x.transforms.size).reduce((a, b) => a + b, 0);
    const cpuCount = os.cpus().length;
    const assetsCreationPipeline = await prepareAssetsGenerationEnv(pipeline, totalCount);
    const queue = new PQueue({ concurrency: Math.max(cpuCount, 1) });
    const assetsTimer = performance.now();
    for (const [originalPath, transforms] of staticImageList) {
      await generateImagesForPath(originalPath, transforms, assetsCreationPipeline, queue);
    }
    await queue.onIdle();
    const assetsTimeEnd = performance.now();
    logger.info(null, green(`\u2713 Completed in ${getTimeStat(assetsTimer, assetsTimeEnd)}.
`));
    delete globalThis?.astroAsset?.addStaticImage;
  }
  await runHookBuildGenerated({ config, logger });
}
const THRESHOLD_SLOW_RENDER_TIME_MS = 500;
async function generatePage(pageData, ssrEntry, builtPaths, pipeline) {
  const { config, logger } = pipeline;
  const pageModulePromise = ssrEntry.page;
  const styles = pageData.styles.sort(cssOrder).map(({ sheet }) => sheet).reduce(mergeInlineCss, []);
  const linkIds = [];
  const scripts = pageData.hoistedScript ?? null;
  if (!pageModulePromise) {
    throw new Error(
      `Unable to find the module for ${pageData.component}. This is unexpected and likely a bug in Astro, please report.`
    );
  }
  const pageModule = await pageModulePromise();
  const generationOptions = {
    pageData,
    linkIds,
    scripts,
    styles,
    mod: pageModule
  };
  async function generatePathWithLogs(path, route, index, paths, isConcurrent) {
    const timeStart = performance.now();
    pipeline.logger.debug("build", `Generating: ${path}`);
    const filePath = getOutputFilename(config, path, pageData.route.type);
    const lineIcon = index === paths.length - 1 && !isConcurrent || paths.length === 1 ? "\u2514\u2500" : "\u251C\u2500";
    if (!isConcurrent) {
      logger.info(null, `  ${blue(lineIcon)} ${dim(filePath)}`, false);
    }
    await generatePath(path, pipeline, generationOptions, route);
    const timeEnd = performance.now();
    const isSlow = timeEnd - timeStart > THRESHOLD_SLOW_RENDER_TIME_MS;
    const timeIncrease = (isSlow ? red : dim)(`(+${getTimeStat(timeStart, timeEnd)})`);
    if (isConcurrent) {
      logger.info(null, `  ${blue(lineIcon)} ${dim(filePath)} ${timeIncrease}`);
    } else {
      logger.info("SKIP_FORMAT", ` ${timeIncrease}`);
    }
  }
  for (const route of eachRouteInRouteData(pageData)) {
    const icon = route.type === "page" || route.type === "redirect" || route.type === "fallback" ? green("\u25B6") : magenta("\u03BB");
    logger.info(null, `${icon} ${getPrettyRouteName(route)}`);
    const paths = await getPathsForRoute(route, pageModule, pipeline, builtPaths);
    if (config.build.concurrency > 1) {
      const limit = PLimit(config.build.concurrency);
      const promises = [];
      for (let i = 0; i < paths.length; i++) {
        const path = paths[i];
        promises.push(limit(() => generatePathWithLogs(path, route, i, paths, true)));
      }
      await Promise.allSettled(promises);
    } else {
      for (let i = 0; i < paths.length; i++) {
        const path = paths[i];
        await generatePathWithLogs(path, route, i, paths, false);
      }
    }
  }
}
function* eachRouteInRouteData(data) {
  yield data.route;
  for (const fallbackRoute of data.route.fallbackRoutes) {
    yield fallbackRoute;
  }
}
async function getPathsForRoute(route, mod, pipeline, builtPaths) {
  const { logger, options, routeCache, serverLike } = pipeline;
  let paths = [];
  if (route.pathname) {
    paths.push(route.pathname);
    builtPaths.add(removeTrailingForwardSlash(route.pathname));
  } else {
    const staticPaths = await callGetStaticPaths({
      mod,
      route,
      routeCache,
      logger,
      ssr: serverLike
    }).catch((err) => {
      logger.error("build", `Failed to call getStaticPaths for ${route.component}`);
      throw err;
    });
    const label = staticPaths.length === 1 ? "page" : "pages";
    logger.debug(
      "build",
      `\u251C\u2500\u2500 ${bold(green("\u221A"))} ${route.component} \u2192 ${magenta(`[${staticPaths.length} ${label}]`)}`
    );
    paths = staticPaths.map((staticPath) => {
      try {
        return stringifyParams(staticPath.params, route);
      } catch (e) {
        if (e instanceof TypeError) {
          throw getInvalidRouteSegmentError(e, route, staticPath);
        }
        throw e;
      }
    }).filter((staticPath) => {
      if (!builtPaths.has(removeTrailingForwardSlash(staticPath))) {
        return true;
      }
      const matchedRoute = matchRoute(staticPath, options.manifest);
      return matchedRoute === route;
    });
    for (const staticPath of paths) {
      builtPaths.add(removeTrailingForwardSlash(staticPath));
    }
  }
  return paths;
}
function getInvalidRouteSegmentError(e, route, staticPath) {
  const invalidParam = /^Expected "([^"]+)"/.exec(e.message)?.[1];
  const received = invalidParam ? staticPath.params[invalidParam] : void 0;
  let hint = "Learn about dynamic routes at https://docs.astro.build/en/core-concepts/routing/#dynamic-routes";
  if (invalidParam && typeof received === "string") {
    const matchingSegment = route.segments.find(
      (segment) => segment[0]?.content === invalidParam
    )?.[0];
    const mightBeMissingSpread = matchingSegment?.dynamic && !matchingSegment?.spread;
    if (mightBeMissingSpread) {
      hint = `If the param contains slashes, try using a rest parameter: **[...${invalidParam}]**. Learn more at https://docs.astro.build/en/core-concepts/routing/#dynamic-routes`;
    }
  }
  return new AstroError({
    ...AstroErrorData.InvalidDynamicRoute,
    message: invalidParam ? AstroErrorData.InvalidDynamicRoute.message(
      route.route,
      JSON.stringify(invalidParam),
      JSON.stringify(received)
    ) : `Generated path for ${route.route} is invalid.`,
    hint
  });
}
function addPageName(pathname, opts) {
  const trailingSlash = opts.settings.config.trailingSlash;
  const buildFormat = opts.settings.config.build.format;
  const pageName = shouldAppendForwardSlash(trailingSlash, buildFormat) ? pathname.replace(/\/?$/, "/").replace(/^\//, "") : pathname.replace(/^\//, "");
  opts.pageNames.push(pageName);
}
function getUrlForPath(pathname, base, origin, format, trailingSlash, routeType) {
  let ending;
  switch (format) {
    case "directory":
    case "preserve": {
      ending = trailingSlash === "never" ? "" : "/";
      break;
    }
    case "file":
    default: {
      ending = ".html";
      break;
    }
  }
  let buildPathname;
  if (pathname === "/" || pathname === "") {
    buildPathname = base;
  } else if (routeType === "endpoint") {
    const buildPathRelative = removeLeadingForwardSlash(pathname);
    buildPathname = joinPaths(base, buildPathRelative);
  } else {
    const buildPathRelative = removeTrailingForwardSlash(removeLeadingForwardSlash(pathname)) + ending;
    buildPathname = joinPaths(base, buildPathRelative);
  }
  const url = new URL(buildPathname, origin);
  return url;
}
async function generatePath(pathname, pipeline, gopts, route) {
  const { mod } = gopts;
  const { config, logger, options } = pipeline;
  logger.debug("build", `Generating: ${pathname}`);
  if (route.type === "page") {
    addPageName(pathname, options);
  }
  if (route.type === "fallback" && // If route is index page, continue rendering. The index page should
  // always be rendered
  route.pathname !== "/" && // Check if there is a translated page with the same path
  Object.values(options.allPages).some((val) => val.route.pattern.test(pathname))) {
    return;
  }
  const url = getUrlForPath(
    pathname,
    config.base,
    options.origin,
    config.build.format,
    config.trailingSlash,
    route.type
  );
  const request = createRequest({
    base: config.base,
    url,
    headers: new Headers(),
    logger,
    staticLike: true
  });
  const renderContext = await RenderContext.create({
    pipeline,
    pathname,
    request,
    routeData: route
  });
  let body;
  let response;
  try {
    response = await renderContext.render(mod);
  } catch (err) {
    if (!AstroError.is(err) && !err.id && typeof err === "object") {
      err.id = route.component;
    }
    throw err;
  }
  if (response.status >= 300 && response.status < 400) {
    if (routeIsRedirect(route) && !config.build.redirects) {
      return;
    }
    const locationSite = getRedirectLocationOrThrow(response.headers);
    const siteURL = config.site;
    const location = siteURL ? new URL(locationSite, siteURL) : locationSite;
    const fromPath = new URL(request.url).pathname;
    const delay = response.status === 302 ? 2 : 0;
    body = `<!doctype html>
<title>Redirecting to: ${location}</title>
<meta http-equiv="refresh" content="${delay};url=${location}">
<meta name="robots" content="noindex">
<link rel="canonical" href="${location}">
<body>
	<a href="${location}">Redirecting from <code>${fromPath}</code> to <code>${location}</code></a>
</body>`;
    if (config.compressHTML === true) {
      body = body.replaceAll("\n", "");
    }
    if (route.type !== "redirect") {
      route.redirect = location.toString();
    }
  } else {
    if (!response.body) return;
    body = Buffer.from(await response.arrayBuffer());
  }
  const outFolder = getOutFolder(config, pathname, route);
  const outFile = getOutFile(config, outFolder, pathname, route);
  route.distURL = outFile;
  await fs.promises.mkdir(outFolder, { recursive: true });
  await fs.promises.writeFile(outFile, body);
}
function getPrettyRouteName(route) {
  if (isRelativePath(route.component)) {
    return route.route;
  } else if (route.component.includes("node_modules/")) {
    return /.*node_modules\/(.+)/.exec(route.component)?.[1] ?? route.component;
  } else {
    return route.component;
  }
}
function createBuildManifest(settings, internals, renderers, middleware, key) {
  let i18nManifest = void 0;
  if (settings.config.i18n) {
    i18nManifest = {
      fallback: settings.config.i18n.fallback,
      fallbackType: toFallbackType(settings.config.i18n.routing),
      strategy: toRoutingStrategy(settings.config.i18n.routing, settings.config.i18n.domains),
      defaultLocale: settings.config.i18n.defaultLocale,
      locales: settings.config.i18n.locales,
      domainLookupTable: {}
    };
  }
  return {
    hrefRoot: settings.config.root.toString(),
    trailingSlash: settings.config.trailingSlash,
    assets: /* @__PURE__ */ new Set(),
    entryModules: Object.fromEntries(internals.entrySpecifierToBundleMap.entries()),
    inlinedScripts: internals.inlinedScripts,
    routes: [],
    adapterName: "",
    clientDirectives: settings.clientDirectives,
    compressHTML: settings.config.compressHTML,
    renderers,
    base: settings.config.base,
    assetsPrefix: settings.config.build.assetsPrefix,
    site: settings.config.site,
    componentMetadata: internals.componentMetadata,
    i18n: i18nManifest,
    buildFormat: settings.config.build.format,
    middleware() {
      return {
        onRequest: middleware
      };
    },
    checkOrigin: settings.config.security?.checkOrigin ?? false,
    key,
    experimentalEnvGetSecretEnabled: false
  };
}
export {
  generatePages
};
