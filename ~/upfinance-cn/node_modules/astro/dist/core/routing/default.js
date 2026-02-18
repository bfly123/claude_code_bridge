import { DEFAULT_404_COMPONENT } from "../constants.js";
import {
  SERVER_ISLAND_COMPONENT,
  SERVER_ISLAND_ROUTE,
  createEndpoint as createServerIslandEndpoint,
  ensureServerIslandRoute
} from "../server-islands/endpoint.js";
import {
  DEFAULT_404_ROUTE,
  default404Instance,
  ensure404Route
} from "./astro-designed-error-pages.js";
function injectDefaultRoutes(ssrManifest, routeManifest) {
  ensure404Route(routeManifest);
  ensureServerIslandRoute(ssrManifest, routeManifest);
  return routeManifest;
}
function createDefaultRoutes(manifest) {
  const root = new URL(manifest.hrefRoot);
  return [
    {
      instance: default404Instance,
      matchesComponent: (filePath) => filePath.href === new URL(DEFAULT_404_COMPONENT, root).href,
      route: DEFAULT_404_ROUTE.route,
      component: DEFAULT_404_COMPONENT
    },
    {
      instance: createServerIslandEndpoint(manifest),
      matchesComponent: (filePath) => filePath.href === new URL(SERVER_ISLAND_COMPONENT, root).href,
      route: SERVER_ISLAND_ROUTE,
      component: SERVER_ISLAND_COMPONENT
    }
  ];
}
export {
  createDefaultRoutes,
  injectDefaultRoutes
};
