import {
  DEFAULT_404_COMPONENT,
  NOOP_MIDDLEWARE_HEADER,
  REROUTE_DIRECTIVE_HEADER,
  REWRITE_DIRECTIVE_HEADER_KEY,
  clientLocalsSymbol
} from "../core/constants.js";
import { AstroErrorData, isAstroError } from "../core/errors/index.js";
import { req } from "../core/messages.js";
import { loadMiddleware } from "../core/middleware/loadMiddleware.js";
import { RenderContext } from "../core/render-context.js";
import { getProps } from "../core/render/index.js";
import { createRequest } from "../core/request.js";
import { matchAllRoutes } from "../core/routing/index.js";
import { getSortedPreloadedMatches } from "../prerender/routing.js";
import { writeSSRResult, writeWebResponse } from "./response.js";
function isLoggedRequest(url) {
  return url !== "/favicon.ico";
}
function getCustom404Route(manifestData) {
  const route404 = /^\/404\/?$/;
  return manifestData.routes.find((r) => route404.test(r.route));
}
function getCustom500Route(manifestData) {
  const route500 = /^\/500\/?$/;
  return manifestData.routes.find((r) => route500.test(r.route));
}
async function matchRoute(pathname, manifestData, pipeline) {
  const { config, logger, routeCache, serverLike, settings } = pipeline;
  const matches = matchAllRoutes(pathname, manifestData);
  const preloadedMatches = await getSortedPreloadedMatches({ pipeline, matches, settings });
  for await (const { preloadedComponent, route: maybeRoute, filePath } of preloadedMatches) {
    try {
      await getProps({
        mod: preloadedComponent,
        routeData: maybeRoute,
        routeCache,
        pathname,
        logger,
        serverLike
      });
      return {
        route: maybeRoute,
        filePath,
        resolvedPathname: pathname,
        preloadedComponent,
        mod: preloadedComponent
      };
    } catch (e) {
      if (isAstroError(e) && e.title === AstroErrorData.NoMatchingStaticPathFound.title) {
        continue;
      }
      throw e;
    }
  }
  const altPathname = pathname.replace(/\/index\.html$/, "/").replace(/\.html$/, "");
  if (altPathname !== pathname) {
    return await matchRoute(altPathname, manifestData, pipeline);
  }
  if (matches.length) {
    const possibleRoutes = matches.flatMap((route) => route.component);
    logger.warn(
      "router",
      `${AstroErrorData.NoMatchingStaticPathFound.message(
        pathname
      )}

${AstroErrorData.NoMatchingStaticPathFound.hint(possibleRoutes)}`
    );
  }
  const custom404 = getCustom404Route(manifestData);
  if (custom404) {
    const filePath = new URL(`./${custom404.component}`, config.root);
    const preloadedComponent = await pipeline.preload(custom404, filePath);
    return {
      route: custom404,
      filePath,
      resolvedPathname: pathname,
      preloadedComponent,
      mod: preloadedComponent
    };
  }
  return void 0;
}
async function handleRoute({
  matchedRoute,
  url,
  pathname,
  body,
  pipeline,
  manifestData,
  incomingRequest,
  incomingResponse
}) {
  const timeStart = performance.now();
  const { config, loader, logger } = pipeline;
  if (!matchedRoute) {
    throw new Error("No route matched, and default 404 route was not found.");
  }
  let request;
  let renderContext;
  let mod = void 0;
  let route;
  const middleware = (await loadMiddleware(loader)).onRequest;
  const locals = Reflect.get(incomingRequest, clientLocalsSymbol);
  const { preloadedComponent } = matchedRoute;
  route = matchedRoute.route;
  request = createRequest({
    base: config.base,
    url,
    headers: incomingRequest.headers,
    method: incomingRequest.method,
    body,
    logger,
    clientAddress: incomingRequest.socket.remoteAddress,
    staticLike: config.output === "static" || route.prerender
  });
  for (const [name, value] of Object.entries(config.server.headers ?? {})) {
    if (value) incomingResponse.setHeader(name, value);
  }
  mod = preloadedComponent;
  renderContext = await RenderContext.create({
    locals,
    pipeline,
    pathname,
    middleware: isDefaultPrerendered404(matchedRoute.route) ? void 0 : middleware,
    request,
    routeData: route
  });
  let response;
  let statusCode = 200;
  let isReroute = false;
  let isRewrite = false;
  try {
    response = await renderContext.render(mod);
    isReroute = response.headers.has(REROUTE_DIRECTIVE_HEADER);
    isRewrite = response.headers.has(REWRITE_DIRECTIVE_HEADER_KEY);
    const statusCodedMatched = getStatusByMatchedRoute(matchedRoute);
    statusCode = isRewrite ? (
      // Ignore `matchedRoute` status for rewrites
      response.status
    ) : (
      // Our internal noop middleware sets a particular header. If the header isn't present, it means that the user have
      // their own middleware, so we need to return what the user returns.
      !response.headers.has(NOOP_MIDDLEWARE_HEADER) && !isReroute ? response.status : statusCodedMatched ?? response.status
    );
  } catch (err) {
    const custom500 = getCustom500Route(manifestData);
    if (!custom500) {
      throw err;
    }
    logger.error("router", err.stack || err.message);
    const filePath500 = new URL(`./${custom500.component}`, config.root);
    const preloaded500Component = await pipeline.preload(custom500, filePath500);
    renderContext.props.error = err;
    response = await renderContext.render(preloaded500Component);
    statusCode = 500;
  }
  if (isLoggedRequest(pathname)) {
    const timeEnd = performance.now();
    logger.info(
      null,
      req({
        url: pathname,
        method: incomingRequest.method,
        statusCode,
        isRewrite,
        reqTime: timeEnd - timeStart
      })
    );
  }
  if (statusCode === 404 && response.headers.get(REROUTE_DIRECTIVE_HEADER) !== "no") {
    const fourOhFourRoute = await matchRoute("/404", manifestData, pipeline);
    if (fourOhFourRoute) {
      renderContext = await RenderContext.create({
        locals,
        pipeline,
        pathname,
        middleware: isDefaultPrerendered404(fourOhFourRoute.route) ? void 0 : middleware,
        request,
        routeData: fourOhFourRoute.route
      });
      response = await renderContext.render(fourOhFourRoute.preloadedComponent);
    }
  }
  if (isReroute) {
    response.headers.delete(REROUTE_DIRECTIVE_HEADER);
  }
  if (isRewrite) {
    response.headers.delete(REROUTE_DIRECTIVE_HEADER);
  }
  if (route.type === "endpoint") {
    await writeWebResponse(incomingResponse, response);
    return;
  }
  if (isRewrite) {
    await writeSSRResult(request, response, incomingResponse);
    return;
  }
  if (response.status < 400 && response.status >= 300) {
    await writeSSRResult(request, response, incomingResponse);
    return;
  }
  if (response.status !== statusCode) {
    response = new Response(response.body, {
      status: statusCode,
      headers: response.headers
    });
  }
  await writeSSRResult(request, response, incomingResponse);
}
function getStatusByMatchedRoute(matchedRoute) {
  if (matchedRoute?.route.route === "/404") return 404;
  if (matchedRoute?.route.route === "/500") return 500;
  return void 0;
}
function isDefaultPrerendered404(route) {
  return route.route === "/404" && route.prerender && route.component === DEFAULT_404_COMPONENT;
}
export {
  handleRoute,
  matchRoute
};
