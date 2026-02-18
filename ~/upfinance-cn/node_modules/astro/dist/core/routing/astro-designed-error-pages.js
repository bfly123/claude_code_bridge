import notFoundTemplate from "../../template/4xx.js";
import { DEFAULT_404_COMPONENT, DEFAULT_500_COMPONENT } from "../constants.js";
const DEFAULT_404_ROUTE = {
  component: DEFAULT_404_COMPONENT,
  generate: () => "",
  params: [],
  pattern: /\/404/,
  prerender: false,
  pathname: "/404",
  segments: [[{ content: "404", dynamic: false, spread: false }]],
  type: "page",
  route: "/404",
  fallbackRoutes: [],
  isIndex: false
};
const DEFAULT_500_ROUTE = {
  component: DEFAULT_500_COMPONENT,
  generate: () => "",
  params: [],
  pattern: /\/500/,
  prerender: false,
  pathname: "/500",
  segments: [[{ content: "500", dynamic: false, spread: false }]],
  type: "page",
  route: "/500",
  fallbackRoutes: [],
  isIndex: false
};
function ensure404Route(manifest) {
  if (!manifest.routes.some((route) => route.route === "/404")) {
    manifest.routes.push(DEFAULT_404_ROUTE);
  }
  return manifest;
}
async function default404Page({ pathname }) {
  return new Response(
    notFoundTemplate({
      statusCode: 404,
      title: "Not found",
      tabTitle: "404: Not Found",
      pathname
    }),
    { status: 404, headers: { "Content-Type": "text/html; charset=utf-8" } }
  );
}
default404Page.isAstroComponentFactory = true;
const default404Instance = {
  default: default404Page
};
export {
  DEFAULT_404_ROUTE,
  DEFAULT_500_ROUTE,
  default404Instance,
  ensure404Route
};
