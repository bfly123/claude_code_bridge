import { removeTrailingForwardSlash } from "../core/path.js";
import { runWithErrorHandling } from "./controller.js";
import { recordServerError } from "./error.js";
import { handle500Response } from "./response.js";
import { handleRoute, matchRoute } from "./route.js";
async function handleRequest({
  pipeline,
  manifestData,
  controller,
  incomingRequest,
  incomingResponse
}) {
  const { config, loader } = pipeline;
  const origin = `${loader.isHttps() ? "https" : "http"}://${incomingRequest.headers[":authority"] ?? incomingRequest.headers.host}`;
  const url = new URL(origin + incomingRequest.url);
  let pathname;
  if (config.trailingSlash === "never" && !incomingRequest.url) {
    pathname = "";
  } else {
    pathname = url.pathname;
  }
  url.pathname = removeTrailingForwardSlash(config.base) + url.pathname;
  let body = void 0;
  if (!(incomingRequest.method === "GET" || incomingRequest.method === "HEAD")) {
    let bytes = [];
    await new Promise((resolve) => {
      incomingRequest.on("data", (part) => {
        bytes.push(part);
      });
      incomingRequest.on("end", resolve);
    });
    body = Buffer.concat(bytes);
  }
  await runWithErrorHandling({
    controller,
    pathname,
    async run() {
      const matchedRoute = await matchRoute(pathname, manifestData, pipeline);
      const resolvedPathname = matchedRoute?.resolvedPathname ?? pathname;
      return await handleRoute({
        matchedRoute,
        url,
        pathname: resolvedPathname,
        body,
        pipeline,
        manifestData,
        incomingRequest,
        incomingResponse
      });
    },
    onError(_err) {
      const { error, errorWithMetadata } = recordServerError(loader, config, pipeline, _err);
      handle500Response(loader, incomingResponse, errorWithMetadata);
      return error;
    }
  });
}
export {
  handleRequest
};
